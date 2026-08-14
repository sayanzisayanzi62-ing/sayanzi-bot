# =========================================================
# LUNEX BOT — FULL RAILWAY EDITION
# bot.py
# discord.py 2.x
# MongoDB + SQLite
# Slash Commands + Legacy Commands
# Tickets + XP + Levels + Moderation + Protection
# =========================================================

import os
import re
import time
import asyncio
import sqlite3
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands
from discord import app_commands

import certifi
from pymongo import MongoClient
import aiosqlite


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

MONGODB_URI = os.getenv("MONGODB_URI")

SITE_URL = os.getenv(
    "FRONTEND_URL",
    "https://lunexbot.netlify.app"
)

COLOR = 0x8000FF

OWNER_ID = 1446592341908652112

SUPPORT_INVITE = "https://discord.gg/FMEXcwAvg"

BOT_INVITE = (
    "https://discord.com/oauth2/authorize"
    "?client_id=1501541120058851348"
    "&permissions=8"
    "&integration_type=0"
    "&scope=bot"
)


# =========================================================
# ENVIRONMENT CHECK
# =========================================================

if not TOKEN:
    raise RuntimeError(
        "DISCORD_BOT_TOKEN is missing."
    )

if not MONGODB_URI:
    raise RuntimeError(
        "MONGODB_URI is missing."
    )


# =========================================================
# MONGODB
# =========================================================

try:
    mongo = MongoClient(
        MONGODB_URI,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=5000,
        maxPoolSize=20,
        minPoolSize=1
    )

    mongo.admin.command("ping")

    mdb = mongo.get_default_database()

    guild_settings = mdb["guildsettings"]

    print("✅ MongoDB connected.")

except Exception as e:
    print("❌ MongoDB connection error:", e)
    raise


# =========================================================
# DEFAULT SETTINGS
# =========================================================

DEFAULT_SETTINGS = {
    "guildId": None,

    "welcome": {
        "enabled": False,
        "channelId": None,
        "message": "اهلا [User] فيك بالسيرفر!"
    },

    "leave": {
        "enabled": False,
        "channelId": None,
        "message": "وداعا [User] :("
    },

    "ticket": {
        "enabled": False,
        "image": "",
        "message": "اضغط الزر بالأسفل لفتح تكت جديد",
        "description": (
            "مرحبا [User]، فريق الدعم راح يرد عليك قريبا"
        ),
        "categoryId": None,
        "channelId": None
    },

    "autoReplies": [],

    "commandAliases": [],

    "protection": {
        "badwords": True,
        "links": True,
        "antispam": True
    },

    "badwords": {}
}


# =========================================================
# SETTINGS CACHE
# =========================================================

settings_cache = {}

SETTINGS_CACHE_TTL = 300


def clone_defaults():

    return {
        "guildId": None,

        "welcome": {
            **DEFAULT_SETTINGS["welcome"]
        },

        "leave": {
            **DEFAULT_SETTINGS["leave"]
        },

        "ticket": {
            **DEFAULT_SETTINGS["ticket"]
        },

        "autoReplies": [],

        "commandAliases": [],

        "protection": {
            **DEFAULT_SETTINGS["protection"]
        },

        "badwords": {}
    }


def merge_settings(data):

    settings = clone_defaults()

    if not data:
        return settings

    settings["guildId"] = data.get("guildId")

    for key in (
        "welcome",
        "leave",
        "ticket",
        "protection"
    ):

        if isinstance(data.get(key), dict):

            settings[key].update(
                data[key]
            )

    if isinstance(
        data.get("autoReplies"),
        list
    ):

        settings["autoReplies"] = data[
            "autoReplies"
        ]

    if isinstance(
        data.get("commandAliases"),
        list
    ):

        settings["commandAliases"] = data[
            "commandAliases"
        ]

    if isinstance(
        data.get("badwords"),
        dict
    ):

        settings["badwords"] = data[
            "badwords"
        ]

    return settings


async def get_settings(guild_id):

    guild_id = str(guild_id)

    now = time.time()

    cached = settings_cache.get(
        guild_id
    )

    if cached:

        expires_at, data = cached

        if now < expires_at:
            return data

    try:

        doc = guild_settings.find_one(
            {
                "guildId": guild_id
            }
        )

        if not doc:

            data = clone_defaults()

            data["guildId"] = guild_id

            guild_settings.update_one(
                {
                    "guildId": guild_id
                },
                {
                    "$setOnInsert": data
                },
                upsert=True
            )

        else:

            data = merge_settings(doc)

    except Exception as e:

        print(
            "❌ MongoDB settings error:",
            e
        )

        data = clone_defaults()

        data["guildId"] = guild_id

    settings_cache[guild_id] = (
        now + SETTINGS_CACHE_TTL,
        data
    )

    return data


async def update_settings(
    guild_id,
    update
):

    guild_id = str(guild_id)

    try:

        guild_settings.update_one(
            {
                "guildId": guild_id
            },
            {
                "$set": update,
                "$setOnInsert": {
                    "guildId": guild_id
                }
            },
            upsert=True
        )

    except Exception as e:

        print(
            "❌ MongoDB update error:",
            e
        )

    settings_cache.pop(
        guild_id,
        None
    )

    return await get_settings(
        guild_id
    )


# =========================================================
# MESSAGE BUILDER
# =========================================================

def build_message(
    template,
    member
):

    text = template or ""

    text = text.replace(
        "[User]",
        member.mention
    )

    text = text.replace(
        "[user]",
        member.mention
    )

    text = text.replace(
        "[Username]",
        member.name
    )

    text = text.replace(
        "[username]",
        member.name
    )

    text = text.replace(
        "[Server]",
        member.guild.name
    )

    text = text.replace(
        "[server]",
        member.guild.name
    )

    text = text.replace(
        "[MemberCount]",
        str(member.guild.member_count)
    )

    text = text.replace(
        "[member_count]",
        str(member.guild.member_count)
    )

    text = text.replace(
        "[nember]",
        str(member.guild.member_count)
    )

    return text


# =========================================================
# DISCORD INTENTS
# =========================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True


# =========================================================
# BOT
# =========================================================

bot = commands.Bot(
    command_prefix=["!", "#"],
    intents=intents,
    case_insensitive=True,
    help_command=None
)


# =========================================================
# GLOBAL STATE
# =========================================================

db = None

xp_pending = {}

spam_cache = {}

badword_cache = {}

_background_task = None

_started = False

_sync_done = False


# =========================================================
# CONSTANTS
# =========================================================

XP_PER_MESSAGE = 20

SPAM_LIMIT = 6

SPAM_WINDOW = 7


# =========================================================
# LOCALIZATION
# =========================================================

