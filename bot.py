# =========================================
# LUNEX BOT — MULTI-LANGUAGE + WEBSITE INTEGRATION
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

_mongo = MongoClient(os.environ["MONGODB_URI"])
_mdb = _mongo.get_default_database()
guild_settings = _mdb["guildsettings"]

DEFAULT_SETTINGS = {
    "welcome": {"enabled": False, "channelId": None, "message": "اهلا [user] فيك بالسيرفر! [ing]"},
    "leave": {"enabled": False, "channelId": None, "message": "وداعا [user] :( [ing]"},
    "ticket": {"enabled": False, "name": "Ticket", "image": "", "channelId": None},
    "autoReplies": [],
    "commandAliases": []
}


def get_settings(guild_id: str) -> dict:
    doc = guild_settings.find_one({"guildId": guild_id})
    if not doc:
        doc = {"guildId": guild_id, **DEFAULT_SETTINGS}
        guild_settings.insert_one(doc)
    return doc


def update_settings(guild_id: str, update: dict) -> dict:
    guild_settings.update_one(
        {"guildId": guild_id},
        {"$set": update, "$setOnInsert": {"guildId": guild_id}},
        upsert=True
    )
    return get_settings(guild_id)


def build_message(template: str, member: discord.Member) -> str:
    return (template or "").replace("[user]", member.mention).replace("[ing]", "")


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

_views_registered = False

# =========================================
# DATABASE INITIALIZATION (SQLite - للـ XP فقط، الإعدادات بـ Mongo)
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
lang TEXT DEFAULT 'en'
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
        "nick_changed": "✅ Nickname changed successfully.",
        "cleared": "🧹 Cleared `{}` messages.",
        "error": "❌ Error:",
        "help_desc": f"Our bot is advanced with powerful and scientific features\nBot commands are available here\nTo learn more, visit us:\n{SITE_URL}",
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
        "nick_changed": "✅ تم تغيير اللقب بنجاح.",
        "cleared": "🧹 تم مسح `{}` رسالة.",
        "error": "❌ حدث خطأ:",
        "help_desc": f"بوتنا متطور باشياء قوية وعلمية\nاوامر البوت موجودة هنا\nلمعرفة المزيد زورنا\n{SITE_URL}",
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


def is_admin(member: discord.Member) -> bool:
    return bool(member.guild_permissions.administrator) or member.id == member.guild.owner_id


def parse_time(t_str):
    try:
        value = int(t_str[:-1])
        unit = t_str[-1].lower()
        if unit == "s":
            return value
        elif unit == "m":
            return value * 60
        elif unit == "h":
            return value * 3600
        elif unit == "d":
            return value * 86400
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
            ticket_name = ticket.get("name") or "ticket"

            raw_name = f"{ticket_name}-{interaction.user.name}".lower()
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
            channel = await interaction.guild.create_text_channel(safe_name, overwrites=overwrites)

            embed = discord.Embed(
                title=ticket.get("name") or "Ticket",
                description=f"Hello {interaction.user.mention}, our support team will be with you shortly.",
                color=0x57F287
            )
            if ticket.get("image"):
                embed.set_image(url=ticket["image"])

            await channel.send(embed=embed, view=CloseTicketView())
            await interaction.response.send_message(f"Your ticket has been opened: {channel.mention}", ephemeral=True)
        except Exception as e:
            print("open ticket error:", e)
            if not interaction.response.is_done():
                await interaction.response.send_message("Something went wrong opening your ticket, try again.", ephemeral=True)


