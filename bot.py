# ============================================================
# LUNEX BOT — FULL POWER EDITION
# discord.py 2.x
# Railway + MongoDB + SQLite
#
# WEBSITE ONLY:
#   - Welcome settings
#   - Ticket settings
#   - Command aliases / edit commands
#
# MEMBER:
#   /commands
#   /help
#   /server
#   /me
#   /profile
#   /xp
#   /level
#   /register
#   /top
#   /top_day
#   /top_week
#
# STAFF:
#   Moderation
#   Protection
#   XP Management
#   Server Management
#   Information
# ============================================================

import os
import re
import time
import sqlite3
import asyncio
from datetime import timedelta

import discord
from discord.ext import commands
from discord import app_commands

from dotenv import load_dotenv

from motor.motor_asyncio import AsyncIOMotorClient
import certifi


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")

SITE_URL = os.getenv(
    "FRONTEND_URL",
    "https://lunex.example"
)

DB_PATH = os.getenv(
    "SQLITE_PATH",
    "lunex.db"
)

if not TOKEN:
    raise RuntimeError(
        "DISCORD_BOT_TOKEN is missing."
    )

if not MONGODB_URI:
    raise RuntimeError(
        "MONGODB_URI is missing."
    )


# ============================================================
# INTENTS
# ============================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.message_content = True


# ============================================================
# BOT
# ============================================================

class LunexBot(commands.Bot):

    def __init__(self):

        super().__init__(
            command_prefix="!",
            intents=intents,
            case_insensitive=True,
            help_command=None
        )


bot = LunexBot()


# ============================================================
# MONGODB
# ============================================================

mongo = AsyncIOMotorClient(
    MONGODB_URI,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000,
    socketTimeoutMS=5000,
    maxPoolSize=20,
    minPoolSize=1
)

db = mongo["lunex"]

guild_settings = db["guild_settings"]


# ============================================================
# SQLITE
# ============================================================

def sqlite_connection():

    return sqlite3.connect(
        DB_PATH,
        timeout=30
    )


async def init_database():

    conn = sqlite_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS xp (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            total_messages INTEGER DEFAULT 0,
            daily_xp INTEGER DEFAULT 0,
            weekly_xp INTEGER DEFAULT 0,
            monthly_xp INTEGER DEFAULT 0,
            last_message REAL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS level_roles (
            guild_id INTEGER NOT NULL,
            level INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, level)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guild_languages (
            guild_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'ar'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT,
            created_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS xp_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            created_at REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()

    print("✅ SQLite database initialized.")


# ============================================================
# MONGODB CACHE
# ============================================================

settings_cache = {}

SETTINGS_CACHE_TTL = 300


# ============================================================
# DEFAULT WEBSITE SETTINGS
# ============================================================

DEFAULT_SETTINGS = {

    "language": "ar",

    # --------------------------------------------------------
    # WEBSITE ONLY — WELCOME
    # --------------------------------------------------------

    "welcome": {
        "enabled": False,
        "channelId": None,
        "message": "Welcome {user}!"
    },

    # --------------------------------------------------------
    # WEBSITE ONLY — LEAVE
    # --------------------------------------------------------

    "leave": {
        "enabled": False,
        "channelId": None,
        "message": "{user} has left the server."
    },

    # --------------------------------------------------------
    # WEBSITE ONLY — TICKETS
    # --------------------------------------------------------

    "ticket": {
        "enabled": False,
        "channelId": None,
        "categoryId": None,
        "closedCategoryId": None,
        "supportRoleId": None,
        "message": "Open a ticket using the button below.",
        "description": "Lunex Support",
        "image": None,
        "allowUserClose": True,
        "deleteAfterClose": False
    },

    # --------------------------------------------------------
    # WEBSITE ONLY — EDIT COMMANDS / ALIASES
    # --------------------------------------------------------

    "commandAliases": {},

    # --------------------------------------------------------
    # WEBSITE AUTO REPLIES
    # --------------------------------------------------------

    "autoReplies": [],

    # --------------------------------------------------------
    # BAD WORDS
    # --------------------------------------------------------

    "badwords": [],

    # --------------------------------------------------------
    # PROTECTION
    # --------------------------------------------------------

    "protection": {

        "badwords": True,

        "links": True,

        "antispam": True
    }
}


# ============================================================
# SETTINGS
# ============================================================

def deep_copy_settings():

    import copy

    return copy.deepcopy(
        DEFAULT_SETTINGS
    )


async def get_settings(guild_id):

    guild_id = str(guild_id)

    cached = settings_cache.get(
        guild_id
    )

    if cached:

        timestamp, data = cached

        if (
            time.time() - timestamp
            < SETTINGS_CACHE_TTL
        ):

            return data

    data = await guild_settings.find_one(
        {
            "guildId": guild_id
        }
    )

    if not data:

        data = deep_copy_settings()

        data["guildId"] = guild_id

        await guild_settings.update_one(
            {
                "guildId": guild_id
            },
            {
                "$setOnInsert": data
            },
            upsert=True
        )

    settings_cache[guild_id] = (
        time.time(),
        data
    )

    return data


async def update_settings(
    guild_id,
    update
):

    guild_id = str(guild_id)

    await guild_settings.update_one(
        {
            "guildId": guild_id
        },
        {
            "$set": update
        },
        upsert=True
    )

    settings_cache.pop(
        guild_id,
        None
    )

    return await get_settings(
        guild_id
    )


# ============================================================
# LANGUAGE
# ============================================================

TEXT = {

    "ar": {

        "no_permission":
            "❌ ليس لديك الصلاحية.",

        "language_changed":
            "🇱🇾 تم تغيير لغة البوت إلى العربية.",

        "registered":
            "تم تسجيلك بنجاح.",

        "clear":
            "تم حذف الرسائل بنجاح.",

        "error":
            "❌ حدث خطأ.",

        "empty":
            "لا توجد بيانات كافية حتى الآن."
    },

    "en": {

        "no_permission":
            "❌ You don't have permission.",

        "language_changed":
            "🇬🇧 Bot language changed to English.",

        "registered":
            "You have been registered successfully.",

        "clear":
            "Messages deleted successfully.",

        "error":
            "❌ An error occurred.",

        "empty":
            "Not enough data yet."
    }
}


async def get_language(guild_id):

    conn = sqlite_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT language
        FROM guild_languages
        WHERE guild_id = ?
        """,
        (int(guild_id),)
    )

    row = cursor.fetchone()

    conn.close()

    if row and row[0] in TEXT:
        return row[0]

    return "ar"


async def set_language(
    guild_id,
    language
):

    if language not in TEXT:
        return False

    conn = sqlite_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO guild_languages
        (guild_id, language)
        VALUES (?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET
            language = excluded.language
        """,
        (
            int(guild_id),
            language
        )
    )

    conn.commit()
    conn.close()

    return True


# ============================================================
# XP
# ============================================================

def xp_for_level(level):

    return 100 + (
        level * 50
    )


def calculate_level(total_xp):

    level = 0
    remaining = total_xp

    while True:

        required = xp_for_level(
            level
        )

        if remaining < required:
            break

        remaining -= required
        level += 1

    return level


async def get_user_xp(
    guild_id,
    user_id
):

    conn = sqlite_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            xp,
            level,
            total_messages,
            daily_xp,
            weekly_xp,
            monthly_xp
        FROM xp
        WHERE guild_id = ?
        AND user_id = ?
        """,
        (
            int(guild_id),
            int(user_id)
        )
    )

    row = cursor.fetchone()

    conn.close()

    if not row:

        return {
            "xp": 0,
            "level": 0,
            "total_messages": 0,
            "daily_xp": 0,
            "weekly_xp": 0,
            "monthly_xp": 0
        }

    return {

        "xp": row[0],
        "level": row[1],
        "total_messages": row[2],
        "daily_xp": row[3],
        "weekly_xp": row[4],
        "monthly_xp": row[5]
    }


async def add_xp(
    guild_id,
    user_id,
    amount=5
):

    now = time.time()

    conn = sqlite_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT xp, level, last_message
        FROM xp
        WHERE guild_id = ?
        AND user_id = ?
        """,
        (
            int(guild_id),
            int(user_id)
        )
    )

    row = cursor.fetchone()

    if row:

        old_xp = row[0]
        old_level = row[1]
        last_message = row[2] or 0

    else:

        old_xp = 0
        old_level = 0
        last_message = 0

    if now - last_message < 5:

        conn.close()

        return (
            old_level,
            old_level
        )

    new_xp = old_xp + amount

    new_level = calculate_level(
        new_xp
    )

    cursor.execute(
        """
        INSERT INTO xp (
            guild_id,
            user_id,
            xp,
            level,
            total_messages,
            daily_xp,
            weekly_xp,
            monthly_xp,
            last_message
        )

        VALUES (
            ?, ?, ?, ?, 1, ?, ?, ?, ?
        )

        ON CONFLICT(guild_id, user_id)

        DO UPDATE SET

            xp = excluded.xp,

            level = excluded.level,

            total_messages =
                xp.total_messages + 1,

            daily_xp =
                xp.daily_xp + excluded.daily_xp,

            weekly_xp =
                xp.weekly_xp + excluded.weekly_xp,

            monthly_xp =
                xp.monthly_xp + excluded.monthly_xp,

            last_message =
                excluded.last_message
        """,
        (
            int(guild_id),
            int(user_id),
            new_xp,
            new_level,
            amount,
            amount,
            amount,
            now
        )
    )

    conn.commit()
    conn.close()

    return (
        old_level,
        new_level
    )


