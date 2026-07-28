# =========================================
# SAYANZI FINAL BOT (UPDATED)
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

# =========================================
# BOT
# =========================================

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    case_insensitive=True,
    help_command=None
)

# =========================================
# DATABASE
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

db.commit()

# =========================================
# CACHE
# =========================================

auto_replies = {}
protection_words = {}
spam_cache = {}

# =========================================
# ADMIN & HIERARCHY CHECK
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

async def check_admin_and_hierarchy(interaction: discord.Interaction, member: discord.Member = None):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)
        return False

    if member:
        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("❌ رتبته اعلى من رتبتي!", ephemeral=True)
            return False

        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ رتبته اعلى من رتبتك!", ephemeral=True)
            return False

    return True

# =========================================
# TIME PARSER
# =========================================

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
# HELP MENU
# =========================================

class HelpSelect(discord.ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label="All members 🔥",
                description="اوامر الاعضاء والمسابقات"
            ),
            discord.SelectOption(
                label="الادارة العليا 👑",
                description="اوامر الادارة والحماية"
            )
        ]

        super().__init__(
            placeholder="قائمة أوامر البوت",
            options=options,
            custom_id="help_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "All members 🔥":
            embed = discord.Embed(
                title="🔥 All Members",
                description=(
                    "𝐒𝐚𝐲𝐚𝐧𝐳𝐢 𝐛𝐨𝐭. 𝐈𝐭'𝐬 𝐚 𝐡𝐞𝐥𝐩 𝐛𝐨𝐭 𝐟𝐨𝐫 𝐬𝐨𝐦𝐞 𝐬𝐞𝐫𝐯𝐞𝐫𝐬; "
                    "𝐢𝐟 𝐲𝐨𝐮 𝐝𝐨𝐧'𝐭 𝐡𝐚𝐯𝐞 𝐚𝐧𝐲𝐭𝐡𝐢𝐧𝐠 𝐭𝐨 𝐡𝐞𝐥𝐩 𝐲𝐨𝐮, 𝐭𝐡𝐢𝐬 𝐢𝐬 𝐭𝐡𝐞 𝐬𝐨𝐥𝐮𝐭𝐢𝐨𝐧.\n"
                    f"Support: {SUPPORT_INVITE}"
                ),
                color=COLOR
            )
            embed.add_field(
                name="📌 Commands",
                value="""
!xp
/xp

!level
/level

!t
!t day
!t week

!i

!help
/commands

!افاتار
!عضو
!سيرفر
!لغز
!اسرع
!كت
""",
                inline=False
            )

            await interaction.response.edit_message(
                embed=embed,
                view=HelpView()
            )

        else:
            embed = discord.Embed(
                title="👑 Admin Commands",
                description=(
                    "𝐒𝐚𝐲𝐚𝐧𝐳𝐢 𝐛𝐨𝐭. 𝐈𝐭'𝐬 𝐚 𝐡𝐞𝐥𝐩 𝐛𝐨𝐭 𝐟𝐨𝐫 𝐬𝐨𝐦𝐞 𝐬𝐞𝐫𝐯𝐞𝐫𝐬; "
                    "𝐢𝐟 𝐲𝐨𝐮 𝐝𝐨𝐧'𝐭 𝐡𝐚𝐯𝐞 𝐚𝐧𝐲𝐭𝐡𝐢𝐧𝐠 𝐭𝐨 𝐡𝐞𝐥𝐩 𝐲𝐨𝐮, 𝐭𝐡𝐢𝐬 𝐢𝐬 𝐭𝐡𝐞 𝐬𝐨𝐥𝐮𝐭𝐢𝐨𝐧.\n"
                    f"Support: {SUPPORT_INVITE}"
                ),
                color=COLOR
            )
            embed.add_field(
                name="🛡 Commands",
                value="""
/ban
/unban

/timeout
/timeout_remove

/add_role
/remove_role

/protection
/protection_remove
/protection_list

/auto_reply
/auto_reply_remove
/auto_reply_list

/message
/giveaway
/send_all
/send_online

!clear
!مسح

!تحذير
!لاتحذير

!قف
!فت
!come @الشخص (للأدمن فقط)
""",
                inline=False
            )

            await interaction.response.edit_message(
                embed=embed,
                view=HelpView()
            )

class HelpView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(HelpSelect())

# =========================================
# GIVEAWAY SYSTEM
# =========================================

class GiveawayView(discord.ui.View):

    def __init__(self, prize, duration):
        super().__init__(timeout=duration)
        self.prize = prize
        self.participants = []

    @discord.ui.button(
        label="🎉 اشترك في الجيف أواي (0)",
        style=discord.ButtonStyle.blurple,
        custom_id="giveaway_btn"
    )
    async def enter_giveaway(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if interaction.user.id in self.participants:
            return await interaction.response.send_message(
                "❌ لقد انضممت مسبقاً لهذا الجيف أواي!",
                ephemeral=True
            )

        self.participants.append(interaction.user.id)
        button.label = f"🎉 اشترك في الجيف أواي ({len(self.participants)})"
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            "✅ تم تسجيل دخولك في السحب بنجاح!",
            ephemeral=True
        )

# =========================================
# READY
# =========================================

@bot.event
async def on_ready():
    await bot.tree.sync()
    bot.add_view(HelpView())
    print(f"✅ Logged in as {bot.user}")

# =========================================
# MESSAGE EVENT
# =========================================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if not message.guild:
        return

    gid = str(message.guild.id)
    uid = str(message.author.id)

    # XP

    cur.execute(
        "SELECT * FROM xp WHERE guild_id=? AND user_id=?",
        (gid, uid)
    )

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
        cur.execute("""
        INSERT INTO xp VALUES(?,?,?,?,?)
        """, (gid, uid, 1, 1, 1))

    db.commit()

    # AUTO REPLY

    for trigger, reply in auto_replies.items():
        if trigger in message.content.lower():
            embed = discord.Embed(
                description=reply,
                color=COLOR
            )
            await message.channel.send(embed=embed)

    # PROTECTION

    for word, sec in protection_words.items():
        if word in message.content.lower():
            try:
                await message.delete()
                await message.author.timeout(
                    timedelta(seconds=sec)
                )
                await message.channel.send(
                    f"⛔ {message.author.mention} تم إعطاؤه تايم"
                )
            except:
                pass

    # ANTI LINKS

    if "http://" in message.content.lower() or "https://" in message.content.lower():
        if not is_admin(message.author, message.guild):
            try:
                await message.delete()
                await message.channel.send(
                    f"🚫 {message.author.mention} الروابط ممنوعة"
                )
            except:
                pass

    # ANTI SPAM

    key = (gid, uid)
    spam_cache[key] = spam_cache.get(key, []) + [time.time()]
    spam_cache[key] = [
        t for t in spam_cache[key]
        if time.time() - t < 3
    ]

    if len(spam_cache[key]) >= 5:
        try:
            await message.author.timeout(
                timedelta(minutes=10),
                reason="Spam"
            )
            await message.channel.send(
                f"⏱ {message.author.mention} سبام"
            )
        except:
            pass
        spam_cache[key] = []

    await bot.process_commands(message)

# =========================================
# HELP
# =========================================

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="Sayanzi Bot",
        description=(
            "𝐒𝐚𝐲𝐚𝐧𝐳𝐢 𝐛𝐨𝐭. 𝐈𝐭'𝐬 𝐚 𝐡𝐞𝐥𝐩 𝐛𝐨𝐭 𝐟𝐨𝐫 𝐬𝐨𝐦𝐞 𝐬𝐞𝐫𝐯𝐞𝐫𝐬; "
            "𝐢𝐟 𝐲𝐨𝐮 𝐝𝐨𝐧'𝐭 𝐡𝐚𝐯𝐞 𝐚𝐧𝐲𝐭𝐡𝐢𝐧𝐠 𝐭𝐨 𝐡𝐞𝐥𝐩 𝐲𝐨𝐮, 𝐭𝐡𝐢𝐬 𝐢𝐬 𝐭𝐡𝐞 𝐬𝐨𝐥𝐮𝐭𝐢𝐨𝐧.\n"
            f"Support: {SUPPORT_INVITE}\n\n"
            "اضغط القائمة لرؤية الأوامر"
        ),
        color=COLOR
    )
    await ctx.send(
        embed=embed,
        view=HelpView()
    )

