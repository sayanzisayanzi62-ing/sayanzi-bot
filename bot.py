# ============================================================
# LUNEX BOT — RAILWAY OPTIMIZED EDITION
# Discord.py 2.x
# MongoDB Motor Async + SQLite aiosqlite
# FULL SLASH COMMAND EDITION
# ============================================================

import os
import re
import time
import asyncio
from datetime import timedelta, datetime, timezone

import discord
from discord.ext import commands
from discord import app_commands

import aiosqlite
import certifi

from motor.motor_asyncio import AsyncIOMotorClient


# ============================================================
# CONFIG
# ============================================================

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


# ============================================================
# SAFETY CHECK
# ============================================================

if not TOKEN:
    raise RuntimeError(
        "DISCORD_BOT_TOKEN environment variable is missing."
    )

if not MONGODB_URI:
    raise RuntimeError(
        "MONGODB_URI environment variable is missing."
    )


# ============================================================
# MONGODB
# ============================================================

mongo = AsyncIOMotorClient(
    MONGODB_URI,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000,
    socketTimeoutMS=5000,
    maxPoolSize=20,
    minPoolSize=1
)

mdb = mongo.get_default_database()

guild_settings = mdb["guildsettings"]


# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULT_SETTINGS = {
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


# ============================================================
# SETTINGS CACHE
# ============================================================

settings_cache = {}

SETTINGS_CACHE_TTL = 300


def clone_defaults():

    return {
        "welcome": DEFAULT_SETTINGS["welcome"].copy(),

        "leave": DEFAULT_SETTINGS["leave"].copy(),

        "ticket": DEFAULT_SETTINGS["ticket"].copy(),

        "autoReplies": [],

        "commandAliases": [],

        "protection":
            DEFAULT_SETTINGS["protection"].copy(),

        "badwords": {}
    }


def merge_settings(data):

    settings = clone_defaults()

    if not data:
        return settings

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

    for key in (
        "autoReplies",
        "commandAliases"
    ):

        if isinstance(data.get(key), list):

            settings[key] = data[key]

    if isinstance(
        data.get("badwords"),
        dict
    ):

        settings["badwords"] = data["badwords"]

    return settings


async def get_settings(guild_id: str):

    guild_id = str(guild_id)

    now = time.time()

    cached = settings_cache.get(
        guild_id
    )

    if cached:

        expires_at, data = cached

        if now < expires_at:

            return data

    doc = await guild_settings.find_one(
        {
            "guildId": guild_id
        }
    )

    if not doc:

        data = clone_defaults()

        await guild_settings.update_one(
            {
                "guildId": guild_id
            },
            {
                "$setOnInsert": {
                    "guildId": guild_id,
                    **data
                }
            },
            upsert=True
        )

    else:

        data = merge_settings(
            doc
        )

    settings_cache[guild_id] = (
        now + SETTINGS_CACHE_TTL,
        data
    )

    return data


async def update_settings(
    guild_id: str,
    update: dict
):

    guild_id = str(guild_id)

    await guild_settings.update_one(
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

    settings_cache.pop(
        guild_id,
        None
    )

    return await get_settings(
        guild_id
    )


# ============================================================
# MESSAGE BUILDER
# ============================================================

def build_message(
    template: str,
    member: discord.Member
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
        "[Img]",
        ""
    )

    text = text.replace(
        "[img]",
        ""
    )

    text = text.replace(
        "[nember]",
        str(member.guild.member_count)
    )

    text = text.replace(
        "[member_count]",
        str(member.guild.member_count)
    )

    return text


# ============================================================
# INTENTS
# ============================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.message_content = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    case_insensitive=True,
    help_command=None
)


# ============================================================
# GLOBAL STATE
# ============================================================

db = None

xp_pending = {}

spam_cache = {}

badword_cache = {}

_views_registered = False

_commands_synced = False

_background_started = False


# ============================================================
# XP CONFIG
# ============================================================

XP_PER_MESSAGE = 1

XP_PER_LEVEL = 20


# ============================================================
# LOCALIZATION
# ============================================================

locales = {

    "en": {

        "lang_set":
            "Your personal language has been set to English.",

        "higher_bot":
            "Their role is higher than or equal to mine!",

        "higher_user":
            "Their role is higher than or equal to yours!",

        "banned":
            "Member banned successfully.",

        "kicked":
            "Member kicked successfully.",

        "unbanned":
            "User unbanned.",

        "invalid_time":
            "Invalid time format. Example: `10m`, `1h`, `1d`.",

        "timeout_applied":
            "Timeout applied successfully.",

        "timeout_removed":
            "Timeout removed.",

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
            "Cleared `{}` messages.",

        "error":
            "Error:"
    },

    "ar": {

        "lang_set":
            "تم تعيين لغتك الشخصية إلى العربية.",

        "higher_bot":
            "رتبة هذا العضو أعلى من رتبتي أو مساوية لها!",

        "higher_user":
            "رتبة هذا العضو أعلى من رتبتك أو مساوية لها!",

        "banned":
            "تم حظر العضو بنجاح.",

        "kicked":
            "تم طرد العضو بنجاح.",

        "unbanned":
            "تم فك الحظر عن المستخدم.",

        "invalid_time":
            "صيغة الوقت غير صحيحة. مثال: `10m` أو `1h` أو `1d`.",

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

        "error":
            "حدث خطأ:"
    }
}


# ============================================================
# DATABASE
# ============================================================