# ============================================================
# XP ADMIN
# ============================================================

async def modify_xp(
    guild_id,
    user_id,
    amount,
    moderator_id
):

    conn = sqlite_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT xp
        FROM xp
        WHERE guild_id = ?
        AND user_id = ?
        """,
        (
            int(guild_id),
            int(user_id)
        )
    )

    row = cursor.fetchone()

    current = row[0] if row else 0

    new_xp = max(
        0,
        current + amount
    )

    new_level = calculate_level(
        new_xp
    )

    cursor.execute(
        """
        INSERT INTO xp (
            guild_id,
            user_id,
            xp,
            level,
            total_messages,
            daily_xp,
            weekly_xp,
            monthly_xp,
            last_message
        )

        VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0)

        ON CONFLICT(guild_id, user_id)

        DO UPDATE SET
            xp = excluded.xp,
            level = excluded.level
        """,
        (
            int(guild_id),
            int(user_id),
            new_xp,
            new_level
        )
    )

    cursor.execute(
        """
        INSERT INTO xp_history (
            guild_id,
            user_id,
            amount,
            moderator_id,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            int(guild_id),
            int(user_id),
            int(amount),
            int(moderator_id),
            time.time()
        )
    )

    conn.commit()
    conn.close()

    return new_xp, new_level


async def set_user_level(
    guild_id,
    user_id,
    level
):

    level = max(
        0,
        int(level)
    )

    total_xp = 0

    for current in range(level):

        total_xp += xp_for_level(
            current
        )

    conn = sqlite_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO xp (
            guild_id,
            user_id,
            xp,
            level,
            total_messages,
            daily_xp,
            weekly_xp,
            monthly_xp,
            last_message
        )

        VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0)

        ON CONFLICT(guild_id, user_id)

        DO UPDATE SET
            xp = excluded.xp,
            level = excluded.level
        """,
        (
            int(guild_id),
            int(user_id),
            total_xp,
            level
        )
    )

    conn.commit()
    conn.close()

    return total_xp


# ============================================================
# LEVEL ROLES
# ============================================================

async def set_level_role(
    guild_id,
    level,
    role_id
):

    conn = sqlite_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO level_roles
        (
            guild_id,
            level,
            role_id
        )
        VALUES (?, ?, ?)

        ON CONFLICT(guild_id, level)

        DO UPDATE SET
            role_id = excluded.role_id
        """,
        (
            int(guild_id),
            int(level),
            int(role_id)
        )
    )

    conn.commit()
    conn.close()


async def get_level_role(
    guild_id,
    level
):

    conn = sqlite_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role_id
        FROM level_roles
        WHERE guild_id = ?
        AND level = ?
        """,
        (
            int(guild_id),
            int(level)
        )
    )

    row = cursor.fetchone()

    conn.close()

    return int(row[0]) if row else None


async def give_level_role(
    guild,
    member,
    level
):

    role_id = await get_level_role(
        guild.id,
        level
    )

    if not role_id:
        return

    role = guild.get_role(
        role_id
    )

    if not role:
        return

    bot_member = guild.me

    if not bot_member:
        return

    if role >= bot_member.top_role:
        return

    if role in member.roles:
        return

    try:

        await member.add_roles(
            role,
            reason=f"Lunex Level {level} reward"
        )

    except (
        discord.Forbidden,
        discord.HTTPException
    ):

        pass


# ============================================================
# WARNINGS
# ============================================================

async def add_warning(
    guild_id,
    user_id,
    moderator_id,
    reason
):

    conn = sqlite_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO warnings (
            guild_id,
            user_id,
            moderator_id,
            reason,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            int(guild_id),
            int(user_id),
            int(moderator_id),
            reason,
            time.time()
        )
    )

    conn.commit()
    conn.close()


async def get_warnings(
    guild_id,
    user_id
):

    conn = sqlite_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            moderator_id,
            reason,
            created_at
        FROM warnings
        WHERE guild_id = ?
        AND user_id = ?
        ORDER BY created_at DESC
        """,
        (
            int(guild_id),
            int(user_id)
        )
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


async def remove_warning(
    guild_id,
    user_id
):

    conn = sqlite_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM warnings
        WHERE rowid = (
            SELECT rowid
            FROM warnings
            WHERE guild_id = ?
            AND user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        )
        """,
        (
            int(guild_id),
            int(user_id)
        )
    )

    deleted = cursor.rowcount

    conn.commit()
    conn.close()

    return deleted


# ============================================================
# STAFF CHECK
# ============================================================

def staff_only():

    async def predicate(
        interaction: discord.Interaction
    ):

        if not interaction.guild:

            return False

        return (
            interaction.user.guild_permissions.manage_guild
            or interaction.user.guild_permissions.administrator
        )

    return app_commands.check(
        predicate
    )


# ============================================================
# HELP SYSTEM
# ONLY TWO CATEGORIES
# ============================================================

MEMBER_COMMANDS = """

