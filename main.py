import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio
from PIL import Image, ImageDraw, ImageFont
import io

# ================= =================
#  Discord Intents and Bot Setup
# ================= =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "bot_data.json"

# ================= =================
#  Database Helper Functions
# ================= =================
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {DATA_FILE}: {e}")
    return {
        "menus": {},
        "staff_stats": {},
        "active_tickets": {},
        "kashf_channel_id": None
    }

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving {DATA_FILE}: {e}")

db_data = load_data()

# ================= =================
#  Profile Card Generation Logic
# ================= =================
def generate_profile_card(member, tickets_count, avg_rating, total_stars):
    width, height = 600, 300
    bg_color = (20, 22, 26)
    card_color = (30, 35, 42)
    accent_color = (114, 137, 218)
    text_color = (255, 255, 255)

    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Draw rounded background card
    draw.rounded_rectangle([20, 20, width - 20, height - 20], radius=15, fill=card_color)

    try:
        font_large = ImageFont.truetype("arial.ttf", 22)
        font_small = ImageFont.truetype("arial.ttf", 16)
    except IOError:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Draw Admin Name
    draw.text((40, 35), f"بطاقة أداء الإداري: {member.name}", fill=text_color, font=font_large)

    # Total Tickets Box
    draw.rounded_rectangle([40, 90, 200, 180], radius=10, fill=(45, 52, 62))
    draw.text((50, 100), "إجمالي التكتات", fill=(180, 180, 180), font=font_small)
    draw.text((50, 130), str(tickets_count), fill=accent_color, font=font_large)

    # Average Rating Box
    draw.rounded_rectangle([215, 90, 375, 180], radius=10, fill=(45, 52, 62))
    draw.text((225, 100), "متوسط التقييم", fill=(180, 180, 180), font=font_small)
    draw.text((225, 130), f"⭐ {avg_rating:.1f}/5.0", fill=(255, 215, 0), font=font_large)

    # Total Stars Box
    draw.rounded_rectangle([390, 90, 550, 180], radius=10, fill=(45, 52, 62))
    draw.text((400, 100), "مجموع النجوم", fill=(180, 180, 180), font=font_small)
    draw.text((400, 130), str(total_stars), fill=(255, 215, 0), font=font_large)

    # Footer Branding
    draw.text((40, 225), f"السيرفر: {member.guild.name}", fill=(150, 150, 150), font=font_small)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# ================= =================
#  UI Components (Views, Selects & Buttons)
# ================= =================
class RatingView(discord.ui.View):
    def __init__(self, staff_id, ticket_channel):
        super().__init__(timeout=120)
        self.staff_id = str(staff_id)
        self.ticket_channel = ticket_channel

    @discord.ui.select(
        placeholder="اختر تقييم الخدمة الإدارية...",
        options=[
            discord.SelectOption(label="⭐ 5 - ممتاز جداً", value="5"),
            discord.SelectOption(label="⭐ 4 - جيد جداً", value="4"),
            discord.SelectOption(label="⭐ 3 - متوسط", value="3"),
            discord.SelectOption(label="⭐ 2 - سيئ", value="2"),
            discord.SelectOption(label="⭐ 1 - سيئ جداً", value="1"),
        ]
    )
    async def select_rating(self, interaction: discord.Interaction, select: discord.ui.Select):
        rating = int(select.values[0])
        stats = db_data["staff_stats"].get(self.staff_id, {"tickets": 0, "total_stars": 0, "ratings_count": 0})
        stats["total_stars"] += rating
        stats["ratings_count"] += 1
        db_data["staff_stats"][self.staff_id] = stats
        save_data(db_data)

        await interaction.response.send_message("شكرًا لك على تقديم تقييمك! جاري إغلاق التكت وحذفه...", ephemeral=True)
        await asyncio.sleep(2)
        try:
            await self.ticket_channel.delete()
        except discord.NotFound:
            pass

