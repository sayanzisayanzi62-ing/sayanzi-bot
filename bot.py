# =========================================
# LUNEX BOT — MULTI-LANGUAGE + WEBSITE INTEGRATION + LEADERBOARDS
# discord.py 2.x
# =========================================

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import timedelta, datetime, timezone
import asyncio
import sqlite3
import time
import io
import os
import certifi

from pymongo import MongoClient

# =========================================
# CONFIG
# =========================================

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

COLOR = 0x8000ff
OWNER_ID = 1446592341908652112
SUPPORT_INVITE = "https://discord.gg/FMEXcwAvg"
BOT_INVITE = "https://discord.com/oauth2/authorize?client_id=1501541120058851348&permissions=8&integration_type=0&scope=bot"
SITE_URL = os.getenv("FRONTEND_URL", "https://lunexbot.netlify.app")

# =========================================
# MONGODB (نفس قاعدة بيانات الموقع)
# =========================================

_mongo = MongoClient(os.environ["MONGODB_URI"], tlsCAFile=certifi.where())
_mdb = _mongo.get_default_database()
guild_settings = _mdb["guildsettings"]

DEFAULT_SETTINGS = {
    "welcome": {"enabled": False, "channelId": None, "message": "اهلا [User] فيك بالسيرفر! [Img]"},
    "leave": {"enabled": False, "channelId": None, "message": "وداعا [User] :( [Img]"},
    "ticket": {
        "enabled": False, "image": "",
        "message": "اضغط الزر بالأسفل لفتح تكت جديد",
        "description": "مرحبا [User]، فريق الدعم راح يرد عليك قريبا",
        "categoryId": None, "channelId": None
    },
    "autoReplies": [],
    "commandAliases": []
}

# Cache to prevent frequent MongoDB lookups per message
_settings_cache = {}

def get_settings(guild_id: str) -> dict:
    if guild_id in _settings_cache:
        return _settings_cache[guild_id]
    
    doc = guild_settings.find_one({"guildId": guild_id})
    if not doc:
        doc = {"guildId": guild_id, **DEFAULT_SETTINGS}
        guild_settings.insert_one(doc)
    
    _settings_cache[guild_id] = doc
    return doc


def update_settings(guild_id: str, update: dict) -> dict:
    guild_settings.update_one(
        {"guildId": guild_id},
        {"$set": update, "$setOnInsert": {"guildId": guild_id}},
        upsert=True
    )
    if guild_id in _settings_cache:
        del _settings_cache[guild_id]
    return get_settings(guild_id)


def build_message(template: str, member: discord.Member) -> str:
    text = (template or "")
    text = text.replace("[User]", member.mention).replace("[user]", member.mention)
    text = text.replace("[Img]", "").replace("[ing]", "")
    text = text.replace("[nember]", str(member.guild.member_count))
    return text


# =========================================
# BOT INTENTS SETUP (Optimized for speed)
# =========================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(
    command_prefix=["!", "#"],
    intents=intents,
    case_insensitive=True,
    help_command=None
)

_views_registered = False
_commands_synced = False

# =========================================
# DATABASE INITIALIZATION (SQLite - للـ XP والتوب فقط)
# =========================================

db = sqlite3.connect("lunex.db", check_same_thread=False)
cur = db.cursor()

# Enable WAL mode for significantly faster SQLite performance
cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous=NORMAL;")

cur.execute("""
CREATE TABLE IF NOT EXISTS xp(
guild_id TEXT,
user_id TEXT,
messages INTEGER DEFAULT 0,
day_count INTEGER DEFAULT 0,
week_count INTEGER DEFAULT 0,
month_count INTEGER DEFAULT 0,
PRIMARY KEY (guild_id, user_id)
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
CREATE TABLE IF NOT EXISTS user_settings(
user_id TEXT PRIMARY KEY,
lang TEXT DEFAULT 'en'
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS reset_tracker(
id INTEGER PRIMARY KEY CHECK (id = 1),
last_day TEXT,
last_week TEXT,
last_month TEXT
)
""")

db.commit()

badword_words = {}
spam_cache = {}

# =========================================
# LOCALIZATION
# =========================================

