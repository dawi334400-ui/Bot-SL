import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio
from PIL import Image, ImageDraw, ImageFont
import io
import requests

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
#  Profile Card Generation Logic (HD 800x450)
# ================= =================
def generate_profile_card(member, tickets_count, total_stars, most_frequent_rating):
    width, height = 800, 450
    bg_color = (15, 17, 23)
    card_bg = (24, 28, 38)
    box_bg = (33, 39, 53)
    gold_accent = (255, 193, 7)
    text_white = (255, 255, 255)
    text_gray = (175, 185, 200)

    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Outer Frame & Border Accent
    draw.rounded_rectangle([15, 15, width - 15, height - 15], radius=20, fill=card_bg, outline=gold_accent, width=2)

    try:
        font_title = ImageFont.truetype("arial.ttf", 26)
        font_large = ImageFont.truetype("arial.ttf", 24)
        font_sub = ImageFont.truetype("arial.ttf", 16)
        font_bold = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font_title = ImageFont.load_default()
        font_large = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_bold = ImageFont.load_default()

    # Header Title
    draw.text((40, 30), f"👑 بطاقة كشف وإحصائيات أداء الإداري", fill=gold_accent, font=font_title)
    draw.line([(40, 70), (width - 40, 70)], fill=(50, 60, 80), width=2)

    # ---------------- 4 MAIN BOXES DESIGN ----------------
    # Box 1: Total Tickets
    draw.rounded_rectangle([40, 95, 380, 235], radius=15, fill=box_bg, outline=(55, 65, 85), width=1)
    draw.text((60, 110), "📊 إجمالي التكتات المستلمة", fill=text_gray, font=font_sub)
    draw.text((60, 150), f"{tickets_count} تكت", fill=text_white, font=font_large)

    # Box 2: Total Stars Rating
    draw.rounded_rectangle([420, 95, 760, 235], radius=15, fill=box_bg, outline=(55, 65, 85), width=1)
    draw.text((440, 110), "⭐ مجموع تقييم النجوم التوتل", fill=text_gray, font=font_sub)
    draw.text((440, 150), f"{total_stars} نجمة", fill=gold_accent, font=font_large)

    # Box 3: Most Frequent Rating
    draw.rounded_rectangle([40, 255, 380, 395], radius=15, fill=box_bg, outline=(55, 65, 85), width=1)
    draw.text((60, 270), "🏆 أعلى تقييم متكرر ياخذه", fill=text_gray, font=font_sub)
    draw.text((60, 310), f"⭐ {most_frequent_rating}", fill=(76, 175, 80), font=font_large)

    # Box 4: Admin Identity & Server Logo Branding
    draw.rounded_rectangle([420, 255, 760, 395], radius=15, fill=box_bg, outline=gold_accent, width=1)
    draw.text((440, 270), "👤 الإداري المسجل", fill=text_gray, font=font_sub)
    draw.text((440, 305), f"{member.display_name}", fill=text_white, font=font_bold)
    draw.text((440, 345), f"سيرفر: {member.guild.name}", fill=gold_accent, font=font_sub)

    # Fetch Avatar image if available
    try:
        avatar_url = member.display_avatar.url
        resp = requests.get(avatar_url)
        avatar_img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        avatar_img = avatar_img.resize((70, 70))
        
        # Make avatar circular
        mask = Image.new('L', (70, 70), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 70, 70), fill=255)
        
        img.paste(avatar_img, (670, 290), mask)
    except Exception as e:
        print(f"Could not load avatar: {e}")

    # Footer
    draw.text((40, 410), "نظام التكتات والكشف الإداري المتقدم", fill=(100, 110, 130), font=font_sub)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# ================= =================
#  UI Views and Control Modals
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
        stats = db_data["staff_stats"].get(self.staff_id, {
            "tickets": 0, "total_stars": 0, "ratings_count": 0, "ratings_list": []
        })
        stats["total_stars"] += rating
        stats["ratings_count"] += 1
        if "ratings_list" not in stats:
            stats["ratings_list"] = []
        stats["ratings_list"].append(rating)

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