@bot.tree.command(name="commands")
async def commands_list(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Sayanzi Bot",
        description=(
            "𝐒𝐚𝐲𝐚𝐧𝐳𝐢 𝐛𝐨𝐭. 𝐈𝐭'𝐬 𝐚 𝐡𝐞𝐥𝐩 𝐛𝐨𝐭 𝐟𝐨𝐫 𝐬𝐨𝐦𝐞 𝐬𝐞𝐫𝐯𝐞𝐫𝐬; "
            "𝐢𝐟 𝐲𝐨𝐮 𝐝𝐨𝐧'𝐭 𝐡𝐚𝐯𝐞 𝐚𝐧𝐲𝐭𝐡𝐢𝐧𝐠 𝐭𝐨 𝐡𝐞𝐥𝐩 𝐲𝐨𝐮, 𝐭𝐡𝐢𝐬 𝐢𝐬 𝐭𝐡𝐞 𝐬𝐨𝐥𝐮𝐭𝐢𝐨𝐧.\n"
            f"Support: {SUPPORT_INVITE}\n\n"
            "اضغط القائمة لرؤية الأوامر"
        ),
        color=COLOR
    )
    await interaction.response.send_message(
        embed=embed,
        view=HelpView()
    )

# =========================================
# XP & LEVEL & TOP & PROFILE
# =========================================

