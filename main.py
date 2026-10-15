import discord
from discord.ext import commands
from discord import app_commands, ui
import datetime
import random
import asyncio
import json, os

DATA_FILE = os.path.join(os.environ.get("DATA_DIR", "/data"), "bot_state.json")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix="-", intents=intents)

# متغيرات الإعدادات العامة
رقم_روم_اللوق = None  
رقم_روم_الترحيب = None
رقم_روم_الاقتراحات = None
رقم_روم_الترقيات = None          # زيادة: روم ترقيات الشرطة
رقم_روم_عصابات_الترقيات = None     # زيادة: روم ترقيات العصابات
رقم_روم_الإدارة_الترقيات = None    # زيادة: روم ترقيات الإدارة
رقم_رتبة_غير_مفعل = None  
رقم_رتبة_المفعل = None    

user_data = {}  
RANKS_XP = {}         # زيادة: رتب ونقاط الشرطة
GANG_RANKS_XP = {}    # زيادة: رتب ونقاط العصابات
ADMIN_RANKS_XP = {}   # زيادة: رتب ونقاط الإدارة

DEFAULT_USER_STATS = {
    "xp": 0, "level": 1, "bank": 1000, "cash": 500,
    "reports": 0, "gang_reports": 0, "tickets_solved": 0,
    "admin_xp": 0, "total_tickets_opened": 0
}

def save_state():
    try:
        state = {
            "رقم_روم_اللوق": رقم_روم_اللوق,
            "رقم_روم_الترحيب": رقم_روم_الترحيب,
            "رقم_روم_الاقتراحات": رقم_روم_الاقتراحات,
            "رقم_روم_الترقيات": رقم_روم_الترقيات,
            "رقم_روم_عصابات_الترقيات": رقم_روم_عصابات_الترقيات,
            "رقم_روم_الإدارة_الترقيات": رقم_روم_الإدارة_الترقيات,
            "رقم_رتبة_غير_مفعل": رقم_رتبة_غير_مفعل,
            "رقم_رتبة_المفعل": رقم_رتبة_المفعل,
            "user_data": {str(uid): stats for uid, stats in user_data.items()},
            "RANKS_XP": RANKS_XP,
            "GANG_RANKS_XP": GANG_RANKS_XP,
            "ADMIN_RANKS_XP": ADMIN_RANKS_XP,
        }
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        tmp_file = DATA_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
        os.replace(tmp_file, DATA_FILE)
    except Exception as e:
        print(f"فشل حفظ البيانات: {e}")

def load_state():
    global رقم_روم_اللوق, رقم_روم_الترحيب, رقم_روم_الاقتراحات, رقم_روم_الترقيات
    global رقم_روم_عصابات_الترقيات, رقم_روم_الإدارة_الترقيات
    global رقم_رتبة_غير_مفعل, رقم_رتبة_المفعل
    global user_data, RANKS_XP, GANG_RANKS_XP, ADMIN_RANKS_XP
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        def as_id(value):
            return int(value) if value is not None else None

        def as_ranks(value):
            return {str(k): int(v) for k, v in (value or {}).items()}

        رقم_روم_اللوق = as_id(state.get("رقم_روم_اللوق"))
        رقم_روم_الترحيب = as_id(state.get("رقم_روم_الترحيب"))
        رقم_روم_الاقتراحات = as_id(state.get("رقم_روم_الاقتراحات"))
        رقم_روم_الترقيات = as_id(state.get("رقم_روم_الترقيات"))
        رقم_روم_عصابات_الترقيات = as_id(state.get("رقم_روم_عصابات_الترقيات"))
        رقم_روم_الإدارة_الترقيات = as_id(state.get("رقم_روم_الإدارة_الترقيات"))
        رقم_رتبة_غير_مفعل = as_id(state.get("رقم_رتبة_غير_مفعل"))
        رقم_رتبة_المفعل = as_id(state.get("رقم_رتبة_المفعل"))

        loaded_users = {}
        for uid, stats in (state.get("user_data") or {}).items():
            merged = dict(DEFAULT_USER_STATS)
            merged.update({k: int(v) for k, v in stats.items()})
            loaded_users[int(uid)] = merged
        user_data = loaded_users

        RANKS_XP = as_ranks(state.get("RANKS_XP"))
        GANG_RANKS_XP = as_ranks(state.get("GANG_RANKS_XP"))
        ADMIN_RANKS_XP = as_ranks(state.get("ADMIN_RANKS_XP"))
    except Exception as e:
        print(f"فشل تحميل البيانات: {e}")