class DynamicMenuSelect(discord.ui.Select):
    def __init__(self, options_list, menu_type, allowed_role_ids, observer_role_ids):
        self.menu_type = menu_type
        self.allowed_role_ids = allowed_role_ids
        self.observer_role_ids = observer_role_ids
        
        select_options = []
        for opt in options_list:
            select_options.append(
                discord.SelectOption(
                    label=opt["label"],
                    description=opt.get("description", "اضغط هنا للفتح مباشرة"),
                    emoji=opt.get("emoji", "🎟️")
                )
            )
        super().__init__(placeholder="اختر الخدمة أو قسم التقديم من القائمة...", min_values=1, max_values=1, options=select_options)

    async def callback(self, interaction: discord.Interaction):
        selected_label = self.values[0]
        guild = interaction.guild
        category = interaction.channel.category

        ticket_count = len(db_data["active_tickets"]) + 1
        clean_title = selected_label.replace(" ", "-")
        channel_name = f"{clean_title}-{ticket_count}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        
        for role_id in self.allowed_role_ids:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
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
            description="الرجاء توضيح طلبك وشرحه بالتفصيل. سيتم استلام التكت تلقائياً فور أول رد من الإداري.",
            color=discord.Color.gold()
        )
        view = TicketControlView(self.menu_type)
        await ticket_channel.send(content=f"{interaction.user.mention}", embed=embed, view=view)
        await interaction.response.send_message(f"✅ تم إنشاء التكت بنجاح: {ticket_channel.mention}", ephemeral=True)

class DynamicMenuView(discord.ui.View):
    def __init__(self, options_list, menu_type, allowed_role_ids, observer_role_ids):
        super().__init__(timeout=None)
        self.add_item(DynamicMenuSelect(options_list, menu_type, allowed_role_ids, observer_role_ids))

# Modal popup window for creating menu title, bio, and buttons
class CreateMenuModal(discord.ui.Modal, title="✨ لوحة إعداد المنيو وتصميمه"):
    عنوان_المنيو = discord.ui.TextInput(label="عنوان المنيو الرئيسي", placeholder="مثال: ⚜️ تكتات الدعم الفني والإدارة", required=True)
    الوصف_البايو = discord.ui.TextInput(label="البايو / الوصف الشارح", style=discord.TextStyle.paragraph, placeholder="أكتب البايو والتعليمات هنا...", required=True)
    خيارات_المنيو = discord.ui.TextInput(
        label="الأزرار/الخيارات (افصل بـ | بين الخيارات)",
        style=discord.TextStyle.paragraph,
        placeholder="مثال: شكوى دكاتره | تقديم عصابات | استفسار عام",
        required=True
    )

    def __init__(self, menu_type, allowed_role_ids, observer_role_ids):
        super().__init__()
        self.menu_type = menu_type
        self.allowed_role_ids = allowed_role_ids
        self.observer_role_ids = observer_role_ids

    async def on_submit(self, interaction: discord.Interaction):
        raw_options = self.خيارات_المنيو.value.split("|")
        options_list = []
        for opt in raw_options:
            cleaned = opt.strip()
            if cleaned:
                options_list.append({"label": cleaned, "description": "اضغط للفتح مباشرة", "emoji": "🎟️"})

        embed = discord.Embed(
            title=self.عنوان_المنيو.value,
            description=self.الوصف_البايو.value,
            color=discord.Color.gold()
        )
        view = DynamicMenuView(options_list, self.menu_type, self.allowed_role_ids, self.observer_role_ids)
        msg = await interaction.channel.send(embed=embed, view=view)

        db_data["menus"][str(msg.id)] = {
            "title": self.عنوان_المنيو.value,
            "description": self.الوصف_البايو.value,
            "options": options_list,
            "menu_type": self.menu_type,
            "allowed_role_ids": self.allowed_role_ids,
            "observer_role_ids": self.observer_role_ids
        }
        save_data(db_data)

        await interaction.response.send_message("✅ تم إنشاء المنيو واللوحة التفاعلية بنجاح!", ephemeral=True)