locales = {

    "en": {

        "lang_set":
            "✅ Your personal language has been set to English.",

        "higher_bot":
            "❌ Their role is higher than or equal to mine!",

        "higher_user":
            "❌ Their role is higher than or equal to yours!",

        "banned":
            "✅ Member banned successfully.",

        "kicked":
            "✅ Member kicked successfully.",

        "unbanned":
            "✅ User unbanned.",

        "invalid_time":
            "❌ Invalid time format. Example: `10m`, `1h`, `1d`.",

        "timeout_applied":
            "✅ Timeout applied successfully.",

        "timeout_removed":
            "✅ Timeout removed.",

        "channel_locked":
            "🔒 Channel locked successfully.",

        "channel_unlocked":
            "🔓 Channel unlocked successfully.",

        "role_added":
            "✅ Role added successfully.",

        "role_removed":
            "✅ Role removed successfully.",

        "nick_changed":
            "✅ Nickname changed successfully.",

        "cleared":
            "🧹 Cleared `{}` messages.",

        "no_permission":
            "❌ You don't have permission to use this command.",

        "error":
            "❌ An error occurred."
    },

    "ar": {

        "lang_set":
            "✅ تم تعيين لغتك الشخصية إلى العربية.",

        "higher_bot":
            "❌ رتبة هذا العضو أعلى من رتبتي أو مساوية لها!",

        "higher_user":
            "❌ رتبة هذا العضو أعلى من رتبتك أو مساوية لها!",

        "banned":
            "✅ تم حظر العضو بنجاح.",

        "kicked":
            "✅ تم طرد العضو بنجاح.",

        "unbanned":
            "✅ تم فك الحظر عن المستخدم.",

        "invalid_time":
            "❌ صيغة الوقت غير صحيحة. مثال: `10m` أو `1h` أو `1d`.",

        "timeout_applied":
            "✅ تم إعطاء العضو تايم أوت بنجاح.",

        "timeout_removed":
            "✅ تم إزالة التايم أوت عن العضو.",

        "channel_locked":
            "🔒 تم قفل القناة بنجاح.",

        "channel_unlocked":
            "🔓 تم فتح القناة بنجاح.",

        "role_added":
            "✅ تم إعطاء الرتبة بنجاح.",

        "role_removed":
            "✅ تم سحب الرتبة بنجاح.",

        "nick_changed":
            "✅ تم تغيير اللقب بنجاح.",

        "cleared":
            "🧹 تم مسح `{}` رسالة.",

        "no_permission":
            "❌ ليس لديك صلاحية لاستخدام هذا الأمر.",

        "error":
            "❌ حدث خطأ."
    }
}


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

async def init_database():

    global db

    if db is not None:
        return

    db = await aiosqlite.connect(
        "lunex.db"
    )

    await db.execute("""
        CREATE TABLE IF NOT EXISTS xp(
            guild_id TEXT,
            user_id TEXT,
            messages INTEGER DEFAULT 0,
            day_count INTEGER DEFAULT 0,
            week_count INTEGER DEFAULT 0,
            month_count INTEGER DEFAULT 0,
            PRIMARY KEY(guild_id, user_id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS warns(
            guild_id TEXT,
            user_id TEXT,
            warns INTEGER DEFAULT 0,
            PRIMARY KEY(guild_id, user_id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS premium_users(
            user_id TEXT,
            guild_id TEXT,
            role_id TEXT,
            expiry_time REAL,
            PRIMARY KEY(user_id, guild_id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS user_settings(
            user_id TEXT PRIMARY KEY,
            lang TEXT DEFAULT 'en'
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS level_roles(
            guild_id TEXT,
            level INTEGER,
            role_id TEXT,
            PRIMARY KEY(guild_id, level)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS reset_tracker(
            id INTEGER PRIMARY KEY CHECK(id = 1),
            last_day TEXT,
            last_week TEXT,
            last_month TEXT
        )
    """)

    await db.commit()

    print("✅ SQLite database initialized.")


# =========================================================
# LANGUAGE FUNCTIONS
# =========================================================

async def get_lang(user_id):

    if db is None:
        return "en"

    try:

        async with db.execute(
            """
            SELECT lang
            FROM user_settings
            WHERE user_id=?
            """,
            (
                str(user_id),
            )
        ) as cursor:

            row = await cursor.fetchone()

        if row and row[0] in locales:
            return row[0]

    except Exception as e:

        print(
            "Language error:",
            e
        )

    return "en"


async def t(
    user_id,
    key,
    *args
):

    lang = await get_lang(
        user_id
    )

    text = locales.get(
        lang,
        locales["en"]
    ).get(
        key,
        key
    )

    if args:

        try:
            return text.format(
                *args
            )

        except Exception:
            pass

    return text


# =========================================================
# TIME PARSER
# =========================================================

def parse_time(value):

    if not value:
        return None

    value = value.strip().lower()

    match = re.fullmatch(
        r"(\d+)(s|m|h|d)",
        value
    )

    if not match:
        return None

    number = int(
        match.group(1)
    )

    unit = match.group(2)

    if number <= 0:
        return None

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400
    }

    return number * multipliers[unit]


# =========================================================
# XP FUNCTIONS
# =========================================================

def calculate_level(messages):

    if messages <= 0:
        return 0

    return messages // XP_PER_MESSAGE


async def get_user_xp(
    guild_id,
    user_id
):

    if db is None:
        return 0

    guild_id = str(guild_id)
    user_id = str(user_id)

    try:

        async with db.execute(
            """
            SELECT messages
            FROM xp
            WHERE guild_id=?
            AND user_id=?
            """,
            (
                guild_id,
                user_id
            )
        ) as cursor:

            row = await cursor.fetchone()

        stored = (
            row[0]
            if row
            else 0
        )

    except Exception:

        stored = 0

    pending = xp_pending.get(
        (
            guild_id,
            user_id
        ),
        {}
    )

    return (
        stored
        + pending.get(
            "messages",
            0
        )
    )


def add_xp_memory(
    guild_id,
    user_id
):

    key = (
        str(guild_id),
        str(user_id)
    )

    if key not in xp_pending:

        xp_pending[key] = {

            "messages": 0,

            "day_count": 0,

            "week_count": 0,

            "month_count": 0
        }

    xp_pending[key]["messages"] += 1

    xp_pending[key]["day_count"] += 1

    xp_pending[key]["week_count"] += 1

    xp_pending[key]["month_count"] += 1


# =========================================================
# XP FLUSH
# =========================================================

async def flush_xp():

    global xp_pending

    if not xp_pending:
        return

    if db is None:
        return

    pending = xp_pending

    xp_pending = {}

    try:

        for (
            guild_id,
            user_id
        ), values in pending.items():

            await db.execute(
                """
                INSERT INTO xp(
                    guild_id,
                    user_id,
                    messages,
                    day_count,
                    week_count,
                    month_count
                )

                VALUES (?, ?, ?, ?, ?, ?)

                ON CONFLICT(guild_id, user_id)

                DO UPDATE SET

                    messages =
                        messages
                        + excluded.messages,

                    day_count =
                        day_count
                        + excluded.day_count,

                    week_count =
                        week_count
                        + excluded.week_count,

                    month_count =
                        month_count
                        + excluded.month_count
                """,
                (
                    guild_id,
                    user_id,
                    values["messages"],
                    values["day_count"],
                    values["week_count"],
                    values["month_count"]
                )
            )

        await db.commit()

    except Exception as e:

        print(
            "❌ XP flush error:",
            e
        )

        for key, values in pending.items():

            if key not in xp_pending:

                xp_pending[key] = {

                    "messages": 0,

                    "day_count": 0,

                    "week_count": 0,

                    "month_count": 0
                }

            for field in values:

                xp_pending[key][field] += (
                    values[field]
                )