@bot.command()
async def xp(ctx):
    gid = str(ctx.guild.id)
    uid = str(ctx.author.id)

    cur.execute("""
    SELECT messages FROM xp
    WHERE guild_id=? AND user_id=?
    """, (gid, uid))

    data = cur.fetchone()
    amount = data[0] if data else 0

    embed = discord.Embed(
        title="⭐ XP",
        description=f"```{amount}```",
        color=COLOR
    )
    await ctx.send(embed=embed)

@bot.tree.command(name="xp")
async def slash_xp(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    uid = str(interaction.user.id)

    cur.execute("""
    SELECT messages FROM xp
    WHERE guild_id=? AND user_id=?
    """, (gid, uid))

    data = cur.fetchone()
    amount = data[0] if data else 0

    embed = discord.Embed(
        title="⭐ XP",
        description=f"```{amount}```",
        color=COLOR
    )
    await interaction.response.send_message(embed=embed)

@bot.command()
async def level(ctx):
    gid = str(ctx.guild.id)
    uid = str(ctx.author.id)

    cur.execute("""
    SELECT messages FROM xp
    WHERE guild_id=? AND user_id=?
    """, (gid, uid))

    data = cur.fetchone()
    amount = data[0] if data else 0
    lvl = amount // 50

    embed = discord.Embed(
        title="📊 LEVEL",
        description=f"```{lvl}```",
        color=COLOR
    )
    await ctx.send(embed=embed)

@bot.tree.command(name="level")
async def slash_level(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    uid = str(interaction.user.id)

    cur.execute("""
    SELECT messages FROM xp
    WHERE guild_id=? AND user_id=?
    """, (gid, uid))

    data = cur.fetchone()
    amount = data[0] if data else 0
    lvl = amount // 50

    embed = discord.Embed(
        title="📊 LEVEL",
        description=f"```{lvl}```",
        color=COLOR
    )
    await interaction.response.send_message(embed=embed)

@bot.command()
async def t(ctx, mode=None):
    gid = str(ctx.guild.id)
    column = "messages"
    title_text = "Months Top 👑"

    if mode == "day":
        column = "day_count"
        title_text = "Top Day 👑"
    elif mode == "week":
        column = "week_count"
        title_text = "Top Week 👑"

    cur.execute(f"""
    SELECT user_id, {column}
    FROM xp
    WHERE guild_id=?
    ORDER BY {column} DESC
    LIMIT 10
    """, (gid,))

    rows = cur.fetchall()

    embed = discord.Embed(
        title=f"🏆 {title_text}",
        color=COLOR
    )

    for i, (uid, count) in enumerate(rows, start=1):
        embed.add_field(
            name=f"{i}. <@{uid}>",
            value=f"💬 {count}",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name="i")
async def profile(ctx, member: discord.Member = None):
    member = member or ctx.author
    gid = str(ctx.guild.id)
    uid = str(member.id)

    cur.execute("""
    SELECT messages FROM xp
    WHERE guild_id=? AND user_id=?
    """, (gid, uid))
    data = cur.fetchone()
    messages = data[0] if data else 0
    lvl = messages // 50

    created_at = member.created_at.strftime("%Y-%m-%d")
    joined_at = member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "غير معروف"

    embed = discord.Embed(
        title=f"Profile: {member.name}",
        color=COLOR
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🏷️ الاسم", value=f"`{member}`", inline=False)
    embed.add_field(name="🆔 الآيدي", value=f"`{member.id}`", inline=False)
    embed.add_field(name="📊 اللفل", value=f"`{lvl}` (XP: {messages})", inline=False)
    embed.add_field(name="👑 أعلى رتبة", value=member.top_role.mention, inline=False)
    embed.add_field(name="📅 تاريخ إنشاء الحساب", value=f"`{created_at}`", inline=False)
    embed.add_field(name="📥 تاريخ دخول السيرفر", value=f"`{joined_at}`", inline=False)

    await ctx.send(embed=embed)

@bot.command(name="افاتار")
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author

    embed = discord.Embed(
        title=f"{member.name}",
        color=COLOR
    )
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="عضو")
async def member_info(ctx, member: discord.Member = None):
    member = member or ctx.author

    embed = discord.Embed(
        title=f"{member}",
        color=COLOR
    )
    embed.add_field(
        name="👑 Rank",
        value=member.top_role.mention
    )
    await ctx.send(embed=embed)

@bot.command(name="سيرفر")
async def server_info(ctx):
    guild = ctx.guild

    embed = discord.Embed(
        title="🖥 Server",
        color=COLOR
    )
    embed.add_field(
        name="👥 Members",
        value=guild.member_count
    )
    await ctx.send(embed=embed)

# =========================================
# GAMES (!come, !لغز, !اسرع, !كت)
# =========================================

@bot.command(name="come")
async def come_command(ctx, member: discord.Member = None):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ هذا الأمر مخصص للأدمنية فقط!")

    if not member:
        return await ctx.send("❌ يرجى منشن الشخص المراد استدعاؤه!")
    
    try:
        embed = discord.Embed(
            title="🔔 استدعاء جديد",
            description=f"تم استدعائك من {ctx.author.mention}\nالى سيرفر (**{ctx.guild.name}**)\nننتظر حضورك",
            color=COLOR
        )
        await member.send(embed=embed)
        await ctx.send("تم ارسال الاستدعاء للشخص ! ✔️")
    except:
        await ctx.send("❌ تعذر إرسال رسالة خاصة لهذا الشخص (قد يكون مغلق الخاص).")

RIDDLES = [
    {"riddle": "ما هو الشيء الذي كلما أخذت منه كبر وكلما وضعت فيه صغر؟", "answer": "الحفرة"},
    {"riddle": "له أوراق وليس بنبات، وله جلد وليس بحيوان، وعلم وليس بإنسان، فمن يكون؟", "answer": "الكتاب"},
    {"riddle": "ما هو الباب الذي لا يمكن فتحه؟", "answer": "الباب المفتوح"},
    {"riddle": "يسير بلا رجلين ولا يدخل إلا للأذنين فما هو؟", "answer": "الصوت"},
    {"riddle": "ما هو الشيء الذي يوجد في وسط مكة؟", "answer": "حرف الكاف"}
]

@bot.command(name="لغز")
async def play_riddle(ctx):
    selected = random.choice(RIDDLES)
    
    embed = discord.Embed(
        title="🧩 لعبة الألغاز والتحدي",
        description=f"**{selected['riddle']}**\n\n⏱️ لديك 30 ثانية للإجابة هنا في الشات!",
        color=COLOR
    )
    await ctx.send(embed=embed)

    def check(m):
        return m.channel.id == ctx.channel.id and not m.author.bot and selected['answer'] in m.content

    start_time = time.time()
    try:
        msg = await bot.wait_for('message', timeout=30.0, check=check)
        duration = round(time.time() - start_time, 1)

        winner_embed = discord.Embed(
            title="🎉 You Win!",
            description=f"مبروك {msg.author.mention}! لقد فزت بالإجابة الصحيحة وهي: **{selected['answer']}**",
            color=0x00ff00
        )
        winner_embed.add_field(name="⏱️ المدة المستغرقـة", value=f"`{duration} ثانية`", inline=False)
        await ctx.send(embed=winner_embed)
    except asyncio.TimeoutError:
        timeout_embed = discord.Embed(
            title="⏰ انتهى الوقت!",
            description=f"لم يقم أحد بالإجابة الصحيحة. الإجابة كانت: **{selected['answer']}**",
            color=0xff0000
        )
        await ctx.send(embed=timeout_embed)

FAST_WORDS = ["ديسكورد", "برمجة", "بايثون", "تطوير", "سيرفر", "العاب", "تحدي", "سرعة", "حاسوب", "ذكاء"]

@bot.command(name="اسرع")
async def play_fast(ctx):
    word = random.choice(FAST_WORDS)
    
    embed = discord.Embed(
        title="⚡ لعبة الأسرع",
        description=f"اكتب هذه الكلمة بأسرع ما يمكن: **`{word}`**\n\n⏱️ لديك 20 ثانية!",
        color=COLOR
    )
    await ctx.send(embed=embed)

    def check(m):
        return m.channel.id == ctx.channel.id and not m.author.bot and m.content.strip() == word

    start_time = time.time()
    try:
        msg = await bot.wait_for('message', timeout=20.0, check=check)
        duration = round(time.time() - start_time, 1)

        winner_embed = discord.Embed(
            title="🏆 أسرع شخص!",
            description=f"كفو {msg.author.mention}! كنت الأسرع في كتابة الكلمة.",
            color=0x00ff00
        )
        winner_embed.add_field(name="⏱️ الوقت المستغرق", value=f"`{duration} ثانية`", inline=False)
        await ctx.send(embed=winner_embed)
    except asyncio.TimeoutError:
        await ctx.send(f"⏰ انتهى الوقت ولم يكتب أحد الكلمة (`{word}`) بالسرعة المطلوبة!")

QUESTIONS = [
    "ماذا تريد أن تفعل في المستقبل؟",
    "ما هي أكلتك المفضلة؟",
    "لو ملكت العالم ليوم واحد، ماذا ستفعل أولاً؟",
    "ما هي أكثر لعبة توتر الأعصاب بالنسبة لك؟",
    "هل تستخدم الهاتف أكثر أم الحاسوب؟",
    "ما هي هوايتك المفضلة بعيداً عن الألعاب والنت؟"
]

@bot.command(name="كت")
async def play_cat(ctx):
    question = random.choice(QUESTIONS)
    embed = discord.Embed(
        title="💬 كت تويت (اسئلة عامة)",
        description=f"**{question}**",
        color=COLOR
    )
    await ctx.send(embed=embed)

# =========================================
# MODERATION (WARNINGS, CLEAR, LOCK)
# =========================================

@bot.command(name="تحذير")
async def warn(ctx, member: discord.Member):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.")

    if member.top_role >= ctx.guild.me.top_role:
        return await ctx.send("❌ رتبته اعلى من رتبتي!")

    if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
        return await ctx.send("❌ رتبته اعلى من رتبتك!")

    gid = str(ctx.guild.id)
    uid = str(member.id)

    cur.execute("""
    SELECT warns FROM warns
    WHERE guild_id=? AND user_id=?
    """, (gid, uid))

    data = cur.fetchone()

    if data:
        cur.execute("""
        UPDATE warns
        SET warns=warns+1
        WHERE guild_id=? AND user_id=?
        """, (gid, uid))
    else:
        cur.execute("""
        INSERT INTO warns VALUES(?,?,?)
        """, (gid, uid, 1))

    db.commit()
    await ctx.send(f"⚠ تم تحذير {member.mention}")

@bot.command(name="لاتحذير")
async def unwarn(ctx, member: discord.Member):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.")

    gid = str(ctx.guild.id)
    uid = str(member.id)

    cur.execute("""
    UPDATE warns
    SET warns = CASE
        WHEN warns > 0 THEN warns - 1
        ELSE 0
    END
    WHERE guild_id=? AND user_id=?
    """, (gid, uid))

    db.commit()
    await ctx.send(f"✅ تمت إزالة تحذير من {member.mention}")

@bot.command(name="سجل")
async def warns_log(ctx, member: discord.Member = None):
    member = member or ctx.author
    gid = str(ctx.guild.id)
    uid = str(member.id)

    cur.execute("""
    SELECT warns FROM warns
    WHERE guild_id=? AND user_id=?
    """, (gid, uid))

    data = cur.fetchone()
    warns = data[0] if data else 0

    await ctx.send(
        f"⚠ {member.mention} لديه `{warns}` تحذير"
    )

@bot.command(name="clear", aliases=["مسح"])
async def clear(ctx, amount: int):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.")

    await ctx.channel.purge(limit=amount + 1)

@bot.command(name="قف")
async def lock(ctx):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.")

    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False

    await ctx.channel.set_permissions(
        ctx.guild.default_role,
        overwrite=overwrite
    )
    await ctx.send("🔒 تم قفل الشات")

@bot.command(name="فت")
async def unlock(ctx):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.")

    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True

    await ctx.channel.set_permissions(
        ctx.guild.default_role,
        overwrite=overwrite
    )
    await ctx.send("🔓 تم فتح الشات")

# =========================================
# ADMIN SLASH COMMANDS
# =========================================

@bot.tree.command(name="ban")
async def ban(
    interaction: discord.Interaction,
    member: discord.Member
):
    if not await check_admin_and_hierarchy(interaction, member):
        return

    await member.ban()
    await interaction.response.send_message("✅ تم")

@bot.tree.command(name="unban")
async def unban(
    interaction: discord.Interaction,
    user_id: str
):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)

    user = await bot.fetch_user(int(user_id))
    await interaction.guild.unban(user)
    await interaction.response.send_message("✅ تم")

@bot.tree.command(name="timeout")
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    time: str
):
    if not await check_admin_and_hierarchy(interaction, member):
        return

    seconds = parse_time(time)
    if not seconds:
        return await interaction.response.send_message("❌ صيغة الوقت غير صحيحة", ephemeral=True)

    await member.timeout(
        timedelta(seconds=seconds)
    )
    await interaction.response.send_message("✅ تم")

