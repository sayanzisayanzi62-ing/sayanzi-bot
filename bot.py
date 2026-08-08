# =========================================
# LUNEX FINAL BOT (MULTI-LANGUAGE & PERMISSIONS)
# discord.py 2.x
# =========================================

import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
import asyncio
import sqlite3
import time
import io
import os

TOKEN = os.getenv("TOKEN")

COLOR = 0x8000ff
OWNER_ID = 1446592341908652112
SUPPORT_INVITE = "https://discord.gg/FMEXcwAvg"
BOT_INVITE = "https://discord.com/oauth2/authorize?client_id=1501541120058851348&permissions=8&integration_type=0&scope=bot"
WEBSITE_LINK = "https://lunexbot.netlify.app"

# =========================================
# BOT INTENTS SETUP
# =========================================

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=["!", "#"],
    intents=intents,
    case_insensitive=True,
    help_command=None
)

# =========================================
# DATABASE INITIALIZATION
# =========================================

db = sqlite3.connect("lunex.db")
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
CREATE TABLE IF NOT EXISTS server_settings(
guild_id TEXT PRIMARY KEY,
t_role_id TEXT,
admin_role_id TEXT,
lang TEXT DEFAULT 'en'
)
""")

db.commit()

# =========================================
# CACHE & LOCALIZATION
# =========================================

auto_replies = {}
badword_words = {}
spam_cache = {}

locales = {
    "en": {
        "lang_set": "✅ Language has been set to English.",
        "higher_bot": "❌ Their role is higher than or equal to mine!",
        "higher_user": "❌ Their role is higher than or equal to yours!",
        "banned": "✅ Member banned successfully.",
        "unbanned": "✅ User unbanned.",
        "invalid_time": "❌ Invalid time format (e.g., 10m, 1h).",
        "timeout_applied": "✅ Timeout applied successfully.",
        "timeout_removed": "✅ Timeout removed.",
        "channel_locked": "🔒 Channel locked successfully.",
        "channel_unlocked": "🔓 Channel unlocked successfully.",
        "role_added": "✅ Role added successfully.",
        "role_removed": "✅ Role removed successfully.",
        "cleared": "🧹 Cleared `{}` messages.",
        "error": "❌ Error:",
        "help_desc": "Our bot is advanced with powerful and scientific features\nBot commands are available here\nTo learn more, visit us:\nhttps://lunexbot.netlify.app",
        "all_member_title": "👥 All Member Commands",
        "staff_member_title": "👑 Staff Member Commands",
        "general_xp": "📌 General & XP",
        "mod_sec": "🛡️ Moderation & Security"
    },
    "ar": {
        "lang_set": "✅ تم تعيين لغة البوت إلى العربية.",
        "higher_bot": "❌ رتبة هذا العضو أعلى من رتبتي أو مساوية لها!",
        "higher_user": "❌ رتبة هذا العضو أعلى من رتبتك أو مساوية لها!",
        "banned": "✅ تم حظر العضو بنجاح.",
        "unbanned": "✅ تم فك الحظر عن المستخدم.",
        "invalid_time": "❌ صيغة الوقت غير صحيحة (مثال: 10m, 1h).",
        "timeout_applied": "✅ تم إعطاء العضو تايم أوت بنجاح.",
        "timeout_removed": "✅ تم إزالة التايم أوت عن العضو.",
        "channel_locked": "🔒 تم قفل القناة بنجاح.",
        "channel_unlocked": "🔓 تم فتح القناة بنجاح.",
        "role_added": "✅ تم إعطاء الرتبة بنجاح.",
        "role_removed": "✅ تم سحب الرتبة بنجاح.",
        "cleared": "🧹 تم مسح `{}` رسالة.",
        "error": "❌ حدث خطأ:",
        "help_desc": "بوتنا متطور باشياء قوية وعلمية\nاوامر البوت موجودة هنا\nلمعرفة المزيد زورنا\nhttps://lunexbot.netlify.app",
        "all_member_title": "👥 أوامر الأعضاء",
        "staff_member_title": "👑 أوامر الإدارة",
        "general_xp": "📌 الأوامر العامة ونقاط الخبرة",
        "mod_sec": "🛡️ الإشراف والحماية"
    }
}

def get_lang(guild_id: str) -> str:
    cur.execute("SELECT lang FROM server_settings WHERE guild_id=?", (str(guild_id),))
    row = cur.fetchone()
    if row and row[0] in locales:
        return row[0]
    return "en"

def t(guild_id: str, key: str, *args) -> str:
    lang = get_lang(guild_id)
    text = locales[lang].get(key, key)
    if args:
        return text.format(*args)
    return text

# =========================================
# PERMISSIONS & HIERARCHY CHECKS
# =========================================

async def check_hierarchy(interaction: discord.Interaction, member: discord.Member):
    gid = str(interaction.guild.id)
    if member.top_role >= interaction.guild.me.top_role:
        await interaction.response.send_message(t(gid, "higher_bot"), ephemeral=True)
        return False

    if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message(t(gid, "higher_user"), ephemeral=True)
        return False

    return True

def parse_time(t_str):
    try:
        value = int(t_str[:-1])
        unit = t_str[-1].lower()
        if unit == "s": return value
        elif unit == "m": return value * 60
        elif unit == "h": return value * 3600
        elif unit == "d": return value * 86400
    except:
        return None
    return None

# =========================================
# HELP MENU INTERACTIVE
# =========================================

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="All member", description="Member commands & XP", emoji="👥"),
            discord.SelectOption(label="Staff member", description="Administration and security commands", emoji="👑")
        ]
        super().__init__(placeholder="Select desired category", options=options, custom_id="help_select")

    async def callback(self, interaction: discord.Interaction):
        gid = str(interaction.guild.id)
        if self.values[0] == "All member":
            embed = discord.Embed(title=t(gid, "all_member_title"), color=COLOR)
            embed.add_field(name=t(gid, "general_xp"), value="!xp / /xp | !level / /level\n!t | !t day | !t week\n!i [member] | !عضو | !افاتار | !سيرفر\n/commands", inline=False)
            await interaction.response.edit_message(embed=embed, view=HelpView())

        elif self.values[0] == "Staff member":
            embed = discord.Embed(title=t(gid, "staff_member_title"), color=COLOR)
            embed.add_field(name=t(gid, "mod_sec"), value="/language\n/unwarn @member | !سجل @member\n!clear <number> / !مسح <number>\n/lock | /open\n/ban | /unban\n/timeout | /timeout_remove\n/add_role | /remove_role\n/badword | /auto_reply | /protection | /welcom_join", inline=False)
            await interaction.response.edit_message(embed=embed, view=HelpView())

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(HelpSelect())
        self.add_item(discord.ui.Button(label="Add Bot", emoji="🔗", url=BOT_INVITE, style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="Support", emoji="💬", url=SUPPORT_INVITE, style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="Website", emoji="🌐", url=WEBSITE_LINK, style=discord.ButtonStyle.link))

# =========================================
# BACKGROUND TASKS & EVENTS
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

@bot.event
async def on_ready():
    await bot.tree.sync()
    bot.add_view(HelpView())
    bot.loop.create_task(check_expired_premiums())
    print(f"✅ Lunex Bot Logged in as {bot.user}")

@bot.event
async def on_member_join(member):
    cur.execute("SELECT message FROM welcome_settings WHERE guild_id=?", (str(member.guild.id),))
    row = cur.fetchone()
    if not row:
        return
    
    msg_template = row[0]
    final_text = msg_template.replace("[user]", member.mention)

    if "[ing]" in final_text:
        final_text = final_text.replace("[ing]", "")
        try:
            avatar_bytes = await member.display_avatar.read()
            file = discord.File(io.BytesIO(avatar_bytes), filename="avatar.png")
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

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    gid = str(message.guild.id)
    uid = str(message.author.id)
    is_admin = message.author.guild_permissions.administrator

    cur.execute("SELECT * FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    if cur.fetchone():
        cur.execute("UPDATE xp SET messages=messages+1, day_count=day_count+1, week_count=week_count+1 WHERE guild_id=? AND user_id=?", (gid, uid))
    else:
        cur.execute("INSERT INTO xp VALUES(?,?,?,?,?)", (gid, uid, 1, 1, 1))
    db.commit()

    for trigger, reply in auto_replies.items():
        if trigger in message.content.lower():
            await message.channel.send(embed=discord.Embed(description=reply, color=COLOR))

    if not is_admin:
        for word, sec in badword_words.items():
            if word in message.content.lower():
                try:
                    await message.delete()
                    await message.author.timeout(timedelta(seconds=sec))
                    await message.channel.send(f"⛔ {message.author.mention} has been timed out for using forbidden words.")
                except:
                    pass

        if "http://" in message.content.lower() or "https://" in message.content.lower():
            try:
                await message.delete()
                await message.channel.send(f"🚫 {message.author.mention} Links are not allowed in this server!")
            except:
                pass

        key = (gid, uid)
        spam_cache[key] = spam_cache.get(key, []) + [time.time()]
        spam_cache[key] = [t_ for t_ in spam_cache[key] if time.time() - t_ < 3]

        if len(spam_cache[key]) >= 5:
            try:
                await message.author.timeout(timedelta(minutes=10), reason="Spamming")
                await message.channel.send(f"⏱ {message.author.mention} You have been timed out for spamming.")
            except:
                pass
            spam_cache[key] = []

    await bot.process_commands(message)

# =========================================
# LANGUAGE COMMAND
# =========================================

@bot.tree.command(name="language", description="Change bot language for this server")
@app_commands.describe(lang="Choose language")
@app_commands.choices(lang=[
    app_commands.Choice(name="English", value="en"),
    app_commands.Choice(name="العربية", value="ar")
])
@app_commands.default_permissions(manage_guild=True)
async def set_language(interaction: discord.Interaction, lang: str):
    gid = str(interaction.guild.id)
    cur.execute("INSERT INTO server_settings (guild_id, lang) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET lang=?", (gid, lang, lang))
    db.commit()
    await interaction.response.send_message(t(gid, "lang_set"), ephemeral=True)

# =========================================
# SETTINGS & PROTECTION SLASH COMMANDS
# =========================================

@bot.tree.command(name="welcom_join", description="Set custom welcome message")
@app_commands.default_permissions(manage_guild=True)
async def welcom_join(interaction: discord.Interaction, message: str):
    gid = str(interaction.guild.id)
    cur.execute("INSERT OR REPLACE INTO welcome_settings VALUES (?, ?)", (gid, message))
    db.commit()
    await interaction.response.send_message(embed=discord.Embed(title="✅ Saved", description=message, color=COLOR))

@bot.tree.command(name="protection", description="Add protection settings")
@app_commands.default_permissions(manage_guild=True)
async def protection_config(interaction: discord.Interaction, feature: str, status: str):
    await interaction.response.send_message(f"✅ `{feature}` ➔ `{status}`", ephemeral=True)

# =========================================
# INFO, HELP & XP
# =========================================

@bot.command(name="help")
async def help_command(ctx):
    gid = str(ctx.guild.id)
    embed = discord.Embed(title="Lunex Bot", description=t(gid, "help_desc"), color=COLOR)
    await ctx.send(embed=embed, view=HelpView())

@bot.tree.command(name="commands", description="Display bot commands")
async def commands_list(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    embed = discord.Embed(title="Lunex Bot", description=t(gid, "help_desc"), color=COLOR)
    await interaction.response.send_message(embed=embed, view=HelpView(), ephemeral=True)

@bot.command()
async def xp(ctx):
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(ctx.author.id)))
    row = cur.fetchone()
    await ctx.send(embed=discord.Embed(title="⭐ XP", description=f"```{row[0] if row else 0}```", color=COLOR))

@bot.command()
async def level(ctx):
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(ctx.author.id)))
    row = cur.fetchone()
    await ctx.send(embed=discord.Embed(title="📊 LEVEL", description=f"```{(row[0] if row else 0) // 50}```", color=COLOR))

@bot.command(name="i")
async def profile(ctx, member: discord.Member = None):
    member = member or ctx.author
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(member.id)))
    msgs = cur.fetchone()[0] if cur.fetchone() else 0
    embed = discord.Embed(title=f"Profile: {member.name}", color=COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🆔 ID", value=f"`{member.id}`", inline=False)
    embed.add_field(name="📊 Level", value=f"`{msgs // 50}`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="سيرفر")
async def server_info(ctx):
    embed = discord.Embed(title=f"🖥 {ctx.guild.name}", color=COLOR)
    if ctx.guild.icon: embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.add_field(name="👥 Members", value=f"`{ctx.guild.member_count}`")
    await ctx.send(embed=embed)

# =========================================
# MODERATION COMMANDS (Text)
# =========================================

@bot.command(name="سجل")
@commands.has_permissions(manage_messages=True)
async def records_command(ctx, member: discord.Member = None):
    member = member or ctx.author
    cur.execute("SELECT warns FROM warns WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(member.id)))
    row = cur.fetchone()
    await ctx.send(embed=discord.Embed(title=f"📋 Records for {member.name}", description=f"⚠️ Warnings: `{row[0] if row else 0}`", color=COLOR))

@bot.command(name="clear", aliases=["مسح"])
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    gid = str(ctx.guild.id)
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(t(gid, "cleared", amount))
    await asyncio.sleep(3)
    try: await msg.delete()
    except: pass

# =========================================
# MODERATION SLASH COMMANDS (PERMISSIONS)
# =========================================

@bot.tree.command(name="ban", description="Ban a member")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member):
    if not await check_hierarchy(interaction, member): return
    await member.ban()
    await interaction.response.send_message(t(str(interaction.guild.id), "banned"))

@bot.tree.command(name="unban", description="Unban a user by ID")
@app_commands.default_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str):
    gid = str(interaction.guild.id)
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(t(gid, "unbanned"))
    except Exception as e:
        await interaction.response.send_message(f"{t(gid, 'error')} `{e}`", ephemeral=True)

@bot.tree.command(name="lock", description="Lock channel")
@app_commands.default_permissions(manage_channels=True)
async def lock_slash(interaction: discord.Interaction):
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message(t(str(interaction.guild.id), "channel_locked"))

@bot.tree.command(name="open", description="Unlock channel")
@app_commands.default_permissions(manage_channels=True)
async def open_slash(interaction: discord.Interaction):
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = True
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message(t(str(interaction.guild.id), "channel_unlocked"))

@bot.tree.command(name="timeout", description="Timeout a member")
@app_commands.default_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, time: str):
    gid = str(interaction.guild.id)
    if not await check_hierarchy(interaction, member): return
    secs = parse_time(time)
    if not secs: return await interaction.response.send_message(t(gid, "invalid_time"), ephemeral=True)
    await member.timeout(timedelta(seconds=secs))
    await interaction.response.send_message(t(gid, "timeout_applied"))

@bot.tree.command(name="timeout_remove", description="Remove timeout")
@app_commands.default_permissions(moderate_members=True)
async def timeout_remove(interaction: discord.Interaction, member: discord.Member):
    gid = str(interaction.guild.id)
    if not await check_hierarchy(interaction, member): return
    await member.timeout(None)
    await interaction.response.send_message(t(gid, "timeout_removed"))

@bot.tree.command(name="add_role", description="Add a role")
@app_commands.default_permissions(manage_roles=True)
async def add_role(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not await check_hierarchy(interaction, member): return
    await member.add_roles(role)
    await interaction.response.send_message(t(str(interaction.guild.id), "role_added"))

@bot.tree.command(name="remove_role", description="Remove a role")
@app_commands.default_permissions(manage_roles=True)
async def remove_role(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not await check_hierarchy(interaction, member): return
    await member.remove_roles(role)
    await interaction.response.send_message(t(str(interaction.guild.id), "role_removed"))

# =========================================
# BADWORD & AUTO-REPLY
# =========================================

@bot.tree.command(name="badword", description="Add banned word")
@app_commands.default_permissions(manage_guild=True)
async def badword(interaction: discord.Interaction, word: str, time: str):
    secs = parse_time(time)
    if not secs: return await interaction.response.send_message(t(str(interaction.guild.id), "invalid_time"), ephemeral=True)
    badword_words[word.lower()] = secs
    await interaction.response.send_message(f"✅ Added `{word}`", ephemeral=True)

@bot.tree.command(name="auto_reply", description="Add auto reply")
@app_commands.default_permissions(manage_guild=True)
async def auto_reply(interaction: discord.Interaction, trigger: str, reply: str):
    auto_replies[trigger.lower()] = reply
    await interaction.response.send_message(f"✅ Added auto-reply for `{trigger}`", ephemeral=True)

# =========================================
# RUN BOT
# =========================================

bot.run(TOKEN)

