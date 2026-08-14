# =========================================================
# LUNEX BOT — FINAL RAILWAY EDITION
# Compatible with the provided app.py
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
import threading
from datetime import timedelta, datetime, timezone

import discord
from discord.ext import commands, tasks
from discord import app_commands

import certifi


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

SUPPORT_INVITE = (
    "https://discord.gg/FMEXcwAvg"
)

BOT_INVITE = (
    "https://discord.com/oauth2/authorize"
    "?client_id=1501541120058851348"
    "&permissions=8"
    "&integration_type=0"
    "&scope=bot"
)


# =========================================================
# ENV CHECK
# =========================================================

if not TOKEN:
    raise RuntimeError(
        "DISCORD_BOT_TOKEN is missing."
    )

if not MONGODB_URI:
    print(
        "⚠️ MONGODB_URI is missing. "
        "MongoDB settings will use memory fallback."
    )


# =========================================================
# MONGODB
# =========================================================

mongo = None
mdb = None
guild_settings = None
mongo_available = False


def connect_mongodb():

    global mongo
    global mdb
    global guild_settings
    global mongo_available

    if not MONGODB_URI:
        print(
            "⚠️ MongoDB URI not configured."
        )
        return

    try:

        from pymongo import MongoClient

        mongo = MongoClient(
            MONGODB_URI,
            tls=True,
            tlsCAFile=certifi.where(),

            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,

            maxPoolSize=20,
            minPoolSize=1,

            retryWrites=True
        )

        # لا نجعل فشل ping يمنع تشغيل البوت.
        mongo.admin.command(
            "ping"
        )

        mdb = mongo.get_default_database()

        if mdb is None:

            print(
                "⚠️ MongoDB URI has no default database."
            )

            mongo_available = False
            return

        guild_settings = mdb[
            "guildsettings"
        ]

        mongo_available = True

        print(
            "✅ MongoDB connected."
        )

    except Exception as e:

        mongo_available = False

        print(
            "⚠️ MongoDB unavailable."
        )

        print(
            "MongoDB error:",
            repr(e)
        )

        print(
            "⚠️ Lunex will continue using memory settings."
        )


connect_mongodb()


# =========================================================
# DEFAULT SETTINGS
# =========================================================