def حساب_النقاط(user_id):
    if user_id not in user_data:
        user_data[user_id] = dict(DEFAULT_USER_STATS)
        save_state()
    return user_data[user_id]

# --- زيادة: فحوصات الترقيات التلقائية للقطاعات ---
async def فحص_الترقية(member: discord.Member):
    stats = حساب_النقاط(member.id)
    current_xp = stats["xp"]
    new_rank = None
    for rank_name, required_xp in RANKS_XP.items():
        if current_xp >= required_xp:
            new_rank = rank_name
    if new_rank:
        guild = member.guild
        role = discord.utils.get(guild.roles, name=new_rank)
        if role and role not in member.roles:
            await member.add_roles(role)
            if رقم_روم_الترقيات:
                target_chan = guild.get_channel(رقم_روم_الترقيات)
                if target_chan:
                    embed = discord.Embed(
                        title="🎖️ ترقية عسكرية جديدة!",
                        description=f"تهانينا العريضة للعسكري {member.mention}\nتمت ترقيته رسمياً إلى رتبة **[{new_rank}]** بعد وصوله إلى {current_xp} XP.",
                        color=discord.Color.gold()
                    )
                    await target_chan.send(embed=embed)

async def فحص_ترقية_عصابة(member: discord.Member):
    stats = حساب_النقاط(member.id)
    current_xp = stats["xp"]
    new_rank = None
    for rank_name, required_xp in GANG_RANKS_XP.items():
        if current_xp >= required_xp:
            new_rank = rank_name
    if new_rank:
        guild = member.guild
        role = discord.utils.get(guild.roles, name=new_rank)
        if role and role not in member.roles:
            await member.add_roles(role)
            if رقم_روم_عصابات_الترقيات:
                target_chan = guild.get_channel(رقم_روم_عصابات_الترقيات)
                if target_chan:
                    embed = discord.Embed(
                        title="🏴 ترقية نفوذ عصابة جديدة!",
                        description=f"تنبيه إجرامي! العضو {member.mention}\nارتفع نفوذه وتمت ترقيته إلى رتبة **[{new_rank}]** بعد وصوله إلى {current_xp} XP.",
                        color=discord.Color.dark_red()
                    )
                    await target_chan.send(embed=embed)

async def فحص_ترقية_إدارة(member: discord.Member):
    stats = حساب_النقاط(member.id)
    current_admin_xp = stats["admin_xp"]
    new_rank = None
    for rank_name, required_xp in ADMIN_RANKS_XP.items():
        if current_admin_xp >= required_xp:
            new_rank = rank_name
    if new_rank:
        guild = member.guild
        role = discord.utils.get(guild.roles, name=new_rank)
        if role and role not in member.roles:
            await member.add_roles(role)
            if رقم_روم_الإدارة_الترقيات:
                target_chan = guild.get_channel(رقم_روم_الإدارة_الترقيات)
                if target_chan:
                    embed = discord.Embed(
                        title="🛡️ ترقية إدارية مميزة!",
                        description=f"شكراً لجهودك العظيمة يا إداري {member.mention}!\nتمت ترقيتك إلى رتبة **[{new_rank}]** بعد وصوله إلى {current_admin_xp} نقطة إدارية.",
                        color=discord.Color.blue()
                    )
                    await target_chan.send(embed=embed)

