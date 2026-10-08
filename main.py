import discord
from discord import app_commands
from discord.ext import commands
import datetime

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.moderation = True

bot = commands.Bot(command_prefix="!", intents=intents)

# قواعد البيانات المؤقتة
log_channels = {}     # لتخزين رومات اللوجات
welcome_settings = {} # لتخزين إعدادات الترحيب
bad_words = ["كلمة_ممنوعة_1", "كلمة_ممنوعة_2"] # الكلمات الممنوعة

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"بوت SL الشامل يعمل بنجاح باسم {bot.user}")

# ==========================================
# 1. نظام إعداد رومات اللوجات والترحيب
# ==========================================
@bot.tree.command(name="تحديد-روم-اللوج", description="حدد روم معين لتسجيل الأحداث واللوجات بدقة")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(section=[
    app_commands.Choice(name="حذف وإنشاء الرومات", value="channels"),
    app_commands.Choice(name="حذف وتعديل الرسائل", value="messages"),
    app_commands.Choice(name="دخول وخروج الأعضاء", value="members")
])
async def set_log_channel(interaction: discord.Interaction, section: str, channel: discord.TextChannel):
    guild_id = interaction.guild.id
    if guild_id not in log_channels:
        log_channels[guild_id] = {}
    
    log_channels[guild_id][section] = channel.id
    await interaction.response.send_message(f"تم ربط قسم **{section}** بروم {channel.mention} بنجاح!", ephemeral=True)

async def send_log(guild_id, section, embed):
    if guild_id in log_channels and section in log_channels[guild_id]:
        channel = bot.get_channel(log_channels[guild_id][section])
        if channel:
            await channel.send(embed=embed)

@bot.tree.command(name="اعداد-الترحيب", description="ضبط روم الرسائل والترحيب مع صورة وكلام مخصص")
@app_commands.default_permissions(administrator=True)
async def set_welcome(interaction: discord.Interaction, channel: discord.TextChannel, message: str, image_url: str = None):
    guild_id = interaction.guild.id
    welcome_settings[guild_id] = {
        "channel_id": channel.id,
        "message": message,
        "image_url": image_url
    }
    await interaction.response.send_message(f"تم حفظ إعدادات الترحيب في روم {channel.mention} بنجاح!", ephemeral=True)

# ==========================================
# 2. مراقبة السيرفر (الرومات، الرسائل، الأعضاء)
# ==========================================
@bot.event
async def on_guild_channel_delete(channel):
    embed = discord.Embed(
        title="🗑️ تم حذف روم في السيرفر",
        description=f"**اسم الروم المحذوف:** `{channel.name}`\n**نوع الروم:** {channel.type}",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now()
    )
    await send_log(channel.guild.id, "channels", embed)

@bot.event
async def on_guild_channel_create(channel):
    embed = discord.Embed(
        title="✨ تم إنشاء روم جديد",
        description=f"**الروم:** {channel.mention}\n**الاسم:** `{channel.name}`",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now()
    )
    await send_log(channel.guild.id, "channels", embed)

@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    embed = discord.Embed(
        title="💬 تم حذف رسالة",
        description=f"**الكاتب:** {message.author.mention}\n**الروم:** {message.channel.mention}\n**المحتوى المحذوف:**\n{message.content or '[محتوى ميديا أو فارغ]'}",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.now()
    )
    embed.set_footer(text=f"ID: {message.author.id}")
    await send_log(message.guild.id, "messages", embed)

@bot.event
async def on_message(message):
    if message.author.bot: return
    if any(word in message.content for word in bad_words):
        try:
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention}, ممنوع استخدام هذه الكلمة هنا!", delete_after=4)
        except: pass
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    guild_id = member.guild.id
    embed_log = discord.Embed(
        title="📥 انضم عضو جديد للسيرفر",
        description=f"{member.mention} (`{member.name}`)",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now()
    )
    embed_log.set_thumbnail(url=member.display_avatar.url)
    await send_log(guild_id, "members", embed_log)

    if guild_id in welcome_settings:
        cfg = welcome_settings[guild_id]
        channel = bot.get_channel(cfg["channel_id"])
        if channel:
            custom_msg = cfg["message"].replace("{user}", member.mention).replace("{server}", member.guild.name)
            embed_welcome = discord.Embed(
                title="👋 أهلاً بك في السيرفر",
                description=custom_msg,
                color=discord.Color.gold()
            )
            if cfg["image_url"]:
                embed_welcome.set_image(url=cfg["image_url"])
            embed_welcome.set_thumbnail(url=member.display_avatar.url)
            await channel.send(content=member.mention, embed=embed_welcome)