**General**
`/commands`
`/help`
`/server`
`/me`
`/profile`
`/register`

**XP**
`/xp`
`/level`
`/top`
`/top_day`
`/top_week`
"""


STAFF_COMMANDS = """

**Moderation**
`/clear`
`/kick`
`/ban`
`/unban`
`/timeout`
`/untimeout`
`/warn`
`/warnings`
`/unwarn`
`/lock`
`/unlock`
`/slowmode`

**Protection**
`/protection`
`/protection_remove`
`/antispam`
`/antilink`
`/badwords`
`/badwords_add`
`/badwords_remove`

**XP Management**
`/xp_add`
`/xp_remove`
`/xp_reset`
`/level_set`
`/level_reset`
`/level_roll`

**Server Management**
`/language`
`/announce`
`/nickname`
`/role_add`
`/role_remove`
"""


def member_embed():

    return discord.Embed(
        title="👥 Member commands",
        description=MEMBER_COMMANDS,
        color=discord.Color.blurple()
    )


def staff_embed():

    return discord.Embed(
        title="👑 Staff commands",
        description=STAFF_COMMANDS,
        color=discord.Color.gold()
    )


class HelpSelect(
    discord.ui.Select
):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="Member commands",
                value="member",
                emoji="👥"
            ),

            discord.SelectOption(
                label="Staff commands",
                value="staff",
                emoji="👑"
            )
        ]

        super().__init__(
            placeholder="اختر قسم الأوامر...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if self.values[0] == "member":

            embed = member_embed()

        else:

            embed = staff_embed()

        await interaction.response.edit_message(
            embed=embed,
            view=HelpView()
        )


class HelpView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=180
        )

        self.add_item(
            HelpSelect()
        )


# ============================================================
# /COMMANDS
# ============================================================

@bot.tree.command(
    name="commands",
    description="عرض أوامر Lunex"
)
async def commands_command(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🌙 LUNEX COMMANDS",
        description=(
            "مرحبًا بك في مركز أوامر **Lunex**.\n\n"
            "اختر إحدى الفئتين:"
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="👥 Member commands",
        value="أوامر الأعضاء والمعلومات العامة.",
        inline=False
    )

    embed.add_field(
        name="👑 Staff commands",
        value="أوامر الإدارة والإشراف والحماية.",
        inline=False
    )

    embed.set_footer(
        text="Lunex • Command Center"
    )

    await interaction.response.send_message(
        embed=embed,
        view=HelpView(),
        ephemeral=True
    )


# ============================================================
# !HELP
# ============================================================

@bot.command(
    name="help"
)
async def help_command(
    ctx
):

    embed = discord.Embed(
        title="🌙 LUNEX HELP",
        description=(
            "مرحبًا بك في مركز أوامر **Lunex**.\n\n"
            "اختر إحدى الفئتين:"
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="👥 Member commands",
        value="أوامر الأعضاء والمعلومات العامة.",
        inline=False
    )

    embed.add_field(
        name="👑 Staff commands",
        value="أوامر الإدارة والإشراف والحماية.",
        inline=False
    )

    await ctx.send(
        embed=embed,
        view=HelpView()
    )


# ============================================================
# MEMBER — /SERVER
# ============================================================

@bot.tree.command(
    name="server",
    description="عرض معلومات السيرفر"
)
async def server_command(
    interaction: discord.Interaction
):

    guild = interaction.guild

    embed = discord.Embed(
        title=f"🏠 {guild.name}",
        color=discord.Color.blurple()
    )

    if guild.icon:

        embed.set_thumbnail(
            url=guild.icon.url
        )

    embed.add_field(
        name="👥 Members",
        value=str(guild.member_count),
        inline=True
    )

    embed.add_field(
        name="💬 Channels",
        value=str(len(guild.channels)),
        inline=True
    )

    embed.add_field(
        name="🎭 Roles",
        value=str(len(guild.roles)),
        inline=True
    )

    embed.add_field(
        name="🆔 Server ID",
        value=str(guild.id),
        inline=False
    )

    embed.add_field(
        name="👑 Owner",
        value=guild.owner.mention
        if guild.owner else "Unknown",
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# MEMBER — /ME
# ============================================================

@bot.tree.command(
    name="me",
    description="عرض معلومات حسابك"
)
async def me_command(
    interaction: discord.Interaction
):

    data = await get_user_xp(
        interaction.guild.id,
        interaction.user.id
    )

    embed = discord.Embed(
        title=f"👤 {interaction.user.display_name}",
        color=discord.Color.blurple()
    )

    embed.set_thumbnail(
        url=interaction.user.display_avatar.url
    )

    embed.add_field(
        name="⭐ Level",
        value=str(data["level"])
    )

    embed.add_field(
        name="✨ XP",
        value=str(data["xp"])
    )

    embed.add_field(
        name="💬 Messages",
        value=str(data["total_messages"])
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# MEMBER — /PROFILE
# ============================================================

@bot.tree.command(
    name="profile",
    description="عرض الملف الشخصي"
)
async def profile_command(
    interaction: discord.Interaction
):

    data = await get_user_xp(
        interaction.guild.id,
        interaction.user.id
    )

    embed = discord.Embed(
        title="👤 PROFILE",
        description=(
            f"**User:** {interaction.user.mention}\n\n"
            f"⭐ Level: **{data['level']}**\n"
            f"✨ XP: **{data['xp']}**\n"
            f"💬 Messages: **{data['total_messages']}**"
        ),
        color=discord.Color.blurple()
    )

    embed.set_thumbnail(
        url=interaction.user.display_avatar.url
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# MEMBER — /XP
# ============================================================

@bot.tree.command(
    name="xp",
    description="عرض نقاط الخبرة"
)
async def xp_command(
    interaction: discord.Interaction
):

    data = await get_user_xp(
        interaction.guild.id,
        interaction.user.id
    )

    await interaction.response.send_message(
        f"✨ XP: **{data['xp']}**\n"
        f"⭐ Level: **{data['level']}**\n"
        f"💬 Messages: **{data['total_messages']}**"
    )


# ============================================================
# MEMBER — /LEVEL
# ============================================================

@bot.tree.command(
    name="level",
    description="عرض مستواك"
)
async def level_command(
    interaction: discord.Interaction
):

    data = await get_user_xp(
        interaction.guild.id,
        interaction.user.id
    )

    await interaction.response.send_message(
        f"⭐ Level: **{data['level']}**\n"
        f"✨ XP: **{data['xp']}**"
    )


# ============================================================
# MEMBER — /REGISTER
# ============================================================

@bot.tree.command(
    name="register",
    description="تسجيل حسابك في Lunex"
)
async def register_command(
    interaction: discord.Interaction
):

    await get_user_xp(
        interaction.guild.id,
        interaction.user.id
    )

    await interaction.response.send_message(
        "✅ تم تسجيلك بنجاح.",
        ephemeral=True
    )


# ============================================================
# LEADERBOARD
# ============================================================

async def get_leaderboard(
    guild_id,
    period
):

    allowed_columns = {

        "day": "daily_xp",

        "week": "weekly_xp",

        "month": "monthly_xp",

        "all": "xp"
    }

    column = allowed_columns.get(
        period,
        "xp"
    )

    conn = sqlite_connection()
    cursor = conn.cursor()

    cursor.execute(
        f"""
        SELECT user_id, {column}
        FROM xp
        WHERE guild_id = ?
        ORDER BY {column} DESC
        LIMIT 10
        """,
        (int(guild_id),)
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


async def send_leaderboard(
    interaction,
    period
):

    rows = await get_leaderboard(
        interaction.guild.id,
        period
    )

    if not rows:

        await interaction.response.send_message(
            "🏆 لا توجد بيانات حتى الآن."
        )

        return

    titles = {

        "day": "🏆 TOP DAY",

        "week": "🏆 TOP WEEK",

        "month": "🏆 TOP MONTH",

        "all": "🏆 TOP"
    }

    medals = [
        "🥇",
        "🥈",
        "🥉"
    ]

    description = ""

    for index, (
        user_id,
        value
    ) in enumerate(rows):

        member = interaction.guild.get_member(
            int(user_id)
        )

        name = (
            member.display_name
            if member
            else f"User {user_id}"
        )

        position = (
            medals[index]
            if index < 3
            else f"`#{index + 1}`"
        )

        description += (
            f"{position} "
            f"**{name}** — "
            f"`{value} XP`\n"
        )

    embed = discord.Embed(
        title=titles[period],
        description=description,
        color=discord.Color.gold()
    )

    embed.set_footer(
        text="Lunex Leaderboards"
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# MEMBER — LEADERBOARDS
# ============================================================

@bot.tree.command(
    name="top",
    description="متصدرين الشهر"
)
async def top_command(
    interaction: discord.Interaction
):

    await send_leaderboard(
        interaction,
        "month"
    )


@bot.tree.command(
    name="top_day",
    description="متصدرين اليوم"
)
async def top_day_command(
    interaction: discord.Interaction
):

    await send_leaderboard(
        interaction,
        "day"
    )


@bot.tree.command(
    name="top_week",
    description="متصدرين الأسبوع"
)
async def top_week_command(
    interaction: discord.Interaction
):

    await send_leaderboard(
        interaction,
        "week"
    )


# ============================================================
# STAFF — /LANGUAGE
# ============================================================

@bot.tree.command(
    name="language",
    description="تغيير لغة البوت"
)
@app_commands.describe(
    language="اللغة"
)
@app_commands.choices(
    language=[
        app_commands.Choice(
            name="العربية 🇱🇾",
            value="ar"
        ),
        app_commands.Choice(
            name="English 🇬🇧",
            value="en"
        )
    ]
)
@app_commands.default_permissions(
    manage_guild=True
)
async def language_command(
    interaction: discord.Interaction,
    language: app_commands.Choice[str]
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ تحتاج Manage Server.",
            ephemeral=True
        )

        return

    await set_language(
        interaction.guild.id,
        language.value
    )

    await interaction.response.send_message(
        TEXT[language.value]["language_changed"]
    )


# ============================================================
# STAFF — /CLEAR
# ============================================================

@bot.tree.command(
    name="clear",
    description="حذف الرسائل"
)
@app_commands.describe(
    amount="من 1 إلى 100"
)
@app_commands.default_permissions(
    manage_messages=True
)
async def clear_command(
    interaction: discord.Interaction,
    amount: app_commands.Range[int, 1, 100]
):

    if not interaction.user.guild_permissions.manage_messages:

        await interaction.response.send_message(
            "❌ تحتاج Manage Messages.",
            ephemeral=True
        )

        return

    await interaction.response.defer(
        ephemeral=True
    )

    try:

        deleted = await interaction.channel.purge(
            limit=amount
        )

        await interaction.followup.send(
            f"🧹 تم حذف **{len(deleted)}** رسالة.",
            ephemeral=True
        )

    except discord.Forbidden:

        await interaction.followup.send(
            "❌ البوت لا يملك صلاحية حذف الرسائل.",
            ephemeral=True
        )

    except discord.HTTPException:

        await interaction.followup.send(
            "❌ حدث خطأ أثناء الحذف.",
            ephemeral=True
        )


# ============================================================
# STAFF — /KICK
# ============================================================

@bot.tree.command(
    name="kick",
    description="طرد عضو"
)
@app_commands.describe(
    member="العضو",
    reason="السبب"
)
@app_commands.default_permissions(
    kick_members=True
)
async def kick_command(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    if not interaction.user.guild_permissions.kick_members:

        await interaction.response.send_message(
            "❌ تحتاج Kick Members.",
            ephemeral=True
        )

        return

    if member == interaction.user:

        await interaction.response.send_message(
            "❌ لا يمكنك طرد نفسك.",
            ephemeral=True
        )

        return

    if member.top_role >= interaction.user.top_role:

        await interaction.response.send_message(
            "❌ لا يمكنك طرد عضو أعلى منك أو بنفس رتبتك.",
            ephemeral=True
        )

        return

    try:

        await member.kick(
            reason=reason
        )

        await interaction.response.send_message(
            f"👢 تم طرد {member.mention}.\n"
            f"**السبب:** {reason}"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ البوت لا يستطيع طرد هذا العضو.",
            ephemeral=True
        )


# ============================================================
# STAFF — /BAN
# ============================================================

@bot.tree.command(
    name="ban",
    description="حظر عضو"
)
@app_commands.describe(
    member="العضو",
    reason="السبب"
)
@app_commands.default_permissions(
    ban_members=True
)
async def ban_command(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    if not interaction.user.guild_permissions.ban_members:

        await interaction.response.send_message(
            "❌ تحتاج Ban Members.",
            ephemeral=True
        )

        return

    if member == interaction.user:

        await interaction.response.send_message(
            "❌ لا يمكنك حظر نفسك.",
            ephemeral=True
        )

        return

    if member.top_role >= interaction.user.top_role:

        await interaction.response.send_message(
            "❌ لا يمكنك حظر عضو أعلى منك أو بنفس رتبتك.",
            ephemeral=True
        )

        return

    try:

        await member.ban(
            reason=reason
        )

        await interaction.response.send_message(
            f"🔨 تم حظر {member.mention}.\n"
            f"**السبب:** {reason}"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ البوت لا يستطيع حظر هذا العضو.",
            ephemeral=True
        )


# ============================================================
# STAFF — /UNBAN
# ============================================================

@bot.tree.command(
    name="unban",
    description="فك حظر مستخدم"
)
@app_commands.describe(
    user_id="ID المستخدم"
)
@app_commands.default_permissions(
    ban_members=True
)
async def unban_command(
    interaction: discord.Interaction,
    user_id: str
):

    if not interaction.user.guild_permissions.ban_members:

        await interaction.response.send_message(
            "❌ تحتاج Ban Members.",
            ephemeral=True
        )

        return

    try:

        user = await bot.fetch_user(
            int(user_id)
        )

        await interaction.guild.unban(
            user
        )

        await interaction.response.send_message(
            f"✅ تم فك حظر {user.mention}."
        )

    except ValueError:

        await interaction.response.send_message(
            "❌ ID غير صحيح.",
            ephemeral=True
        )

    except discord.NotFound:

        await interaction.response.send_message(
            "❌ المستخدم غير محظور.",
            ephemeral=True
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ لا أملك صلاحية فك الحظر.",
            ephemeral=True
        )


# ============================================================
# STAFF — /TIMEOUT
# ============================================================

@bot.tree.command(
    name="timeout",
    description="إعطاء Timeout"
)
@app_commands.describe(
    member="العضو",
    minutes="المدة بالدقائق",
    reason="السبب"
)
@app_commands.default_permissions(
    moderate_members=True
)
async def timeout_command(
    interaction: discord.Interaction,
    member: discord.Member,
    minutes: app_commands.Range[int, 1, 40320],
    reason: str = "No reason provided"
):

    if not interaction.user.guild_permissions.moderate_members:

        await interaction.response.send_message(
            "❌ تحتاج Moderate Members.",
            ephemeral=True
        )

        return

    if member.top_role >= interaction.user.top_role:

        await interaction.response.send_message(
            "❌ لا يمكنك Timeout لهذا العضو.",
            ephemeral=True
        )

        return

    try:

        await member.timeout(
            timedelta(minutes=minutes),
            reason=reason
        )

        await interaction.response.send_message(
            f"🔇 تم إعطاء Timeout لـ {member.mention} "
            f"لمدة **{minutes} دقيقة**."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ لا أستطيع إعطاء Timeout لهذا العضو.",
            ephemeral=True
        )


# ============================================================
# STAFF — /UNTIMEOUT
# ============================================================

@bot.tree.command(
    name="untimeout",
    description="إزالة Timeout"
)
@app_commands.describe(
    member="العضو"
)
@app_commands.default_permissions(
    moderate_members=True
)
async def untimeout_command(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not interaction.user.guild_permissions.moderate_members:

        await interaction.response.send_message(
            "❌ تحتاج Moderate Members.",
            ephemeral=True
        )

        return

    try:

        await member.timeout(
            None,
            reason=f"Timeout removed by {interaction.user}"
        )

        await interaction.response.send_message(
            f"🔊 تم إزالة Timeout عن {member.mention}."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ لا أستطيع تعديل Timeout.",
            ephemeral=True
        )


# ============================================================
# STAFF — /WARN
# ============================================================

@bot.tree.command(
    name="warn",
    description="تحذير عضو"
)
@app_commands.describe(
    member="العضو",
    reason="السبب"
)
@app_commands.default_permissions(
    moderate_members=True
)
async def warn_command(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    if not interaction.user.guild_permissions.moderate_members:

        await interaction.response.send_message(
            "❌ تحتاج Moderate Members.",
            ephemeral=True
        )

        return

    await add_warning(
        interaction.guild.id,
        member.id,
        interaction.user.id,
        reason
    )

    warnings = await get_warnings(
        interaction.guild.id,
        member.id
    )

    await interaction.response.send_message(
        f"⚠️ تم تحذير {member.mention}.\n"
        f"**السبب:** {reason}\n"
        f"**عدد التحذيرات:** {len(warnings)}"
    )


# ============================================================
# STAFF — /WARNINGS
# ============================================================

@bot.tree.command(
    name="warnings",
    description="عرض تحذيرات عضو"
)
@app_commands.describe(
    member="العضو"
)
@app_commands.default_permissions(
    moderate_members=True
)
async def warnings_command(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not interaction.user.guild_permissions.moderate_members:

        await interaction.response.send_message(
            "❌ تحتاج Moderate Members.",
            ephemeral=True
        )

        return

    rows = await get_warnings(
        interaction.guild.id,
        member.id
    )

    if not rows:

        await interaction.response.send_message(
            f"✅ {member.mention} ليس لديه تحذيرات."
        )

        return

    description = ""

    for index, (
        moderator_id,
        reason,
        created_at
    ) in enumerate(rows[:10], 1):

        description += (
            f"**#{index}** — {reason}\n"
            f"Moderator: <@{moderator_id}>\n\n"
        )

    embed = discord.Embed(
        title=f"⚠️ Warnings — {member.display_name}",
        description=description,
        color=discord.Color.orange()
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# STAFF — /UNWARN
# ============================================================

@bot.tree.command(
    name="unwarn",
    description="إزالة آخر تحذير"
)
@app_commands.describe(
    member="العضو"
)
@app_commands.default_permissions(
    moderate_members=True
)
async def unwarn_command(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not interaction.user.guild_permissions.moderate_members:

        await interaction.response.send_message(
            "❌ تحتاج Moderate Members.",
            ephemeral=True
        )

        return

    deleted = await remove_warning(
        interaction.guild.id,
        member.id
    )

    if deleted:

        await interaction.response.send_message(
            f"✅ تم إزالة آخر تحذير عن {member.mention}."
        )

    else:

        await interaction.response.send_message(
            "❌ لا توجد تحذيرات.",
            ephemeral=True
        )


# ============================================================
# STAFF — /LOCK
# ============================================================

@bot.tree.command(
    name="lock",
    description="قفل القناة"
)
@app_commands.default_permissions(
    manage_channels=True
)
async def lock_command(
    interaction: discord.Interaction
):

    if not interaction.user.guild_permissions.manage_channels:

        await interaction.response.send_message(
            "❌ تحتاج Manage Channels.",
            ephemeral=True
        )

        return

    overwrite = interaction.channel.overwrites_for(
        interaction.guild.default_role
    )

    overwrite.send_messages = False

    try:

        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite,
            reason=f"Locked by {interaction.user}"
        )

        await interaction.response.send_message(
            "🔒 تم قفل القناة."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ لا أملك صلاحية تعديل القناة.",
            ephemeral=True
        )


# ============================================================
# STAFF — /UNLOCK
# ============================================================

@bot.tree.command(
    name="unlock",
    description="فتح القناة"
)
@app_commands.default_permissions(
    manage_channels=True
)
async def unlock_command(
    interaction: discord.Interaction
):

    if not interaction.user.guild_permissions.manage_channels:

        await interaction.response.send_message(
            "❌ تحتاج Manage Channels.",
            ephemeral=True
        )

        return

    overwrite = interaction.channel.overwrites_for(
        interaction.guild.default_role
    )

    overwrite.send_messages = None

    try:

        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite,
            reason=f"Unlocked by {interaction.user}"
        )

        await interaction.response.send_message(
            "🔓 تم فتح القناة."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ لا أملك صلاحية تعديل القناة.",
            ephemeral=True
        )


# ============================================================
# STAFF — /SLOWMODE
# ============================================================

@bot.tree.command(
    name="slowmode",
    description="تعيين Slowmode"
)
@app_commands.describe(
    seconds="الثواني من 0 إلى 21600"
)
@app_commands.default_permissions(
    manage_channels=True
)
async def slowmode_command(
    interaction: discord.Interaction,
    seconds: app_commands.Range[int, 0, 21600]
):

    if not interaction.user.guild_permissions.manage_channels:

        await interaction.response.send_message(
            "❌ تحتاج Manage Channels.",
            ephemeral=True
        )

        return

    try:

        await interaction.channel.edit(
            slowmode_delay=seconds
        )

        await interaction.response.send_message(
            f"🐌 تم ضبط Slowmode على **{seconds} ثانية**."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ لا أستطيع تعديل القناة.",
            ephemeral=True
        )


# ============================================================
# STAFF — /PROTECTION
# ============================================================

@bot.tree.command(
    name="protection",
    description="عرض وتفعيل حماية السيرفر"
)
@app_commands.describe(
    feature="نوع الحماية",
    enabled="تفعيل أو تعطيل"
)
@app_commands.choices(
    feature=[
        app_commands.Choice(
            name="All Protection",
            value="all"
        ),
        app_commands.Choice(
            name="Anti Spam",
            value="antispam"
        ),
        app_commands.Choice(
            name="Anti Link",
            value="links"
        ),
        app_commands.Choice(
            name="Bad Words",
            value="badwords"
        )
    ]
)
@app_commands.default_permissions(
    manage_guild=True
)
async def protection_command(
    interaction: discord.Interaction,
    feature: app_commands.Choice[str],
    enabled: bool
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ تحتاج Manage Server.",
            ephemeral=True
        )

        return

    key = feature.value

    if key == "all":

        update = {
            "protection.antispam": enabled,
            "protection.links": enabled,
            "protection.badwords": enabled
        }

    else:

        update = {
            f"protection.{key}": enabled
        }

    await update_settings(
        interaction.guild.id,
        update
    )

    state = "🟢 ON" if enabled else "🔴 OFF"

    await interaction.response.send_message(
        f"🛡️ **{feature.name}** → {state}"
    )


# ============================================================
# STAFF — /PROTECTION_REMOVE
# ============================================================

@bot.tree.command(
    name="protection_remove",
    description="تعطيل حماية معينة"
)
@app_commands.describe(
    feature="نوع الحماية"
)
@app_commands.choices(
    feature=[
        app_commands.Choice(
            name="All Protection",
            value="all"
        ),
        app_commands.Choice(
            name="Anti Spam",
            value="antispam"
        ),
        app_commands.Choice(
            name="Anti Link",
            value="links"
        ),
        app_commands.Choice(
            name="Bad Words",
            value="badwords"
        )
    ]
)
@app_commands.default_permissions(
    manage_guild=True
)
async def protection_remove_command(
    interaction: discord.Interaction,
    feature: app_commands.Choice[str]
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ تحتاج Manage Server.",
            ephemeral=True
        )

        return

    if feature.value == "all":

        update = {
            "protection.antispam": False,
            "protection.links": False,
            "protection.badwords": False
        }

    else:

        update = {
            f"protection.{feature.value}": False
        }

    await update_settings(
        interaction.guild.id,
        update
    )

    await interaction.response.send_message(
        f"🛡️ تم تعطيل **{feature.name}**."
    )


# ============================================================
# STAFF — /ANTISPAM
# ============================================================

@bot.tree.command(
    name="antispam",
    description="تفعيل أو تعطيل Anti Spam"
)
@app_commands.describe(
    enabled="الحالة"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def antispam_command(
    interaction: discord.Interaction,
    enabled: bool
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ تحتاج Manage Server.",
            ephemeral=True
        )

        return

    await update_settings(
        interaction.guild.id,
        {
            "protection.antispam": enabled
        }
    )

    await interaction.response.send_message(
        "🛡️ Anti-Spam: "
        + ("🟢 ON" if enabled else "🔴 OFF")
    )


# ============================================================
# STAFF — /ANTILINK
# ============================================================

@bot.tree.command(
    name="antilink",
    description="تفعيل أو تعطيل منع الروابط"
)
@app_commands.describe(
    enabled="الحالة"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def antilink_command(
    interaction: discord.Interaction,
    enabled: bool
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ تحتاج Manage Server.",
            ephemeral=True
        )

        return

    await update_settings(
        interaction.guild.id,
        {
            "protection.links": enabled
        }
    )

    await interaction.response.send_message(
        "🔗 Anti-Link: "
        + ("🟢 ON" if enabled else "🔴 OFF")
    )


# ============================================================
# STAFF — /BADWORDS
# ============================================================

@bot.tree.command(
    name="badwords",
    description="تفعيل أو تعطيل فلتر الكلمات"
)
@app_commands.describe(
    enabled="الحالة"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def badwords_command(
    interaction: discord.Interaction,
    enabled: bool
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ تحتاج Manage Server.",
            ephemeral=True
        )

        return

    await update_settings(
        interaction.guild.id,
        {
            "protection.badwords": enabled
        }
    )

    await interaction.response.send_message(
        "🤬 Bad Words: "
        + ("🟢 ON" if enabled else "🔴 OFF")
    )


# ============================================================
# STAFF — /BADWORDS_ADD
# ============================================================

@bot.tree.command(
    name="badwords_add",
    description="إضافة كلمة للفلتر"
)
@app_commands.describe(
    word="الكلمة"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def badwords_add_command(
    interaction: discord.Interaction,
    word: str
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ تحتاج Manage Server.",
            ephemeral=True
        )

        return

    word = word.strip().lower()

    if not word:

        await interaction.response.send_message(
            "❌ الكلمة فارغة.",
            ephemeral=True
        )

        return

    settings = await get_settings(
        interaction.guild.id
    )

    words = settings.get(
        "badwords",
        []
    )

    if not isinstance(words, list):

        words = []

    if word in words:

        await interaction.response.send_message(
            "⚠️ الكلمة موجودة مسبقًا.",
            ephemeral=True
        )

        return

    words.append(word)

    await update_settings(
        interaction.guild.id,
        {
            "badwords": words
        }
    )

    await interaction.response.send_message(
        f"✅ تمت إضافة `{word}` إلى قائمة الكلمات."
    )


# ============================================================
# STAFF — /BADWORDS_REMOVE
# ============================================================

@bot.tree.command(
    name="badwords_remove",
    description="حذف كلمة من الفلتر"
)
@app_commands.describe(
    word="الكلمة"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def badwords_remove_command(
    interaction: discord.Interaction,
    word: str
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ تحتاج Manage Server.",
            ephemeral=True
        )

        return

    word = word.strip().lower()

    settings = await get_settings(
        interaction.guild.id
    )

    words = settings.get(
        "badwords",
        []
    )

    if word not in words:

        await interaction.response.send_message(
            "❌ الكلمة غير موجودة.",
            ephemeral=True
        )

        return

    words.remove(word)

    await update_settings(
        interaction.guild.id,
        {
            "badwords": words
        }
    )

    await interaction.response.send_message(
        f"✅ تم حذف `{word}`."
    )


# ============================================================
# STAFF — /XP_ADD
# ============================================================

@bot.tree.command(
    name="xp_add",
    description="إضافة XP لعضو"
)
@app_commands.describe(
    member="العضو",
    amount="الكمية"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def xp_add_command(
    interaction: discord.Interaction,
    member: discord.Member,
    amount: app_commands.Range[int, 1, 1000000]
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ تحتاج Manage Server.",
            ephemeral=True
        )

        return

    new_xp, level = await modify_xp(
        interaction.guild.id,
        member.id,
        amount,
        interaction.user.id
    )

    await interaction.response.send_message(
        f"✨ تمت إضافة **{amount} XP** إلى "
        f"{member.mention}.\n"
        f"XP: **{new_xp}**\n"
        f"Level: **{level}**"
    )


# ============================================================
# STAFF — /XP_REMOVE
# ============================================================

@bot.tree.command(
    name="xp_remove",
    description="إزالة XP من عضو"
)
@app_commands.describe(
    member="العضو",
    amount="الكمية"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def xp_remove_command(
    interaction: discord.Interaction,
    member: discord.Member,
    amount: app_commands.Range[int, 1, 1000000]
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ تحتاج Manage Server.",
            ephemeral=True
        )

        return

    new_xp, level = await modify_xp(
        interaction.guild.id,
        member.id,
        -amount,
        interaction.user.id
    )

    await interaction.response.send_message(
        f"➖ تمت إزالة **{amount} XP** من "
        f"{member.mention}.\n"
        f"XP: **{new_xp}**\n"
        f"Level: **{level}**"
    )


# ============================================================
# STAFF — /XP_RESET
# ============================================================

@bot.tree.command(
    name="xp_reset",
    description="تصفير XP عضو"
)
@app_commands.describe(
    member="العضو"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def xp_reset_command(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ تحتاج Manage Server.",
            ephemeral=True
        )

        return

    conn = sqlite_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM xp
        WHERE guild_id = ?
        AND user_id = ?
        """,
        (
            interaction.guild.id,
            member.id
        )
    )

    conn.commit()
    conn.close()

    await interaction.response.send_message(
        f"🧹 تم تصفير XP لـ {member.mention}."
    )


