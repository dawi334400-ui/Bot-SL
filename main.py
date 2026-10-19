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

# ----------------- 🏦 نظام البنك المالي -----------------
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

# ----------------- 🎟️ نظام التكتات والمنيو -----------------
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
            discord.SelectOption(label="⭐ 5 - ممتاز جداً", value="5"),
            discord.SelectOption(label="⭐ 4 - جيد جداً", value="4"),
            discord.SelectOption(label="⭐ 3 - متوسط", value="3"),
            discord.SelectOption(label="⭐ 2 - سيئ", value="2"),
            discord.SelectOption(label="⭐ 1 - سيئ جداً", value="1"),
        ]
    )
    async def select_rating(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.ticket_owner_id:
            await interaction.response.send_message("❌ مخصص لصاحب التكت فقط!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        rating = int(select.values[0])
        stats = db_data["staff_stats"].get(self.staff_id, {
            "tickets": 0, "total_stars": 0, "ratings_count": 0, "ratings_list": []
        })
        stats["total_stars"] += rating
        stats["ratings_count"] += 1
        stats["ratings_list"].append(rating)

        db_data["staff_stats"][self.staff_id] = stats
        save_data(db_data)

        await interaction.followup.send("✅ شكراً لك! جاري إغلاق التكت...", ephemeral=True)
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

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="👥 اختر العضو لإضافته...", custom_id="add_member_select")
    async def select_member(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        member = select.values[0]
        await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
        await interaction.response.send_message(f"✅ تم إضافة {member.mention} للتكت.", ephemeral=False)

class RemoveMemberSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="🚫 اختر العضو لإزالته...", custom_id="remove_member_select")
    async def select_member(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        member = select.values[0]
        ticket_info = db_data["active_tickets"].get(str(interaction.channel.id), {})
        if member.id == ticket_info.get("owner_id"):
            await interaction.response.send_message("❌ لا يمكنك إزالة صاحب التكت!", ephemeral=True)
            return
        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(f"✅ تم إزالة صلاحيات {member.mention}.", ephemeral=False)

class TicketControlView(discord.ui.View):
    def __init__(self, menu_type="admin"):
        super().__init__(timeout=None)
        self.menu_type = menu_type

    @discord.ui.button(label="إضافة عضو ➕", style=discord.ButtonStyle.secondary, custom_id="add_member_btn")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("اختر العضو:", view=AddMemberSelectView(), ephemeral=True)

    @discord.ui.button(label="إزالة عضو ➖", style=discord.ButtonStyle.secondary, custom_id="remove_member_btn")
    async def remove_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("اختر العضو:", view=RemoveMemberSelectView(), ephemeral=True)

    @discord.ui.button(label="إغلاق التكت 🔒", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_id = str(interaction.channel.id)
        ticket_info = db_data["active_tickets"].get(channel_id, {})
        claimed_staff_id = ticket_info.get("staff_id")
        owner_id = ticket_info.get("owner_id")
        menu_type = ticket_info.get("menu_type", self.menu_type)

        if menu_type == "admin" and claimed_staff_id:
            view = RatingView(staff_id=claimed_staff_id, ticket_channel=interaction.channel, ticket_owner_id=owner_id)
            await interaction.response.send_message("⭐ يرجى تقييم الخدمة قبل الإغلاق:", view=view)
        else:
            await interaction.response.send_message("🔒 جاري إغلاق التكت...")
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
        super().__init__(label=label, emoji=emoji if emoji else None, style=discord.ButtonStyle.primary, custom_id=cid)
        self.button_text = button_text
        self.menu_type = menu_type
        self.allowed_role_ids = allowed_role_ids
        self.observer_role_ids = observer_role_ids
        self.msg_id = str(msg_id)
        self.btn_index = btn_index

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        msg_id_target = self.msg_id or (str(interaction.message.id) if interaction.message else "")
        menu_info = db_data["menus"].get(msg_id_target, {})
        buttons_list = menu_info.get("buttons", [])
        
        btn_data = buttons_list[self.btn_index] if 0 <= self.btn_index < len(buttons_list) else None
        btn_text = btn_data.get("text", "") if btn_data else self.button_text
        allowed_roles = btn_data.get("allowed_role_ids", []) if btn_data else self.allowed_role_ids
        observer_roles = btn_data.get("observer_role_ids", []) if btn_data else self.observer_role_ids

        guild = interaction.guild
        category = interaction.channel.category
        ticket_count = len(db_data["active_tickets"]) + 1
        channel_name = f"{self.label.replace(' ', '-')}-{ticket_count}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        for role_id in set([int(r) for r in allowed_roles + observer_roles]):
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        except Exception as e:
            await interaction.followup.send(f"❌ خطأ: {e}", ephemeral=True)
            return

        db_data["active_tickets"][str(ticket_channel.id)] = {
            "owner_id": interaction.user.id,
            "staff_id": None,
            "menu_type": menu_info.get("menu_type", self.menu_type),
            "allowed_role_ids": [int(r) for r in allowed_roles],
            "observer_role_ids": [int(r) for r in observer_roles]
        }
        save_data(db_data)

        embed = discord.Embed(title=f"🎟️ مرحباً بك في {channel_name}", description=btn_text or "📌 يرجى توضيح طلبك.", color=discord.Color.gold())
        await ticket_channel.send(embed=embed, view=TicketControlView())
        await interaction.followup.send(f"✅ تم فتح التكت: {ticket_channel.mention}", ephemeral=True)

class DynamicMenuView(discord.ui.View):
    def __init__(self, buttons_list, menu_type, msg_id=""):
        super().__init__(timeout=None)
        for idx, btn in enumerate(buttons_list):
            self.add_item(InteractiveTicketButton(
                label=btn.get("label", "تكت"),
                emoji=btn.get("emoji"),
                button_text=btn.get("text", ""),
                menu_type=menu_type,
                allowed_role_ids=btn.get("allowed_role_ids", []),
                observer_role_ids=btn.get("observer_role_ids", []),
                btn_index=idx,
                msg_id=str(msg_id)
            ))

# ----------------- أوامر السلاش الرئيسية -----------------
@bot.tree.command(name="البنك", description="فتح قائمة البنك الرئيسية")
async def bank_main_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="🏦 نظام البنك المالي", description="اختر من الأزرار أدناه:", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed, view=BankMainView(), ephemeral=True)

@bot.tree.command(name="لوحة_المدير", description="[للمديرين] لوحة تحكم البنك")
async def admin_panel_cmd(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ للإدارة فقط.", ephemeral=True)
        return
    embed = discord.Embed(title="⚙️ لوحة تحكم مدير البنك", color=discord.Color.red())
    await interaction.response.send_message(embed=embed, view=AdminBankPanelView(), ephemeral=True)

@bot.tree.command(name="إنشاء_منيو", description="إنشاء منيو تفاعلي جديد")
@app_commands.choices(نوع_المنيو=[app_commands.Choice(name="إداري", value="admin"), app_commands.Choice(name="عصابات", value="normal")])
async def create_menu(interaction: discord.Interaction, نوع_المنيو: app_commands.Choice[str]):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ للصلاحيات فقط.", ephemeral=True)
        return
    embed = discord.Embed(title="مركز الدعم والمساعدة", description="اختر قسماً:", color=discord.Color.gold())
    msg = await interaction.channel.send(embed=embed)
    db_data["menus"][str(msg.id)] = {"title": embed.title, "description": embed.description, "buttons": [], "menu_type": نوع_المنيو.value}
    save_data(db_data)
    await interaction.response.send_message("✅ تم إنشاء المنيو بنجاح.", ephemeral=True)

# ----------------- الأحداث الأساسية وتسجيل الأزرار -----------------
@bot.event
async def on_ready():
    # تسجيل جميع الأزرار الدائمة لكي لا تتوقف أبداً
    bot.add_view(TicketControlView())
    bot.add_view(BankMainView())
    bot.add_view(AdminBankPanelView())
    bot.add_view(InvestmentGamesView())

    for msg_id, menu_data in db_data.get("menus", {}).items():
        buttons = menu_data.get("buttons", [])
        if buttons:
            try:
                bot.add_view(DynamicMenuView(buttons, menu_data.get("menu_type", "admin"), str(msg_id)))
            except Exception:
                pass

    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN environment variable.")
    bot.run(TOKEN)