async def post_ticket_panel(guild_id: str, channel_id: str):
    """يستدعى من الموقع (API) لنشر لوحة فتح تكت بروم معين"""
    guild = bot.get_guild(int(guild_id))
    if not guild:
        raise ValueError("Bot is not in this server")
    channel = guild.get_channel(int(channel_id))
    if not channel:
        raise ValueError("Channel not found")

    settings = get_settings(str(guild_id))
    ticket = settings.get("ticket", {})

    embed = discord.Embed(
        title=ticket.get("name") or "Ticket",
        description="Click the button below to open a new ticket.",
        color=COLOR
    )
    if ticket.get("image"):
        embed.set_image(url=ticket["image"])

    await channel.send(embed=embed, view=TicketView())


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
            all_cmds = (
                "**/xp** | **!xp**\n**/level** | **!level**\n"
                "**!i** `[member]`\n**!سيرفر**\n**!سجل** `[member]`\n"
                "**/commands**"
            )
            embed = discord.Embed(title=t(gid, "all_member_title"), color=COLOR)
            embed.add_field(name=t(gid, "general_xp"), value=all_cmds, inline=False)
            await interaction.response.edit_message(embed=embed, view=HelpView())

        elif self.values[0] == "Staff member":
            staff_cmds = (
                "**/language** | **/l**\n**/unwarn**\n**!clear** | **!مسح**\n"
                "**/lock** | **/open**\n**/ban** | **/unban**\n**/timeout** | **/timeout_remove**\n"
                "**/add_role** | **/remove_role**\n**/nickname**\n**/badword**\n**/auto_reply**\n"
                "**/protection**"
            )
            embed = discord.Embed(title=t(gid, "staff_member_title"), color=COLOR)
            embed.add_field(name=t(gid, "mod_sec"), value=staff_cmds, inline=False)
            await interaction.response.edit_message(embed=embed, view=HelpView())


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(HelpSelect())
        self.add_item(discord.ui.Button(label="Add Bot", emoji="🔗", url=BOT_INVITE, style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="Support", emoji="💬", url=SUPPORT_INVITE, style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="Website", emoji="🌐", url=SITE_URL, style=discord.ButtonStyle.link))


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
        except Exception:
            pass
        await asyncio.sleep(60)


@bot.event
async def on_ready():
    global _views_registered
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

    if not _views_registered:
        bot.add_view(HelpView())
        bot.add_view(TicketView())
        bot.add_view(CloseTicketView())
        _views_registered = True

    bot.loop.create_task(check_expired_premiums())
    print(f"✅ Lunex Bot Logged in as {bot.user}")


