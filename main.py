# ============================================================
# Discord Server Bot - main.py
‏# Python 3.10+
‏# Install:
‏#   pip install -U discord.py aiosqlite
#
‏# Environment variable:
‏#   DISCORD_TOKEN=YOUR_BOT_TOKEN
#
‏# Enable Server Members Intent in Discord Developer Portal.
# ============================================================

‏import os
‏import io
‏import json
‏import time
‏import random
‏import asyncio
‏import logging
‏from datetime import datetime, timedelta, timezone

‏import discord
‏import aiosqlite
‏from discord import app_commands
‏from discord.ext import commands

‏# ------------------------- CONFIG ----------------------------

‏TOKEN = os.getenv("DISCORD_TOKEN")
‏DB_FILE = "server_bot.db"

‏logging.basicConfig(level=logging.INFO)
‏log = logging.getLogger("server-bot")

‏intents = discord.Intents.default()
‏intents.members = True
‏intents.message_content = True
‏intents.guilds = True
‏intents.messages = True


‏def now():
‏    return int(time.time())


‏def money(value):
‏    return f"{value:,}"


‏def embed(title, description="", color=discord.Color.blurple()):
‏    return discord.Embed(
‏        title=title,
‏        description=description,
‏        color=color,
‏        timestamp=datetime.now(timezone.utc),
    )


‏def is_staff(interaction: discord.Interaction):
‏    p = interaction.user.guild_permissions
‏    return p.administrator or p.manage_guild or p.moderate_members


‏async def setting(guild_id, key, default=None):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
‏            "SELECT value FROM settings WHERE guild_id=? AND key=?",
‏            (guild_id, key),
        )
‏        row = await cur.fetchone()
‏        return row[0] if row else default


‏async def set_setting(guild_id, key, value):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        await db.execute(
            """
‏            INSERT INTO settings(guild_id,key,value)
‏            VALUES(?,?,?)
‏            ON CONFLICT(guild_id,key)
‏            DO UPDATE SET value=excluded.value
            """,
‏            (guild_id, key, str(value)),
        )
‏        await db.commit()


‏async def log_action(guild, title, description):
‏    channel_id = await setting(guild.id, "log_channel")
‏    if not channel_id:
‏        return
‏    channel = guild.get_channel(int(channel_id))
‏    if channel:
‏        try:
‏            await channel.send(embed=embed(title, description))
‏        except discord.HTTPException:
‏            pass


‏async def get_balance(guild_id, user_id):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
‏            "SELECT wallet,bank FROM economy WHERE guild_id=? AND user_id=?",
‏            (guild_id, user_id),
        )
‏        row = await cur.fetchone()
‏        return row if row else (0, 0)


‏async def change_balance(guild_id, user_id, wallet_delta=0, bank_delta=0):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        await db.execute(
            """
‏            INSERT OR IGNORE INTO economy(guild_id,user_id,wallet,bank)
‏            VALUES(?,?,0,0)
            """,
‏            (guild_id, user_id),
        )
‏        await db.execute(
            """
‏            UPDATE economy
‏            SET wallet=wallet+?, bank=bank+?
‏            WHERE guild_id=? AND user_id=?
            """,
‏            (wallet_delta, bank_delta, guild_id, user_id),
        )
‏        await db.commit()


‏async def transaction(guild_id, user_id, kind, amount, note=""):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        await db.execute(
            """
‏            INSERT INTO transactions
‏            (guild_id,user_id,kind,amount,note,created_at)
‏            VALUES(?,?,?,?,?,?)
            """,
‏            (guild_id, user_id, kind, amount, note, now()),
        )
‏        await db.commit()


‏# ------------------------- DATABASE -------------------------

‏async def init_db():
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        await db.executescript("""
‏        CREATE TABLE IF NOT EXISTS settings(
‏            guild_id INTEGER NOT NULL,
‏            key TEXT NOT NULL,
‏            value TEXT,
‏            PRIMARY KEY(guild_id,key)
        );

‏        CREATE TABLE IF NOT EXISTS warnings(
‏            id INTEGER PRIMARY KEY AUTOINCREMENT,
‏            guild_id INTEGER NOT NULL,
‏            user_id INTEGER NOT NULL,
‏            moderator_id INTEGER NOT NULL,
‏            reason TEXT NOT NULL,
‏            created_at INTEGER NOT NULL
        );

‏        CREATE TABLE IF NOT EXISTS cases(
‏            id INTEGER PRIMARY KEY AUTOINCREMENT,
‏            guild_id INTEGER NOT NULL,
‏            user_id INTEGER NOT NULL,
‏            moderator_id INTEGER NOT NULL,
‏            action TEXT NOT NULL,
‏            reason TEXT NOT NULL,
‏            created_at INTEGER NOT NULL
        );

‏        CREATE TABLE IF NOT EXISTS tickets(
‏            id INTEGER PRIMARY KEY AUTOINCREMENT,
‏            guild_id INTEGER NOT NULL,
‏            channel_id INTEGER NOT NULL UNIQUE,
‏            user_id INTEGER NOT NULL,
‏            claimed_by INTEGER,
‏            status TEXT NOT NULL DEFAULT 'open',
‏            created_at INTEGER NOT NULL
        );

‏        CREATE TABLE IF NOT EXISTS economy(
‏            guild_id INTEGER NOT NULL,
‏            user_id INTEGER NOT NULL,
‏            wallet INTEGER NOT NULL DEFAULT 0,
‏            bank INTEGER NOT NULL DEFAULT 0,
‏            last_daily INTEGER NOT NULL DEFAULT 0,
‏            last_work INTEGER NOT NULL DEFAULT 0,
‏            PRIMARY KEY(guild_id,user_id)
        );

‏        CREATE TABLE IF NOT EXISTS transactions(
‏            id INTEGER PRIMARY KEY AUTOINCREMENT,
‏            guild_id INTEGER NOT NULL,
‏            user_id INTEGER NOT NULL,
‏            kind TEXT NOT NULL,
‏            amount INTEGER NOT NULL,
‏            note TEXT,
‏            created_at INTEGER NOT NULL
        );

‏        CREATE TABLE IF NOT EXISTS xp(
‏            guild_id INTEGER NOT NULL,
‏            user_id INTEGER NOT NULL,
‏            points INTEGER NOT NULL DEFAULT 0,
‏            messages INTEGER NOT NULL DEFAULT 0,
‏            PRIMARY KEY(guild_id,user_id)
        );

‏        CREATE TABLE IF NOT EXISTS suggestions(
‏            id INTEGER PRIMARY KEY AUTOINCREMENT,
‏            guild_id INTEGER NOT NULL,
‏            user_id INTEGER NOT NULL,
‏            text TEXT NOT NULL,
‏            status TEXT NOT NULL DEFAULT 'pending',
‏            created_at INTEGER NOT NULL
        );

‏        CREATE TABLE IF NOT EXISTS reports(
‏            id INTEGER PRIMARY KEY AUTOINCREMENT,
‏            guild_id INTEGER NOT NULL,
‏            reporter_id INTEGER NOT NULL,
‏            target_id INTEGER NOT NULL,
‏            reason TEXT NOT NULL,
‏            status TEXT NOT NULL DEFAULT 'open',
‏            created_at INTEGER NOT NULL
        );

‏        CREATE TABLE IF NOT EXISTS staff_evaluations(
‏            id INTEGER PRIMARY KEY AUTOINCREMENT,
‏            guild_id INTEGER NOT NULL,
‏            staff_id INTEGER NOT NULL,
‏            evaluator_id INTEGER NOT NULL,
‏            score INTEGER NOT NULL,
‏            note TEXT NOT NULL,
‏            created_at INTEGER NOT NULL
        );

‏        CREATE TABLE IF NOT EXISTS staff_ledger(
‏            id INTEGER PRIMARY KEY AUTOINCREMENT,
‏            guild_id INTEGER NOT NULL,
‏            staff_id INTEGER NOT NULL,
‏            actor_id INTEGER NOT NULL,
‏            amount INTEGER NOT NULL,
‏            note TEXT NOT NULL,
‏            created_at INTEGER NOT NULL
        );

‏        CREATE TABLE IF NOT EXISTS staff_notes(
‏            id INTEGER PRIMARY KEY AUTOINCREMENT,
‏            guild_id INTEGER NOT NULL,
‏            staff_id INTEGER NOT NULL,
‏            actor_id INTEGER NOT NULL,
‏            note TEXT NOT NULL,
‏            created_at INTEGER NOT NULL
        );

‏        CREATE TABLE IF NOT EXISTS afk(
‏            guild_id INTEGER NOT NULL,
‏            user_id INTEGER NOT NULL,
‏            reason TEXT NOT NULL,
‏            created_at INTEGER NOT NULL,
‏            PRIMARY KEY(guild_id,user_id)
        );
        """)