# =========================================================
# LEVEL ROLES
# =========================================================

async def get_level_role(
    guild_id,
    level
):

    async with db.execute(
        """
        SELECT role_id
        FROM level_roles
        WHERE guild_id=?
        AND level=?
        """,
        (
            str(guild_id),
            int(level)
        )
    ) as cursor:

        row = await cursor.fetchone()

    return row[0] if row else None


async def set_level_role(
    guild_id,
    level,
    role_id
):

    await db.execute(
        """
        INSERT INTO level_roles(
            guild_id,
            level,
            role_id
        )

        VALUES (?, ?, ?)

        ON CONFLICT(guild_id, level)

        DO UPDATE SET
            role_id=excluded.role_id
        """,
        (
            str(guild_id),
            int(level),
            str(role_id)
        )
    )

    await db.commit()


async def remove_level_role(
    guild_id,
    level
):

    await db.execute(
        """
        DELETE FROM level_roles
        WHERE guild_id=?
        AND level=?
        """,
        (
            str(guild_id),
            int(level)
        )
    )

    await db.commit()


async def give_level_role(
    member,
    level
):

    if not member.guild:
        return

    role_id = await get_level_role(
        member.guild.id,
        level
    )

    if not role_id:
        return

    role = member.guild.get_role(
        int(role_id)
    )

    if not role:
        return

    me = member.guild.me

    if not me:
        return

    if role >= me.top_role:
        return

    try:

        await member.add_roles(
            role,
            reason=f"Lunex Level {level}"
        )

    except Exception as e:

        print(
            "Level role error:",
            e
        )


# =========================================================
# HIERARCHY
# =========================================================

async def check_hierarchy(
    interaction,
    member
):

    guild = interaction.guild

    if not guild:

        await interaction.response.send_message(
            "❌ هذا الأمر يستخدم داخل السيرفر فقط.",
            ephemeral=True
        )

        return False

    me = guild.me

    if not me:

        await interaction.response.send_message(
            "❌ تعذر العثور على البوت.",
            ephemeral=True
        )

        return False

    if member == guild.owner:

        await interaction.response.send_message(
            "❌ لا يمكنك التعامل مع مالك السيرفر.",
            ephemeral=True
        )

        return False

    if member == me:

        await interaction.response.send_message(
            "❌ لا يمكنني التعامل مع نفسي.",
            ephemeral=True
        )

        return False

    if member.top_role >= me.top_role:

        await interaction.response.send_message(
            await t(
                interaction.user.id,
                "higher_bot"
            ),
            ephemeral=True
        )

        return False

    if (
        member.top_role
        >= interaction.user.top_role
        and interaction.user.id
        != guild.owner_id
    ):

        await interaction.response.send_message(
            await t(
                interaction.user.id,
                "higher_user"
            ),
            ephemeral=True
        )

        return False

    return True


# =========================================================
# TICKET CLOSE VIEW
# =========================================================

class CloseTicketView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="lunex_close_ticket"
    )
    async def close_ticket(
        self,
        interaction,
        button
    ):

        if not interaction.channel:

            await interaction.response.send_message(
                "❌ Channel unavailable.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🔒 Closing this ticket in 5 seconds..."
        )

        await asyncio.sleep(5)

        try:

            await interaction.channel.delete(
                reason="Lunex ticket closed"
            )

        except Exception as e:

            print(
                "Ticket delete error:",
                e
            )


# =========================================================
# TICKET OPEN VIEW
# =========================================================

class TicketView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Open Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="lunex_open_ticket"
    )
    async def open_ticket(
        self,
        interaction,
        button
    ):

        try:

            guild = interaction.guild

            if not guild:

                await interaction.response.send_message(
                    "❌ هذا الزر يستخدم داخل السيرفر فقط.",
                    ephemeral=True
                )

                return

            settings = await get_settings(
                guild.id
            )

            ticket = settings.get(
                "ticket",
                {}
            )

            safe_name = (
                f"ticket-{interaction.user.id}"
            )

            existing = discord.utils.get(
                guild.text_channels,
                name=safe_name
            )

            if existing:

                await interaction.response.send_message(
                    f"🎫 لديك تكت مفتوح بالفعل: {existing.mention}",
                    ephemeral=True
                )

                return

            overwrites = {

                guild.default_role:
                    discord.PermissionOverwrite(
                        view_channel=False
                    ),

                interaction.user:
                    discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True
                    ),

                guild.me:
                    discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_channels=True
                    )
            }

            category = None

            category_id = ticket.get(
                "categoryId"
            )

            if category_id:

                try:

                    category = guild.get_channel(
                        int(category_id)
                    )

                except Exception:

                    category = None

            channel = await guild.create_text_channel(
                safe_name,
                overwrites=overwrites,
                category=category,
                reason="Lunex ticket opened"
            )

            description = build_message(
                ticket.get(
                    "description"
                )
                or
                "مرحبا [User]، فريق الدعم راح يرد عليك قريبا",
                interaction.user
            )

            embed = discord.Embed(
                title="🎫 Lunex Ticket",
                description=description,
                color=COLOR
            )

            image = ticket.get(
                "image"
            )

            if image:

                embed.set_image(
                    url=image
                )

            await channel.send(
                content=interaction.user.mention,
                embed=embed,
                view=CloseTicketView()
            )

            await interaction.response.send_message(
                f"🎫 تم فتح التكت: {channel.mention}",
                ephemeral=True
            )

        except Exception as e:

            print(
                "Open ticket error:",
                e
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ حدث خطأ أثناء فتح التكت.",
                    ephemeral=True
                )


# =========================================================
# TICKET PANEL
# =========================================================

async def ticket_panel(
    channel
):

    embed = discord.Embed(
        title="🎫 Lunex Support",
        description=(
            "اضغط الزر بالأسفل لفتح تكت جديد.\n\n"
            "فريق الدعم سيساعدك بأسرع وقت."
        ),
        color=COLOR
    )

    if bot.user:

        embed.set_thumbnail(
            url=bot.user.display_avatar.url
        )

    await channel.send(
        embed=embed,
        view=TicketView()
    )


# =========================================================
# APP.PY COMPATIBILITY
# =========================================================

async def post_ticket_panel(
    channel
):

    return await ticket_panel(
        channel
    )


# =========================================================
# HELP VIEW
# =========================================================