# ============================================================
# STAFF — /LEVEL_SET
# ============================================================

@bot.tree.command(
    name="level_set",
    description="تعيين مستوى عضو"
)
@app_commands.describe(
    member="العضو",
    level="المستوى"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def level_set_command(
    interaction: discord.Interaction,
    member: discord.Member,
    level: app_commands.Range[int, 0, 1000]
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ تحتاج Manage Server.",
            ephemeral=True
        )

        return

    xp = await set_user_level(
        interaction.guild.id,
        member.id,
        level
    )

    await give_level_role(
        interaction.guild,
        member,
        level
    )

    await interaction.response.send_message(
        f"⭐ تم تعيين مستوى {member.mention} إلى "
        f"**{level}**.\n"
        f"XP: **{xp}**"
    )


# ============================================================
# STAFF — /LEVEL_RESET
# ============================================================

@bot.tree.command(
    name="level_reset",
    description="تصفير مستوى عضو"
)
@app_commands.describe(
    member="العضو"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def level_reset_command(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ تحتاج Manage Server.",
            ephemeral=True
        )

        return

    await set_user_level(
        interaction.guild.id,
        member.id,
        0
    )

    await interaction.response.send_message(
        f"🔄 تم تصفير مستوى {member.mention}."
    )


# ============================================================
# STAFF — /LEVEL_ROLL
# ============================================================

@bot.tree.command(
    name="level_roll",
    description="ربط مستوى برتبة"
)
@app_commands.describe(
    level="المستوى",
    role="الرتبة"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def level_roll_command(
    interaction: discord.Interaction,
    level: app_commands.Range[int, 1, 1000],
    role: discord.Role
):

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ تحتاج Manage Server.",
            ephemeral=True
        )

        return

    if role.is_default():

        await interaction.response.send_message(
            "❌ لا يمكن استخدام @everyone.",
            ephemeral=True
        )

        return

    bot_member = interaction.guild.me

    if bot_member and role >= bot_member.top_role:

        await interaction.response.send_message(
            "❌ رتبة البوت يجب أن تكون أعلى من الرتبة.",
            ephemeral=True
        )

        return

    await set_level_role(
        interaction.guild.id,
        level,
        role.id
    )

    await interaction.response.send_message(
        f"🎉 تم ربط Level **{level}** "
        f"بالرتبة {role.mention}."
    )


# ============================================================
# STAFF — /ANNOUNCE
# ============================================================

@bot.tree.command(
    name="announce",
    description="إرسال إعلان"
)
@app_commands.describe(
    title="العنوان",
    message="نص الإعلان"
)
@app_commands.default_permissions(
    manage_messages=True
)
async def announce_command(
    interaction: discord.Interaction,
    title: str,
    message: str
):

    if not interaction.user.guild_permissions.manage_messages:

        await interaction.response.send_message(
            "❌ تحتاج Manage Messages.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title=f"📢 {title}",
        description=message,
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text=f"By {interaction.user.display_name}"
    )

    await interaction.channel.send(
        embed=embed
    )

    await interaction.response.send_message(
        "✅ تم إرسال الإعلان.",
        ephemeral=True
    )


# ============================================================
# STAFF — /NICKNAME
# ============================================================

@bot.tree.command(
    name="nickname",
    description="تغيير لقب عضو"
)
@app_commands.describe(
    member="العضو",
    nickname="اللقب الجديد"
)
@app_commands.default_permissions(
    manage_nicknames=True
)
async def nickname_command(
    interaction: discord.Interaction,
    member: discord.Member,
    nickname: str
):

    if not interaction.user.guild_permissions.manage_nicknames:

        await interaction.response.send_message(
            "❌ تحتاج Manage Nicknames.",
            ephemeral=True
        )

        return

    if member.top_role >= interaction.user.top_role:

        await interaction.response.send_message(
            "❌ لا يمكنك تغيير لقب هذا العضو.",
            ephemeral=True
        )

        return

    try:

        await member.edit(
            nick=nickname,
            reason=f"Nickname changed by {interaction.user}"
        )

        await interaction.response.send_message(
            f"✅ تم تغيير لقب {member.mention} إلى "
            f"**{nickname}**."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ لا أستطيع تغيير اللقب.",
            ephemeral=True
        )


# ============================================================
# STAFF — /ROLE_ADD
# ============================================================

@bot.tree.command(
    name="role_add",
    description="إعطاء رتبة لعضو"
)
@app_commands.describe(
    member="العضو",
    role="الرتبة"
)
@app_commands.default_permissions(
    manage_roles=True
)
async def role_add_command(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role
):

    if not interaction.user.guild_permissions.manage_roles:

        await interaction.response.send_message(
            "❌ تحتاج Manage Roles.",
            ephemeral=True
        )

        return

    if role >= interaction.user.top_role:

        await interaction.response.send_message(
            "❌ لا يمكنك استخدام رتبة أعلى منك.",
            ephemeral=True
        )

        return

    if role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ رتبة البوت يجب أن تكون أعلى.",
            ephemeral=True
        )

        return

    try:

        await member.add_roles(
            role,
            reason=f"Role added by {interaction.user}"
        )

        await interaction.response.send_message(
            f"✅ تمت إضافة {role.mention} إلى {member.mention}."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ لا أستطيع إعطاء هذه الرتبة.",
            ephemeral=True
        )


# ============================================================
# STAFF — /ROLE_REMOVE
# ============================================================

@bot.tree.command(
    name="role_remove",
    description="إزالة رتبة من عضو"
)
@app_commands.describe(
    member="العضو",
    role="الرتبة"
)
@app_commands.default_permissions(
    manage_roles=True
)
async def role_remove_command(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role
):

    if not interaction.user.guild_permissions.manage_roles:

        await interaction.response.send_message(
            "❌ تحتاج Manage Roles.",
            ephemeral=True
        )

        return

    if role >= interaction.user.top_role:

        await interaction.response.send_message(
            "❌ لا يمكنك إزالة رتبة أعلى منك.",
            ephemeral=True
        )

        return

    try:

        await member.remove_roles(
            role,
            reason=f"Role removed by {interaction.user}"
        )

        await interaction.response.send_message(
            f"✅ تمت إزالة {role.mention} من {member.mention}."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ لا أستطيع إزالة هذه الرتبة.",
            ephemeral=True
        )


# ============================================================
# PROTECTION ENGINE
# ============================================================

URL_PATTERN = re.compile(
    r"(https?://|www\.|discord\.gg/|discord\.com/invite/)",
    re.IGNORECASE
)


spam_tracker = {}


async def process_protection(
    message
):

    if not message.guild:
        return False

    if message.author.bot:
        return False

    # Staff bypass
    if (
        message.author.guild_permissions.manage_messages
        or message.author.guild_permissions.administrator
    ):

        return False

    settings = await get_settings(
        message.guild.id
    )

    protection = settings.get(
        "protection",
        {}
    )

    # --------------------------------------------------------
    # ANTI LINK
    # --------------------------------------------------------

    if protection.get(
        "links",
        True
    ):

        if URL_PATTERN.search(
            message.content
        ):

            try:
                await message.delete()

            except (
                discord.Forbidden,
                discord.HTTPException
            ):
                pass

            try:

                await message.channel.send(
                    f"🔗 {message.author.mention} "
                    f"الروابط غير مسموحة هنا.",
                    delete_after=5
                )

            except discord.HTTPException:
                pass

            return True

    # --------------------------------------------------------
    # BAD WORDS
    # --------------------------------------------------------

    if protection.get(
        "badwords",
        True
    ):

        words = settings.get(
            "badwords",
            []
        )

        content = message.content.lower()

        for word in words:

            if word and word.lower() in content:

                try:
                    await message.delete()

                except (
                    discord.Forbidden,
                    discord.HTTPException
                ):
                    pass

                try:

                    await message.channel.send(
                        f"🤬 {message.author.mention} "
                        f"تم حذف الرسالة بسبب فلتر الكلمات.",
                        delete_after=5
                    )

                except discord.HTTPException:
                    pass

                return True

    # --------------------------------------------------------
    # ANTI SPAM
    # --------------------------------------------------------

    if protection.get(
        "antispam",
        True
    ):

        now = time.time()

        key = (
            message.guild.id,
            message.author.id
        )

        entries = spam_tracker.get(
            key,
            []
        )

        entries = [
            timestamp
            for timestamp in entries
            if now - timestamp < 7
        ]

        entries.append(
            now
        )

        spam_tracker[key] = entries

        if len(entries) >= 6:

            try:

                await message.delete()

            except (
                discord.Forbidden,
                discord.HTTPException
            ):
                pass

            try:

                await message.author.timeout(
                    timedelta(
                        seconds=30
                    ),
                    reason="Lunex Anti-Spam"
                )

            except (
                discord.Forbidden,
                discord.HTTPException
            ):
                pass

            spam_tracker[key] = []

            return True

    return False


# ============================================================
# MESSAGE XP + PROTECTION
# ============================================================

@bot.event
async def on_message(
    message: discord.Message
):

    if message.author.bot:
        return

    if message.guild:

        try:

            blocked = await process_protection(
                message
            )

            if blocked:

                return

        except Exception as e:

            print(
                "❌ Protection error:",
                repr(e)
            )

        # ----------------------------------------------------
        # XP
        # ----------------------------------------------------

        try:

            old_level, new_level = await add_xp(
                message.guild.id,
                message.author.id,
                5
            )

            if new_level > old_level:

                await give_level_role(
                    message.guild,
                    message.author,
                    new_level
                )

                try:

                    await message.channel.send(
                        f"🎉 {message.author.mention} "
                        f"وصل إلى المستوى **{new_level}**!",
                        delete_after=8
                    )

                except discord.HTTPException:

                    pass

        except Exception as e:

            print(
                "❌ XP error:",
                repr(e)
            )

    await bot.process_commands(
        message
    )


# ============================================================
# ERROR HANDLING — SLASH
# ============================================================

@bot.tree.error
async def on_app_command_error(
    interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        message = (
            "❌ ليس لديك الصلاحية المطلوبة."
        )

    elif isinstance(
        error,
        app_commands.errors.CommandOnCooldown
    ):

        message = (
            "⏳ حاول مرة أخرى لاحقًا."
        )

    else:

        print(
            "❌ Slash command error:",
            repr(error)
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

    except discord.HTTPException:

        pass


# ============================================================
# PREFIX ERROR
# ============================================================

@bot.event
async def on_command_error(
    ctx,
    error
):

    if isinstance(
        error,
        commands.CommandNotFound
    ):

        return

    if isinstance(
        error,
        commands.MissingPermissions
    ):

        await ctx.send(
            "❌ ليس لديك الصلاحية المطلوبة."
        )

        return

    print(
        "❌ Prefix command error:",
        repr(error)
    )


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    print(
        "=========================================="
    )

    print(
        f"🌙 Lunex logged in as "
        f"{bot.user} ({bot.user.id})"
    )

    print(
        f"🏠 Servers: {len(bot.guilds)}"
    )

    print(
        "🛡️ Protection: READY"
    )

    print(
        "⭐ XP System: READY"
    )

    print(
        "🌐 Website Settings: READY"
    )

    print(
        "=========================================="
    )


# ============================================================
# SETUP HOOK
# ============================================================

@bot.event
async def setup_hook():

    await init_database()

    try:

        await mongo.admin.command(
            "ping"
        )

        print(
            "✅ MongoDB connected."
        )

    except Exception as e:

        print(
            "⚠️ MongoDB unavailable:",
            repr(e)
        )

    try:

        synced = await bot.tree.sync()

        print(
            f"✅ Synced {len(synced)} slash commands."
        )

    except Exception as e:

        print(
            "❌ Slash sync failed:",
            repr(e)
        )


# ============================================================
# SHUTDOWN
# ============================================================

async def close_connections():

    try:

        mongo.close()

    except Exception:
        pass


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        bot.run(
            TOKEN
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