@bot.tree.command(name="timeout_remove")
async def timeout_remove(
    interaction: discord.Interaction,
    member: discord.Member
):
    if not await check_admin_and_hierarchy(interaction, member):
        return

    await member.timeout(None)
    await interaction.response.send_message("✅ تم")

@bot.tree.command(name="add_role")
async def add_role(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role
):
    if not await check_admin_and_hierarchy(interaction, member):
        return

    if role >= interaction.guild.me.top_role:
        return await interaction.response.send_message("❌ هذه الرتبة اعلى من رتبتي!", ephemeral=True)

    await member.add_roles(role)
    await interaction.response.send_message("✅ تم")

@bot.tree.command(name="remove_role")
async def remove_role(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role
):
    if not await check_admin_and_hierarchy(interaction, member):
        return

    if role >= interaction.guild.me.top_role:
        return await interaction.response.send_message("❌ هذه الرتبة اعلى من رتبتي!", ephemeral=True)

    await member.remove_roles(role)
    await interaction.response.send_message("✅ تم")

@bot.tree.command(name="message")
async def message(
    interaction: discord.Interaction,
    text: str
):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)

    embed = discord.Embed(
        description=text,
        color=COLOR
    )
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ تم", ephemeral=True)

@bot.tree.command(name="giveaway")
@app_commands.describe(time="مدة الجيف اواي مثل 10s أو 5m أو 1h", winner="عدد الفائزين", give="جائزة المسابقة مثل 500k")
async def giveaway_slash(
    interaction: discord.Interaction,
    time: str,
    winner: int,
    give: str
):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ ليس لديك صلاحية Administrator.", ephemeral=True)

    seconds = parse_time(time)
    if not seconds:
        return await interaction.response.send_message("❌ صيغة الوقت غير صحيحة (مثال: 30s, 10m, 1h)", ephemeral=True)

    view = GiveawayView(give, seconds)
    
    embed = discord.Embed(
        title="🎉 GIVEAWAY 🎉",
        description=f"🎁 **{give}**\n\n👑 Hosted by {interaction.user.mention}\n👥 Winners: `{winner}`\n⏱️ Duration: `{time}`\n\nاضغط على الزر أدناه للمشاركة!",
        color=COLOR
    )
    
    await interaction.response.send_message("✅ تم بدء الجيف أواي بنجاح!", ephemeral=True)
    msg = await interaction.channel.send(embed=embed, view=view)

    await asyncio.sleep(seconds)

    if not view.participants:
        return await msg.edit(content="❌ انتهى الجيف أواي ولم يشارك أحد!", view=None)

    actual_winners = min(winner, len(view.participants))
    winners_ids = random.sample(view.participants, actual_winners)
    winners_mentions = ", ".join([f"<@{uid}>" for uid in winners_ids])

    winner_embed = discord.Embed(
        title="🏆 انتهى الجيف أواي!",
        description=f"الفائزون بالجائزة **{give}** هم: {winners_mentions} 🎉\n👑 Hosted by {interaction.user.mention}",
        color=0x00ff00
    )
    await msg.edit(embed=winner_embed, view=None)
    await interaction.channel.send(f"مبروك {winners_mentions} لقد فزتم بـ **{give}**! 🎊")