locales = {
    "en": {
        "lang_set": "✅ Your personal language has been set to English.",
        "higher_bot": "❌ Their role is higher than or equal to mine!",
        "higher_user": "❌ Their role is higher than or equal to yours!",
        "banned": "✅ Member banned successfully.",
        "kicked": "✅ Member kicked successfully.",
        "unbanned": "✅ User unbanned.",
        "invalid_time": "❌ Invalid time format (e.g., 10m, 1h).",
        "timeout_applied": "✅ Timeout applied successfully.",
        "timeout_removed": "✅ Timeout removed.",
        "channel_locked": "🔒 Channel locked successfully.",
        "channel_unlocked": "🔓 Channel unlocked successfully.",
        "role_added": "✅ Role added successfully.",
        "role_removed": "✅ Role removed successfully.",
        "nick_changed": "✅ Nickname changed successfully.",
        "cleared": "🧹 Cleared `{}` messages.",
        "error": "❌ Error:"
    },
    "ar": {
        "lang_set": "✅ تم تعيين لغتك الشخصية إلى العربية.",
        "higher_bot": "❌ رتبة هذا العضو أعلى من رتبتي أو مساوية لها!",
        "higher_user": "❌ رتبة هذا العضو أعلى من رتبتك أو مساوية لها!",
        "banned": "✅ تم حظر العضو بنجاح.",
        "kicked": "✅ تم طرد العضو بنجاح.",
        "unbanned": "✅ تم فك الحظر عن المستخدم.",
        "invalid_time": "❌ صيغة الوقت غير صحيحة (مثال: 10m, 1h).",
        "timeout_applied": "✅ تم إعطاء العضو تايم أوت بنجاح.",
        "timeout_removed": "✅ تم إزالة التايم أوت عن العضو.",
        "channel_locked": "🔒 تم قفل القناة بنجاح.",
        "channel_unlocked": "🔓 تم فتح القناة بنجاح.",
        "role_added": "✅ تم إعطاء الرتبة بنجاح.",
        "role_removed": "✅ تم سحب الرتبة بنجاح.",
        "nick_changed": "✅ تم تغيير اللقب بنجاح.",
        "cleared": "🧹 تم مسح `{}` رسالة.",
        "error": "❌ حدث خطأ:"
    }
}

_lang_cache = {}

def get_lang(user_id: str) -> str:
    if user_id in _lang_cache:
        return _lang_cache[user_id]
    
    cur.execute("SELECT lang FROM user_settings WHERE user_id=?", (str(user_id),))
    row = cur.fetchone()
    lang = row[0] if row and row[0] in locales else "en"
    _lang_cache[user_id] = lang
    return lang


def t(user_id: str, key: str, *args) -> str:
    lang = get_lang(user_id)
    text = locales[lang].get(key, key)
    if args:
        return text.format(*args)
    return text


# =========================================
# PERMISSIONS & HIERARCHY CHECKS
# =========================================

async def check_hierarchy(interaction: discord.Interaction, member: discord.Member):
    uid = str(interaction.user.id)
    if member.top_role >= interaction.guild.me.top_role:
        await interaction.response.send_message(t(uid, "higher_bot"), ephemeral=True)
        return False
    if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message(t(uid, "higher_user"), ephemeral=True)
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
    except Exception:
        return None
    return None


