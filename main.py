import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "bot_data.json"

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

def generate_profile_card(member, tickets_count, total_stars, most_frequent_rating, avatar_bytes=None):
    width, height = 800, 450
    bg_color = (15, 17, 23)
    card_bg = (24, 28, 38)
    box_bg = (33, 39, 53)
    gold_accent = (255, 193, 7)
    text_white = (255, 255, 255)
    text_gray = (175, 185, 200)

    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

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

    draw.text((40, 30), f"👑 بطاقة كشف وإحصائيات أداء الإداري", fill=gold_accent, font=font_title)
    draw.line([(40, 70), (width - 40, 70)], fill=(50, 60, 80), width=2)

    # Box 1
    draw.rounded_rectangle([40, 95, 380, 235], radius=15, fill=box_bg, outline=(55, 65, 85), width=1)
    draw.text((60, 110), "📊 إجمالي التكتات المستلمة", fill=text_gray, font=font_sub)
    draw.text((60, 150), f"{tickets_count} تكت", fill=text_white, font=font_large)

    # Box 2
    draw.rounded_rectangle([420, 95, 760, 235], radius=15, fill=box_bg, outline=(55, 65, 85), width=1)
    draw.text((440, 110), "⭐ مجموع تقييم النجوم التوتل", fill=text_gray, font=font_sub)
    draw.text((440, 150), f"{total_stars} نجمة", fill=gold_accent, font=font_large)

    # Box 3
    draw.rounded_rectangle([40, 255, 380, 395], radius=15, fill=box_bg, outline=(55, 65, 85), width=1)
    draw.text((60, 270), "🏆 أعلى تقييم متكرر ياخذه", fill=text_gray, font=font_sub)
    draw.text((60, 310), f"⭐ {most_frequent_rating}", fill=(76, 175, 80), font=font_large)

    # Box 4
    draw.rounded_rectangle([420, 255, 760, 395], radius=15, fill=box_bg, outline=gold_accent, width=1)
    draw.text((440, 270), "👤 الإداري المسجل", fill=text_gray, font=font_sub)
    draw.text((440, 305), f"{member.display_name}", fill=text_white, font=font_bold)
    draw.text((440, 345), f"سيرفر: {member.guild.name}", fill=gold_accent, font=font_sub)

    if avatar_bytes:
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar_img = avatar_img.resize((70, 70))
            mask = Image.new('L', (70, 70), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, 70, 70), fill=255)
            img.paste(avatar_img, (670, 290), mask)
        except Exception as e:
            print(f"Could not load avatar: {e}")

    draw.text((40, 410), "نظام التكتات والكشف الإداري المتقدم", fill=(100, 110, 130), font=font_sub)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

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

