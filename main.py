# ============================================================
# Discord Server Bot - main.py (!كشف command in specific channel)
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

TOKEN = os.getenv("DISCORD_TOKEN")
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


# ------------------------- تصميم بطاقة الكشف (Canvas) -------------------------

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

    # المربع الأول - اليمين (الأفتار والاسم والرتبة)
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
    draw.text((380, 355), f"الحالة: نشط في الإدارة", fill=(46, 204, 113), font=font_small)

    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename="profile_card.png")


# ------------------------- المنيو والتذاكر -------------------------

class MainSelectMenu(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="الدعم الفني والتذاكر", value="tickets", description="فتح تذكرة جديدة", emoji="🎫"),
            discord.SelectOption(label="البنك والاقتصاد", value="economy", description="عرض الرصيد", emoji="🏦"),
            discord.SelectOption(label="الألعاب والمستويات", value="games", description="عرض مستواك", emoji="🎮"),
        ]
        super().__init__(placeholder="اختر القسم الذي تريده...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "tickets":
            await interaction.response.send_message("تم اختيار قسم التذاكر بنجاح!", ephemeral=True)
        elif self.values[0] == "economy":
            await interaction.response.send_message("قائمة البنك والاقتصاد.", ephemeral=True)
        elif self.values[0] == "games":
            await interaction.response.send_message("قائمة الألعاب والمستويات.", ephemeral=True)


class MainMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MainSelectMenu())


# ------------------------- إعداد البوت -------------------------

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    await init_db()
    bot.add_view(MainMenuView())
    log.info("Logged in as %s", bot.user)


# أمر إرسال المنيو (سلاش كومانْد عادي)
@bot.tree.command(name="المنيو", description="إرسال القائمة الرئيسية للبوت")
@app_commands.checks.has_permissions(manage_guild=True)
async def menu_cmd(interaction: discord.Interaction):
    e = embed("✨ القائمة الرئيسية للسيرفر", "اختر من القائمة المنسدلة أدناه:")
    await interaction.channel.send(embed=e, view=MainMenuView())
    await interaction.response.send_message("تم إرسال المنيو بنجاح!", ephemeral=True)


# أمر لتحديد الروم المخصص لأمر الكشف (للإدارة فقط)
@bot.tree.command(name="تحديد_روم_الكشف", description="تحديد الروم المخصص لاستخدام أمر !كشف فيه فقط")
@app_commands.checks.has_permissions(manage_guild=True)
async def set_kashf_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    await set_setting(interaction.guild_id, "kashf_channel_id", str(channel.id))
    await interaction.response.send_message(f"✅ تم تحديد روم الكشف بنجاح: {channel.mention}", ephemeral=True)


# ------------------------- أمر !كشف في الروم المخصص فقط -------------------------

@bot.command(name="كشف")
async def kashf(ctx, member: discord.Member = None):
    # جلب ايدي الروم المخصص من قاعدة البيانات
    allowed_channel_id = await setting(ctx.guild.id, "kashf_channel_id")
    
    # إذا تم تحديد روم مخصص ولم يكن العضو يكتب فيه، يتم تجاهل الأمر أو إخباره
    if allowed_channel_id and ctx.channel.id != int(allowed_channel_id):
        return await ctx.message.delete()  # يحذف الرسالة عشان مايصير سبام
        # أو يمكنك استبدالها بـ: return await ctx.send(f"❌ هذا الأمر مخصص فقط في روم <#{allowed_channel_id}>", delete_after=5)

    member = member or ctx.author
    
    # بيانات تجريبية (تذاكر، تقييم، نجوم)
    tickets = 14
    avg = 4.9
    total_stars = 72

    file = await generate_profile_card(member, avg, total_stars, tickets)
    
    e = embed(f"📊 كشف حساب الأداء للإداري: {member.display_name}")
    e.set_image(url="attachment://profile_card.png")
    
    await ctx.send(embed=e, file=file)


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN environment variable.")
    bot.run(TOKEN)