‏        await db.commit()


‏# ------------------------- BOT ------------------------------

‏class ServerBot(commands.Bot):
‏    async def setup_hook(self):
‏        await init_db()
‏        self.add_view(TicketPanelView())
‏        self.add_view(TicketControlView())
‏        try:
‏            synced = await self.tree.sync()
‏            log.info("Synced %s application commands", len(synced))
‏        except Exception:
‏            log.exception("Command sync failed")


‏bot = ServerBot(command_prefix="!", intents=intents)


‏# ------------------------- TICKETS --------------------------

‏class TicketPanelView(discord.ui.View):
‏    def __init__(self):
‏        super().__init__(timeout=None)

‏    @discord.ui.button(
‏        label="فتح تذكرة",
‏        emoji="🎫",
‏        style=discord.ButtonStyle.primary,
‏        custom_id="serverbot:ticket_open",
    )
‏    async def open_ticket(self, interaction, button):
‏        guild = interaction.guild
‏        if guild is None:
‏            return await interaction.response.send_message(
                "هذا الزر يعمل داخل السيرفر فقط.", ephemeral=True
            )

‏        category_id = await setting(guild.id, "ticket_category")
‏        category = guild.get_channel(int(category_id)) if category_id else None

‏        async with aiosqlite.connect(DB_FILE) as db:
‏            cur = await db.execute(
                """
‏                SELECT channel_id FROM tickets
‏                WHERE guild_id=? AND user_id=? AND status='open'
                """,
‏                (guild.id, interaction.user.id),
            )
‏            row = await cur.fetchone()

‏        if row and guild.get_channel(row[0]):
‏            return await interaction.response.send_message(
‏                f"لديك تذكرة مفتوحة: <#{row[0]}>",
‏                ephemeral=True,
            )

‏        overwrites = {
‏            guild.default_role: discord.PermissionOverwrite(
‏                view_channel=False
            ),
‏            interaction.user: discord.PermissionOverwrite(
‏                view_channel=True,
‏                send_messages=True,
‏                read_message_history=True,
‏                attach_files=True,
            ),
        }

‏        staff_role_id = await setting(guild.id, "staff_role")
‏        if staff_role_id:
‏            role = guild.get_role(int(staff_role_id))
‏            if role:
‏                overwrites[role] = discord.PermissionOverwrite(
‏                    view_channel=True,
‏                    send_messages=True,
‏                    read_message_history=True,
                )

‏        try:
‏            channel = await guild.create_text_channel(
‏                name=f"ticket-{interaction.user.name}"[:90],
‏                category=category if isinstance(category, discord.CategoryChannel) else None,
‏                overwrites=overwrites,
‏                reason=f"Ticket opened by {interaction.user}",
            )
‏            async with aiosqlite.connect(DB_FILE) as db:
‏                await db.execute(
                    """
‏                    INSERT INTO tickets
‏                    (guild_id,channel_id,user_id,created_at)
‏                    VALUES(?,?,?,?)
                    """,
‏                    (guild.id, channel.id, interaction.user.id, now()),
                )
‏                await db.commit()

‏            await channel.send(
‏                content=f"{interaction.user.mention}",
‏                embed=embed(
                    "🎫 تذكرتك مفتوحة",
                    "اكتب تفاصيل طلبك هنا. استخدم الأزرار أدناه لإدارة التذكرة.",
                ),
‏                view=TicketControlView(),
            )
‏            await interaction.response.send_message(
‏                f"تم فتح تذكرتك: {channel.mention}",
‏                ephemeral=True,
            )
‏            await log_action(
‏                guild, "Ticket opened",
‏                f"{interaction.user.mention} opened {channel.mention}",
            )
‏        except discord.Forbidden:
‏            await interaction.response.send_message(
                "ما عندي صلاحية إنشاء القناة أو إدارة صلاحياتها.",
‏                ephemeral=True,
            )


‏class TicketControlView(discord.ui.View):
‏    def __init__(self):
‏        super().__init__(timeout=None)

‏    async def ticket_record(self, channel_id):
‏        async with aiosqlite.connect(DB_FILE) as db:
‏            cur = await db.execute(
‏                "SELECT guild_id,user_id,status FROM tickets WHERE channel_id=?",
‏                (channel_id,),
            )
‏            return await cur.fetchone()

‏    @discord.ui.button(
‏        label="استلام",
‏        emoji="🙋",
‏        style=discord.ButtonStyle.success,
‏        custom_id="serverbot:ticket_claim",
    )
‏    async def claim_ticket(self, interaction, button):
‏        if not is_staff(interaction):
‏            return await interaction.response.send_message(
                "هذا الإجراء للطاقم فقط.", ephemeral=True
            )

‏        async with aiosqlite.connect(DB_FILE) as db:
‏            await db.execute(
‏                "UPDATE tickets SET claimed_by=? WHERE channel_id=? AND status='open'",
‏                (interaction.user.id, interaction.channel_id),
            )
‏            await db.commit()

‏        await interaction.response.send_message(
‏            f"استلم التذكرة {interaction.user.mention}."
        )

‏    @discord.ui.button(
‏        label="إغلاق",
‏        emoji="🔒",
‏        style=discord.ButtonStyle.danger,
‏        custom_id="serverbot:ticket_close",
    )
‏    async def close_ticket(self, interaction, button):
‏        row = await self.ticket_record(interaction.channel_id)
‏        if not row:
‏            return await interaction.response.send_message(
                "هذه القناة ليست تذكرة مسجلة.", ephemeral=True
            )

‏        _, owner_id, status = row
‏        if status != "open":
‏            return await interaction.response.send_message(
                "التذكرة مغلقة بالفعل.", ephemeral=True
            )

‏        if interaction.user.id != owner_id and not is_staff(interaction):
‏            return await interaction.response.send_message(
                "يمكن لصاحب التذكرة أو الطاقم إغلاقها.",
‏                ephemeral=True,
            )

‏        await interaction.response.send_message(
            "سيتم إغلاق التذكرة خلال لحظات."
        )
‏        await asyncio.sleep(2)

‏        try:
‏            messages = []
‏            async for msg in interaction.channel.history(
‏                limit=500, oldest_first=True
            ):
‏                content = msg.content or ""
‏                if msg.attachments:
‏                    content += " " + " ".join(a.url for a in msg.attachments)
‏                messages.append(
‏                    f"[{msg.created_at.isoformat()}] "
‏                    f"{msg.author}: {content}"
                )

‏            transcript = "\n".join(messages) or "No messages"
‏            data = io.BytesIO(transcript.encode("utf-8"))
‏            file = discord.File(data, filename="transcript.txt")

‏            log_id = await setting(interaction.guild_id, "log_channel")
‏            log_channel = (
‏                interaction.guild.get_channel(int(log_id)) if log_id else None
            )
‏            if log_channel:
‏                await log_channel.send(
‏                    embed=embed(
‏                        "Ticket transcript",
‏                        f"Channel: {interaction.channel.name}\n"
‏                        f"Closed by: {interaction.user.mention}",
                    ),
‏                    file=file,
                )

‏            async with aiosqlite.connect(DB_FILE) as db:
‏                await db.execute(
‏                    "UPDATE tickets SET status='closed' WHERE channel_id=?",
‏                    (interaction.channel_id,),
                )
‏                await db.commit()

‏            await interaction.channel.delete(
‏                reason=f"Ticket closed by {interaction.user}"
            )
‏        except discord.Forbidden:
‏            log.warning("Missing permission to close ticket")


‏# ------------------------- EVENTS ---------------------------

‏@bot.event
‏async def on_ready():
‏    log.info("Logged in as %s (%s)", bot.user, bot.user.id)


‏@bot.event
‏async def on_message(message):
‏    if message.author.bot or not message.guild:
‏        return

