# =========================================
# SAYANZI FINAL BOT (CUSTOMIZED MENU & FULL FEATURES)
# discord.py 2.x
# =========================================

import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
import asyncio
import sqlite3
import time
import random
import io

import os
TOKEN = os.getenv("TOKEN")

COLOR = 0x8000ff
OWNER_ID = 1446592341908652112
SUPPORT_INVITE = "https://discord.gg/h3FB6hsmn"
BOT_INVITE = "https://discord.com/oauth2/authorize?client_id=1501541120058851348&permissions=8&integration_type=0&scope=bot"

# =========================================
# BOT INTENTS SETUP
# =========================================

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=["!", "#", "c."],
    intents=intents,
    case_insensitive=True,
    help_command=None
)

# =========================================
# DATABASE INITIALIZATION
# =========================================

db = sqlite3.connect("sayanzi.db")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS xp(
guild_id TEXT,
user_id TEXT,
messages INTEGER DEFAULT 0,
day_count INTEGER DEFAULT 0,
week_count INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS warns(
guild_id TEXT,
user_id TEXT,
warns INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS economy(
guild_id TEXT,
user_id TEXT,
balance REAL DEFAULT 0,
last_daily REAL DEFAULT 0,
PRIMARY KEY (guild_id, user_id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS welcome_settings(
guild_id TEXT PRIMARY KEY,
message TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS premium_users(
user_id TEXT,
guild_id TEXT,
role_id TEXT,
expiry_time REAL,
PRIMARY KEY (user_id, guild_id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS mafia_hints_usage(
user_id TEXT,
guild_id TEXT,
hints_count INTEGER DEFAULT 0,
last_reset REAL,
PRIMARY KEY (user_id, guild_id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS server_settings(
guild_id TEXT PRIMARY KEY,
t_role_id TEXT,
admin_role_id TEXT
)
""")

db.commit()

# =========================================
# CACHE & DICTIONARIES
# =========================================

auto_replies = {}
badword_words = {}
spam_cache = {}

# =========================================
# PERMISSIONS & HIERARCHY CHECKS
# =========================================

def is_admin(interaction_or_member, guild=None):
    if isinstance(interaction_or_member, discord.Interaction):
        user = interaction_or_member.user
        g = interaction_or_member.guild
    else:
        user = interaction_or_member
        g = guild

    if not g:
        return False
    
    if user.id == g.owner_id:
        return True

    member = g.get_member(user.id)
    if member and member.guild_permissions.administrator:
        return True
        
    return False

def is_user_premium(user_id, guild_id):
    if user_id == OWNER_ID:
        return True
    current_time = time.time()
    cur.execute("SELECT expiry_time FROM premium_users WHERE user_id=? AND guild_id=?", (str(user_id), str(guild_id)))
    row = cur.fetchone()
    if row and row[0] > current_time:
        return True
    return False

async def check_admin_and_hierarchy(interaction: discord.Interaction, member: discord.Member = None):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)
        return False

    if member:
        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("❌ رتبته أعلى من رتبتي!", ephemeral=True)
            return False

        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ رتبته أعلى من رتبتك!", ephemeral=True)
            return False

    return True

def parse_time(t):
    try:
        value = int(t[:-1])
        unit = t[-1].lower()

        if unit == "s":
            return value
        elif unit == "m":
            return value * 60
        elif unit == "h":
            return value * 3600
        elif unit == "d":
            return value * 86400
    except:
        return None

# =========================================
# GAMES VIEWS (MAFIA & CHAIRS)
# =========================================

class MafiaView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=180)
        self.players = []
        self.guild_id = guild_id

    @discord.ui.button(label="تسجيل 📥", style=discord.ButtonStyle.green, custom_id="mafia_join")
    async def join_mafia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            return await interaction.response.send_message("❌ أنت مسجل بالفعل في لعبة المافيا!", ephemeral=True)
        
        max_limit = 25 if is_user_premium(interaction.user.id, self.guild_id) else 15
        
        if len(self.players) >= max_limit:
            return await interaction.response.send_message(f"❌ عذراً، اكتمل العدد الأقصى للمافيا (`{max_limit}` لاعباً)!", ephemeral=True)
        
        self.players.append(interaction.user)
        await interaction.response.send_message(f"✅ تم تسجيلك بنجاح في لعبة المافيا!", ephemeral=True)

    @discord.ui.button(label="خروج 📤", style=discord.ButtonStyle.red, custom_id="mafia_leave")
    async def leave_mafia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            return await interaction.response.send_message("❌ أنت لست مسجلاً أساساً!", ephemeral=True)
        
        self.players.remove(interaction.user)
        await interaction.response.send_message("✅ تم إزالتك من قائمة المسجلين.", ephemeral=True)

    @discord.ui.button(label="بدء اللعبة 🚀", style=discord.ButtonStyle.blurple, custom_id="mafia_start")
    async def start_mafia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ المشرفين فقط يمكنهم بدء اللعبة!", ephemeral=True)
        if len(self.players) < 4:
            return await interaction.response.send_message("❌ يجب أن يكون عدد المسجلين 4 لاعبين على الأقل!", ephemeral=True)
        
        self.stop()
        mentions = ", ".join([p.mention for p in self.players])
        embed = discord.Embed(
            title="🎮 بدأت لعبة المافيا!",
            description=f"المشاركون فيها ({len(self.players)}):\n{mentions}",
            color=COLOR
        )
        await interaction.response.edit_message(embed=embed, view=None)

class ChairsView(discord.ui.View):
    def __init__(self, host, guild_id):
        super().__init__(timeout=120)
        self.players = []
        self.host = host
        self.guild_id = guild_id

    @discord.ui.button(label="جلس على الكرسي 🪑", style=discord.ButtonStyle.green, custom_id="chair_sit")
    async def sit_chair(self, interaction: discord.Interaction, button: discord.ui.Button):
        max_limit = 30 if is_user_premium(interaction.user.id, self.guild_id) else 20
        if len(self.players) >= max_limit:
            return await interaction.response.send_message(f"❌ عذراً، اكتملت السعة القصوى!", ephemeral=True)

        if interaction.user not in self.players:
            self.players.append(interaction.user)
            await interaction.response.send_message("🏃‍♂️ لحقت ومسكت كرسي!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ أنت جالس بالفعل!", ephemeral=True)

# =========================================
# SUGGESTION VIEW
# =========================================

class SuggestionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.yes_voters = set()
        self.no_voters = set()

    @discord.ui.button(label="👍 موافق (0)", style=discord.ButtonStyle.green, custom_id="suggest_yes")
    async def vote_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid in self.no_voters:
            self.no_voters.remove(uid)
        self.yes_voters.add(uid)
        button.label = f"👍 موافق ({len(self.yes_voters)})"
        self.children[1].label = f"👎 غير موافق ({len(self.no_voters)})"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("✅ تم تسجيل صوتك!", ephemeral=True)

    @discord.ui.button(label="👎 غير موافق (0)", style=discord.ButtonStyle.red, custom_id="suggest_no")
    async def vote_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid in self.yes_voters:
            self.yes_voters.remove(uid)
        self.no_voters.add(uid)
        self.children[0].label = f"👍 موافق ({len(self.yes_voters)})"
        button.label = f"👎 غير موافق ({len(self.no_voters)})"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("❌ تم تسجيل صوتك!", ephemeral=True)

# =========================================
# HELP MENU INTERACTIVE (محدث حسب الطلب - بدون برودكاست أو إضافة فلوس)
# =========================================

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="All member", description="اوامر الاعضاء والفلوس والألعاب", emoji="👥"),
            discord.SelectOption(label="Staff member", description="اوامر الإدارة والحماية", emoji="👑")
        ]
        super().__init__(placeholder="اختر القائمة المطلوبة", options=options, custom_id="help_select")

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "All member":
            embed = discord.Embed(
                title="👥 All member (اوامر الأعضاء)",
                description="قائمة الأوامر العامة، الفلوس، الـ XP والألعاب:",
                color=COLOR
            )
            embed.add_field(
                name="💰 Economy & General",
                value="""
#credit / c / !credit / /credit [عضو]
/daily (الحصول على الراتب 10k)
/tax <المبلغ> (حساب الضريبة)
!xp / /xp | !level / /level
!t | !t day | !t week
!i [عضو] | !عضو | !افاتار | !سيرفر
!اقتراح <الاقتراح>
!mafia | !mafia_hint | !chairs
""",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=HelpView())

        elif self.values[0] == "Staff member":
            embed = discord.Embed(
                title="👑 Staff member (اوامر الإدارة)",
                description="قائمة المشرفين وإدارة السيرفر والحماية:",
                color=COLOR
            )
            embed.add_field(
                name="🛡️ Moderation & Security",
                value="""
!تحذير @عضو | !لاتحذير @عضو | !سجل @عضو
!clear <عدد> | !مسح <عدد>
!قف | !فت
/ban | /unban
/timeout | /timeout_remove
/add_role | /remove_role
/badword | /badword_remove | /badword_list
/auto_reply | /auto_reply_remove | /auto_reply_list
""",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=HelpView())

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(HelpSelect())
        self.add_item(discord.ui.Button(label="اضافة البوت", emoji="🔗", url=BOT_INVITE, style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="الدعم الفني", emoji="💬", url=SUPPORT_INVITE, style=discord.ButtonStyle.link))

# =========================================
# BACKGROUND TASKS
# =========================================

async def check_expired_premiums():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            current_time = time.time()
            cur.execute("SELECT user_id, guild_id FROM premium_users WHERE expiry_time <= ?", (current_time,))
            rows = cur.fetchall()
            for uid, gid in rows:
                cur.execute("DELETE FROM premium_users WHERE user_id=? AND guild_id=?", (uid, gid))
                db.commit()
        except:
            pass
        await asyncio.sleep(60)

# =========================================
# BOT READY EVENT
# =========================================

@bot.event
async def on_ready():
    await bot.tree.sync()
    bot.add_view(HelpView())
    bot.loop.create_task(check_expired_premiums())
    print(f"✅ Sayanzi Bot Logged in as {bot.user}")

# =========================================
# WELCOME EVENT
# =========================================

@bot.event
async def on_member_join(member):
    cur.execute("SELECT message FROM welcome_settings WHERE guild_id=?", (str(member.guild.id),))
    row = cur.fetchone()
    if not row:
        return
    
    msg_template = row[0]
    final_text = msg_template.replace("[user]", member.mention)

    # إذا كانت الرسالة تحتوي على [ing] نقوم بدمج صورة الحساب
    if "[ing]" in final_text:
        final_text = final_text.replace("[ing]", "")
        try:
            avatar_bytes = await member.display_avatar.read()
            file = discord.File(io.BytesIO(avatar_bytes), filename="avatar.png")
            
            # البحث عن أول قناة عامة أو قناة ترحيب
            for channel in member.guild.text_channels:
                if "welcome" in channel.name or "ترحيب" in channel.name or channel.permissions_for(member.guild.me).send_messages:
                    embed = discord.Embed(description=final_text, color=COLOR)
                    embed.set_image(url="attachment://avatar.png")
                    await channel.send(embed=embed, file=file)
                    break
        except:
            pass
    else:
        for channel in member.guild.text_channels:
            if "welcome" in channel.name or "ترحيب" in channel.name or channel.permissions_for(member.guild.me).send_messages:
                embed = discord.Embed(description=final_text, color=COLOR)
                await channel.send(embed=embed)
                break

# =========================================
# MESSAGE EVENT (XP, AUTO REPLY, BADWORD, ANTI SPAM & LINKS, CREDIT PREFIX)
# =========================================

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    gid = str(message.guild.id)
    uid = str(message.author.id)

    # XP System
    cur.execute("SELECT * FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    if cur.fetchone():
        cur.execute("UPDATE xp SET messages=messages+1, day_count=day_count+1, week_count=week_count+1 WHERE guild_id=? AND user_id=?", (gid, uid))
    else:
        cur.execute("INSERT INTO xp VALUES(?,?,?,?,?)", (gid, uid, 1, 1, 1))
    db.commit()

    # Credit Text Commands: #credit, c, !credit (ProBot style transfer & balance)
    content = message.content.strip()
    if content.startswith(("#credit", "c", "!credit")) or content == "c":
        parts = content.split()
        # Case 1: Checking balance (!credit / c / #credit)
        if len(parts) == 1 or (len(parts) == 2 and parts[1].startswith("<@")):
            target = message.mentions[0] if message.mentions else message.author
            t_uid = str(target.id)
            cur.execute("SELECT balance FROM economy WHERE guild_id=? AND user_id=?", (gid, t_uid))
            row = cur.fetchone()
            bal = row[0] if row else 0.0
            embed = discord.Embed(description=f"👤 **{target.name}** رصيدك هو: **{bal:,.0f} 🪙**", color=COLOR)
            return await message.channel.send(embed=embed)
        
        # Case 2: Transferring credits (!credit @user amount)
        elif len(parts) >= 3 and message.mentions:
            recipient = message.mentions[0]
            if recipient.id == message.author.id:
                return await message.channel.send("❌ لا يمكنك التحويل لنفسك!")
            try:
                raw_amount = float(parts[2])
            except:
                return await message.channel.send("❌ يرجى كتابة مبلغ صحيح للتحويل!")
            
            if raw_amount <= 0:
                return await message.channel.send("❌ المبلغ يجب أن يكون أكبر من الصفر!")

            # ProBot Tax Calculation (5%)
            tax = raw_amount * 0.05
            net_amount = raw_amount - tax

            # Check sender balance
            cur.execute("SELECT balance FROM economy WHERE guild_id=? AND user_id=?", (gid, uid))
            s_row = cur.fetchone()
            s_bal = s_row[0] if s_row else 0.0

            if s_bal < raw_amount:
                return await message.channel.send(f"❌ ليس لديك رصيد كافٍ! رصيدك الحالي: **{s_bal:,.0f} 🪙**")

            # Deduct from sender
            cur.execute("UPDATE economy SET balance = balance - ? WHERE guild_id=? AND user_id=?", (raw_amount, gid, uid))
            
            # Add to recipient
            cur.execute("SELECT balance FROM economy WHERE guild_id=? AND user_id=?", (gid, str(recipient.id)))
            r_row = cur.fetchone()
            if r_row:
                cur.execute("UPDATE economy SET balance = balance + ? WHERE guild_id=? AND user_id=?", (net_amount, gid, str(recipient.id)))
            else:
                cur.execute("INSERT INTO economy VALUES(?,?,?,?)", (gid, str(recipient.id), net_amount, 0))
            db.commit()

            embed = discord.Embed(
                description=f"💸 **تحويل ناجح!**\n- المبلغ المرسل: `{raw_amount:,.0f}`\n- الضريبة (5%): `{tax:,.0f}`\n- المبلغ المستلم للطرف الآخر: **{net_amount:,.0f} 🪙**",
                color=COLOR
            )
            return await message.channel.send(embed=embed)

    # Auto Reply
    for trigger, reply in auto_replies.items():
        if trigger in message.content.lower():
            embed = discord.Embed(description=reply, color=COLOR)
            await message.channel.send(embed=embed)

    # Badword Protection
    for word, sec in badword_words.items():
        if word in message.content.lower():
            try:
                await message.delete()
                await message.author.timeout(timedelta(seconds=sec))
                await message.channel.send(f"⛔ {message.author.mention} تم إعطاؤه تايم لمخالفة كلمات الحماية المحظورة.")
            except:
                pass

    # Anti Links
    if "http://" in message.content.lower() or "https://" in message.content.lower():
        if not is_admin(message.author, message.guild):
            try:
                await message.delete()
                await message.channel.send(f"🚫 {message.author.mention} الروابط ممنوعة في هذا السيرفر!")
            except:
                pass

    # Anti Spam
    key = (gid, uid)
    spam_cache[key] = spam_cache.get(key, []) + [time.time()]
    spam_cache[key] = [t for t in spam_cache[key] if time.time() - t < 3]

    if len(spam_cache[key]) >= 5:
        try:
            await message.author.timeout(timedelta(minutes=10), reason="Spamming")
            await message.channel.send(f"⏱ {message.author.mention} تم إعطاؤك تايم بسبب السبام المتكرر.")
        except:
            pass
        spam_cache[key] = []

    await bot.process_commands(message)

# =========================================
# ECONOMY & TAX SLASH COMMANDS
# =========================================

@bot.tree.command(name="credit", description="عرض رصيدك أو رصيد عضو آخر")
async def slash_credit(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    gid = str(interaction.guild.id)
    uid = str(member.id)
    cur.execute("SELECT balance FROM economy WHERE guild_id=? AND user_id=?", (gid, uid))
    row = cur.fetchone()
    bal = row[0] if row else 0.0
    embed = discord.Embed(description=f"👤 **{member.name}** رصيدك هو: **{bal:,.0f} 🪙**", color=COLOR)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="الحصول على راتبك اليومي (10 آلاف كريدت)")
async def slash_daily(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    uid = str(interaction.user.id)
    current_time = time.time()
    
    cur.execute("SELECT last_daily FROM economy WHERE guild_id=? AND user_id=?", (gid, uid))
    row = cur.fetchone()
    
    if row and current_time - row[0] < 86400:
        remaining = int(86400 - (current_time - row[0]))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        return await interaction.response.send_message(f"⏳ لقد استلمت راتبك مسبقاً! يمكنك الاستلام بعد `{hours} ساعة و {minutes} دقيقة`.", ephemeral=True)
    
    daily_amount = 10000.0
    if row:
        cur.execute("UPDATE economy SET balance = balance + ?, last_daily = ? WHERE guild_id=? AND user_id=?", (daily_amount, current_time, gid, uid))
    else:
        cur.execute("INSERT INTO economy VALUES(?,?,?,?)", (gid, uid, daily_amount, current_time))
    db.commit()
    
    embed = discord.Embed(description=f"🎁 **تم إيداع الراتب اليومي بنجاح!**\nحصلت على: **{daily_amount:,.0f} 🪙**", color=COLOR)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="tax", description="حساب ضريبة التحويل (النسبة 5%)")
@app_commands.describe(amount="المبلغ المراد تحويله")
async def slash_tax(interaction: discord.Interaction, amount: float):
    tax = amount * 0.05
    net = amount - tax
    transfer_amount = amount / 0.95  # المبلغ الذي يجب كتابته ليصله المبلغ صافياً
    
    embed = discord.Embed(title="🧮 حاسبة ضريبة البوت", color=COLOR)
    embed.add_field(name="المبلغ المطلوب تحويله", value=f"`{amount:,.0f}`", inline=False)
    embed.add_field(name="قيمة الضريبة (5%)", value=f"`{tax:,.0f}`", inline=False)
    embed.add_field(name="المبلغ الذي سيصله صافي", value=f"**{net:,.0f} 🪙**", inline=False)
    embed.add_field(name="اكتب هذا الأمر ليصله المبلغ كاملاً", value=f"`!credit @user {transfer_amount:,.2f}`", inline=False)
    await interaction.response.send_message(embed=embed)

# =========================================
# WELCOME COMMAND (/welcom_join)
# =========================================

@bot.tree.command(name="welcom_join", description="تحديد رسالة الترحيب بالأعضاء الجدد مع [user] و [ing]")
@app_commands.describe(message="رسالة الترحيب (استخدم [user] لعمل منشن و [ing] لصورة الحساب)")
async def welcom_join(interaction: discord.Interaction, message: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ ليس لديك صلاحية Administrator.", ephemeral=True)
    
    gid = str(interaction.guild.id)
    cur.execute("INSERT OR REPLACE INTO welcome_settings VALUES (?, ?)", (gid, message))
    db.commit()
    
    embed = discord.Embed(title="✅ تم حفظ نظام الترحيب", description=f"**الرسالة المدخلة:**\n{message}", color=COLOR)
    await interaction.response.send_message(embed=embed)

# =========================================
# GAMES COMMANDS (MAFIA, CHAIRS)
# =========================================

@bot.command(name="mafia")
async def mafia_game(ctx):
    view = MafiaView(ctx.guild.id)
    embed = discord.Embed(title="🕵️‍♂️ تسجيل لعبة المافيا", description="اضغط على زر **(تسجيل 📥)** أدناه للمشاركة.", color=COLOR)
    await ctx.send(embed=embed, view=view)

@bot.command(name="mafia_hint")
async def mafia_hint(ctx):
    if not is_user_premium(ctx.author.id, ctx.guild.id):
        return await ctx.send("❌ ميزة مخصصة لمشتركي البريميوم فقط!")

    gid = str(ctx.guild.id)
    uid = str(ctx.author.id)
    current_time = time.time()
    
    cur.execute("SELECT hints_count, last_reset FROM mafia_hints_usage WHERE user_id=? AND guild_id=?", (uid, gid))
    row = cur.fetchone()

    hints_allowed = 5
    if row:
        hints_count, last_reset = row
        if current_time - last_reset >= 86400:
            hints_count = 0
            last_reset = current_time
        if hints_count >= hints_allowed:
            return await ctx.send("❌ استهلكت جميع تلميحاتك الـ 5 المسموحة اليوم!")
        hints_count += 1
        cur.execute("UPDATE mafia_hints_usage SET hints_count=?, last_reset=? WHERE user_id=? AND guild_id=?", (hints_count, last_reset, uid, gid))
    else:
        hints_count = 1
        cur.execute("INSERT INTO mafia_hints_usage VALUES (?, ?, ?, ?)", (uid, gid, hints_count, current_time))
    db.commit()

    hints_pool = [
        "💡 تلميح مافيا: راقب الأقوال المتقاطعة، العضو الهادئ غالباً مشتبه به.",
        "💡 تلميح مافيا: التخفي وسط النقاشات العامة أسلوب شائع للمتخفين.",
        "💡 تلميح مافيا: في الجولات المتقدمة، التركيز على تصرفات آخر شخص يكشف الكثير."
    ]
    embed = discord.Embed(title="🕵️‍♂️ تلميح المافيا", description=f"{random.choice(hints_pool)}\n\n*المتبقي لديك اليوم: **{hints_allowed - hints_count}***5", color=COLOR)
    await ctx.send(embed=embed)

@bot.command(name="chairs")
async def chairs_game(ctx):
    view = ChairsView(ctx.author, ctx.guild.id)
    embed = discord.Embed(title="🪑 لعبة الكراسي الموسيقية", description="اضغط على زر **(جلس على الكرسي 🪑)** للانضمام!", color=COLOR)
    await ctx.send(embed=embed, view=view)
    
    await asyncio.sleep(15)
    view.stop()
    players = view.players
    if len(players) < 2:
        return await ctx.send("❌ عدد المشاركين قليل جداً!")

    total_p = len(players)
    current_chairs = max(5, total_p - 5)
    while len(players) > 1:
        await asyncio.sleep(5)
        loser = random.choice(players)
        players.remove(loser)
        await ctx.send(f"❌ تم استبعاد: {loser.mention} | المتبقي: `{len(players)}`")
    await ctx.send(f"🏆 الفائز بلقب ملك الكراسي: {players[0].mention} 🎉")

# =========================================
# SUGGESTION COMMAND
# =========================================

@bot.command(name="اقتراح")
async def suggestion_command(ctx, *, text: str = None):
    if not text:
        return await ctx.send("❌ يرجى كتابة الاقتراح بجانب الأمر!")
    embed = discord.Embed(title="💡 اقتراح جديد", description=f"**صاحب الاقتراح:** {ctx.author.mention}\n\n{text}", color=COLOR)
    view = SuggestionView()
    await ctx.message.delete()
    await ctx.send(embed=embed, view=view)

# =========================================
# HELP & COMMANDS LIST
# =========================================

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(title="Sayanzi bot", description="من هنا يمكنك الوصول الى جميع الاوامر الأساسية للبوت.", color=COLOR)
    await ctx.send(embed=embed, view=HelpView())

@bot.tree.command(name="commands", description="عرض لوحة مساعدة بوت Sayanzi")
async def commands_list(interaction: discord.Interaction):
    embed = discord.Embed(title="Sayanzi bot", description="من هنا يمكنك الوصول الى جميع الاوامر الأساسية للبوت.", color=COLOR)
    await interaction.response.send_message(embed=embed, view=HelpView())

# =========================================
# XP, LEVEL, TOP, PROFILE, INFO COMMANDS
# =========================================

@bot.command()
async def xp(ctx):
    gid = str(ctx.guild.id)
    uid = str(ctx.author.id)
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    row = cur.fetchone()
    await ctx.send(embed=discord.Embed(title="⭐ XP", description=f"```{row[0] if row else 0}```", color=COLOR))

@bot.tree.command(name="xp", description="عرض نقاط الخبرة XP")
async def slash_xp(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    uid = str(interaction.user.id)
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    row = cur.fetchone()
    await interaction.response.send_message(embed=discord.Embed(title="⭐ XP", description=f"```{row[0] if row else 0}```", color=COLOR))

@bot.command()
async def level(ctx):
    gid = str(ctx.guild.id)
    uid = str(ctx.author.id)
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    row = cur.fetchone()
    amt = row[0] if row else 0
    await ctx.send(embed=discord.Embed(title="📊 LEVEL", description=f"```{amt // 50}```", color=COLOR))

@bot.tree.command(name="level", description="عرض مستواك الحالي")
async def slash_level(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    uid = str(interaction.user.id)
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    row = cur.fetchone()
    amt = row[0] if row else 0
    await interaction.response.send_message(embed=discord.Embed(title="📊 LEVEL", description=f"```{amt // 50}```", color=COLOR))

@bot.command(name="t")
async def top_command(ctx, mode=None):
    gid = str(ctx.guild.id)
    col, title = "messages", "Months Top"
    if mode == "day":
        col, title = "day_count", "Top Day"
    elif mode == "week":
        col, title = "week_count", "Top Week"
    cur.execute(f"SELECT user_id, {col} FROM xp WHERE guild_id=? ORDER BY {col} DESC LIMIT 10", (gid,))
    embed = discord.Embed(title=f"🏆 {title}", color=COLOR)
    for i, (uid, cnt) in enumerate(cur.fetchall(), start=1):
        embed.add_field(name=f"{i}. <@{uid}>", value=f"💬 {cnt} نقطة", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="i")
async def profile(ctx, member: discord.Member = None):
    member = member or ctx.author
    gid = str(ctx.guild.id)
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, str(member.id)))
    row = cur.fetchone()
    msgs = row[0] if row else 0
    embed = discord.Embed(title=f"Profile: {member.name}", color=COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🏷️ الاسم", value=f"`{member}`", inline=False)
    embed.add_field(name="🆔 الآيدي", value=f"`{member.id}`", inline=False)
    embed.add_field(name="📊 المستوى / XP", value=f"المستوى: `{msgs // 50}` | نقاط: `{msgs}`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="افاتار")
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"Avatar: {member.name}", color=COLOR)
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="عضو")
async def member_info(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"Member Info: {member}", color=COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="👑 أعلى رتبة", value=member.top_role.mention)
    embed.add_field(name="🆔 الآيدي", value=f"`{member.id}`")
    await ctx.send(embed=embed)

@bot.command(name="سيرفر", aliases=["server"])
async def server_info(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"🖥 معلومات سيرفر: {guild.name}", color=COLOR)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="👥 الأعضاء", value=f"`{guild.member_count}`", inline=True)
    embed.add_field(name="👑 المالك", value=f"{guild.owner.mention}", inline=True)
    await ctx.send(embed=embed)

# =========================================
# MODERATION COMMANDS (Text)
# =========================================

@bot.command(name="تحذير")
async def warn(ctx, member: discord.Member):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ ليس لديك صلاحية!")
    gid = str(ctx.guild.id)
    uid = str(member.id)
    cur.execute("SELECT warns FROM warns WHERE guild_id=? AND user_id=?", (gid, uid))
    if cur.fetchone():
        cur.execute("UPDATE warns SET warns=warns+1 WHERE guild_id=? AND user_id=?", (gid, uid))
    else:
        cur.execute("INSERT INTO warns VALUES(?,?,?)", (gid, uid, 1))
    db.commit()
    await ctx.send(f"⚠ تم تحذير {member.mention}.")

@bot.command(name="لاتحذير")
async def unwarn(ctx, member: discord.Member):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ ليس لديك صلاحية!")
    cur.execute("UPDATE warns SET warns = CASE WHEN warns > 0 THEN warns - 1 ELSE 0 END WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(member.id)))
    db.commit()
    await ctx.send(f"✅ تمت إزالة تحذير من {member.mention}.")

@bot.command(name="سجل")
async def records_command(ctx, member: discord.Member = None):
    member = member or ctx.author
    cur.execute("SELECT warns FROM warns WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(member.id)))
    row = cur.fetchone()
    await ctx.send(embed=discord.Embed(title=f"📋 سجل {member.name}", description=f"⚠️ التحذيرات: `{row[0] if row else 0}`", color=COLOR))

@bot.command(name="clear", aliases=["مسح"])
async def clear(ctx, amount: int):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ ليس لديك صلاحية!")
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 تم مسح `{amount}` رسالة.")
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except:
        pass

@bot.command(name="قف")
async def lock(ctx):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ ليس لديك صلاحية!")
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔒 تم قفل الشات.")

@bot.command(name="فت")
async def unlock(ctx):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ ليس لديك صلاحية!")
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔓 تم فتح الشات.")

# =========================================
# ADMIN SLASH COMMANDS (مستقيمة تماماً بدون تفرعات)
# =========================================

@bot.tree.command(name="ban", description="حظر عضو من السيرفر")
async def ban(interaction: discord.Interaction, member: discord.Member):
    if not await check_admin_and_hierarchy(interaction, member):
        return
    await member.ban()
    await interaction.response.send_message("✅ تم حظر العضو بنجاح.")

@bot.tree.command(name="unban", description="إلغاء حظر عضو بواسطة الآيدي")
async def unban(interaction: discord.Interaction, user_id: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ ليس لديك صلاحية.", ephemeral=True)
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message("✅ تم إلغاء حظر العضو.")
    except Exception as e:
        await interaction.response.send_message(f"❌ خطأ:\n`{e}`", ephemeral=True)

@bot.tree.command(name="timeout", description="إعطاء تايم لعضو لفترة محددة")
async def timeout(interaction: discord.Interaction, member: discord.Member, time: str):
    if not await check_admin_and_hierarchy(interaction, member):
        return
    secs = parse_time(time)
    if not secs:
        return await interaction.response.send_message("❌ صيغة الوقت خاطئة (مثال: 10m, 1h)", ephemeral=True)
    await member.timeout(timedelta(seconds=secs))
    await interaction.response.send_message("✅ تم إعطاء التايم بنجاح.")

@bot.tree.command(name="timeout_remove", description="إزالة التايم عن العضو")
async def timeout_remove(interaction: discord.Interaction, member: discord.Member):
    if not await check_admin_and_hierarchy(interaction, member):
        return
    await member.timeout(None)
    await interaction.response.send_message("✅ تمت إزالة التايم.")

@bot.tree.command(name="add_role", description="إضافة رتبة لعضو")
async def add_role(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not await check_admin_and_hierarchy(interaction, member):
        return
    await member.add_roles(role)
    await interaction.response.send_message(f"✅ تم إضافة الرتبة لـ {member.mention}.")

@bot.tree.command(name="remove_role", description="إزالة رتبة من عضو")
async def remove_role(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not await check_admin_and_hierarchy(interaction, member):
        return
    await member.remove_roles(role)
    await interaction.response.send_message(f"✅ تمت إزالة الرتبة من {member.mention}.")

# =========================================
# BADWORD & AUTO-REPLY COMMANDS
# =========================================

@bot.tree.command(name="badword", description="إضافة كلمة محظورة لنظام الحماية مع وقت التايم")
@app_commands.describe(word="الكلمة المحظورة", time="مدة التايم مثل: 10s أو 5m")
async def badword(interaction: discord.Interaction, word: str, time: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ ليس لديك صلاحية.", ephemeral=True)
    secs = parse_time(time)
    if not secs:
        return await interaction.response.send_message("❌ صيغة الوقت غير صحيحة", ephemeral=True)
    badword_words[word.lower()] = secs
    await interaction.response.send_message(f"✅ تم إضافة `{word}` لقائمة الكلمات المحظورة.", ephemeral=True)

@bot.tree.command(name="badword_remove", description="إزالة كلمة من قائمة الحماية")
async def badword_remove(interaction: discord.Interaction, word: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ ليس لديك صلاحية.", ephemeral=True)
    if word.lower() in badword_words:
        del badword_words[word.lower()]
        await interaction.response.send_message(f"✅ تم إزالة `{word}`.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ الكلمة غير موجودة.", ephemeral=True)

@bot.tree.command(name="badword_list", description="عرض قائمة الكلمات المحظورة")
async def badword_list(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ ليس لديك صلاحية.", ephemeral=True)
    if not badword_words:
        return await interaction.response.send_message("📋 قائمة الكلمات المحظورة فارغة.", ephemeral=True)
    lst = "\n".join([f"• `{w}` ({s}ث)" for w, s in badword_words.items()])
    await interaction.response.send_message(embed=discord.Embed(title="🛡️ الكلمات المحظورة", description=lst, color=COLOR), ephemeral=True)

@bot.tree.command(name="auto_reply", description="إضافة رد تلقائي لكلمة معينة")
async def auto_reply(interaction: discord.Interaction, trigger: str, reply: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ ليس لديك صلاحية.", ephemeral=True)
    auto_replies[trigger.lower()] = reply
    await interaction.response.send_message(f"✅ تم إضافة الرد التلقائي لـ `{trigger}`.", ephemeral=True)

@bot.tree.command(name="auto_reply_remove", description="إزالة رد تلقائي")
async def auto_reply_remove(interaction: discord.Interaction, trigger: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ ليس لديك صلاحية.", ephemeral=True)
    if trigger.lower() in auto_replies:
        del auto_replies[trigger.lower()]
        await interaction.response.send_message("✅ تم الحذف بنجاح.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ غير موجودة.", ephemeral=True)

@bot.tree.command(name="auto_reply_list", description="عرض الردود التلقائية")
async def auto_reply_list(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ ليس لديك صلاحية.", ephemeral=True)
    if not auto_replies:
        return await interaction.response.send_message("📋 قائمة الردود فارغة.", ephemeral=True)
    lst = "\n".join([f"• **{t}** ➔ `{r}`" for t, r in auto_replies.items()])
    await interaction.response.send_message(embed=discord.Embed(title="💬 الردود التلقائية", description=lst, color=COLOR), ephemeral=True)

# =========================================
# OWNER BROADCAST COMMANDS (خاصة بمالك البوت حصرياً ومخفية من الهيلب)
# =========================================

@bot.tree.command(name="send_all", description="إرسال برودكاست لكل الأعضاء مع دعم [user]")
async def send_all(interaction: discord.Interaction, text: str):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ مخصص لمالك البوت فقط!", ephemeral=True)
    await interaction.response.send_message("⏳ جاري الإرسال...", ephemeral=True)
    success = 0
    for member in interaction.guild.members:
        if member.bot:
            continue
        try:
            await member.send(text.replace("[user]", member.mention))
            success += 1
            await asyncio.sleep(3)
        except:
            pass
    await interaction.followup.send(f"✅ تم الإرسال بنجاح لـ `{success}` عضو.", ephemeral=True)

@bot.tree.command(name="send_online", description="إرسال برودكاست للأعضاء المتواجدين مع دعم [user]")
async def send_online(interaction: discord.Interaction, text: str):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ مخصص لمالك البوت فقط!", ephemeral=True)
    await interaction.response.send_message("⏳ جاري الإرسال...", ephemeral=True)
    success = 0
    for member in interaction.guild.members:
        if member.bot or member.status == discord.Status.offline:
            continue
        try:
            await member.send(text.replace("[user]", member.mention))
            success += 1
            await asyncio.sleep(3)
        except:
            pass
    await interaction.followup.send(f"✅ تم الإرسال للأونلاين بنجاح لـ `{success}` عضو.", ephemeral=True)

# =========================================
# RUN BOT
# =========================================

bot.run(TOKEN)