class HelpSelect(
    discord.ui.Select
):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="Member",
                value="member",
                description="XP, levels and profiles",
                emoji="👥"
            ),

            discord.SelectOption(
                label="Moderation",
                value="moderation",
                description="Moderation commands",
                emoji="🛡️"
            ),

            discord.SelectOption(
                label="Management",
                value="management",
                description="Server management",
                emoji="⚙️"
            ),

            discord.SelectOption(
                label="Security",
                value="security",
                description="Protection system",
                emoji="🔐"
            )
        ]

        super().__init__(
            placeholder="اختر قسم الأوامر",
            options=options,
            custom_id="lunex_help_select"
        )

    async def callback(
        self,
        interaction
    ):

        value = self.values[0]

        if value == "member":

            description = (
                "`/xp` — XP\n"
                "`/level` — Level\n"
                "`/profile` — Profile\n"
                "`/avatar` — Avatar\n"
                "`/server` — Server info\n"
                "`/leaderboard` — Leaderboard\n"
                "`/language` — Language"
            )

            title = "👥 MEMBER COMMANDS"

        elif value == "moderation":

            description = (
                "`/ban` — Ban\n"
                "`/kick` — Kick\n"
                "`/unban` — Unban\n"
                "`/timeout` — Timeout\n"
                "`/timeout_remove` — Remove timeout\n"
                "`/clear` — Clear messages\n"
                "`/lock` — Lock channel\n"
                "`/open` — Unlock channel\n"
                "`/add_role` — Add role\n"
                "`/remove_role` — Remove role\n"
                "`/nickname` — Nickname"
            )

            title = "🛡️ MODERATION COMMANDS"

        elif value == "management":

            description = (
                "`/commands` — All commands\n"
                "`/help` — Help\n"
                "`/ticket_panel` — Ticket panel\n"
                "`/auto_reply` — Add auto reply\n"
                "`/auto_reply_remove` — Remove auto reply\n"
                "`/badword` — Add bad word\n"
                "`/level_roll` — Level role"
            )

            title = "⚙️ MANAGEMENT COMMANDS"

        else:

            description = (
                "`/protection` — Protection settings\n"
                "`/badword` — Bad words\n"
                "`/auto_reply` — Auto replies\n\n"
                "Protection:\n"
                "• Bad Words\n"
                "• Links\n"
                "• Anti Spam"
            )

            title = "🔐 SECURITY COMMANDS"

        embed = discord.Embed(
            title=title,
            description=description,
            color=COLOR
        )

        if bot.user:

            embed.set_thumbnail(
                url=bot.user.display_avatar.url
            )

        embed.set_footer(
            text="Lunex • More than a bot"
        )

        await interaction.response.edit_message(
            embed=embed,
            view=HelpView()
        )


class HelpView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            HelpSelect()
        )

        self.add_item(
            discord.ui.Button(
                label="Add Bot",
                emoji="🔗",
                url=BOT_INVITE,
                style=discord.ButtonStyle.link
            )
        )

        self.add_item(
            discord.ui.Button(
                label="Support",
                emoji="💬",
                url=SUPPORT_INVITE,
                style=discord.ButtonStyle.link
            )
        )

        self.add_item(
            discord.ui.Button(
                label="Website",
                emoji="🌐",
                url=SITE_URL,
                style=discord.ButtonStyle.link
            )
        )


# =========================================================
# HELP EMBED
# =========================================================

def build_main_embed():

    embed = discord.Embed(
        title="🌙 LUNEX BOT",
        description=(
            "**Advanced Discord server management.**\n\n"
            "اختر قسم الأوامر من القائمة بالأسفل.\n\n"
            f"🌐 Website: {SITE_URL}"
        ),
        color=COLOR
    )

    if bot.user:

        embed.set_thumbnail(
            url=bot.user.display_avatar.url
        )

    embed.add_field(
        name="⭐ XP System",
        value=(
            f"كل **{XP_PER_MESSAGE} رسالة = Level واحد**.\n"
            "يمكن ربط Level برتبة باستخدام `/level_roll`."
        ),
        inline=False
    )

    embed.add_field(
        name="🎫 Tickets",
        value="نظام تذاكر كامل مع أزرار فتح وإغلاق.",
        inline=False
    )

    embed.add_field(
        name="🛡️ Protection",
        value="Bad Words + Links + Anti Spam.",
        inline=False
    )

    embed.set_footer(
        text="Lunex • More than a bot"
    )

    return embed


# =========================================================
# /HELP
# =========================================================

@bot.tree.command(
    name="help",
    description="Show Lunex help menu"
)
async def help_command(
    interaction
):

    await interaction.response.send_message(
        embed=build_main_embed(),
        view=HelpView()
    )


# =========================================================
# /COMMANDS
# =========================================================