# Modal popup window for editing menu by message ID
class EditMenuModal(discord.ui.Modal, title="✏️ تعديل المنيو والخيارات"):
    العنوان_الجديد = discord.ui.TextInput(label="العنوان الجديد", required=True)
    الوصف_الجديد = discord.ui.TextInput(label="البايو / الوصف الجديد", style=discord.TextStyle.paragraph, required=True)
    الخيارات_الجديدة = discord.ui.TextInput(
        label="تحديث الأزرار/الخيارات (مفصولة بـ |)",
        style=discord.TextStyle.paragraph,
        required=True
    )

    def __init__(self, message_id, default_title="", default_desc="", default_opts=""):
        super().__init__()
        self.message_id = str(message_id)
        self.العنوان_الجديد.default = default_title
        self.الوصف_الجديد.default = default_desc
        self.الخيارات_الجديدة.default = default_opts

    async def on_submit(self, interaction: discord.Interaction):
        try:
            msg = await interaction.channel.fetch_message(int(self.message_id))
            menu_info = db_data["menus"].get(self.message_id, {})

            raw_options = self.الخيارات_الجديدة.value.split("|")
            options_list = []
            for opt in raw_options:
                cleaned = opt.strip()
                if cleaned:
                    options_list.append({"label": cleaned, "description": "اضغط للفتح مباشرة", "emoji": "🎟️"})

            embed = msg.embeds[0]
            embed.title = self.العنوان_الجديد.value
            embed.description = self.الوصف_الجديد.value

            view = DynamicMenuView(
                options_list,
                menu_info.get("menu_type", "admin"),
                menu_info.get("allowed_role_ids", []),
                menu_info.get("observer_role_ids", [])
            )
            await msg.edit(embed=embed, view=view)

            menu_info["title"] = self.العنوان_الجديد.value
            menu_info["description"] = self.الوصف_الجديد.value
            menu_info["options"] = options_list
            db_data["menus"][self.message_id] = menu_info
            save_data(db_data)

            await interaction.response.send_message("✅ تم تعديل المنيو والأزرار بنجاح!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ حدث خطأ أثناء التعديل: {e}", ephemeral=True)

# ================= =================
#  Message Handling & Commands
# ================= =================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Command !كشف
    if message.content.startswith("!كشف"):
        kashf_chan_id = db_data.get("kashf_channel_id")
        if kashf_chan_id and message.channel.id != kashf_chan_id:
            await message.channel.send(f"❌ هذا الأمر مخصص في روم الكشف المحدد فقط!", delete_after=5)
            return

        target = message.mentions[0] if message.mentions else message.author
        stats = db_data["staff_stats"].get(str(target.id), {
            "tickets": 0, "total_stars": 0, "ratings_count": 0, "ratings_list": []
        })

        tickets_count = stats["tickets"]
        total_stars = stats["total_stars"]
        ratings_list = stats.get("ratings_list", [])

        if ratings_list:
            most_frequent_rating = f"{max(set(ratings_list), key=ratings_list.count)}/5"
        else:
            most_frequent_rating = "لا يوجد تقييمات"

        card_buffer = generate_profile_card(target, tickets_count, total_stars, most_frequent_rating)
        file = discord.File(fp=card_buffer, filename="profile_card.png")

        embed = discord.Embed(title=f"👑 بطاقة كشف أداء الإداري: {target.display_name}", color=discord.Color.gold())
        embed.set_image(url="attachment://profile_card.png")
        await message.channel.send(file=file, embed=embed)
        return

    channel_id = str(message.channel.id)
    if channel_id in db_data["active_tickets"]:
        ticket_info = db_data["active_tickets"][channel_id]

        if ticket_info["staff_id"] is None:
            allowed_role_ids = ticket_info.get("allowed_role_ids", [])
            is_staff = False

            author_role_ids = [r.id for r in message.author.roles]
            if any(role_id in author_role_ids for role_id in allowed_role_ids):
                is_staff = True
            elif message.author.guild_permissions.administrator:
                is_staff = True

            if is_staff and message.author.id != ticket_info["owner_id"]:
                ticket_info["staff_id"] = message.author.id
                db_data["active_tickets"][channel_id] = ticket_info

                staff_id_str = str(message.author.id)
                stats = db_data["staff_stats"].get(staff_id_str, {
                    "tickets": 0, "total_stars": 0, "ratings_count": 0, "ratings_list": []
                })
                stats["tickets"] += 1
                db_data["staff_stats"][staff_id_str] = stats
                save_data(db_data)

                guild = message.guild
                for r_id in allowed_role_ids:
                    role = guild.get_role(r_id)
                    if role:
                        await message.channel.set_permissions(role, read_messages=False)

                await message.channel.set_permissions(message.author, read_messages=True, send_messages=True)

                await message.channel.send(embed=discord.Embed(
                    description=f"✅ **تم الاستلام تلقائياً بواسطة:** {message.author.mention}\n🔒 تم قفل التكت ومنع باقي الإداريين من التدخل.",
                    color=discord.Color.green()
                ))

    await bot.process_commands(message)

