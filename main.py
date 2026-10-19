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

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "bot_data.json"
BANK_DATA_FILE = "bank_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {DATA_FILE}: {e}")
    return {
        "menus": {},
        "staff_stats": {},
        "active_tickets": {},
        "kashf_channel_id": None
    }

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving {DATA_FILE}: {e}")

db_data = load_data()

# ----------------- دوال وأنظمة البنك المستقلة -----------------
def load_bank_data():
    if os.path.exists(BANK_DATA_FILE):
        try:
            with open(BANK_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "users": {},
        "organizations": {},
        "settings": {
            "games_rewards": {
                "فك الشفرة": {"سهل": 100, "متوسط": 250, "صعب": 500},
                "الكنز": {"سهل": 150, "متوسط": 300, "صعب": 600},
                "تحدي الذكاء": {"سهل": 200, "متوسط": 400, "صعب": 800}
            }
        },
        "logs": []
    }

def save_bank_data(data):
    try:
        with open(BANK_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving bank data: {e}")

bank_db = load_bank_data()

class AdminBankPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="➕ إنشاء حساب مؤسسة", style=discord.ButtonStyle.success, custom_id="admin_create_org", row=0)
    async def create_org_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ هذه اللوحة مخصصة لمدير البنك فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(AdminCreateOrgModal())

    @discord.ui.button(label="💰 تعديل رصيد (إضافة/خصم)", style=discord.ButtonStyle.primary, custom_id="admin_modify_bal", row=0)
    async def modify_bal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ هذه اللوحة مخصصة لمدير البنك فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(AdminModifyBalanceModal())

    @discord.ui.button(label="🎮 تعديل مكافآت الألعاب", style=discord.ButtonStyle.secondary, custom_id="admin_edit_rewards", row=1)
    async def edit_rewards_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ هذه اللوحة مخصصة لمدير البنك فقط.", ephemeral=True)
            return
        await interaction.response.send_message("⚙️ قائمة إدارة ومكافآت الألعاب قيد التحديث المستمر.", ephemeral=True)