# =========================================
# BROADCAST COMMANDS (/send_all, /send_online) [With Anti-Spam Delay]
# =========================================

@bot.tree.command(name="send_all", description="إرسال رسالة برودكاست لجميع أعضاء السيرفر بالخاص")
@app_commands.describe(text="النص المراد إرساله")
async def send_all(interaction: discord.Interaction, text: str):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ هذا الأمر مخصص لمالك البوت الأساسي فقط!", ephemeral=True)

    await interaction.response.send_message("⏳ جاري بدء إرسال الرسالة لجميع الأعضاء (مع فاصل زمني للأمان 3.5 ثانية)...", ephemeral=True)
    
    success = 0
    failed = 0
    
    for member in interaction.guild.members:
        if member.bot:
            continue
        try:
            embed = discord.Embed(
                title=f"📢 رسالة إدارية من سيرفر {interaction.guild.name}",
                description=text,
                color=COLOR
            )
            await member.send(embed=embed)
            success += 1
            await asyncio.sleep(3.5)
        except:
            failed += 1

    await interaction.followup.send(f"✅ تم الإرسال بنجاح!\n- تم الإرسال إلى: `{success}` عضو\n- فشل الإرسال إلى: `{failed}` عضو", ephemeral=True)

@bot.tree.command(name="send_online", description="إرسال رسالة برودكاست للأعضاء المتواجدين (Online) فقط بالخاص")
@app_commands.describe(text="النص المراد إرساله")
async def send_online(interaction: discord.Interaction, text: str):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ هذا الأمر مخصص لمالك البوت الأساسي فقط!", ephemeral=True)

    await interaction.response.send_message("⏳ جاري بدء إرسال الرسالة للأعضاء المتواجدين (مع فاصل زمني للأمان 3.5 ثانية)...", ephemeral=True)
    
    success = 0
    failed = 0
    
    for member in interaction.guild.members:
        if member.bot:
            continue
        if member.status == discord.Status.offline:
            continue
        try:
            embed = discord.Embed(
                title=f"📢 رسالة إدارية من سيرفر {interaction.guild.name}",
                description=text,
                color=COLOR
            )
            await member.send(embed=embed)
            success += 1
            await asyncio.sleep(3.5)
        except:
            failed += 1

    await interaction.followup.send(f"✅ تم الإرسال بنجاح!\n- تم الإرسال إلى: `{success}` عضو أونلاين\n- فشل الإرسال إلى: `{failed}` عضو", ephemeral=True)