‏    # Remove AFK status when the user speaks.
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
‏            "SELECT reason FROM afk WHERE guild_id=? AND user_id=?",
‏            (message.guild.id, message.author.id),
        )
‏        row = await cur.fetchone()
‏        if row:
‏            await db.execute(
‏                "DELETE FROM afk WHERE guild_id=? AND user_id=?",
‏                (message.guild.id, message.author.id),
            )
‏            await db.commit()
‏            try:
‏                await message.channel.send(
‏                    f"مرحبًا بعودتك {message.author.mention}، أزلت حالة AFK.",
‏                    delete_after=8,
                )
‏            except discord.HTTPException:
‏                pass

‏    # XP is independent from staff evaluations and staff ledger.
‏    if not message.content.startswith("!"):
‏        async with aiosqlite.connect(DB_FILE) as db:
‏            await db.execute(
                """
‏                INSERT OR IGNORE INTO xp(guild_id,user_id,points,messages)
‏                VALUES(?,?,0,0)
                """,
‏                (message.guild.id, message.author.id),
            )
‏            await db.execute(
                """
‏                UPDATE xp SET points=points+?, messages=messages+1
‏                WHERE guild_id=? AND user_id=?
                """,
‏                (random.randint(5, 12), message.guild.id, message.author.id),
            )
‏            await db.commit()

‏    for user in message.mentions:
‏        async with aiosqlite.connect(DB_FILE) as db:
‏            cur = await db.execute(
‏                "SELECT reason FROM afk WHERE guild_id=? AND user_id=?",
‏                (message.guild.id, user.id),
            )
‏            row = await cur.fetchone()
‏        if row:
‏            await message.channel.send(
‏                f"{user.display_name} في وضع AFK: {row[0]}",
‏                delete_after=10,
            )

‏    await bot.process_commands(message)


‏@bot.event
‏async def on_member_join(member):
‏    welcome_id = await setting(member.guild.id, "welcome_channel")
‏    if welcome_id:
‏        channel = member.guild.get_channel(int(welcome_id))
‏        if channel:
‏            message = await setting(
‏                member.guild.id,
‏                "welcome_text",
                "أهلًا {user} في {server}!",
            )
‏            try:
‏                await channel.send(
‏                    message.format(
‏                        user=member.mention,
‏                        server=member.guild.name,
‏                        member=member.name,
                    )
                )
‏            except discord.HTTPException:
‏                pass

‏    role_id = await setting(member.guild.id, "autorole")
‏    if role_id:
‏        role = member.guild.get_role(int(role_id))
‏        if role:
‏            try:
‏                await member.add_roles(role, reason="Configured autorole")
‏            except discord.HTTPException:
‏                pass


‏@bot.event
‏async def on_member_remove(member):
‏    leave_id = await setting(member.guild.id, "leave_channel")
‏    if leave_id:
‏        channel = member.guild.get_channel(int(leave_id))
‏        if channel:
‏            text = await setting(
‏                member.guild.id,
‏                "leave_text",
‏                "{member} غادر السيرفر.",
            )
‏            try:
‏                await channel.send(
‏                    text.format(member=member.name, server=member.guild.name)
                )
‏            except discord.HTTPException:
‏                pass


‏# ------------------------- SETUP ----------------------------

‏@bot.tree.command(name="setup", description="إعداد قناة السجلات والترحيب والتذاكر")
‏@app_commands.checks.has_permissions(administrator=True)
‏@app_commands.describe(
‏    log_channel="قناة السجلات",
‏    welcome_channel="قناة الترحيب",
‏    leave_channel="قناة المغادرة",
‏    staff_role="رتبة الطاقم",
‏    ticket_category="تصنيف قنوات التذاكر",
)
‏async def setup(
‏    interaction: discord.Interaction,
‏    log_channel: discord.TextChannel = None,
‏    welcome_channel: discord.TextChannel = None,
‏    leave_channel: discord.TextChannel = None,
‏    staff_role: discord.Role = None,
‏    ticket_category: discord.CategoryChannel = None,
):
‏    values = {
‏        "log_channel": log_channel.id if log_channel else None,
‏        "welcome_channel": welcome_channel.id if welcome_channel else None,
‏        "leave_channel": leave_channel.id if leave_channel else None,
‏        "staff_role": staff_role.id if staff_role else None,
‏        "ticket_category": ticket_category.id if ticket_category else None,
    }

‏    for key, value in values.items():
‏        if value is not None:
‏            await set_setting(interaction.guild_id, key, value)

‏    await interaction.response.send_message(
        "تم حفظ الإعدادات التي اخترتها.",
‏        ephemeral=True,
    )


‏@bot.tree.command(name="settings", description="عرض إعدادات البوت في السيرفر")
‏@app_commands.checks.has_permissions(manage_guild=True)
‏async def settings_cmd(interaction: discord.Interaction):
‏    keys = [
‏        "log_channel", "welcome_channel", "leave_channel",
‏        "staff_role", "ticket_category", "autorole",
    ]
‏    lines = []
‏    for key in keys:
‏        value = await setting(interaction.guild_id, key, "غير محدد")
‏        lines.append(f"**{key}**: {value}")

‏    await interaction.response.send_message(
‏        embed=embed("إعدادات السيرفر", "\n".join(lines)),
‏        ephemeral=True,
    )


‏@bot.tree.command(name="setlog", description="تحديد قناة السجلات")
‏@app_commands.checks.has_permissions(manage_guild=True)
‏async def setlog(interaction: discord.Interaction, channel: discord.TextChannel):
‏    await set_setting(interaction.guild_id, "log_channel", channel.id)
‏    await interaction.response.send_message(
‏        f"تم تعيين قناة السجلات: {channel.mention}",
‏        ephemeral=True,
    )


‏@bot.tree.command(name="setwelcome", description="تحديد قناة الترحيب")
‏@app_commands.checks.has_permissions(manage_guild=True)
‏async def setwelcome(interaction: discord.Interaction, channel: discord.TextChannel):
‏    await set_setting(interaction.guild_id, "welcome_channel", channel.id)
‏    await interaction.response.send_message(
‏        f"تم تعيين قناة الترحيب: {channel.mention}",
‏        ephemeral=True,
    )


‏@bot.tree.command(name="setleave", description="تحديد قناة المغادرة")
‏@app_commands.checks.has_permissions(manage_guild=True)
‏async def setleave(interaction: discord.Interaction, channel: discord.TextChannel):
‏    await set_setting(interaction.guild_id, "leave_channel", channel.id)
‏    await interaction.response.send_message(
‏        f"تم تعيين قناة المغادرة: {channel.mention}",
‏        ephemeral=True,
    )


‏@bot.tree.command(name="setautorole", description="تحديد الرتبة التلقائية")
‏@app_commands.checks.has_permissions(manage_roles=True)
‏async def setautorole(interaction: discord.Interaction, role: discord.Role):
‏    if role >= interaction.guild.me.top_role:
‏        return await interaction.response.send_message(
            "رتبة البوت يجب أن تكون أعلى من الرتبة المحددة.",
‏            ephemeral=True,
        )
‏    await set_setting(interaction.guild_id, "autorole", role.id)
‏    await interaction.response.send_message(
‏        f"تم تعيين الرتبة التلقائية: {role.mention}",
‏        ephemeral=True,
    )


‏@bot.tree.command(name="setstaff", description="تحديد رتبة الطاقم")
‏@app_commands.checks.has_permissions(administrator=True)
‏async def setstaff(interaction: discord.Interaction, role: discord.Role):
‏    await set_setting(interaction.guild_id, "staff_role", role.id)
‏    await interaction.response.send_message(
‏        f"تم تحديد رتبة الطاقم: {role.mention}",
‏        ephemeral=True,
    )


‏# ------------------------- MODERATION -----------------------

‏async def create_case(guild, user, moderator, action, reason):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
            """
‏            INSERT INTO cases
‏            (guild_id,user_id,moderator_id,action,reason,created_at)
‏            VALUES(?,?,?,?,?,?)
            """,
‏            (guild.id, user.id, moderator.id, action, reason, now()),
        )
‏        case_id = cur.lastrowid
‏        await db.commit()
‏    await log_action(
‏        guild,
‏        f"Moderation: {action}",
‏        f"Case #{case_id}\nTarget: {user.mention}\n"
‏        f"Moderator: {moderator.mention}\nReason: {reason}",
    )
‏    return case_id