# =========================================
# TICKET VIEWS (مربوطة بلوحة التحكم بالموقع)
# =========================================

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket 🔒", style=discord.ButtonStyle.danger, custom_id="lunex_close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing this ticket in 5 seconds...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except Exception:
            pass


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket 🎫", style=discord.ButtonStyle.primary, custom_id="lunex_open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            settings = get_settings(str(interaction.guild.id))
            ticket = settings.get("ticket", {})

            raw_name = f"ticket-{interaction.user.name}".lower()
            safe_name = "".join(c for c in raw_name if c.isalnum() or c == "-")[:90]

            existing = discord.utils.get(interaction.guild.text_channels, name=safe_name)
            if existing:
                await interaction.response.send_message(f"You already have an open ticket: {existing.mention}", ephemeral=True)
                return

            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            }

            category = None
            if ticket.get("categoryId"):
                category = interaction.guild.get_channel(int(ticket["categoryId"]))

            channel = await interaction.guild.create_text_channel(safe_name, overwrites=overwrites, category=category)

            description = build_message(ticket.get("description") or "Hello [User], our support team will be with you shortly.", interaction.user)
            embed = discord.Embed(title="Ticket", description=description, color=0x57F287)
            if ticket.get("image"):
                embed.set_image(url=ticket["image"])

            await channel.send(embed=embed, view=CloseTicketView())
            await interaction.response.send_message(f"Your ticket has been opened: {channel.mention}", ephemeral=True)
        except Exception as e:
            print("open ticket error:", e)
            if not interaction.response.is_done():
                await interaction.response.send_message("Something went wrong opening your ticket, try again.", ephemeral=True)


async def post_ticket_panel(guild_id: str, channel_id: str):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        raise ValueError("Bot is not in this server")
    channel = guild.get_channel(int(channel_id))
    if not channel:
        raise ValueError("Channel not found")

    settings = get_settings(str(guild_id))
    ticket = settings.get("ticket", {})

    embed = discord.Embed(title="Ticket", description=ticket.get("message") or "Click the button below to open a new ticket.", color=COLOR)
    if ticket.get("image"):
        embed.set_image(url=ticket["image"])

    await channel.send(embed=embed, view=TicketView())


# =========================================
# HELP MENU (فخم)
# =========================================

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="All member", description="Member commands & XP", emoji="👥"),
            discord.SelectOption(label="Staff member", description="Administration and security commands", emoji="👑")
        ]
        super().__init__(placeholder="Select desired category", options=options, custom_id="help_select")

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "All member":
            embed = discord.Embed(
                title="👥 __**ALL MEMBER COMMANDS**__",
                description=f"**Everything available to every member.**\n\n📌 **Visit us:** {SITE_URL}",
                color=COLOR
            )
            embed.add_field(
                name="__**⭐ XP & Leaderboards**__",
                value="**!xp** / **/xp** — your XP\n**!level** / **/level** — your level\n**!t** — monthly top 10\n**!t day** — daily top 10\n**!t week** — weekly top 10",
                inline=False
            )
            embed.add_field(
                name="__**📌 Info**__",
                value="**!i** `[member]` — profile\n**!افاتار** `[member]` — avatar\n**!سيرفر** — server info\n**/language** — set your language\n**/commands**",
                inline=False
            )
            if bot.user:
                embed.set_thumbnail(url=bot.user.display_avatar.url)
            embed.set_footer(text="Lunex • More than a bot")
            await interaction.response.edit_message(embed=embed, view=HelpView())

        elif self.values[0] == "Staff member":
            embed = discord.Embed(
                title="👑 __**STAFF MEMBER COMMANDS**__",
                description=f"**Moderation, security, and server management.**\n\n📌 **Visit us:** {SITE_URL}",
                color=COLOR
            )
            embed.add_field(
                name="__**🛡️ Moderation**__",
                value="**/ban** | **/kick** | **/unban**\n**/timeout** | **/timeout_remove**\n**/lock** | **/open**\n**!clear** / **!مسح**\n**!سجل**",
                inline=False
            )
            embed.add_field(
                name="__**⚙️ Management**__",
                value="**/add_role** | **/remove_role**\n**/nickname**\n**/badword**\n**/auto_reply**\n**/protection**",
                inline=False
            )
            if bot.user:
                embed.set_thumbnail(url=bot.user.display_avatar.url)
            embed.set_footer(text="Lunex • More than a bot")
            await interaction.response.edit_message(embed=embed, view=HelpView())


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(HelpSelect())
        self.add_item(discord.ui.Button(label="Add Bot", emoji="🔗", url=BOT_INVITE, style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="Support", emoji="💬", url=SUPPORT_INVITE, style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="Website", emoji="🌐", url=SITE_URL, style=discord.ButtonStyle.link))