class TicketControlView(discord.ui.View):
    def __init__(self, menu_type):
        super().__init__(timeout=None)
        self.menu_type = menu_type

    @discord.ui.button(label="إضافة عضو", style=discord.ButtonStyle.secondary, custom_id="add_member")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("من فضلك أرسل منشن العضو المُراد إضافته للتكت في شات التكت.", ephemeral=True)

    @discord.ui.button(label="إزالة عضو", style=discord.ButtonStyle.secondary, custom_id="remove_member")
    async def remove_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("من فضلك أرسل منشن العضو المُراد إزالته من التكت في شات التكت.", ephemeral=True)

    @discord.ui.button(label="إغلاق التكت 🔒", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_id = str(interaction.channel.id)
        ticket_info = db_data["active_tickets"].get(channel_id, {})
        claimed_staff_id = ticket_info.get("staff_id")

        if self.menu_type == "admin" and claimed_staff_id:
            view = RatingView(staff_id=claimed_staff_id, ticket_channel=interaction.channel)
            await interaction.response.send_message("يرجى تقييم خدمة الإداري قبل إغلاق التكت:", view=view)
        else:
            await interaction.response.send_message("جاري إغلاق التكت وحذفه نهائياً...")
            await asyncio.sleep(2)
            try:
                await interaction.channel.delete()
            except discord.NotFound:
                pass

class MenuDropdown(discord.ui.Select):
    def __init__(self, title, menu_type, allowed_role_ids, observer_role_ids):
        self.title = title
        self.menu_type = menu_type
        self.allowed_role_ids = allowed_role_ids
        self.observer_role_ids = observer_role_ids
        options = [
            discord.SelectOption(label=f"فتح {title}", description="اضغط هنا للتواصل المباشر مع المسؤلين", emoji="🎟️")
        ]
        super().__init__(placeholder="اختر الخدمة المطلوبة من هنا...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = interaction.channel.category

        ticket_count = len(db_data["active_tickets"]) + 1
        clean_title = self.title.replace(" ", "-")
        channel_name = f"{clean_title}-{ticket_count}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        
        # Allowed Handling Roles
        for role_id in self.allowed_role_ids:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
        # Supervisor/Observer Roles (Read and Send permission to step in if needed)
        for role_id in self.observer_role_ids:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )

        db_data["active_tickets"][str(ticket_channel.id)] = {
            "owner_id": interaction.user.id,
            "staff_id": None,
            "menu_type": self.menu_type,
            "allowed_role_ids": self.allowed_role_ids,
            "observer_role_ids": self.observer_role_ids
        }
        save_data(db_data)

        embed = discord.Embed(
            title=f"🎟️ مرحباً بك في {channel_name}",
            description="الرجاء توضيح طلبك. سيتم تسليم التكت تلقائياً لأول إداري يقوم بالرد.",
            color=discord.Color.blue()
        )
        view = TicketControlView(self.menu_type)
        await ticket_channel.send(content=f"{interaction.user.mention}", embed=embed, view=view)
        await interaction.response.send_message(f"تم إنشاء التكت الخاص بك بنجاح: {ticket_channel.mention}", ephemeral=True)

class MenuDropdownView(discord.ui.View):
    def __init__(self, title, menu_type, allowed_role_ids, observer_role_ids):
        super().__init__(timeout=None)
        self.add_item(MenuDropdown(title, menu_type, allowed_role_ids, observer_role_ids))

# ================= =================
#  Event Handling (Message & Auto-Claim)
# ================= =================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Check for !كشف in specific Kashf Channel or anywhere if not set
    if message.content.startswith("!كشف"):
        kashf_chan_id = db_data.get("kashf_channel_id")
        if kashf_chan_id and message.channel.id != kashf_chan_id:
            await message.channel.send(f"❌ هذا الأمر مخصص في روم الكشف المحدد فقط!", delete_after=5)
            return

        target = message.mentions[0] if message.mentions else message.author
        stats = db_data["staff_stats"].get(str(target.id), {"tickets": 0, "total_stars": 0, "ratings_count": 0})
        
        tickets_count = stats["tickets"]
        total_stars = stats["total_stars"]
        ratings_count = stats["ratings_count"]
        avg_rating = (total_stars / ratings_count) if ratings_count > 0 else 0.0

        card_buffer = generate_profile_card(target, tickets_count, avg_rating, total_stars)
        file = discord.File(fp=card_buffer, filename="profile_card.png")
        
        embed = discord.Embed(title=f"📊 بطاقة كشف أداء الإداري {target.display_name}", color=discord.Color.blue())
        embed.set_image(url="attachment://profile_card.png")
        await message.channel.send(file=file, embed=embed)
        return

    channel_id = str(message.channel.id)
    if channel_id in db_data["active_tickets"]:
        ticket_info = db_data["active_tickets"][channel_id]
        
        # Auto Claim on first staff message
        if ticket_info["staff_id"] is None:
            allowed_role_ids = ticket_info.get("allowed_role_ids", [])
            is_staff = False

            author_role_ids = [r.id for r in message.author.roles]
            if any(role_id in author_role_ids for role_id in allowed_role_ids):
                is_staff = True
            elif message.author.guild_permissions.administrator:
                is_staff = True

            # If sender is valid staff and NOT the ticket creator
            if is_staff and message.author.id != ticket_info["owner_id"]:
                ticket_info["staff_id"] = message.author.id
                db_data["active_tickets"][channel_id] = ticket_info
                
                # Update staff stats
                staff_id_str = str(message.author.id)
                stats = db_data["staff_stats"].get(staff_id_str, {"tickets": 0, "total_stars": 0, "ratings_count": 0})
                stats["tickets"] += 1
                db_data["staff_stats"][staff_id_str] = stats
                save_data(db_data)

                # Restrict permissions so other staff members cannot claim
                guild = message.guild
                for r_id in allowed_role_ids:
                    role = guild.get_role(r_id)
                    if role:
                        await message.channel.set_permissions(role, read_messages=False)

                await message.channel.set_permissions(message.author, read_messages=True, send_messages=True)

                await message.channel.send(embed=discord.Embed(
                    description=f"✅ **تم الاستلام تلقائياً من قبل الإداري:** {message.author.mention}\n🔒 تم قفل التكت ومنع باقي الإداريين من التدخل.",
                    color=discord.Color.green()
                ))

    await bot.process_commands(message)

# ================= =================
#  Slash Commands Setup
# ================= =================
@bot.tree.command(name="إنشاء_منيو", description="إنشاء منيو تفاعلي للتكتات والتقديم")
@app_commands.describe(
    العنوان="عنوان المنيو (مثال: تكتات الإدارة أو تقديم عصابات)",
    الوصف="الوصف المكتوب تحت العنوان",
    نوع_المنيو="نوع المنيو (إداري مع تقييم أو تقديم وعصابات بدون تقييم)",
    رتب_الاستلام="منشن الرتب المسؤولة عن الاستلام",
    رتب_الاطلاع="منشن الرتب المشرفة القادرة على الاطلاع (اختياري)"
)
@app_commands.choices(نوع_المنيو=[
    app_commands.Choice(name="منيو إداري (يحتوي تقييم)", value="admin"),
    app_commands.Choice(name="منيو عصابات وتقديم (بدون تقييم)", value="normal")
])
async def create_menu(
    interaction: discord.Interaction, 
    العنوان: str,
    الوصف: str,
    نوع_المنيو: app_commands.Choice[str], 
    رتب_الاستلام: str,
    رتب_الاطلاع: str = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
        return

    allowed_role_ids = [int(role_id) for role_id in رتب_الاستلام.replace("<@&", "").replace(">", "").split() if role_id.isdigit()]
    
    observer_role_ids = []
    if رتب_الاطلاع:
        observer_role_ids = [int(role_id) for role_id in رتب_الاطلاع.replace("<@&", "").replace(">", "").split() if role_id.isdigit()]

    if not allowed_role_ids:
        await interaction.response.send_message("❌ يرجى منشن رتبة استلام واحدة على الأقل بشكل صحيح.", ephemeral=True)
        return

    embed = discord.Embed(
        title=العنوان,
        description=الوصف,
        color=discord.Color.gold()
    )
    view = MenuDropdownView(title=العنوان, menu_type=نوع_المنيو.value, allowed_role_ids=allowed_role_ids, observer_role_ids=observer_role_ids)
    msg = await interaction.channel.send(embed=embed, view=view)
    
    # Save Menu Data for future edits
    db_data["menus"][str(msg.id)] = {
        "title": العنوان,
        "description": الوصف,
        "menu_type": نوع_المنيو.value,
        "allowed_role_ids": allowed_role_ids,
        "observer_role_ids": observer_role_ids
    }
    save_data(db_data)
    
    await interaction.response.send_message("✅ تم إرسال المنيو التفاعلي بنجاح!", ephemeral=True)

@bot.tree.command(name="تعديل_منيو", description="تعديل عنوان أو وصف منيو قائم عبر آيدي الرسالة")
@app_commands.describe(
    آيدي_الرسالة="آيدي رسالة المنيو المُراد تعديله",
    العنوان_الجديد="العنوان الجديد للمنيو",
    الوصف_الجديد="الوصف الجديد للمنيو"
)
async def edit_menu(
    interaction: discord.Interaction,
    آيدي_الرسالة: str,
    العنوان_الجديد: str,
    الوصف_الجديد: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
        return

    try:
        msg = await interaction.channel.fetch_message(int(آيدي_الرسالة))
        embed = msg.embeds[0]
        embed.title = العنوان_الجديد
        embed.description = الوصف_الجديد
        await msg.edit(embed=embed)
        
        if آيدي_الرسالة in db_data["menus"]:
            db_data["menus"][آيدي_الرسالة]["title"] = العنوان_الجديد
            db_data["menus"][آيدي_الرسالة]["description"] = الوصف_الجديد
            save_data(db_data)

        await interaction.response.send_message("✅ تم تعديل المنيو بنجاح!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ تعذر العثور على الرسالة في هذا الروم: {e}", ephemeral=True)

@bot.tree.command(name="تحديد_روم_الكشف", description="تحديد الروم المخصص لاستخدام أمر !كشف")
@app_commands.describe(الروم="اختر الروم المخصص لأمر الكشف")
async def set_kashf_channel(interaction: discord.Interaction, الروم: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
        return

    db_data["kashf_channel_id"] = الروم.id
    save_data(db_data)
    await interaction.response.send_message(f"✅ تم تحديد {الروم.mention} كروم مخصص لأمر `!كشف` بنجاح!", ephemeral=True)

@bot.command(name="متصدرين")
async def leaderboard(ctx):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("هذا الأمر مخصص للقادة والإدارة العليا فقط.")
        return

    sorted_staff = sorted(db_data["staff_stats"].items(), key=lambda x: x[1].get("tickets", 0), reverse=True)
    
    embed = discord.Embed(title="🏆 لوحة متصدرين استلام التكتات", color=discord.Color.gold())
    description = ""
    for idx, (staff_id, stats) in enumerate(sorted_staff[:10], start=1):
        member = ctx.guild.get_member(int(staff_id))
        name = member.mention if member else f"مستخدم ({staff_id})"
        tickets = stats.get("tickets", 0)
        stars = stats.get("total_stars", 0)
        description += f"**#{idx}** | {name} - **التكتات:** `{tickets}` | **النجوم:** `⭐ {stars}`\n"

    embed.description = description or "لا توجد إحصائيات مسجلة حتى الآن."
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN environment variable.")
    bot.run(TOKEN)