‏@bot.tree.command(name="ban", description="حظر عضو")
‏@app_commands.checks.has_permissions(ban_members=True)
‏async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "لم يحدد"):
‏    if member == interaction.user or member == interaction.guild.owner:
‏        return await interaction.response.send_message("لا يمكن حظر هذا العضو.", ephemeral=True)
‏    if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
‏        return await interaction.response.send_message("رتبة العضو أعلى من رتبتك أو مساوية لها.", ephemeral=True)
‏    try:
‏        await member.ban(reason=reason)
‏        case_id = await create_case(interaction.guild, member, interaction.user, "ban", reason)
‏        await interaction.response.send_message(f"تم حظر {member} | القضية #{case_id}")
‏    except discord.Forbidden:
‏        await interaction.response.send_message("لا أملك صلاحية الحظر أو رتبة البوت منخفضة.", ephemeral=True)


‏@bot.tree.command(name="unban", description="فك حظر عضو باستخدام معرّفه")
‏@app_commands.checks.has_permissions(ban_members=True)
‏async def unban(interaction: discord.Interaction, user_id: str, reason: str = "لم يحدد"):
‏    try:
‏        uid = int(user_id)
‏        user = await bot.fetch_user(uid)
‏        await interaction.guild.unban(user, reason=reason)
‏        await create_case(interaction.guild, user, interaction.user, "unban", reason)
‏        await interaction.response.send_message(f"تم فك حظر {user}.")
‏    except (ValueError, discord.NotFound):
‏        await interaction.response.send_message("لم أجد هذا المستخدم في قائمة المحظورين.", ephemeral=True)
‏    except discord.Forbidden:
‏        await interaction.response.send_message("لا أملك صلاحية فك الحظر.", ephemeral=True)


‏@bot.tree.command(name="kick", description="طرد عضو")
‏@app_commands.checks.has_permissions(kick_members=True)
‏async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "لم يحدد"):
‏    if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
‏        return await interaction.response.send_message("رتبة العضو أعلى من رتبتك أو مساوية لها.", ephemeral=True)
‏    try:
‏        await member.kick(reason=reason)
‏        case_id = await create_case(interaction.guild, member, interaction.user, "kick", reason)
‏        await interaction.response.send_message(f"تم طرد {member} | القضية #{case_id}")
‏    except discord.Forbidden:
‏        await interaction.response.send_message("لا أملك صلاحية الطرد.", ephemeral=True)


‏@bot.tree.command(name="timeout", description="تقييد عضو لمدة محددة بالدقائق")
‏@app_commands.checks.has_permissions(moderate_members=True)
‏async def timeout_cmd(
‏    interaction: discord.Interaction,
‏    member: discord.Member,
‏    minutes: app_commands.Range[int, 1, 40320],
‏    reason: str = "لم يحدد",
):
‏    if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
‏        return await interaction.response.send_message("لا يمكنك تقييد هذا العضو بسبب ترتيب الرتب.", ephemeral=True)
‏    try:
‏        await member.timeout(timedelta(minutes=minutes), reason=reason)
‏        case_id = await create_case(interaction.guild, member, interaction.user, "timeout", reason)
‏        await interaction.response.send_message(f"تم تقييد {member.mention} لمدة {minutes} دقيقة. القضية #{case_id}")
‏    except discord.Forbidden:
‏        await interaction.response.send_message("لا أملك صلاحية التقييد.", ephemeral=True)


‏@bot.tree.command(name="untimeout", description="إزالة التقييد عن عضو")
‏@app_commands.checks.has_permissions(moderate_members=True)
‏async def untimeout(interaction: discord.Interaction, member: discord.Member, reason: str = "لم يحدد"):
‏    try:
‏        await member.timeout(None, reason=reason)
‏        await create_case(interaction.guild, member, interaction.user, "untimeout", reason)
‏        await interaction.response.send_message(f"تمت إزالة التقييد عن {member.mention}.")
‏    except discord.Forbidden:
‏        await interaction.response.send_message("لا أملك صلاحية إزالة التقييد.", ephemeral=True)


‏@bot.tree.command(name="warn", description="إعطاء تحذير لعضو")
‏@app_commands.checks.has_permissions(moderate_members=True)
‏async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        await db.execute(
            """
‏            INSERT INTO warnings(guild_id,user_id,moderator_id,reason,created_at)
‏            VALUES(?,?,?,?,?)
            """,
‏            (interaction.guild_id, member.id, interaction.user.id, reason, now()),
        )
‏        await db.commit()

‏    case_id = await create_case(interaction.guild, member, interaction.user, "warn", reason)
‏    await interaction.response.send_message(f"تم تحذير {member.mention}. القضية #{case_id}")


‏@bot.tree.command(name="warnings", description="عرض تحذيرات عضو")
‏@app_commands.checks.has_permissions(moderate_members=True)
‏async def warnings(interaction: discord.Interaction, member: discord.Member):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
            """
‏            SELECT moderator_id,reason,created_at FROM warnings
‏            WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 15
            """,
‏            (interaction.guild_id, member.id),
        )
‏        rows = await cur.fetchall()

‏    if not rows:
‏        return await interaction.response.send_message("لا توجد تحذيرات مسجلة.", ephemeral=True)

‏    lines = [
‏        f"<@{mod}> — {reason} — <t:{created}:R>"
‏        for mod, reason, created in rows
    ]
‏    await interaction.response.send_message(
‏        embed=embed(f"تحذيرات {member}", "\n".join(lines)),
‏        ephemeral=True,
    )


‏@bot.tree.command(name="clearwarnings", description="مسح تحذيرات عضو")
‏@app_commands.checks.has_permissions(moderate_members=True)
‏async def clearwarnings(interaction: discord.Interaction, member: discord.Member):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        await db.execute(
‏            "DELETE FROM warnings WHERE guild_id=? AND user_id=?",
‏            (interaction.guild_id, member.id),
        )
‏        await db.commit()
‏    await interaction.response.send_message(f"تم مسح تحذيرات {member.mention}.")