def build_main_embed():
    embed = discord.Embed(
        title="🌙 __**LUNEX BOT**__",
        description=f"**Advanced, powerful, and simple server management.**\n\n📌 **To learn more, visit us:** {SITE_URL}",
        color=COLOR
    )
    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="Lunex • More than a bot")
    return embed


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
        except Exception:
            pass
        await asyncio.sleep(60)


async def reset_leaderboards():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            now = datetime.now(timezone.utc)
            today_str = now.strftime("%Y-%m-%d")
            week_str = "-".join(map(str, now.isocalendar()[:2]))
            month_str = now.strftime("%Y-%m")

            cur.execute("SELECT last_day, last_week, last_month FROM reset_tracker WHERE id=1")
            row = cur.fetchone()
            if not row:
                cur.execute("INSERT INTO reset_tracker VALUES (1, ?, ?, ?)", (today_str, week_str, month_str))
                db.commit()
            else:
                last_day, last_week, last_month = row
                if last_day != today_str:
                    cur.execute("UPDATE xp SET day_count=0")
                if last_week != week_str:
                    cur.execute("UPDATE xp SET week_count=0")
                if last_month != month_str:
                    cur.execute("UPDATE xp SET month_count=0")
                cur.execute("UPDATE reset_tracker SET last_day=?, last_week=?, last_month=? WHERE id=1", (today_str, week_str, month_str))
                db.commit()
        except Exception as e:
            print("reset error:", e)
        await asyncio.sleep(3600)


# =========================================
# BOT READY
# =========================================