@bot.event
async def on_member_remove(member):
    embed = discord.Embed(
        title="📤 غادر عضو السيرفر",
        description=f"{member.mention} (`{member.name}`)",
        color=discord.Color.dark_gray(),
        timestamp=datetime.datetime.now()
    )
    await send_log(member.guild.id, "members", embed)

# ==========================================
# 3. نظام الإدارة والميوت (/اسكت)
# ==========================================
@bot.tree.command(name="اسكت", description="إعطاء تايم أوت لعضو لفترة معينة (بالدقائق)")
@app_commands.default_permissions(moderate_members=True)
async def mute_user(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "إزعاج أو مخالفة"):
    delta = datetime.timedelta(minutes=minutes)
    try:
        await member.timeout(datetime.datetime.now(datetime.timezone.utc) + delta, reason=reason)
        await interaction.response.send_message(f"تم إعطاء تايم أوت لـ {member.mention} لمدة **{minutes} دقيقة**. السبب: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"عذراً، تأكد أن صلاحيات البوت أعلى من العضو.", ephemeral=True)

# ==========================================
# 4. نظام التكتات والتقديمات اليدوية الشامل
# ==========================================
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 إغلاق التكت", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("جاري إغلاق التكت وحذفه خلال 5 ثوانٍ...", ephemeral=True)
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete()

class MasterApplicationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_custom_ticket(self, interaction: discord.Interaction, ticket_type: str, cat_name: str):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name=cat_name)
        if not category:
            category = await guild.create_category(cat_name)
        
        channel_name = f"{ticket_type}-{interaction.user.name}".lower().replace(" ", "-")
        existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if existing_channel:
            await interaction.response.send_message(f"لديك تذكرة مفتوحة بالفعل في هذا القسم: {existing_channel.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
        
        embed = discord.Embed(
            title=f"📋 تذكرة {ticket_type}",
            description=f"مرحباً بك {interaction.user.mention}!\nيرجى كتابة تفاصيل طلبك أو الإجابة على الأسئلة هنا، وسيتواجد معك المسؤول في أقرب وقت.",
            color=discord.Color.blue()
        )
        await channel.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"تم فتح تذكرة {ticket_type} بنجاح في الروم: {channel.mention}", ephemeral=True)

    @discord.ui.button(label="🎖️ تقديم عساكر", style=discord.ButtonStyle.primary, custom_id="apply_military")
    async def apply_military(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_custom_ticket(interaction, "عساكر", "تقديمات العساكر")

    @discord.ui.button(label="🛡️ تقديم حرس", style=discord.ButtonStyle.success, custom_id="apply_guard")
    async def apply_guard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_custom_ticket(interaction, "حرس", "تقديمات الحرس")

    @discord.ui.button(label="🔫 تقديم عصابات", style=discord.ButtonStyle.danger, custom_id="apply_gang")
    async def apply_gang(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_custom_ticket(interaction, "عصابات", "تقديمات العصابات")

    @discord.ui.button(label="🎫 تذكرة دعم عامة", style=discord.ButtonStyle.secondary, custom_id="apply_support")
    async def apply_support(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_custom_ticket(interaction, "دعم", "تذاكر الدعم")

@bot.tree.command(name="منيو-التقديمات", description="إرسال لوحة التقديمات والتكتات الشاملة في الروم الحالي")
@app_commands.default_permissions(administrator=True)
async def master_menu(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📌 لوحة التقديمات والتكتات الرسمية",
        description="اختر القسم المناسب بالأسفل عبر الضغط على الزر لفتح تذكرة خاصة بك وتقديم طلبك يدوياً بكل سهولة:",
        color=discord.Color.dark_purple()
    )
    embed.add_field(name="🎖️ العساكر", value="للتقديم على الوظائف العسكرية", inline=True)
    embed.add_field(name="🛡️ الحرس", value="للتقديم على قطاع الحرس", inline=True)
    embed.add_field(name="🔫 العصابات", value="لتقديم وتأسيس العصابات", inline=True)
    embed.add_field(name="🎫 الدعم الفني", value="للاستفسارات وحل المشاكل", inline=True)
    
    await interaction.channel.send(embed=embed, view=MasterApplicationView())
    await interaction.response.send_message("تم إرسال لوحة التقديمات بنجاح!", ephemeral=True)

# تشغيل البوت بالتوكن الخاص بك
bot.run("MTU1MzAwOTMzNzAxNzA0MDk5Ng.GkoRWt.FRsJP1QMp-84HctzRyJvQX713ho54sSggOC3gA")
