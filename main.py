import os
import sqlite3
import asyncio
import discord

from discord.ext import commands
from discord import app_commands

# ==================================
# إعدادات البوت
# ==================================

TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE = "بيانات_البوت.db"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# منع تكرار إنشاء التذاكر بالتزامن
اقفال_التذاكر = {}
اقفال_قاعدة_البيانات = asyncio.Lock()


# ==================================
# قاعدة البيانات
# ==================================

def تهيئة_قاعدة_البيانات():
    with sqlite3.connect(DATABASE) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS التذاكر (
                معرّف INTEGER PRIMARY KEY AUTOINCREMENT,
                معرّف_السيرفر INTEGER NOT NULL,
                معرّف_العضو INTEGER NOT NULL,
                معرّف_القناة INTEGER UNIQUE,
                الحالة TEXT NOT NULL DEFAULT 'مفتوحة',
                UNIQUE (معرّف_السيرفر, معرّف_العضو, الحالة)
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS إعدادات_السيرفر (
                معرّف_السيرفر INTEGER PRIMARY KEY,
                قناة_السجلات INTEGER,
                قناة_الترحيب INTEGER,
                قناة_المغادرة INTEGER,
                قناة_الاقتراحات INTEGER,
                قناة_التذاكر INTEGER
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS الخبرة (
                معرّف_السيرفر INTEGER NOT NULL,
                معرّف_العضو INTEGER NOT NULL,
                النقاط INTEGER NOT NULL DEFAULT 0,
                المستوى INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (معرّف_السيرفر, معرّف_العضو)
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS الأرصدة (
                معرّف_السيرفر INTEGER NOT NULL,
                معرّف_العضو INTEGER NOT NULL,
                الرصيد INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (معرّف_السيرفر, معرّف_العضو)
            )
        """)

        db.commit()


# ==================================
# سجل العمليات
# ==================================

async def تسجيل_عملية(السيرفر, النص):
    with sqlite3.connect(DATABASE) as db:
        نتيجة = db.execute("""
            SELECT قناة_السجلات
            FROM إعدادات_السيرفر
            WHERE معرّف_السيرفر = ?
        """, (السيرفر.id,)).fetchone()

    if not نتيجة or not نتيجة[0]:
        return

    القناة = السيرفر.get_channel(نتيجة[0])

    if القناة:
        try:
            await القناة.send(
                f"📋 **سجل العمليات**\n{النص}"
            )
        except discord.HTTPException:
            pass


# ==================================
# تشغيل البوت
# ==================================

@bot.event
async def on_ready():
    تهيئة_قاعدة_البيانات()

    bot.add_view(لوحة_التذاكر())

    try:
        الأوامر = await bot.tree.sync()
        print(f"تم تحديث {len(الأوامر)} أمر.")
    except Exception as خطأ:
        print(f"تعذر تحديث الأوامر: {خطأ}")

    print(f"تم تشغيل البوت: {bot.user}")


# ==================================
# أمر المساعدة
# ==================================

@bot.tree.command(
    name="مساعدة",
    description="عرض معلومات وأوامر البوت"
)
async def مساعدة(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 قائمة أوامر البوت",
        description=(
            "🎫 `/إنشاء_لوحة_التذاكر`\n"
            "📋 `/تحديد_السجلات`\n"
            "👋 `/تحديد_الترحيب`\n"
            "💡 `/اقتراح`\n"
            "💰 `/رصيدي`\n"
            "🏆 `/مستواي`\n"
            "📊 `/معلومات_السيرفر`\n"
            "🔨 `/طرد`\n"
            "🔇 `/اسكت`\n"
            "🔊 `/فك_السكوت`\n"
            "🚫 `/حظر`\n"
            "📨 `/إرسال_رسالة`\n"
        ),
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ==================================
# تحديد قناة السجلات
# ==================================

@bot.tree.command(
    name="تحديد_السجلات",
    description="تحديد قناة تسجيل عمليات البوت"
)
@app_commands.checks.has_permissions(administrator=True)
async def تحديد_السجلات(
    interaction: discord.Interaction,
    القناة: discord.TextChannel
):
    with sqlite3.connect(DATABASE) as db:
        db.execute("""
            INSERT INTO إعدادات_السيرفر
                (معرّف_السيرفر, قناة_السجلات)
            VALUES (?, ?)
            ON CONFLICT(معرّف_السيرفر)
            DO UPDATE SET قناة_السجلات = excluded.قناة_السجلات
        """, (interaction.guild_id, القناة.id))
        db.commit()

    await interaction.response.send_message(
        f"تم تحديد قناة السجلات: {القناة.mention}",
        ephemeral=True
    )


# ==================================
# تحديد قناة الترحيب
# ==================================

@bot.tree.command(
    name="تحديد_الترحيب",
    description="تحديد قناة الترحيب بالأعضاء"
)
@app_commands.checks.has_permissions(administrator=True)
async def تحديد_الترحيب(
    interaction: discord.Interaction,
    القناة: discord.TextChannel
):
    with sqlite3.connect(DATABASE) as db:
        db.execute("""
            INSERT INTO إعدادات_السيرفر
                (معرّف_السيرفر, قناة_الترحيب)
            VALUES (?, ?)
            ON CONFLICT(معرّف_السيرفر)
            DO UPDATE SET قناة_الترحيب = excluded.قناة_الترحيب
        """, (interaction.guild_id, القناة.id))
        db.commit()

    await interaction.response.send_message(
        f"تم تحديد قناة الترحيب: {القناة.mention}",
        ephemeral=True
    )


@bot.event
async def on_member_join(العضو):
    with sqlite3.connect(DATABASE) as db:
        نتيجة = db.execute("""
            SELECT قناة_الترحيب
            FROM إعدادات_السيرفر
            WHERE معرّف_السيرفر = ?
        """, (العضو.guild.id,)).fetchone()

    if نتيجة and نتيجة[0]:
        القناة = العضو.guild.get_channel(نتيجة[0])

        if القناة:
            await القناة.send(
                f"🎉 أهلًا وسهلًا {العضو.mention}!\n"
                f"نورت سيرفر **{العضو.guild.name}**."
            )


# ==================================
# نظام التذاكر
# ==================================

class لوحة_التذاكر(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="فتح تذكرة",
        emoji="🎫",
        style=discord.ButtonStyle.primary,
        custom_id="لوحة_التذاكر:فتح"
    )
    async def فتح_تذكرة(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "هذا الزر متاح داخل السيرفر فقط.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        السيرفر = interaction.guild
        العضو = interaction.user
        القفل = اقفال_التذاكر.setdefault(
            (السيرفر.id, العضو.id),
            asyncio.Lock()
        )

        async with القفل:
            with sqlite3.connect(DATABASE) as db:
                db.execute("BEGIN IMMEDIATE")

                موجودة = db.execute("""
                    SELECT معرّف_القناة
                    FROM التذاكر
                    WHERE معرّف_السيرفر = ?
                      AND معرّف_العضو = ?
                      AND الحالة = 'مفتوحة'
                """, (السيرفر.id, العضو.id)).fetchone()

                if موجودة:
                    القناة_القديمة = السيرفر.get_channel(
                        موجودة[0]
                    ) if موجودة[0] else None

                    if القناة_القديمة:
                        db.commit()
                        await interaction.followup.send(
                            f"لديك تذكرة مفتوحة بالفعل: "
                            f"{القناة_القديمة.mention}",
                            ephemeral=True
                        )
                        return

                    # إزالة التذكرة القديمة إذا حذفت قناتها
                    db.execute("""
                        UPDATE التذاكر
                        SET الحالة = 'مغلقة'
                        WHERE معرّف_السيرفر = ?
                          AND معرّف_العضو = ?
                          AND الحالة = 'مفتوحة'
                    """, (السيرفر.id, العضو.id))

                الفئة = discord.utils.get(
                    السيرفر.categories,
                    name="التذاكر"
                )

                if الفئة is None:
                    try:
                        الفئة = await السيرفر.create_category(
                            "التذاكر",
                            reason="إنشاء فئة نظام التذاكر"
                        )
                    except discord.HTTPException:
                        db.rollback()
                        await interaction.followup.send(
                            "تعذر إنشاء فئة التذاكر. تحقق من صلاحيات البوت.",
                            ephemeral=True
                        )
                        return

                الصلاحيات = {
                    السيرفر.default_role: discord.PermissionOverwrite(
                        view_channel=False
                    ),
                    العضو: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True
                    ),
                    السيرفر.me: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        manage_channels=True,
                        read_message_history=True
                    )
                }

                try:
                    قناة = await السيرفر.create_text_channel(
                        name=f"تذكرة-{العضو.id}",
                        category=الفئة,
                        overwrites=الصلاحيات,
                        reason=f"تذكرة دعم للعضو {العضو.id}"
                    )

                    db.execute("""
                        INSERT INTO التذاكر (
                            معرّف_السيرفر,
                            معرّف_العضو,
                            معرّف_القناة,
                            الحالة
                        ) VALUES (?, ?, ?, 'مفتوحة')
                    """, (السيرفر.id, العضو.id, قناة.id))

                    db.commit()

                except Exception as خطأ:
                    db.rollback()

                    # إزالة القناة إذا فشل تسجيلها في قاعدة البيانات
                    if "قناة" in locals():
                        try:
                            await قناة.delete(
                                reason="فشل حفظ التذكرة في قاعدة البيانات"
                            )
                        except discord.HTTPException:
                            pass

                    print(f"خطأ إنشاء التذكرة: {خطأ}")

                    await interaction.followup.send(
                        "تعذر إنشاء التذكرة. حاول مرة أخرى.",
                        ephemeral=True
                    )
                    return

            await قناة.send(
                f"مرحبًا {العضو.mention}، تم فتح تذكرتك.\n"
                "اشرح مشكلتك وسيتم مساعدتك.",
                view=أزرار_إغلاق_التذكرة()
            )

            await تسجيل_عملية(
                السيرفر,
                f"فتح تذكرة للعضو {العضو.mention} في {قناة.mention}"
            )

            await interaction.followup.send(
                f"تم فتح تذكرتك: {قناة.mention}",
                ephemeral=True
            )


class أزرار_إغلاق_التذكرة(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="إغلاق التذكرة",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="التذاكر:إغلاق"
    )
    async def إغلاق_التذكرة(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "ليس لديك صلاحية إغلاق التذاكر.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        with sqlite3.connect(DATABASE) as db:
            db.execute("""
                UPDATE التذاكر
                SET الحالة = 'مغلقة'
                WHERE معرّف_القناة = ?
                  AND معرّف_السيرفر = ?
                  AND الحالة = 'مفتوحة'
            """, (interaction.channel_id, interaction.guild_id))
            db.commit()

        await تسجيل_عملية(
            interaction.guild,
            f"إغلاق التذكرة بواسطة {interaction.user.mention}"
        )

        await interaction.channel.delete(
            reason=f"إغلاق التذكرة بواسطة {interaction.user}"
        )


@bot.tree.command(
    name="إنشاء_لوحة_التذاكر",
    description="إنشاء لوحة فتح التذاكر"
)
@app_commands.checks.has_permissions(administrator=True)
async def إنشاء_لوحة_التذاكر(
    interaction: discord.Interaction
):
    await interaction.response.send_message(
        "🎫 **الدعم الفني**\nاضغط على الزر لفتح تذكرة.",
        view=لوحة_التذاكر()
    )


# ==================================
# نظام الاقتراحات
# ==================================

@bot.tree.command(
    name="اقتراح",
    description="إرسال اقتراح لإدارة السيرفر"
)
@app_commands.describe(النص="اكتب اقتراحك")
async def اقتراح(
    interaction: discord.Interaction,
    النص: str
):
    embed = discord.Embed(
        title="💡 اقتراح جديد",
        description=النص,
        color=discord.Color.green()
    )

    embed.set_footer(
        text=f"مقدم الاقتراح: {interaction.user}"
    )

    await interaction.response.send_message(
        "تم إرسال اقتراحك.",
        ephemeral=True
    )

    await interaction.channel.send(embed=embed)


# ==================================
# نظام الخبرة والمستويات
# ==================================

@bot.event
async def on_message(الرسالة):
    if الرسالة.author.bot or not الرسالة.guild:
        return

    with sqlite3.connect(DATABASE) as db:
        db.execute("""
            INSERT INTO الخبرة (
                معرّف_السيرفر,
                معرّف_العضو,
                النقاط,
                المستوى
            ) VALUES (?, ?, 5, 1)
            ON CONFLICT(معرّف_السيرفر, معرّف_العضو)
            DO UPDATE SET النقاط = النقاط + 5
        """, (الرسالة.guild.id, الرسالة.author.id))

        نتيجة = db.execute("""
            SELECT النقاط, المستوى
            FROM الخبرة
            WHERE معرّف_السيرفر = ?
              AND معرّف_العضو = ?
        """, (الرسالة.guild.id, الرسالة.author.id)).fetchone()

        النقاط, المستوى = نتيجة

        المستوى_الجديد = (النقاط // 100) + 1

        if المستوى_الجديد > المستوى:
            db.execute("""
                UPDATE الخبرة
                SET المستوى = ?
                WHERE معرّف_السيرفر = ?
                  AND معرّف_العضو = ?
            """, (
                المستوى_الجديد,
                الرسالة.guild.id,
                الرسالة.author.id
            ))

        db.commit()

    await bot.process_commands(الرسالة)


@bot.tree.command(
    name="مستواي",
    description="عرض مستواك ونقاط خبرتك"
)
async def مستواي(interaction: discord.Interaction):
    with sqlite3.connect(DATABASE) as db:
        نتيجة = db.execute("""
            SELECT النقاط, المستوى
            FROM الخبرة
            WHERE معرّف_السيرفر = ?
              AND معرّف_العضو = ?
        """, (interaction.guild_id, interaction.user.id)).fetchone()

    if نتيجة is None:
        النقاط, المستوى = 0, 1
    else:
        النقاط, المستوى = نتيجة

    await interaction.response.send_message(
        f"🏆 مستواك: {المستوى}\n"
        f"✨ نقاط الخبرة: {النقاط}",
        ephemeral=True
    )


# ==================================
# نظام الاقتصاد
# ==================================

@bot.tree.command(
    name="رصيدي",
    description="عرض رصيدك المالي"
)
async def رصيدي(interaction: discord.Interaction):
    with sqlite3.connect(DATABASE) as db:
        db.execute("""
            INSERT OR IGNORE INTO الأرصدة (
                معرّف_السيرفر,
                معرّف_العضو,
                الرصيد
            ) VALUES (?, ?, 0)
        """, (interaction.guild_id, interaction.user.id))

        نتيجة = db.execute("""
            SELECT الرصيد FROM الأرصدة
            WHERE معرّف_السيرفر = ?
              AND معرّف_العضو = ?
        """, (interaction.guild_id, interaction.user.id)).fetchone()

        db.commit()

    await interaction.response.send_message(
        f"💰 رصيدك الحالي: {نتيجة[0]} عملة",
        ephemeral=True
    )


# ==================================
# أوامر الإدارة
# ==================================

@bot.tree.command(
    name="طرد",
    description="طرد عضو من السيرفر"
)
@app_commands.checks.has_permissions(kick_members=True)
async def طرد(
    interaction: discord.Interaction,
    العضو: discord.Member,
    السبب: str = "لم يتم تحديد سبب"
):
    if العضو.id == interaction.user.id:
        await interaction.response.send_message(
            "لا يمكنك طرد نفسك.",
            ephemeral=True
        )
        return

    if العضو.top_role >= interaction.user.top_role:
        await interaction.response.send_message(
            "لا يمكنك طرد عضو رتبته مساوية لرتبتك أو أعلى منها.",
            ephemeral=True
        )
        return

    try:
        await العضو.kick(
            reason=f"{السبب} | بواسطة {interaction.user}"
        )

        await interaction.response.send_message(
            f"تم طرد {العضو.mention}.\nالسبب: {السبب}"
        )

        await تسجيل_عملية(
            interaction.guild,
            f"طرد {العضو} بواسطة {interaction.user}. السبب: {السبب}"
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "البوت لا يملك صلاحية طرد هذا العضو.",
            ephemeral=True
        )


@bot.tree.command(
    name="اسكت",
    description="إسكات عضو لمدة محددة بالدقائق"
)
@app_commands.checks.has_permissions(moderate_members=True)
async def اسكت(
    interaction: discord.Interaction,
    العضو: discord.Member,
    الدقائق: app_commands.Range[int, 1, 40320],
    السبب: str = "لم يتم تحديد سبب"
):
    if العضو.top_role >= interaction.user.top_role:
        await interaction.response.send_message(
            "لا يمكنك معاقبة عضو رتبته مساوية لرتبتك أو أعلى منها.",
            ephemeral=True
        )
        return

    try:
        await العضو.timeout(
            discord.utils.utcnow() + discord.timedelta(
                minutes=الدقائق
            ),
            reason=السبب
        )

        await interaction.response.send_message(
            f"تم إسكات {العضو.mention} لمدة {الدقائق} دقيقة.\n"
            f"السبب: {السبب}"
        )

        await تسجيل_عملية(
            interaction.guild,
            f"إسكات {العضو} لمدة {الدقائق} دقيقة. السبب: {السبب}"
        )

    except (discord.Forbidden, discord.HTTPException):
        await interaction.response.send_message(
            "تعذر إسكات العضو. تحقق من صلاحيات البوت والرتب.",
            ephemeral=True
        )


@bot.tree.command(
    name="فك_السكوت",
    description="إزالة الإسكات عن عضو"
)
@app_commands.checks.has_permissions(moderate_members=True)
async def فك_السكوت(
    interaction: discord.Interaction,
    العضو: discord.Member
):
    try:
        await العضو.timeout(None)

        await interaction.response.send_message(
            f"تم فك الإسكات عن {العضو.mention}."
        )

    except discord.HTTPException:
        await interaction.response.send_message(
            "تعذر فك الإسكات.",
            ephemeral=True
        )


@bot.tree.command(
    name="حظر",
    description="حظر عضو من السيرفر"
)
@app_commands.checks.has_permissions(ban_members=True)
async def حظر(
    interaction: discord.Interaction,
    العضو: discord.Member,
    السبب: str = "لم يتم تحديد سبب"
):
    if العضو.id == interaction.user.id:
        await interaction.response.send_message(
            "لا يمكنك حظر نفسك.",
            ephemeral=True
        )
        return

    if العضو.top_role >= interaction.user.top_role:
        await interaction.response.send_message(
            "لا يمكنك حظر عضو رتبته مساوية لرتبتك أو أعلى منها.",
            ephemeral=True
        )
        return

    try:
        await العضو.ban(
            reason=f"{السبب} | بواسطة {interaction.user}"
        )

        await interaction.response.send_message(
            f"🚫 تم حظر {العضو} من السيرفر.\n"
            f"السبب: {السبب}\n"
            "السيرفر ما وقف على أحد."
        )

        await تسجيل_عملية(
            interaction.guild,
            f"حظر {العضو} بواسطة {interaction.user}. السبب: {السبب}"
        )

    except discord.HTTPException:
        await interaction.response.send_message(
            "تعذر حظر العضو.",
            ephemeral=True
        )


# ==================================
# معلومات السيرفر
# ==================================

@bot.tree.command(
    name="معلومات_السيرفر",
    description="عرض معلومات السيرفر"
)
async def معلومات_السيرفر(interaction: discord.Interaction):
    السيرفر = interaction.guild

    embed = discord.Embed(
        title=f"معلومات {السيرفر.name}",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="عدد الأعضاء",
        value=str(sيرفر_عدد_الأعضاء(السيرفر)),
        inline=True
    )

    embed.add_field(
        name="عدد القنوات",
        value=str(len(السيرفر.channels)),
        inline=True
    )

    embed.add_field(
        name="عدد الرتب",
        value=str(len(السيرفر.roles)),
        inline=True
    )

    await interaction.response.send_message(embed=embed)


def سيرفر_عدد_الأعضاء(السيرفر):
    return السيرفر.member_count or len(السيرفر.members)


# ==================================
# تشغيل البرنامج
# ==================================

if not TOKEN:
    raise RuntimeError(
        "أضف توكن البوت في متغير البيئة DISCORD_TOKEN."
    )

bot.run(TOKEN)