‏@bot.tree.command(name="purge", description="حذف عدد من الرسائل")
‏@app_commands.checks.has_permissions(manage_messages=True)
‏async def purge(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
‏    await interaction.response.defer(ephemeral=True)
‏    deleted = await interaction.channel.purge(limit=amount)
‏    await interaction.followup.send(f"تم حذف {len(deleted)} رسالة.", ephemeral=True)


‏@bot.tree.command(name="slowmode", description="تحديد مهلة بين الرسائل بالثواني")
‏@app_commands.checks.has_permissions(manage_channels=True)
‏async def slowmode(interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
‏    if not isinstance(interaction.channel, discord.TextChannel):
‏        return await interaction.response.send_message("هذا الأمر للقنوات النصية.", ephemeral=True)
‏    await interaction.channel.edit(slowmode_delay=seconds)
‏    await interaction.response.send_message(f"تم ضبط Slowmode على {seconds} ثانية.")


‏@bot.tree.command(name="lock", description="قفل القناة أمام الأعضاء")
‏@app_commands.checks.has_permissions(manage_channels=True)
‏async def lock(interaction: discord.Interaction):
‏    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
‏    overwrite.send_messages = False
‏    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
‏    await interaction.response.send_message("🔒 تم قفل القناة.")


‏@bot.tree.command(name="unlock", description="فتح القناة أمام الأعضاء")
‏@app_commands.checks.has_permissions(manage_channels=True)
‏async def unlock(interaction: discord.Interaction):
‏    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
‏    overwrite.send_messages = None
‏    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
‏    await interaction.response.send_message("🔓 تم فتح القناة.")


‏@bot.tree.command(name="hide", description="إخفاء القناة عن الأعضاء")
‏@app_commands.checks.has_permissions(manage_channels=True)
‏async def hide(interaction: discord.Interaction):
‏    await interaction.channel.set_permissions(
‏        interaction.guild.default_role, view_channel=False
    )
‏    await interaction.response.send_message("تم إخفاء القناة.")


‏@bot.tree.command(name="unhide", description="إظهار القناة للأعضاء")
‏@app_commands.checks.has_permissions(manage_channels=True)
‏async def unhide(interaction: discord.Interaction):
‏    await interaction.channel.set_permissions(
‏        interaction.guild.default_role, view_channel=None
    )
‏    await interaction.response.send_message("تم إظهار القناة.")


‏@bot.tree.command(name="nickname", description="تغيير لقب عضو")
‏@app_commands.checks.has_permissions(manage_nicknames=True)
‏async def nickname(interaction: discord.Interaction, member: discord.Member, name: str = None):
‏    try:
‏        await member.edit(nick=name, reason=f"Changed by {interaction.user}")
‏        await interaction.response.send_message(f"تم تحديث لقب {member.mention}.")
‏    except discord.Forbidden:
‏        await interaction.response.send_message("لا أملك صلاحية تغيير هذا اللقب.", ephemeral=True)


‏@bot.tree.command(name="roleadd", description="إضافة رتبة لعضو")
‏@app_commands.checks.has_permissions(manage_roles=True)
‏async def roleadd(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
‏    if role >= interaction.guild.me.top_role:
‏        return await interaction.response.send_message("رتبة البوت يجب أن تكون أعلى.", ephemeral=True)
‏    try:
‏        await member.add_roles(role, reason=f"Added by {interaction.user}")
‏        await interaction.response.send_message(f"تمت إضافة {role.mention} إلى {member.mention}.")
‏    except discord.Forbidden:
‏        await interaction.response.send_message("لا أملك صلاحية إدارة هذه الرتبة.", ephemeral=True)


‏@bot.tree.command(name="roleremove", description="إزالة رتبة من عضو")
‏@app_commands.checks.has_permissions(manage_roles=True)
‏async def roleremove(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
‏    if role >= interaction.guild.me.top_role:
‏        return await interaction.response.send_message("رتبة البوت يجب أن تكون أعلى.", ephemeral=True)
‏    try:
‏        await member.remove_roles(role, reason=f"Removed by {interaction.user}")
‏        await interaction.response.send_message(f"تمت إزالة {role.mention} من {member.mention}.")
‏    except discord.Forbidden:
‏        await interaction.response.send_message("لا أملك صلاحية إدارة هذه الرتبة.", ephemeral=True)


‏@bot.tree.command(name="modlogs", description="عرض سجل قضايا عضو")
‏@app_commands.checks.has_permissions(moderate_members=True)
‏async def modlogs(interaction: discord.Interaction, member: discord.Member):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
            """
‏            SELECT id,action,reason,moderator_id,created_at
‏            FROM cases WHERE guild_id=? AND user_id=?
‏            ORDER BY id DESC LIMIT 15
            """,
‏            (interaction.guild_id, member.id),
        )
‏        rows = await cur.fetchall()

‏    if not rows:
‏        return await interaction.response.send_message("لا توجد قضايا مسجلة.", ephemeral=True)

‏    lines = [
‏        f"#{cid} **{action}** — {reason} — <@{mod}> — <t:{created}:R>"
‏        for cid, action, reason, mod, created in rows
    ]
‏    await interaction.response.send_message(
‏        embed=embed(f"سجل {member}", "\n".join(lines)),
‏        ephemeral=True,
    )


‏# ------------------------- TICKET PANEL ---------------------

‏@bot.tree.command(name="ticketpanel", description="إرسال لوحة فتح التذاكر")
‏@app_commands.checks.has_permissions(manage_guild=True)
‏async def ticketpanel(interaction: discord.Interaction):
‏    await interaction.channel.send(
‏        embed=embed(
            "🎫 الدعم الفني",
            "اضغط الزر لفتح تذكرة جديدة. يرجى كتابة تفاصيل طلبك بعد فتحها.",
        ),
‏        view=TicketPanelView(),
    )
‏    await interaction.response.send_message("تم إرسال لوحة التذاكر.", ephemeral=True)


‏@bot.tree.command(name="ticketadd", description="إضافة عضو إلى التذكرة الحالية")
‏@app_commands.checks.has_permissions(manage_channels=True)
‏async def ticketadd(interaction: discord.Interaction, member: discord.Member):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
‏            "SELECT channel_id FROM tickets WHERE channel_id=? AND status='open'",
‏            (interaction.channel_id,),
        )
‏        row = await cur.fetchone()
‏    if not row:
‏        return await interaction.response.send_message("هذه ليست تذكرة مفتوحة.", ephemeral=True)
‏    await interaction.channel.set_permissions(
‏        member, view_channel=True, send_messages=True, read_message_history=True
    )
‏    await interaction.response.send_message(f"تمت إضافة {member.mention} للتذكرة.")


‏@bot.tree.command(name="ticketremove", description="إزالة عضو من التذكرة الحالية")
‏@app_commands.checks.has_permissions(manage_channels=True)
‏async def ticketremove(interaction: discord.Interaction, member: discord.Member):
‏    try:
‏        await interaction.channel.set_permissions(member, overwrite=None)
‏        await interaction.response.send_message(f"تمت إزالة {member.mention} من القناة.")
‏    except discord.Forbidden:
‏        await interaction.response.send_message("لا أملك صلاحية تعديل القناة.", ephemeral=True)


‏@bot.tree.command(name="ticketrename", description="تغيير اسم قناة التذكرة")
‏@app_commands.checks.has_permissions(manage_channels=True)
‏async def ticketrename(interaction: discord.Interaction, name: str):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
‏            "SELECT channel_id FROM tickets WHERE channel_id=? AND status='open'",
‏            (interaction.channel_id,),
        )
‏        row = await cur.fetchone()
‏    if not row:
‏        return await interaction.response.send_message("هذه ليست تذكرة مفتوحة.", ephemeral=True)
‏    await interaction.channel.edit(name=name[:90])
‏    await interaction.response.send_message("تم تغيير اسم التذكرة.")


‏@bot.tree.command(name="ticketstats", description="إحصائيات التذاكر")
‏@app_commands.checks.has_permissions(manage_guild=True)
‏async def ticketstats(interaction: discord.Interaction):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
            """
‏            SELECT status,COUNT(*) FROM tickets
‏            WHERE guild_id=? GROUP BY status
            """,
‏            (interaction.guild_id,),
        )
‏        rows = await cur.fetchall()
‏    values = dict(rows)
‏    await interaction.response.send_message(
‏        embed=embed(
            "إحصائيات التذاكر",
‏            f"مفتوحة: {values.get('open', 0)}\nمغلقة: {values.get('closed', 0)}",
        )
    )


‏# ------------------------- SUGGESTIONS / REPORTS ------------

‏@bot.tree.command(name="suggest", description="إرسال اقتراح للإدارة")
‏async def suggest(interaction: discord.Interaction, suggestion: str):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
            """
‏            INSERT INTO suggestions(guild_id,user_id,text,created_at)
‏            VALUES(?,?,?,?)
            """,
‏            (interaction.guild_id, interaction.user.id, suggestion, now()),
        )
‏        sid = cur.lastrowid
‏        await db.commit()

‏    channel_id = await setting(interaction.guild_id, "suggestion_channel")
‏    channel = interaction.guild.get_channel(int(channel_id)) if channel_id else None
‏    if channel:
‏        await channel.send(
‏            embed=embed(
‏                f"اقتراح #{sid}",
‏                f"**من:** {interaction.user.mention}\n{suggestion}",
            )
        )
‏    await interaction.response.send_message(f"تم تسجيل اقتراحك برقم #{sid}.", ephemeral=True)


‏@bot.tree.command(name="setsuggestions", description="تحديد قناة الاقتراحات")
‏@app_commands.checks.has_permissions(manage_guild=True)
‏async def setsuggestions(interaction: discord.Interaction, channel: discord.TextChannel):
‏    await set_setting(interaction.guild_id, "suggestion_channel", channel.id)
‏    await interaction.response.send_message(f"تم تعيين قناة الاقتراحات: {channel.mention}")


‏@bot.tree.command(name="report", description="إرسال بلاغ عن عضو")
‏async def report(interaction: discord.Interaction, member: discord.Member, reason: str):
‏    if member.id == interaction.user.id:
‏        return await interaction.response.send_message("لا يمكنك الإبلاغ عن نفسك.", ephemeral=True)

‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
            """
‏            INSERT INTO reports(guild_id,reporter_id,target_id,reason,created_at)
‏            VALUES(?,?,?,?,?)
            """,
‏            (interaction.guild_id, interaction.user.id, member.id, reason, now()),
        )
‏        rid = cur.lastrowid
‏        await db.commit()

‏    await log_action(
‏        interaction.guild,
‏        f"Report #{rid}",
‏        f"Reporter: {interaction.user.mention}\n"
‏        f"Target: {member.mention}\nReason: {reason}",
    )