DEFAULT_SETTINGS = {

    "guildId": None,

    "welcome": {

        "enabled": False,

        "channelId": None,

        "message":
            "اهلا [User] فيك بالسيرفر!"
    },

    "leave": {

        "enabled": False,

        "channelId": None,

        "message":
            "وداعا [User] :("
    },

    "ticket": {

        "enabled": False,

        "image": "",

        "message":
            "اضغط الزر بالأسفل لفتح تكت جديد",

        "description":
            "مرحبا [User]، فريق الدعم راح يرد عليك قريبا",

        "categoryId": None,

        "closedCategoryId": None,

        "channelId": None,

        "supportRoleId": None,

        "allowUserClose": True,

        "deleteAfterClose": True
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
# MEMORY SETTINGS
# =========================================================

memory_settings = {}

settings_cache = {}

SETTINGS_CACHE_TTL = 300


# =========================================================
# SETTINGS HELPERS
# =========================================================

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

    if not isinstance(data, dict):
        return settings

    settings["guildId"] = data.get(
        "guildId"
    )

    for key in (
        "welcome",
        "leave",
        "ticket",
        "protection"
    ):

        if isinstance(
            data.get(key),
            dict
        ):

            settings[key].update(
                data[key]
            )

    if isinstance(
        data.get("autoReplies"),
        list
    ):

        settings["autoReplies"] = list(
            data["autoReplies"]
        )

    if isinstance(
        data.get("commandAliases"),
        list
    ):

        settings["commandAliases"] = list(
            data["commandAliases"]
        )

    if isinstance(
        data.get("badwords"),
        dict
    ):

        settings["badwords"] = dict(
            data["badwords"]
        )

    return settings


# =========================================================
# GET SETTINGS
#
# IMPORTANT:
# app.py calls this synchronously.
# Therefore this function is NOT async.
# =========================================================

def get_settings(
    guild_id: str
):

    guild_id = str(
        guild_id
    )

    now = time.time()

    cached = settings_cache.get(
        guild_id
    )

    if cached:

        expires_at, data = cached

        if now < expires_at:

            return data

    # -----------------------------------------
    # MongoDB
    # -----------------------------------------

    if mongo_available and guild_settings:

        try:

            doc = guild_settings.find_one(
                {
                    "guildId":
                        guild_id
                }
            )

            if doc:

                data = merge_settings(
                    doc
                )

            else:

                data = clone_defaults()

                data["guildId"] = guild_id

                guild_settings.update_one(

                    {
                        "guildId":
                            guild_id
                    },

                    {
                        "$setOnInsert":
                            data
                    },

                    upsert=True
                )

        except Exception as e:

            print(
                "⚠️ MongoDB get settings error:",
                repr(e)
            )

            data = memory_settings.get(
                guild_id,
                clone_defaults()
            )

    else:

        data = memory_settings.get(
            guild_id,
            clone_defaults()
        )

    data = merge_settings(
        data
    )

    data["guildId"] = guild_id

    memory_settings[guild_id] = data

    settings_cache[guild_id] = (

        now + SETTINGS_CACHE_TTL,

        data
    )

    return data


# =========================================================
# UPDATE SETTINGS
#
# IMPORTANT:
# app.py calls this synchronously.
# =========================================================

def update_settings(
    guild_id: str,
    update: dict
):

    guild_id = str(
        guild_id
    )

    if not isinstance(
        update,
        dict
    ):

        return get_settings(
            guild_id
        )

    current = get_settings(
        guild_id
    )

    # -----------------------------------------
    # Nested settings
    # -----------------------------------------

    result = merge_settings(
        current
    )

    for key, value in update.items():

        if key in (
            "welcome",
            "leave",
            "ticket",
            "protection"
        ):

            if isinstance(
                value,
                dict
            ):

                result[key].update(
                    value
                )

        elif key in (
            "autoReplies",
            "commandAliases"
        ):

            if isinstance(
                value,
                list
            ):

                result[key] = list(
                    value
                )

        elif key == "badwords":

            if isinstance(
                value,
                dict
            ):

                result["badwords"] = dict(
                    value
                )

        else:

            result[key] = value

    result["guildId"] = guild_id

    # -----------------------------------------
    # Memory
    # -----------------------------------------

    memory_settings[guild_id] = result

    # -----------------------------------------
    # MongoDB
    # -----------------------------------------

    if mongo_available and guild_settings:

        try:

            mongo_update = {}

            for key, value in update.items():

                mongo_update[
                    key
                ] = value

            mongo_update[
                "guildId"
            ] = guild_id

            guild_settings.update_one(

                {
                    "guildId":
                        guild_id
                },

                {
                    "$set":
                        mongo_update
                },

                upsert=True
            )

        except Exception as e:

            print(
                "⚠️ MongoDB update settings error:",
                repr(e)
            )

    settings_cache.pop(
        guild_id,
        None
    )

    return get_settings(
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
        member.display_name
    )

    text = text.replace(
        "[username]",
        member.display_name
    )

    text = text.replace(
        "[Img]",
        member.display_avatar.url
    )

    text = text.replace(
        "[img]",
        member.display_avatar.url
    )

    text = text.replace(
        "[member_count]",
        str(
            member.guild.member_count
        )
    )

    text = text.replace(
        "[nember]",
        str(
            member.guild.member_count
        )
    )

    text = text.replace(
        "[Server]",
        member.guild.name
    )

    text = text.replace(
        "[server]",
        member.guild.name
    )

    return text


# =========================================================
# DISCORD INTENTS
# =========================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.message_content = True
intents.messages = True


# =========================================================
# BOT
# =========================================================

bot = commands.Bot(

    command_prefix=[
        "!",
        "#"
    ],

    intents=intents,

    case_insensitive=True,

    help_command=None
)


# =========================================================
# GLOBAL STATE
# =========================================================

db = None

db_lock = threading.Lock()

xp_pending = {}

spam_cache = {}

badword_cache = {}

_views_registered = False

_commands_synced = False

_background_started = False


# =========================================================
# SQLITE
# =========================================================

def init_database():

    global db

    if db is not None:
        return

    db = sqlite3.connect(

        "lunex.db",

        check_same_thread=False
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS xp(
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            messages INTEGER DEFAULT 0,
            day_count INTEGER DEFAULT 0,
            week_count INTEGER DEFAULT 0,
            month_count INTEGER DEFAULT 0,
            PRIMARY KEY(guild_id, user_id)
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS warns(
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            warns INTEGER DEFAULT 0,
            PRIMARY KEY(guild_id, user_id)
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS premium_users(
            user_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            role_id TEXT,
            expiry_time REAL,
            PRIMARY KEY(user_id, guild_id)
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_settings(
            user_id TEXT PRIMARY KEY,
            lang TEXT DEFAULT 'en'
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS reset_tracker(
            id INTEGER PRIMARY KEY CHECK(id = 1),
            last_day TEXT,
            last_week TEXT,
            last_month TEXT
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS level_roles(
            guild_id TEXT,
            level INTEGER,
            role_id TEXT,
            PRIMARY KEY(guild_id, level)
        )
        """
    )

    db.commit()

    print(
        "✅ SQLite database initialized."
    )


init_database()


# =========================================================
# LOCALIZATION
# =========================================================

locales = {

    "en": {

        "lang_set":
            "Your personal language has been set to English.",

        "higher_bot":
            "Their role is higher than or equal to mine.",

        "higher_user":
            "Their role is higher than or equal to yours.",

        "banned":
            "Member banned successfully.",

        "kicked":
            "Member kicked successfully.",

        "unbanned":
            "User unbanned successfully.",

        "timeout_applied":
            "Timeout applied successfully.",

        "timeout_removed":
            "Timeout removed successfully.",

        "channel_locked":
            "Channel locked successfully.",

        "channel_unlocked":
            "Channel unlocked successfully.",

        "role_added":
            "Role added successfully.",

        "role_removed":
            "Role removed successfully.",

        "nick_changed":
            "Nickname changed successfully.",

        "cleared":
            "Cleared {} messages.",

        "invalid_time":
            "Invalid time format. Example: `10m`, `1h`, `1d`.",

        "error":
            "An error occurred.",

        "no_permission":
            "You don't have permission to use this command."
    },

    "ar": {

        "lang_set":
            "تم تعيين لغتك الشخصية إلى العربية.",

        "higher_bot":
            "رتبة هذا العضو أعلى من رتبتي أو مساوية لها.",

        "higher_user":
            "رتبة هذا العضو أعلى من رتبتك أو مساوية لها.",

        "banned":
            "تم حظر العضو بنجاح.",

        "kicked":
            "تم طرد العضو بنجاح.",

        "unbanned":
            "تم فك الحظر عن المستخدم.",

        "timeout_applied":
            "تم إعطاء العضو تايم أوت بنجاح.",

        "timeout_removed":
            "تم إزالة التايم أوت عن العضو.",

        "channel_locked":
            "تم قفل القناة بنجاح.",

        "channel_unlocked":
            "تم فتح القناة بنجاح.",

        "role_added":
            "تم إعطاء الرتبة بنجاح.",

        "role_removed":
            "تم سحب الرتبة بنجاح.",

        "nick_changed":
            "تم تغيير اللقب بنجاح.",

        "cleared":
            "تم مسح `{}` رسالة.",

        "invalid_time":
            "صيغة الوقت غير صحيحة. مثال: `10m` أو `1h` أو `1d`.",

        "error":
            "حدث خطأ.",

        "no_permission":
            "ليس لديك صلاحية لاستخدام هذا الأمر."
    }
}


# =========================================================
# LANGUAGE FUNCTIONS
# =========================================================

def get_lang(
    user_id
):

    try:

        with db_lock:

            cursor = db.execute(

                """
                SELECT lang
                FROM user_settings
                WHERE user_id=?
                """,

                (
                    str(user_id),
                )
            )

            row = cursor.fetchone()

        if row and row[0] in locales:

            return row[0]

    except Exception as e:

        print(
            "Language error:",
            repr(e)
        )

    return "en"


def t(
    user_id,
    key,
    *args
):

    lang = get_lang(
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

def parse_time(
    value
):

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

    return (
        number
        * multipliers[unit]
    )


# =========================================================
# XP
# =========================================================

XP_PER_LEVEL = 20


def calculate_level(
    messages
):

    return max(
        0,
        int(messages)
        // XP_PER_LEVEL
    )


def messages_for_next_level(
    messages
):

    level = calculate_level(
        messages
    )

    target = (
        (level + 1)
        * XP_PER_LEVEL
    )

    return max(
        0,
        target - messages
    )


def get_xp_data(
    guild_id,
    user_id
):

    guild_id = str(
        guild_id
    )

    user_id = str(
        user_id
    )

    with db_lock:

        cursor = db.execute(

            """
            SELECT
                messages,
                day_count,
                week_count,
                month_count
            FROM xp
            WHERE guild_id=?
            AND user_id=?
            """,

            (
                guild_id,
                user_id
            )
        )

        row = cursor.fetchone()

    result = {

        "messages": 0,

        "day_count": 0,

        "week_count": 0,

        "month_count": 0
    }

    if row:

        result = {

            "messages":
                int(row[0] or 0),

            "day_count":
                int(row[1] or 0),

            "week_count":
                int(row[2] or 0),

            "month_count":
                int(row[3] or 0)
        }

    pending = xp_pending.get(

        (
            guild_id,
            user_id
        ),

        {}
    )

    return {

        key:
            result[key]
            + int(
                pending.get(
                    key,
                    0
                )
            )

        for key in result
    }


def get_user_xp(
    guild_id,
    user_id
):

    return get_xp_data(
        guild_id,
        user_id
    )["messages"]


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

    xp_pending[key][
        "messages"
    ] += 1

    xp_pending[key][
        "day_count"
    ] += 1

    xp_pending[key][
        "week_count"
    ] += 1

    xp_pending[key][
        "month_count"
    ] += 1


# =========================================================
# FLUSH XP
# =========================================================

def flush_xp():

    global xp_pending

    if not xp_pending:
        return

    pending = xp_pending

    xp_pending = {}

    try:

        with db_lock:

            for (
                guild_id,
                user_id
            ), values in pending.items():

                db.execute(

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

                    ON CONFLICT(
                        guild_id,
                        user_id
                    )
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

            db.commit()

    except Exception as e:

        print(
            "❌ XP flush error:",
            repr(e)
        )

        for key, values in pending.items():

            if key not in xp_pending:

                xp_pending[key] = {

                    "messages": 0,

                    "day_count": 0,

                    "week_count": 0,

                    "month_count": 0
                }

            for field, value in values.items():

                xp_pending[key][field] += value


# =========================================================
# LEVEL ROLES
# =========================================================

def set_level_role(
    guild_id,
    level,
    role_id
):

    with db_lock:

        db.execute(

            """
            INSERT INTO level_roles(
                guild_id,
                level,
                role_id
            )

            VALUES (?, ?, ?)

            ON CONFLICT(
                guild_id,
                level
            )

            DO UPDATE SET
                role_id=excluded.role_id
            """,

            (
                str(guild_id),

                int(level),

                str(role_id)
            )
        )

        db.commit()


def get_level_role(
    guild_id,
    level
):

    with db_lock:

        cursor = db.execute(

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
        )

        row = cursor.fetchone()

    if not row:
        return None

    try:

        return int(
            row[0]
        )

    except Exception:

        return None


def remove_level_role(
    guild_id,
    level
):

    with db_lock:

        db.execute(

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

        db.commit()


def get_all_level_roles(
    guild_id
):

    with db_lock:

        cursor = db.execute(

            """
            SELECT level, role_id
            FROM level_roles
            WHERE guild_id=?
            ORDER BY level ASC
            """,

            (
                str(guild_id),
            )
        )

        return cursor.fetchall()


async def give_level_role(
    member,
    level
):

    role_id = get_level_role(

        member.guild.id,

        level
    )

    if not role_id:
        return

    role = member.guild.get_role(
        role_id
    )

    if not role:
        return

    me = member.guild.me

    if not me:
        return

    if role >= me.top_role:

        print(
            "⚠️ Cannot give level role:",
            role.id
        )

        return

    try:

        await member.add_roles(

            role,

            reason=
                f"Lunex Level {level}"
        )

    except Exception as e:

        print(
            "Level role error:",
            repr(e)
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

            "This command can only be used in a server.",

            ephemeral=True
        )

        return False

    me = guild.me

    if not me:

        await interaction.response.send_message(

            "❌ Bot member is unavailable.",

            ephemeral=True
        )

        return False

    if member == guild.owner:

        await interaction.response.send_message(

            "❌ لا يمكنك استخدام الأمر على مالك السيرفر.",

            ephemeral=True
        )

        return False

    if member == me:

        await interaction.response.send_message(

            "❌ لا يمكنني تنفيذ الأمر على نفسي.",

            ephemeral=True
        )

        return False

    if member.top_role >= me.top_role:

        await interaction.response.send_message(

            t(
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

            t(
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

        channel = interaction.channel

        if not channel:

            await interaction.response.send_message(

                "Channel unavailable.",

                ephemeral=True
            )

            return

        settings = get_settings(
            interaction.guild.id
        )

        ticket = settings.get(
            "ticket",
            {}
        )

        support_role_id = ticket.get(
            "supportRoleId"
        )

        allowed = False

        if interaction.user.guild_permissions.manage_channels:

            allowed = True

        if support_role_id:

            try:

                role = interaction.guild.get_role(
                    int(support_role_id)
                )

                if role and role in interaction.user.roles:

                    allowed = True

            except Exception:
                pass

        if not allowed:

            await interaction.response.send_message(

                "❌ ليس لديك صلاحية لإغلاق التذكرة.",

                ephemeral=True
            )

            return

        await interaction.response.send_message(

            "🔒 سيتم إغلاق التذكرة خلال 5 ثوانٍ..."
        )

        await asyncio.sleep(
            5
        )

        delete_after = ticket.get(
            "deleteAfterClose",
            True
        )

        if delete_after:

            try:

                await channel.delete(
                    reason="Lunex ticket closed"
                )

            except Exception as e:

                print(
                    "Ticket delete error:",
                    repr(e)
                )

        else:

            try:

                await channel.edit(
                    name=
                        f"closed-{channel.name}"
                )

            except Exception:
                pass


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

        guild = interaction.guild

        if not guild:

            await interaction.response.send_message(

                "This button can only be used in a server.",

                ephemeral=True
            )

            return

        settings = get_settings(
            guild.id
        )

        ticket = settings.get(
            "ticket",
            {}
        )

        # -----------------------------------------
        # Ticket name
        # -----------------------------------------

        safe_name = re.sub(

            r"[^a-z0-9\-]",

            "",

            (
                f"ticket-{interaction.user.name}"
            ).lower()
        )

        if not safe_name:

            safe_name = (
                f"ticket-{interaction.user.id}"
            )

        # Discord channel name limit
        safe_name = safe_name[:90]

        existing = discord.utils.get(

            guild.text_channels,

            name=safe_name
        )

        if existing:

            await interaction.response.send_message(

                f"🎫 لديك تذكرة بالفعل: {existing.mention}",

                ephemeral=True
            )

            return

        # -----------------------------------------
        # Category
        # -----------------------------------------

        category = None

        category_id = ticket.get(
            "categoryId"
        )

        if category_id:

            try:

                category = guild.get_channel(
                    int(category_id)
                )

                if not isinstance(
                    category,
                    discord.CategoryChannel
                ):

                    category = None

            except Exception:

                category = None

        # -----------------------------------------
        # Support role
        # -----------------------------------------

        support_role = None

        support_role_id = ticket.get(
            "supportRoleId"
        )

        if support_role_id:

            try:

                support_role = guild.get_role(
                    int(support_role_id)
                )

            except Exception:

                support_role = None

        # -----------------------------------------
        # Permissions
        # -----------------------------------------

        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            interaction.user:
                discord.PermissionOverwrite(

                    view_channel=True,

                    send_messages=True,

                    read_message_history=True,

                    attach_files=True,

                    embed_links=True
                ),

            guild.me:
                discord.PermissionOverwrite(

                    view_channel=True,

                    send_messages=True,

                    read_message_history=True,

                    manage_channels=True,

                    manage_messages=True
                )
        }

        if support_role:

            overwrites[
                support_role
            ] = discord.PermissionOverwrite(

                view_channel=True,

                send_messages=True,

                read_message_history=True
            )

        # -----------------------------------------
        # Create
        # -----------------------------------------

        try:

            channel = await guild.create_text_channel(

                safe_name,

                overwrites=overwrites,

                category=category,

                reason="Lunex ticket opened"
            )

        except Exception as e:

            print(
                "Create ticket error:",
                repr(e)
            )

            await interaction.response.send_message(

                "❌ لم أستطع إنشاء التذكرة. "
                "تأكد من صلاحيات البوت.",

                ephemeral=True
            )

            return

        # -----------------------------------------
        # Embed
        # -----------------------------------------

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

        embed.set_footer(
            text="Lunex • Support"
        )

        # -----------------------------------------
        # Send
        # -----------------------------------------

        content = interaction.user.mention

        if support_role:

            content += (
                f" {support_role.mention}"
            )

        try:

            await channel.send(

                content=content,

                embed=embed,

                view=CloseTicketView()
            )

        except Exception as e:

            print(
                "Ticket message error:",
                repr(e)
            )

        await interaction.response.send_message(

            f"🎫 تم فتح التذكرة: {channel.mention}",

            ephemeral=True
        )


# =========================================================
# TICKET PANEL
# =========================================================

async def ticket_panel(
    channel
):

    settings = get_settings(
        channel.guild.id
    )

    ticket = settings.get(
        "ticket",
        {}
    )

    embed = discord.Embed(

        title="🎫 Lunex Support",

        description=(

            ticket.get(
                "message"
            )
            or
            "اضغط الزر بالأسفل لفتح تكت جديد."
        ),

        color=COLOR
    )

    if bot.user:

        embed.set_thumbnail(
            url=bot.user.display_avatar.url
        )

    image = ticket.get(
        "image"
    )

    if image:

        embed.set_image(
            url=image
        )

    embed.set_footer(
        text="Lunex • More than a bot"
    )

    await channel.send(

        embed=embed,

        view=TicketView()
    )


# =========================================================
# IMPORTANT:
# app.py calls:
#
# post_ticket_panel(guild_id, channel_id)
#
# =========================================================

async def post_ticket_panel(
    guild_id,
    channel_id
):

    guild = bot.get_guild(
        int(guild_id)
    )

    if not guild:

        raise RuntimeError(
            "Guild not found."
        )

    channel = guild.get_channel(
        int(channel_id)
    )

    if not channel:

        raise RuntimeError(
            "Channel not found."
        )

    if not isinstance(
        channel,
        discord.TextChannel
    ):

        raise RuntimeError(
            "Channel must be a text channel."
        )

    await ticket_panel(
        channel
    )


# =========================================================
# HELP SELECT
# =========================================================

class HelpSelect(
    discord.ui.Select
):

    def __init__(self):

        options = [

            discord.SelectOption(

                label="Member",

                value="member",

                description=
                    "XP, levels and profile",

                emoji="👥"
            ),

            discord.SelectOption(

                label="Moderation",

                value="moderation",

                description=
                    "Moderation commands",

                emoji="🛡️"
            ),

            discord.SelectOption(

                label="Management",

                value="management",

                description=
                    "Server management",

                emoji="⚙️"
            ),

            discord.SelectOption(

                label="Security",

                value="security",

                description=
                    "Protection commands",

                emoji="🔐"
            )
        ]

        super().__init__(

            placeholder=
                "اختر قسم الأوامر",

            options=options,

            custom_id=
                "lunex_help_select"
        )

    async def callback(
        self,
        interaction
    ):

        value = self.values[0]

        if value == "member":

            embed = discord.Embed(

                title="👥 MEMBER COMMANDS",

                description=(

                    "`/xp` — عرض XP\n"
                    "`/level` — عرض المستوى\n"
                    "`/profile` — البروفايل\n"
                    "`/avatar` — الأفاتار\n"
                    "`/server` — معلومات السيرفر\n"
                    "`/leaderboard` — الترتيب\n"
                    "`/language` — اللغة"
                ),

                color=COLOR
            )

        elif value == "moderation":

            embed = discord.Embed(

                title="🛡️ MODERATION COMMANDS",

                description=(

                    "`/ban` — حظر\n"
                    "`/kick` — طرد\n"
                    "`/unban` — فك الحظر\n"
                    "`/timeout` — تايم أوت\n"
                    "`/timeout_remove` — إزالة التايم أوت\n"
                    "`/clear` — مسح\n"
                    "`/lock` — قفل\n"
                    "`/open` — فتح\n"
                    "`/add_role` — إعطاء رتبة\n"
                    "`/remove_role` — سحب رتبة\n"
                    "`/nickname` — تغيير الاسم"
                ),

                color=COLOR
            )

        elif value == "management":

            embed = discord.Embed(

                title="⚙️ MANAGEMENT COMMANDS",

                description=(

                    "`/commands` — الأوامر\n"
                    "`/help` — المساعدة\n"
                    "`/ticket_panel` — لوحة التذاكر\n"
                    "`/auto_reply` — رد تلقائي\n"
                    "`/auto_reply_remove` — حذف رد\n"
                    "`/badword` — كلمة ممنوعة\n"
                    "`/level_roll` — ربط Level برتبة"
                ),

                color=COLOR
            )

        else:

            embed = discord.Embed(

                title="🔐 SECURITY COMMANDS",

                description=(

                    "`/protection` — إعداد الحماية\n"
                    "`/badword` — الكلمات الممنوعة\n"
                    "`/auto_reply` — الردود التلقائية\n\n"
                    "• Bad Words\n"
                    "• Links\n"
                    "• Anti Spam"
                ),

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


# =========================================================
# HELP VIEW
# =========================================================

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

                style=
                    discord.ButtonStyle.link
            )
        )

        self.add_item(

            discord.ui.Button(

                label="Support",

                emoji="💬",

                url=SUPPORT_INVITE,

                style=
                    discord.ButtonStyle.link
            )
        )

        self.add_item(

            discord.ui.Button(

                label="Website",

                emoji="🌐",

                url=SITE_URL,

                style=
                    discord.ButtonStyle.link
            )
        )


# =========================================================
# MAIN HELP
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

            f"كل **{XP_PER_LEVEL} رسالة = Level واحد**.\n"

            "يمكن ربط الـ Level برتبة."
        ),

        inline=False
    )

    embed.add_field(

        name="🎫 Tickets",

        value=(
            "نظام تذاكر كامل مع "
            "صلاحيات ودعم ورتبة."
        ),

        inline=False
    )

    embed.add_field(

        name="🛡️ Protection",

        value=(
            "Bad Words • Links • Anti Spam"
        ),

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

    description=
        "Show Lunex help menu"
)
async def help_command(
    interaction
):

    await interaction.response.send_message(

        embed=build_main_embed(),

        view=HelpView(),

        ephemeral=True
    )


# =========================================================
# /COMMANDS
# =========================================================

@bot.tree.command(

    name="commands",

    description=
        "Show Lunex commands"
)
async def commands_command(
    interaction
):

    embed = discord.Embed(

        title="🌙 Lunex Commands",

        description=(

            "### 👥 Member\n"
            "`/xp`\n"
            "`/level`\n"
            "`/profile`\n"
            "`/avatar`\n"
            "`/server`\n"
            "`/leaderboard`\n"
            "`/language`\n\n"

            "### 🛡️ Moderation\n"
            "`/ban`\n"
            "`/kick`\n"
            "`/unban`\n"
            "`/timeout`\n"
            "`/timeout_remove`\n"
            "`/clear`\n"
            "`/lock`\n"
            "`/open`\n"
            "`/add_role`\n"
            "`/remove_role`\n"
            "`/nickname`\n\n"

            "### 🎫 Tickets\n"
            "`/ticket_panel`\n"
            "`/ticket_config`\n\n"

            "### ⭐ XP\n"
            "`/level_roll`\n"
            "`/level_roll_remove`\n"
            "`/level_roll_list`"
        ),

        color=COLOR
    )

    await interaction.response.send_message(

        embed=embed,

        ephemeral=True
    )


# =========================================================
# /XP
# =========================================================

@bot.tree.command(

    name="xp",

    description="Show XP"
)
async def slash_xp(
    interaction
):

    if not interaction.guild:

        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True
        )

        return

    xp = get_user_xp(

        interaction.guild.id,

        interaction.user.id
    )

    level = calculate_level(
        xp
    )

    remaining = messages_for_next_level(
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

    embed.add_field(

        name="Next Level",

        value=f"`{remaining} رسالة`",

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

    description="Show your level"
)
async def slash_level(
    interaction
):

    if not interaction.guild:

        await interaction.response.send_message(

            "This command can only be used in a server.",

            ephemeral=True
        )

        return

    xp = get_user_xp(

        interaction.guild.id,

        interaction.user.id
    )

    level = calculate_level(
        xp
    )

    remaining = messages_for_next_level(
        xp
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

        name="💬 Messages",

        value=f"`{xp}`",

        inline=True
    )

    embed.add_field(

        name="⬆️ Next",

        value=f"`{remaining}`",

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

    description=
        "Show member profile"
)
@app_commands.describe(
    member="Member"
)
async def profile(

    interaction,

    member: discord.Member = None
):

    if not interaction.guild:

        await interaction.response.send_message(

            "This command can only be used in a server.",

            ephemeral=True
        )

        return

    member = (
        member
        or interaction.user
    )

    xp = get_user_xp(

        interaction.guild.id,

        member.id
    )

    level = calculate_level(
        xp
    )

    embed = discord.Embed(

        title=
            f"👤 {member.display_name}",

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

    description="Show avatar"
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

        title=
            f"🖼️ {member.display_name}",

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

    description=
        "Show server information"
)
async def server_info(
    interaction
):

    guild = interaction.guild

    if not guild:

        await interaction.response.send_message(

            "This command can only be used in a server.",

            ephemeral=True
        )

        return

    embed = discord.Embed(

        title=
            f"🏠 {guild.name}",

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

        name="💬 Channels",

        value=f"`{len(guild.channels)}`",

        inline=True
    )

    embed.add_field(

        name="🏷️ Roles",

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

    description=
        "Show XP leaderboard"
)
async def leaderboard(
    interaction
):

    if not interaction.guild:

        await interaction.response.send_message(

            "This command can only be used in a server.",

            ephemeral=True
        )

        return

    with db_lock:

        cursor = db.execute(

            """
            SELECT user_id, messages
            FROM xp
            WHERE guild_id=?
            ORDER BY messages DESC
            LIMIT 10
            """,

            (
                str(
                    interaction.guild.id
                ),
            )
        )

        rows = cursor.fetchall()

    if not rows:

        await interaction.response.send_message(

            "لا توجد بيانات XP حتى الآن.",

            ephemeral=True
        )

        return

    lines = []

    for index, (
        user_id,
        messages
    ) in enumerate(rows, 1):

        member = interaction.guild.get_member(
            int(user_id)
        )

        name = (
            member.display_name
            if member
            else f"User {user_id}"
        )

        level = calculate_level(
            messages
        )

        lines.append(

            f"**#{index}** "
            f"{name} — "
            f"`{messages} XP` "
            f"• Level `{level}`"
        )

    embed = discord.Embed(

        title="🏆 Lunex Leaderboard",

        description="\n".join(
            lines
        ),

        color=COLOR
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /LANGUAGE
# =========================================================

@bot.tree.command(

    name="language",

    description=
        "Change your language"
)
@app_commands.describe(
    language="ar or en"
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

    language
):

    with db_lock:

        db.execute(

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
                str(
                    interaction.user.id
                ),

                language.value
            )
        )

        db.commit()

    await interaction.response.send_message(

        t(
            interaction.user.id,
            "lang_set"
        ),

        ephemeral=True
    )


# =========================================================
# /BAN
# =========================================================

@bot.tree.command(

    name="ban",

    description="Ban a member"
)
@app_commands.describe(
    member="Member",
    reason="Reason"
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

            t(
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
    member="Member",
    reason="Reason"
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

            t(
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
            user
        )

        await interaction.response.send_message(

            t(
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
# /TIMEOUT
# =========================================================

@bot.tree.command(

    name="timeout",

    description="Timeout a member"
)
@app_commands.describe(

    member="Member",

    duration=
        "Example: 10m, 1h, 1d",

    reason="Reason"
)
@app_commands.default_permissions(
    moderate_members=True
)
async def timeout_member(

    interaction,

    member: discord.Member,

    duration: str,

    reason: str = "No reason provided"
):

    seconds = parse_time(
        duration
    )

    if not seconds:

        await interaction.response.send_message(

            t(
                interaction.user.id,
                "invalid_time"
            ),

            ephemeral=True
        )

        return

    if not await check_hierarchy(
        interaction,
        member
    ):
        return

    if seconds > 28 * 86400:

        await interaction.response.send_message(

            "❌ الحد الأقصى للتايم أوت هو 28 يوم.",

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

            t(
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

    description=
        "Remove timeout"
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
            None
        )

        await interaction.response.send_message(

            t(
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

    description=
        "Delete messages"
)
@app_commands.describe(
    amount="Amount"
)
@app_commands.default_permissions(
    manage_messages=True
)
async def clear(

    interaction,

    amount: app_commands.Range[
        int,
        1,
        100
    ]
):

    await interaction.response.defer(
        ephemeral=True
    )

    try:

        deleted = await interaction.channel.purge(

            limit=amount
            + 1
        )

        count = max(
            0,
            len(deleted) - 1
        )

        await interaction.followup.send(

            t(
                interaction.user.id,
                "cleared",
                count
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

    description=
        "Lock current channel"
)
@app_commands.default_permissions(
    manage_channels=True
)
async def lock(
    interaction
):

    channel = interaction.channel

    try:

        overwrite = (
            channel.overwrites_for(
                interaction.guild.default_role
            )
        )

        overwrite.send_messages = False

        await channel.set_permissions(

            interaction.guild.default_role,

            overwrite=overwrite,

            reason="Lunex channel lock"
        )

        await interaction.response.send_message(

            t(
                interaction.user.id,
                "channel_locked"
            )
        )

    except Exception as e:

        await interaction.response.send_message(

            f"❌ {e}",

            ephemeral=True
        )


# =========================================================
# /OPEN
# =========================================================

@bot.tree.command(

    name="open",

    description=
        "Unlock current channel"
)
@app_commands.default_permissions(
    manage_channels=True
)
async def open_channel(
    interaction
):

    channel = interaction.channel

    try:

        overwrite = (
            channel.overwrites_for(
                interaction.guild.default_role
            )
        )

        overwrite.send_messages = None

        await channel.set_permissions(

            interaction.guild.default_role,

            overwrite=overwrite,

            reason="Lunex channel unlock"
        )

        await interaction.response.send_message(

            t(
                interaction.user.id,
                "channel_unlocked"
            )
        )

    except Exception as e:

        await interaction.response.send_message(

            f"❌ {e}",

            ephemeral=True
        )


# =========================================================
# /ADD_ROLE
# =========================================================

@bot.tree.command(

    name="add_role",

    description=
        "Give a role"
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
            role
        )

        await interaction.response.send_message(

            t(
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

    description=
        "Remove a role"
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
            role
        )

        await interaction.response.send_message(

            t(
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

    description=
        "Change nickname"
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
            nick=nickname
        )

        await interaction.response.send_message(

            t(
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
# /TICKET_PANEL
# =========================================================

@bot.tree.command(

    name="ticket_panel",

    description=
        "Post ticket panel"
)
@app_commands.describe(
    channel="Ticket panel channel"
)
@app_commands.default_permissions(
    manage_channels=True
)
async def ticket_panel_command(

    interaction,

    channel: discord.TextChannel = None
):

    channel = (
        channel
        or interaction.channel
    )

    try:

        await ticket_panel(
            channel
        )

        await interaction.response.send_message(

            f"✅ تم نشر لوحة التذاكر في {channel.mention}.",

            ephemeral=True
        )

    except Exception as e:

        await interaction.response.send_message(

            f"❌ {e}",

            ephemeral=True
        )


# =========================================================
# /TICKET_CONFIG
# =========================================================

@bot.tree.command(

    name="ticket_config",

    description=
        "Enable or disable tickets"
)
@app_commands.describe(
    enabled="Enable tickets"
)
@app_commands.default_permissions(
    manage_channels=True
)
async def ticket_config(

    interaction,

    enabled: bool
):

    current = get_settings(
        interaction.guild.id
    )

    ticket = dict(
        current.get(
            "ticket",
            {}
        )
    )

    ticket["enabled"] = enabled

    update_settings(

        interaction.guild.id,

        {
            "ticket":
                ticket
        }
    )

    status = (
        "مفعلة"
        if enabled
        else "متوقفة"
    )

    await interaction.response.send_message(

        f"🎫 التذاكر الآن **{status}**."
    )


# =========================================================
# /LEVEL_ROLL
# =========================================================

@bot.tree.command(

    name="level_roll",

    description=
        "Assign a role at a level"
)
@app_commands.describe(

    level="Required level",

    role="Role to assign"
)
@app_commands.default_permissions(
    manage_roles=True
)
async def level_roll(

    interaction,

    level: app_commands.Range[
        int,
        1,
        100000
    ],

    role: discord.Role
):

    guild = interaction.guild

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

    if role >= guild.me.top_role:

        await interaction.response.send_message(

            "❌ الرتبة أعلى من رتبة البوت أو مساوية لها.",

            ephemeral=True
        )

        return

    set_level_role(

        guild.id,

        level,

        role.id
    )

    await interaction.response.send_message(

        f"🎯 تم ربط Level `{level}` بالرتبة {role.mention}."
    )


# =========================================================
# /LEVEL_ROLL_REMOVE
# =========================================================

@bot.tree.command(

    name="level_roll_remove",

    description=
        "Remove level role"
)
@app_commands.describe(
    level="Level"
)
@app_commands.default_permissions(
    manage_roles=True
)
async def level_roll_remove(

    interaction,

    level: app_commands.Range[
        int,
        1,
        100000
    ]
):

    remove_level_role(

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

    description=
        "List level roles"
)
async def level_roll_list(
    interaction
):

    rows = get_all_level_roles(

        interaction.guild.id
    )

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

                    f"⭐ Level `{level}` → "
                    f"{role.mention}"
                )

            else:

                lines.append(

                    f"⭐ Level `{level}` → "
                    "`Deleted Role`"
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

    description=
        "Add automatic reply"
)
@app_commands.describe(

    trigger="Trigger text",

    response="Response"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def auto_reply(

    interaction,

    trigger: str,

    response: str
):

    settings = get_settings(
        interaction.guild.id
    )

    replies = list(
        settings.get(
            "autoReplies",
            []
        )
    )

    replies.append({

        "trigger":
            trigger.lower(),

        "response":
            response
    })

    update_settings(

        interaction.guild.id,

        {
            "autoReplies":
                replies
        }
    )

    await interaction.response.send_message(

        "✅ تمت إضافة الرد التلقائي."
    )


# =========================================================
# /AUTO_REPLY_REMOVE
# =========================================================

@bot.tree.command(

    name="auto_reply_remove",

    description=
        "Remove automatic reply"
)
@app_commands.describe(
    trigger="Trigger"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def auto_reply_remove(

    interaction,

    trigger: str
):

    settings = get_settings(
        interaction.guild.id
    )

    replies = list(
        settings.get(
            "autoReplies",
            []
        )
    )

    before = len(
        replies
    )

    replies = [

        item

        for item in replies

        if str(
            item.get(
                "trigger",
                ""
            )
        ).lower()
        != trigger.lower()
    ]

    update_settings(

        interaction.guild.id,

        {
            "autoReplies":
                replies
        }
    )

    if len(replies) == before:

        await interaction.response.send_message(

            "❌ لم أجد هذا الرد.",

            ephemeral=True
        )

        return

    await interaction.response.send_message(

        "✅ تم حذف الرد التلقائي."
    )


# =========================================================
# /BADWORD
# =========================================================

@bot.tree.command(

    name="badword",

    description=
        "Manage bad words"
)
@app_commands.describe(
    word="Word"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def badword(

    interaction,

    word: str
):

    settings = get_settings(
        interaction.guild.id
    )

    words = dict(
        settings.get(
            "badwords",
            {}
        )
    )

    words[word.lower()] = True

    update_settings(

        interaction.guild.id,

        {
            "badwords":
                words
        }
    )

    await interaction.response.send_message(

        "✅ تمت إضافة الكلمة إلى قائمة الحظر."
    )


# =========================================================
# /PROTECTION
# =========================================================

@bot.tree.command(

    name="protection",

    description=
        "Configure protection"
)
@app_commands.describe(

    badwords="Bad words protection",

    links="Link protection",

    antispam="Anti spam"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def protection(

    interaction,

    badwords: bool = None,

    links: bool = None,

    antispam: bool = None
):

    settings = get_settings(
        interaction.guild.id
    )

    protection_settings = dict(

        settings.get(
            "protection",
            {}
        )
    )

    if badwords is not None:

        protection_settings[
            "badwords"
        ] = badwords

    if links is not None:

        protection_settings[
            "links"
        ] = links

    if antispam is not None:

        protection_settings[
            "antispam"
        ] = antispam

    update_settings(

        interaction.guild.id,

        {
            "protection":
                protection_settings
        }
    )

    await interaction.response.send_message(

        embed=discord.Embed(

            title="🛡️ Lunex Protection",

            description=(

                f"🚫 Bad Words: "
                f"`{protection_settings.get('badwords', True)}`\n"

                f"🔗 Links: "
                f"`{protection_settings.get('links', True)}`\n"

                f"⚡ Anti Spam: "
                f"`{protection_settings.get('antispam', True)}`"
            ),

            color=COLOR
        )
    )


# =========================================================
# MESSAGE PROTECTION
# =========================================================

LINK_REGEX = re.compile(

    r"(https?://|www\.)",

    re.IGNORECASE
)


def contains_badword(
    content,
    words
):

    content = content.lower()

    for word in words:

        if word.lower() in content:

            return True

    return False


async def handle_protection(
    message
):

    if not message.guild:
        return False

    if message.author.bot:
        return False

    settings = get_settings(
        message.guild.id
    )

    protection = settings.get(
        "protection",
        {}
    )

    # -----------------------------------------
    # Ignore moderators
    # -----------------------------------------

    if message.author.guild_permissions.manage_messages:

        return False

    # -----------------------------------------
    # Bad words
    # -----------------------------------------

    if protection.get(
        "badwords",
        True
    ):

        words = list(

            settings.get(
                "badwords",
                {}
            ).keys()
        )

        if words and contains_badword(
            message.content,
            words
        ):

            try:

                await message.delete(
                    reason="Lunex bad word filter"
                )

            except Exception:
                pass

            try:

                await message.channel.send(

                    f"⚠️ {message.author.mention} "
                    "تم حذف رسالتك لأنها تحتوي على كلمة ممنوعة.",

                    delete_after=5
                )

            except Exception:
                pass

            return True

    # -----------------------------------------
    # Links
    # -----------------------------------------

    if protection.get(
        "links",
        True
    ):

        if LINK_REGEX.search(
            message.content
        ):

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

    # -----------------------------------------
    # Anti Spam
    # -----------------------------------------

    if protection.get(
        "antispam",
        True
    ):

        key = (

            message.guild.id,

            message.author.id
        )

        now = time.time()

        entries = spam_cache.get(
            key,
            []
        )

        entries = [

            timestamp

            for timestamp in entries

            if now - timestamp < 5
        ]

        entries.append(
            now
        )

        spam_cache[key] = entries

        if len(entries) >= 7:

            try:

                await message.delete(
                    reason="Lunex anti spam"
                )

            except Exception:
                pass

            try:

                await message.channel.send(

                    f"⚡ {message.author.mention} "
                    "خفف سرعة الإرسال.",

                    delete_after=5
                )

            except Exception:
                pass

            return True

    return False


# =========================================================
# AUTO REPLIES
# =========================================================

async def handle_auto_replies(
    message
):

    if not message.guild:
        return

    settings = get_settings(
        message.guild.id
    )

    replies = settings.get(
        "autoReplies",
        []
    )

    content = message.content.lower().strip()

    for item in replies:

        if not isinstance(
            item,
            dict
        ):
            continue

        trigger = str(
            item.get(
                "trigger",
                ""
            )
        ).lower().strip()

        response = str(
            item.get(
                "response",
                ""
            )
        )

        if trigger and trigger in content:

            response = build_message(

                response,

                message.author
            )

            try:

                await message.channel.send(
                    response
                )

            except Exception:
                pass

            break


# =========================================================
# MESSAGE XP
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

    blocked = await handle_protection(
        message
    )

    if blocked:

        await bot.process_commands(
            message
        )

        return

    # -----------------------------------------
    # XP
    # -----------------------------------------

    guild_id = str(
        message.guild.id
    )

    user_id = str(
        message.author.id
    )

    old_xp = get_user_xp(

        guild_id,

        user_id
    )

    old_level = calculate_level(
        old_xp
    )

    add_xp_memory(

        guild_id,

        user_id
    )

    new_xp = old_xp + 1

    new_level = calculate_level(
        new_xp
    )

    # -----------------------------------------
    # Level up
    # -----------------------------------------

    if new_level > old_level:

        try:

            await give_level_role(

                message.author,

                new_level
            )

            await message.channel.send(

                f"🎉 {message.author.mention} "
                f"وصل إلى **Level {new_level}**!",

                delete_after=8
            )

        except Exception as e:

            print(
                "Level up error:",
                repr(e)
            )

    # -----------------------------------------
    # Auto reply
    # -----------------------------------------

    await handle_auto_replies(
        message
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

    settings = get_settings(
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

    try:

        channel = member.guild.get_channel(

            int(channel_id)
        )

    except Exception:

        channel = None

    if not isinstance(
        channel,
        discord.TextChannel
    ):
        return

    message = build_message(

        welcome.get(
            "message",
            "اهلا [User] فيك بالسيرفر!"
        ),

        member
    )

    try:

        await channel.send(
            message
        )

    except Exception as e:

        print(
            "Welcome error:",
            repr(e)
        )


# =========================================================
# LEAVE
# =========================================================

@bot.event
async def on_member_remove(
    member
):

    settings = get_settings(
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

    try:

        channel = member.guild.get_channel(

            int(channel_id)
        )

    except Exception:

        channel = None

    if not isinstance(
        channel,
        discord.TextChannel
    ):
        return

    message = build_message(

        leave.get(
            "message",
            "وداعا [User] :("
        ),

        member
    )

    try:

        await channel.send(
            message
        )

    except Exception as e:

        print(
            "Leave error:",
            repr(e)
        )


# =========================================================
# XP BACKGROUND TASK
# =========================================================

@tasks.loop(
    seconds=10
)
async def xp_flush_task():

    try:

        await asyncio.to_thread(
            flush_xp
        )

    except Exception as e:

        print(
            "XP task error:",
            repr(e)
        )


# =========================================================
# PREMIUM CLEANUP
# =========================================================

@tasks.loop(
    minutes=10
)
async def premium_cleanup_task():

    try:

        now = time.time()

        with db_lock:

            db.execute(

                """
                DELETE FROM premium_users
                WHERE expiry_time IS NOT NULL
                AND expiry_time > 0
                AND expiry_time <= ?
                """,

                (
                    now,
                )
            )

            db.commit()

    except Exception as e:

        print(
            "Premium cleanup error:",
            repr(e)
        )


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    global _views_registered
    global _commands_synced
    global _background_started

    print(
        "=================================================="
    )

    print(
        f"🤖 Logged in as: {bot.user}"
    )

    print(
        f"🆔 Bot ID: {bot.user.id}"
    )

    print(
        f"🌐 Guilds: {len(bot.guilds)}"
    )

    print(
        f"🗄️ MongoDB: "
        f"{'ONLINE' if mongo_available else 'OFFLINE/FALLBACK'}"
    )

    print(
        "=================================================="
    )

    # -----------------------------------------
    # Persistent views
    # -----------------------------------------

    if not _views_registered:

        try:

            bot.add_view(
                TicketView()
            )

            bot.add_view(
                CloseTicketView()
            )

            _views_registered = True

            print(
                "✅ Ticket views registered."
            )

        except Exception as e:

            print(
                "View registration error:",
                repr(e)
            )

    # -----------------------------------------
    # Sync commands
    # -----------------------------------------

    if not _commands_synced:

        try:

            synced = await bot.tree.sync()

            _commands_synced = True

            print(
                f"✅ Synced {len(synced)} slash commands."
            )

        except Exception as e:

            print(
                "❌ Slash command sync error:",
                repr(e)
            )

    # -----------------------------------------
    # Tasks
    # -----------------------------------------

    if not _background_started:

        try:

            if not xp_flush_task.is_running():

                xp_flush_task.start()

            if not premium_cleanup_task.is_running():

                premium_cleanup_task.start()

            _background_started = True

        except Exception as e:

            print(
                "Background task error:",
                repr(e)
            )

    # -----------------------------------------
    # Presence
    # -----------------------------------------

    try:

        await bot.change_presence(

            activity=discord.Activity(

                type=discord.ActivityType.watching,

                name=
                    f"{len(bot.guilds)} servers • /help"
            )
        )

    except Exception:
        pass


# =========================================================
# COMMAND ERROR HANDLER
# =========================================================

@bot.tree.error
async def on_app_command_error(
    interaction,
    error
):

    original = getattr(
        error,
        "original",
        error
    )

    print(
        "Slash command error:",
        repr(original)
    )

    message = (
        "❌ حدث خطأ أثناء تنفيذ الأمر."
    )

    try:

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

    except Exception:
        pass


# =========================================================
# SHUTDOWN
# =========================================================

@bot.event
async def on_disconnect():

    print(
        "⚠️ Discord disconnected."
    )


# =========================================================
# LEGACY COMMANDS
# =========================================================

@bot.command(
    name="me"
)
async def legacy_me(
    ctx
):

    member = ctx.author

    xp = get_user_xp(

        ctx.guild.id,

        member.id
    )

    level = calculate_level(
        xp
    )

    embed = discord.Embed(

        title=
            f"👤 {member.display_name}",

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

    await ctx.send(
        embed=embed
    )


# =========================================================
# LEGACY AVATAR
# =========================================================

@bot.command(
    name="avatar"
)
async def legacy_avatar(
    ctx
):

    member = ctx.author

    embed = discord.Embed(
        title="🖼️ Avatar",
        color=COLOR
    )

    embed.set_image(
        url=member.display_avatar.url
    )

    await ctx.send(
        embed=embed
    )


# =========================================================
# LEGACY SERVER
# =========================================================

@bot.command(
    name="server"
)
async def legacy_server(
    ctx
):

    guild = ctx.guild

    embed = discord.Embed(

        title=
            f"🏠 {guild.name}",

        color=COLOR
    )

    embed.add_field(

        name="👥 Members",

        value=f"`{guild.member_count}`",

        inline=True
    )

    embed.add_field(

        name="💬 Channels",

        value=f"`{len(guild.channels)}`",

        inline=True
    )

    embed.add_field(

        name="🏷️ Roles",

        value=f"`{len(guild.roles)}`",

        inline=True
    )

    await ctx.send(
        embed=embed
    )


# =========================================================
# BOT RUN
#
# app.py starts bot.run(BOT_TOKEN)
# Therefore bot.py DOES NOT run bot here.
# =========================================================

print(
    "✅ Lunex bot module loaded successfully."
)
