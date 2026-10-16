import os
import json
import io
import discord
from discord.ext import commands
import aiosqlite
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
MENU_DB = "menus.db"

# 🛑 ضع هنا ID الروم المخصص لكشف حساب الإدارة (اتركه None إذا تبيه يشتغل بأي روم، أو حط الـ ID بين القوسين)
ALLOWED_CHANNEL_ID = None  # مثال: ALLOWED_CHANNEL_ID = 123456789012345678

# --- 1. تهيئة قاعدة البيانات ---
async def setup_menu_db():
    async with aiosqlite.connect(MENU_DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS custom_menus (
                message_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                owner_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                buttons TEXT NOT NULL,
                is_ticket_menu INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channel_counters (
                guild_id INTEGER,
                button_label TEXT,
                counter INTEGER,
                PRIMARY KEY (guild_id, button_label)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS active_tickets (
                channel_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                claimed_by INTEGER DEFAULT NULL,
                role_id INTEGER DEFAULT NULL,
                is_ticket INTEGER DEFAULT 0,
                button_label TEXT DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS staff_stats (
                staff_id INTEGER PRIMARY KEY,
                tickets_claimed INTEGER DEFAULT 0,
                total_stars INTEGER DEFAULT 0,
                rating_count INTEGER DEFAULT 0
            )
        """)
        await db.commit()

# --- 2. دالة توليد صورة كشف الحساب الفخمة بلون الرتبة ---
async def generate_staff_card(member: discord.Member, guild: discord.Guild, claimed: int, avg_stars: float, rating_count: int) -> io.BytesIO:
    width, height = 900, 450
    card = Image.new("RGBA", (width, height), (15, 18, 26, 255))
    draw = ImageDraw.Draw(card)

    role_color = member.top_role.color.to_rgb() if member.top_role and member.top_role.color.value != 0 else (138, 43, 226)
    glow_color = (role_color[0], role_color[1], role_color[2], 50)
    border_color = (role_color[0], role_color[1], role_color[2], 220)

    draw.rounded_rectangle([15, 15, width - 15, height - 15], radius=25, outline=border_color, width=3)
    draw.rounded_rectangle([25, 25, width - 25, height - 25], radius=20, fill=(23, 28, 41, 255))

    draw.ellipse([width - 320, -120, width + 100, 320], fill=glow_color)
    draw.ellipse([-100, height - 150, 200, height + 150], fill=glow_color)

    async def get_circular_avatar(asset, size):
        if not asset:
            img = Image.new("RGBA", (size, size), (50, 50, 60, 255))
        else:
            avatar_bytes = await asset.read()
            img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            img = img.resize((size, size), Image.Resampling.LANCZOS)
        
        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size, size), fill=255)
        
        output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        output.paste(img, (0, 0), mask)
        return output

    user_avatar = await get_circular_avatar(member.display_avatar, 130)
    card.paste(user_avatar, (50, 50), user_avatar)
    draw.ellipse([46, 46, 184, 184], outline=border_color, width=4)

    if guild and guild.icon:
        server_logo = await get_circular_avatar(guild.icon, 80)
        card.paste(server_logo, (width - 130, 45), server_logo)
        draw.ellipse([width - 133, 42, width - 47, 128], outline=(255, 215, 0, 255), width=3)

    try:
        font_title = ImageFont.truetype("arial.ttf", 36)
        font_sub = ImageFont.truetype("arial.ttf", 22)
        font_stat_val = ImageFont.truetype("arial.ttf", 32)
        font_stat_lbl = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font_title = font_sub = font_stat_val = font_stat_lbl = ImageFont.load_default()

    role_name = member.top_role.name if member.top_role else "طاقم الإدارة"

    draw.text((200, 60), member.display_name, fill=(255, 255, 255, 255), font=font_title)
    draw.text((200, 110), f"ROLE: {role_name.upper()}", fill=role_color, font=font_sub)
    if guild:
        draw.text((width - 145, 135), guild.name[:18], fill=(220, 220, 220, 255), font=font_stat_lbl)

    boxes = [
        {"title": "TICKETS CLAIMED", "value": f"{claimed}", "x": 50, "color": border_color},
        {"title": "AVERAGE RATING", "value": f"{avg_stars} / 5.0", "x": 320, "color": (255, 215, 0, 255)},
        {"title": "TOTAL RATINGS", "value": f"{rating_count}", "x": 590, "color": (57, 255, 20, 255)},
    ]

    for box in boxes:
        x = box["x"]
        draw.rounded_rectangle([x, 230, x + 250, 370], radius=15, fill=(30, 36, 52, 255), outline=box["color"], width=2)
        draw.text((x + 20, 250), box["title"], fill=(160, 170, 190, 255), font=font_stat_lbl)
        draw.text((x + 20, 295), box["value"], fill=(255, 255, 255, 255), font=font_stat_val)

    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# --- 3. واجهة التقييم وحفظ النجوم ---
class RatingView(discord.ui.View):
    def __init__(self, staff_id: int):
        super().__init__(timeout=120)
        self.staff_id = staff_id

    async def send_rating(self, interaction: discord.Interaction, stars: int):
        staff_mention = f"<@{self.staff_id}>" if self.staff_id else "طاقم الإدارة"
        stars_str = "⭐" * stars
        
        if self.staff_id:
            async with aiosqlite.connect(MENU_DB) as db:
                await db.execute("""
                    INSERT INTO staff_stats (staff_id, tickets_claimed, total_stars, rating_count)
                    VALUES (?, 0, ?, 1)
                    ON CONFLICT(staff_id) DO UPDATE SET
                        total_stars = total_stars + ?,
                        rating_count = rating_count + 1
                """, (self.staff_id, stars, stars))
                await db.commit()

        embed = discord.Embed(
            title="شكراً لتقييمك! 🌟",
            description=f"تقييمك للخدمة: **{stars_str}** ({stars}/5)\nالموظف المستلم: {staff_mention}",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        import asyncio
        await asyncio.sleep(2)
        try:
            await interaction.channel.delete()
        except Exception:
            pass

    @discord.ui.button(label="1 ⭐", style=discord.ButtonStyle.secondary)
    async def star1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_rating(interaction, 1)

    @discord.ui.button(label="2 ⭐", style=discord.ButtonStyle.secondary)
    async def star2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_rating(interaction, 2)

    @discord.ui.button(label="3 ⭐", style=discord.ButtonStyle.secondary)
    async def star3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_rating(interaction, 3)

    @discord.ui.button(label="4 ⭐", style=discord.ButtonStyle.secondary)
    async def star4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_rating(interaction, 4)

    @discord.ui.button(label="5 ⭐", style=discord.ButtonStyle.success)
    async def star5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_rating(interaction, 5)

# --- 4. نافذة إضافة/إزالة عضو ---
class AddMemberModal(discord.ui.Modal, title="إضافة عضو إلى التكت"):
    member_id = discord.ui.TextInput(label="معرف العضو (User ID) أو المنشن", placeholder="مثال: 123456789", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_input = self.member_id.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            member = await interaction.guild.fetch_member(int(user_input))
            await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
            await interaction.followup.send(f"✅ تم إضافة العضو {member.mention} إلى القناة بنجاح.", ephemeral=True)
            await interaction.channel.send(f"📥 تم إضافة {member.mention} إلى القناة بواسطة {interaction.user.mention}.")
        except Exception:
            await interaction.followup.send("❌ تعذر العثور على العضو، يرجى التأكد من الـ ID.", ephemeral=True)

class RemoveMemberModal(discord.ui.Modal, title="إزالة عضو من التكت"):
    member_id = discord.ui.TextInput(label="معرف العضو (User ID) أو المنشن", placeholder="مثال: 123456789", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_input = self.member_id.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            member = await interaction.guild.fetch_member(int(user_input))
            await interaction.channel.set_permissions(member, overwrite=None)
            await interaction.followup.send(f"✅ تم إزالة العضو {member.mention} من القناة.", ephemeral=True)
            await interaction.channel.send(f"📤 تم إزالة {member.display_name} من القناة.")
        except Exception:
            await interaction.followup.send("❌ تعذر العثور على العضو، يرجى التأكد من الـ ID.", ephemeral=True)

# --- 5. أزرار التحكم بداخل القناة ---
class ChannelControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق القناة", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="close_dynamic_channel")
    async def close_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(MENU_DB) as db:
            async with db.execute("SELECT claimed_by, is_ticket FROM active_tickets WHERE channel_id = ?", (interaction.channel_id,)) as cursor:
                row = await cursor.fetchone()

        is_ticket_channel = row[1] if row else 0
        claimed_by_id = row[0] if row else None

        if is_ticket_channel == 1:
            embed = discord.Embed(
                title="🔒 إغلاق التكت وتقييم الخدمة",
                description="يرجى تقييم أداء ومساعدة الموظف قبل إغلاق القناة:",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, view=RatingView(claimed_by_id), ephemeral=True)
        else:
            await interaction.response.send_message("🔒 سيتم إغلاق وحذف هذه القناة خلال 3 ثوانٍ...", ephemeral=False)
            import asyncio
            await asyncio.sleep(3)
            try:
                await interaction.channel.delete()
            except Exception:
                pass

    @discord.ui.button(label="إضافة عضو", emoji="➕", style=discord.ButtonStyle.secondary, custom_id="add_member_to_ticket")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddMemberModal())

    @discord.ui.button(label="إزالة عضو", emoji="➖", style=discord.ButtonStyle.secondary, custom_id="remove_member_from_ticket")
    async def remove_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RemoveMemberModal())

# --- 6. أزرار المنيو المنشور ---
class MenuButton(discord.ui.Button):
    def __init__(self, item, index, message_id, is_ticket_menu):
        self.item = item
        self.is_ticket_menu = is_ticket_menu
        emoji_val = item.get("emoji")
        if emoji_val and not emoji_val.strip():
            emoji_val = None

        super().__init__(
            label=item.get("label", "زر")[:80],
            emoji=emoji_val,
            style=discord.ButtonStyle.primary,
            custom_id=f"published_menu:{message_id}:{index}"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        value = self.item.get("value", "لم يتم تحديد محتوى هذا الزر.")
        label = self.item.get("label", "قسم")
        role_id = self.item.get("role_id")

        guild = interaction.guild
        if not guild:
            return await interaction.followup.send("هذا الأمر يعمل داخل السيرفرات فقط.", ephemeral=True)

        async with aiosqlite.connect(MENU_DB) as db:
            async with db.execute(
                "SELECT counter FROM channel_counters WHERE guild_id = ? AND button_label = ?", 
                (guild.id, label)
            ) as cursor:
                row = await cursor.fetchone()
            
            if row:
                count = row[0] + 1
                await db.execute(
                    "UPDATE channel_counters SET counter = ? WHERE guild_id = ? AND button_label = ?", 
                    (count, guild.id, label)
                )
            else:
                count = 1
                await db.execute(
                    "INSERT INTO channel_counters (guild_id, button_label, counter) VALUES (?, ?, ?)", 
                    (guild.id, label, count)
                )
            await db.commit()

        channel_name = f"{label}-{count:02d}".replace(" ", "-").lower()

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        parsed_role_id = None
        if role_id:
            try:
                parsed_role_id = int(role_id)
                staff_role = guild.get_role(parsed_role_id)
                if staff_role:
                    overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            except Exception:
                pass

        try:
            new_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
            
            async with aiosqlite.connect(MENU_DB) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO active_tickets (channel_id, user_id, role_id, is_ticket, button_label) VALUES (?, ?, ?, ?, ?)",
                    (new_channel.id, interaction.user.id, parsed_role_id, 1 if self.is_ticket_menu else 0, label)
                )
                await db.commit()

            embed = discord.Embed(
                title=f"📁 {label} #{count:02d}",
                description=f"مرحباً بك {interaction.user.mention}!\n\n{value}\n\n*يمكنك التحكم بالقناة بالضغط على الأزرار أدناه.*",
                color=discord.Color.green()
            )
            
            await new_channel.send(content=interaction.user.mention, embed=embed, view=ChannelControlView())
            await interaction.followup.send(f"✅ تم فتح قناتك الخاصة بنجاح: {new_channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ حدث خطأ أثناء إنشاء القناة: {e}", ephemeral=True)

class PublishedMenu(discord.ui.View):
    def __init__(self, buttons, message_id, is_ticket_menu=0):
        super().__init__(timeout=None)
        for index, item in enumerate(buttons[:25]):
            self.add_item(MenuButton(item, index, message_id, is_ticket_menu))

# --- 7. لوحة التحكم والمعدل ---
class MenuEditor(discord.ui.View):
    def __init__(self, owner_id, message):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.message = message

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("هذه اللوحة متاحة لمنشئها فقط.", ephemeral=True)
            return False
        return True

    async def get_data(self):
        async with aiosqlite.connect(MENU_DB) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM custom_menus WHERE message_id=?", (self.message.id,))
            row = await cur.fetchone()
        return dict(row) if row else None

    async def refresh_menu(self, interaction: discord.Interaction):
        data = await self.get_data()
        if data is None:
            return

        buttons = json.loads(data["buttons"])
        is_ticket_menu = data.get("is_ticket_menu", 0)
        embed = discord.Embed(
            title=data["title"],
            description=data["description"],
            color=discord.Color.blurple()
        )

        await self.message.edit(embed=embed, view=PublishedMenu(buttons, self.message.id, is_ticket_menu))

    @discord.ui.button(label="تعديل العنوان", emoji="📝", style=discord.ButtonStyle.primary)
    async def edit_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MenuTextModal(self, "title"))

    @discord.ui.button(label="تعديل الوصف", emoji="📄", style=discord.ButtonStyle.primary)
    async def edit_description(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MenuTextModal(self, "description"))

    @discord.ui.button(label="إضافة زر", emoji="➕", style=discord.ButtonStyle.success)
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = await self.get_data()
        if not data:
            return await interaction.response.send_message("المنيو غير موجودة.", ephemeral=True)

        if len(json.loads(data["buttons"])) >= 25:
            return await interaction.response.send_message("وصلت إلى الحد الأقصى: 25 زرًا في المنيو.", ephemeral=True)

        await interaction.response.send_modal(MenuButtonModal(self, "add"))

    @discord.ui.button(label="تعديل زر", emoji="✏️", style=discord.ButtonStyle.secondary)
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = await self.get_data()
        if not data or not json.loads(data["buttons"]):
            return await interaction.response.send_message("ما فيه أزرار لتعديلها.", ephemeral=True)

        await interaction.response.send_modal(MenuButtonModal(self, "edit"))

    @discord.ui.button(label="حذف زر", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = await self.get_data()
        if not data or not json.loads(data["buttons"]):
            return await interaction.response.send_message("ما فيه أزرار لحذفها.", ephemeral=True)

        await interaction.response.send_modal(MenuButtonModal(self, "delete"))

    @discord.ui.button(label="تحديث المنيو", emoji="🔄", style=discord.ButtonStyle.success)
    async def update_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self.refresh_menu(interaction)
        await interaction.followup.send("✅ تم تحديث المنيو بنجاح.", ephemeral=True)

class MenuTextModal(discord.ui.Modal):
    def __init__(self, editor, field):
        self.editor = editor
        self.field = field
        label = "عنوان المنيو" if field == "title" else "وصف المنيو"
        super().__init__(title=label)

        self.text = discord.ui.TextInput(
            label=label,
            max_length=250 if field == "title" else 2000,
            style=discord.TextStyle.paragraph if field == "description" else discord.TextStyle.short
        )
        self.add_item(self.text)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with aiosqlite.connect(MENU_DB) as db:
            await db.execute(
                f"UPDATE custom_menus SET {self.field}=? WHERE message_id=?",
                (self.text.value, self.editor.message.id)
            )
            await db.commit()

        await self.editor.refresh_menu(interaction)
        await interaction.followup.send("✅ تم تحديث العنوان/الوصف بنجاح!", ephemeral=True)

class MenuButtonModal(discord.ui.Modal):
    def __init__(self, editor, mode):
        self.editor = editor
        self.mode = mode
        titles = {"add": "إضافة زر", "edit": "تعديل زر", "delete": "حذف زر"}
        super().__init__(title=titles[mode])

        self.index = discord.ui.TextInput(
            label="رقم الزر (اتركه فارغاً عند الإضافة)",
            placeholder="مثال: 1 (مطلوب للتعديل والحذف فقط)",
            required=False,
            max_length=2
        )
        self.add_item(self.index)

        if mode != "delete":
            self.label_input = discord.ui.TextInput(label="اسم الزر", max_length=80)
            self.emoji_input = discord.ui.TextInput(label="الإيموجي (اختياري)", required=False, max_length=20)
            self.role_input = discord.ui.TextInput(label="معرف رتبة الطاقم المسؤول (ID)", required=False, max_length=25)
            self.value_input = discord.ui.TextInput(
                label="محتوى الرسالة داخل القناة الخاصة",
                style=discord.TextStyle.paragraph,
                max_length=1000
            )
            self.add_item(self.label_input)
            self.add_item(self.emoji_input)
            self.add_item(self.role_input)
            self.add_item(self.value_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with aiosqlite.connect(MENU_DB) as db:
            cur = await db.execute("SELECT buttons FROM custom_menus WHERE message_id=?", (self.editor.message.id,))
            row = await cur.fetchone()

            if not row:
                return await interaction.followup.send("المنيو غير موجودة.", ephemeral=True)

            buttons = json.loads(row[0])

            if self.mode == "add":
                if len(buttons) >= 25:
                    return await interaction.followup.send("لا يمكن إضافة أكثر من 25 زرًا.", ephemeral=True)
                
                emoji_val = self.emoji_input.value.strip() if self.emoji_input.value else None
                role_val = self.role_input.value.strip() if self.role_input.value else None
                buttons.append({
                    "label": self.label_input.value,
                    "emoji": emoji_val,
                    "role_id": role_val,
                    "value": self.value_input.value
                })

            else:
                try:
                    index = int(self.index.value) - 1
                    if index < 0 or index >= len(buttons):
                        raise ValueError
                except (ValueError, TypeError):
                    return await interaction.followup.send("يرجى إدخال رقم زر صحيح للتعديل أو الحذف.", ephemeral=True)

                if self.mode == "delete":
                    buttons.pop(index)
                else:
                    emoji_val = self.emoji_input.value.strip() if self.emoji_input.value else None
                    role_val = self.role_input.value.strip() if self.role_input.value else None
                    buttons[index] = {
                        "label": self.label_input.value,
                        "emoji": emoji_val,
                        "role_id": role_val,
                        "value": self.value_input.value
                    }

            await db.execute(
                "UPDATE custom_menus SET buttons=? WHERE message_id=?",
                (json.dumps(buttons, ensure_ascii=False), self.editor.message.id)
            )
            await db.commit()

        await self.editor.refresh_menu(interaction)
        await interaction.followup.send("✅ تم تحديث الأزرار بنجاح!", ephemeral=True)

# --- 8. معالجة الأحداث وأوامر الكتابة المباشرة !كشف في الروم المحدد ---
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command(name="كشف")
async def text_staff_statement(ctx, member: discord.Member = None):
    # تحقق من الروم المخصص إذا تم تعيينه
    if ALLOWED_CHANNEL_ID and ctx.channel.id != ALLOWED_CHANNEL_ID:
        return await ctx.message.delete()  # يحذف الرسالة عشان ما يصير إزعاج بالرومات الثانية

    target = member or ctx.author

    async with aiosqlite.connect(MENU_DB) as db:
        async with db.execute("SELECT tickets_claimed, total_stars, rating_count FROM staff_stats WHERE staff_id = ?", (target.id,)) as cursor:
            row = await cursor.fetchone()

    claimed = row[0] if row else 0
    total_stars = row[1] if row else 0
    rating_count = row[2] if row else 0
    avg_stars = round(total_stars / rating_count, 1) if rating_count > 0 else 0.0

    image_buffer = await generate_staff_card(target, ctx.guild, claimed, avg_stars, rating_count)
    file = discord.File(fp=image_buffer, filename="staff_card.png")

    await ctx.send(content=f"📊 **كشف حساب الأداء للإداري:** {target.mention}", file=file)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    async with aiosqlite.connect(MENU_DB) as db:
        async with db.execute("SELECT user_id, claimed_by, role_id, is_ticket, button_label FROM active_tickets WHERE channel_id = ?", (message.channel.id,)) as cursor:
            row = await cursor.fetchone()

        if row:
            user_id, claimed_by, role_id, is_ticket, button_label = row
            if message.author.id != user_id and claimed_by is None:
                await db.execute("UPDATE active_tickets SET claimed_by = ? WHERE channel_id = ?", (message.author.id, message.channel.id))
                
                await db.execute("""
                    INSERT INTO staff_stats (staff_id, tickets_claimed, total_stars, rating_count)
                    VALUES (?, 1, 0, 0)
                    ON CONFLICT(staff_id) DO UPDATE SET
                        tickets_claimed = tickets_claimed + 1
                """, (message.author.id,))
                await db.commit()

                if is_ticket == 1:
                    if role_id:
                        staff_role = message.guild.get_role(role_id)
                        if staff_role:
                            await message.channel.set_permissions(staff_role, view_channel=False)

                    await message.channel.set_permissions(message.author, view_channel=True, send_messages=True, read_message_history=True)

                    embed = discord.Embed(
                        description=f"🔒 **تم استلام التكت وحصر القناة بواسطة:** {message.author.mention}\n*تم إخفاء التكت عن باقي الإداريين منعاً للتدخل.*",
                        color=discord.Color.blue()
                    )
                    await message.channel.send(embed=embed)
                else:
                    embed = discord.Embed(
                        description=f"📋 **تم استلام طلب ({button_label}) بواسطة:** {message.author.mention}",
                        color=discord.Color.gold()
                    )
                    await message.channel.send(embed=embed)

    await bot.process_commands(message)

@bot.event
async def on_ready():
    await setup_menu_db()
    bot.add_view(ChannelControlView())
    
    async with aiosqlite.connect(MENU_DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT message_id, buttons, is_ticket_menu FROM custom_menus")
        rows = await cur.fetchall()
        for row in rows:
            buttons = json.loads(row["buttons"])
            bot.add_view(PublishedMenu(buttons, row["message_id"], row["is_ticket_menu"]))

    await bot.tree.sync()
    print(f"✅ تم تشغيل البوت بنجاح باسم: {bot.user}")

# --- 9. أوامر إنشاء وتعديل المنيو (سلاش خاصة بإدارة المنيوهات فقط) ---

@bot.tree.command(name="إنشاء_منيو", description="إنشاء منيو تفاعلي جديد في القناة الحالية")
@app_commands.describe(نوع_المنيو="اختر هل المنيو مخصص للتكتات أم منيو خدمات عادي")
@app_commands.choices(نوع_المنيو=[
    app_commands.Choice(name="منيو تكتات إدارية (يحتوي تقييم واستلام حصري)", value=1),
    app_commands.Choice(name="منيو خدمات وعصابات عادية (بدون تقييم)", value=0)
])
@app_commands.checks.has_permissions(manage_guild=True)
async def create_custom_menu(interaction: discord.Interaction, نوع_المنيو: app_commands.Choice[int]):
    if interaction.guild is None or interaction.channel is None:
        return await interaction.response.send_message("استخدم الأمر داخل السيرفر.", ephemeral=True)

    is_ticket = نوع_المنيو.value

    embed = discord.Embed(
        title="منيو جديدة",
        description="اضغط أزرار الإدارة لتخصيص العنوان والوصف والأزرار.",
        color=discord.Color.blurple()
    )

    message = await interaction.channel.send(embed=embed)

    async with aiosqlite.connect(MENU_DB) as db:
        await db.execute(
            """INSERT INTO custom_menus
               (message_id, guild_id, channel_id, owner_id, title, description, buttons, is_ticket_menu)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                message.id,
                interaction.guild.id,
                interaction.channel.id,
                interaction.user.id,
                "منيو جديدة",
                "اضغط أحد الأزرار أدناه.",
                "[]",
                is_ticket
            )
        )
        await db.commit()

    await interaction.response.send_message(
        "تم إنشاء المنيو في هذه القناة. لوحة التعديل بالأسفل (مخفية للعامة).",
        view=MenuEditor(interaction.user.id, message),
        ephemeral=True
    )

@bot.tree.command(name="تعديل_منيو", description="إظهار لوحة تعديل المنيو الموجود في القناة")
@app_commands.describe(رابط_الرسالة_أو_المعرف="انسخ رابط رسالة المنيو أو معرفها")
@app_commands.checks.has_permissions(manage_guild=True)
async def edit_custom_menu(interaction: discord.Interaction, رابط_الرسالة_أو_المعرف: str):
    if interaction.guild is None or interaction.channel is None:
        return await interaction.response.send_message("استخدم الأمر داخل السيرفر.", ephemeral=True)

    msg_id_str = رابط_الرسالة_أو_المعرف.split("/")[-1]
    try:
        msg_id = int(msg_id_str)
    except ValueError:
        return await interaction.response.send_message("❌ رابط أو معرف الرسالة غير صحيح.", ephemeral=True)

    async with aiosqlite.connect(MENU_DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM custom_menus WHERE message_id=?", (msg_id,))
        row = await cur.fetchone()

    if not row:
        return await interaction.response.send_message("❌ لم يتم العثور على هذا المنيو في قاعدة البيانات.", ephemeral=True)

    try:
        target_message = await interaction.channel.fetch_message(msg_id)
    except Exception:
        return await interaction.response.send_message("❌ تعذر العثور على رسالة المنيو في هذه القناة.", ephemeral=True)

    await interaction.response.send_message(
        "تم جلب لوحة التحكم للمنيو المطلوب بنجاح (مخفية للعامة):",
        view=MenuEditor(interaction.user.id, target_message),
        ephemeral=True
    )

if __name__ == "__main__":
    if not TOKEN:
        print("❌ خطأ: لم يتم العثور على DISCORD_TOKEN في ملف .env")
    else:
        bot.run(TOKEN)