# ================= =================
#  Slash Commands Setup
# ================= =================
@bot.tree.command(name="إنشاء_منيو", description="فتح لوحة الأزرار التفاعلية لتصميم المنيو والبايو والخيارات")
@app_commands.describe(
    نوع_المنيو="نوع المنيو (إداري مع تقييم أو تقديم/عصابات بدون تقييم)",
    رتب_الاستلام="منشن الرتب المسؤولة عن الاستلام",
    رتب_الاطلاع="منشن الرتب المشرفة القادرة على الاطلاع (اختياري)"
)
@app_commands.choices(نوع_المنيو=[
    app_commands.Choice(name="منيو إداري (يحتوي تقييم)", value="admin"),
    app_commands.Choice(name="منيو عصابات وتقديم (بدون تقييم)", value="normal")
])
async def create_menu(
    interaction: discord.Interaction,
    نوع_المنيو: app_commands.Choice[str],
    رتب_الاستلام: str,
    رتب_الاطلاع: str = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
        return

    allowed_role_ids = [int(r) for r in رتب_الاستلام.replace("<@&", "").replace(">", "").split() if r.isdigit()]
    observer_role_ids = []
    if رتب_الاطلاع:
        observer_role_ids = [int(r) for r in رتب_الاطلاع.replace("<@&", "").replace(">", "").split() if r.isdigit()]

    if not allowed_role_ids:
        await interaction.response.send_message("❌ يرجى منشن رتبة استلام واحدة على الأقل بشكل صحيح.", ephemeral=True)
        return

    modal = CreateMenuModal(
        menu_type=نوع_المنيو.value,
        allowed_role_ids=allowed_role_ids,
        observer_role_ids=observer_role_ids
    )
    await interaction.response.send_modal(modal)

@bot.tree.command(name="تعديل_منيو", description="تعديل عنوان وبايو وأزرار منيو قائم عبر آيدي الرسالة")
@app_commands.describe(آيدي_الرسالة="آيدي رسالة المنيو المُراد تعديله")
async def edit_menu(interaction: discord.Interaction, آيدي_الرسالة: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
        return

    menu_info = db_data["menus"].get(آيدي_الرسالة, {})
    default_title = menu_info.get("title", "")
    default_desc = menu_info.get("description", "")
    existing_opts = [opt["label"] for opt in menu_info.get("options", [])]
    default_opts = " | ".join(existing_opts)

    modal = EditMenuModal(
        message_id=آيدي_الرسالة,
        default_title=default_title,
        default_desc=default_desc,
        default_opts=default_opts
    )
    await interaction.response.send_modal(modal)

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