class AddMemberModal(discord.ui.Modal, title="➕ إضافة عضو للتكت"):
    member_id = discord.ui.TextInput(label="آيدي أو منشن العضو", placeholder="مثال: 123456789012345678", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        clean_id = self.member_id.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            member = await interaction.guild.fetch_member(int(clean_id))
        except Exception:
            await interaction.response.send_message("❌ لم يتم العثور على هذا العضو بالسيرفر تأكد من الآيدي الصحيح.", ephemeral=True)
            return

        await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
        await interaction.response.send_message(f"✅ تم بنجاح إضافة {member.mention} إلى هذا التكت.", ephemeral=False)

class RemoveMemberModal(discord.ui.Modal, title="➖ إزالة عضو من التكت"):
    member_id = discord.ui.TextInput(label="آيدي أو منشن العضو", placeholder="مثال: 123456789012345678", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        clean_id = self.member_id.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            member = await interaction.guild.fetch_member(int(clean_id))
        except Exception:
            await interaction.response.send_message("❌ لم يتم العثور على هذا العضو بالسيرفر.", ephemeral=True)
            return

        ticket_info = db_data["active_tickets"].get(str(interaction.channel.id), {})
        owner_id = ticket_info.get("owner_id")
        if member.id == owner_id:
            await interaction.response.send_message("❌ لا يمكنك إزالة صاحب التكت الأساسي!", ephemeral=True)
            return

        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(f"✅ تم إزالة صلاحيات {member.mention} من هذا التكت.", ephemeral=False)

class TicketControlView(discord.ui.View):
    def __init__(self, menu_type):
        super().__init__(timeout=None)
        self.menu_type = menu_type

    @discord.ui.button(label="إضافة عضو ➕", style=discord.ButtonStyle.secondary, custom_id="add_member")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_info = db_data["active_tickets"].get(str(interaction.channel.id), {})
        staff_id = ticket_info.get("staff_id")
        
        is_admin = interaction.user.guild_permissions.administrator
        is_owner = interaction.user.id == ticket_info.get("owner_id")
        is_staff = interaction.user.id == staff_id

        if not (is_admin or is_owner or is_staff):
            await interaction.response.send_message("❌ ليس لديك صلاحية لإضافة أعضاء لهذا التكت.", ephemeral=True)
            return

        await interaction.response.send_modal(AddMemberModal())

    @discord.ui.button(label="إزالة عضو ➖", style=discord.ButtonStyle.secondary, custom_id="remove_member")
    async def remove_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_info = db_data["active_tickets"].get(str(interaction.channel.id), {})
        staff_id = ticket_info.get("staff_id")
        
        is_admin = interaction.user.guild_permissions.administrator
        is_staff = interaction.user.id == staff_id

        if not (is_admin or is_staff):
            await interaction.response.send_message("❌ هذا الزر مخصص لإدارة التكت فقط.", ephemeral=True)
            return

        await interaction.response.send_modal(RemoveMemberModal())

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
                db_data["active_tickets"].pop(channel_id, None)
                save_data(db_data)
                await interaction.channel.delete()
            except discord.NotFound:
                pass

class InteractiveTicketButton(discord.ui.Button):
    def __init__(self, label, emoji, button_text, menu_type, allowed_role_ids, observer_role_ids):
        super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.primary)
        self.button_text = button_text
        self.menu_type = menu_type
        self.allowed_role_ids = allowed_role_ids
        self.observer_role_ids = observer_role_ids

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = interaction.channel.category

        ticket_count = len(db_data["active_tickets"]) + 1
        clean_title = self.label.replace(" ", "-")
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

        desc = self.button_text if self.button_text else "الرجاء توضيح طلبك وشرحه بالتفصيل. سيتم استلام التكت تلقائياً فور أول رد من الإداري."

        embed = discord.Embed(
            title=f"🎟️ مرحباً بك في {channel_name}",
            description=desc,
            color=discord.Color.gold()
        )
        view = TicketControlView(self.menu_type)
        await ticket_channel.send(content=f"{interaction.user.mention}", embed=embed, view=view)
        await interaction.response.send_message(f"✅ تم إنشاء التكت بنجاح: {ticket_channel.mention}", ephemeral=True)

class DynamicMenuView(discord.ui.View):
    def __init__(self, buttons_list, menu_type, allowed_role_ids, observer_role_ids):
        super().__init__(timeout=None)
        for btn in buttons_list:
            btn_allowed = btn.get("allowed_role_ids", allowed_role_ids)
            btn_observer = btn.get("observer_role_ids", observer_role_ids)
            
            self.add_item(InteractiveTicketButton(
                label=btn.get("label", "فتح تكت"),
                emoji=btn.get("emoji") if btn.get("emoji") else None,
                button_text=btn.get("text", ""),
                menu_type=menu_type,
                allowed_role_ids=btn_allowed,
                observer_role_ids=btn_observer
            ))

class AddButtonRoleSetupModal(discord.ui.Modal, title="➕ إضافة زر جديد مع رتبه"):
    btn_label = discord.ui.TextInput(label="عنوان الزر (اسم الزر)", placeholder="مثال: تقديم شرطة", required=True)
    btn_emoji = discord.ui.TextInput(label="إيموجي الزر (اختياري)", placeholder="مثال: 🚔", required=False)
    btn_text = discord.ui.TextInput(label="الرسالة والتعليمات داخل التكت", style=discord.TextStyle.paragraph, placeholder="أكتب الرسالة التي تظهر للعضو فور فتح هذا التكت...", required=False)

    def __init__(self, message_id):
        super().__init__()
        self.message_id = message_id

    async def on_submit(self, interaction: discord.Interaction):
        view = ButtonRoleSelectView(self.message_id, self.btn_label.value, self.btn_emoji.value, self.btn_text.value)
        await interaction.response.send_message("حدد الآن رتب الاستلام والاطلاع الخاصة **بهذا الزر** من القوائم بالأسفل:", view=view, ephemeral=True)

class ButtonRoleSelectView(discord.ui.View):
    def __init__(self, message_id, label, emoji, text):
        super().__init__(timeout=180)
        self.message_id = message_id
        self.label = label
        self.emoji = emoji
        self.text = text
        self.allowed_role_ids = []
        self.observer_role_ids = []

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="اختر رتبة/رتب الاستلام لهذا الزر...",
        min_values=1,
        max_values=10,
        row=0
    )
    async def select_allowed(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        self.allowed_role_ids = [r.id for r in select.values]
        await interaction.response.send_message(f"✅ تم تحديد {len(self.allowed_role_ids)} رتبة للاستلام.", ephemeral=True)

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="اختر رتبة/رتب الاطلاع لهذا الزر (اختياري)...",
        min_values=0,
        max_values=10,
        row=1
    )
    async def select_observer(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        self.observer_role_ids = [r.id for r in select.values]
        await interaction.response.send_message(f"✅ تم تحديد {len(self.observer_role_ids)} رتبة للاطلاع.", ephemeral=True)

    @discord.ui.button(label="حفظ وإضافة الزر النهائي ✨", style=discord.ButtonStyle.success, row=2)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.allowed_role_ids:
            await interaction.response.send_message("❌ يجب اختيار رتبة استلام واحدة على الأقل!", ephemeral=True)
            return

        menu_info = db_data["menus"].get(self.message_id)
        if menu_info:
            buttons = menu_info.get("buttons", [])
            buttons.append({
                "label": self.label,
                "emoji": self.emoji.strip() if self.emoji else None,
                "text": self.text.strip() if self.text else "",
                "allowed_role_ids": self.allowed_role_ids,
                "observer_role_ids": self.observer_role_ids
            })
            menu_info["buttons"] = buttons
            db_data["menus"][self.message_id] = menu_info
            save_data(db_data)
            await update_menu_message(interaction.guild, interaction.channel, self.message_id)
            await interaction.response.send_message("✅ تم إضافة الزر ورتبه بنجاح وتحديث القائمة!", ephemeral=True)

class MenuControlPanelView(discord.ui.View):
    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.message_id = message_id

    @discord.ui.button(label="تعديل العنوان 📝", style=discord.ButtonStyle.primary, row=0)
    async def edit_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditTitleModal(self.message_id))

    @discord.ui.button(label="تعديل الوصف 📄", style=discord.ButtonStyle.primary, row=0)
    async def edit_desc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditDescriptionModal(self.message_id))

    @discord.ui.button(label="إضافة زر ➕", style=discord.ButtonStyle.success, row=1)
    async def add_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddButtonRoleSetupModal(self.message_id))

    @discord.ui.button(label="تعديل زر ✏️", style=discord.ButtonStyle.secondary, row=1)
    async def edit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        menu_info = db_data["menus"].get(self.message_id, {})
        buttons = menu_info.get("buttons", [])
        if not buttons:
            await interaction.response.send_message("❌ لا توجد أزرار لتعديلها حالياً.", ephemeral=True)
            return
        await interaction.response.send_message("اختر الزر الذي تريد تعديله:", view=EditButtonView(self.message_id, buttons), ephemeral=True)

    @discord.ui.button(label="حذف زر 🗑️", style=discord.ButtonStyle.danger, row=1)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        menu_info = db_data["menus"].get(self.message_id, {})
        buttons = menu_info.get("buttons", [])
        if not buttons:
            await interaction.response.send_message("❌ لا توجد أزرار لحذفها.", ephemeral=True)
            return
        await interaction.response.send_message("اختر رقم الزر المُراد حذفه:", view=DeleteButtonView(self.message_id, buttons), ephemeral=True)

    @discord.ui.button(label="تحديث المنيو 🔄", style=discord.ButtonStyle.success, row=2)
    async def refresh_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_menu_message(interaction.guild, interaction.channel, self.message_id)
        await interaction.response.send_message("✅ تم تحديث المنيو وإغلاق اللوحة بنجاح!", ephemeral=True)
        try:
            await interaction.message.delete()
        except Exception:
            pass