async def init_database():

    global db

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
        CREATE TABLE IF NOT EXISTS reset_tracker(
            id INTEGER PRIMARY KEY CHECK(id = 1),
            last_day TEXT,
            last_week TEXT,
            last_month TEXT
        )
    """)

    # ========================================================
    # LEVEL ROLES
    # level = level number
    # role_id = Discord role ID
    # ========================================================

    await db.execute("""
        CREATE TABLE IF NOT EXISTS level_roles(
            guild_id TEXT,
            level INTEGER,
            role_id TEXT,
            PRIMARY KEY(guild_id, level)
        )
    """)

    await db.commit()


# ============================================================
# LANGUAGE FUNCTIONS
# ============================================================

async def get_lang(user_id: str):

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

    return "en"


async def t(
    user_id: str,
    key: str,
    *args
):

    lang = await get_lang(
        user_id
    )

    text = locales[lang].get(
        key,
        key
    )

    if args:

        return text.format(
            *args
        )

    return text


# ============================================================
# TIME PARSER
# ============================================================

def parse_time(value):

    try:

        value = value.strip().lower()

        if len(value) < 2:
            return None

        number = int(
            value[:-1]
        )

        unit = value[-1]

        if number <= 0:
            return None

        if unit == "s":
            return number

        if unit == "m":
            return number * 60

        if unit == "h":
            return number * 3600

        if unit == "d":
            return number * 86400

    except Exception:

        return None

    return None


# ============================================================
# HIERARCHY
# ============================================================

async def check_hierarchy(
    interaction: discord.Interaction,
    member: discord.Member
):

    uid = str(
        interaction.user.id
    )

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
            "Bot member is unavailable.",
            ephemeral=True
        )

        return False

    if member == guild.owner:

        await interaction.response.send_message(
            "You cannot moderate the server owner.",
            ephemeral=True
        )

        return False

    if member.top_role >= me.top_role:

        await interaction.response.send_message(
            await t(
                uid,
                "higher_bot"
            ),
            ephemeral=True
        )

        return False

    if (
        member.top_role >= interaction.user.top_role
        and
        interaction.user.id != guild.owner_id
    ):

        await interaction.response.send_message(
            await t(
                uid,
                "higher_user"
            ),
            ephemeral=True
        )

        return False

    return True


# ============================================================
# XP HELPERS
# ============================================================

async def get_messages(
    guild_id,
    user_id
):

    guild_id = str(guild_id)

    user_id = str(user_id)

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

    pending = xp_pending.get(
        (
            guild_id,
            user_id
        ),
        {}
    )

    return (
        (row[0] if row else 0)
        +
        pending.get(
            "messages",
            0
        )
    )


def calculate_level(messages):

    return messages // XP_PER_LEVEL


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


# ============================================================
# LEVEL ROLE SYSTEM
# ============================================================

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

    if not row:
        return None

    return int(row[0])


async def process_level_roles(
    guild: discord.Guild,
    user_id: str
):

    try:

        member = guild.get_member(
            int(user_id)
        )

        if not member:
            return

        messages = await get_messages(
            guild.id,
            user_id
        )

        current_level = calculate_level(
            messages
        )

        if current_level <= 0:
            return

        async with db.execute(
            """
            SELECT level, role_id
            FROM level_roles
            WHERE guild_id=?
            AND level<=?
            ORDER BY level ASC
            """,
            (
                str(guild.id),
                current_level
            )
        ) as cursor:

            rows = await cursor.fetchall()

        if not rows:
            return

        bot_member = guild.me

        if not bot_member:
            return

        for level, role_id in rows:

            role = guild.get_role(
                int(role_id)
            )

            if not role:
                continue

            if role >= bot_member.top_role:
                continue

            if role in member.roles:
                continue

            try:

                await member.add_roles(
                    role,
                    reason=(
                        f"Lunex Level {level} reward"
                    )
                )

                print(
                    f"🎉 {member} received "
                    f"{role.name} for level {level}"
                )

            except Exception as e:

                print(
                    "level role error:",
                    e
                )

    except Exception as e:

        print(
            "process level roles error:",
            e
        )


# ============================================================
# FLUSH XP
# ============================================================

async def flush_xp():

    global xp_pending

    if not xp_pending:
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
                        messages + excluded.messages,

                    day_count =
                        day_count + excluded.day_count,

                    week_count =
                        week_count + excluded.week_count,

                    month_count =
                        month_count + excluded.month_count
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
            "XP flush error:",
            e
        )

        # Restore pending XP if database failed
        for key, values in pending.items():

            if key not in xp_pending:

                xp_pending[key] = values

            else:

                for field in values:

                    xp_pending[key][field] += (
                        values[field]
                    )


# ============================================================
# XP LOOP
# ============================================================

async def xp_loop():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            await flush_xp()

        except Exception as e:

            print(
                "XP loop error:",
                e
            )

        await asyncio.sleep(10)


# ============================================================
# LEVEL ROLE LOOP
# ============================================================

async def level_role_loop():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            # First save latest XP
            await flush_xp()

            # Process users that recently sent messages
            users = []

            async with db.execute(
                """
                SELECT guild_id, user_id
                FROM xp
                """
            ) as cursor:

                rows = await cursor.fetchall()

            for guild_id, user_id in rows:

                guild = bot.get_guild(
                    int(guild_id)
                )

                if not guild:
                    continue

                users.append(
                    (
                        guild,
                        user_id
                    )
                )

            # Limit processing per cycle
            # to keep Railway fast.
            for guild, user_id in users:

                await process_level_roles(
                    guild,
                    user_id
                )

        except Exception as e:

            print(
                "level role loop error:",
                e
            )

        await asyncio.sleep(15)


# ============================================================
# PREMIUM EXPIRY
# ============================================================

async def check_expired_premiums():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            current_time = time.time()

            await db.execute(
                """
                DELETE FROM premium_users
                WHERE expiry_time <= ?
                """,
                (
                    current_time,
                )
            )

            await db.commit()

        except Exception as e:

            print(
                "premium error:",
                e
            )

        await asyncio.sleep(60)


# ============================================================
# LEADERBOARD RESET
# ============================================================

async def reset_leaderboards():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            now = datetime.now(
                timezone.utc
            )

            today = now.strftime(
                "%Y-%m-%d"
            )

            iso = now.isocalendar()

            week = (
                f"{iso.year}-{iso.week}"
            )

            month = now.strftime(
                "%Y-%m"
            )

            async with db.execute(
                """
                SELECT
                    last_day,
                    last_week,
                    last_month

                FROM reset_tracker

                WHERE id=1
                """
            ) as cursor:

                row = await cursor.fetchone()

            if not row:

                await db.execute(
                    """
                    INSERT INTO reset_tracker
                    VALUES(1, ?, ?, ?)
                    """,
                    (
                        today,
                        week,
                        month
                    )
                )

            else:

                last_day, last_week, last_month = row

                if last_day != today:

                    await db.execute(
                        """
                        UPDATE xp
                        SET day_count=0
                        """
                    )

                if last_week != week:

                    await db.execute(
                        """
                        UPDATE xp
                        SET week_count=0
                        """
                    )

                if last_month != month:

                    await db.execute(
                        """
                        UPDATE xp
                        SET month_count=0
                        """
                    )

                await db.execute(
                    """
                    UPDATE reset_tracker

                    SET
                        last_day=?,
                        last_week=?,
                        last_month=?

                    WHERE id=1
                    """,
                    (
                        today,
                        week,
                        month
                    )
                )

            await db.commit()

        except Exception as e:

            print(
                "reset error:",
                e
            )

        await asyncio.sleep(3600)


# ============================================================
# TICKET CLOSE VIEW
# ============================================================

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
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            "Closing this ticket in 5 seconds..."
        )

        await asyncio.sleep(5)

        try:

            await interaction.channel.delete()

        except Exception as e:

            print(
                "ticket delete error:",
                e
            )


# ============================================================
# TICKET VIEW
# ============================================================

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
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        try:

            guild = interaction.guild

            if not guild:
                return

            settings = await get_settings(
                guild.id
            )

            ticket = settings[
                "ticket"
            ]

            safe_name = (
                f"ticket-{interaction.user.id}"
            )

            existing = discord.utils.get(
                guild.text_channels,
                name=safe_name
            )

            if existing:

                await interaction.response.send_message(
                    f"You already have an open ticket: {existing.mention}",
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
                        read_message_history=True
                    )
            }

            category = None

            if ticket.get(
                "categoryId"
            ):

                try:

                    category = guild.get_channel(
                        int(ticket["categoryId"])
                    )

                except Exception:

                    category = None

            channel = await guild.create_text_channel(
                safe_name,
                overwrites=overwrites,
                category=category
            )

            description = build_message(
                ticket.get(
                    "description"
                )
                or
                "Hello [User], our support team will be with you shortly.",
                interaction.user
            )

            embed = discord.Embed(
                title="🎫 Ticket",
                description=description,
                color=COLOR
            )

            if ticket.get("image"):

                embed.set_image(
                    url=ticket["image"]
                )

            await channel.send(
                embed=embed,
                view=CloseTicketView()
            )

            await interaction.response.send_message(
                f"Your ticket has been opened: {channel.mention}",
                ephemeral=True
            )

        except Exception as e:

            print(
                "open ticket error:",
                e
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Something went wrong opening your ticket.",
                    ephemeral=True
                )


# ============================================================
# HELP
# ============================================================

class HelpSelect(
    discord.ui.Select
):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="Member",
                description="Member, XP and information commands",
                emoji="👥",
                value="member"
            ),

            discord.SelectOption(
                label="Staff",
                description="Moderation and server commands",
                emoji="🛡️",
                value="staff"
            ),

            discord.SelectOption(
                label="XP & Levels",
                description="XP, levels and level rewards",
                emoji="⭐",
                value="xp"
            )
        ]

        super().__init__(
            placeholder="Choose a category",
            options=options,
            custom_id="lunex_help_select"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        selected = self.values[0]

        if selected == "member":

            embed = discord.Embed(
                title="👥 MEMBER COMMANDS",
                color=COLOR
            )

            embed.add_field(
                name="📌 Information",
                value=(
                    "`/profile` — View profile\n"
                    "`/avatar` — View avatar\n"
                    "`/server` — Server information\n"
                    "`/language` — Change your language"
                ),
                inline=False
            )

        elif selected == "xp":

            embed = discord.Embed(
                title="⭐ XP & LEVEL COMMANDS",
                description=(
                    "Every message gives **1 XP**.\n"
                    f"Every **{XP_PER_LEVEL} XP** gives 1 level."
                ),
                color=COLOR
            )

            embed.add_field(
                name="XP",
                value=(
                    "`/xp` — Check XP\n"
                    "`/level` — Check level\n"
                    "`/leaderboard` — Leaderboard"
                ),
                inline=False
            )

            embed.add_field(
                name="🎁 Level Roles",
                value=(
                    "`/level_roll` — Set a level reward\n"
                    "`/level_roll_remove` — Remove reward\n"
                    "`/level_roll_list` — Show rewards"
                ),
                inline=False
            )

        else:

            embed = discord.Embed(
                title="🛡️ STAFF COMMANDS",
                color=COLOR
            )

            embed.add_field(
                name="Moderation",
                value=(
                    "`/ban`\n"
                    "`/kick`\n"
                    "`/unban`\n"
                    "`/timeout`\n"
                    "`/timeout_remove`\n"
                    "`/clear`"
                ),
                inline=False
            )

            embed.add_field(
                name="Server",
                value=(
                    "`/lock`\n"
                    "`/open`\n"
                    "`/add_role`\n"
                    "`/remove_role`\n"
                    "`/nickname`\n"
                    "`/protection`"
                ),
                inline=False
            )

            embed.add_field(
                name="Automation",
                value=(
                    "`/badword`\n"
                    "`/auto_reply`\n"
                    "`/auto_reply_remove`"
                ),
                inline=False
            )

        embed.set_footer(
            text="Lunex • More than a bot"
        )

        if bot.user:

            embed.set_thumbnail(
                url=bot.user.display_avatar.url
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


def build_main_embed():

    embed = discord.Embed(
        title="🌙 LUNEX BOT",
        description=(
            "Advanced, powerful and simple server management.\n\n"
            "Use the menu below to explore all commands."
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
            f"1 message = 1 XP\n"
            f"{XP_PER_LEVEL} XP = 1 Level"
        ),
        inline=False
    )

    embed.set_footer(
        text="Lunex • More than a bot"
    )

    return embed


# ============================================================
# WELCOME
# ============================================================

@bot.event
async def on_member_join(
    member: discord.Member
):

    try:

        settings = await get_settings(
            member.guild.id
        )

        welcome = settings[
            "welcome"
        ]

        if not welcome.get(
            "enabled"
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

        embed = discord.Embed(
            description=build_message(
                welcome.get(
                    "message"
                ),
                member
            ),
            color=COLOR
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        await channel.send(
            embed=embed
        )

    except Exception as e:

        print(
            "welcome error:",
            e
        )


# ============================================================
# LEAVE
# ============================================================

@bot.event
async def on_member_remove(
    member: discord.Member
):

    try:

        settings = await get_settings(
            member.guild.id
        )

        leave = settings[
            "leave"
        ]

        if not leave.get(
            "enabled"
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

        embed = discord.Embed(
            description=build_message(
                leave.get(
                    "message"
                ),
                member
            ),
            color=COLOR
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        await channel.send(
            embed=embed
        )

    except Exception as e:

        print(
            "leave error:",
            e
        )


# ============================================================
# BADWORDS
# ============================================================

async def get_badwords(
    guild_id
):

    guild_id = str(
        guild_id
    )

    if guild_id in badword_cache:

        return badword_cache[
            guild_id
        ]

    settings = await get_settings(
        guild_id
    )

    data = settings.get(
        "badwords",
        {}
    )

    badword_cache[
        guild_id
    ] = data

    return data


# ============================================================
# MESSAGE EVENT
# ============================================================

@bot.event
async def on_message(
    message: discord.Message
):

    if message.author.bot:
        return

    if not message.guild:
        return

    guild_id = str(
        message.guild.id
    )

    user_id = str(
        message.author.id
    )

    # ========================================================
    # XP
    # ========================================================

    add_xp_memory(
        guild_id,
        user_id
    )

    # ========================================================
    # SETTINGS
    # ========================================================

    try:

        settings = await get_settings(
            guild_id
        )

    except Exception as e:

        print(
            "settings error:",
            e
        )

        settings = clone_defaults()

    protection = settings.get(
        "protection",
        {}
    )

    # ========================================================
    # AUTO REPLIES
    # ========================================================

    try:

        content_lower = (
            message.content.strip().lower()
        )

        for entry in settings.get(
            "autoReplies",
            []
        ):

            trigger = str(
                entry.get(
                    "message",
                    ""
                )
            ).strip().lower()

            if (
                trigger
                and trigger in content_lower
            ):

                reply = entry.get(
                    "reply",
                    ""
                )

                if reply:

                    await message.channel.send(
                        embed=discord.Embed(
                            description=reply,
                            color=COLOR
                        )
                    )

                break

    except Exception as e:

        print(
            "auto reply error:",
            e
        )

    # ========================================================
    # PROTECTION
    # ========================================================

    try:

        if not message.author.guild_permissions.administrator:

            # ==================================================
            # BADWORDS
            # ==================================================

            if protection.get(
                "badwords",
                True
            ):

                badwords = await get_badwords(
                    guild_id
                )

                content_lower = (
                    message.content.lower()
                )

                for word, seconds in badwords.items():

                    pattern = (
                        r"(?<!\w)"
                        +
                        re.escape(
                            str(word).lower()
                        )
                        +
                        r"(?!\w)"
                    )

                    if re.search(
                        pattern,
                        content_lower
                    ):

                        try:

                            await message.delete()

                            await message.author.timeout(
                                timedelta(
                                    seconds=int(
                                        seconds
                                    )
                                ),
                                reason="Forbidden word"
                            )

                            await message.channel.send(
                                f"⛔ {message.author.mention} "
                                "was timed out for using a forbidden word.",
                                delete_after=5
                            )

                        except Exception as e:

                            print(
                                "badword error:",
                                e
                            )

                        break

            # ==================================================
            # LINKS
            # ==================================================

            if protection.get(
                "links",
                True
            ):

                content_lower = (
                    message.content.lower()
                )

                if (
                    "http://" in content_lower
                    or
                    "https://" in content_lower
                ):

                    try:

                        await message.delete()

                        await message.channel.send(
                            f"🚫 {message.author.mention} "
                            "Links are not allowed in this server!",
                            delete_after=5
                        )

                    except Exception as e:

                        print(
                            "link protection error:",
                            e
                        )

            # ==================================================
            # ANTISPAM
            # ==================================================

            if protection.get(
                "antispam",
                True
            ):

                key = (
                    guild_id,
                    user_id
                )

                now = time.time()

                history = spam_cache.get(
                    key,
                    []
                )

                history.append(
                    now
                )

                history = [
                    timestamp
                    for timestamp in history
                    if now - timestamp < 3
                ]

                spam_cache[
                    key
                ] = history

                if len(history) >= 5:

                    try:

                        await message.author.timeout(
                            timedelta(
                                minutes=10
                            ),
                            reason="Spamming"
                        )

                        await message.channel.send(
                            f"⏱ {message.author.mention} "
                            "You have been timed out for spamming.",
                            delete_after=5
                        )

                    except Exception as e:

                        print(
                            "spam error:",
                            e
                        )

                    spam_cache[
                        key
                    ] = []

    except Exception as e:

        print(
            "protection error:",
            e
        )

    # ========================================================
    # Prefix compatibility: !help only
    # ========================================================

    await bot.process_commands(
        message
    )


# ============================================================
# !help COMPATIBILITY
# ============================================================

@bot.command(
    name="help"
)
async def prefix_help(
    ctx
):

    await ctx.send(
        embed=build_main_embed(),
        view=HelpView()
    )


# ============================================================
# /HELP
# ============================================================

@bot.tree.command(
    name="help",
    description="Open Lunex help menu"
)
async def slash_help(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        embed=build_main_embed(),
        view=HelpView(),
        ephemeral=True
    )


# ============================================================
# /COMMANDS
# ============================================================

@bot.tree.command(
    name="commands",
    description="Show all Lunex commands"
)
async def commands_list(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        embed=build_main_embed(),
        view=HelpView(),
        ephemeral=True
    )


# ============================================================
# /LANGUAGE
# ============================================================

@bot.tree.command(
    name="language",
    description="Set your personal language"
)
@app_commands.describe(
    lang="Choose your language"
)
@app_commands.choices(
    lang=[
        app_commands.Choice(
            name="English",
            value="en"
        ),
        app_commands.Choice(
            name="العربية",
            value="ar"
        )
    ]
)
async def language(
    interaction: discord.Interaction,
    lang: app_commands.Choice[str]
):

    uid = str(
        interaction.user.id
    )

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
            uid,
            lang.value
        )
    )

    await db.commit()

    await interaction.response.send_message(
        await t(
            uid,
            "lang_set"
        ),
        ephemeral=True
    )


# ============================================================
# /XP
# ============================================================

@bot.tree.command(
    name="xp",
    description="Check your XP"
)
async def slash_xp(
    interaction: discord.Interaction
):

    messages = await get_messages(
        interaction.guild.id,
        interaction.user.id
    )

    embed = discord.Embed(
        title="⭐ XP",
        description=f"`{messages} XP`",
        color=COLOR
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /LEVEL
# ============================================================

@bot.tree.command(
    name="level",
    description="Check your level"
)
async def slash_level(
    interaction: discord.Interaction
):

    messages = await get_messages(
        interaction.guild.id,
        interaction.user.id
    )

    level = calculate_level(
        messages
    )

    current_progress = (
        messages % XP_PER_LEVEL
    )

    embed = discord.Embed(
        title="📊 LEVEL",
        color=COLOR
    )

    embed.add_field(
        name="Level",
        value=f"`{level}`",
        inline=True
    )

    embed.add_field(
        name="XP",
        value=f"`{messages}`",
        inline=True
    )

    embed.add_field(
        name="Progress",
        value=(
            f"`{current_progress}/{XP_PER_LEVEL}`"
        ),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /PROFILE
# ============================================================

@bot.tree.command(
    name="profile",
    description="View a member profile"
)
@app_commands.describe(
    member="Member to view"
)
async def profile(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    member = (
        member
        or interaction.user
    )

    messages = await get_messages(
        interaction.guild.id,
        member.id
    )

    level = calculate_level(
        messages
    )

    embed = discord.Embed(
        title=f"👤 Profile • {member.name}",
        color=COLOR
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.add_field(
        name="⭐ XP",
        value=f"`{messages}`",
        inline=True
    )

    embed.add_field(
        name="📊 Level",
        value=f"`{level}`",
        inline=True
    )

    embed.add_field(
        name="👑 Top Role",
        value=member.top_role.mention,
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /AVATAR
# ============================================================

@bot.tree.command(
    name="avatar",
    description="View a member avatar"
)
@app_commands.describe(
    member="Member"
)
async def avatar(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    member = (
        member
        or interaction.user
    )

    embed = discord.Embed(
        title=f"🖼️ Avatar • {member.name}",
        color=COLOR
    )

    embed.set_image(
        url=member.display_avatar.url
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /SERVER
# ============================================================

@bot.tree.command(
    name="server",
    description="View server information"
)
async def server(
    interaction: discord.Interaction
):

    guild = interaction.guild

    bots_count = sum(
        1
        for member in guild.members
        if member.bot
    )

    embed = discord.Embed(
        title=f"🖥️ {guild.name}",
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
        name="🤖 Bots",
        value=f"`{bots_count}`",
        inline=True
    )

    embed.add_field(
        name="📅 Created",
        value=(
            f"`{guild.created_at.strftime('%Y-%m-%d')}`"
        ),
        inline=True
    )

    embed.add_field(
        name="👑 Owner",
        value=(
            guild.owner.mention
            if guild.owner
            else "Unknown"
        ),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /LEADERBOARD
# ============================================================

@bot.tree.command(
    name="leaderboard",
    description="Show XP leaderboard"
)
@app_commands.describe(
    period="Leaderboard period"
)
@app_commands.choices(
    period=[
        app_commands.Choice(
            name="Monthly",
            value="month"
        ),
        app_commands.Choice(
            name="Weekly",
            value="week"
        ),
        app_commands.Choice(
            name="Daily",
            value="day"
        )
    ]
)
async def leaderboard(
    interaction: discord.Interaction,
    period: app_commands.Choice[str] = None
):

    await flush_xp()

    gid = str(
        interaction.guild.id
    )

    selected = (
        period.value
        if period
        else "month"
    )

    if selected == "day":

        column = "day_count"

        title = "🏆 Daily Leaderboard"

    elif selected == "week":

        column = "week_count"

        title = "🏆 Weekly Leaderboard"

    else:

        column = "month_count"

        title = "🏆 Monthly Leaderboard"

    query = f"""
        SELECT user_id, {column}
        FROM xp
        WHERE guild_id=?
        AND {column}>0
        ORDER BY {column} DESC
        LIMIT 10
    """

    async with db.execute(
        query,
        (
            gid,
        )
    ) as cursor:

        rows = await cursor.fetchall()

    embed = discord.Embed(
        title=title,
        color=COLOR
    )

    if not rows:

        embed.description = (
            "No data yet."
        )

    else:

        medals = [
            "🥇",
            "🥈",
            "🥉"
        ]

        lines = []

        for index, (
            user_id,
            count
        ) in enumerate(
            rows,
            start=1
        ):

            medal = (
                medals[index - 1]
                if index <= 3
                else f"`#{index}`"
            )

            lines.append(
                f"{medal} <@{user_id}> — `{count}` messages"
            )

        embed.description = "\n".join(
            lines
        )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /LEVEL_ROLL
#
# Example:
# /level_roll level:5 role:@Level 5
#
# When member reaches level 5:
# they automatically receive that role.
# ============================================================

@bot.tree.command(
    name="level_roll",
    description="Set a role reward for a level"
)
@app_commands.describe(
    level="The level that gives the role",
    role="The role to give"
)
@app_commands.default_permissions(
    manage_roles=True
)
async def level_roll(
    interaction: discord.Interaction,
    level: app_commands.Range[int, 1, 100000],
    role: discord.Role
):

    guild = interaction.guild

    if not guild:

        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True
        )

        return

    me = guild.me

    if not me:

        await interaction.response.send_message(
            "Bot member is unavailable.",
            ephemeral=True
        )

        return

    if role.is_default():

        await interaction.response.send_message(
            "❌ You cannot use @everyone.",
            ephemeral=True
        )

        return

    if role.managed:

        await interaction.response.send_message(
            "❌ Managed/integration roles cannot be assigned.",
            ephemeral=True
        )

        return

    if role >= me.top_role:

        await interaction.response.send_message(
            "❌ That role is higher than or equal to my highest role.",
            ephemeral=True
        )

        return

    # User cannot configure a role above their own role
    if (
        interaction.user.id != guild.owner_id
        and
        role >= interaction.user.top_role
    ):

        await interaction.response.send_message(
            "❌ You cannot configure a role higher than or equal to your highest role.",
            ephemeral=True
        )

        return

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
            str(guild.id),
            int(level),
            str(role.id)
        )
    )

    await db.commit()

    await interaction.response.send_message(
        f"✅ Level **{level}** → {role.mention}\n"
        f"Members will receive this role when they reach level **{level}**."
    )


# ============================================================
# /LEVEL_ROLL_REMOVE
# ============================================================

@bot.tree.command(
    name="level_roll_remove",
    description="Remove a level role reward"
)
@app_commands.describe(
    level="Level reward to remove"
)
@app_commands.default_permissions(
    manage_roles=True
)
async def level_roll_remove(
    interaction: discord.Interaction,
    level: app_commands.Range[int, 1, 100000]
):

    result = await db.execute(
        """
        DELETE FROM level_roles
        WHERE guild_id=?
        AND level=?
        """,
        (
            str(interaction.guild.id),
            int(level)
        )
    )

    await db.commit()

    if result.rowcount == 0:

        await interaction.response.send_message(
            f"❌ There is no reward configured for level `{level}`.",
            ephemeral=True
        )

        return

    await interaction.response.send_message(
        f"✅ Level reward `{level}` has been removed."
    )


# ============================================================
# /LEVEL_ROLL_LIST
# ============================================================

@bot.tree.command(
    name="level_roll_list",
    description="Show all level role rewards"
)
async def level_roll_list(
    interaction: discord.Interaction
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
        title="🎁 Level Role Rewards",
        color=COLOR
    )

    if not rows:

        embed.description = (
            "No level rewards have been configured."
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
                    f"⭐ Level `{level}` → "
                    f"`Deleted role ({role_id})`"
                )

        embed.description = "\n".join(
            lines
        )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ============================================================
# /PROTECTION
# ============================================================

@bot.tree.command(
    name="protection",
    description="Configure server protection"
)
@app_commands.describe(
    feature="Protection feature",
    status="on or off"
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
    ],
    status=[
        app_commands.Choice(
            name="ON",
            value="on"
        ),
        app_commands.Choice(
            name="OFF",
            value="off"
        )
    ]
)
@app_commands.default_permissions(
    manage_guild=True
)
async def protection(
    interaction: discord.Interaction,
    feature: app_commands.Choice[str],
    status: app_commands.Choice[str]
):

    enabled = (
        status.value == "on"
    )

    await update_settings(
        str(interaction.guild.id),
        {
            f"protection.{feature.value}":
                enabled
        }
    )

    await interaction.response.send_message(
        f"✅ `{feature.name}` → `{status.name}`"
    )


# ============================================================
# /BAN
# ============================================================

@bot.tree.command(
    name="ban",
    description="Ban a member"
)
@app_commands.default_permissions(
    ban_members=True
)
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = None
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
                str(interaction.user.id),
                "banned"
            )
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ {e}",
            ephemeral=True
        )


# ============================================================
# /KICK
# ============================================================

@bot.tree.command(
    name="kick",
    description="Kick a member"
)
@app_commands.default_permissions(
    kick_members=True
)
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = None
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
                str(interaction.user.id),
                "kicked"
            )
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ {e}",
            ephemeral=True
        )


# ============================================================
# /UNBAN
# ============================================================

@bot.tree.command(
    name="unban",
    description="Unban a user by ID"
)
@app_commands.default_permissions(
    ban_members=True
)
async def unban(
    interaction: discord.Interaction,
    user_id: str
):

    uid = str(
        interaction.user.id
    )

    try:

        user = await bot.fetch_user(
            int(user_id)
        )

        await interaction.guild.unban(
            user
        )

        await interaction.response.send_message(
            await t(
                uid,
                "unbanned"
            )
        )

    except Exception as e:

        await interaction.response.send_message(
            f"{await t(uid, 'error')} `{e}`",
            ephemeral=True
        )


# ============================================================
# /TIMEOUT
# ============================================================

@bot.tree.command(
    name="timeout",
    description="Timeout a member"
)
@app_commands.default_permissions(
    moderate_members=True
)
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    time: str
):

    uid = str(
        interaction.user.id
    )

    if not await check_hierarchy(
        interaction,
        member
    ):
        return

    seconds = parse_time(
        time
    )

    if not seconds:

        await interaction.response.send_message(
            await t(
                uid,
                "invalid_time"
            ),
            ephemeral=True
        )

        return

    if seconds > 28 * 86400:

        await interaction.response.send_message(
            "❌ Discord timeout cannot exceed 28 days.",
            ephemeral=True
        )

        return

    try:

        await member.timeout(
            timedelta(
                seconds=seconds
            )
        )

        await interaction.response.send_message(
            await t(
                uid,
                "timeout_applied"
            )
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ {e}",
            ephemeral=True
        )


# ============================================================
# /TIMEOUT_REMOVE
# ============================================================

@bot.tree.command(
    name="timeout_remove",
    description="Remove timeout"
)
@app_commands.default_permissions(
    moderate_members=True
)
async def timeout_remove(
    interaction: discord.Interaction,
    member: discord.Member
):

    uid = str(
        interaction.user.id
    )

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
            await t(
                uid,
                "timeout_removed"
            )
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ {e}",
            ephemeral=True
        )


# ============================================================
# /LOCK
# ============================================================

@bot.tree.command(
    name="lock",
    description="Lock the current channel"
)
@app_commands.default_permissions(
    manage_channels=True
)
async def lock(
    interaction: discord.Interaction
):

    overwrite = (
        interaction.channel.overwrites_for(
            interaction.guild.default_role
        )
    )

    overwrite.send_messages = False

    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite
    )

    await interaction.response.send_message(
        await t(
            str(interaction.user.id),
            "channel_locked"
        )
    )


# ============================================================
# /OPEN
# ============================================================

@bot.tree.command(
    name="open",
    description="Unlock the current channel"
)
@app_commands.default_permissions(
    manage_channels=True
)
async def open_channel(
    interaction: discord.Interaction
):

    overwrite = (
        interaction.channel.overwrites_for(
            interaction.guild.default_role
        )
    )

    overwrite.send_messages = None

    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite
    )

    await interaction.response.send_message(
        await t(
            str(interaction.user.id),
            "channel_unlocked"
        )
    )


# ============================================================
# /ADD_ROLE
# ============================================================

@bot.tree.command(
    name="add_role",
    description="Add a role to a member"
)
@app_commands.default_permissions(
    manage_roles=True
)
async def add_role(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role
):

    if not await check_hierarchy(
        interaction,
        member
    ):
        return

    me = interaction.guild.me

    if role >= me.top_role:

        await interaction.response.send_message(
            "❌ That role is higher than or equal to my role.",
            ephemeral=True
        )

        return

    if role.is_default() or role.managed:

        await interaction.response.send_message(
            "❌ This role cannot be assigned.",
            ephemeral=True
        )

        return

    await member.add_roles(
        role
    )

    await interaction.response.send_message(
        await t(
            str(interaction.user.id),
            "role_added"
        )
    )


# ============================================================
# /REMOVE_ROLE
# ============================================================

@bot.tree.command(
    name="remove_role",
    description="Remove a role from a member"
)
@app_commands.default_permissions(
    manage_roles=True
)
async def remove_role(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role
):

    if not await check_hierarchy(
        interaction,
        member
    ):
        return

    me = interaction.guild.me

    if role >= me.top_role:

        await interaction.response.send_message(
            "❌ That role is higher than or equal to my role.",
            ephemeral=True
        )

        return

    await member.remove_roles(
        role
    )

    await interaction.response.send_message(
        await t(
            str(interaction.user.id),
            "role_removed"
        )
    )


# ============================================================
# /NICKNAME
# ============================================================

@bot.tree.command(
    name="nickname",
    description="Change a member nickname"
)
@app_commands.default_permissions(
    manage_nicknames=True
)
async def nickname(
    interaction: discord.Interaction,
    member: discord.Member,
    nickname: str = None
):

    uid = str(
        interaction.user.id
    )

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
            await t(
                uid,
                "nick_changed"
            )
        )

    except Exception as e:

        await interaction.response.send_message(
            f"{await t(uid, 'error')} `{e}`",
            ephemeral=True
        )


# ============================================================
# /CLEAR
# ============================================================

@bot.tree.command(
    name="clear",
    description="Delete messages"
)
@app_commands.default_permissions(
    manage_messages=True
)
async def clear(
    interaction: discord.Interaction,
    amount: app_commands.Range[int, 1, 100]
):

    try:

        deleted = await interaction.channel.purge(
            limit=int(amount)
        )

        await interaction.response.send_message(
            f"🧹 Cleared `{len(deleted)}` messages.",
            ephemeral=True
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ {e}",
            ephemeral=True
        )


# ============================================================
# /BADWORD
# ============================================================

@bot.tree.command(
    name="badword",
    description="Add a forbidden word"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def badword(
    interaction: discord.Interaction,
    word: str,
    time: str
):

    seconds = parse_time(
        time
    )

    if not seconds:

        await interaction.response.send_message(
            await t(
                str(interaction.user.id),
                "invalid_time"
            ),
            ephemeral=True
        )

        return

    word = word.strip().lower()

    if not word:

        await interaction.response.send_message(
            "❌ Invalid word.",
            ephemeral=True
        )

        return

    gid = str(
        interaction.guild.id
    )

    await guild_settings.update_one(
        {
            "guildId": gid
        },
        {
            "$set": {
                f"badwords.{word}":
                    seconds
            },
            "$setOnInsert": {
                "guildId": gid
            }
        },
        upsert=True
    )

    badword_cache.pop(
        gid,
        None
    )

    settings_cache.pop(
        gid,
        None
    )

    await interaction.response.send_message(
        f"✅ Added `{word}`.",
        ephemeral=True
    )


# ============================================================
# /AUTO_REPLY
# ============================================================

@bot.tree.command(
    name="auto_reply",
    description="Add automatic reply"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def auto_reply(
    interaction: discord.Interaction,
    trigger: str,
    reply: str
):

    gid = str(
        interaction.guild.id
    )

    await guild_settings.update_one(
        {
            "guildId": gid
        },
        {
            "$push": {
                "autoReplies": {
                    "message": trigger,
                    "reply": reply
                }
            },
            "$setOnInsert": {
                "guildId": gid
            }
        },
        upsert=True
    )

    settings_cache.pop(
        gid,
        None
    )

    await interaction.response.send_message(
        f"✅ Auto-reply added for `{trigger}`.",
        ephemeral=True
    )


# ============================================================
# /AUTO_REPLY_REMOVE
# ============================================================

@bot.tree.command(
    name="auto_reply_remove",
    description="Remove automatic reply"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def auto_reply_remove(
    interaction: discord.Interaction,
    trigger: str
):

    gid = str(
        interaction.guild.id
    )

    await guild_settings.update_one(
        {
            "guildId": gid
        },
        {
            "$pull": {
                "autoReplies": {
                    "message": trigger
                }
            }
        }
    )

    settings_cache.pop(
        gid,
        None
    )

    await interaction.response.send_message(
        "✅ Auto-reply removed.",
        ephemeral=True
    )


# ============================================================
# /TICKET_PANEL
# ============================================================

@bot.tree.command(
    name="ticket_panel",
    description="Send the ticket panel"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def ticket_panel(
    interaction: discord.Interaction
):

    settings = await get_settings(
        interaction.guild.id
    )

    ticket = settings[
        "ticket"
    ]

    embed = discord.Embed(
        title="🎫 Support Ticket",
        description=(
            ticket.get(
                "message"
            )
            or
            "Press the button below to open a ticket."
        ),
        color=COLOR
    )

    if ticket.get(
        "image"
    ):

        embed.set_image(
            url=ticket["image"]
        )

    await interaction.channel.send(
        embed=embed,
        view=TicketView()
    )

    await interaction.response.send_message(
        "✅ Ticket panel sent.",
        ephemeral=True
    )


# ============================================================
# /RECORDS
# ============================================================

@bot.tree.command(
    name="records",
    description="View warning records"
)
@app_commands.default_permissions(
    manage_messages=True
)
async def records(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    member = (
        member
        or interaction.user
    )

    async with db.execute(
        """
        SELECT warns
        FROM warns
        WHERE guild_id=?
        AND user_id=?
        """,
        (
            str(interaction.guild.id),
            str(member.id)
        )
    ) as cursor:

        row = await cursor.fetchone()

    warnings = (
        row[0]
        if row
        else 0
    )

    embed = discord.Embed(
        title=f"📋 Records • {member.name}",
        description=(
            f"⚠️ Warnings: `{warnings}`"
        ),
        color=COLOR
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# ON READY
# ============================================================

@bot.event
async def on_ready():

    global _views_registered
    global _commands_synced
    global _background_started

    # ========================================================
    # SYNC SLASH COMMANDS
    # ========================================================

    if not _commands_synced:

        try:

            synced = await bot.tree.sync()

            print(
                f"✅ Synced {len(synced)} slash commands."
            )

        except Exception as e:

            print(
                "❌ Command sync error:",
                e
            )

        _commands_synced = True

    # ========================================================
    # PERSISTENT VIEWS
    # ========================================================

    if not _views_registered:

        try:

            bot.add_view(
                HelpView()
            )

            bot.add_view(
                TicketView()
            )

            bot.add_view(
                CloseTicketView()
            )

            _views_registered = True

        except Exception as e:

            print(
                "View registration error:",
                e
            )

    # ========================================================
    # BACKGROUND TASKS
    # ========================================================

    if not _background_started:

        asyncio.create_task(
            xp_loop()
        )

        asyncio.create_task(
            level_role_loop()
        )

        asyncio.create_task(
            check_expired_premiums()
        )

        asyncio.create_task(
            reset_leaderboards()
        )

        _background_started = True

    print(
        "=========================================="
    )

    print(
        f"🌙 Lunex logged in as {bot.user}"
    )

    print(
        f"🏠 Servers: {len(bot.guilds)}"
    )

    print(
        f"⭐ XP per message: {XP_PER_MESSAGE}"
    )

    print(
        f"📊 XP per level: {XP_PER_LEVEL}"
    )

    print(
        "=========================================="
    )


# ============================================================
# SHUTDOWN
# ============================================================

async def close_database():

    global db

    if db:

        try:

            await db.close()

        except Exception:
            pass

    try:

        mongo.close()

    except Exception:
        pass


# ============================================================
# MAIN
# ============================================================

async def main():

    await init_database()

    try:

        await bot.start(
            TOKEN
        )

    finally:

        await close_database()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        pass