# =========================================
# PROTECTION & AUTO REPLY CONFIGURATION
# =========================================

@bot.tree.command(name="protection")
async def protection(
    interaction: discord.Interaction,
    word: str,
    time: str
):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)

    seconds = parse_time(time)
    if not seconds:
        return await interaction.response.send_message("❌ صيغة الوقت غير صحيحة", ephemeral=True)

    protection_words[word.lower()] = seconds
    await interaction.response.send_message("✅ تم")

@bot.tree.command(name="protection_remove")
async def protection_remove(
    interaction: discord.Interaction,
    word: str
):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)

    protection_words.pop(word.lower(), None)
    await interaction.response.send_message("✅ تم")

@bot.tree.command(name="protection_list")
async def protection_list(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)

    if not protection_words:
        return await interaction.response.send_message("❌ لا توجد كلمات")

    text = ""
    for word, sec in protection_words.items():
        text += f"🔹 {word} = {sec}s\n"

    embed = discord.Embed(
        title="🛡 Protection List",
        description=text,
        color=COLOR
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="auto_reply")
async def auto_reply(
    interaction: discord.Interaction,
    trigger: str,
    reply: str
):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)

    auto_replies[trigger.lower()] = reply
    await interaction.response.send_message("✅ تم")

@bot.tree.command(name="auto_reply_remove")
async def auto_reply_remove(
    interaction: discord.Interaction,
    trigger: str
):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)

    auto_replies.pop(trigger.lower(), None)
    await interaction.response.send_message("✅ تم")

@bot.tree.command(name="auto_reply_list")
async def auto_reply_list(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ لا يمكنك فعل ذلك، ليس لديك صلاحية Administrator.", ephemeral=True)

    if not auto_replies:
        return await interaction.response.send_message("❌ لا توجد ردود")

    text = ""
    for trigger, reply in auto_replies.items():
        text += f"🔹 {trigger} => {reply}\n"

    embed = discord.Embed(
        title="🤖 Auto Replies",
        description=text,
        color=COLOR
    )
    await interaction.response.send_message(embed=embed)

# =========================================
# RUN
# =========================================

bot.run(TOKEN)