# =========================================
# WELCOME / LEAVE — من إعدادات الموقع فقط
# (ما فيه أمر ديسكورد يضبطها، بس من لوحة التحكم بالموقع)
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
# MESSAGE EVENT (XP, ALIASES, AUTO REPLY, BADWORD, ANTI SPAM & LINKS)
# =========================================

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    gid = str(message.guild.id)
    uid = str(message.author.id)
    admin = message.author.guild_permissions.administrator

    cur.execute("SELECT * FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    if cur.fetchone():
        cur.execute("UPDATE xp SET messages=messages+1, day_count=day_count+1, week_count=week_count+1 WHERE guild_id=? AND user_id=?", (gid, uid))
    else:
        cur.execute("INSERT INTO xp VALUES(?,?,?,?,?)", (gid, uid, 1, 1, 1))
    db.commit()

    settings = get_settings(gid)

    # --- اختصارات الأوامر المخصصة (من الموقع) ---
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

    # Auto Reply (من إعدادات الموقع)
    content_lower = message.content.strip().lower()
    for reply_entry in settings.get("autoReplies", []):
        trigger = (reply_entry.get("message") or "").strip().lower()
        if trigger and trigger in content_lower:
            await message.channel.send(embed=discord.Embed(description=reply_entry.get("reply", ""), color=COLOR))
            break

    if not admin:
        for word, sec in badword_words.items():
            if word in message.content.lower():
                try:
                    await message.delete()
                    await message.author.timeout(timedelta(seconds=sec))
                    await message.channel.send(f"⛔ {message.author.mention} has been timed out for using forbidden words.")
                except Exception:
                    pass

        if "http://" in message.content.lower() or "https://" in message.content.lower():
            try:
                await message.delete()
                await message.channel.send(f"🚫 {message.author.mention} Links are not allowed in this server!")
            except Exception:
                pass

        key = (gid, uid)
        spam_cache[key] = spam_cache.get(key, []) + [time.time()]
        spam_cache[key] = [t_ for t_ in spam_cache[key] if time.time() - t_ < 3]

        if len(spam_cache[key]) >= 5:
            try:
                await message.author.timeout(timedelta(minutes=10), reason="Spamming")
                await message.channel.send(f"⏱ {message.author.mention} You have been timed out for spamming.")
            except Exception:
                pass
            spam_cache[key] = []

    await bot.process_commands(message)


# =========================================
# LANGUAGE COMMANDS (/language & /l)
# =========================================

async def handle_language_setting(interaction: discord.Interaction, lang: str):
    gid = str(interaction.guild.id)
    cur.execute("INSERT INTO server_settings (guild_id, lang) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET lang=?", (gid, lang, lang))
    db.commit()
    await interaction.response.send_message(t(gid, "lang_set"), ephemeral=True)


@bot.tree.command(name="language", description="Change bot language for this server")
@app_commands.describe(lang="Choose language")
@app_commands.choices(lang=[
    app_commands.Choice(name="English", value="en"),
    app_commands.Choice(name="العربية", value="ar")
])
@app_commands.default_permissions(manage_guild=True)
async def set_language(interaction: discord.Interaction, lang: str):
    await handle_language_setting(interaction, lang)


@bot.tree.command(name="l", description="Change bot language (Shortcut for /language)")
@app_commands.describe(lang="Choose language")
@app_commands.choices(lang=[
    app_commands.Choice(name="English", value="en"),
    app_commands.Choice(name="العربية", value="ar")
])
@app_commands.default_permissions(manage_guild=True)
async def set_language_alias(interaction: discord.Interaction, lang: str):
    await handle_language_setting(interaction, lang)


# =========================================
# PROTECTION SLASH COMMAND
# =========================================

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
    embed = discord.Embed(title="🌙 Lunex Bot", description=t(gid, "help_desc"), color=COLOR)
    await ctx.send(embed=embed, view=HelpView())


@bot.tree.command(name="commands", description="Display bot commands")
async def commands_list(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    embed = discord.Embed(title="🌙 Lunex Bot", description=t(gid, "help_desc"), color=COLOR)
    await interaction.response.send_message(embed=embed, view=HelpView(), ephemeral=True)


@bot.command()
async def xp(ctx):
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(ctx.author.id)))
    row = cur.fetchone()
    await ctx.send(embed=discord.Embed(title="⭐ XP", description=f"```{row[0] if row else 0}```", color=COLOR))


@bot.tree.command(name="xp", description="Check your XP points")
async def slash_xp(interaction: discord.Interaction):
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (str(interaction.guild.id), str(interaction.user.id)))
    row = cur.fetchone()
    await interaction.response.send_message(embed=discord.Embed(title="⭐ XP", description=f"```{row[0] if row else 0}```", color=COLOR))


@bot.command()
async def level(ctx):
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(ctx.author.id)))
    row = cur.fetchone()
    await ctx.send(embed=discord.Embed(title="📊 LEVEL", description=f"```{(row[0] if row else 0) // 50}```", color=COLOR))


@bot.tree.command(name="level", description="Check your current level")
async def slash_level(interaction: discord.Interaction):
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (str(interaction.guild.id), str(interaction.user.id)))
    row = cur.fetchone()
    await interaction.response.send_message(embed=discord.Embed(title="📊 LEVEL", description=f"```{(row[0] if row else 0) // 50}```", color=COLOR))