# --- زيادة: نظام أزرار تقييم التكت للإداري ---
class تقييم_التكت_View(ui.View):
    def __init__(self, admin_member: discord.Member):
        super().__init__(timeout=None)
        self.admin_member = admin_member

    async def process_rating(self, interaction: discord.Interaction, stars: int):
        stats = حساب_النقاط(self.admin_member.id)
        stats["admin_xp"] += stars
        stats["tickets_solved"] += 1
        save_state()
        
        embed = discord.Embed(
            title="⭐ تم تقييم خدمة الإداري بنجاح",
            description=f"تم منح الإداري {self.admin_member.mention} تقييم **{stars} نجوم**\nوعليه تمت إضافة **+{stars} نقاط إدارية** لرصيده!",
            color=discord.Color.gold()
        )
        embed.add_field(name="إجمالي النقاط الإدارية", value=f"{stats['admin_xp']} نقطة", inline=True)
        embed.add_field(name="إجمالي التكتات المحلولة", value=str(stats["tickets_solved"]), inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)
        await فحص_ترقية_إدارة(self.admin_member)

    @ui.button(label="⭐ 1", style=discord.ButtonStyle.secondary)
    async def star_1(self, interaction: discord.Interaction, button: ui.Button):
        await self.process_rating(interaction, 1)

    @ui.button(label="⭐⭐ 2", style=discord.ButtonStyle.secondary)
    async def star_2(self, interaction: discord.Interaction, button: ui.Button):
        await self.process_rating(interaction, 2)

    @ui.button(label="⭐⭐⭐ 3", style=discord.ButtonStyle.primary)
    async def star_3(self, interaction: discord.Interaction, button: ui.Button):
        await self.process_rating(interaction, 3)

    @ui.button(label="⭐⭐⭐⭐ 4", style=discord.ButtonStyle.success)
    async def star_4(self, interaction: discord.Interaction, button: ui.Button):
        await self.process_rating(interaction, 4)

    @ui.button(label="⭐⭐⭐⭐⭐ 5", style=discord.ButtonStyle.success)
    async def star_5(self, interaction: discord.Interaction, button: ui.Button):
        await self.process_rating(interaction, 5)