‏    await interaction.response.send_message(
‏        f"تم إرسال البلاغ للإدارة برقم #{rid}.",
‏        ephemeral=True,
    )


‏@bot.tree.command(name="reportstatus", description="عرض البلاغات المفتوحة")
‏@app_commands.checks.has_permissions(moderate_members=True)
‏async def reportstatus(interaction: discord.Interaction):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
            """
‏            SELECT id,reporter_id,target_id,reason FROM reports
‏            WHERE guild_id=? AND status='open'
‏            ORDER BY id DESC LIMIT 15
            """,
‏            (interaction.guild_id,),
        )
‏        rows = await cur.fetchall()
‏    if not rows:
‏        return await interaction.response.send_message("لا توجد بلاغات مفتوحة.", ephemeral=True)
‏    lines = [
‏        f"#{rid}: المبلّغ <@{reporter}>، العضو <@{target}> — {reason}"
‏        for rid, reporter, target, reason in rows
    ]
‏    await interaction.response.send_message(
‏        embed=embed("البلاغات المفتوحة", "\n".join(lines)),
‏        ephemeral=True,
    )


‏@bot.tree.command(name="closereport", description="إغلاق بلاغ برقم البلاغ")
‏@app_commands.checks.has_permissions(moderate_members=True)
‏async def closereport(interaction: discord.Interaction, report_id: int):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
‏            "UPDATE reports SET status='closed' WHERE guild_id=? AND id=?",
‏            (interaction.guild_id, report_id),
        )
‏        await db.commit()
‏    if cur.rowcount:
‏        await interaction.response.send_message(f"تم إغلاق البلاغ #{report_id}.")
‏    else:
‏        await interaction.response.send_message("لم يتم العثور على البلاغ.", ephemeral=True)


‏# ------------------------- ECONOMY --------------------------

‏@bot.tree.command(name="balance", description="عرض رصيدك أو رصيد عضو")
‏async def balance(interaction: discord.Interaction, member: discord.Member = None):
‏    member = member or interaction.user
‏    wallet, bank = await get_balance(interaction.guild_id, member.id)
‏    await interaction.response.send_message(
‏        embed=embed(
‏            f"رصيد {member.display_name}",
‏            f"💵 المحفظة: **{money(wallet)}**\n"
‏            f"🏦 البنك: **{money(bank)}**\n"
‏            f"المجموع: **{money(wallet + bank)}**",
        )
    )


‏@bot.tree.command(name="daily", description="استلام المكافأة اليومية")
‏async def daily(interaction: discord.Interaction):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        await db.execute(
‏            "INSERT OR IGNORE INTO economy(guild_id,user_id) VALUES(?,?,?)",
‏            (interaction.guild_id, interaction.user.id, 0),
        )
‏        cur = await db.execute(
‏            "SELECT last_daily FROM economy WHERE guild_id=? AND user_id=?",
‏            (interaction.guild_id, interaction.user.id),
        )
‏        row = await cur.fetchone()
‏        last = row[0] if row else 0

‏        if now() - last < 86400:
‏            remaining = 86400 - (now() - last)
‏            return await interaction.response.send_message(
‏                f"استلمت مكافأتك مسبقًا. جرّب بعد <t:{now()+remaining}:R>.",
‏                ephemeral=True,
            )

‏        reward = 500
‏        await db.execute(
            """
‏            UPDATE economy SET wallet=wallet+?,last_daily=?
‏            WHERE guild_id=? AND user_id=?
            """,
‏            (reward, now(), interaction.guild_id, interaction.user.id),
        )
‏        await db.commit()

‏    await transaction(interaction.guild_id, interaction.user.id, "daily", reward)
‏    await interaction.response.send_message(f"استلمت مكافأتك اليومية: **{money(reward)}**.")


‏@bot.tree.command(name="work", description="العمل للحصول على مال")
‏async def work(interaction: discord.Interaction):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        await db.execute(
‏            "INSERT OR IGNORE INTO economy(guild_id,user_id) VALUES(?,?,?)",
‏            (interaction.guild_id, interaction.user.id, 0),
        )
‏        cur = await db.execute(
‏            "SELECT last_work FROM economy WHERE guild_id=? AND user_id=?",
‏            (interaction.guild_id, interaction.user.id),
        )
‏        row = await cur.fetchone()
‏        last = row[0] if row else 0
‏        if now() - last < 3600:
‏            return await interaction.response.send_message(
‏                f"يمكنك العمل مرة أخرى <t:{last+3600}:R>.",
‏                ephemeral=True,
            )
‏        reward = random.randint(100, 350)
‏        await db.execute(
            """
‏            UPDATE economy SET wallet=wallet+?,last_work=?
‏            WHERE guild_id=? AND user_id=?
            """,
‏            (reward, now(), interaction.guild_id, interaction.user.id),
        )
‏        await db.commit()

‏    await transaction(interaction.guild_id, interaction.user.id, "work", reward)
‏    await interaction.response.send_message(f"عملت وحصلت على **{money(reward)}**.")


‏@bot.tree.command(name="deposit", description="إيداع مال في البنك")
‏async def deposit(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100000000]):
‏    wallet, _ = await get_balance(interaction.guild_id, interaction.user.id)
‏    if wallet < amount:
‏        return await interaction.response.send_message("رصيد المحفظة غير كافٍ.", ephemeral=True)
‏    await change_balance(interaction.guild_id, interaction.user.id, -amount, amount)
‏    await transaction(interaction.guild_id, interaction.user.id, "deposit", amount)
‏    await interaction.response.send_message(f"أودعت **{money(amount)}** في البنك.")


‏@bot.tree.command(name="withdraw", description="سحب مال من البنك")
‏async def withdraw(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100000000]):
‏    _, bank = await get_balance(interaction.guild_id, interaction.user.id)
‏    if bank < amount:
‏        return await interaction.response.send_message("رصيد البنك غير كافٍ.", ephemeral=True)
‏    await change_balance(interaction.guild_id, interaction.user.id, amount, -amount)
‏    await transaction(interaction.guild_id, interaction.user.id, "withdraw", amount)
‏    await interaction.response.send_message(f"سحبت **{money(amount)}** من البنك.")


‏@bot.tree.command(name="pay", description="تحويل مال إلى عضو")
‏async def pay(interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, 100000000]):
‏    if member.bot or member.id == interaction.user.id:
‏        return await interaction.response.send_message("لا يمكنك التحويل لهذا المستخدم.", ephemeral=True)

‏    wallet, _ = await get_balance(interaction.guild_id, interaction.user.id)
‏    if wallet < amount:
‏        return await interaction.response.send_message("رصيدك غير كافٍ.", ephemeral=True)

‏    await change_balance(interaction.guild_id, interaction.user.id, -amount)
‏    await change_balance(interaction.guild_id, member.id, amount)
‏    await transaction(interaction.guild_id, interaction.user.id, "pay_sent", amount, str(member.id))
‏    await transaction(interaction.guild_id, member.id, "pay_received", amount, str(interaction.user.id))
‏    await interaction.response.send_message(
‏        f"حوّلت **{money(amount)}** إلى {member.mention}."
    )


‏@bot.tree.command(name="richest", description="عرض أغنى الأعضاء")
‏async def richest(interaction: discord.Interaction):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
            """
‏            SELECT user_id,wallet+bank AS total FROM economy
‏            WHERE guild_id=? ORDER BY total DESC LIMIT 10
            """,
‏            (interaction.guild_id,),
        )
‏        rows = await cur.fetchall()

‏    if not rows:
‏        return await interaction.response.send_message("لا توجد أرصدة مسجلة.")

‏    lines = [
‏        f"**{i}.** <@{uid}> — **{money(total)}**"
‏        for i, (uid, total) in enumerate(rows, 1)
    ]
‏    await interaction.response.send_message(embed=embed("🏆 أغنى الأعضاء", "\n".join(lines)))


‏@bot.tree.command(name="transactions", description="عرض آخر معاملاتك المالية")
‏async def transactions_cmd(interaction: discord.Interaction, member: discord.Member = None):
‏    member = member or interaction.user
‏    if member.id != interaction.user.id and not is_staff(interaction):
‏        return await interaction.response.send_message(
            "يمكنك عرض معاملاتك فقط.",
‏            ephemeral=True,
        )

‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
            """
‏            SELECT kind,amount,note,created_at FROM transactions
‏            WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 10
            """,
‏            (interaction.guild_id, member.id),
        )
‏        rows = await cur.fetchall()

‏    if not rows:
‏        return await interaction.response.send_message("لا توجد معاملات مسجلة.", ephemeral=True)

‏    lines = [
‏        f"**{kind}** — {money(amount)} — {note or '-'} — <t:{created}:R>"
‏        for kind, amount, note, created in rows
    ]
‏    await interaction.response.send_message(
‏        embed=embed(f"معاملات {member.display_name}", "\n".join(lines)),
‏        ephemeral=True,
    )


‏@bot.tree.command(name="economyadd", description="إضافة مال لعضو إداريًا")
‏@app_commands.checks.has_permissions(administrator=True)
‏async def economyadd(interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, 100000000]):
‏    await change_balance(interaction.guild_id, member.id, wallet_delta=amount)
‏    await transaction(interaction.guild_id, member.id, "admin_add", amount, str(interaction.user.id))
‏    await interaction.response.send_message(f"تمت إضافة **{money(amount)}** إلى محفظة {member.mention}.")


‏@bot.tree.command(name="economyremove", description="خصم مال من عضو إداريًا")
‏@app_commands.checks.has_permissions(administrator=True)
‏async def economyremove(interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, 100000000]):
‏    wallet, _ = await get_balance(interaction.guild_id, member.id)
‏    if wallet < amount:
‏        return await interaction.response.send_message("رصيد المحفظة أقل من المبلغ.", ephemeral=True)
‏    await change_balance(interaction.guild_id, member.id, wallet_delta=-amount)
‏    await transaction(interaction.guild_id, member.id, "admin_remove", amount, str(interaction.user.id))
‏    await interaction.response.send_message(f"تم خصم **{money(amount)}** من {member.mention}.")


‏# ------------------------- XP / LEVELS ----------------------

‏@bot.tree.command(name="rank", description="عرض نقاط وخبرة عضو")
‏async def rank(interaction: discord.Interaction, member: discord.Member = None):
‏    member = member or interaction.user
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
‏            "SELECT points,messages FROM xp WHERE guild_id=? AND user_id=?",
‏            (interaction.guild_id, member.id),
        )
‏        row = await cur.fetchone()

‏    points, messages = row if row else (0, 0)
‏    level = int((points / 100) ** 0.5)
‏    needed = ((level + 1) ** 2) * 100

‏    await interaction.response.send_message(
‏        embed=embed(
‏            f"📈 مستوى {member.display_name}",
‏            f"المستوى: **{level}**\n"
‏            f"النقاط: **{points}**\n"
‏            f"الرسائل المحتسبة: **{messages}**\n"
‏            f"نقاط المستوى التالي: **{needed}**",
        )
    )


‏@bot.tree.command(name="leaderboard", description="لوحة متصدرين الخبرة")
‏async def leaderboard(interaction: discord.Interaction):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
            """
‏            SELECT user_id,points FROM xp WHERE guild_id=?
‏            ORDER BY points DESC LIMIT 10
            """,
‏            (interaction.guild_id,),
        )
‏        rows = await cur.fetchall()

‏    if not rows:
‏        return await interaction.response.send_message("لا توجد بيانات خبرة بعد.")

‏    lines = [
‏        f"**{i}.** <@{uid}> — {points} نقطة"
‏        for i, (uid, points) in enumerate(rows, 1)
    ]
‏    await interaction.response.send_message(embed=embed("🏆 متصدرون الخبرة", "\n".join(lines)))


‏# ------------------------- STAFF SYSTEM ---------------------

‏@bot.tree.command(name="staffeval", description="تقييم عضو من الطاقم")
‏@app_commands.checks.has_permissions(manage_guild=True)
‏async def staffeval(
‏    interaction: discord.Interaction,
‏    member: discord.Member,
‏    score: app_commands.Range[int, 1, 10],
‏    note: str,
):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        await db.execute(
            """
‏            INSERT INTO staff_evaluations
‏            (guild_id,staff_id,evaluator_id,score,note,created_at)
‏            VALUES(?,?,?,?,?,?)
            """,
‏            (interaction.guild_id, member.id, interaction.user.id, score, note, now()),
        )
‏        await db.commit()

‏    await interaction.response.send_message(
‏        f"تم تسجيل تقييم {member.mention}: **{score}/10**."
    )


‏@bot.tree.command(name="staffprofile", description="عرض ملف وتقييمات عضو الطاقم")
‏@app_commands.checks.has_permissions(manage_guild=True)
‏async def staffprofile(interaction: discord.Interaction, member: discord.Member):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
            """
‏            SELECT AVG(score),COUNT(*) FROM staff_evaluations
‏            WHERE guild_id=? AND staff_id=?
            """,
‏            (interaction.guild_id, member.id),
        )
‏        avg, count = await cur.fetchone()

‏        cur = await db.execute(
            """
‏            SELECT SUM(amount) FROM staff_ledger
‏            WHERE guild_id=? AND staff_id=?
            """,
‏            (interaction.guild_id, member.id),
        )
‏        ledger = (await cur.fetchone())[0] or 0

‏        cur = await db.execute(
            """
‏            SELECT note,actor_id,created_at FROM staff_notes
‏            WHERE guild_id=? AND staff_id=? ORDER BY id DESC LIMIT 5
            """,
‏            (interaction.guild_id, member.id),
        )
‏        notes = await cur.fetchall()

‏    note_text = "\n".join(
‏        f"• {n} — <@{actor}> — <t:{created}:R>"
‏        for n, actor, created in notes
‏    ) or "لا توجد ملاحظات."

‏    await interaction.response.send_message(
‏        embed=embed(
‏            f"ملف الطاقم: {member.display_name}",
‏            f"متوسط التقييم: **{avg or 0:.2f}/10**\n"
‏            f"عدد التقييمات: **{count}**\n"
‏            f"صافي سجل حساب الطاقم: **{money(ledger)}**\n\n"
‏            f"**آخر الملاحظات:**\n{note_text}",
        ),
‏        ephemeral=True,
    )


‏@bot.tree.command(name="staffnote", description="إضافة ملاحظة لعضو الطاقم")
‏@app_commands.checks.has_permissions(manage_guild=True)
‏async def staffnote(interaction: discord.Interaction, member: discord.Member, note: str):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        await db.execute(
            """
‏            INSERT INTO staff_notes(guild_id,staff_id,actor_id,note,created_at)
‏            VALUES(?,?,?,?,?)
            """,
‏            (interaction.guild_id, member.id, interaction.user.id, note, now()),
        )
‏        await db.commit()

‏    await interaction.response.send_message("تم تسجيل الملاحظة.", ephemeral=True)


‏@bot.tree.command(name="staffmoney", description="تسجيل مبلغ في حساب الطاقم المستقل")
‏@app_commands.checks.has_permissions(administrator=True)
‏async def staffmoney(
‏    interaction: discord.Interaction,
‏    member: discord.Member,
‏    amount: int,
‏    note: str,
):
‏    if amount == 0:
‏        return await interaction.response.send_message("المبلغ لا يمكن أن يكون صفرًا.", ephemeral=True)

‏    async with aiosqlite.connect(DB_FILE) as db:
‏        await db.execute(
            """
‏            INSERT INTO staff_ledger
‏            (guild_id,staff_id,actor_id,amount,note,created_at)
‏            VALUES(?,?,?,?,?,?)
            """,
‏            (interaction.guild_id, member.id, interaction.user.id, amount, note, now()),
        )
‏        await db.commit()

‏    await interaction.response.send_message(
‏        f"تم تسجيل حركة حساب الطاقم لـ {member.mention}: **{amount:+,}**.",
‏        ephemeral=True,
    )


‏@bot.tree.command(name="staffstats", description="إحصائيات تقييمات الطاقم")
‏@app_commands.checks.has_permissions(manage_guild=True)
‏async def staffstats(interaction: discord.Interaction):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        cur = await db.execute(
            """
‏            SELECT staff_id,AVG(score),COUNT(*)
‏            FROM staff_evaluations WHERE guild_id=?
‏            GROUP BY staff_id ORDER BY AVG(score) DESC LIMIT 10
            """,
‏            (interaction.guild_id,),
        )