@bot.command(name="i")
async def profile(ctx, member: discord.Member = None):
    member = member or ctx.author
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(member.id)))
    row = cur.fetchone()
    msgs = row[0] if row else 0
    embed = discord.Embed(title=f"Profile: {member.name}", color=COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🆔 ID", value=f"`{member.id}`", inline=False)
    embed.add_field(name="📊 Level", value=f"`{msgs // 50}`", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="سيرفر")
async def server_info(ctx):
    embed = discord.Embed(title=f"🖥 {ctx.guild.name}", color=COLOR)
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
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
    try:
        await msg.delete()
    except Exception:
        pass


# =========================================
# MODERATION SLASH COMMANDS (PERMISSIONS)
# =========================================

@bot.tree.command(name="ban", description="Ban a member")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member):
    if not await check_hierarchy(interaction, member):
        return
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
    if not await check_hierarchy(interaction, member):
        return
    secs = parse_time(time)
    if not secs:
        return await interaction.response.send_message(t(gid, "invalid_time"), ephemeral=True)
    await member.timeout(timedelta(seconds=secs))
    await interaction.response.send_message(t(gid, "timeout_applied"))


@bot.tree.command(name="timeout_remove", description="Remove timeout")
@app_commands.default_permissions(moderate_members=True)
async def timeout_remove(interaction: discord.Interaction, member: discord.Member):
    gid = str(interaction.guild.id)
    if not await check_hierarchy(interaction, member):
        return
    await member.timeout(None)
    await interaction.response.send_message(t(gid, "timeout_removed"))


@bot.tree.command(name="add_role", description="Add a role")
@app_commands.default_permissions(manage_roles=True)
async def add_role(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not await check_hierarchy(interaction, member):
        return
    await member.add_roles(role)
    await interaction.response.send_message(t(str(interaction.guild.id), "role_added"))


@bot.tree.command(name="remove_role", description="Remove a role")
@app_commands.default_permissions(manage_roles=True)
async def remove_role(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not await check_hierarchy(interaction, member):
        return
    await member.remove_roles(role)
    await interaction.response.send_message(t(str(interaction.guild.id), "role_removed"))


@bot.tree.command(name="nickname", description="Change a member's nickname")
@app_commands.describe(member="Select member", nickname="New nickname (leave blank to reset)")
@app_commands.default_permissions(manage_nicknames=True)
async def nickname(interaction: discord.Interaction, member: discord.Member, nickname: str = None):
    gid = str(interaction.guild.id)
    if not await check_hierarchy(interaction, member):
        return
    try:
        await member.edit(nick=nickname)
        await interaction.response.send_message(t(gid, "nick_changed"))
    except Exception as e:
        await interaction.response.send_message(f"{t(gid, 'error')} `{e}`", ephemeral=True)


# =========================================
# BADWORD & AUTO-REPLY (مربوطة بإعدادات الموقع)
# =========================================

@bot.tree.command(name="badword", description="Add banned word")
@app_commands.default_permissions(manage_guild=True)
async def badword(interaction: discord.Interaction, word: str, time: str):
    secs = parse_time(time)
    if not secs:
        return await interaction.response.send_message(t(str(interaction.guild.id), "invalid_time"), ephemeral=True)
    badword_words[word.lower()] = secs
    await interaction.response.send_message(f"✅ Added `{word}`", ephemeral=True)


@bot.tree.command(name="auto_reply", description="Add auto reply")
@app_commands.default_permissions(manage_guild=True)
async def auto_reply(interaction: discord.Interaction, trigger: str, reply: str):
    guild_settings.update_one(
        {"guildId": str(interaction.guild.id)},
        {"$push": {"autoReplies": {"message": trigger, "reply": reply}},
         "$setOnInsert": {"guildId": str(interaction.guild.id)}},
        upsert=True
    )
    await interaction.response.send_message(f"✅ Added auto-reply for `{trigger}`", ephemeral=True)


@bot.tree.command(name="auto_reply_remove", description="Remove an automatic reply")
async def auto_reply_remove(interaction: discord.Interaction, trigger: str):
    guild_settings.update_one(
        {"guildId": str(interaction.guild.id)},
        {"$pull": {"autoReplies": {"message": trigger}}}
    )
    await interaction.response.send_message("✅ Deleted successfully.", ephemeral=True)


# =========================================
# RUN BOT
# =========================================

if __name__ == "__main__":
    bot.run(TOKEN)