class EditTitleModal(discord.ui.Modal, title="📝 تعديل العنوان"):
    new_title = discord.ui.TextInput(label="العنوان الجديد للمنيو", required=True)
    def __init__(self, message_id):
        super().__init__()
        self.message_id = message_id
    async def on_submit(self, interaction: discord.Interaction):
        menu_info = db_data["menus"].get(self.message_id)
        if menu_info:
            menu_info["title"] = self.new_title.value
            db_data["menus"][self.message_id] = menu_info
            save_data(db_data)
            await update_menu_message(interaction.guild, interaction.channel, self.message_id)
            await interaction.response.send_message("✅ تم تعديل العنوان بنجاح!", ephemeral=True)

class EditDescriptionModal(discord.ui.Modal, title="📄 تعديل الوصف"):
    new_desc = discord.ui.TextInput(label="الوصف الجديد للمنيو", style=discord.TextStyle.paragraph, required=True)
    def __init__(self, message_id):
        super().__init__()
        self.message_id = message_id
    async def on_submit(self, interaction: discord.Interaction):
        menu_info = db_data["menus"].get(self.message_id)
        if menu_info:
            menu_info["description"] = self.new_desc.value
            db_data["menus"][self.message_id] = menu_info
            save_data(db_data)
            await update_menu_message(interaction.guild, interaction.channel, self.message_id)
            await interaction.response.send_message("✅ تم تعديل الوصف بنجاح!", ephemeral=True)

