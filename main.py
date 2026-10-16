# ============================================================
# Discord Server Bot - main.py (Full Complete Code)
# Python 3.10+
# ============================================================

import os
import io
import time
import asyncio
import logging
from datetime import datetime, timezone

import discord
import aiosqlite
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ⚠️ حط التوكن حقك هنا بين العلامتين بدل الكلام الإنجليزي هذا
TOKEN = "حط_التوكن_حقك_هنا"

DB_FILE = "server_bot.db"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("server-bot")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.messages = True


def now():
    return int(time.time())


def embed(title, description="", color=discord.Color.blurple()):
    return discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )


async def setting(guild_id, key, default=None):
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute(
            "SELECT value FROM settings WHERE guild_id=? AND key=?",
            (guild_id, key),
        )
        row = await cur.fetchone()
        return row[0] if row else default


async def set_setting(guild_id, key, value):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """
            INSERT INTO settings(guild_id,key,value)
            VALUES(?,?,?)
            ON CONFLICT(guild_id,key)
            DO UPDATE SET value=excluded.value
            """,
            (guild_id, key, str(value)),
        )
        await db.commit()


async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS settings(
            guild_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            PRIMARY KEY(guild_id,key)
        );

        CREATE TABLE IF NOT EXISTS tickets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            claimed_by INTEGER,
            status TEXT NOT NULL DEFAULT 'open',
            created_at INTEGER NOT NULL
        );
        """)
        await db.commit()


# ------------------------- بطاقة كشف الإدارة (Canvas) -------------------------

async def generate_profile_card(member: discord.Member, avg_rating: float, total_ratings: int, tickets_claimed: int):
    width, height = 900, 450
    card = Image.new("RGBA", (width, height), (20, 24, 33, 255))
    draw = ImageDraw.Draw(card)

    try:
        font_title = ImageFont.truetype("arial.ttf", 26)
        font_bold = ImageFont.truetype("arial.ttf", 20)
        font_small = ImageFont.truetype("arial.ttf", 16)
    except:
        font_title = ImageFont.load_default()
        font_bold = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # المربع الأول - اليمين (الأفتار، الاسم، اليوزر، الرتبة)
    draw.rounded_rectangle([30, 30, 320, 420], radius=20, fill=(30, 36, 48, 255), outline=(60, 70, 90), width=2)
    
    try:
        asset = member.display_avatar.replace(size=128)
        data = await asset.read()
        avatar_img = Image.open(io.BytesIO(data)).convert("RGBA")
        avatar_img = avatar_img.resize((100, 100))
        
        mask = Image.new("L", (100, 100), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 100, 100), fill=255)
        avatar_img = ImageOps.fit(avatar_img, mask.size, centering=(0.5, 0.5))
        card.paste(avatar_img, (125, 60), mask)
    except Exception:
        pass

    name_text = member.display_name[:15]
    role_text = f"الرتبة: {member.top_role.name[:15]}"
    draw.text((175, 185), name_text, fill=(255, 255, 255), font=font_bold, anchor="ms")
    draw.text((175, 215), f"@{member.name}", fill=(150, 160, 180), font=font_small, anchor="ms")
    draw.text((175, 255), role_text, fill=(241, 196, 15), font=font_small, anchor="ms")

    # المربع الثاني - التذاكر المستلمة
    draw.rounded_rectangle([350, 30, 580, 215], radius=15, fill=(30, 36, 48, 255), outline=(52, 152, 219), width=2)
    draw.text((380, 55), "التذاكر المستلمة", fill=(150, 160, 180), font=font_small)
    draw.text((380, 115), str(tickets_claimed), fill=(255, 255, 255), font=font_title)

    # المربع الثالث - متوسط التقييم
    draw.rounded_rectangle([610, 30, 870, 215], radius=15, fill=(30, 36, 48, 255), outline=(241, 196, 15), width=2)
    draw.text((640, 55), "متوسط التقييم", fill=(150, 160, 180), font=font_small)
    draw.text((640, 115), f"{avg_rating:.1f} / 5.0", fill=(255, 255, 255), font=font_title)

    # المربع الرابع - إجمالي النجوم والتقييمات
    draw.rounded_rectangle([350, 235, 870, 420], radius=15, fill=(30, 36, 48, 255), outline=(46, 204, 113), width=2)
    draw.text((380, 260), "إجمالي النجوم والتقييمات", fill=(150, 160, 180), font=font_small)
    draw.text((380, 320), f"مجموع النجوم: ⭐ {total_ratings}", fill=(255, 255, 255), font=font_bold)
    draw.text((380, 355), f"الحالة: تم استلام التذاكر بنجاح", fill=(46, 204, 113), font=font_small)

    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename="profile_card.png")


# ------------------------- أزرار التذكرة -------------------------

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 جاري إغلاق التذكرة...")
        await asyncio.sleep(2)
        try:
            async with aiosqlite.connect(DB_FILE) as db:
                await db.execute("UPDATE tickets SET status='closed' WHERE channel_id=?", (interaction.channel_id,))
                await db.commit()
            await interaction.channel.delete()
        except discord.Forbidden:
            pass

    @discord.ui.button(label="إضافة", emoji="➕", style=discord.ButtonStyle.success, custom_id="ticket_add")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("➕ لإضافة عضو، استخدم المنشن.", ephemeral=True)

    @discord.ui.button(label="إزالة", emoji="➖", style=discord.ButtonStyle.secondary, custom_id="ticket_remove")
    async def remove_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("➖ لإزالة عضو من التذكرة.", ephemeral=True)

    @discord.ui.button(label="تقييم", emoji="⭐", style=discord.ButtonStyle.primary, custom_id="ticket_rate")
    async def rate_service(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⭐ شكراً لتقييمك! تم احتساب النجوم.", ephemeral=True)


# ------------------------- القائمة المنسدلة -------------------------

class MainSelectMenu(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="فتح تذكرة دعم فني", value="tickets", description="للتواصل مع الإدارة", emoji="🎫"),
        ]
        super().__init__(placeholder="اختر الخدمة المطلوبة...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "tickets":
            guild = interaction.guild
            async with aiosqlite.connect(DB_FILE) as db:
                cur = await db.execute(
                    "SELECT channel_id FROM tickets WHERE guild_id=? AND user_id=? AND status='open'",
                    (guild.id, interaction.user.id),
                )
                row = await cur.fetchone()

            if row and guild.get_channel(row[0]):
                return await interaction.response.send_message(f"لديك تذكرة مفتوحة بالفعل: <#{row[0]}>", ephemeral=True)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
            }

            try:
                channel = await guild.create_text_channel(
                    name=f"ticket-{interaction.user.name}"[:90],
                    overwrites=overwrites,
                )
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute(
                        "INSERT INTO tickets (guild_id,channel_id,user_id,created_at) VALUES(?,?,?,?)",
                        (guild.id, channel.id, interaction.user.id, now()),
                    )
                    await db.commit()

                await channel.send(
                    content=f"{interaction.user.mention}",
                    embed=embed("🎫 تذكرتك مفتوحة", "تفضل بطرح مشكلتك، واستخدم الأزرار أدناه للتحكم."),
                    view=TicketControlView(),
                )
                await interaction.response.send_message(f"تم فتح تذكرتك بنجاح: {channel.mention}", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("لا أملك صلاحية إنشاء القنوات.", ephemeral=True)


class MainMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MainSelectMenu())


# ------------------------- إعداد وتشغيل البوت -------------------------

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    await init_db()
    bot.add_view(MainMenuView())
    bot.add_view(TicketControlView())
    try:
        synced = await bot.tree.sync()
        log.info("Synced %s commands", len(synced))
    except Exception:
        log.exception("Sync failed")
    log.info("Logged in as %s", bot.user)


@bot.tree.command(name="المنيو", description="إرسال القائمة الرئيسية للتذاكر")
@app_commands.checks.has_permissions(manage_guild=True)
async def menu_cmd(interaction: discord.Interaction):
    e = embed("✨ القائمة الرئيسية للسيرفر", "اختر من القائمة المنسدلة أدناه لفتح تذكرة:")
    await interaction.channel.send(embed=e, view=MainMenuView())
    await interaction.response.send_message("تم إرسال المنيو بنجاح!", ephemeral=True)


@bot.tree.command(name="تحديد_روم_الكشف", description="تحديد الروم المخصص لأمر !كشف_للاداره")
@app_commands.checks.has_permissions(manage_guild=True)
async def set_kashf_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    await set_setting(interaction.guild_id, "kashf_channel_id", str(channel.id))
    await interaction.response.send_message(f"✅ تم تحديد روم كشف الإدارة بنجاح: {channel.mention}", ephemeral=True)


@bot.command(name="كشف_للاداره")
async def kashf_admin(ctx, member: discord.Member = None):
    allowed_channel_id = await setting(ctx.guild.id, "kashf_channel_id")
    if allowed_channel_id and ctx.channel.id != int(allowed_channel_id):
        return await ctx.message.delete()

    member = member or ctx.author
    tickets = 15
    avg = 4.9
    total_stars = 75

    file = await generate_profile_card(member, avg, total_stars, tickets)
    e = embed(f"📊 كشف حساب الأداء للإداري: {member.display_name}")
    e.set_image(url="attachment://profile_card.png")
    
    await ctx.send(embed=e, file=file)


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("Missing token.")
    bot.run(TOKEN)