class AdminCreateOrgModal(discord.ui.Modal, title="🏛️ إنشاء حساب مؤسسة جديد"):
    org_name = discord.ui.TextInput(label="اسم المؤسسة", placeholder="مثال: الشرطة، المرور...", required=True)
    manager_name = discord.ui.TextInput(label="آيدي أو اسم القائد المسؤول", placeholder="اكتب آيدي العضو أو اسمه بدقة...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.org_name.value.strip()
        mgr_input = self.manager_name.value.strip()

        if name in bank_db["organizations"]:
            await interaction.response.send_message(f"❌ حساب المؤسسة **{name}** موجود مسبقاً!", ephemeral=True)
            return

        target_member = None
        for m in interaction.guild.members:
            if mgr_input in m.name or mgr_input in m.display_name or str(m.id) == mgr_input:
                target_member = m
                break

        if not target_member:
            await interaction.response.send_message(f"❌ لم يتم العثور على العضو المسؤول المذكور: `{mgr_input}`", ephemeral=True)
            return

        bank_db["organizations"][name] = {
            "manager_id": target_member.id,
            "balance": 5000,
            "history": []
        }
        save_bank_data(bank_db)
        await interaction.response.send_message(f"✅ تم بنجاح إنشاء حساب مؤسسة **{name}** وتعيين {target_member.mention} مسؤولاً عنها برصيد أساسي 5000!", ephemeral=True)

class AdminModifyBalanceModal(discord.ui.Modal, title="💰 تعديل رصيد حساب أو مؤسسة"):
    target_name = discord.ui.TextInput(label="اسم المؤسسة أو العضو", placeholder="اسم المؤسسة أو اسم/آيدي العضو...", required=True)
    amount = discord.ui.TextInput(label="المبلغ (استخدم سالب للخصم مثل -500)", placeholder="مثال: 1000 أو -500", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.target_name.value.strip()
        try:
            amt = int(self.amount.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ يرجى إدخال رقم صحيح للمبلغ.", ephemeral=True)
            return

        if name in bank_db["organizations"]:
            bank_db["organizations"][name]["balance"] += amt
            save_bank_data(bank_db)
            await interaction.response.send_message(f"✅ تم تعديل رصيد مؤسسة **{name}** بمقدار ({amt}). الرصيد الجديد: `{bank_db['organizations'][name]['balance']}`", ephemeral=True)
            return

        target_member = None
        for m in interaction.guild.members:
            if name in m.name or name in m.display_name or str(m.id) == name:
                target_member = m
                break

        if target_member:
            uid = str(target_member.id)
            udata = bank_db["users"].setdefault(uid, {"balance": 1000, "history": []})
            udata["balance"] += amt
            save_bank_data(bank_db)
            await interaction.response.send_message(f"✅ تم تعديل رصيد العضو {target_member.mention} بمقدار ({amt}). الرصيد الجديد: `{udata['balance']}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ لم يتم العثور على الحساب المذكور: `{name}`", ephemeral=True)

class InvestmentGamesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎮 الألعاب", style=discord.ButtonStyle.primary, custom_id="bank_games_btn")
    async def games_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎯 اختر اللعبة التي تريد خوضها:", view=GameSelectView(), ephemeral=True)

    @discord.ui.button(label="📈 خيارات الاستثمار", style=discord.ButtonStyle.success, custom_id="bank_invest_btn")
    async def invest_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📈 خيارات الاستثمار البنكي",
            description="اختر باقة الاستثمار المناسبة:\n\n1️⃣ **آمن (عائد 10%)** - 500\n2️⃣ **متوسط (عائد 25%)** - 1500\n3️⃣ **عالي المخاطر (عائد 50%)** - 3000",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, view=InvestOptionsView(), ephemeral=True)

class GameSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="اختر اللعبة...",
        options=[
            discord.SelectOption(label="فك الشفرة", description="ابحث عن الشفرة الصحيحة", emoji="🔐"),
            discord.SelectOption(label="الكنز", description="اختر الصندوق الصحيح", emoji="💰"),
            discord.SelectOption(label="تحدي الذكاء", description="أجب عن السؤال المالي", emoji="🧠")
        ],
        custom_id="select_game_menu"
    )
    async def select_game(self, interaction: discord.Interaction, select: discord.ui.Select):
        game_name = select.values[0]
        await interaction.response.send_message(f"🎮 اخترت لعبة **{game_name}**. حدد مستوى الصعوبة:", view=GameDifficultyView(game_name), ephemeral=True)

class GameDifficultyView(discord.ui.View):
    def __init__(self, game_name):
        super().__init__(timeout=None)
        self.game_name = game_name

    @discord.ui.button(label="سهل", style=discord.ButtonStyle.success, custom_id="diff_easy")
    async def easy_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_game(interaction, "سهل")

    @discord.ui.button(label="متوسط", style=discord.ButtonStyle.primary, custom_id="diff_medium")
    async def med_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_game(interaction, "متوسط")

    @discord.ui.button(label="صعب", style=discord.ButtonStyle.danger, custom_id="diff_hard")
    async def hard_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_game(interaction, "صعب")

    async def play_game(self, interaction: discord.Interaction, difficulty: str):
        rewards = bank_db["settings"]["games_rewards"].get(self.game_name, {})
        reward_amount = rewards.get(difficulty, 100)
        won = random.choice([True, False])
        user_id = str(interaction.user.id)
        user_data = bank_db["users"].setdefault(user_id, {"balance": 1000, "history": []})

        if won:
            user_data["balance"] += reward_amount
            user_data["history"].append(f"ربح {reward_amount} من لعبة {self.game_name} ({difficulty})")
            save_bank_data(bank_db)
            await interaction.response.send_message(f"🎉 مبروك! فزت في لعبة **{self.game_name}** ({difficulty}) وحصلت على **{reward_amount}**!", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ لم تحالفك الحظ في لعبة **{self.game_name}** ({difficulty}). حاول مرة أخرى!", ephemeral=True)

class InvestOptionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="باقة 500 (آمن)", style=discord.ButtonStyle.secondary, custom_id="inv_500")
    async def inv_500(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_investment(interaction, 500, 0.1, 1.0)

    @discord.ui.button(label="باقة 1500 (متوسط)", style=discord.ButtonStyle.primary, custom_id="inv_1500")
    async def inv_1500(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_investment(interaction, 1500, 0.25, 0.8)

    @discord.ui.button(label="باقة 3000 (مخاطرة)", style=discord.ButtonStyle.danger, custom_id="inv_3000")
    async def inv_3000(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_investment(interaction, 3000, 0.5, 0.5)

    async def process_investment(self, interaction: discord.Interaction, cost: int, profit_rate: float, win_chance: float):
        user_id = str(interaction.user.id)
        user_data = bank_db["users"].setdefault(user_id, {"balance": 1000, "history": []})

        if user_data["balance"] < cost:
            await interaction.response.send_message(f"❌ رصيدك ({user_data['balance']}) لا يكفي (المطلوب: {cost})!", ephemeral=True)
            return

        user_data["balance"] -= cost
        success = random.random() <= win_chance
        if success:
            profit = int(cost * profit_rate)
            total_back = cost + profit
            user_data["balance"] += total_back
            user_data["history"].append(f"استثمار ناجح: ربح {profit}")
            save_bank_data(bank_db)
            await interaction.response.send_message(f"📈 نجح الاستثمار! إجمالي المبلغ المضاف: **{total_back}**", ephemeral=True)
        else:
            user_data["history"].append(f"استثمار خاسر: فقدان {cost}")
            save_bank_data(bank_db)
            await interaction.response.send_message(f"📉 خسر الاستثمار وتم خصم **{cost}** من حسابك.", ephemeral=True)

class BankMainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💳 حسابي", style=discord.ButtonStyle.primary, custom_id="bank_my_account")
    async def my_account(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        user_data = bank_db["users"].setdefault(user_id, {"balance": 1000, "history": []})
        history_text = "\n".join(user_data["history"][-5:]) if user_data["history"] else "لا توجد عمليات سابقة."
        
        embed = discord.Embed(
            title=f"💳 الحساب البنكي لـ {interaction.user.display_name}",
            description=f"💰 **الرصيد الحالي:** `{user_data['balance']}`\n\n📜 **آخر العمليات:**\n{history_text}",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="💸 تحويل الأموال", style=discord.ButtonStyle.success, custom_id="bank_transfer")
    async def transfer_money(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TransferModal())

    @discord.ui.button(label="📈 الاستثمار والألعاب", style=discord.ButtonStyle.secondary, custom_id="bank_invest_games")
    async def invest_games(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📊 اختر القسم الذي ترغب به:", view=InvestmentGamesView(), ephemeral=True)

    @discord.ui.button(label="🏆 المتصدرون", style=discord.ButtonStyle.secondary, custom_id="bank_leaderboard")
    async def leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        sorted_users = sorted(bank_db["users"].items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:5]
        sorted_orgs = sorted(bank_db["organizations"].items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:5]

        desc = "🏆 **أغنى الأفراد:**\n"
        for idx, (uid, udata) in enumerate(sorted_users):
            member = interaction.guild.get_member(int(uid))
            name = member.mention if member else f"مستخدم ({uid})"
            desc += f"#{idx+1} | {name} - الرصيد: `{udata.get('balance', 0)}`\n"

        desc += "\n🏛️ **أرصدة المؤسسات:**\n"
        if not sorted_orgs:
            desc += "لا توجد مؤسسات مسجلة.\n"
        else:
            for idx, (org_name, odata) in enumerate(sorted_orgs):
                desc += f"#{idx+1} | **{org_name}** - الرصيد: `{odata.get('balance', 0)}`\n"

        embed = discord.Embed(title="📊 لوحة المتصدرين", description=desc, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🏛️ حسابات المؤسسات", style=discord.ButtonStyle.secondary, custom_id="bank_orgs")
    async def organizations_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        my_orgs = [name for name, data in bank_db["organizations"].items() if data.get("manager_id") == user_id]
        
        desc = "🏛️ **قائمة حسابات المؤسسات التي تديرها:**\n"
        if not my_orgs and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ ليس لديك أي مؤسسة مسجلة باسمك.", ephemeral=True)
            return

        for org_name in my_orgs:
            org_data = bank_db["organizations"][org_name]
            desc += f"\n📌 **{org_name}**\n   └ 💰 الرصيد: `{org_data['balance']}`\n"

        if interaction.user.guild_permissions.administrator:
            desc += "\n*(أنت مدير عام ولديُك صلاحيات الإدارة الكاملة)*"

        embed = discord.Embed(title="إدارة حسابات المؤسسات", description=desc, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class TransferModal(discord.ui.Modal, title="💸 تحويل الأموال"):
    recipient_name = discord.ui.TextInput(label="اسم المستلم (عضو أو مؤسسة)", placeholder="اكتب اسم الحساب أو العضو...", required=True)
    amount = discord.ui.TextInput(label="المبلغ", placeholder="مثال: 500", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amt = int(self.amount.value.strip())
            if amt <= 0:
                await interaction.response.send_message("❌ المبلغ يجب أن يكون أكبر من صفر.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ أدخل رقماً صحيحاً للمبلغ.", ephemeral=True)
            return

        sender_id = str(interaction.user.id)
        target_name = self.recipient_name.value.strip()
        sender_data = bank_db["users"].setdefault(sender_id, {"balance": 1000, "history": []})

        if sender_data["balance"] < amt:
            await interaction.response.send_message("❌ رصيدك الشخصي لا يكفي!", ephemeral=True)
            return

        if target_name in bank_db["organizations"]:
            sender_data["balance"] -= amt
            bank_db["organizations"][target_name]["balance"] += amt
            sender_data["history"].append(f"تحويل مبلغ {amt} إلى مؤسسة {target_name}")
            save_bank_data(bank_db)
            await interaction.response.send_message(f"✅ تم تحويل **{amt}** إلى حساب المؤسسة **{target_name}**!", ephemeral=True)
        else:
            target_user = None
            for member in interaction.guild.members:
                if target_name in member.name or target_name in member.display_name or str(member.id) == target_name:
                    target_user = member
                    break

            if not target_user:
                await interaction.response.send_message(f"❌ لم يتم العثور على العضو: `{target_name}`", ephemeral=True)
                return

            if target_user.id == interaction.user.id:
                await interaction.response.send_message("❌ لا يمكنك التحويل لنفسك!", ephemeral=True)
                return

            target_id = str(target_user.id)
            target_data = bank_db["users"].setdefault(target_id, {"balance": 1000, "history": []})

            sender_data["balance"] -= amt
            target_data["balance"] += amt
            sender_data["history"].append(f"تحويل مبلغ {amt} إلى العضو {target_user.display_name}")
            save_bank_data(bank_db)

            await interaction.response.send_message(f"✅ تم تحويل **{amt}** إلى العضو {target_user.mention}!", ephemeral=True)
# -------------------------------------------------------------

class RatingView(discord.ui.View):
    def __init__(self, staff_id, ticket_channel, ticket_owner_id):
        super().__init__(timeout=None)
        self.staff_id = str(staff_id)
        self.ticket_channel = ticket_channel
        self.ticket_owner_id = ticket_owner_id

    @discord.ui.select(
        placeholder="⭐ اختر تقييم الخدمة الإدارية...",
        custom_id="ticket_rating_select",
        options=[
            discord.SelectOption(label="⭐ 5 - ممتاز جداً", value="5", description="خدمة ممتازة وسريعة"),
            discord.SelectOption(label="⭐ 4 - جيد جداً", value="4", description="خدمة جيدة جداً"),
            discord.SelectOption(label="⭐ 3 - متوسط", value="3", description="خدمة مقبولة"),
            discord.SelectOption(label="⭐ 2 - سيئ", value="2", description="خدمة تحتاج تحسين"),
            discord.SelectOption(label="⭐ 1 - سيئ جداً", value="1", description="خدمة غير مرضية"),
        ]
    )
    async def select_rating(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.ticket_owner_id:
            await interaction.response.send_message("❌ تقييم الخدمة مخصص فقط للمواطن (صاحب التكت الأساسي)!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        rating = int(select.values[0])
        stats = db_data["staff_stats"].get(self.staff_id, {
            "tickets": 0, "total_stars": 0, "ratings_count": 0, "ratings_list": []
        })
        stats["total_stars"] += rating
        stats["ratings_count"] += 1
        if "ratings_list" not in stats:
            stats["ratings_list"] = []
        stats["ratings_list"].append(rating)

        db_data["staff_stats"][self.staff_id] = stats
        save_data(db_data)

        await interaction.followup.send("✅ شكرًا لك على تقديم تقييمك! جاري إغلاق التكت وحذفه...", ephemeral=True)
        await asyncio.sleep(2)
        try:
            db_data["active_tickets"].pop(str(self.ticket_channel.id), None)
            save_data(db_data)
            await self.ticket_channel.delete()
        except Exception:
            pass

class AddMemberSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="👥 اختر العضو الذي تريد إضافته للروم...",
        custom_id="add_member_select"
    )
    async def select_member(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        member = select.values[0]
        await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
        await interaction.response.send_message(f"✅ تم بنجاح إضافة {member.mention} إلى هذا التكت.", ephemeral=False)

class RemoveMemberSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="🚫 اختر العضو الذي تريد إزالته من الروم...",
        custom_id="remove_member_select"
    )
    async def select_member(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        member = select.values[0]
        ticket_info = db_data["active_tickets"].get(str(interaction.channel.id), {})
        owner_id = ticket_info.get("owner_id")
        
        if member.id == owner_id:
            await interaction.response.send_message("❌ لا يمكنك إزالة صاحب التكت الأساسي!", ephemeral=True)
            return

        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(f"✅ تم إزالة صلاحيات {member.mention} من هذا التكت.", ephemeral=False)

class TicketControlView(discord.ui.View):
    def __init__(self, menu_type="admin"):
        super().__init__(timeout=None)
        self.menu_type = menu_type

    @discord.ui.button(label="إضافة عضو ➕", style=discord.ButtonStyle.secondary, custom_id="add_member_btn")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_id = str(interaction.channel.id)
        ticket_info = db_data["active_tickets"].get(channel_id, {})
        claimed_staff_id = ticket_info.get("staff_id")
        allowed_role_ids = ticket_info.get("allowed_role_ids", [])

        is_admin = interaction.user.guild_permissions.administrator
        is_staff = interaction.user.id == claimed_staff_id
        has_allowed_role = any(r.id in [int(rid) for rid in allowed_role_ids] for r in interaction.user.roles)

        if not (is_admin or is_staff or has_allowed_role):
            await interaction.response.send_message("❌ هذا الخيار مخصص للإدارة المعتمدة فقط.", ephemeral=True)
            return

        await interaction.response.send_message("اختر العضو المراد إضافته من القائمة أدناه:", view=AddMemberSelectView(), ephemeral=True)

    @discord.ui.button(label="إزالة عضو ➖", style=discord.ButtonStyle.secondary, custom_id="remove_member_btn")
    async def remove_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_id = str(interaction.channel.id)
        ticket_info = db_data["active_tickets"].get(channel_id, {})
        claimed_staff_id = ticket_info.get("staff_id")
        allowed_role_ids = ticket_info.get("allowed_role_ids", [])

        is_admin = interaction.user.guild_permissions.administrator
        is_staff = interaction.user.id == claimed_staff_id
        has_allowed_role = any(r.id in [int(rid) for rid in allowed_role_ids] for r in interaction.user.roles)

        if not (is_admin or is_staff or has_allowed_role):
            await interaction.response.send_message("❌ هذا الخيار مخصص للإدارة المعتمدة فقط.", ephemeral=True)
            return

        await interaction.response.send_message("اختر العضو المراد إزالته من القائمة أدناه:", view=RemoveMemberSelectView(), ephemeral=True)

    @discord.ui.button(label="إغلاق التكت 🔒", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_id = str(interaction.channel.id)
        ticket_info = db_data["active_tickets"].get(channel_id, {})
        claimed_staff_id = ticket_info.get("staff_id")
        owner_id = ticket_info.get("owner_id")
        menu_type = ticket_info.get("menu_type", self.menu_type)
        allowed_role_ids = ticket_info.get("allowed_role_ids", [])

        is_admin = interaction.user.guild_permissions.administrator
        is_staff = (claimed_staff_id and interaction.user.id == claimed_staff_id)
        has_allowed_role = any(r.id in [int(rid) for rid in allowed_role_ids] for r in interaction.user.roles)

        if not (is_admin or is_staff or has_allowed_role):
            await interaction.response.send_message("❌ لا يمكنك إغلاق التكت! خيار الإغلاق مخصص للإدارة المعتمدة فقط.", ephemeral=True)
            return

        if menu_type == "admin" and claimed_staff_id:
            view = RatingView(staff_id=claimed_staff_id, ticket_channel=interaction.channel, ticket_owner_id=owner_id)
            await interaction.response.send_message("⭐ يرجى تقييم خدمة الإداري قبل إغلاق التكت:", view=view)
        else:
            await interaction.response.send_message("🔒 جاري إغلاق التكت وحذفه نهائياً...")
            await asyncio.sleep(2)
            try:
                db_data["active_tickets"].pop(channel_id, None)
                save_data(db_data)
                await interaction.channel.delete()
            except Exception:
                pass

class InteractiveTicketButton(discord.ui.Button):
    def __init__(self, label, emoji, button_text, menu_type, allowed_role_ids, observer_role_ids, btn_index=0, msg_id=""):
        cid = f"dyn_btn_{msg_id}_{btn_index}" if msg_id else f"dyn_btn_{btn_index}"
        
        parsed_emoji = None
        if emoji and isinstance(emoji, str) and emoji.strip():
            e_str = emoji.strip()
            if e_str.startswith("<a:") or e_str.startswith("<:"):
                try:
                    parsed_emoji = discord.PartialEmoji.from_str(e_str)
                except Exception:
                    parsed_emoji = None
            else:
                parsed_emoji = e_str
        
        super().__init__(label=label, emoji=parsed_emoji, style=discord.ButtonStyle.primary, custom_id=cid)
        self.button_text = button_text
        self.menu_type = menu_type
        self.allowed_role_ids = allowed_role_ids
        self.observer_role_ids = observer_role_ids
        self.msg_id = str(msg_id)
        self.btn_index = btn_index

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id

        msg_id_target = self.msg_id
        if (not msg_id_target or msg_id_target == "") and interaction.message:
            msg_id_target = str(interaction.message.id)

        menu_info = db_data["menus"].get(msg_id_target, {})
        buttons_list = menu_info.get("buttons", [])
        
        btn_data = None
        if 0 <= self.btn_index < len(buttons_list):
            btn_data = buttons_list[self.btn_index]
            
        btn_text = btn_data.get("text", "") if btn_data else self.button_text
        allowed_roles = btn_data.get("allowed_role_ids", []) if btn_data else self.allowed_role_ids
        observer_roles = btn_data.get("observer_role_ids", []) if btn_data else self.observer_role_ids
        current_menu_type = menu_info.get("menu_type", self.menu_type)

        for ticket_id, ticket_data in list(db_data["active_tickets"].items()):
            if ticket_data.get("owner_id") == user_id:
                existing_channel = interaction.guild.get_channel(int(ticket_id))
                if existing_channel:
                    await interaction.followup.send(
                        f"❌ لديك تكت مفتوح بالفعل: {existing_channel.mention}\nيرجى إغلاق تكتك الحالي قبل فتح تكت جديد.",
                        ephemeral=True
                    )
                    return
                else:
                    db_data["active_tickets"].pop(ticket_id, None)
                    save_data(db_data)

        guild = interaction.guild
        category = interaction.channel.category

        ticket_count = len(db_data["active_tickets"]) + 1
        clean_title = self.label.replace(" ", "-") if self.label else "ticket"
        channel_name = f"{clean_title}-{ticket_count}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        
        all_roles_to_add = set([int(r) for r in allowed_roles + observer_roles])
        for role_id in all_roles_to_add:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites
            )
        except Exception as e:
            await interaction.followup.send(f"❌ حدث خطأ أثناء إنشاء روم التكت: {e}", ephemeral=True)
            return

        db_data["active_tickets"][str(ticket_channel.id)] = {
            "owner_id": interaction.user.id,
            "staff_id": None,
            "menu_type": current_menu_type,
            "button_label": self.label,
            "allowed_role_ids": [int(r) for r in allowed_roles],
            "observer_role_ids": [int(r) for r in observer_roles]
        }
        save_data(db_data)

        desc = btn_text if (btn_text and btn_text.strip()) else "📌 الرجاء توضيح طلبك وشرحه بالتفصيل. سيتم استلام التكت تلقائياً فور أول رد من الإداري."

        embed = discord.Embed(
            title=f"🎟️ مرحباً بك {interaction.user.display_name} في {channel_name}",
            description=desc[:4000],
            color=discord.Color.gold()
        )
        view = TicketControlView(current_menu_type)
        
        await ticket_channel.send(embed=embed, view=view)
        await interaction.followup.send(f"✅ تم إنشاء التكت بنجاح: {ticket_channel.mention}", ephemeral=True)

class DynamicMenuView(discord.ui.View):
    def __init__(self, buttons_list, menu_type, msg_id=""):
        super().__init__(timeout=None)
        for idx, btn in enumerate(buttons_list):
            emoji_val = btn.get("emoji")
            if emoji_val and not str(emoji_val).strip():
                emoji_val = None

            try:
                self.add_item(InteractiveTicketButton(
                    label=btn.get("label", "فتح تكت"),
                    emoji=emoji_val,
                    button_text=btn.get("text", ""),
                    menu_type=menu_type,
                    allowed_role_ids=btn.get("allowed_role_ids", []),
                    observer_role_ids=btn.get("observer_role_ids", []),
                    btn_index=idx,
                    msg_id=str(msg_id)
                ))
            except Exception:
                self.add_item(InteractiveTicketButton(
                    label=btn.get("label", "فتح تكت"),
                    emoji=None,
                    button_text=btn.get("text", ""),
                    menu_type=menu_type,
                    allowed_role_ids=btn.get("allowed_role_ids", []),
                    observer_role_ids=btn.get("observer_role_ids", []),
                    btn_index=idx,
                    msg_id=str(msg_id)
                ))

class AddButtonSimpleModal(discord.ui.Modal, title="➕ إضافة زر جديد"):
    btn_label = discord.ui.TextInput(label="عنوان الزر (اسم الزر)", placeholder="مثال: تقديم شرطة", required=True)
    btn_emoji = discord.ui.TextInput(label="إيموجي الزر (اختياري)", placeholder="مثال: 🚔 (أو اتركه فارغاً)", required=False)
    btn_text = discord.ui.TextInput(label="الرسالة والتعليمات داخل التكت", style=discord.TextStyle.paragraph, placeholder="أكتب الرسالة التي تظهر للعضو فور فتح هذا التكت...", required=False)

    def __init__(self, message_id):
        super().__init__()
        self.message_id = str(message_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            menu_info = db_data["menus"].get(self.message_id, {})
            buttons = menu_info.get("buttons", [])
            
            emoji_val = self.btn_emoji.value.strip() if self.btn_emoji.value and self.btn_emoji.value.strip() else None
            
            buttons.append({
                "label": self.btn_label.value.strip(),
                "emoji": emoji_val,
                "text": self.btn_text.value.strip() if self.btn_text.value else "",
                "allowed_role_ids": [],
                "observer_role_ids": []
            })
            menu_info["buttons"] = buttons
            db_data["menus"][self.message_id] = menu_info
            save_data(db_data)
            
            success_update, err_msg = await update_menu_message(interaction.guild, interaction.channel, self.message_id)
            if success_update:
                await interaction.followup.send("✅ تم إضافة الزر بنجاح ونزل في المنيو فوراً!", ephemeral=True)
            else:
                await interaction.followup.send(f"⚠️ تعذر تحديث المنيو تلقائياً بسبب: {err_msg}\nحاول الضغط على زر 'تحديث المنيو 🔄' الآن.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ حدث خطأ أثناء إضافة الزر: {e}", ephemeral=True)

class EditButtonCompleteView(discord.ui.View):
    def __init__(self, message_id, button_index, button_data):
        super().__init__(timeout=None)
        self.message_id = str(message_id)
        self.button_index = button_index
        self.button_data = button_data

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="🛡️ حدد/عدل رتب الاستلام لهذا الزر...",
        min_values=0,
        max_values=10,
        custom_id="edit_allowed_roles_select",
        row=0
    )
    async def select_allowed(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        await interaction.response.defer(ephemeral=True)
        self.button_data["allowed_role_ids"] = [r.id for r in select.values]
        await self.save_and_update(interaction.guild, interaction.channel)
        await interaction.followup.send(f"✅ تم تحديث رتب الاستلام لهذا الزر ({len(select.values)} رتبة) وتحديث المنيو بنجاح!", ephemeral=True)

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="👀 حدد/عدل رتب الاطلاع لهذا الزر (اختياري)...",
        min_values=0,
        max_values=10,
        custom_id="edit_observer_roles_select",
        row=1
    )
    async def select_observer(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        await interaction.response.defer(ephemeral=True)
        self.button_data["observer_role_ids"] = [r.id for r in select.values]
        await self.save_and_update(interaction.guild, interaction.channel)
        await interaction.followup.send(f"✅ تم تحديث رتب الاطلاع لهذا الزر ({len(select.values)} رتبة) وتحديث المنيو بنجاح!", ephemeral=True)

    @discord.ui.button(label="📝 تعديل نص العنوان والإيموجي والرسالة", style=discord.ButtonStyle.primary, custom_id="edit_btn_text_details", row=2)
    async def edit_text_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditButtonTextModal(self.message_id, self.button_index, self.button_data))

    async def save_and_update(self, guild, channel):
        menu_info = db_data["menus"].get(self.message_id)
        if menu_info:
            buttons = menu_info.get("buttons", [])
            if 0 <= self.button_index < len(buttons):
                buttons[self.button_index] = self.button_data
                menu_info["buttons"] = buttons
                db_data["menus"][self.message_id] = menu_info
                save_data(db_data)
                await update_menu_message(guild, channel, self.message_id)

class EditButtonTextModal(discord.ui.Modal, title="📝 تعديل تفاصيل ومحتوى الزر"):
    def __init__(self, message_id, button_index, button_data):
        super().__init__()
        self.message_id = str(message_id)
        self.button_index = button_index
        self.button_data = button_data

        self.btn_label = discord.ui.TextInput(label="عنوان الزر", default=button_data.get("label", ""), required=True)
        self.btn_emoji = discord.ui.TextInput(label="إيموجي الزر", default=button_data.get("emoji", "") or "", required=False)
        self.btn_text = discord.ui.TextInput(label="الرسالة والتعليمات داخل التكت", style=discord.TextStyle.paragraph, default=button_data.get("text", "") or "", required=False)
        
        self.add_item(self.btn_label)
        self.add_item(self.btn_emoji)
        self.add_item(self.btn_text)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.button_data["label"] = self.btn_label.value.strip()
        self.button_data["emoji"] = self.btn_emoji.value.strip() if self.btn_emoji.value and self.btn_emoji.value.strip() else None
        self.button_data["text"] = self.btn_text.value.strip() if self.btn_text.value else ""

        menu_info = db_data["menus"].get(self.message_id)
        if menu_info:
            buttons = menu_info.get("buttons", [])
            if 0 <= self.button_index < len(buttons):
                buttons[self.button_index] = self.button_data
                menu_info["buttons"] = buttons
                db_data["menus"][self.message_id] = menu_info
                save_data(db_data)
                await update_menu_message(interaction.guild, interaction.channel, self.message_id)
                await interaction.followup.send("✅ تم تحديث تفاصيل الزر وتحديث المنيو تلقائياً بنجاح!", ephemeral=True)

class MenuControlPanelView(discord.ui.View):
    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.message_id = str(message_id)

    @discord.ui.button(label="تعديل العنوان 📝", style=discord.ButtonStyle.primary, custom_id="panel_edit_title", row=0)
    async def edit_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditTitleModal(self.message_id))

    @discord.ui.button(label="تعديل الوصف 📄", style=discord.ButtonStyle.primary, custom_id="panel_edit_desc", row=0)
    async def edit_desc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditDescriptionModal(self.message_id))

    @discord.ui.button(label="إضافة زر ➕", style=discord.ButtonStyle.success, custom_id="panel_add_btn", row=1)
    async def add_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddButtonSimpleModal(self.message_id))

    @discord.ui.button(label="تعديل زر ✏️", style=discord.ButtonStyle.secondary, custom_id="panel_edit_btn", row=1)
    async def edit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        menu_info = db_data["menus"].get(self.message_id, {})
        buttons = menu_info.get("buttons", [])
        if not buttons:
            await interaction.response.send_message("❌ لا توجد أزرار لتعديلها حالياً.", ephemeral=True)
            return
        await interaction.response.send_message("اختر الزر الذي تريد تعديل إعداداته ورتبه ونصه:", view=EditButtonSelectView(self.message_id, buttons), ephemeral=True)

    @discord.ui.button(label="حذف زر 🗑️", style=discord.ButtonStyle.danger, custom_id="panel_delete_btn", row=1)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        menu_info = db_data["menus"].get(self.message_id, {})
        buttons = menu_info.get("buttons", [])
        if not buttons:
            await interaction.response.send_message("❌ لا توجد أزرار لحذفها.", ephemeral=True)
            return
        await interaction.response.send_message("اختر رقم الزر المُراد حذفه:", view=DeleteButtonView(self.message_id, buttons), ephemeral=True)

    @discord.ui.button(label="تحديث المنيو 🔄", style=discord.ButtonStyle.success, custom_id="panel_refresh_menu", row=2)
    async def refresh_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        success, err_msg = await update_menu_message(interaction.guild, interaction.channel, self.message_id)
        if success:
            await interaction.followup.send("✅ تم تحديث المنيو بنجاح ونزلت جميع الأزرار!", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ تعذر تحديث المنيو بسبب: {err_msg}", ephemeral=True)

class EditTitleModal(discord.ui.Modal, title="📝 تعديل العنوان"):
    new_title = discord.ui.TextInput(label="العنوان الجديد للمنيو", required=True)
    def __init__(self, message_id):
        super().__init__()
        self.message_id = str(message_id)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        menu_info = db_data["menus"].get(self.message_id, {})
        menu_info["title"] = self.new_title.value.strip()
        db_data["menus"][self.message_id] = menu_info
        save_data(db_data)
        await update_menu_message(interaction.guild, interaction.channel, self.message_id)
        await interaction.followup.send("✅ تم تعديل العنوان وتحديث المنيو بنجاح!", ephemeral=True)

class EditDescriptionModal(discord.ui.Modal, title="📄 تعديل الوصف"):
    new_desc = discord.ui.TextInput(label="الوصف الجديد للمنيو", style=discord.TextStyle.paragraph, required=True)
    def __init__(self, message_id):
        super().__init__()
        self.message_id = str(message_id)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        menu_info = db_data["menus"].get(self.message_id, {})
        desc_text = self.new_desc.value.strip()
        if len(desc_text) > 3900:
            desc_text = desc_text[:3900] + "\n\n...(تم قص الجزء الزائد لتجاوز الحد المسموح به في ديسكورد)"

        menu_info["description"] = desc_text
        db_data["menus"][self.message_id] = menu_info
        save_data(db_data)
        await update_menu_message(interaction.guild, interaction.channel, self.message_id)
        await interaction.followup.send("✅ تم تعديل الوصف وتحديث المنيو بنجاح!", ephemeral=True)

class DeleteButtonSelect(discord.ui.Select):
    def __init__(self, message_id, buttons):
        self.message_id = str(message_id)
        options = []
        for idx, b in enumerate(buttons):
            em = b.get("emoji")
            if em and not str(em).strip():
                em = None
            try:
                options.append(discord.SelectOption(label=f"زر رقم #{idx + 1}: {b['label']}", value=str(idx), emoji=em))
            except Exception:
                options.append(discord.SelectOption(label=f"زر رقم #{idx + 1}: {b['label']}", value=str(idx)))
                
        super().__init__(placeholder="اختر رقم الزر المُراد حذفه...", custom_id="delete_btn_select", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected_index = int(self.values[0])
        menu_info = db_data["menus"].get(self.message_id)
        if menu_info and "buttons" in menu_info:
            buttons = menu_info.get("buttons", [])
            if 0 <= selected_index < len(buttons):
                removed = buttons.pop(selected_index)
                menu_info["buttons"] = buttons
                db_data["menus"][self.message_id] = menu_info
                save_data(db_data)
                await update_menu_message(interaction.guild, interaction.channel, self.message_id)
                await interaction.followup.send(f"✅ تم حذف الزر ({removed['label']}) وتحديث المنيو بنجاح!", ephemeral=True)

class DeleteButtonView(discord.ui.View):
    def __init__(self, message_id, buttons):
        super().__init__(timeout=None)
        self.add_item(DeleteButtonSelect(message_id, buttons))

class EditButtonSelect(discord.ui.Select):
    def __init__(self, message_id, buttons):
        self.message_id = str(message_id)
        self.buttons = buttons
        options = []
        for idx, b in enumerate(buttons):
            em = b.get("emoji")
            if em and not str(em).strip():
                em = None
            try:
                options.append(discord.SelectOption(label=f"زر رقم #{idx + 1}: {b['label']}", value=str(idx), emoji=em))
            except Exception:
                options.append(discord.SelectOption(label=f"زر رقم #{idx + 1}: {b['label']}", value=str(idx)))

        super().__init__(placeholder="اختر رقم الزر المُراد تعديله...", custom_id="edit_btn_select", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        current_btn = self.buttons[selected_index]
        view = EditButtonCompleteView(self.message_id, selected_index, current_btn)
        await interaction.response.send_message("⚙️ **لوحة تعديل الزر الشاملة:**\nقم بتحديد/تعديل رتب الاستلام ورتب الاطلاع أو نصوص الزر من القوائم أدناه مباشرة:", view=view, ephemeral=True)

class EditButtonSelectView(discord.ui.View):
    def __init__(self, message_id, buttons):
        super().__init__(timeout=None)
        self.add_item(EditButtonSelect(message_id, buttons))

async def update_menu_message(guild, channel, message_id):
    msg_id_str = str(message_id)
    menu_info = db_data["menus"].get(msg_id_str, {})
    
    target_msg = None
    try:
        target_msg = await channel.fetch_message(int(message_id))
    except Exception:
        for ch in guild.text_channels:
            try:
                target_msg = await ch.fetch_message(int(message_id))
                if target_msg:
                    break
            except Exception:
                continue

    if not target_msg:
        return False, "لم يتم العثور على رسالة المنيو في القناة."

    raw_desc = menu_info.get("description", "مرحباً بك في مركز الدعم!")
    if len(raw_desc) > 3900:
        raw_desc = raw_desc[:3900] + "\n...(تم قص النص الزائد للالتزام بحدود ديسكورد)"

    embed = discord.Embed(
        title=menu_info.get("title", "مركز الدعم والمساعدة"),
        description=raw_desc,
        color=discord.Color.gold()
    )

    buttons_list = menu_info.get("buttons", [])
    
    view = None
    if buttons_list:
        try:
            view = DynamicMenuView(buttons_list, menu_info.get("menu_type", "admin"), msg_id_str)
            bot.add_view(view)
            await target_msg.edit(embed=embed, view=view)
            return True, None
        except Exception:
            for b in buttons_list:
                b["emoji"] = None
            menu_info["buttons"] = buttons_list
            db_data["menus"][msg_id_str] = menu_info
            save_data(db_data)
            
            view = DynamicMenuView(buttons_list, menu_info.get("menu_type", "admin"), msg_id_str)
            bot.add_view(view)
            
    try:
        await target_msg.edit(embed=embed, view=view)
        return True, None
    except Exception as e:
        print(f"Error editing menu message: {e}")
        return False, str(e)

@bot.tree.command(name="إنشاء_منيو", description="إنشاء منيو تفاعلي جديد")
@app_commands.describe(نوع_المنيو="نوع المنيو (إداري أو عصابات/تقديم)")
@app_commands.choices(نوع_المنيو=[
    app_commands.Choice(name="منيو إداري (يحتوي تقييم)", value="admin"),
    app_commands.Choice(name="منيو عصابات وتقديم (بدون تقييم)", value="normal")
])
async def create_menu(interaction: discord.Interaction, نوع_المنيو: app_commands.Choice[str]):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
        return

    default_title = "مركز الدعم والمساعدة | Support Center"
    default_desc = "مرحباً بك في مركز الدعم والخدمات! 👋\n\nيرجى اختيار القسم المناسب أدناه لفتح قناة خاصة بك."

    embed = discord.Embed(title=default_title, description=default_desc, color=discord.Color.gold())
    menu_msg = await interaction.channel.send(embed=embed)

    msg_id = str(menu_msg.id)
    db_data["menus"][msg_id] = {
        "title": default_title,
        "description": default_desc,
        "buttons": [],
        "menu_type": نوع_المنيو.value
    }
    save_data(db_data)

    panel_view = MenuControlPanelView(msg_id)
    bot.add_view(panel_view)
    
    await interaction.response.send_message(
        "🛠️ **لوحة التحكم بالمنيو (مخفية لك فقط):**\nاستخدم الأزرار بالأسفل لإضافة الأزرار ورتب الاستلاستلام والتعديل وسينزل المنيو فوراً بالقناة:",
        view=panel_view,
        ephemeral=True
    )

@bot.tree.command(name="تعديل_منيو", description="فتح لوحة التحكم والتعديل لمنيو قائم عبر آيدي الرسالة")
@app_commands.describe(آيدي_الرسالة="آيدي رسالة المنيو المراد تعديله")
async def edit_menu(interaction: discord.Interaction, آيدي_الرسالة: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
        return

    if آيدي_الرسالة not in db_data["menus"]:
        await interaction.response.send_message("❌ لم يتم العثور على منيو مسجل بهذا الآيدي.", ephemeral=True)
        return

    panel_view = MenuControlPanelView(آيدي_الرسالة)
    bot.add_view(panel_view)
    await interaction.response.send_message("🛠️ **لوحة التحكم والتعديل في المنيو:**", view=panel_view, ephemeral=True)

@bot.tree.command(name="تحديد_روم_الكشف", description="تحديد الروم المخصص لاستخدام أمر الكشف ومتصدرين الإدارة")
@app_commands.describe(الروم="اختر الروم المخصص لأوامر الكشف ومتصدرين الإدارة")
async def set_kashf_channel(interaction: discord.Interaction, الروم: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا تملك صلاحية.", ephemeral=True)
        return
    db_data["kashf_channel_id"] = الروم.id
    save_data(db_data)
    await interaction.response.send_message(f"✅ تم تحديد {الروم.mention} كروم مخصص لأوامر `!كشف` و `!المتصدرين` بنجاح!", ephemeral=True)

# ----------------- أوامر السلاش الجديدة للبنك -----------------
@bot.tree.command(name="البنك", description="فتح قائمة البنك الرئيسية للأرصدة والخدمات")
async def bank_main_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🏦 نظام البنك المالي المركزي",
        description="مرحباً بك في النظام البنكي المتكامل!\nاختر من الأزرار بالأسفل لإدارة حسابك، التحويل، الاستثمار، أو عرض المؤسسات:",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, view=BankMainView(), ephemeral=True)

@bot.tree.command(name="لوحة_المدير", description="[للمديرين فقط] فتح لوحة تحكم وإدارة البنك والمؤسسات والأرصدة")
async def admin_panel_cmd(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر مخصص لمدير البنك فقط.", ephemeral=True)
        return

    embed = discord.Embed(
        title="⚙️ لوحة تحكم مدير البنك المركزى",
        description="أهلاً بك يا مدير البنك.\nاختر الإجراء الذي ترغب بتنفيذه من الأزرار أدناه:",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed, view=AdminBankPanelView(), ephemeral=True)
# -------------------------------------------------------------

@bot.command(name="كشف")
async def kashf_prefix(ctx, member: discord.Member = None):
    kashf_chan_id = db_data.get("kashf_channel_id")
    if kashf_chan_id and ctx.channel.id != kashf_chan_id:
        try:
            await ctx.message.delete()
        except Exception:
            pass
        return

    target = member if member else ctx.author
    stats = db_data["staff_stats"].get(str(target.id), {
        "tickets": 0, "total_stars": 0, "ratings_count": 0, "ratings_list": []
    })

    tickets_count = stats.get("tickets", 0)
    total_stars = stats.get("total_stars", 0)
    ratings_count = stats.get("ratings_count", 0)
    ratings_list = stats.get("ratings_list", [])

    if ratings_list:
        avg_stars = round(total_stars / ratings_count, 1) if ratings_count > 0 else 0.0
        most_frequent_rating = f"{max(set(ratings_list), key=ratings_list.count)}/5"
    else:
        avg_stars = 0.0
        most_frequent_rating = "لا يوجد تقييمات"

    joined_date = target.joined_at
    if joined_date:
        now = datetime.now(timezone.utc)
        delta = now - joined_date
        days = delta.days
        years = days // 365
        months = (days % 365) // 30
        remaining_days = (days % 365) % 30
        
        duration_parts = []
        if years > 0:
            duration_parts.append(f"{years} سنة")
        if months > 0:
            duration_parts.append(f"{months} شهر")
        duration_parts.append(f"{remaining_days} يوم")
        joined_duration_str = "، ".join(duration_parts)
    else:
        joined_duration_str = "غير معروف"

    current_time_str = datetime.now().strftime("%Y-%m-%d | %I:%M %p")

    embed = discord.Embed(
        title="👑 تقرير أداء الإداري الشامل",
        description=(
            f"----------------------------------------\n"
            f"👤 **الإداري:** {target.mention} (`{target.display_name}`)\n"
            f"🏰 **السيرفر:** `{ctx.guild.name}`\n"
            f"⏳ **مدة تواجده بالسيرفر:** `{joined_duration_str}`\n\n"
            f"📊 **إجمالي التكتات المستلمة:** `{tickets_count} تكت`\n"
            f"⭐ **إجمالي النجوم:** `{total_stars} نجمة`\n"
            f"📈 **متوسط التقييم العام:** `{avg_stars} / 5`\n"
            f"🏆 **التقييم الأكثر تكراراً:** `⭐ {most_frequent_rating}`\n"
            f"🕒 **وقت الإصدار والتاريخ:** `{current_time_str}`\n"
            f"----------------------------------------"
        ),
        color=discord.Color.gold()
    )
    
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    await ctx.send(content=f"{target.mention}", embed=embed)

@bot.command(name="المتصدرين")
async def leaderboard_prefix(ctx):
    kashf_chan_id = db_data.get("kashf_channel_id")
    if kashf_chan_id and ctx.channel.id != kashf_chan_id:
        try:
            await ctx.message.delete()
        except Exception:
            pass
        return

    sorted_staff = sorted(db_data["staff_stats"].items(), key=lambda x: (x[1].get("tickets", 0), x[1].get("total_stars", 0)), reverse=True)
    
    current_time_str = datetime.now().strftime("%Y-%m-%d | %I:%M %p")
    
    embed = discord.Embed(
        title="🏆 لوحة متصدرين الإدارة واستلام التكتات",
        color=discord.Color.gold()
    )
    
    description = "----------------------------------------\n"
    medals = ["🥇", "🥈", "🥉", "🏅", "🏅", "🏅", "🏅", "🏅", "🏅", "🏅"]
    
    top_staff = sorted_staff[:10]
    if not top_staff:
        description += "لا توجد إحصائيات مسجلة حتى الآن.\n"
    else:
        for idx, (staff_id, stats) in enumerate(top_staff):
            member = ctx.guild.get_member(int(staff_id))
            name = member.mention if member else f"مستخدم ({staff_id})"
            tickets = stats.get("tickets", 0)
            stars = stats.get("total_stars", 0)
            medal = medals[idx] if idx < len(medals) else "🔹"
            description += f"{medal} **#{idx+1}** | {name}\n   └ 🎫 التكتات: `{tickets}` | ⭐ النجوم: `{stars}`\n\n"
            
    description += "----------------------------------------"
    embed.description = description
    embed.set_footer(text=f"وقت التحديث: {current_time_str}")
    
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    await ctx.send(embed=embed)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    channel_id = str(message.channel.id)
    if channel_id in db_data["active_tickets"]:
        ticket_info = db_data["active_tickets"][channel_id]

        if ticket_info.get("staff_id") is None:
            allowed_role_ids = [int(r) for r in ticket_info.get("allowed_role_ids", [])]
            is_staff = False

            author_role_ids = [r.id for r in message.author.roles]
            if any(role_id in author_role_ids for role_id in allowed_role_ids) or message.author.guild_permissions.administrator:
                is_staff = True

            if is_staff and message.author.id != ticket_info["owner_id"]:
                ticket_info["staff_id"] = message.author.id
                db_data["active_tickets"][channel_id] = ticket_info

                staff_id_str = str(message.author.id)
                stats = db_data["staff_stats"].get(staff_id_str, {
                    "tickets": 0, "total_stars": 0, "ratings_count": 0, "ratings_list": []
                })

                stats["tickets"] += 1
                db_data["staff_stats"][staff_id_str] = stats
                save_data(db_data)

                guild = message.guild
                for r_id in allowed_role_ids:
                    role = guild.get_role(r_id)
                    if role:
                        try:
                            await message.channel.set_permissions(role, read_messages=False)
                        except Exception:
                            pass

                try:
                    await message.channel.set_permissions(message.author, read_messages=True, send_messages=True)
                except Exception:
                    pass

                await message.channel.send(embed=discord.Embed(
                    description=f"✅ **تم الاستلام تلقائياً بواسطة:** {message.author.mention}\n🔒 تم قفل التكت ومنع باقي الإداريين.",
                    color=discord.Color.green()
                ))

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.event
async def on_ready():
    bot.add_view(TicketControlView())
    for msg_id, menu_data in db_data.get("menus", {}).items():
        bot.add_view(MenuControlPanelView(str(msg_id)))
        buttons = menu_data.get("buttons", [])
        if buttons:
            try:
                bot.add_view(DynamicMenuView(buttons, menu_data.get("menu_type", "admin"), str(msg_id)))
            except Exception:
                pass

    # تسجيل أزرار البنك الدائمة لكي لا تتوقف أبداً
    bot.add_view(BankMainView())
    bot.add_view(AdminBankPanelView())
    bot.add_view(InvestmentGamesView())

    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN environment variable.")
    bot.run(TOKEN)