class DeleteButtonSelect(discord.ui.Select):
    def __init__(self, message_id, buttons):
        self.message_id = message_id
        options = [
            discord.SelectOption(label=f"زر رقم #{idx + 1}: {b['label']}", value=str(idx), emoji=b.get("emoji"))
            for idx, b in enumerate(buttons)
        ]
        super().__init__(placeholder="اختر رقم الزر المُراد حذفه...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        menu_info = db_data["menus"].get(self.message_id)
        if menu_info and "buttons" in menu_info:
            buttons = menu_info.get("buttons", [])
            if 0 <= selected_index < len(buttons):
                removed = buttons.pop(selected_index)
                menu_info["buttons"] = buttons
                db_data["menus"][self.message_id] = menu_info
                save_data(db_data)
                await update_menu_message(interaction.guild, interaction.channel, self.message_id)
                await interaction.response.send_message(f"✅ تم حذف الزر ({removed['label']}) بنجاح!", ephemeral=True)

class DeleteButtonView(discord.ui.View):
    def __init__(self, message_id, buttons):
        super().__init__(timeout=60)
        self.add_item(DeleteButtonSelect(message_id, buttons))

class EditButtonSelect(discord.ui.Select):
    def __init__(self, message_id, buttons):
        self.message_id = message_id
        self.buttons = buttons
        options = [
            discord.SelectOption(label=f"زر رقم #{idx + 1}: {b['label']}", value=str(idx), emoji=b.get("emoji"))
            for idx, b in enumerate(buttons)
        ]
        super().__init__(placeholder="اختر رقم الزر المُراد تعديله...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        current_btn = self.buttons[selected_index]
        view = ButtonRoleSelectView(self.message_id, current_btn.get("label"), current_btn.get("emoji"), current_btn.get("text"))
        await interaction.response.send_message("عدل الرتب والإعدادات الخاصة بهذا الزر من القوائم أدناه:", view=view, ephemeral=True)

class EditButtonView(discord.ui.View):
    def __init__(self, message_id, buttons):
        super().__init__(timeout=60)
        self.add_item(EditButtonSelect(message_id, buttons))

async def update_menu_message(guild, channel, message_id):
    menu_info = db_data["menus"].get(str(message_id))
    if not menu_info:
        return
    try:
        msg = await channel.fetch_message(int(message_id))
    except Exception:
        return

    embed = discord.Embed(
        title=menu_info.get("title", "مركز الدعم والمساعدة"),
        description=menu_info.get("description", "مرحباً بك في مركز الدعم!"),
        color=discord.Color.gold()
    )

    buttons_list = menu_info.get("buttons", [])
    view = DynamicMenuView(
        buttons_list,
        menu_info.get("menu_type", "admin"),
        menu_info.get("allowed_role_ids", []),
        menu_info.get("observer_role_ids", [])
    ) if buttons_list else None

    await msg.edit(embed=embed, view=view)

@bot.tree.command(name="إنشاء_منيو", description="إنشاء منيو تفاعلي جديد")
@app_commands.describe(نوع_المنيو="نوع المنيو (إداري أو عصابات/تقديم)")
@app_commands.choices(نوع_المنيو=[
    app_commands.Choice(name="منيو إداري (يحتوي تقييم)", value="admin"),
    app_commands.Choice(name="منيو عصابات وتقديم (بدون تقييم)", value="normal")
])
async def create_menu(interaction: discord.Interaction, نوع_المنيو: app_commands.Choice[str]):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
        return

    default_title = "مركز الدعم والمساعدة | Support Center"
    default_desc = "مرحباً بك في مركز الدعم والخدمات! 👋\n\nيرجى اختيار القسم المناسب أدناه لفتح قناة خاصة بك."

    embed = discord.Embed(title=default_title, description=default_desc, color=discord.Color.gold())
    menu_msg = await interaction.channel.send(embed=embed)

    msg_id = str(menu_msg.id)
    db_data["menus"][msg_id] = {
        "title": default_title,
        "description": default_desc,
        "buttons": [],
        "menu_type": نوع_المنيو.value,
        "allowed_role_ids": [],
        "observer_role_ids": []
    }
    save_data(db_data)

    panel_view = MenuControlPanelView(msg_id)
    await interaction.response.send_message(
        "✅ **تم إنشاء المنيو بنجاح!**\nقم بإضافة الأزرار وتحديد رتب الاستلام والإطلاع لكل زر عبر لوحة التحكم بالأسفل:",
        view=panel_view,
        ephemeral=True
    )

@bot.tree.command(name="تعديل_منيو", description="فتح لوحة التحكم والتعديل لمنيو قائم عبر آيدي الرسالة")
@app_commands.describe(آيدي_الرسالة="آيدي رسالة المنيو المراد تعديله")
async def edit_menu(interaction: discord.Interaction, آيدي_الرسالة: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
        return

    if آيدي_الرسالة not in db_data["menus"]:
        await interaction.response.send_message("❌ لم يتم العثور على منيو مسجل بهذا الآيدي.", ephemeral=True)
        return

    panel_view = MenuControlPanelView(آيدي_الرسالة)
    await interaction.response.send_message("🛠️ **لوحة التحكم والتعديل في المنيو:**", view=panel_view, ephemeral=True)

@bot.tree.command(name="تحديد_روم_الكشف", description="تحديد الروم المخصص لاستخدام أمر الكشف")
@app_commands.describe(الروم="اختر الروم المخصص لأمر الكشف")
async def set_kashf_channel(interaction: discord.Interaction, الروم: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("لا تملك صلاحية.", ephemeral=True)
        return
    db_data["kashf_channel_id"] = الروم.id
    save_data(db_data)
    await interaction.response.send_message(f"✅ تم تحديد {الروم.mention} كروم مخصص لأمر `!كشف` بنجاح!", ephemeral=True)

@bot.command(name="كشف")
async def kashf_prefix(ctx, member: discord.Member = None):
    kashf_chan_id = db_data.get("kashf_channel_id")
    if kashf_chan_id and ctx.channel.id != kashf_chan_id:
        try:
            await ctx.message.delete()
        except Exception:
            pass
        return

    target = member if member else ctx.author
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

    avatar_bytes = None
    try:
        avatar_bytes = await target.display_avatar.read()
    except Exception:
        pass

    card_buffer = generate_profile_card(target, tickets_count, total_stars, most_frequent_rating, avatar_bytes)
    file = discord.File(fp=card_buffer, filename="profile_card.png")

    embed = discord.Embed(title=f"👑 بطاقة كشف أداء الإداري: {target.display_name}", color=discord.Color.gold())
    embed.set_image(url="attachment://profile_card.png")
    await ctx.send(file=file, embed=embed)

@bot.tree.command(name="متصدرين", description="عرض لوحة متصدرين أداء الإداريين واستلام التكتات")
async def leaderboard_slash(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("مخصص للقادة فقط.", ephemeral=True)
        return

    sorted_staff = sorted(db_data["staff_stats"].items(), key=lambda x: x[1].get("tickets", 0), reverse=True)
    embed = discord.Embed(title="🏆 لوحة متصدرين استلام التكتات", color=discord.Color.gold())
    description = ""
    for idx, (staff_id, stats) in enumerate(sorted_staff[:10], start=1):
        member = interaction.guild.get_member(int(staff_id))
        name = member.mention if member else f"مستخدم ({staff_id})"
        tickets = stats.get("tickets", 0)
        stars = stats.get("total_stars", 0)
        description += f"**#{idx}** | {name} - **التكتات:** `{tickets}` | **النجوم:** `⭐ {stars}`\n"

    embed.description = description or "لا توجد إحصائيات حتى الآن."
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    channel_id = str(message.channel.id)
    if channel_id in db_data["active_tickets"]:
        ticket_info = db_data["active_tickets"][channel_id]

        if ticket_info["staff_id"] is None:
            allowed_role_ids = ticket_info.get("allowed_role_ids", [])
            is_staff = False

            author_role_ids = [r.id for r in message.author.roles]
            if any(role_id in author_role_ids for role_id in allowed_role_ids) or message.author.guild_permissions.administrator:
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
                        try:
                            await message.channel.set_permissions(role, read_messages=False)
                        except Exception:
                            pass

                try:
                    await message.channel.set_permissions(message.author, read_messages=True, send_messages=True)
                except Exception:
                    pass

                await message.channel.send(embed=discord.Embed(
                    description=f"✅ **تم الاستلام تلقائياً بواسطة:** {message.author.mention}\n🔒 تم قفل التكت ومنع باقي الإداريين.",
                    color=discord.Color.green()
                ))

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN environment variable.")
    bot.run(TOKEN)