@bot.event
async def on_ready():
    global _views_registered, _commands_synced

    if not _commands_synced:
        try:
            synced = await bot.tree.sync()
            print(f"✅ Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"❌ Failed to sync commands: {e}")
        _commands_synced = True

    if not _views_registered:
        bot.add_view(HelpView())
        bot.add_view(TicketView())
        bot.add_view(CloseTicketView())
        _views_registered = True

        bot.loop.create_task(check_expired_premiums())
        bot.loop.create_task(reset_leaderboards())

    print(f"✅ Lunex Bot Logged in as {bot.user}")


# =========================================
# WELCOME / LEAVE
# =========================================

@bot.event
async def on_member_join(member: discord.Member):
    try:
        settings = get_settings(str(member.guild.id))
        welcome = settings.get("welcome", {})
        if not welcome.get("enabled") or not welcome.get("channelId"):
            return
        channel = member.guild.get_channel(int(welcome["channelId"]))
        if not channel:
            return
        embed = discord.Embed(description=build_message(welcome.get("message"), member), color=COLOR)
        embed.set_image(url=member.display_avatar.url)
        await channel.send(embed=embed)
    except Exception as e:
        print("welcome error:", e)


@bot.event
async def on_member_remove(member: discord.Member):
    try:
        settings = get_settings(str(member.guild.id))
        leave = settings.get("leave", {})
        if not leave.get("enabled") or not leave.get("channelId"):
            return
        channel = member.guild.get_channel(int(leave["channelId"]))
        if not channel:
            return
        embed = discord.Embed(description=build_message(leave.get("message"), member), color=COLOR)
        embed.set_image(url=member.display_avatar.url)
        await channel.send(embed=embed)
    except Exception as e:
        print("leave error:", e)


# =========================================
# MESSAGE EVENT (Optimized & Non-blocking)
# =========================================

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    gid = str(message.guild.id)
    uid = str(message.author.id)

    # Fire-and-forget or lightweight synchronous SQLite execution
    try:
        cur.execute("SELECT 1 FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
        if cur.fetchone():
            cur.execute("UPDATE xp SET messages=messages+1, day_count=day_count+1, week_count=week_count+1, month_count=month_count+1 WHERE guild_id=? AND user_id=?", (gid, uid))
        else:
            cur.execute("INSERT INTO xp (guild_id, user_id, messages, day_count, week_count, month_count) VALUES (?,?,1,1,1,1)", (gid, uid))
        db.commit()
    except Exception as e:
        print("xp update error:", e)

    try:
        settings = get_settings(gid)

        for prefix in ("!", "#"):
            if message.content.startswith(prefix):
                rest = message.content[len(prefix):]
                first_word, _, remainder = rest.partition(" ")
                for alias_entry in settings.get("commandAliases", []):
                    if first_word == alias_entry.get("alias"):
                        original = alias_entry.get("original")
                        new_content = f"{prefix}{original}"
                        if remainder:
                            new_content += f" {remainder}"
                        message.content = new_content
                        break

        content_lower = message.content.strip().lower()
        for reply_entry in settings.get("autoReplies", []):
            trigger = (reply_entry.get("message") or "").strip().lower()
            if trigger and trigger in content_lower:
                asyncio.create_task(message.channel.send(embed=discord.Embed(description=reply_entry.get("reply", ""), color=COLOR)))
                break
    except Exception as e:
        print("mongo settings error:", e)

    try:
        if not message.author.guild_permissions.administrator:
            for word, sec in badword_words.items():
                if word in message.content.lower():
                    asyncio.create_task(message.delete())
                    asyncio.create_task(message.author.timeout(timedelta(seconds=sec)))
                    asyncio.create_task(message.channel.send(f"⛔ {message.author.mention} has been timed out for using forbidden words."))
                    break

            if "http://" in message.content.lower() or "https://" in message.content.lower():
                asyncio.create_task(message.delete())
                asyncio.create_task(message.channel.send(f"🚫 {message.author.mention} Links are not allowed in this server!"))

            key = (gid, uid)
            spam_cache[key] = spam_cache.get(key, []) + [time.time()]
            spam_cache[key] = [t_ for t_ in spam_cache[key] if time.time() - t_ < 3]
            if len(spam_cache[key]) >= 5:
                asyncio.create_task(message.author.timeout(timedelta(minutes=10), reason="Spamming"))
                asyncio.create_task(message.channel.send(f"⏱ {message.author.mention} You have been timed out for spamming."))
                spam_cache[key] = []
    except Exception as e:
        print("protection error:", e)

    await bot.process_commands(message)


# =========================================
# LANGUAGE
# =========================================

@bot.tree.command(name="language", description="Set your personal language for bot replies")
@app_commands.describe(lang="Choose your language")
@app_commands.choices(lang=[
    app_commands.Choice(name="English", value="en"),
    app_commands.Choice(name="العربية", value="ar")
])
async def set_language(interaction: discord.Interaction, lang: str):
    uid = str(interaction.user.id)
    cur.execute("INSERT INTO user_settings (user_id, lang) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET lang=?", (uid, lang, lang))
    db.commit()
    if uid in _lang_cache:
        del _lang_cache[uid]
    await interaction.response.send_message(t(uid, "lang_set"), ephemeral=True)


# =========================================
# PROTECTION
# =========================================

@bot.tree.command(name="protection", description="Add protection settings")
@app_commands.default_permissions(manage_guild=True)
async def protection_config(interaction: discord.Interaction, feature: str, status: str):
    await interaction.response.send_message(f"✅ `{feature}` ➔ `{status}`", ephemeral=True)


# =========================================
# HELP & COMMANDS
# =========================================

@bot.command(name="help")
async def help_command(ctx):
    await ctx.send(embed=build_main_embed(), view=HelpView())


@bot.tree.command(name="commands", description="Display Lunex bot commands")
async def commands_list(interaction: discord.Interaction):
    await interaction.response.send_message(embed=build_main_embed(), view=HelpView(), ephemeral=True)


# =========================================
# XP / LEVEL
# =========================================

@bot.command()
async def xp(ctx):
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(ctx.author.id)))
    row = cur.fetchone()
    await ctx.send(embed=discord.Embed(title="⭐ XP", description=f"```{row[0] if row else 0}```", color=COLOR))


@bot.tree.command(name="xp", description="Check your XP")
async def slash_xp(interaction: discord.Interaction):
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (str(interaction.guild.id), str(interaction.user.id)))
    row = cur.fetchone()
    await interaction.response.send_message(embed=discord.Embed(title="⭐ XP", description=f"```{row[0] if row else 0}```", color=COLOR))


@bot.command()
async def level(ctx):
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(ctx.author.id)))
    row = cur.fetchone()
    await ctx.send(embed=discord.Embed(title="📊 LEVEL", description=f"```{(row[0] if row else 0) // 50}```", color=COLOR))