@bot.tree.command(
    name="commands",
    description="Show all Lunex commands"
)
async def commands_command(
    interaction
):

    embed = discord.Embed(
        title="📚 LUNEX COMMANDS",
        description=(
            "**👥 Member**\n"
            "`/xp` `/level` `/profile` `/avatar` `/server`\n"
            "`/leaderboard` `/language`\n\n"

            "**🛡️ Moderation**\n"
            "`/ban` `/kick` `/unban` `/timeout`\n"
            "`/timeout_remove` `/clear` `/lock` `/open`\n"
            "`/add_role` `/remove_role` `/nickname`\n\n"

            "**⚙️ Management**\n"
            "`/ticket_panel` `/auto_reply`\n"
            "`/auto_reply_remove` `/badword`\n"
            "`/badword_remove` `/protection`\n\n"

            "**⭐ Levels**\n"
            "`/level_roll` `/level_roll_remove`\n"
            "`/level_roll_list`"
        ),
        color=COLOR
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# /LANGUAGE
# =========================================================

@bot.tree.command(
    name="language",
    description="Change your personal language"
)
@app_commands.describe(
    language="Choose ar or en"
)
@app_commands.choices(
    language=[
        app_commands.Choice(
            name="Arabic",
            value="ar"
        ),
        app_commands.Choice(
            name="English",
            value="en"
        )
    ]
)
async def language(
    interaction,
    language: app_commands.Choice[str]
):

    await db.execute(
        """
        INSERT INTO user_settings(
            user_id,
            lang
        )

        VALUES (?, ?)

        ON CONFLICT(user_id)

        DO UPDATE SET
            lang=excluded.lang
        """,
        (
            str(interaction.user.id),
            language.value
        )
    )

    await db.commit()

    await interaction.response.send_message(
        await t(
            interaction.user.id,
            "lang_set"
        ),
        ephemeral=True
    )


# =========================================================
# /XP
# =========================================================

@bot.tree.command(
    name="xp",
    description="Show XP"
)
async def xp_command(
    interaction
):

    xp = await get_user_xp(
        interaction.guild.id,
        interaction.user.id
    )

    level = calculate_level(
        xp
    )

    embed = discord.Embed(
        title="⭐ XP",
        color=COLOR
    )

    embed.add_field(
        name="XP",
        value=f"`{xp}`",
        inline=True
    )

    embed.add_field(
        name="Level",
        value=f"`{level}`",
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /LEVEL
# =========================================================

@bot.tree.command(
    name="level",
    description="Show level"
)
async def level_command(
    interaction
):

    xp = await get_user_xp(
        interaction.guild.id,
        interaction.user.id
    )

    level = calculate_level(
        xp
    )

    next_level = (
        (level + 1)
        * XP_PER_MESSAGE
    )

    remaining = max(
        0,
        next_level - xp
    )

    embed = discord.Embed(
        title="📊 Level",
        color=COLOR
    )

    embed.add_field(
        name="⭐ Level",
        value=f"`{level}`",
        inline=True
    )

    embed.add_field(
        name="XP",
        value=f"`{xp}`",
        inline=True
    )

    embed.add_field(
        name="Next Level",
        value=f"`{remaining} XP`",
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /PROFILE
# =========================================================

@bot.tree.command(
    name="profile",
    description="Show member profile"
)
@app_commands.describe(
    member="Member"
)
async def profile(
    interaction,
    member: discord.Member = None
):

    member = (
        member
        or interaction.user
    )

    xp = await get_user_xp(
        interaction.guild.id,
        member.id
    )

    level = calculate_level(
        xp
    )

    embed = discord.Embed(
        title=f"👤 {member.display_name}",
        color=COLOR
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.add_field(
        name="⭐ XP",
        value=f"`{xp}`",
        inline=True
    )

    embed.add_field(
        name="📊 Level",
        value=f"`{level}`",
        inline=True
    )

    embed.add_field(
        name="🏷️ Role",
        value=member.top_role.mention,
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /AVATAR
# =========================================================

@bot.tree.command(
    name="avatar",
    description="Show member avatar"
)
@app_commands.describe(
    member="Member"
)
async def avatar(
    interaction,
    member: discord.Member = None
):

    member = (
        member
        or interaction.user
    )

    embed = discord.Embed(
        title=f"🖼️ {member.display_name}",
        color=COLOR
    )

    embed.set_image(
        url=member.display_avatar.url
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /SERVER
# =========================================================

@bot.tree.command(
    name="server",
    description="Show server information"
)
async def server(
    interaction
):

    guild = interaction.guild

    embed = discord.Embed(
        title=f"🏠 {guild.name}",
        color=COLOR
    )

    if guild.icon:

        embed.set_thumbnail(
            url=guild.icon.url
        )

    embed.add_field(
        name="👥 Members",
        value=f"`{guild.member_count}`",
        inline=True
    )

    embed.add_field(
        name="📝 Channels",
        value=f"`{len(guild.channels)}`",
        inline=True
    )

    embed.add_field(
        name="🎭 Roles",
        value=f"`{len(guild.roles)}`",
        inline=True
    )

    embed.add_field(
        name="🆔 ID",
        value=f"`{guild.id}`",
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /LEADERBOARD
# =========================================================

@bot.tree.command(
    name="leaderboard",
    description="Show XP leaderboard"
)
async def leaderboard(
    interaction
):

    async with db.execute(
        """
        SELECT user_id, messages
        FROM xp
        WHERE guild_id=?
        ORDER BY messages DESC
        LIMIT 10
        """,
        (
            str(interaction.guild.id),
        )
    ) as cursor:

        rows = await cursor.fetchall()

    embed = discord.Embed(
        title="🏆 XP LEADERBOARD",
        color=COLOR
    )

    if not rows:

        embed.description = (
            "لا توجد بيانات بعد."
        )

    else:

        lines = []

        for index, (
            user_id,
            xp
        ) in enumerate(
            rows,
            start=1
        ):

            member = interaction.guild.get_member(
                int(user_id)
            )

            name = (
                member.display_name
                if member
                else f"User {user_id}"
            )

            level = calculate_level(
                xp
            )

            lines.append(
                f"**#{index}** {name} — "
                f"`{xp} XP` — Level `{level}`"
            )

        embed.description = "\n".join(
            lines
        )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /BAN
# =========================================================

@bot.tree.command(
    name="ban",
    description="Ban a member"
)
@app_commands.describe(
    member="Member to ban",
    reason="Ban reason"
)
@app_commands.default_permissions(
    ban_members=True
)
async def ban(
    interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    if not await check_hierarchy(
        interaction,
        member
    ):
        return

    try:

        await member.ban(
            reason=reason
        )

        await interaction.response.send_message(
            await t(
                interaction.user.id,
                "banned"
            )
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ {e}",
            ephemeral=True
        )


# =========================================================
# /KICK
# =========================================================

@bot.tree.command(
    name="kick",
    description="Kick a member"
)
@app_commands.describe(
    member="Member to kick",
    reason="Kick reason"
)
@app_commands.default_permissions(
    kick_members=True
)
async def kick(
    interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    if not await check_hierarchy(
        interaction,
        member
    ):
        return

    try:

        await member.kick(
            reason=reason
        )

        await interaction.response.send_message(
            await t(
                interaction.user.id,
                "kicked"
            )
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ {e}",
            ephemeral=True
        )


# =========================================================
# /TIMEOUT
# =========================================================

@bot.tree.command(
    name="timeout",
    description="Timeout a member"
)
@app_commands.describe(
    member="Member",
    duration="Example: 10m, 1h, 1d",
    reason="Reason"
)
@app_commands.default_permissions(
    moderate_members=True
)
async def timeout(
    interaction,
    member: discord.Member,
    duration: str,
    reason: str = "No reason provided"
):

    if not await check_hierarchy(
        interaction,
        member
    ):
        return

    seconds = parse_time(
        duration
    )

    if not seconds:

        await interaction.response.send_message(
            await t(
                interaction.user.id,
                "invalid_time"
            ),
            ephemeral=True
        )

        return

    if seconds > 2419200:

        await interaction.response.send_message(
            "❌ الحد الأقصى للتايم أوت هو 28 يومًا.",
            ephemeral=True
        )

        return

    try:

        until = (
            datetime.now(
                timezone.utc
            )
            + timedelta(
                seconds=seconds
            )
        )

        await member.timeout(
            until,
            reason=reason
        )

        await interaction.response.send_message(
            await t(
                interaction.user.id,
                "timeout_applied"
            )
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ {e}",
            ephemeral=True
        )


# =========================================================
# /TIMEOUT_REMOVE
# =========================================================

@bot.tree.command(
    name="timeout_remove",
    description="Remove timeout"
)
@app_commands.describe(
    member="Member"
)
@app_commands.default_permissions(
    moderate_members=True
)
async def timeout_remove(
    interaction,
    member: discord.Member
):

    if not await check_hierarchy(
        interaction,
        member
    ):
        return

    try:

        await member.timeout(
            None,
            reason="Lunex timeout removed"
        )

        await interaction.response.send_message(
            await t(
                interaction.user.id,
                "timeout_removed"
            )
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ {e}",
            ephemeral=True
        )


# =========================================================
# /CLEAR
# =========================================================

@bot.tree.command(
    name="clear",
    description="Delete messages"
)
@app_commands.describe(
    amount="Number of messages"
)
@app_commands.default_permissions(
    manage_messages=True
)
async def clear(
    interaction,
    amount: app_commands.Range[int, 1, 100]
):

    await interaction.response.defer(
        ephemeral=True
    )

    try:

        deleted = await interaction.channel.purge(
            limit=amount
        )

        await interaction.followup.send(
            await t(
                interaction.user.id,
                "cleared",
                len(deleted)
            ),
            ephemeral=True
        )

    except Exception as e:

        await interaction.followup.send(
            f"❌ {e}",
            ephemeral=True
        )


# =========================================================
# /LOCK
# =========================================================

@bot.tree.command(
    name="lock",
    description="Lock current channel"
)
@app_commands.default_permissions(
    manage_channels=True
)
async def lock(
    interaction
):

    channel = interaction.channel

    overwrite = channel.overwrites_for(
        interaction.guild.default_role
    )

    overwrite.send_messages = False

    await channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite,
        reason="Lunex channel lock"
    )

    await interaction.response.send_message(
        await t(
            interaction.user.id,
            "channel_locked"
        )
    )


# =========================================================
# /OPEN
# =========================================================

@bot.tree.command(
    name="open",
    description="Unlock current channel"
)
@app_commands.default_permissions(
    manage_channels=True
)
async def open_channel(
    interaction
):

    channel = interaction.channel

    overwrite = channel.overwrites_for(
        interaction.guild.default_role
    )

    overwrite.send_messages = None

    await channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite,
        reason="Lunex channel unlock"
    )

    await interaction.response.send_message(
        await t(
            interaction.user.id,
            "channel_unlocked"
        )
    )


# =========================================================
# /ADD_ROLE
# =========================================================

@bot.tree.command(
    name="add_role",
    description="Add role to member"
)
@app_commands.describe(
    member="Member",
    role="Role"
)
@app_commands.default_permissions(
    manage_roles=True
)
async def add_role(
    interaction,
    member: discord.Member,
    role: discord.Role
):

    if not await check_hierarchy(
        interaction,
        member
    ):
        return

    if role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ هذه الرتبة أعلى من رتبة البوت.",
            ephemeral=True
        )

        return

    try:

        await member.add_roles(
            role,
            reason=f"Lunex by {interaction.user}"
        )

        await interaction.response.send_message(
            await t(
                interaction.user.id,
                "role_added"
            )
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ {e}",
            ephemeral=True
        )


# =========================================================
# /REMOVE_ROLE
# =========================================================

@bot.tree.command(
    name="remove_role",
    description="Remove role from member"
)
@app_commands.describe(
    member="Member",
    role="Role"
)
@app_commands.default_permissions(
    manage_roles=True
)
async def remove_role(
    interaction,
    member: discord.Member,
    role: discord.Role
):

    if not await check_hierarchy(
        interaction,
        member
    ):
        return

    if role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ هذه الرتبة أعلى من رتبة البوت.",
            ephemeral=True
        )

        return

    try:

        await member.remove_roles(
            role,
            reason=f"Lunex by {interaction.user}"
        )

        await interaction.response.send_message(
            await t(
                interaction.user.id,
                "role_removed"
            )
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ {e}",
            ephemeral=True
        )


# =========================================================
# /NICKNAME
# =========================================================

@bot.tree.command(
    name="nickname",
    description="Change member nickname"
)
@app_commands.describe(
    member="Member",
    nickname="New nickname"
)
@app_commands.default_permissions(
    manage_nicknames=True
)
async def nickname(
    interaction,
    member: discord.Member,
    nickname: str
):

    if not await check_hierarchy(
        interaction,
        member
    ):
        return

    try:

        await member.edit(
            nick=nickname,
            reason=f"Lunex by {interaction.user}"
        )

        await interaction.response.send_message(
            await t(
                interaction.user.id,
                "nick_changed"
            )
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ {e}",
            ephemeral=True
        )


# =========================================================
# /UNBAN
# =========================================================

@bot.tree.command(
    name="unban",
    description="Unban a user"
)
@app_commands.describe(
    user_id="User ID"
)
@app_commands.default_permissions(
    ban_members=True
)
async def unban(
    interaction,
    user_id: str
):

    try:

        user = await bot.fetch_user(
            int(user_id)
        )

        await interaction.guild.unban(
            user,
            reason=f"Lunex by {interaction.user}"
        )

        await interaction.response.send_message(
            await t(
                interaction.user.id,
                "unbanned"
            )
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ {e}",
            ephemeral=True
        )


# =========================================================
# /TICKET_PANEL
# =========================================================

@bot.tree.command(
    name="ticket_panel",
    description="Send ticket panel"
)
@app_commands.default_permissions(
    manage_channels=True
)
async def ticket_panel_command(
    interaction
):

    await ticket_panel(
        interaction.channel
    )

    await interaction.response.send_message(
        "✅ تم إرسال لوحة التذاكر.",
        ephemeral=True
    )


# =========================================================
# /LEVEL_ROLL
# =========================================================

@bot.tree.command(
    name="level_roll",
    description="Set a role for a level"
)
@app_commands.describe(
    level="Required level",
    role="Role to give"
)
@app_commands.default_permissions(
    manage_roles=True
)
async def level_roll(
    interaction,
    level: app_commands.Range[int, 1, 100000],
    role: discord.Role
):

    guild = interaction.guild

    me = guild.me

    if role.is_default():

        await interaction.response.send_message(
            "❌ لا يمكن استخدام @everyone.",
            ephemeral=True
        )

        return

    if role.managed:

        await interaction.response.send_message(
            "❌ لا يمكن استخدام Managed Role.",
            ephemeral=True
        )

        return

    if role >= me.top_role:

        await interaction.response.send_message(
            "❌ الرتبة أعلى من رتبة البوت أو مساوية لها.",
            ephemeral=True
        )

        return

    await set_level_role(
        guild.id,
        level,
        role.id
    )

    embed = discord.Embed(
        title="🎯 Level Role",
        description=(
            f"تم إعداد النظام بنجاح.\n\n"
            f"⭐ Level: `{level}`\n"
            f"🏷️ Role: {role.mention}\n\n"
            f"كل {XP_PER_MESSAGE} رسالة = Level واحد."
        ),
        color=COLOR
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /LEVEL_ROLL_REMOVE
# =========================================================

@bot.tree.command(
    name="level_roll_remove",
    description="Remove a level role"
)
@app_commands.describe(
    level="Level"
)
@app_commands.default_permissions(
    manage_roles=True
)
async def level_roll_remove(
    interaction,
    level: app_commands.Range[int, 1, 100000]
):

    await remove_level_role(
        interaction.guild.id,
        level
    )

    await interaction.response.send_message(
        f"✅ تم حذف إعداد Level `{level}`."
    )


# =========================================================
# /LEVEL_ROLL_LIST
# =========================================================

@bot.tree.command(
    name="level_roll_list",
    description="Show level roles"
)
async def level_roll_list(
    interaction
):

    async with db.execute(
        """
        SELECT level, role_id
        FROM level_roles
        WHERE guild_id=?
        ORDER BY level ASC
        """,
        (
            str(interaction.guild.id),
        )
    ) as cursor:

        rows = await cursor.fetchall()

    embed = discord.Embed(
        title="🎯 Level Roles",
        color=COLOR
    )

    if not rows:

        embed.description = (
            "لا توجد رتب Level محددة."
        )

    else:

        lines = []

        for level, role_id in rows:

            role = interaction.guild.get_role(
                int(role_id)
            )

            if role:

                lines.append(
                    f"⭐ Level `{level}` → {role.mention}"
                )

            else:

                lines.append(
                    f"⭐ Level `{level}` → Deleted role"
                )

        embed.description = "\n".join(
            lines
        )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# /AUTO_REPLY
# =========================================================

@bot.tree.command(
    name="auto_reply",
    description="Add automatic reply"
)
@app_commands.describe(
    trigger="Trigger word",
    response="Bot response"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def auto_reply(
    interaction,
    trigger: str,
    response: str
):

    settings = await get_settings(
        interaction.guild.id
    )

    replies = settings.get(
        "autoReplies",
        []
    )

    replies.append({
        "trigger": trigger.lower(),
        "response": response
    })

    await update_settings(
        interaction.guild.id,
        {
            "autoReplies": replies
        }
    )

    await interaction.response.send_message(
        "✅ تم إضافة الرد التلقائي."
    )


# =========================================================
# /AUTO_REPLY_REMOVE
# =========================================================

@bot.tree.command(
    name="auto_reply_remove",
    description="Remove automatic reply"
)
@app_commands.describe(
    trigger="Trigger word"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def auto_reply_remove(
    interaction,
    trigger: str
):

    settings = await get_settings(
        interaction.guild.id
    )

    replies = settings.get(
        "autoReplies",
        []
    )

    trigger = trigger.lower()

    new_replies = [
        x for x in replies
        if x.get("trigger", "").lower()
        != trigger
    ]

    await update_settings(
        interaction.guild.id,
        {
            "autoReplies": new_replies
        }
    )

    await interaction.response.send_message(
        "✅ تم حذف الرد التلقائي."
    )


# =========================================================
# /BADWORD
# =========================================================

@bot.tree.command(
    name="badword",
    description="Add a forbidden word"
)
@app_commands.describe(
    word="Forbidden word"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def badword(
    interaction,
    word: str
):

    settings = await get_settings(
        interaction.guild.id
    )

    words = settings.get(
        "badwords",
        {}
    )

    words[word.lower()] = True

    await update_settings(
        interaction.guild.id,
        {
            "badwords": words
        }
    )

    badword_cache.pop(
        str(interaction.guild.id),
        None
    )

    await interaction.response.send_message(
        "✅ تمت إضافة الكلمة الممنوعة."
    )


# =========================================================
# /BADWORD_REMOVE
# =========================================================

@bot.tree.command(
    name="badword_remove",
    description="Remove forbidden word"
)
@app_commands.describe(
    word="Word"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def badword_remove(
    interaction,
    word: str
):

    settings = await get_settings(
        interaction.guild.id
    )

    words = settings.get(
        "badwords",
        {}
    )

    words.pop(
        word.lower(),
        None
    )

    await update_settings(
        interaction.guild.id,
        {
            "badwords": words
        }
    )

    badword_cache.pop(
        str(interaction.guild.id),
        None
    )

    await interaction.response.send_message(
        "✅ تم حذف الكلمة."
    )


# =========================================================
# /PROTECTION
# =========================================================

@bot.tree.command(
    name="protection",
    description="Configure server protection"
)
@app_commands.describe(
    feature="Protection feature",
    enabled="Enable or disable"
)
@app_commands.choices(
    feature=[
        app_commands.Choice(
            name="Bad Words",
            value="badwords"
        ),
        app_commands.Choice(
            name="Links",
            value="links"
        ),
        app_commands.Choice(
            name="Anti Spam",
            value="antispam"
        )
    ]
)
@app_commands.default_permissions(
    manage_guild=True
)
async def protection(
    interaction,
    feature: app_commands.Choice[str],
    enabled: bool
):

    settings = await get_settings(
        interaction.guild.id
    )

    protection_settings = settings.get(
        "protection",
        {}
    )

    protection_settings[
        feature.value
    ] = enabled

    await update_settings(
        interaction.guild.id,
        {
            "protection": protection_settings
        }
    )

    state = (
        "ON"
        if enabled
        else "OFF"
    )

    await interaction.response.send_message(
        f"🛡️ `{feature.name}` → **{state}**"
    )


# =========================================================
# LINK DETECTION
# =========================================================

URL_PATTERN = re.compile(
    r"(https?://|www\.)\S+",
    re.IGNORECASE
)


# =========================================================
# PROTECTION PROCESSOR
# =========================================================

async def process_protection(
    message
):

    if not message.guild:
        return False

    if message.author.bot:
        return False

    settings = await get_settings(
        message.guild.id
    )

    protection = settings.get(
        "protection",
        {}
    )

    content = message.content.lower()

    # -----------------------------------------------------
    # BAD WORDS
    # -----------------------------------------------------

    if protection.get(
        "badwords",
        True
    ):

        words = settings.get(
            "badwords",
            {}
        )

        for word in words:

            if word.lower() in content:

                try:

                    await message.delete(
                        reason="Lunex bad word filter"
                    )

                except Exception:
                    pass

                try:

                    await message.channel.send(
                        f"⚠️ {message.author.mention} "
                        "هذه الكلمة ممنوعة.",
                        delete_after=5
                    )

                except Exception:
                    pass

                return True

    # -----------------------------------------------------
    # LINKS
    # -----------------------------------------------------

    if protection.get(
        "links",
        True
    ):

        if URL_PATTERN.search(
            content
        ):

            if (
                message.author.guild_permissions
                .manage_messages
            ):

                return False

            try:

                await message.delete(
                    reason="Lunex link protection"
                )

            except Exception:
                pass

            try:

                await message.channel.send(
                    f"🔗 {message.author.mention} "
                    "الروابط غير مسموحة هنا.",
                    delete_after=5
                )

            except Exception:
                pass

            return True

    # -----------------------------------------------------
    # ANTI SPAM
    # -----------------------------------------------------

    if protection.get(
        "antispam",
        True
    ):

        key = (
            message.guild.id,
            message.author.id
        )

        now = time.time()

        timestamps = spam_cache.get(
            key,
            []
        )

        timestamps = [
            t for t in timestamps
            if now - t < SPAM_WINDOW
        ]

        timestamps.append(
            now
        )

        spam_cache[key] = timestamps

        if len(timestamps) >= SPAM_LIMIT:

            spam_cache[key] = []

            try:

                await message.author.timeout(
                    timedelta(
                        seconds=30
                    ),
                    reason="Lunex Anti Spam"
                )

                await message.channel.send(
                    f"🛡️ {message.author.mention} "
                    "تم إعطاؤك تايم أوت بسبب السبام.",
                    delete_after=7
                )

            except Exception:
                pass

            return True

    return False


# =========================================================
# AUTO REPLIES
# =========================================================

async def process_auto_replies(
    message
):

    if not message.guild:
        return

    settings = await get_settings(
        message.guild.id
    )

    replies = settings.get(
        "autoReplies",
        []
    )

    content = message.content.lower().strip()

    for item in replies:

        trigger = str(
            item.get(
                "trigger",
                ""
            )
        ).lower().strip()

        response = item.get(
            "response"
        )

        if not trigger:
            continue

        if trigger == content:

            if response:

                try:

                    await message.channel.send(
                        build_message(
                            response,
                            message.author
                        )
                    )

                except Exception as e:

                    print(
                        "Auto reply error:",
                        e
                    )

            break


# =========================================================
# XP MESSAGE EVENT
# =========================================================

async def process_xp(
    message
):

    if not message.guild:
        return

    old_xp = await get_user_xp(
        message.guild.id,
        message.author.id
    )

    old_level = calculate_level(
        old_xp
    )

    add_xp_memory(
        message.guild.id,
        message.author.id
    )

    new_xp = old_xp + 1

    new_level = calculate_level(
        new_xp
    )

    if new_level > old_level:

        await give_level_role(
            message.author,
            new_level
        )

        try:

            await message.channel.send(
                f"🎉 {message.author.mention} "
                f"وصل إلى **Level {new_level}**!",
                delete_after=8
            )

        except Exception:
            pass


# =========================================================
# ON MESSAGE
# =========================================================

@bot.event
async def on_message(
    message
):

    if message.author.bot:
        return

    if not message.guild:

        await bot.process_commands(
            message
        )

        return

    blocked = False

    try:

        blocked = await process_protection(
            message
        )

    except Exception as e:

        print(
            "Protection error:",
            e
        )

    if blocked:

        await bot.process_commands(
            message
        )

        return

    try:

        await process_auto_replies(
            message
        )

    except Exception as e:

        print(
            "Auto reply error:",
            e
        )

    try:

        await process_xp(
            message
        )

    except Exception as e:

        print(
            "XP error:",
            e
        )

    await bot.process_commands(
        message
    )


# =========================================================
# WELCOME
# =========================================================

@bot.event
async def on_member_join(
    member
):

    try:

        settings = await get_settings(
            member.guild.id
        )

        welcome = settings.get(
            "welcome",
            {}
        )

        if not welcome.get(
            "enabled",
            False
        ):
            return

        channel_id = welcome.get(
            "channelId"
        )

        if not channel_id:
            return

        channel = member.guild.get_channel(
            int(channel_id)
        )

        if not channel:
            return

        text = build_message(
            welcome.get(
                "message",
                "اهلا [User]!"
            ),
            member
        )

        await channel.send(
            text
        )

    except Exception as e:

        print(
            "Welcome error:",
            e
        )


# =========================================================
# LEAVE
# =========================================================

@bot.event
async def on_member_remove(
    member
):

    try:

        settings = await get_settings(
            member.guild.id
        )

        leave = settings.get(
            "leave",
            {}
        )

        if not leave.get(
            "enabled",
            False
        ):
            return

        channel_id = leave.get(
            "channelId"
        )

        if not channel_id:
            return

        channel = member.guild.get_channel(
            int(channel_id)
        )

        if not channel:
            return

        text = build_message(
            leave.get(
                "message",
                "وداعا [User]"
            ),
            member
        )

        await channel.send(
            text
        )

    except Exception as e:

        print(
            "Leave error:",
            e
        )


# =========================================================
# BACKGROUND LOOP
# =========================================================

async def background_loop():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            await flush_xp()

        except Exception as e:

            print(
                "Background XP error:",
                e
            )

        await asyncio.sleep(
            10
        )


# =========================================================
# PREMIUM CHECK
# =========================================================

async def premium_loop():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            now = time.time()

            async with db.execute(
                """
                SELECT
                    user_id,
                    guild_id
                FROM premium_users
                WHERE expiry_time IS NOT NULL
                AND expiry_time <= ?
                """,
                (
                    now,
                )
            ) as cursor:

                expired = await cursor.fetchall()

            for user_id, guild_id in expired:

                await db.execute(
                    """
                    DELETE FROM premium_users
                    WHERE user_id=?
                    AND guild_id=?
                    """,
                    (
                        user_id,
                        guild_id
                    )
                )

            if expired:
                await db.commit()

        except Exception as e:

            print(
                "Premium loop error:",
                e
            )

        await asyncio.sleep(
            60
        )


# =========================================================
# LEVEL ROLE COMMANDS
# =========================================================

# Already implemented:
#
# /level_roll
# /level_roll_remove
# /level_roll_list


# =========================================================
# COMMAND ERROR HANDLER
# =========================================================

@bot.tree.error
async def on_app_command_error(
    interaction,
    error
):

    print(
        "Slash command error:",
        repr(error)
    )

    try:

        if isinstance(
            error,
            app_commands.MissingPermissions
        ):

            message = (
                "❌ ليس لديك الصلاحيات المطلوبة."
            )

        elif isinstance(
            error,
            app_commands.BotMissingPermissions
        ):

            message = (
                "❌ البوت لا يملك الصلاحيات المطلوبة."
            )

        elif isinstance(
            error,
            app_commands.CommandOnCooldown
        ):

            message = (
                "⏳ الأمر على كول داون."
            )

        else:

            message = (
                "❌ حدث خطأ أثناء تنفيذ الأمر."
            )

        if interaction.response.is_done():

            await interaction.followup.send(
                message,
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                message,
                ephemeral=True
            )

    except Exception as e:

        print(
            "Error handler error:",
            e
        )


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    global _background_task
    global _started
    global _sync_done

    print("=" * 55)

    print(
        f"🌙 Lunex connected as "
        f"{bot.user} ({bot.user.id})"
    )

    print(
        f"🏠 Servers: {len(bot.guilds)}"
    )

    print(
        f"👥 Users cached: {len(bot.users)}"
    )

    print("=" * 55)

    # -----------------------------------------------------
    # Persistent Views
    # -----------------------------------------------------

    if not _started:

        try:

            bot.add_view(
                TicketView()
            )

            bot.add_view(
                CloseTicketView()
            )

            bot.add_view(
                HelpView()
            )

            print(
                "✅ Persistent views registered."
            )

        except Exception as e:

            print(
                "View registration error:",
                e
            )

        _started = True

    # -----------------------------------------------------
    # Sync Slash Commands
    # -----------------------------------------------------

    if not _sync_done:

        try:

            synced = await bot.tree.sync()

            print(
                f"✅ Synced {len(synced)} slash commands."
            )

            _sync_done = True

        except Exception as e:

            print(
                "❌ Slash command sync error:",
                e
            )

    # -----------------------------------------------------
    # Background Tasks
    # -----------------------------------------------------

    if _background_task is None:

        _background_task = asyncio.create_task(
            background_loop()
        )

        asyncio.create_task(
            premium_loop()
        )

        print(
            "✅ Background tasks started."
        )


# =========================================================
# STARTUP
# =========================================================

async def startup():

    await init_database()

    print(
        "🚀 Starting Lunex..."
    )

    await bot.start(
        TOKEN
    )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            startup()
        )

    except KeyboardInterrupt:

        print(
            "🛑 Lunex stopped."
        )

    except Exception as e:

        print(
            "❌ Fatal error:",
            repr(e)
        )