# --- زيادة: منيو تقفيل التكت ---
class منيو_تقفيل_التكت(ui.View):
    def __init__(self, admin_member: discord.Member):
        super().__init__(timeout=None)
        self.admin_member = admin_member

    @ui.button(label="🔒 قفل التكت والتقييم", style=discord.ButtonStyle.danger)
    async def قفل_التكت(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("للمشرفين والإدارة فقط", ephemeral=True)
            return
        
        view = تقييم_التكت_View(self.admin_member)
        embed = discord.Embed(
            title="🔒 تم إغلاق التكت",
            description=f"الرجاء تقييم أداء الإداري المسؤول ({self.admin_member.mention}) بالضغط على عدد النجوم المناسب بالأسفل:",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, view=view)

# --- زيادة: منيو فتح التكتات الأساسي ---
class منيو_فتح_التكت(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🎫 فتح تكت دعم جديد", style=discord.ButtonStyle.primary, emoji="📩")
    async def فتح_تكت(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        member = interaction.user
        
        stats = حساب_النقاط(member.id)
        stats["total_tickets_opened"] += 1
        save_state()

        if رقم_روم_اللوق:
            log_chan = guild.get_channel(رقم_روم_اللوق)
            if log_chan:
                embed_log = discord.Embed(title="🎫 رصد فتح تكت جديد", color=discord.Color.orange())
                embed_log.add_field(name="العضو", value=member.mention, inline=False)
                embed_log.add_field(name="إجمالي مرات فتح التكتات", value=str(stats["total_tickets_opened"]), inline=True)
                embed_log.timestamp = datetime.datetime.now()
                await log_chan.send(embed=embed_log)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        ticket_chan = await guild.create_text_channel(name=f"تكت-{member.name}", overwrites=overwrites)
        view = منيو_تقفيل_التكت(member)
        embed = discord.Embed(
            title="مرحباً بك في تكت الدعم",
            description=f"أهلاً بك يا {member.mention}\nسيتم خدمتك بأسرع وقت ممكن بواسطة الإدارة.\nعند الانتهاء، يستطيع المشرف قفل التكت من الزر بالأسفل.",
            color=discord.Color.blue()
        )
        await ticket_chan.send(embed=embed, view=view)
        await interaction.response.send_message(f"تم إنشاء تكت الخاص بك بنجاح: {ticket_chan.mention}", ephemeral=True)

# --- 1. النظام التلقائي والترحيب والحماية ---
@bot.event
async def on_member_join(member):
    if رقم_رتبة_غير_مفعل:
        role = member.guild.get_role(رقم_رتبة_غير_مفعل)
        if role:
            try:
                await member.add_roles(role)
            except Exception:
                pass

    if رقم_روم_الترحيب:
        chan = member.guild.get_channel(رقم_روم_الترحيب)
        if chan:
            embed = discord.Embed(
                title="أهلاً بك في السيرفر",
                description=f"منور يا {member.mention}\nتم منحك رتبة غير مفعل تلقائياً بانتظار التفعيل.",
                color=discord.Color.purple()
            )
            await chan.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    stats = حساب_النقاط(message.author.id)
    stats["xp"] += 5
    if stats["xp"] >= stats["level"] * 100:
        stats["level"] += 1
    save_state()

    content = message.content.lower()
    if "discord.gg/" in content or "http://" in content or "https://" in content:
        await message.delete()
        await message.channel.send(f"{message.author.mention} ممنوع إرسال الروابط هنا!", delete_after=5)
        return

    await bot.process_commands(message)

# --- 2. لوحة تفعيل الأعضاء ---
class لوحة_التفعيل(ui.View):
    def __init__(self, member: discord.Member, account_name: str):
        super().__init__(timeout=None)
        self.member = member
        self.account_name = account_name

    @ui.button(label="قبول التفعيل", style=discord.ButtonStyle.success)
    async def قبول(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("للإدارة فقط", ephemeral=True)
            return

        guild = interaction.guild
        try:
            if رقم_رتبة_المفعل:
                v_role = guild.get_role(رقم_رتبة_المفعل)
                if v_role:
                    await self.member.add_roles(v_role)
            if رقم_رتبة_غير_مفعل:
                un_role = guild.get_role(رقم_رتبة_غير_مفعل)
                if un_role:
                    await self.member.remove_roles(un_role)

            await self.member.edit(nick=f"[RP] {self.account_name}")
            await interaction.message.edit(view=None)
            await interaction.response.send_message(f"تم تفعيل العضو {self.member.mention} وتغيير اسمه بنجاح", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"حدث خطأ: {e}", ephemeral=True)

    @ui.button(label="رفض الطلب", style=discord.ButtonStyle.danger)
    async def رفض(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("للإدارة فقط", ephemeral=True)
            return
        await interaction.message.edit(view=None)
        await interaction.response.send_message("تم رفض طلب التفعيل", ephemeral=True)

class لوحة_الاقتراح(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="قبول", style=discord.ButtonStyle.success)
    async def قبول_اقتراح(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return
        await interaction.message.edit(view=None)
        await interaction.response.send_message("تم قبول الاقتراح", ephemeral=True)

    @ui.button(label="رفض", style=discord.ButtonStyle.danger)
    async def رفض_اقتراح(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return
        await interaction.message.edit(view=None)
        await interaction.response.send_message("تم رفض الاقتراح", ephemeral=True)

# --- 3. أوامر السلاش (الإدارة والتفعيل والاقتصاد والرولبلاي) ---
@bot.tree.command(name="ضبط_رتبة_غير_مفعل", description="تحديد رتبة غير المفعل التلقائية")
@app_commands.checks.has_permissions(administrator=True)
async def ضبط_رتبة_غير_مفعل(interaction: discord.Interaction, آيدي_الرتبة: str):
    global رقم_رتبة_غير_مفعل
    رقم_رتبة_غير_مفعل = int(آيدي_الرتبة)
    save_state()
    await interaction.response.send_message(f"تم ضبط رتبة غير المفعل برقم: {آيدي_الرتبة}", ephemeral=True)

@bot.tree.command(name="ضبط_رتبة_المفعل", description="تحديد رتبة المفعل عند القبول")
@app_commands.checks.has_permissions(administrator=True)
async def ضبط_رتبة_المفعل(interaction: discord.Interaction, آيدي_الرتبة: str):
    global رقم_رتبة_المفعل
    رقم_رتبة_المفعل = int(آيدي_الرتبة)
    save_state()
    await interaction.response.send_message(f"تم ضبط رتبة المفعل برقم: {آيدي_الرتبة}", ephemeral=True)

@bot.tree.command(name="ضبط_اللوق", description="تحديد روم السجلات واللوق")
@app_commands.checks.has_permissions(administrator=True)
async def ضبط_اللوق(interaction: discord.Interaction, الروم: discord.TextChannel):
    global رقم_روم_اللوق
    رقم_روم_اللوق = الروم.id
    save_state()
    await interaction.response.send_message(f"تم ضبط روم اللوق: {الروم.mention}", ephemeral=True)

@bot.tree.command(name="ضبط_الاقتراحات", description="تحديد روم الاقتراحات")
@app_commands.checks.has_permissions(administrator=True)
async def ضبط_الاقتراحات(interaction: discord.Interaction, الروم: discord.TextChannel):
    global رقم_روم_الاقتراحات
    رقم_روم_الاقتراحات = الروم.id
    save_state()
    await interaction.response.send_message(f"تم ضبط روم الاقتراحات: {الروم.mention}", ephemeral=True)

# --- زيادة: ضبط أروام ومستويات القطاعات والتكتات ---
@bot.tree.command(name="ضبط_روم_الترقيات", description="تحديد روم إرسال إعلانات ترقيات الشرطة")
@app_commands.checks.has_permissions(administrator=True)
async def ضبط_روم_الترقيات(interaction: discord.Interaction, الروم: discord.TextChannel):
    global رقم_روم_الترقيات
    رقم_روم_الترقيات = الروم.id
    save_state()
    await interaction.response.send_message(f"تم ضبط روم ترقيات الشرطة: {الروم.mention}", ephemeral=True)

@bot.tree.command(name="ضبط_روم_عصابات_الترقيات", description="تحديد روم إرسال إعلانات ترقيات العصابات")
@app_commands.checks.has_permissions(administrator=True)
async def ضبط_روم_عصابات_الترقيات(interaction: discord.Interaction, الروم: discord.TextChannel):
    global رقم_روم_عصابات_الترقيات
    رقم_روم_عصابات_الترقيات = الروم.id
    save_state()
    await interaction.response.send_message(f"تم ضبط روم ترقيات العصابات: {الروم.mention}", ephemeral=True)

@bot.tree.command(name="ضبط_روم_الإدارة_الترقيات", description="تحديد روم إرسال إعلانات ترقيات الإدارة")
@app_commands.checks.has_permissions(administrator=True)
async def ضبط_روم_الإدارة_الترقيات(interaction: discord.Interaction, الروم: discord.TextChannel):
    global رقم_روم_الإدارة_الترقيات
    رقم_روم_الإدارة_الترقيات = الروم.id
    save_state()
    await interaction.response.send_message(f"تم ضبط روم ترقيات الإدارة: {الروم.mention}", ephemeral=True)

@bot.tree.command(name="تحديد_ترقية_شرطة", description="تحديد عدد الـ XP المطلوب لرتبة شرطة معينة")
@app_commands.checks.has_permissions(administrator=True)
async def تحديد_ترقية_شرطة(interaction: discord.Interaction, اسم_الرتبة: str, النقاط_المطلوبة: int):
    RANKS_XP[اسم_الرتبة] = النقاط_المطلوبة
    save_state()
    await interaction.response.send_message(f"✅ تم ضبط رتبة الشرطة **{اسم_الرتبة}** لتتطلب **{النقاط_المطلوبة} XP**", ephemeral=True)

@bot.tree.command(name="تحديد_ترقية_عصابة", description="تحديد عدد الـ XP المطلوب لرتبة عصابة معينة")
@app_commands.checks.has_permissions(administrator=True)
async def تحديد_ترقية_عصابة(interaction: discord.Interaction, اسم_الرتبة: str, النقاط_المطلوبة: int):
    GANG_RANKS_XP[اسم_الرتبة] = النقاط_المطلوبة
    save_state()
    await interaction.response.send_message(f"🏴 تم ضبط رتبة العصابة **{اسم_الرتبة}** لتتطلب **{النقاط_المطلوبة} XP**", ephemeral=True)

@bot.tree.command(name="تحديد_رتبة_إدارة", description="تحديد عدد النقاط الإدارية المطلوبة لرتبة الإدارة")
@app_commands.checks.has_permissions(administrator=True)
async def تحديد_رتبة_إدارة(interaction: discord.Interaction, اسم_الرتبة: str, النقاط_المطلوبة: int):
    ADMIN_RANKS_XP[اسم_الرتبة] = النقاط_المطلوبة
    save_state()
    await interaction.response.send_message(f"🛡️ تم ضبط رتبة الإدارة **{اسم_الرتبة}** لتتطلب **{النقاط_المطلوبة} نقطة**", ephemeral=True)

@bot.tree.command(name="قبول_تقرير", description="قبول تقرير عسكري وإعطائه XP محدد")
@app_commands.checks.has_permissions(administrator=True)
async def قبول_تقرير(interaction: discord.Interaction, العسكري: discord.Member, نقاط_المهمة: int, ملاحظة: str = "تقرير مكتمل"):
    stats = حساب_النقاط(العسكري.id)
    stats["xp"] += نقاط_المهمة
    stats["reports"] += 1
    save_state()
    embed = discord.Embed(title="👮‍♂️ قبول تقرير عسكري", color=discord.Color.green())
    embed.add_field(name="العسكري", value=العسكري.mention, inline=False)
    embed.add_field(name="النقاط المضافة", value=f"+{نقاط_المهمة} XP", inline=True)
    embed.add_field(name="إجمالي النقاط", value=f"{stats['xp']} XP", inline=True)
    await interaction.response.send_message(embed=embed)
    await فحص_الترقية(العسكري)

@bot.tree.command(name="قبول_تقرير_عصابة", description="قبول تقرير عصابة وإعطائه XP محدد")
@app_commands.checks.has_permissions(administrator=True)
async def قبول_تقرير_عصابة(interaction: discord.Interaction, العضو: discord.Member, نقاط_المهام: int, ملاحظة: str = "عملية ناجحة"):
    stats = حساب_النقاط(العضو.id)
    stats["xp"] += نقاط_المهام
    stats["gang_reports"] += 1
    save_state()
    embed = discord.Embed(title="🏴 قبول تقرير عصابة", color=discord.Color.dark_red())
    embed.add_field(name="العضو", value=العضو.mention, inline=False)
    embed.add_field(name="النقاط المضافة", value=f"+{نقاط_المهام} XP", inline=True)
    embed.add_field(name="إجمالي النقاط", value=f"{stats['xp']} XP", inline=True)
    await interaction.response.send_message(embed=embed)
    await فحص_ترقية_عصابة(العضو)

@bot.tree.command(name="منيو_التكتات", description="إرسال رسالة منيو فتح التكتات في الشات الحالي")
@app_commands.checks.has_permissions(administrator=True)
async def منيو_التكتات(interaction: discord.Interaction):
    view = منيو_فتح_التكت()
    embed = discord.Embed(
        title="🎫 نظام تكتات السيرفر",
        description="اضغط على الزر بالأسفل لفتح تكت جديد للتواصل مع الإدارة أو طلب مساعدة.",
        color=discord.Color.purple()
    )
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("تم إرسال منيو التكتات بنجاح", ephemeral=True)

@bot.tree.command(name="طلب_تفعيل", description="إرسال طلب تفعيل حسابك للإدارة")
async def طلب_تفعيل(interaction: discord.Interaction, اسم_الحساب: str):
    if not رقم_روم_اللوق:
        await interaction.response.send_message("لم يتم تحديد روم اللوق بعد", ephemeral=True)
        return
    log_chan = interaction.guild.get_channel(رقم_روم_اللوق)
    if log_chan:
        embed = discord.Embed(title="طلب تفعيل جديد", color=discord.Color.gold())
        embed.add_field(name="العضو", value=interaction.user.mention, inline=False)
        embed.add_field(name="اسم الحساب", value=اسم_الحساب, inline=False)
        view = لوحة_التفعيل(interaction.user, اسم_الحساب)
        await log_chan.send(embed=embed, view=view)
        await interaction.response.send_message("تم إرسال طلب التفعيل بنجاح", ephemeral=True)

@bot.tree.command(name="اقتراح", description="إرسال اقتراح جديد لتطوير السيرفر")
async def اقتراح(interaction: discord.Interaction, النص: str):
    if not رقم_روم_الاقتراحات:
        await interaction.response.send_message("لم يتم تحديد روم الاقتراحات بعد", ephemeral=True)
        return
    sug_chan = interaction.guild.get_channel(رقم_روم_الاقتراحات)
    if sug_chan:
        embed = discord.Embed(title="اقتراح جديد", description=النص, color=discord.Color.blue())
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        view = لوحة_الاقتراح()
        await sug_chan.send(embed=embed, view=view)
        await interaction.response.send_message("تم إرسال اقتراحك بنجاح", ephemeral=True)

@bot.tree.command(name="كشف_حساب", description="عرض إحصائيات البروفايل والأموال")
async def كشف_حساب(interaction: discord.Interaction, العضو: discord.Member = None):
    target = العضو or interaction.user
    stats = حساب_النقاط(target.id)
    embed = discord.Embed(title=f"كشف حساب | {target.name}", color=discord.Color.purple())
    embed.add_field(name="المستوى", value=str(stats['level']), inline=True)
    embed.add_field(name="الخبرة XP", value=str(stats['xp']), inline=True)
    embed.add_field(name="النقاط الإدارية", value=str(stats['admin_xp']), inline=True)
    embed.add_field(name="تقارير الشرطة المقبولة", value=str(stats['reports']), inline=True)
    embed.add_field(name="تقارير العصابات المقبولة", value=str(stats['gang_reports']), inline=True)
    embed.add_field(name="التكتات المحلولة (إداري)", value=str(stats['tickets_solved']), inline=True)
    embed.add_field(name="التكتات التي فتحها", value=str(stats['total_tickets_opened']), inline=True)
    embed.add_field(name="رصيد البنك", value=f"{stats['bank']} $", inline=True)
    embed.add_field(name="الكاش", value=f"{stats['cash']} $", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="بنك", description="عرض رصيدك المالي الحالي")
async def بنك(interaction: discord.Interaction):
    stats = حساب_النقاط(interaction.user.id)
    await interaction.response.send_message(f"رصيدك في البنك: {stats['bank']} $ | الكاش: {stats['cash']} $", ephemeral=True)

@bot.tree.command(name="راتب", description="استلام الراتب اليومي")
async def راتب(interaction: discord.Interaction):
    stats = حساب_النقاط(interaction.user.id)
    stats['cash'] += 200
    save_state()
    await interaction.response.send_message("تم استلام راتبك اليومي بقيمة 200 $ بنجاح!", ephemeral=True)

@bot.tree.command(name="تحويل", description="تحويل أموال لعضو آخر")
async def تحويل(interaction: discord.Interaction, العضو: discord.Member, المبلغ: int):
    stats_sender = حساب_النقاط(interaction.user.id)
    stats_receiver = حساب_النقاط(العضو.id)
    if stats_sender['cash'] < المبلغ:
        await interaction.response.send_message("ليس لديك ما يكفي من الكاش!", ephemeral=True)
        return
    stats_sender['cash'] -= المبلغ
    stats_receiver['cash'] += المبلغ
    save_state()
    await interaction.response.send_message(f"تم تحويل {المبلغ} $ إلى {العضو.mention} بنجاح", ephemeral=True)

@bot.tree.command(name="هوية", description="عرض بطاقة الهوية الخاصة بالشخصية")
async def هوية(interaction: discord.Interaction, العضو: discord.Member = None):
    target = العضو or interaction.user
    embed = discord.Embed(title=f"بطاقة هوية الرولبلاي | {target.name}", description="رتبة حكومية / مدنية معتمدة", color=discord.Color.gold())
    embed.add_field(name="الحالة", value="مفعل ومسجل", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="بلاغ_شرطة", description="إرسال بلاغ أمني عاجل للجهات المختصة")
async def بلاغ_شرطة(interaction: discord.Interaction, البلاغ: str):
    await interaction.response.send_message(f"تم إرسال بلاغك الأمني بنجاح: {البلاغ}", ephemeral=True)

@bot.tree.command(name="صوتي_انشاء", description="إنشاء روم صوتي خاص بك")
async def صوتي_انشاء(interaction: discord.Interaction):
    guild = interaction.guild
    overwrites = {guild.default_role: discord.PermissionOverwrite(connect=True), interaction.user: discord.PermissionOverwrite(connect=True, manage_channels=True)}
    chan = await guild.create_voice_channel(name=f"روم {interaction.user.name}", overwrites=overwrites)
    await interaction.response.send_message(f"تم إنشاء رومك الصوتي: {chan.mention}", ephemeral=True)

@bot.tree.command(name="صوتي_قفل", description="قفل رومك الصوتي الحالي")
async def صوتي_قفل(interaction: discord.Interaction):
    if interaction.user.voice and interaction.user.voice.channel:
        await interaction.user.voice.channel.set_permissions(interaction.guild.default_role, connect=False)
        await interaction.response.send_message("تم قفل رومك الصوتي", ephemeral=True)
    else:
        await interaction.response.send_message("لست في روم صوتي حالياً", ephemeral=True)

@bot.tree.command(name="صوتي_فتح", description="فتح رومك الصوتي للجميع")
async def صوتي_فتح(interaction: discord.Interaction):
    if interaction.user.voice and interaction.user.voice.channel:
        await interaction.user.voice.channel.set_permissions(interaction.guild.default_role, connect=True)
        await interaction.response.send_message("تم فتح رومك الصوتي", ephemeral=True)
    else:
        await interaction.response.send_message("لست في روم صوتي حالياً", ephemeral=True)

@bot.tree.command(name="قفل_الشات", description="إغلاق الشات الحالي عن الجميع")
@app_commands.checks.has_permissions(manage_channels=True)
async def قفل_الشات(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("تم قفل الشات بنجاح", ephemeral=True)

# --- زيادة: أمر قفل الشات المخصص لرتبة معينة ---
@bot.tree.command(name="قفل_شات_مخصص", description="قفل الشات والسماح لرتبة معينة فقط بالكتابة")
@app_commands.checks.has_permissions(manage_channels=True)
async def قفل_شات_مخصص(interaction: discord.Interaction, الرتبة: discord.Role):
    guild = interaction.guild
    channel = interaction.channel
    await channel.set_permissions(guild.default_role, send_messages=False)
    await channel.set_permissions(الرتبة, send_messages=True)
    await channel.set_permissions(guild.me, send_messages=True)
    await interaction.response.send_message(f"🔒 تم قفل الشات. وأصبح مخصصاً للكتابة فقط لـ: {الرتبة.mention}", ephemeral=True)

@bot.tree.command(name="فتح_الشات", description="فتح الشات الحالي للجميع")
@app_commands.checks.has_permissions(manage_channels=True)
async def فتح_الشات(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("تم فتح الشات بنجاح", ephemeral=True)

@bot.tree.command(name="مسح", description="مسح وحذف رسائل الشات")
@app_commands.checks.has_permissions(manage_messages=True)
async def مسح(interaction: discord.Interaction, العدد: int):
    await interaction.channel.purge(limit=العدد)
    await interaction.response.send_message(f"تم مسح {العدد} رسالة بنجاح", ephemeral=True)

@bot.tree.command(name="اسكت", description="إعطاء تايم أوت لعضو مخالف")
@app_commands.checks.has_permissions(moderate_members=True)
async def اسكت(interaction: discord.Interaction, العضو: discord.Member, الدقائق: int, السبب: str = "مخالفة"):
    await العضو.timeout(datetime.timedelta(minutes=الدقائق), reason=السبب)
    await interaction.response.send_message(f"تم إسكات العضو {العضو.mention} لمدة {الدقائق} دقائق بسبب: {السبب}", ephemeral=True)

@bot.tree.command(name="باند", description="حظر عضو نهائياً من السيرفر")
@app_commands.checks.has_permissions(ban_members=True)
async def باند(interaction: discord.Interaction, العضو: discord.Member, السبب: str = "مخالفة جسيمة"):
    await العضو.ban(reason=السبب)
    await interaction.response.send_message(f"تم حظر العضو {العضو.mention} نهائياً.", ephemeral=True)

@bot.tree.command(name="قول", description="إرسال رسالة موجهة باسم البوت")
@app_commands.checks.has_permissions(administrator=True)
async def قول(interaction: discord.Interaction, النص: str):
    await interaction.channel.send(النص)
    await interaction.response.send_message("تم إرسال الرسالة", ephemeral=True)

# --- 4. ألعاب البادئة ---
@bot.command(name="لعب")
async def لعب(ctx):
    قائمة = "• `-مافيا` : لعبة المافيا\n• `-عكس` : لعبة العكس\n• `-فكك` : فكك الكلمات\n• `-سرعة` : اختبار السرعة"
    embed = discord.Embed(title="قائمة الألعاب والفعاليات", description=قائمة, color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="مافيا")
async def مافيا(ctx):
    await ctx.send("بدأت لعبة المافيا التفاعلية!")

@bot.command(name="عكس")
async def عكس(ctx):
    await ctx.send(f"لعبة العكس: أسرع واحد يكتب اسم السيرفر: {ctx.guild.name}")

@bot.command(name="فكك")
async def فكك(ctx):
    await ctx.send("لعبة فكك الكلمات: جاري تحضير الكلمة...")

@bot.command(name="سرعة")
async def سرعة(ctx):
    await ctx.send("اختبار سرعة الكتابة بدأ!")

# --- 5. تشغيل البوت ---
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"تم تسجيل الدخول باسم {bot.user.name} وتم مزامنة كافة أوامر السلاش بنجاح!")

load_state()
bot.run(os.environ['TOKEN'])