@bot.tree.command(name="level", description="Check your level")
async def slash_level(interaction: discord.Interaction):
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (str(interaction.guild.id), str(interaction.user.id)))
    row = cur.fetchone()
    await interaction.response.send_message(embed=discord.Embed(title="📊 LEVEL", description=f"```{(row[0] if row else 0) // 50}```", color=COLOR))


# =========================================
# TOP LEADERBOARDS (!t / !t day / !t week)
# =========================================

@bot.command(name="t")
async def top_command(ctx, mode: str = None):
    gid = str(ctx.guild.id)
    if mode == "day":
        col, title = "day_count", "🏆 Daily Top"
    elif mode == "week":
        col, title = "week_count", "🏆 Weekly Top"
    else:
        col, title = "month_count", "🏆 Monthly Top"

    cur.execute(f"SELECT user_id, {col} FROM xp WHERE guild_id=? AND {col} > 0 ORDER BY {col} DESC LIMIT 10", (gid,))
    rows = cur.fetchall()

    embed = discord.Embed(title=title, color=COLOR)
    if not rows:
        embed.description = "No data yet."
    else:
        for i, (uid, cnt) in enumerate(rows, start=1):
            embed.add_field(name=f"{i}. <@{uid}>", value=f"💬 {cnt} messages", inline=False)
    await ctx.send(embed=embed)


# =========================================
# AVATAR
# =========================================

@bot.command(name="افاتار")
async def avatar_command(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"Avatar: {member.name}", color=COLOR)
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)


# =========================================
# SERVER INFO
# =========================================

@bot.command(name="سيرفر")
async def server_info(ctx):
    guild = ctx.guild
    bots_count = sum(1 for m in guild.members if m.bot)
    embed = discord.Embed(title=f"🖥 {guild.name}", color=COLOR)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="👥 Members", value=f"`{guild.member_count}`", inline=True)
    embed.add_field(name="🤖 Bots", value=f"`{bots_count}`", inline=True)
    embed.add_field(name="📅 Created", value=f"`{guild.created_at.strftime('%Y-%m-%d')}`", inline=True)
    embed.add_field(name="👑 Owner", value=f"{guild.owner.mention}" if guild.owner else "Unknown", inline=True)
    await ctx.send(embed=embed)


# =========================================
# PROFILE (!i)
# =========================================

@bot.command(name="i")
async def profile(ctx, member: discord.Member = None):
    member = member or ctx.author
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(member.id)))
    row = cur.fetchone()
    msgs = row[0] if row else 0

    embed = discord.Embed(title=f"Profile: {member.name}", color=COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="⭐ XP", value=f"`{msgs}`", inline=True)
    embed.add_field(name="📊 Level", value=f"`{msgs // 50}`", inline=True)
    embed.add_field(name="👑 Top Role", value=member.top_role.mention, inline=True)
    await ctx.send(embed=embed)


# =========================================
# MODERATION (TEXT)
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
    uid = str(ctx.author.id)
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(t(uid, "cleared", amount))
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except Exception:
        pass


# =========================================
# MODERATION (SLASH)
# =========================================

@bot.tree.command(name="ban", description="Ban a member")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member):
    if not await check_hierarchy(interaction, member):
        return
    await member.ban()
    await interaction.response.send_message(t(str(interaction.user.id), "banned"))


@bot.tree.command(name="kick", description="Kick a member")
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member):
    if not await check_hierarchy(interaction, member):
        return
    await member.kick()
    await interaction.response.send_message(t(str(interaction.user.id), "kicked"))


@bot.tree.command(name="unban", description="Unban a user by ID")
@app_commands.default_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str):
    uid = str(interaction.user.id)
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(t(uid, "unbanned"))
    except Exception as e:
        await interaction.response.send_message(f"{t(uid, 'error')} `{e}`", ephemeral=True)


@bot.tree.command(name="lock", description="Lock channel")
@app_commands.default_permissions(manage_channels=True)
async def lock_slash(interaction: discord.Interaction):
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message(t(str(interaction.user.id), "channel_locked"))


