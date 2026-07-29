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
    command_prefix="!",
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
protection_words = {}
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

def check_command_permission(ctx, command_type):
    gid = str(ctx.guild.id)
    cur.execute("SELECT t_role_id, admin_role_id FROM server_settings WHERE guild_id=?", (gid,))
    row = cur.fetchone()
    
    if not row:
        return True if command_type == "general" else is_admin(ctx.author, ctx.guild)
    
    t_role_id, admin_role_id = row
    
    if command_type == "t":
        if not t_role_id:
            return True
        role = ctx.guild.get_role(int(t_role_id))
        if role and role in ctx.author.roles:
            return True
        return is_admin(ctx.author, ctx.guild)
        
    elif command_type == "admin":
        if is_admin(ctx.author, ctx.guild):
            return True
        if admin_role_id:
            role = ctx.guild.get_role(int(admin_role_id))
            if role and role in ctx.author.roles:
                return True
        return False
        
    return True

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
        await interaction.response.send_message(f"✅ تم تسجيلك بنجاح في لعبة المافيا! (الحد الأقصى الحالي لك: {max_limit})", ephemeral=True)

    @discord.ui.button(label="خروج 📤", style=discord.ButtonStyle.red, custom_id="mafia_leave")
    async def leave_mafia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            return await interaction.response.send_message("❌ أنت لست مسجلاً أساساً!", ephemeral=True)
        
        self.players.remove(interaction.user)
        await interaction.response.send_message("✅ تم إزالتك من قائمة المسجلين.", ephemeral=True)

    @discord.ui.button(label="بدء اللعبة 🚀", style=discord.ButtonStyle.blurple, custom_id="mafia_start")
    async def start_mafia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ صاحب السيرفر أو المشرفين فقط من يمكنهم بدء اللعبة!", ephemeral=True)
        if len(self.players) < 4:
            return await interaction.response.send_message("❌ يجب أن يكون عدد المسجلين 4 لاعبين على الأقل لبدء المافيا!", ephemeral=True)
        
        self.stop()
        mentions = ", ".join([p.mention for p in self.players])
        embed = discord.Embed(
            title="🎮 بدأت لعبة المافيا!",
            description=f"المشاركون فيها ({len(self.players)}):\n{mentions}\n\n*تم إغلاق التسجيل، بالتوفيق للجميع!*",
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
        max_chairs_limit = 30 if is_user_premium(interaction.user.id, self.guild_id) else 20
        if len(self.players) >= max_chairs_limit:
            return await interaction.response.send_message(f"❌ عذراً، اكتملت السعة القصوى للمقاعد (`{max_chairs_limit}`)!", ephemeral=True)

        if interaction.user not in self.players:
            self.players.append(interaction.user)
            await interaction.response.send_message("🏃‍♂️ لحقت ومسكت كرسي!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ أنت جالس بالفعل!", ephemeral=True)

# =========================================
# SUGGESTION VIEW (أزرار التصويت)
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
        await interaction.followup.send("✅ تم تسجيل صوتك (موافق)!", ephemeral=True)

    @discord.ui.button(label="👎 غير موافق (0)", style=discord.ButtonStyle.red, custom_id="suggest_no")
    async def vote_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid in self.yes_voters:
            self.yes_voters.remove(uid)
        self.no_voters.add(uid)
        
        self.children[0].label = f"👍 موافق ({len(self.yes_voters)})"
        button.label = f"👎 غير موافق ({len(self.no_voters)})"
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("❌ تم تسجيل صوتك (غير موافق)!", ephemeral=True)

# =========================================
# HELP MENU INTERACTIVE (محدث حسب الطلب)
# =========================================

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="All member", description="اوامر الاعضاء", emoji="👥"),
            discord.SelectOption(label="Staff member", description="اوامر الادارة", emoji="👑"),
            discord.SelectOption(label="King bot", description="اوامر صاحب البوت", emoji="💳")
        ]
        super().__init__(placeholder="اختر القائمة المطلوبة", options=options, custom_id="help_select")

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "All member":
            embed = discord.Embed(
                title="👥 All member (اوامر الاعضاء)",
                description="قائمة الأوامر العامة ونقاط الـ XP والمستويات والألعاب:",
                color=COLOR
            )
            embed.add_field(
                name="📌 General & Games",
                value="""
!xp / /xp | !level / /level
!t (توب الشهر) | !t day | !t week
!i [عضو] | !عضو | !افاتار | !سيرفر
!اقتراح <الاقتراح>
!mafia | !mafia_hint | !chairs
!help / /commands
""",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=HelpView())

        elif self.values[0] == "Staff member":
            embed = discord.Embed(
                title="👑 Staff member (اوامر الادارة)",
                description="قائمة الإدارة وحماية السيرفر والأمان:",
                color=COLOR
            )
            embed.add_field(
                name="🛡️ Moderation & Security",
                value="""
!تحذير @عضو | !لاتحذير @عضو | !سجل @عضو
!clear <عدد> | !مسح <عدد>
!قف (قفل الشات) | !فت (فتح الشات)
/ban | /unban
/timeout | /timeout_remove
/add_role | /remove_role
/message <نص>
/protection | /protection_remove | /protection_list
/auto_reply | /auto_reply_remove | /auto_reply_list
""",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=HelpView())

        elif self.values[0] == "King bot":
            embed = discord.Embed(
                title="💳 King bot (اوامر صاحب البوت)",
                description="التحكم الكامل والبرودكاست وصلاحيات البريميوم:",
                color=COLOR
            )
            embed.add_field(
                name="⚡ Owner Commands",
                value="""
!add_premium <@عضو> <الوقت>
!remove_premium <@عضو>
/send_all <نص>
/send_online <نص>
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
            cur.execute("SELECT user_id, guild_id, role_id FROM premium_users WHERE expiry_time <= ?", (current_time,))
            rows = cur.fetchall()
            for uid, gid, role_id in rows:
                cur.execute("DELETE FROM premium_users WHERE user_id=? AND guild_id=?", (uid, gid))
                db.commit()
        except Exception as e:
            print(f"Error in premium cleanup task: {e}")
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
# MESSAGE EVENT (XP, AUTO REPLY, PROTECTION, ANTI SPAM & LINKS)
# =========================================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if not message.guild:
        return

    gid = str(message.guild.id)
    uid = str(message.author.id)

    # XP System
    cur.execute("SELECT * FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    data = cur.fetchone()

    if data:
        cur.execute("""
        UPDATE xp
        SET messages=messages+1,
        day_count=day_count+1,
        week_count=week_count+1
        WHERE guild_id=? AND user_id=?
        """, (gid, uid))
    else:
        cur.execute("INSERT INTO xp VALUES(?,?,?,?,?)", (gid, uid, 1, 1, 1))

    db.commit()

    # Auto Reply
    for trigger, reply in auto_replies.items():
        if trigger in message.content.lower():
            embed = discord.Embed(description=reply, color=COLOR)
            await message.channel.send(embed=embed)

    # Protection Words
    for word, sec in protection_words.items():
        if word in message.content.lower():
            try:
                await message.delete()
                await message.author.timeout(timedelta(seconds=sec))
                await message.channel.send(f"⛔ {message.author.mention} تم إعطاؤه تايم لمخالفة كلمات الحماية.")
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
# GAMES COMMANDS (MAFIA, CHAIRS)
# =========================================

@bot.command(name="mafia")
async def mafia_game(ctx):
    view = MafiaView(ctx.guild.id)
    max_desc = "*(الحد الأقصى للمشاركين: **15 لاعباً** - ولأعضاء البريميوم حتى **25 لاعباً**)*"
    embed = discord.Embed(
        title="🕵️‍♂️ تسجيل لعبة المافيا",
        description=f"اضغط على زر **(تسجيل 📥)** أدناه للمشاركة في اللعبة.\n{max_desc}",
        color=COLOR
    )
    await ctx.send(embed=embed, view=view)

@bot.command(name="mafia_hint")
async def mafia_hint(ctx):
    if not is_user_premium(ctx.author.id, ctx.guild.id):
        return await ctx.send("❌ هذه الميزة مخصصة لمشتركي البريميوم (Premium) فقط في الألعاب!")

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
            return await ctx.send("❌ لقد استهلكت جميع تلميحاتك الـ 5 المسموحة لهذا اليوم في لعبة المافيا!")
        
        hints_count += 1
        cur.execute("UPDATE mafia_hints_usage SET hints_count=?, last_reset=? WHERE user_id=? AND guild_id=?", (hints_count, last_reset, uid, gid))
    else:
        hints_count = 1
        cur.execute("INSERT INTO mafia_hints_usage VALUES (?, ?, ?, ?)", (uid, gid, hints_count, current_time))
    
    db.commit()

    hints_pool = [
        "💡 تلميح مافيا: راقب الأقوال المتقاطعة، عادةً العضو الهادئ جداً أو المدافع بشراسة دون سبب يكون مشتبهاً به.",
        "💡 تلميح مافيا: التخفي وسط النقاشات العامة وعدم إبداء رأي حاسم يعد أسلوباً شائعاً للمتخفين.",
        "💡 تلميح مافيا: في الجولات المتقدمة، التركيز على تصرفات آخر شخص انضم للنقاش قد يكشف الكثير.",
        "💡 تلميح مافيا: لا توجّه أصابع الاتهام بدون أدلة كلامية واضحة كي لا تبدو مريباً بنفسك.",
        "💡 تلميح مافيا: تذكر دائماً أن توزيع الأدوار يعتمد على الحظ البحت، فثق بحدسك ولا تتسرع بالحكم."
    ]

    selected_hint = random.choice(hints_pool)
    remaining_hints = hints_allowed - hints_count

    embed = discord.Embed(
        title="🕵️‍♂️ تلميح المافيا (ميزة البريميوم)",
        description=f"{selected_hint}\n\n*المتبقي لديك اليوم: **{remaining_hints}** من أصل 5*",
        color=COLOR
    )
    await ctx.send(embed=embed)

@bot.command(name="chairs")
async def chairs_game(ctx):
    view = ChairsView(ctx.author, ctx.guild.id)
    embed = discord.Embed(
        title="🪑 لعبة الكراسي الموسيقية",
        description="اضغط على زر **(جلس على الكرسي 🪑)** للانضمام والمشاركة في اللعبة!",
        color=COLOR
    )
    await ctx.send(embed=embed, view=view)
    
    await asyncio.sleep(15)
    view.stop()

    players = view.players
    if len(players) < 2:
        return await ctx.send("❌ عدد المشاركين قليل جداً لبدء لعبة الكراسي!")

    total_p = len(players)
    current_chairs = max(5, total_p - 5)
    
    await ctx.send(f"🎮 بدأ التحدي! عدد المشاركين: `{total_p}` | عدد الكراسي الحالي: `{current_chairs}`")

    while current_chairs > 5 and len(players) > current_chairs:
        await asyncio.sleep(4)
        random.shuffle(players)
        players = players[:current_chairs]
        current_chairs -= 2
        if current_chairs < 5:
            current_chairs = 5

    await ctx.send(f"⚠️ وصلت اللعبة إلى المرحلة الحاسمة! متبقي `{len(players)}` لاعبين وعدد الكراسي **5**, والآن ستبدأ التصفية الفردية!")

    while len(players) > 1:
        await asyncio.sleep(5)
        loser = random.choice(players)
        players.remove(loser)
        await ctx.send(f"❌ لم يجد الكرسي في الوقت المناسب وتم استبعاده: {loser.mention} | المتبقي: `{len(players)}` لاعبين")

    winner = players[0]
    await ctx.send(f"🏆 مبروك الفائز بلقب ملك الكراسي: {winner.mention} 🎉🎊")

# =========================================
# SUGGESTION COMMAND (!اقتراح)
# =========================================

@bot.command(name="اقتراح")
async def suggestion_command(ctx, *, text: str = None):
    if not text:
        return await ctx.send("❌ يرجى كتابة الاقتراح بجانب الأمر!\nمثال: `!اقتراح إضافة روم صوتي جديد`")

    embed = discord.Embed(
        title="💡 اقتراح جديد",
        description=f"**صاحب الاقتراح:** {ctx.author.mention}\n\n**المضمون:**\n{text}",
        color=COLOR
    )
    embed.set_footer(text=f"ID: {ctx.author.id}")
    
    view = SuggestionView()
    await ctx.message.delete()
    await ctx.send(embed=embed, view=view)

# =========================================
# HELP & COMMANDS LIST
# =========================================

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="Sayanzi bot",
        description="من هنا يمكنك الوصول الى جميع الاوامر للحصول على الخدمة الكاملة من بوت Sayanzi\n\nاستخدم القائمة الموجودة بالأسفل للوصول الى اوامر البوت.",
        color=COLOR
    )
    await ctx.send(embed=embed, view=HelpView())

@bot.tree.command(name="commands", description="عرض لوحة مساعدة بوت Sayanzi")
async def commands_list(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Sayanzi bot",
        description="من هنا يمكنك الوصول الى جميع الاوامر للحصول على الخدمة الكاملة من بوت Sayanzi\n\nاستخدم القائمة الموجودة بالأسفل للوصول الى اوامر البوت.",
        color=COLOR
    )
    await interaction.response.send_message(embed=embed, view=HelpView())

# =========================================
# XP, LEVEL, TOP, PROFILE, INFO COMMANDS
# =========================================

@bot.command()
async def xp(ctx):
    gid = str(ctx.guild.id)
    uid = str(ctx.author.id)

    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    data = cur.fetchone()
    amount = data[0] if data else 0

    embed = discord.Embed(title="⭐ XP", description=f"```{amount}```", color=COLOR)
    await ctx.send(embed=embed)

@bot.tree.command(name="xp", description="عرض نقاط الخبرة XP الخاصة بك")
async def slash_xp(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    uid = str(interaction.user.id)

    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    data = cur.fetchone()
    amount = data[0] if data else 0

    embed = discord.Embed(title="⭐ XP", description=f"```{amount}```", color=COLOR)
    await interaction.response.send_message(embed=embed)

@bot.command()
async def level(ctx):
    gid = str(ctx.guild.id)
    uid = str(ctx.author.id)

    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    data = cur.fetchone()
    amount = data[0] if data else 0
    lvl = amount // 50

    embed = discord.Embed(title="📊 LEVEL", description=f"```{lvl}```", color=COLOR)
    await ctx.send(embed=embed)

@bot.tree.command(name="level", description="عرض مستواك الحالي بالبوت")
async def slash_level(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    uid = str(interaction.user.id)

    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    data = cur.fetchone()
    amount = data[0] if data else 0
    lvl = amount // 50

    embed = discord.Embed(title="📊 LEVEL", description=f"```{lvl}```", color=COLOR)
    await interaction.response.send_message(embed=embed)

@bot.command(name="t")
async def top_command(ctx, mode=None):
    if not check_command_permission(ctx, "t"):
        return await ctx.send("❌ ليس لديك الصلاحية لاستخدام هذا الأمر!")

    gid = str(ctx.guild.id)
    column = "messages"
    title_text = "👑 Months Top"

    if mode == "day":
        column = "day_count"
        title_text = "👑 Top Day"
    elif mode == "week":
        column = "week_count"
        title_text = "👑 Top Week"

    cur.execute(f"SELECT user_id, {column} FROM xp WHERE guild_id=? ORDER BY {column} DESC LIMIT 10", (gid,))
    rows = cur.fetchall()

    embed = discord.Embed(title=f"🏆 {title_text}", color=COLOR)

    for i, (uid, count) in enumerate(rows, start=1):
        embed.add_field(name=f"{i}. <@{uid}>", value=f"💬 {count} نقطة", inline=False)

    await ctx.send(embed=embed)

@bot.command(name="i")
async def profile(ctx, member: discord.Member = None):
    member = member or ctx.author
    gid = str(ctx.guild.id)
    uid = str(member.id)

    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    data = cur.fetchone()
    messages = data[0] if data else 0
    lvl = messages // 50

    created_at = member.created_at.strftime("%Y-%m-%d")
    joined_at = member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "غير معروف"

    embed = discord.Embed(title=f"Profile: {member.name}", color=COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🏷️ الاسم", value=f"`{member}`", inline=False)
    embed.add_field(name="🆔 الآيدي", value=f"`{member.id}`", inline=False)
    embed.add_field(name="📊 المستوى / XP", value=f"المستوى: `{lvl}` | نقاط XP: `{messages}`", inline=False)
    embed.add_field(name="👑 أعلى رتبة", value=member.top_role.mention, inline=False)
    embed.add_field(name="📅 تاريخ إنشاء الحساب", value=f"`{created_at}`", inline=False)
    embed.add_field(name="📥 تاريخ دخول السيرفر", value=f"`{joined_at}`", inline=False)

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
    total_members = guild.member_count
    bots = sum(1 for m in guild.members if m.bot)
    humans = total_members - bots
    online = sum(1 for m in guild.members if m.status != discord.Status.offline)
    offline = total_members - online

    embed = discord.Embed(title=f"🖥 معلومات سيرفر: {guild.name}", color=COLOR)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
        
    embed.add_field(name="👥 إجمالي الأعضاء", value=f"`{total_members}`", inline=True)
    embed.add_field(name="👤 البشر", value=f"`{humans}`", inline=True)
    embed.add_field(name="🤖 البوتات", value=f"`{bots}`", inline=True)
    embed.add_field(name="🟢 المتواجدين (Online)", value=f"`{online}`", inline=True)
    embed.add_field(name="🔴 غير المتواجدين", value=f"`{offline}`", inline=True)
    embed.add_field(name="👑 صاحب السيرفر", value=f"{guild.owner.mention if guild.owner else 'غير معروف'}", inline=False)

    await ctx.send(embed=embed)

# =========================================
# PREMIUM COMMANDS (OWNER)
# =========================================

@bot.command(name="add_premium")
async def add_premium(ctx, member: discord.Member, time_str: str):
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ هذا الأمر مخصص لمالك البوت فقط!")
    
    seconds = parse_time(time_str)
    if not seconds:
        return await ctx.send("❌ صيغة الوقت غير صحيحة (مثال: 30d, 10h)")
    
    expiry = time.time() + seconds

    try:
        cur.execute("INSERT OR REPLACE INTO premium_users (user_id, guild_id, role_id, expiry_time) VALUES (?, ?, ?, ?)", (str(member.id), str(ctx.guild.id), "0", expiry))
        db.commit()
        
        await ctx.send(f"✅ تمت إضافة ميزات البريميوم للألعاب لـ {member.mention} بنجاح لمدة `{time_str}`!")
    except Exception as e:
        await ctx.send(f"❌ حدث خطأ:\n`{e}`")

@bot.command(name="remove_premium")
async def remove_premium(ctx, member: discord.Member):
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ هذا الأمر مخصص لمالك البوت فقط!")
    
    cur.execute("SELECT * FROM premium_users WHERE user_id=? AND guild_id=?", (str(member.id), str(ctx.guild.id)))
    row = cur.fetchone()
    if row:
        cur.execute("DELETE FROM premium_users WHERE user_id=? AND guild_id=?", (str(member.id), str(ctx.guild.id)))
        db.commit()
        await ctx.send(f"✅ تمت إزالة البريميوم من {member.mention}")
    else:
        await ctx.send("❌ هذا العضو ليس لديه بريميوم مسجل في هذا السيرفر.")

# =========================================
# MODERATION COMMANDS (!تحذير, !لاتحذير, !سجل, !clear, !قف, !فت)
# =========================================

@bot.command(name="تحذير")
async def warn(ctx, member: discord.Member):
    if not check_command_permission(ctx, "admin"):
        return await ctx.send("❌ ليس لديك صلاحية استخدام هذا الأمر!")

    gid = str(ctx.guild.id)
    uid = str(member.id)

    cur.execute("SELECT warns FROM warns WHERE guild_id=? AND user_id=?", (gid, uid))
    data = cur.fetchone()

    if data:
        cur.execute("UPDATE warns SET warns=warns+1 WHERE guild_id=? AND user_id=?", (gid, uid))
    else:
        cur.execute("INSERT INTO warns VALUES(?,?,?)", (gid, uid, 1))

    db.commit()
    await ctx.send(f"⚠ تم تحذير العضو {member.mention} بنجاح.")

@bot.command(name="لاتحذير")
async def unwarn(ctx, member: discord.Member):
    if not check_command_permission(ctx, "admin"):
        return await ctx.send("❌ ليس لديك صلاحية استخدام هذا الأمر!")

    gid = str(ctx.guild.id)
    uid = str(member.id)

    cur.execute("""
    UPDATE warns
    SET warns = CASE WHEN warns > 0 THEN warns - 1 ELSE 0 END
    WHERE guild_id=? AND user_id=?
    """, (gid, uid))

    db.commit()
    await ctx.send(f"✅ تمت إزالة تحذير من العضو {member.mention}.")

@bot.command(name="سجل")
async def records_command(ctx, member: discord.Member = None):
    member = member or ctx.author
    gid = str(ctx.guild.id)
    uid = str(member.id)

    cur.execute("SELECT warns FROM warns WHERE guild_id=? AND user_id=?", (gid, uid))
    data = cur.fetchone()
    warn_count = data[0] if data else 0

    embed = discord.Embed(title=f"📋 سجل المخالفات لـ {member.name}", color=COLOR)
    embed.add_field(name="⚠️ عدد التحذيرات", value=f"`{warn_count}` تحذيرات", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="clear", aliases=["مسح"])
async def clear(ctx, amount: int):
    if not check_command_permission(ctx, "admin"):
        return await ctx.send("❌ ليس لديك صلاحية استخدام هذا الأمر!")

    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 تم مسح `{amount}` رسالة بنجاح.")
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except:
        pass

@bot.command(name="قف")
async def lock(ctx):
    if not check_command_permission(ctx, "admin"):
        return await ctx.send("❌ ليس لديك صلاحية استخدام هذا الأمر!")

    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔒 تم قفل الشات بنجاح.")

@bot.command(name="فت")
async def unlock(ctx):
    if not check_command_permission(ctx, "admin"):
        return await ctx.send("❌ ليس لديك صلاحية استخدام هذا الأمر!")

    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔓 تم فتح الشات بنجاح.")

# =========================================
# ADMIN SLASH COMMANDS (BAN, TIMEOUT, ROLES)
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
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message("✅ تم إلغاء حظر العضو بنجاح.")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ أو لم يتم العثور على المستخدم:\n`{e}`", ephemeral=True)

@bot.tree.command(name="timeout", description="إعطاء تايم لعضو لفترة محددة")
async def timeout(interaction: discord.Interaction, member: discord.Member, time: str):
    if not await check_admin_and_hierarchy(interaction, member):
        return
    seconds = parse_time(time)
    if not seconds:
        return await interaction.response.send_message("❌ صيغة الوقت غير صحيحة (مثال: 10m, 1h)", ephemeral=True)
    await member.timeout(timedelta(seconds=seconds))
    await interaction.response.send_message("✅ تم إعطاء التايم للعضو بنجاح.")

@bot.tree.command(name="timeout_remove", description="إزالة التايم عن العضو")
async def timeout_remove(interaction: discord.Interaction, member: discord.Member):
    if not await check_admin_and_hierarchy(interaction, member):
        return
    await member.timeout(None)
    await interaction.response.send_message("✅ تمت إزالة التايم عن العضو بنجاح.")

@bot.tree.command(name="add_role", description="إضافة رتبة لعضو")
async def add_role(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not await check_admin_and_hierarchy(interaction, member):
        return
    await member.add_roles(role)
    await interaction.response.send_message(f"✅ تم إضافة الرتبة {role.mention} لـ {member.mention} بنجاح.")

@bot.tree.command(name="remove_role", description="إزالة رتبة من عضو")
async def remove_role(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not await check_admin_and_hierarchy(interaction, member):
        return
    await member.remove_roles(role)
    await interaction.response.send_message(f"✅ تمت إزالة الرتبة {role.mention} من {member.mention} بنجاح.")

@bot.tree.command(name="message", description="إرسال رسالة رسمية عبر البوت Embed")
async def message(interaction: discord.Interaction, text: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)
    embed = discord.Embed(description=text, color=COLOR)
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ تم إرسال الرسالة بنجاح.", ephemeral=True)

# =========================================
# PROTECTION & AUTO-REPLY SLASH COMMANDS
# =========================================

@bot.tree.command(name="protection", description="إضافة كلمة محظورة لنظام الحماية مع وقت التايم")
@app_commands.describe(word="الكلمة المراد حظرها", time="مدة التايم مثل: 10s أو 5m")
async def protection(interaction: discord.Interaction, word: str, time: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)
    seconds = parse_time(time)
    if not seconds:
        return await interaction.response.send_message("❌ صيغة الوقت غير صحيحة", ephemeral=True)
    protection_words[word.lower()] = seconds
    await interaction.response.send_message(f"✅ تم إضافة كلمة `{word}` لقائمة الحماية بنجاح.", ephemeral=True)

@bot.tree.command(name="protection_remove", description="إزالة كلمة من نظام الحماية")
async def protection_remove(interaction: discord.Interaction, word: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)
    if word.lower() in protection_words:
        del protection_words[word.lower()]
        await interaction.response.send_message(f"✅ تم إزالة كلمة `{word}` من قائمة الحماية.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ هذه الكلمة غير موجودة في القائمة المحظورة.", ephemeral=True)

@bot.tree.command(name="protection_list", description="عرض قائمة كلمات الحماية المحظورة")
async def protection_list(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)
    if not protection_words:
        return await interaction.response.send_message("📋 قائمة كلمات الحماية فارغة حالياً.", ephemeral=True)
    
    words_str = "\n".join([f"• `{w}` (التايم: {s} ثانية)" for w, s in protection_words.items()])
    embed = discord.Embed(title="🛡️ قائمة كلمات الحماية المحظورة", description=words_str, color=COLOR)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="auto_reply", description="إضافة رد تلقائي لكلمة معينة")
@app_commands.describe(trigger="الكلمة المفتاحية", reply="الرد المراد إرساله")
async def auto_reply(interaction: discord.Interaction, trigger: str, reply: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)
    auto_replies[trigger.lower()] = reply
    await interaction.response.send_message(f"✅ تم إضافة الرد التلقائي للكلمة `{trigger}` بنجاح.", ephemeral=True)

@bot.tree.command(name="auto_reply_remove", description="إزالة رد تلقائي مسجل")
async def auto_reply_remove(interaction: discord.Interaction, trigger: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)
    if trigger.lower() in auto_replies:
        del auto_replies[trigger.lower()]
        await interaction.response.send_message(f"✅ تم حذف الرد التلقائي للكلمة `{trigger}`.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ الكلمة المفتاحية غير موجودة.", ephemeral=True)

@bot.tree.command(name="auto_reply_list", description="عرض قائمة الردود التلقائية")
async def auto_reply_list(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)
    if not auto_replies:
        return await interaction.response.send_message("📋 قائمة الردود التلقائية فارغة حالياً.", ephemeral=True)
    
    replies_str = "\n".join([f"• **{t}** ➔ `{r}`" for t, r in auto_replies.items()])
    embed = discord.Embed(title="💬 قائمة الردود التلقائية", description=replies_str, color=COLOR)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# =========================================
# BROADCAST COMMANDS WITH [user]
# =========================================

@bot.tree.command(name="send_all", description="إرسال رسالة برودكاست لجميع الأعضاء مع دعم [user]")
@app_commands.describe(text="النص (استخدم [user] لعمل منشن)")
async def send_all(interaction: discord.Interaction, text: str):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ مخصص لمالك البوت فقط!", ephemeral=True)
    await interaction.response.send_message("⏳ جاري بدء الإرسال...", ephemeral=True)
    success, failed = 0, 0
    for member in interaction.guild.members:
        if member.bot:
            continue
        try:
            personalized_text = text.replace("[user]", member.mention)
            await member.send(personalized_text)
            success += 1
            await asyncio.sleep(3.5)
        except:
            failed += 1
    await interaction.followup.send(f"✅ تم الإرسال بنجاح!\n- نجح: `{success}`\n- فشل: `{failed}`", ephemeral=True)

@bot.tree.command(name="send_online", description="إرسال رسالة برودكاست للأعضاء المتواجدين مع دعم [user]")
@app_commands.describe(text="النص (استخدم [user] لعمل منشن)")
async def send_online(interaction: discord.Interaction, text: str):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ مخصص لمالك البوت فقط!", ephemeral=True)
    await interaction.response.send_message("⏳ جاري بدء الإرسال للأعضاء المتواجدين...", ephemeral=True)
    success, failed = 0, 0
    for member in interaction.guild.members:
        if member.bot or member.status == discord.Status.offline:
            continue
        try:
            personalized_text = text.replace("[user]", member.mention)
            await member.send(personalized_text)
            success += 1
            await asyncio.sleep(3.5)
        except:
            failed += 1
    await interaction.followup.send(f"✅ تم الإرسال بنجاح للأونلاين!\n- نجح: `{success}`\n- فشل: `{failed}`", ephemeral=True)

# =========================================
# RUN BOT
# =========================================

bot.run(TOKEN)

