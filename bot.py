# =========================================
# LUNEX BOT — ALL-IN-ONE (BOT + WEBSITE API)
# discord.py 2.x (Optimized & Lightning Fast)
# =========================================

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import timedelta, datetime, timezone
import asyncio
import sqlite3
import time
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
# MONGODB & ADVANCED RAM CACHE SYSTEM
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

settings_cache = {}

def load_all_settings_to_cache():
    try:
        for doc in guild_settings.find({}):
            gid = str(doc.get("guildId"))
            settings_cache[gid] = doc
    except Exception as e:
        print("Cache preload error:", e)

def get_settings(guild_id: str) -> dict:
    if guild_id in settings_cache:
        return settings_cache[guild_id]
        
    doc = guild_settings.find_one({"guildId": guild_id})
    if not doc:
        doc = {"guildId": guild_id, **DEFAULT_SETTINGS}
        guild_settings.insert_one(doc)
        
    settings_cache[guild_id] = doc
    return doc

def build_message(template: str, member: discord.Member) -> str:
    text = (template or "")
    text = text.replace("[User]", member.mention).replace("[user]", member.mention)
    text = text.replace("[Img]", "").replace("[ing]", "")
    text = text.replace("[nember]", str(member.guild.member_count))
    return text

# =========================================
# BOT INTENTS & SETUP
# =========================================

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=["!", "#"],
    intents=intents,
    case_insensitive=True,
    help_command=None
)

_views_registered = False
_commands_synced = False

# =========================================
# SQLITE DATABASE INITIALIZATION
# =========================================

db = sqlite3.connect("lunex.db", check_same_thread=False)
cur = db.cursor()

cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous = NORMAL;")
db.commit()

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

def get_lang(user_id: str) -> str:
    cur.execute("SELECT lang FROM user_settings WHERE user_id=?", (str(user_id),))
    row = cur.fetchone()
    if row and row[0] in locales:
        return row[0]
    return "en"

def t(user_id: str, key: str, *args) -> str:
    lang = get_lang(user_id)
    text = locales[lang].get(key, key)
    if args:
        return text.format(*args)
    return text

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
# TICKET SYSTEM & post_ticket_panel (مطلوب للموقع)
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

async def post_ticket_panel(guild_id: int, channel_id: int):
    """دالة لإنشاء وإرسال لوحة التكتات بناءً على طلب الموقع"""
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return False
        
    channel = guild.get_channel(int(channel_id))
    if not channel:
        return False
        
    settings = get_settings(str(guild_id))
    ticket = settings.get("ticket", {})
    
    embed = discord.Embed(
        title="Support Tickets / تكتات الدعم",
        description=ticket.get("message", "اضغط الزر بالأسفل لفتح تكت جديد"),
        color=COLOR
    )
    if ticket.get("image"):
        embed.set_image(url=ticket["image"])
        
    await channel.send(embed=embed, view=TicketView())
    return True

# =========================================
# HELP MENU & VIEWS
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
            embed.add_field(name="__**⭐ XP & Leaderboards**__", value="**!xp** / **/xp**\n**!level** / **/level**\n**!t**", inline=False)
            if bot.user:
                embed.set_thumbnail(url=bot.user.display_avatar.url)
            await interaction.response.edit_message(embed=embed, view=HelpView())

        elif self.values[0] == "Staff member":
            embed = discord.Embed(
                title="👑 __**STAFF MEMBER COMMANDS**__",
                description=f"**Moderation and management.**\n\n📌 **Visit us:** {SITE_URL}",
                color=COLOR
            )
            embed.add_field(name="__**🛡️ Moderation**__", value="**/ban** | **/kick** | **/timeout** | **/lock**\n**!clear**", inline=False)
            if bot.user:
                embed.set_thumbnail(url=bot.user.display_avatar.url)
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
# BOT READY & EVENTS
# =========================================

@bot.event
async def on_ready():
    global _views_registered, _commands_synced

    load_all_settings_to_cache()

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

    print(f"✅ Lunex Bot Logged in as {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    gid = str(message.guild.id)
    uid = str(message.author.id)

    try:
        cur.execute("SELECT 1 FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
        if cur.fetchone():
            cur.execute("UPDATE xp SET messages=messages+1, day_count=day_count+1, week_count=week_count+1, month_count=month_count+1 WHERE guild_id=? AND user_id=?", (gid, uid))
        else:
            cur.execute("INSERT INTO xp (guild_id, user_id, messages, day_count, week_count, month_count) VALUES (?,?,1,1,1,1)", (gid, uid))
        db.commit()
    except Exception as e:
        print("xp update error:", e)

    await bot.process_commands(message)

# =========================================
# ESSENTIAL COMMANDS
# =========================================

@bot.command(name="help")
async def help_command(ctx):
    await ctx.send(embed=build_main_embed(), view=HelpView())

@bot.tree.command(name="commands", description="Display Lunex bot commands")
async def commands_list(interaction: discord.Interaction):
    await interaction.response.send_message(embed=build_main_embed(), view=HelpView(), ephemeral=True)

@bot.tree.command(name="language", description="Set your personal language")
@app_commands.choices(lang=[app_commands.Choice(name="English", value="en"), app_commands.Choice(name="العربية", value="ar")])
async def set_language(interaction: discord.Interaction, lang: str):
    uid = str(interaction.user.id)
    cur.execute("INSERT INTO user_settings (user_id, lang) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET lang=?", (uid, lang, lang))
    db.commit()
    await interaction.response.send_message(t(uid, "lang_set"), ephemeral=True)

@bot.command(name="clear", aliases=["مسح"])
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(t(str(ctx.author.id), "cleared", amount))
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except Exception:
        pass

# =========================================
# RUN BOT
# =========================================

if __name__ == "__main__":
    bot.run(TOKEN)

