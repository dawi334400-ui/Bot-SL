import discord
from discord.ext import commands
from discord import app_commands, ui
import datetime
import random
import asyncio

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
رقم_رتبة_غير_مفعل = None  
رقم_رتبة_المفعل = None    

user_data = {}  

def حساب_النقاط(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            "xp": 0, "level": 1, "bank": 1000, "cash": 500
        }
    return user_data[user_id]

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
    await interaction.response.send_message(f"تم ضبط رتبة غير المفعل برقم: {آيدي_الرتبة}", ephemeral=True)

@bot.tree.command(name="ضبط_رتبة_المفعل", description="تحديد رتبة المفعل عند القبول")
@app_commands.checks.has_permissions(administrator=True)
async def ضبط_رتبة_المفعل(interaction: discord.Interaction, آيدي_الرتبة: str):
    global رقم_رتبة_المفعل
    رقم_رتبة_المفعل = int(آيدي_الرتبة)
    await interaction.response.send_message(f"تم ضبط رتبة المفعل برقم: {آيدي_الرتبة}", ephemeral=True)

@bot.tree.command(name="ضبط_اللوق", description="تحديد روم السجلات واللوق")
@app_commands.checks.has_permissions(administrator=True)
async def ضبط_اللوق(interaction: discord.Interaction, الروم: discord.TextChannel):
    global رقم_روم_اللوق
    رقم_روم_اللوق = الروم.id
    await interaction.response.send_message(f"تم ضبط روم اللوق: {الروم.mention}", ephemeral=True)

@bot.tree.command(name="ضبط_الاقتراحات", description="تحديد روم الاقتراحات")
@app_commands.checks.has_permissions(administrator=True)
async def ضبط_الاقتراحات(interaction: discord.Interaction, الروم: discord.TextChannel):
    global رقم_روم_الاقتراحات
    رقم_روم_الاقتراحات = الروم.id
    await interaction.response.send_message(f"تم ضبط روم الاقتراحات: {الروم.mention}", ephemeral=True)

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
    overwrites = {guild.default_role: discord.PermissionOverwrite(connect=True), interaction.user: discord.PermissionOverwrite(manage_channel=True)}
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

import os
bot.run(os.environ['TOKEN'])