@bot.tree.command(name="open", description="Unlock channel")
@app_commands.default_permissions(manage_channels=True)
async def open_slash(interaction: discord.Interaction):
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = True
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message(t(str(interaction.user.id), "channel_unlocked"))


@bot.tree.command(name="timeout", description="Timeout a member")
@app_commands.default_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, time: str):
    uid = str(interaction.user.id)
    if not await check_hierarchy(interaction, member):
        return
    secs = parse_time(time)
    if not secs:
        return await interaction.response.send_message(t(uid, "invalid_time"), ephemeral=True)
    await member.timeout(timedelta(seconds=secs))
    await interaction.response.send_message(t(uid, "timeout_applied"))


@bot.tree.command(name="timeout_remove", description="Remove timeout")
@app_commands.default_permissions(moderate_members=True)
async def timeout_remove(interaction: discord.Interaction, member: discord.Member):
    uid = str(interaction.user.id)
    if not await check_hierarchy(interaction, member):
        return
    await member.timeout(None)
    await interaction.response.send_message(t(uid, "timeout_removed"))


@bot.tree.command(name="add_role", description="Add a role")
@app_commands.default_permissions(manage_roles=True)
async def add_role(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not await check_hierarchy(interaction, member):
        return
    await member.add_roles(role)
    await interaction.response.send_message(t(str(interaction.user.id), "role_added"))


@bot.tree.command(name="remove_role", description="Remove a role")
@app_commands.default_permissions(manage_roles=True)
async def remove_role(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not await check_hierarchy(interaction, member):
        return
    await member.remove_roles(role)
    await interaction.response.send_message(t(str(interaction.user.id), "role_removed"))


@bot.tree.command(name="nickname", description="Change a member's nickname")
@app_commands.describe(member="Select member", nickname="New nickname (leave blank to reset)")
@app_commands.default_permissions(manage_nicknames=True)
async def nickname(interaction: discord.Interaction, member: discord.Member, nickname: str = None):
    uid = str(interaction.user.id)
    if not await check_hierarchy(interaction, member):
        return
    try:
        await member.edit(nick=nickname)
        await interaction.response.send_message(t(uid, "nick_changed"))
    except Exception as e:
        await interaction.response.send_message(f"{t(uid, 'error')} `{e}`", ephemeral=True)


# =========================================
# BADWORD & AUTO-REPLY
# =========================================

@bot.tree.command(name="badword", description="Add banned word")
@app_commands.default_permissions(manage_guild=True)
async def badword(interaction: discord.Interaction, word: str, time: str):
    secs = parse_time(time)
    if not secs:
        return await interaction.response.send_message(t(str(interaction.user.id), "invalid_time"), ephemeral=True)
    badword_words[word.lower()] = secs
    await interaction.response.send_message(f"✅ Added `{word}`", ephemeral=True)


@bot.tree.command(name="auto_reply", description="Add an automatic reply")
@app_commands.default_permissions(manage_guild=True)
async def auto_reply(interaction: discord.Interaction, trigger: str, reply: str):
    guild_settings.update_one(
        {"guildId": str(interaction.guild.id)},
        {"$push": {"autoReplies": {"message": trigger, "reply": reply}},
         "$setOnInsert": {"guildId": str(interaction.guild.id)}},
        upsert=True
    )
    gid = str(interaction.guild.id)
    if gid in _settings_cache:
        del _settings_cache[gid]
    await interaction.response.send_message(f"✅ Added auto-reply for `{trigger}`", ephemeral=True)


@bot.tree.command(name="auto_reply_remove", description="Remove an automatic reply")
async def auto_reply_remove(interaction: discord.Interaction, trigger: str):
    guild_settings.update_one(
        {"guildId": str(interaction.guild.id)},
        {"$pull": {"autoReplies": {"message": trigger}}}
    )
    gid = str(interaction.guild.id)
    if gid in _settings_cache:
        del _settings_cache[gid]
    await interaction.response.send_message("✅ Deleted successfully.", ephemeral=True)


# =========================================
# RUN BOT
# =========================================

if __name__ == "__main__":
    bot.run(TOKEN)