‏        rows = await cur.fetchall()

‏    if not rows:
‏        return await interaction.response.send_message("لا توجد تقييمات مسجلة.", ephemeral=True)

‏    lines = [
‏        f"<@{uid}> — **{avg:.2f}/10** ({count} تقييم)"
‏        for uid, avg, count in rows
    ]
‏    await interaction.response.send_message(
‏        embed=embed("إحصائيات تقييم الطاقم", "\n".join(lines)),
‏        ephemeral=True,
    )


‏# ------------------------- UTILITY --------------------------

‏@bot.tree.command(name="ping", description="عرض سرعة استجابة البوت")
‏async def ping(interaction: discord.Interaction):
‏    await interaction.response.send_message(f"🏓 {round(bot.latency * 1000)} ms")


‏@bot.tree.command(name="avatar", description="عرض صورة عضو")
‏async def avatar(interaction: discord.Interaction, member: discord.Member = None):
‏    member = member or interaction.user
‏    e = embed(f"Avatar: {member.display_name}")
‏    e.set_image(url=member.display_avatar.url)
‏    await interaction.response.send_message(embed=e)


‏@bot.tree.command(name="userinfo", description="عرض معلومات عضو")
‏async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
‏    member = member or interaction.user
‏    roles = [r.mention for r in member.roles[1:]]
‏    role_text = ", ".join(roles[-15:]) if roles else "لا توجد رتب إضافية"
‏    e = embed(
‏        f"معلومات {member}",
‏        f"المعرّف: `{member.id}`\n"
‏        f"تاريخ الانضمام: {discord.utils.format_dt(member.joined_at, 'R') if member.joined_at else 'غير معروف'}\n"
‏        f"تاريخ إنشاء الحساب: {discord.utils.format_dt(member.created_at, 'R')}\n"
‏        f"البوت: {'نعم' if member.bot else 'لا'}\n"
‏        f"الرتب: {role_text}",
    )
‏    e.set_thumbnail(url=member.display_avatar.url)
‏    await interaction.response.send_message(embed=e)


‏@bot.tree.command(name="serverinfo", description="عرض معلومات السيرفر")
‏async def serverinfo(interaction: discord.Interaction):
‏    guild = interaction.guild
‏    e = embed(
‏        f"معلومات {guild.name}",
‏        f"المعرّف: `{guild.id}`\n"
‏        f"الأعضاء: **{guild.member_count}**\n"
‏        f"القنوات: **{len(guild.channels)}**\n"
‏        f"الرتب: **{len(guild.roles)}**\n"
‏        f"المالك: <@{guild.owner_id}>\n"
‏        f"تاريخ الإنشاء: {discord.utils.format_dt(guild.created_at, 'D')}",
    )
‏    if guild.icon:
‏        e.set_thumbnail(url=guild.icon.url)
‏    await interaction.response.send_message(embed=e)


‏@bot.tree.command(name="botinfo", description="عرض معلومات البوت")
‏async def botinfo(interaction: discord.Interaction):
‏    await interaction.response.send_message(
‏        embed=embed(
            "معلومات البوت",
‏            f"الاسم: **{bot.user}**\n"
‏            f"السيرفرات: **{len(bot.guilds)}**\n"
‏            f"Latency: **{round(bot.latency * 1000)} ms**\n"
‏            f"discord.py: **{discord.__version__}**",
        )
    )


‏@bot.tree.command(name="poll", description="إنشاء تصويت بسيط")
‏async def poll(interaction: discord.Interaction, question: str):
‏    e = embed("📊 تصويت", question)
‏    await interaction.response.send_message(embed=e)
‏    msg = await interaction.original_response()
‏    for emoji in ("👍", "👎"):
‏        try:
‏            await msg.add_reaction(emoji)
‏        except discord.HTTPException:
‏            pass


‏@bot.tree.command(name="afk", description="تفعيل وضع AFK")
‏async def afk(interaction: discord.Interaction, reason: str = "غير متوفر"):
‏    async with aiosqlite.connect(DB_FILE) as db:
‏        await db.execute(
            """
‏            INSERT INTO afk(guild_id,user_id,reason,created_at)
‏            VALUES(?,?,?,?)
‏            ON CONFLICT(guild_id,user_id)
‏            DO UPDATE SET reason=excluded.reason,created_at=excluded.created_at
            """,
‏            (interaction.guild_id, interaction.user.id, reason, now()),
        )
‏        await db.commit()
‏    await interaction.response.send_message(
‏        f"تم تفعيل AFK: {reason}",
‏        ephemeral=True,
    )


‏@bot.tree.command(name="remind", description="إنشاء تذكير بعد عدد من الدقائق")
‏async def remind(
‏    interaction: discord.Interaction,
‏    minutes: app_commands.Range[int, 1, 10080],
‏    reminder: str,
):
‏    await interaction.response.send_message(
‏        f"سأذكرك بعد {minutes} دقيقة.",
‏        ephemeral=True,
    )

‏    async def send_reminder():
‏        await asyncio.sleep(minutes * 60)
‏        try:
‏            await interaction.user.send(f"⏰ تذكير من {interaction.guild.name}: {reminder}")
‏        except discord.HTTPException:
‏            try:
‏                await interaction.channel.send(
‏                    f"{interaction.user.mention} ⏰ تذكير: {reminder}"
                )
‏            except discord.HTTPException:
‏                pass

‏    asyncio.create_task(send_reminder())


‏@bot.tree.command(name="help", description="عرض أقسام أوامر البوت")
‏async def help_cmd(interaction: discord.Interaction):
‏    e = embed(
        "📚 أوامر البوت",
        "**الإعداد:** `/setup` `/settings` `/setlog` `/setwelcome` `/setleave` `/setstaff` `/setautorole`\n"
        "**الإشراف:** `/ban` `/unban` `/kick` `/timeout` `/untimeout` `/warn` `/warnings` `/clearwarnings` `/modlogs` `/purge` `/slowmode` `/lock` `/unlock` `/hide` `/unhide` `/nickname` `/roleadd` `/roleremove`\n"
        "**التذاكر:** `/ticketpanel` `/ticketadd` `/ticketremove` `/ticketrename` `/ticketstats`\n"
        "**المجتمع:** `/suggest` `/setsuggestions` `/report` `/reportstatus` `/closereport` `/poll` `/afk` `/remind`\n"
        "**الاقتصاد:** `/balance` `/daily` `/work` `/deposit` `/withdraw` `/pay` `/richest` `/transactions` `/economyadd` `/economyremove`\n"
        "**المستويات:** `/rank` `/leaderboard`\n"
        "**الطاقم:** `/staffeval` `/staffprofile` `/staffnote` `/staffmoney` `/staffstats`\n"
        "**معلومات:** `/ping` `/avatar` `/userinfo` `/serverinfo` `/botinfo` `/help`",
    )
‏    await interaction.response.send_message(embed=e, ephemeral=True)


‏# ------------------------- ERROR HANDLING -------------------

‏@bot.tree.error
‏async def on_app_command_error(
‏    interaction: discord.Interaction,
‏    error: app_commands.AppCommandError,
):
‏    if isinstance(error, app_commands.MissingPermissions):
‏        message = "ما عندك الصلاحيات اللازمة لهذا الأمر."
‏    elif isinstance(error, app_commands.BotMissingPermissions):
‏        message = "البوت يحتاج صلاحيات إضافية لتنفيذ هذا الأمر."
‏    elif isinstance(error, app_commands.CommandOnCooldown):
‏        message = "الأمر عليه فترة انتظار. جرّب بعد قليل."
‏    else:
‏        log.exception(
‏            "Application command error",
‏            exc_info=(type(error), error, error.__traceback__),
        )
‏        message = "حدث خطأ أثناء تنفيذ الأمر. تحقق من صلاحيات البوت وسجلات التشغيل."

‏    try:
‏        if interaction.response.is_done():
‏            await interaction.followup.send(message, ephemeral=True)
‏        else:
‏            await interaction.response.send_message(message, ephemeral=True)
‏    except discord.HTTPException:
‏        pass


‏# ------------------------- START ----------------------------

‏if __name__ == "__main__":
‏    if not TOKEN:
‏        raise RuntimeError(
‏            "Missing DISCORD_TOKEN environment variable. "
‏            "Set your bot token as an environment variable before starting."
        )
‏    bot.run(TOKEN)
