import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio
from datetime import datetime, timezone
import logging
import random

logging.basicConfig(level=logging.ERROR)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ملفات التخزين المحلية للأنظمة
DATA_FILE = "bot_data.json"
BANK_DATA_FILE = "bank_data.json"
GAMES_DATA_FILE = "games_data.json"
SECURITY_DATA_FILE = "security_data.json"
SECTORS_DATA_FILE = "sectors_data.json"
AI_DATA_FILE = "ai_data.json"
WELCOME_FILE = "welcome_settings.json"
LOGS_FILE = "logs_data.json"

def load_json(filename, default):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def save_json(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

db_data = load_json(DATA_FILE, {"menus": {}, "staff_stats": {}, "active_tickets": {}})
bank_db = load_json(BANK_DATA_FILE, {"users": {}, "organizations": {}, "settings": {"games_rewards": {"فك الشفرة": {"سهل": 100, "متوسط": 250, "صعب": 500}, "الكنز": {"سهل": 150, "متوسط": 300, "صعب": 600}, "تحدي الذكاء": {"سهل": 200, "متوسط": 400, "صعب": 800}}}, "logs": []})
games_db = load_json(GAMES_DATA_FILE, {"allowed_roles": [], "active_game": None})
security_db = load_json(SECURITY_DATA_FILE, {"whitelist": [], "log_channel": None, "protected_roles": []})
sectors_db = load_json(SECTORS_DATA_FILE, {"sectors": {}})
ai_db = load_json(AI_DATA_FILE, {"speaking_mode": False, "ai_channels": []})
welcome_db = load_json(WELCOME_FILE, {
    "welcome_enabled": False, "welcome_channel_id": None,
    "welcome_message": "يا هلا ومرحبا بـ {mention}، نورت سيرفرنا {server}.",
    "leave_enabled": False, "leave_channel_id": None,
    "leave_message": "غادر السيرفر {name}."
})
logs_db = load_json(LOGS_FILE, {"log_channel_id": None})

# ----------------- 🏦 نظام البنك المالي المتكامل -----------------
class AdminBankPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="➕ إنشاء حساب مؤسسة", style=discord.ButtonStyle.success, custom_id="admin_create_org", row=0)
    async def create_org_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ هذه اللوحة مخصصة للإدارة فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(AdminCreateOrgModal())

    @discord.ui.button(label="💰 تعديل رصيد", style=discord.ButtonStyle.primary, custom_id="admin_modify_bal", row=0)
    async def modify_bal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ هذه اللوحة مخصصة للإدارة فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(AdminModifyBalanceModal())

