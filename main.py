import os
import json
import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
MENU_DB = "menus.db"

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
                buttons TEXT NOT NULL
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
        await db.commit()

class CloseChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق القناة", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="close_dynamic_channel")
    async def close_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 سيتم إغلاق وحذف هذه القناة خلال 3 ثوانٍ...", ephemeral=False)
        import asyncio
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete()
        except Exception:
            pass

class MenuButton(discord.ui.Button):
    def __init__(self, item, index, message_id):
        self.item = item
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
        action = self.item.get("action", "channel")
        value = self.item.get("value", "لم يتم تحديد محتوى هذا الزر.")
        label = self.item.get("label", "قسم")

        if action == "channel":
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
            
            try:
                new_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
                
                embed = discord.Embed(
                    title=f"📁 {label} #{count:02d}",
                    description=f"مرحباً بك {interaction.user.mention}!\n\n{value}\n\n*يمكنك إغلاق هذه القناة بالضغط على الزر أدناه.*",
                    color=discord.Color.green()
                )
                
                await new_channel.send(content=interaction.user.mention, embed=embed, view=CloseChannelView())
                await interaction.followup.send(f"✅ تم فتح قناتك الخاصة بنجاح: {new_channel.mention}", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"❌ حدث خطأ أثناء إنشاء القناة: {e}", ephemeral=True)
        else:
            await interaction.followup.send(value, ephemeral=True)

class PublishedMenu(discord.ui.View):
    def __init__(self, buttons, message_id):
        super().__init__(timeout=None)
        for index, item in enumerate(buttons[:25]):
            self.add_item(MenuButton(item, index, message_id))

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
        embed = discord.Embed(
            title=data["title"],
            description=data["description"],
            color=discord.Color.blurple()
        )

        await self.message.edit(embed=embed, view=PublishedMenu(buttons, self.message.id))

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
            self.value_input = discord.ui.TextInput(
                label="محتوى الرسالة داخل القناة الخاصة",
                style=discord.TextStyle.paragraph,
                max_length=1000
            )
            self.add_item(self.label_input)
            self.add_item(self.emoji_input)
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
                buttons.append({
                    "label": self.label_input.value,
                    "emoji": emoji_val,
                    "action": "channel",
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
                    buttons[index] = {
                        "label": self.label_input.value,
                        "emoji": emoji_val,
                        "action": "channel",
                        "value": self.value_input.value
                    }

            await db.execute(
                "UPDATE custom_menus SET buttons=? WHERE message_id=?",
                (json.dumps(buttons, ensure_ascii=False), self.editor.message.id)
            )
            await db.commit()

        await self.editor.refresh_menu(interaction)
        await interaction.followup.send("✅ تم تحديث الأزرار بنجاح!", ephemeral=True)

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await setup_menu_db()
    bot.add_view(CloseChannelView())
    
    async with aiosqlite.connect(MENU_DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT message_id, buttons, owner_id FROM custom_menus")
        rows = await cur.fetchall()
        for row in rows:
            buttons = json.loads(row["buttons"])
            bot.add_view(PublishedMenu(buttons, row["message_id"]))

    await bot.tree.sync()
    print(f"✅ تم تشغيل البوت بنجاح باسم: {bot.user}")

@bot.tree.command(name="إنشاء_منيو", description="إنشاء منيو تفاعلي جديد في القناة الحالية")
@app_commands.checks.has_permissions(manage_guild=True)
async def create_custom_menu(interaction: discord.Interaction):
    if interaction.guild is None or interaction.channel is None:
        return await interaction.response.send_message("استخدم الأمر داخل السيرفر.", ephemeral=True)

    embed = discord.Embed(
        title="منيو جديدة",
        description="اضغط أزرار الإدارة لتخصيص العنوان والوصف والأزرار.",
        color=discord.Color.blurple()
    )

    message = await interaction.channel.send(embed=embed)

    async with aiosqlite.connect(MENU_DB) as db:
        await db.execute(
            """INSERT INTO custom_menus
               (message_id, guild_id, channel_id, owner_id, title, description, buttons)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                message.id,
                interaction.guild.id,
                interaction.channel.id,
                interaction.user.id,
                "منيو جديدة",
                "اضغط أحد الأزرار أدناه.",
                "[]"
            )
        )
        await db.commit()

    # إعادة ربط لوحة التحكم بالرسالة المرسلة
    await interaction.response.send_message(
        "تم إنشاء المنيو في هذه القناة. لوحة التعديل بالأسفل (مخفية للعامة).",
        view=MenuEditor(interaction.user.id, message),
        ephemeral=True
    )

if __name__ == "__main__":
    if not TOKEN:
        print("❌ خطأ: لم يتم العثور على DISCORD_TOKEN في ملف .env")
    else:
        bot.run(TOKEN)