class AdminCreateOrgModal(discord.ui.Modal, title="🏛️ إنشاء حساب مؤسسة جديد"):
    org_name = discord.ui.TextInput(label="اسم المؤسسة", placeholder="مثال: الشرطة، المرور...", required=True)
    manager_name = discord.ui.TextInput(label="آيدي العضو المسؤول", placeholder="اكتب الآيدي هنا...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.org_name.value.strip()
        mgr_input = self.manager_name.value.strip()
        if name in bank_db["organizations"]:
            await interaction.response.send_message(f"❌ حساب المؤسسة **{name}** موجود مسبقاً!", ephemeral=True)
            return
        target_member = interaction.guild.get_member(int(mgr_input)) if mgr_input.isdigit() else None
        if not target_member:
            await interaction.response.send_message(f"❌ لم يتم العثور على العضو المسؤول.", ephemeral=True)
            return
        bank_db["organizations"][name] = {"manager_id": target_member.id, "balance": 5000, "history": []}
        save_json(BANK_DATA_FILE, bank_db)
        await interaction.response.send_message(f"✅ تم إنشاء حساب مؤسسة **{name}** لـ {target_member.mention} بنجاح!", ephemeral=True)

class AdminModifyBalanceModal(discord.ui.Modal, title="💰 تعديل رصيد الحساب أو المؤسسة"):
    target_name = discord.ui.TextInput(label="اسم المؤسسة أو الآيدي", placeholder="اسم المؤسسة أو آيدي العضو...", required=True)
    amount = discord.ui.TextInput(label="المبلغ (استخدم سالب للخصم مثل -500)", placeholder="1000 أو -500", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.target_name.value.strip()
        try:
            amt = int(self.amount.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ يرجى إدخال رقم صحيح للمبلغ.", ephemeral=True)
            return
        if name in bank_db["organizations"]:
            bank_db["organizations"][name]["balance"] += amt
            save_json(BANK_DATA_FILE, bank_db)
            await interaction.response.send_message(f"✅ تم تعديل رصيد مؤسسة **{name}** بمقدار ({amt}).", ephemeral=True)
            return
        await interaction.response.send_message(f"❌ لم يتم العثور على الحساب المذكور.", ephemeral=True)

class BankMainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💳 حسابي", style=discord.ButtonStyle.primary, custom_id="bank_my_account")
    async def my_account(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        user_data = bank_db["users"].setdefault(user_id, {"balance": 1000, "history": []})
        embed = discord.Embed(title=f"💳 حساب {interaction.user.display_name}", description=f"💰 **الرصيد الحالي:** `{user_data['balance']}`", color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ----------------- 🎟️ نظام التكتات والمنيو التفاعلي -----------------
class TicketControlView(discord.ui.View):
    def __init__(self, menu_type="admin"):
        super().__init__(timeout=None)
        self.menu_type = menu_type

    @discord.ui.button(label="إغلاق التكت 🔒", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 جاري إغلاق التكت الح الحالي...")
        await asyncio.sleep(2)
        try:
            channel_id = str(interaction.channel.id)
            db_data["active_tickets"].pop(channel_id, None)
            save_json(DATA_FILE, db_data)
            await interaction.channel.delete()
        except Exception:
            pass

class InteractiveTicketButton(discord.ui.Button):
    def __init__(self, label, emoji, button_text, menu_type, allowed_role_ids, observer_role_ids, btn_index=0, msg_id=""):
        cid = f"dyn_btn_{msg_id}_{btn_index}" if msg_id else f"dyn_btn_{btn_index}"
        super().__init__(label=label, emoji=emoji if emoji else None, style=discord.ButtonStyle.primary, custom_id=cid)
        self.button_text = button_text
        self.menu_type = menu_type
        self.allowed_role_ids = allowed_role_ids
        self.observer_role_ids = observer_role_ids
        self.msg_id = str(msg_id)
        self.btn_index = btn_index

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        category = interaction.channel.category
        ticket_count = len(db_data["active_tickets"]) + 1
        channel_name = f"{self.label.replace(' ', '-')}-{ticket_count}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        for role_id in set([int(r) for r in self.allowed_role_ids + self.observer_role_ids]):
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        except Exception as e:
            await interaction.followup.send(f"❌ خطأ في إنشاء الروم: {e}", ephemeral=True)
            return

        db_data["active_tickets"][str(ticket_channel.id)] = {"owner_id": interaction.user.id}
        save_json(DATA_FILE, db_data)

        embed = discord.Embed(title=f"🎟️ مرحباً بك في {channel_name}", description=self.button_text or "📌 يرجى توضيح طلبك.", color=discord.Color.gold())
        await ticket_channel.send(embed=embed, view=TicketControlView())
        await interaction.followup.send(f"✅ تم فتح التكت بنجاح: {ticket_channel.mention}", ephemeral=True)

class DynamicMenuView(discord.ui.View):
    def __init__(self, buttons_list, menu_type, msg_id=""):
        super().__init__(timeout=None)
        for idx, btn in enumerate(buttons_list):
            self.add_item(InteractiveTicketButton(
                label=btn.get("label", "تكت"),
                emoji=btn.get("emoji"),
                button_text=btn.get("text", ""),
                menu_type=menu_type,
                allowed_role_ids=btn.get("allowed_role_ids", []),
                observer_role_ids=btn.get("observer_role_ids", []),
                btn_index=idx,
                msg_id=str(msg_id)
            ))

# ----------------- 🏛️ إدارة القطاعات والصلاحيات ورتب الحماية -----------------
class SectorManagementView(discord.ui.View):
    def __init__(self, sector_name):
        super().__init__(timeout=None)
        self.sector_name = sector_name

    @discord.ui.button(label="👥 أعضاء القطاع", style=discord.ButtonStyle.primary, custom_id="sector_members_btn")
    async def sector_members(self, interaction: discord.Interaction, button: discord.ui.Button):
        sec_data = sectors_db["sectors"].get(self.sector_name, {})
        allowed_role_ids = sec_data.get("role_ids", [])
        members_in_sector = [m for m in interaction.guild.members if any(r.id in allowed_role_ids for r in m.roles)]
        desc = f"📊 **إحصائيات قطاع: {self.sector_name}**\n👤 **العدد الإجمالي:** `{len(members_in_sector)}`\n"
        embed = discord.Embed(title=f"أعضاء قطاع {self.sector_name}", description=desc, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="إنشاء_قطاع", description="إنشاء قطاع جديد وتحديد المسؤول والرتبة")
@app_commands.checks.has_permissions(administrator=True)
async def create_sector(interaction: discord.Interaction, اسم_القطاع: str, المسؤول: discord.Member, رتبة_القطاع: discord.Role):
    sectors_db["sectors"][اسم_القطاع] = {"manager_id": المسؤول.id, "role_ids": [رتبة_القطاع.id], "protected_roles": []}
    save_json(SECTORS_DATA_FILE, sectors_db)
    await interaction.response.send_message(f"✅ تم إنشاء قطاع **{اسم_القطاع}** وتعيين {المسؤول.mention} مسؤولاً عنه!", ephemeral=True)

@bot.tree.command(name="لوحة_القطاع", description="فتح منيو إدارة القطاع الخاص بك")
async def sector_panel(interaction: discord.Interaction, اسم_القطاع: str):
    sec_data = sectors_db["sectors"].get(اسم_القطاع)
    if not sec_data or (interaction.user.id != sec_data.get("manager_id") and not interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("❌ ليس لديك صلاحية الوصول لهذا القطاع.", ephemeral=True)
        return
    embed = discord.Embed(title=f"⚙️ لوحة تحكم قطاع: {اسم_القطاع}", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed, view=SectorManagementView(اسم_القطاع), ephemeral=True)

# ----------------- 🛡️ نظام الحماية والقائمة البيضاء -----------------
@bot.tree.command(name="القائمة_البيضاء", description="إضافة أو إزالة عضو من القائمة البيضاء المحمية")
@app_commands.checks.has_permissions(administrator=True)
async def whitelist_cmd(interaction: discord.Interaction, عضو: discord.Member):
    uid = عضو.id
    if uid in security_db["whitelist"]:
        security_db["whitelist"].remove(uid)
        save_json(SECURITY_DATA_FILE, security_db)
        await interaction.response.send_message(f"✅ تم إزالة {عضو.mention} من القائمة البيضاء.", ephemeral=True)
    else:
        security_db["whitelist"].append(uid)
        save_json(SECURITY_DATA_FILE, security_db)
        await interaction.response.send_message(f"✅ تم إضافة {عضو.mention} إلى القائمة البيضاء المحمية.", ephemeral=True)

# ----------------- 👁️ نظام الوقّات وسجلات المراقبة -----------------
@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    log_ch_id = logs_db.get("log_channel_id")
    if log_ch_id:
        channel = message.guild.get_channel(log_ch_id)
        if channel:
            embed = discord.Embed(title="👁️ [سجلات الوقّات] رسالة محذوفة", description=f"**المستخدم:** {message.author.mention}\n**الروم:** {message.channel.mention}\n**المحتوى:**\n{message.content}", color=discord.Color.orange())
            await channel.send(embed=embed)

# ----------------- 🎮 نظام الألعاب (10 ألعاب مع التسجيل التلقائي) -----------------
class GameSignupView(discord.ui.View):
    def __init__(self, game_name, required_count=2):
        super().__init__(timeout=60)
        self.game_name = game_name
        self.required_count = required_count
        self.participants = []

    @discord.ui.button(label="تسجيل للمشاركة 🎮", style=discord.ButtonStyle.success, custom_id="game_signup_btn")
    async def signup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.participants:
            await interaction.response.send_message("❌ أنت مسجل مسبقاً في هذه الجولة!", ephemeral=True)
            return
        self.participants.append(interaction.user)
        await interaction.response.send_message(f"✅ تم تسجيك في لعبة **{self.game_name}** بنجاح!", ephemeral=True)
        if len(self.participants) >= self.required_count:
            self.stop()

@bot.tree.command(name="لعبة", description="تشغيل إحدى الألعاب العشر مع التسجيل التلقائي")
@app_commands.choices(اللعبة=[
    app_commands.Choice(name="1. التخمين", value="التخمين"),
    app_commands.Choice(name="2. من أنا؟", value="من أنا؟"),
    app_commands.Choice(name="3. الألغاز", value="الألغاز"),
    app_commands.Choice(name="4. تحدي المعلومات", value="تحدي المعلومات"),
    app_commands.Choice(name="5. صح أو خطأ", value="صح أو خطأ"),
    app_commands.Choice(name="6. خمن الصورة", value="خمن الصورة"),
    app_commands.Choice(name="7. أسرع إجابة", value="أسرع إجابة"),
    app_commands.Choice(name="8. الكلمة المفقودة", value="الكلمة المفقودة"),
    app_commands.Choice(name="9. تحدي الذاكرة", value="تحدي الذاكرة"),
    app_commands.Choice(name="10. حجر ورقة مقص", value="حجر ورقة مقص")
])
async def start_game_cmd(interaction: discord.Interaction, اللعبة: app_commands.Choice[str]):
    game_name = اللعبة.value
    view = GameSignupView(game_name, required_count=2)
    embed = discord.Embed(title=f"🎮 لعبة: {game_name}", description="اضغط على زر التسجيل أدناه للمشاركة في الجولة!", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, view=view)
    await view.wait()
    if view.participants:
        winner = random.choice(view.participants)
        await interaction.followup.send(content=f"🎉 انتهت اللعبة **{game_name}** بفوز العضو {winner.mention}! مبروك!")
    else:
        await interaction.followup.send(content="❌ لم يكتمل عدد المشاركين المطلوب.")

# ----------------- 💡 نظام الاقتراحات التفاعلي -----------------
class SuggestionAdminView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=None)
        self.author_id = author_id
        self.yes_votes = set()
        self.no_votes = set()
        self.is_closed = False

    def update_embed(self, base_embed):
        base_embed.clear_fields()
        base_embed.add_field(name="🟢 تأييد", value=str(len(self.yes_votes)), inline=True)
        base_embed.add_field(name="🔴 غير مؤيد", value=str(len(self.no_votes)), inline=True)
        return base_embed

    @discord.ui.button(label="🟢 تأييد", style=discord.ButtonStyle.success, custom_id="sug_yes", row=0)
    async def say_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.is_closed:
            await interaction.response.send_message("❌ التصويت مغلق.", ephemeral=True)
            return
        uid = interaction.user.id
        self.no_votes.discard(uid)
        self.yes_votes.add(uid)
        embed = self.update_embed(interaction.message.embeds[0])
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🔴 غير مؤيد", style=discord.ButtonStyle.danger, custom_id="sug_no", row=0)
    async def say_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.is_closed:
            await interaction.response.send_message("❌ التصويت مغلق.", ephemeral=True)
            return
        uid = interaction.user.id
        self.yes_votes.discard(uid)
        self.no_votes.add(uid)
        embed = self.update_embed(interaction.message.embeds[0])
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="✅ قبول", style=discord.ButtonStyle.primary, custom_id="sug_accept", row=1)
    async def accept_sug(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ للمسؤولين فقط.", ephemeral=True)
            return
        self.is_closed = True
        for child in self.children:
            child.disabled = True
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "✅ [تم قبول الاقتراح]"
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="❌ رفض", style=discord.ButtonStyle.secondary, custom_id="sug_reject", row=1)
    async def reject_sug(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ للمسؤولين فقط.", ephemeral=True)
            return
        self.is_closed = True
        for child in self.children:
            child.disabled = True
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = "❌ [تم رفض الاقتراح]"
        await interaction.response.edit_message(embed=embed, view=self)

@bot.tree.command(name="اقتراح", description="إرسال اقتراح جديد للتصويت عليه")
async def suggestion_cmd(interaction: discord.Interaction, الاقتراح: str):
    embed = discord.Embed(title="💡 اقتراح جديد", description=الاقتراح, color=discord.Color.gold())
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    embed.add_field(name="🟢 تأييد", value="0", inline=True)
    embed.add_field(name="🔴 غير مؤيد", value="0", inline=True)
    view = SuggestionAdminView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view)

# ----------------- 👋 نظام الترحيب والخروج -----------------
@bot.event
async def on_member_join(member: discord.Member):
    if not welcome_db.get("welcome_enabled", False):
        return
    channel = member.guild.get_channel(welcome_db.get("welcome_channel_id"))
    if channel:
        msg = welcome_db.get("welcome_message", "").format(mention=member.mention, name=member.name, server=member.guild.name)
        await channel.send(msg)

@bot.event
async def on_member_remove(member: discord.Member):
    if not welcome_db.get("leave_enabled", False):
        return
    channel = member.guild.get_channel(welcome_db.get("leave_channel_id"))
    if channel:
        msg = welcome_db.get("leave_message", "").format(mention=member.mention, name=member.name, server=member.guild.name)
        await channel.send(msg)

# ----------------- 🧹 الحذف السريع -----------------
@bot.tree.command(name="حذف", description="حذف عدد محدد من الرسائل في الروم الحالي")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear_messages(interaction: discord.Interaction, عدد: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=عدد)
    msg = await interaction.followup.send(f"🧹 تم حذف {len(deleted)} رسالة بنجاح.", ephemeral=True)
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except Exception:
        pass

# ----------------- 🤖 الذكاء الاصطناعي والتحدث المباشر -----------------
@bot.tree.command(name="قول", description="التحدث مباشرة على لسان البوت")
@app_commands.checks.has_permissions(administrator=True)
async def say_command(interaction: discord.Interaction, الكلام: str):
    ai_db["speaking_mode"] = True
    save_json(AI_DATA_FILE, ai_db)
    await interaction.response.send_message("✅ تم الإرسال.", ephemeral=True)
    await interaction.channel.send(الكلام)

@bot.tree.command(name="إلغاء_قول", description="إيقاف التحدث المباشر")
@app_commands.checks.has_permissions(administrator=True)
async def stop_say_command(interaction: discord.Interaction):
    ai_db["speaking_mode"] = False
    save_json(AI_DATA_FILE, ai_db)
    await interaction.response.send_message("✅ تم إيقاف وضع التحدث المباشر.", ephemeral=True)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if "السلام" in message.content:
        await message.channel.send(f"وعليكم السلام ورحمة الله وبركاته يا {message.author.mention} 🌸")
    elif "ابندك" in message.content or "تبند" in message.content:
        await message.channel.send(f"سوق أقوم أبندك إذا لم تسكت !😘 🤣")
    await bot.process_commands(message)

# ----------------- الأحداث الأساسية والتشغيل -----------------
@bot.event
async def on_ready():
    bot.add_view(TicketControlView())
    bot.add_view(BankMainView())
    bot.add_view(AdminBankPanelView())
    
    for msg_id, menu_data in db_data.get("menus", {}).items():
        buttons = menu_data.get("buttons", [])
        if buttons:
            try:
                bot.add_view(DynamicMenuView(buttons, menu_data.get("menu_type", "admin"), str(msg_id)))
            except Exception:
                pass

    await bot.tree.sync()
    print(f"تم تسجيل الدخول بنجاح باسم {bot.user} 🚀")

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN environment variable.")
    bot.run(TOKEN)
