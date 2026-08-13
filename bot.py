# ============================================================
# LUNEX BOT — RAILWAY OPTIMIZED EDITION
# discord.py 2.x
# Motor (Async MongoDB) + aiosqlite
#
# Slash Commands:
# /me
# /profile
# /server
# /xp
# /level
# /language
# /commands
# /protection
# /badword
# /auto_reply
# /auto_reply_remove
# /ban
# /kick
# /unban
# /timeout
# /timeout_remove
# /lock
# /open
# /add_role
# /remove_role
# /nickname
#
# Prefix:
# !help
# !xp
# !level
# !t
# !clear
# !مسح
# !سجل
# ============================================================

import discord
from discord.ext import commands
from discord import app_commands

from datetime import timedelta, datetime, timezone

import asyncio
import aiosqlite
import time
import os
import re
import certifi

from motor.motor_asyncio import AsyncIOMotorClient


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

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

SITE_URL = os.getenv(
    "FRONTEND_URL",
    "https://lunexbot.netlify.app"
)

MONGODB_URI = os.getenv("MONGODB_URI")

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
    minPoolSize=1,
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
        "message": "اهلا [User] فيك بالسيرفر! [Img]",
    },

    "leave": {
        "enabled": False,
        "channelId": None,
        "message": "وداعا [User] :( [Img]",
    },

    "ticket": {
        "enabled": False,
        "image": "",
        "message": "اضغط الزر بالأسفل لفتح تكت جديد",
        "description": "مرحبا [User]، فريق الدعم راح يرد عليك قريبا",
        "categoryId": None,
        "channelId": None,
    },

    "autoReplies": [],

    "commandAliases": [],

    "protection": {
        "badwords": True,
        "links": True,
        "antispam": True,
    },

    "badwords": {},
}


# ============================================================
# CACHE
# ============================================================

settings_cache = {}

SETTINGS_CACHE_TTL = 300

badword_cache = {}

BADWORD_CACHE_TTL = 300


# ============================================================
# DEFAULT CLONING
# ============================================================

def clone_defaults():

    return {
        "welcome": DEFAULT_SETTINGS["welcome"].copy(),

        "leave": DEFAULT_SETTINGS["leave"].copy(),

        "ticket": DEFAULT_SETTINGS["ticket"].copy(),

        "autoReplies": [],

        "commandAliases": [],

        "protection": DEFAULT_SETTINGS["protection"].copy(),

        "badwords": {},
    }


# ============================================================
# MERGE SETTINGS
# ============================================================

def merge_settings(data):

    settings = clone_defaults()

    if not data:
        return settings

    for key in (
        "welcome",
        "leave",
        "ticket",
        "protection",
    ):

        if isinstance(data.get(key), dict):

            settings[key].update(
                data[key]
            )

    for key in (
        "autoReplies",
        "commandAliases",
    ):

        if isinstance(data.get(key), list):

            settings[key] = data[key]

    if isinstance(data.get("badwords"), dict):

        settings["badwords"] = data["badwords"]

    return settings


# ============================================================
# GET SETTINGS
# ============================================================

async def get_settings(guild_id: str):

    now = time.time()

    cached = settings_cache.get(guild_id)

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
                    **data,
                }
            },

            upsert=True,
        )

    else:

        data = merge_settings(doc)

    settings_cache[guild_id] = (
        now + SETTINGS_CACHE_TTL,
        data,
    )

    return data


# ============================================================
# UPDATE SETTINGS
# ============================================================

async def update_settings(
    guild_id: str,
    update: dict,
):

    await guild_settings.update_one(

        {
            "guildId": guild_id
        },

        {
            "$set": update,

            "$setOnInsert": {
                "guildId": guild_id
            },
        },

        upsert=True,
    )

    settings_cache.pop(
        guild_id,
        None,
    )

    return await get_settings(
        guild_id
    )


# ============================================================
# MESSAGE BUILDER
# ============================================================

def build_message(
    template: str,
    member: discord.Member,
):

    text = template or ""

    text = text.replace(
        "[User]",
        member.mention,
    )

    text = text.replace(
        "[user]",
        member.mention,
    )

    text = text.replace(
        "[Img]",
        "",
    )

    text = text.replace(
        "[img]",
        "",
    )

    text = text.replace(
        "[nember]",
        str(member.guild.member_count),
    )

    text = text.replace(
        "[member_count]",
        str(member.guild.member_count),
    )

    return text


# ============================================================
# DISCORD INTENTS
# ============================================================

intents = discord.Intents.default()

intents.members = True

intents.message_content = True

intents.guilds = True


bot = commands.Bot(

    command_prefix=[
        "!",
        "#",
    ],

    intents=intents,

    case_insensitive=True,

    help_command=None,
)


# ============================================================
# GLOBAL VARIABLES
# ============================================================

db = None

_views_registered = False

_commands_synced = False

_background_started = False


# ============================================================
# XP MEMORY CACHE
# ============================================================

xp_pending = {}


# ============================================================
# SPAM CACHE
# ============================================================

spam_cache = {}


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
            "Invalid time format (e.g. 10m, 1h).",

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
            "Error:",
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
            "صيغة الوقت غير صحيحة، مثال: 10m أو 1h.",

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
            "حدث خطأ:",
    },
}


# ============================================================
# DATABASE
# ============================================================

async def init_database():

    global db

    db = await aiosqlite.connect(
        "lunex.db"
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS xp(
            guild_id TEXT,
            user_id TEXT,
            messages INTEGER DEFAULT 0,
            day_count INTEGER DEFAULT 0,
            week_count INTEGER DEFAULT 0,
            month_count INTEGER DEFAULT 0,
            PRIMARY KEY(guild_id, user_id)
        )
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS warns(
            guild_id TEXT,
            user_id TEXT,
            warns INTEGER DEFAULT 0,
            PRIMARY KEY(guild_id, user_id)
        )
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS premium_users(
            user_id TEXT,
            guild_id TEXT,
            role_id TEXT,
            expiry_time REAL,
            PRIMARY KEY(user_id, guild_id)
        )
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_settings(
            user_id TEXT PRIMARY KEY,
            lang TEXT DEFAULT 'en'
        )
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS reset_tracker(
            id INTEGER PRIMARY KEY CHECK(id = 1),
            last_day TEXT,
            last_week TEXT,
            last_month TEXT
        )
        """
    )

    await db.commit()


# ============================================================
# LANGUAGE
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
        ),

    ) as cursor:

        row = await cursor.fetchone()

    if row and row[0] in locales:

        return row[0]

    return "en"


async def t(
    user_id: str,
    key: str,
    *args,
):

    lang = await get_lang(
        user_id
    )

    text = locales[lang].get(
        key,
        key,
    )

    if args:

        text = text.format(
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
# HIERARCHY CHECK
# ============================================================

async def check_hierarchy(
    interaction: discord.Interaction,
    member: discord.Member,
):

    uid = str(
        interaction.user.id
    )

    guild = interaction.guild

    if not guild:

        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True,
        )

        return False

    me = guild.me

    if not me:

        await interaction.response.send_message(
            "Bot member is unavailable.",
            ephemeral=True,
        )

        return False

    # لا يمكن تعديل صاحب السيرفر
    if member == guild.owner:

        await interaction.response.send_message(
            "You cannot moderate the server owner.",
            ephemeral=True,
        )

        return False

    # رتبة العضو أعلى أو مساوية للبوت
    if member.top_role >= me.top_role:

        await interaction.response.send_message(
            await t(
                uid,
                "higher_bot",
            ),
            ephemeral=True,
        )

        return False

    # رتبة العضو أعلى أو مساوية للمنفذ
    if (
        member.top_role >= interaction.user.top_role
        and interaction.user.id != guild.owner_id
    ):

        await interaction.response.send_message(
            await t(
                uid,
                "higher_user",
            ),
            ephemeral=True,
        )

        return False

    return True


# ============================================================
# XP MEMORY
# ============================================================

def add_xp_memory(
    guild_id,
    user_id,
):

    key = (
        str(guild_id),
        str(user_id),
    )

    if key not in xp_pending:

        xp_pending[key] = {

            "messages": 0,

            "day_count": 0,

            "week_count": 0,

            "month_count": 0,
        }

    xp_pending[key]["messages"] += 1

    xp_pending[key]["day_count"] += 1

    xp_pending[key]["week_count"] += 1

    xp_pending[key]["month_count"] += 1


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
            user_id,
        ), values in pending.items():

            await db.execute(

                """
                INSERT INTO xp (
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
                    values["month_count"],
                ),
            )

        await db.commit()

    except Exception as e:

        print(
            "XP flush error:",
            e,
        )

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
                e,
            )

        await asyncio.sleep(10)


# ============================================================
# PREMIUM EXPIRATION
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
                ),
            )

            await db.commit()

        except Exception as e:

            print(
                "Premium error:",
                e,
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
                        month,
                    ),
                )

            else:

                (
                    last_day,
                    last_week,
                    last_month,
                ) = row

                if last_day != today:

                    await db.execute(
                        "UPDATE xp SET day_count=0"
                    )

                if last_week != week:

                    await db.execute(
                        "UPDATE xp SET week_count=0"
                    )

                if last_month != month:

                    await db.execute(
                        "UPDATE xp SET month_count=0"
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
                        month,
                    ),
                )

            await db.commit()

        except Exception as e:

            print(
                "Reset error:",
                e,
            )

        await asyncio.sleep(3600)


# ============================================================
# BADWORDS
# ============================================================

async def load_badwords(
    guild_id,
):

    try:

        doc = await guild_settings.find_one(

            {
                "guildId": str(guild_id)
            },

            {
                "badwords": 1
            },
        )

        if not doc:

            return {}

        return doc.get(
            "badwords",
            {},
        )

    except Exception as e:

        print(
            "Load badwords error:",
            e,
        )

        return {}


async def get_badwords(
    guild_id,
):

    guild_id = str(
        guild_id
    )

    now = time.time()

    cached = badword_cache.get(
        guild_id
    )

    if cached:

        expires_at, data = cached

        if now < expires_at:

            return data

    data = await load_badwords(
        guild_id
    )

    badword_cache[guild_id] = (
        now + BADWORD_CACHE_TTL,
        data,
    )

    return data


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
        custom_id="lunex_close_ticket",
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await interaction.response.send_message(
            "Closing this ticket in 5 seconds..."
        )

        await asyncio.sleep(5)

        try:

            await interaction.channel.delete()

        except Exception as e:

            print(
                "Ticket delete error:",
                e,
            )


# ============================================================
# TICKET OPEN VIEW
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
        custom_id="lunex_open_ticket",
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        try:

            guild = interaction.guild

            if not guild:
                return

            settings = await get_settings(
                str(guild.id)
            )

            ticket = settings.get(
                "ticket",
                {},
            )

            raw_name = (
                f"ticket-{interaction.user.name}"
            ).lower()

            safe_name = re.sub(
                r"[^a-z0-9\-]",
                "",
                raw_name,
            )[:90]

            if not safe_name:

                safe_name = (
                    f"ticket-{interaction.user.id}"
                )

            existing = discord.utils.get(
                guild.text_channels,
                name=safe_name,
            )

            if existing:

                await interaction.response.send_message(

                    f"You already have an open ticket: "
                    f"{existing.mention}",

                    ephemeral=True,
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
                        read_message_history=True,
                    ),

                guild.me:
                    discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                    ),
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
            )

            description = build_message(

                ticket.get(
                    "description"
                )
                or
                "Hello [User], our support team will be with you shortly.",

                interaction.user,
            )

            embed = discord.Embed(

                title="Ticket",

                description=description,

                color=COLOR,
            )

            image = ticket.get(
                "image"
            )

            if image:

                embed.set_image(
                    url=image
                )

            await channel.send(

                embed=embed,

                view=CloseTicketView(),
            )

            await interaction.response.send_message(

                f"Your ticket has been opened: "
                f"{channel.mention}",

                ephemeral=True,
            )

        except Exception as e:

            print(
                "Open ticket error:",
                e,
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(

                    "Something went wrong opening your ticket.",

                    ephemeral=True,
                )


# ============================================================
# HELP SELECT
# ============================================================

class HelpSelect(
    discord.ui.Select
):

    def __init__(self):

        options = [

            discord.SelectOption(

                label="All member",

                description=(
                    "Member commands & XP"
                ),

                emoji="👥",
            ),

            discord.SelectOption(

                label="Staff member",

                description=(
                    "Administration and security commands"
                ),

                emoji="👑",
            ),
        ]

        super().__init__(

            placeholder="Select desired category",

            options=options,

            custom_id="help_select",
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):

        selected = self.values[0]

        if selected == "All member":

            embed = discord.Embed(

                title="👥 ALL MEMBER COMMANDS",

                description=(

                    "**Everything available to every member.**\n\n"

                    f"Visit us: {SITE_URL}"
                ),

                color=COLOR,
            )

            embed.add_field(

                name="⭐ XP & Leaderboards",

                value=(

                    "**/xp** — your XP\n"
                    "**/level** — your level\n"
                    "**!t** — monthly top 10\n"
                    "**!t day** — daily top 10\n"
                    "**!t week** — weekly top 10"
                ),

                inline=False,
            )

            embed.add_field(

                name="📌 Info",

                value=(

                    "**/me** — your profile\n"
                    "**/profile** `[member]` — avatar\n"
                    "**/server** — server info\n"
                    "**/language** — set language\n"
                    "**/commands** — commands"
                ),

                inline=False,
            )

        else:

            embed = discord.Embed(

                title="👑 STAFF MEMBER COMMANDS",

                description=(

                    "**Moderation, security, and "
                    "server management.**\n\n"

                    f"Visit us: {SITE_URL}"
                ),

                color=COLOR,
            )

            embed.add_field(

                name="🛡️ Moderation",

                value=(

                    "**/ban** | **/kick** | **/unban**\n"
                    "**/timeout** | **/timeout_remove**\n"
                    "**/lock** | **/open**\n"
                    "**!clear** / **!مسح**\n"
                    "**!سجل**"
                ),

                inline=False,
            )

            embed.add_field(

                name="⚙️ Management",

                value=(

                    "**/add_role** | **/remove_role**\n"
                    "**/nickname**\n"
                    "**/badword**\n"
                    "**/auto_reply**\n"
                    "**/protection**"
                ),

                inline=False,
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

            view=HelpView(),
        )


# ============================================================
# HELP VIEW
# ============================================================

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

                style=discord.ButtonStyle.link,
            )
        )

        self.add_item(

            discord.ui.Button(

                label="Support",

                emoji="💬",

                url=SUPPORT_INVITE,

                style=discord.ButtonStyle.link,
            )
        )

        self.add_item(

            discord.ui.Button(

                label="Website",

                emoji="🌐",

                url=SITE_URL,

                style=discord.ButtonStyle.link,
            )
        )


# ============================================================
# MAIN HELP EMBED
# ============================================================

def build_main_embed():

    embed = discord.Embed(

        title="🌙 LUNEX BOT",

        description=(

            "**Advanced, powerful, and simple "
            "server management.**\n\n"

            f"To learn more, visit us: {SITE_URL}"
        ),

        color=COLOR,
    )

    if bot.user:

        embed.set_thumbnail(
            url=bot.user.display_avatar.url
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
    member: discord.Member,
):

    try:

        settings = await get_settings(
            str(member.guild.id)
        )

        welcome = settings.get(
            "welcome",
            {},
        )

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

                member,
            ),

            color=COLOR,
        )

        embed.set_image(
            url=member.display_avatar.url
        )

        await channel.send(
            embed=embed
        )

    except Exception as e:

        print(
            "Welcome error:",
            e,
        )


# ============================================================
# LEAVE
# ============================================================

@bot.event
async def on_member_remove(
    member: discord.Member,
):

    try:

        settings = await get_settings(
            str(member.guild.id)
        )

        leave = settings.get(
            "leave",
            {},
        )

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

                member,
            ),

            color=COLOR,
        )

        embed.set_image(
            url=member.display_avatar.url
        )

        await channel.send(
            embed=embed
        )

    except Exception as e:

        print(
            "Leave error:",
            e,
        )


# ============================================================
# MESSAGE EVENT
# ============================================================

@bot.event
async def on_message(
    message: discord.Message,
):

    # تجاهل البوتات والرسائل خارج السيرفر
    if (
        message.author.bot
        or not message.guild
    ):

        return

    gid = str(
        message.guild.id
    )

    uid = str(
        message.author.id
    )

    # ========================================================
    # XP
    # ========================================================

    add_xp_memory(
        gid,
        uid,
    )

    # ========================================================
    # SETTINGS
    # ========================================================

    try:

        settings = await get_settings(
            gid
        )

    except Exception as e:

        print(
            "Settings error:",
            e,
        )

        settings = clone_defaults()

    protection = settings.get(
        "protection",
        {},
    )

    # ========================================================
    # COMMAND ALIASES
    # ========================================================

    try:

        content = message.content

        if content.startswith(
            (
                "!",
                "#",
            )
        ):

            prefix = content[0]

            rest = content[1:]

            first_word, separator, remainder = (
                rest.partition(" ")
            )

            if first_word:

                for alias_entry in settings.get(
                    "commandAliases",
                    [],
                ):

                    alias = str(
                        alias_entry.get(
                            "alias",
                            "",
                        )
                    ).lower()

                    if (
                        first_word.lower()
                        == alias
                    ):

                        original = alias_entry.get(
                            "original"
                        )

                        if original:

                            new_content = (
                                f"{prefix}{original}"
                            )

                            if separator:

                                new_content += (
                                    f" {remainder}"
                                )

                            message.content = (
                                new_content
                            )

                        break

    except Exception as e:

        print(
            "Alias error:",
            e,
        )

    # ========================================================
    # AUTO REPLY
    # ========================================================

    try:

        auto_replies = settings.get(
            "autoReplies",
            [],
        )

        if auto_replies:

            content_lower = (
                message.content
                .strip()
                .lower()
            )

            for reply_entry in auto_replies:

                trigger = str(
                    reply_entry.get(
                        "message",
                        "",
                    )
                ).strip().lower()

                if not trigger:

                    continue

                if trigger in content_lower:

                    reply = reply_entry.get(
                        "reply",
                        "",
                    )

                    if reply:

                        embed = discord.Embed(

                            description=reply,

                            color=COLOR,
                        )

                        await message.channel.send(
                            embed=embed
                        )

                    break

    except Exception as e:

        print(
            "Auto reply error:",
            e,
        )

    # ========================================================
    # ADMIN BYPASS
    # ========================================================

    if message.author.guild_permissions.administrator:

        await bot.process_commands(
            message
        )

        return

    # ========================================================
    # PROTECTION
    # ========================================================

    try:

        # ----------------------------------------------------
        # BADWORDS
        # ----------------------------------------------------

        if protection.get(
            "badwords",
            True,
        ):

            badwords = await get_badwords(
                gid
            )

            if badwords:

                content_lower = (
                    message.content.lower()
                )

                for word, seconds in badwords.items():

                    word = str(
                        word
                    ).strip()

                    if not word:

                        continue

                    pattern = (
                        r"(?<!\w)"
                        + re.escape(
                            word.lower()
                        )
                        + r"(?!\w)"
                    )

                    if re.search(
                        pattern,
                        content_lower,
                    ):

                        try:

                            await message.delete()

                            await message.author.timeout(

                                timedelta(
                                    seconds=int(
                                        seconds
                                    )
                                ),

                                reason="Forbidden word",
                            )

                            await message.channel.send(

                                f"⛔ "
                                f"{message.author.mention} "
                                f"has been timed out "
                                f"for using forbidden words.",

                                delete_after=5,
                            )

                        except Exception as e:

                            print(
                                "Badword action error:",
                                e,
                            )

                        break

        # ----------------------------------------------------
        # LINK PROTECTION
        # ----------------------------------------------------

        if protection.get(
            "links",
            True,
        ):

            content_lower = (
                message.content.lower()
            )

            if (
                "http://" in content_lower
                or "https://" in content_lower
                or "www." in content_lower
            ):

                try:

                    await message.delete()

                    await message.channel.send(

                        f"🚫 "
                        f"{message.author.mention} "
                        f"Links are not allowed "
                        f"in this server!",

                        delete_after=5,
                    )

                except Exception as e:

                    print(
                        "Link protection error:",
                        e,
                    )

        # ----------------------------------------------------
        # ANTI SPAM
        # ----------------------------------------------------

        if protection.get(
            "antispam",
            True,
        ):

            key = (
                gid,
                uid,
            )

            now = time.monotonic()

            history = spam_cache.get(
                key
            )

            if history is None:

                history = []

                spam_cache[key] = history

            history.append(
                now
            )

            cutoff = now - 3

            spam_cache[key] = [

                timestamp

                for timestamp in history

                if timestamp >= cutoff
            ]

            if len(
                spam_cache[key]
            ) >= 5:

                try:

                    await message.author.timeout(

                        timedelta(
                            minutes=10
                        ),

                        reason="Spamming",
                    )

                    await message.channel.send(

                        f"⏱ "
                        f"{message.author.mention} "
                        f"You have been timed out "
                        f"for spamming.",

                        delete_after=5,
                    )

                except Exception as e:

                    print(
                        "Spam error:",
                        e,
                    )

                spam_cache[key] = []

    except Exception as e:

        print(
            "Protection error:",
            e,
        )

    # ========================================================
    # PREFIX COMMANDS
    # ========================================================

    await bot.process_commands(
        message
    )


# ============================================================
# LANGUAGE
# ============================================================

@bot.tree.command(
    name="language",
    description="Set your personal language",
)
@app_commands.describe(
    lang="Choose your language"
)
@app_commands.choices(

    lang=[

        app_commands.Choice(
            name="English",
            value="en",
        ),

        app_commands.Choice(
            name="العربية",
            value="ar",
        ),
    ]
)
async def set_language(
    interaction: discord.Interaction,
    lang: str,
):

    uid = str(
        interaction.user.id
    )

    try:

        await db.execute(

            """
            INSERT INTO user_settings
            (user_id, lang)

            VALUES (?, ?)

            ON CONFLICT(user_id)

            DO UPDATE SET
                lang=excluded.lang
            """,

            (
                uid,
                lang,
            ),
        )

        await db.commit()

        await interaction.response.send_message(

            await t(
                uid,
                "lang_set",
            ),

            ephemeral=True,
        )

    except Exception as e:

        print(
            "Language error:",
            e,
        )

        await interaction.response.send_message(

            "❌ Failed to change language.",

            ephemeral=True,
        )


# ============================================================
# PROTECTION
# ============================================================

@bot.tree.command(
    name="protection",
    description="Configure server protection",
)
@app_commands.default_permissions(
    manage_guild=True
)
@app_commands.describe(
    feature="Protection feature",
    status="on or off",
)
async def protection_config(
    interaction: discord.Interaction,
    feature: str,
    status: str,
):

    feature = feature.lower().strip()

    status = status.lower().strip()

    allowed = {
        "badwords",
        "links",
        "antispam",
    }

    if feature not in allowed:

        await interaction.response.send_message(

            "❌ Available features: "
            "`badwords`, `links`, `antispam`",

            ephemeral=True,
        )

        return

    if status not in {
        "on",
        "off",
    }:

        await interaction.response.send_message(

            "❌ Status must be `on` or `off`.",

            ephemeral=True,
        )

        return

    enabled = (
        status == "on"
    )

    try:

        await update_settings(

            str(
                interaction.guild.id
            ),

            {
                f"protection.{feature}":
                    enabled
            },
        )

        await interaction.response.send_message(

            f"🛡️ `{feature}` ➜ `{status}`",

            ephemeral=True,
        )

    except Exception as e:

        print(
            "Protection config error:",
            e,
        )

        if not interaction.response.is_done():

            await interaction.response.send_message(

                "❌ Failed to update protection.",

                ephemeral=True,
            )


# ============================================================
# HELP
# ============================================================

@bot.command(
    name="help"
)
async def help_command(
    ctx
):

    await ctx.send(

        embed=build_main_embed(),

        view=HelpView(),
    )


# ============================================================
# COMMANDS
# ============================================================

@bot.tree.command(
    name="commands",
    description="Display Lunex commands",
)
async def commands_list(
    interaction: discord.Interaction,
):

    await interaction.response.send_message(

        embed=build_main_embed(),

        view=HelpView(),

        ephemeral=True,
    )


# ============================================================
# XP HELPER
# ============================================================

async def get_user_messages(
    guild_id: str,
    user_id: str,
):

    async with db.execute(

        """
        SELECT messages
        FROM xp
        WHERE guild_id=?
        AND user_id=?
        """,

        (
            guild_id,
            user_id,
        ),

    ) as cursor:

        row = await cursor.fetchone()

    pending = xp_pending.get(

        (
            guild_id,
            user_id,
        ),

        {},
    )

    messages = (

        (
            row[0]
            if row
            else 0
        )

        + pending.get(
            "messages",
            0,
        )
    )

    return messages


# ============================================================
# PREFIX XP
# ============================================================

@bot.command(
    name="xp"
)
async def xp(
    ctx
):

    guild_id = str(
        ctx.guild.id
    )

    user_id = str(
        ctx.author.id
    )

    messages = await get_user_messages(
        guild_id,
        user_id,
    )

    embed = discord.Embed(

        title="⭐ XP",

        description=f"`{messages}`",

        color=COLOR,
    )

    await ctx.send(
        embed=embed
    )


# ============================================================
# SLASH XP
# ============================================================

@bot.tree.command(
    name="xp",
    description="Check your XP",
)
async def slash_xp(
    interaction: discord.Interaction,
):

    if not interaction.guild:

        await interaction.response.send_message(

            "This command can only be used in a server.",

            ephemeral=True,
        )

        return

    messages = await get_user_messages(

        str(
            interaction.guild.id
        ),

        str(
            interaction.user.id
        ),
    )

    embed = discord.Embed(

        title="⭐ XP",

        description=f"`{messages}`",

        color=COLOR,
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# PREFIX LEVEL
# ============================================================

@bot.command(
    name="level"
)
async def level(
    ctx
):

    guild_id = str(
        ctx.guild.id
    )

    user_id = str(
        ctx.author.id
    )

    messages = await get_user_messages(

        guild_id,

        user_id,
    )

    current_level = (
        messages // 50
    )

    embed = discord.Embed(

        title="📊 LEVEL",

        description=f"`{current_level}`",

        color=COLOR,
    )

    await ctx.send(
        embed=embed
    )


# ============================================================
# SLASH LEVEL
# ============================================================

@bot.tree.command(
    name="level",
    description="Check your level",
)
async def slash_level(
    interaction: discord.Interaction,
):

    if not interaction.guild:

        await interaction.response.send_message(

            "This command can only be used in a server.",

            ephemeral=True,
        )

        return

    messages = await get_user_messages(

        str(
            interaction.guild.id
        ),

        str(
            interaction.user.id
        ),
    )

    current_level = (
        messages // 50
    )

    embed = discord.Embed(

        title="📊 LEVEL",

        description=f"`{current_level}`",

        color=COLOR,
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /ME
# بدل !i
# ============================================================

@bot.tree.command(
    name="me",
    description="View your profile",
)
@app_commands.describe(
    member="Optional member"
)
async def me(
    interaction: discord.Interaction,
    member: discord.Member = None,
):

    if not interaction.guild:

        await interaction.response.send_message(

            "This command can only be used in a server.",

            ephemeral=True,
        )

        return

    member = (
        member
        or interaction.user
    )

    messages = await get_user_messages(

        str(
            interaction.guild.id
        ),

        str(
            member.id
        ),
    )

    level_value = (
        messages // 50
    )

    embed = discord.Embed(

        title=f"Profile: {member.name}",

        color=COLOR,
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.add_field(

        name="⭐ XP",

        value=f"`{messages}`",

        inline=True,
    )

    embed.add_field(

        name="📊 Level",

        value=f"`{level_value}`",

        inline=True,
    )

    embed.add_field(

        name="👑 Top Role",

        value=member.top_role.mention,

        inline=True,
    )

    embed.add_field(

        name="🆔 User ID",

        value=f"`{member.id}`",

        inline=False,
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /PROFILE
# بدل !افاتار
# ============================================================

@bot.tree.command(
    name="profile",
    description="View a member's avatar",
)
@app_commands.describe(
    member="Select a member"
)
async def profile(
    interaction: discord.Interaction,
    member: discord.Member = None,
):

    member = (
        member
        or interaction.user
    )

    embed = discord.Embed(

        title=f"Avatar: {member.name}",

        color=COLOR,
    )

    embed.set_image(
        url=member.display_avatar.url
    )

    embed.set_footer(
        text=f"Lunex • {member.id}"
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /SERVER
# بدل !سيرفر
# ============================================================

@bot.tree.command(
    name="server",
    description="View server information",
)
async def server(
    interaction: discord.Interaction,
):

    guild = interaction.guild

    if not guild:

        await interaction.response.send_message(

            "This command can only be used inside a server.",

            ephemeral=True,
        )

        return

    bots_count = sum(

        1

        for member in guild.members

        if member.bot
    )

    humans_count = (

        guild.member_count - bots_count

        if guild.member_count

        else 0
    )

    embed = discord.Embed(

        title=f"🖥 {guild.name}",

        color=COLOR,
    )

    if guild.icon:

        embed.set_thumbnail(
            url=guild.icon.url
        )

    embed.add_field(

        name="👥 Members",

        value=f"`{guild.member_count}`",

        inline=True,
    )

    embed.add_field(

        name="👤 Humans",

        value=f"`{humans_count}`",

        inline=True,
    )

    embed.add_field(

        name="🤖 Bots",

        value=f"`{bots_count}`",

        inline=True,
    )

    embed.add_field(

        name="💬 Channels",

        value=f"`{len(guild.channels)}`",

        inline=True,
    )

    embed.add_field(

        name="🎭 Roles",

        value=f"`{len(guild.roles)}`",

        inline=True,
    )

    embed.add_field(

        name="📅 Created",

        value=(
            f"`{guild.created_at.strftime('%Y-%m-%d')}`"
        ),

        inline=True,
    )

    if guild.owner:

        embed.add_field(

            name="👑 Owner",

            value=guild.owner.mention,

            inline=True,
        )

    embed.set_footer(

        text=f"Lunex • Server ID: {guild.id}"
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# LEADERBOARD
# ============================================================

@bot.command(
    name="t"
)
async def top_command(
    ctx,
    mode: str = None,
):

    gid = str(
        ctx.guild.id
    )

    if mode:

        mode = mode.lower().strip()

    if mode == "day":

        column = "day_count"

        title = "🏆 Daily Top"

    elif mode == "week":

        column = "week_count"

        title = "🏆 Weekly Top"

    else:

        column = "month_count"

        title = "🏆 Monthly Top"

    await flush_xp()

    query = f"""

        SELECT
            user_id,
            {column}

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
        ),

    ) as cursor:

        rows = await cursor.fetchall()

    embed = discord.Embed(

        title=title,

        color=COLOR,
    )

    if not rows:

        embed.description = (
            "No data yet."
        )

    else:

        for index, (
            user_id,
            count,
        ) in enumerate(

            rows,

            start=1,
        ):

            embed.add_field(

                name=(
                    f"{index}. <@{user_id}>"
                ),

                value=(
                    f"💬 {count} messages"
                ),

                inline=False,
            )

    await ctx.send(
        embed=embed
    )


# ============================================================
# RECORDS
# ============================================================

@bot.command(
    name="سجل"
)
@commands.has_permissions(
    manage_messages=True
)
async def records_command(
    ctx,
    member: discord.Member = None,
):

    member = (
        member
        or ctx.author
    )

    async with db.execute(

        """
        SELECT warns
        FROM warns
        WHERE guild_id=?
        AND user_id=?
        """,

        (
            str(ctx.guild.id),
            str(member.id),
        ),

    ) as cursor:

        row = await cursor.fetchone()

    warnings = (
        row[0]
        if row
        else 0
    )

    embed = discord.Embed(

        title=(
            f"📋 Records for {member.name}"
        ),

        description=(
            f"⚠️ Warnings: {warnings}"
        ),

        color=COLOR,
    )

    await ctx.send(
        embed=embed
    )


# ============================================================
# CLEAR
# ============================================================

@bot.command(
    name="clear",
    aliases=["مسح"],
)
@commands.has_permissions(
    manage_messages=True
)
async def clear(
    ctx,
    amount: int,
):

    if amount <= 0:
        return

    if amount > 100:

        amount = 100

    uid = str(
        ctx.author.id
    )

    await ctx.channel.purge(
        limit=amount + 1
    )

    msg = await ctx.send(

        await t(
            uid,
            "cleared",
            amount,
        )
    )

    await asyncio.sleep(3)

    try:

        await msg.delete()

    except Exception:

        pass


# ============================================================
# BAN
# ============================================================

@bot.tree.command(
    name="ban",
    description="Ban a member",
)
@app_commands.default_permissions(
    ban_members=True
)
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
):

    if not await check_hierarchy(
        interaction,
        member,
    ):

        return

    try:

        await member.ban(

            reason=(
                f"Banned by {interaction.user}"
            )
        )

        await interaction.response.send_message(

            await t(
                str(
                    interaction.user.id
                ),
                "banned",
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(

            "❌ I don't have permission to ban this member.",

            ephemeral=True,
        )


# ============================================================
# KICK
# ============================================================

@bot.tree.command(
    name="kick",
    description="Kick a member",
)
@app_commands.default_permissions(
    kick_members=True
)
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
):

    if not await check_hierarchy(
        interaction,
        member,
    ):

        return

    try:

        await member.kick(

            reason=(
                f"Kicked by {interaction.user}"
            )
        )

        await interaction.response.send_message(

            await t(
                str(
                    interaction.user.id
                ),
                "kicked",
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(

            "❌ I don't have permission to kick this member.",

            ephemeral=True,
        )


# ============================================================
# UNBAN
# ============================================================

@bot.tree.command(
    name="unban",
    description="Unban a user by ID",
)
@app_commands.default_permissions(
    ban_members=True
)
async def unban(
    interaction: discord.Interaction,
    user_id: str,
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
                "unbanned",
            )
        )

    except Exception as e:

        await interaction.response.send_message(

            f"{await t(uid, 'error')} `{e}`",

            ephemeral=True,
        )


# ============================================================
# LOCK
# ============================================================

@bot.tree.command(
    name="lock",
    description="Lock channel",
)
@app_commands.default_permissions(
    manage_channels=True
)
async def lock_slash(
    interaction: discord.Interaction,
):

    overwrite = (
        interaction.channel.overwrites_for(
            interaction.guild.default_role
        )
    )

    overwrite.send_messages = False

    await interaction.channel.set_permissions(

        interaction.guild.default_role,

        overwrite=overwrite,
    )

    await interaction.response.send_message(

        await t(
            str(
                interaction.user.id
            ),
            "channel_locked",
        )
    )


# ============================================================
# OPEN
# ============================================================

@bot.tree.command(
    name="open",
    description="Unlock channel",
)
@app_commands.default_permissions(
    manage_channels=True
)
async def open_slash(
    interaction: discord.Interaction,
):

    overwrite = (
        interaction.channel.overwrites_for(
            interaction.guild.default_role
        )
    )

    overwrite.send_messages = True

    await interaction.channel.set_permissions(

        interaction.guild.default_role,

        overwrite=overwrite,
    )

    await interaction.response.send_message(

        await t(
            str(
                interaction.user.id
            ),
            "channel_unlocked",
        )
    )


# ============================================================
# TIMEOUT
# ============================================================

@bot.tree.command(
    name="timeout",
    description="Timeout a member",
)
@app_commands.default_permissions(
    moderate_members=True
)
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    time: str,
):

    uid = str(
        interaction.user.id
    )

    if not await check_hierarchy(
        interaction,
        member,
    ):

        return

    seconds = parse_time(
        time
    )

    if not seconds:

        await interaction.response.send_message(

            await t(
                uid,
                "invalid_time",
            ),

            ephemeral=True,
        )

        return

    # Discord timeout maximum is 28 days
    if seconds > 28 * 86400:

        await interaction.response.send_message(

            "❌ Timeout cannot be longer than 28 days.",

            ephemeral=True,
        )

        return

    try:

        await member.timeout(

            timedelta(
                seconds=seconds
            ),

            reason=(
                f"Timeout by {interaction.user}"
            ),
        )

        await interaction.response.send_message(

            await t(
                uid,
                "timeout_applied",
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(

            "❌ I don't have permission to timeout this member.",

            ephemeral=True,
        )


# ============================================================
# REMOVE TIMEOUT
# ============================================================

@bot.tree.command(
    name="timeout_remove",
    description="Remove timeout",
)
@app_commands.default_permissions(
    moderate_members=True
)
async def timeout_remove(
    interaction: discord.Interaction,
    member: discord.Member,
):

    uid = str(
        interaction.user.id
    )

    if not await check_hierarchy(
        interaction,
        member,
    ):

        return

    try:

        await member.timeout(
            None
        )

        await interaction.response.send_message(

            await t(
                uid,
                "timeout_removed",
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(

            "❌ I don't have permission to remove the timeout.",

            ephemeral=True,
        )


# ============================================================
# ADD ROLE
# ============================================================

@bot.tree.command(
    name="add_role",
    description="Add a role",
)
@app_commands.default_permissions(
    manage_roles=True
)
async def add_role(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role,
):

    if not await check_hierarchy(
        interaction,
        member,
    ):

        return

    if role >= interaction.guild.me.top_role:

        await interaction.response.send_message(

            "That role is higher than or equal to my role.",

            ephemeral=True,
        )

        return

    if (
        role >= interaction.user.top_role
        and interaction.user.id != interaction.guild.owner_id
    ):

        await interaction.response.send_message(

            "That role is higher than or equal to your role.",

            ephemeral=True,
        )

        return

    try:

        await member.add_roles(

            role,

            reason=(
                f"Role added by {interaction.user}"
            ),
        )

        await interaction.response.send_message(

            await t(
                str(
                    interaction.user.id
                ),
                "role_added",
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(

            "❌ I don't have permission to add this role.",

            ephemeral=True,
        )


# ============================================================
# REMOVE ROLE
# ============================================================

@bot.tree.command(
    name="remove_role",
    description="Remove a role",
)
@app_commands.default_permissions(
    manage_roles=True
)
async def remove_role(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role,
):

    if not await check_hierarchy(
        interaction,
        member,
    ):

        return

    if role >= interaction.guild.me.top_role:

        await interaction.response.send_message(

            "That role is higher than or equal to my role.",

            ephemeral=True,
        )

        return

    if (
        role >= interaction.user.top_role
        and interaction.user.id != interaction.guild.owner_id
    ):

        await interaction.response.send_message(

            "That role is higher than or equal to your role.",

            ephemeral=True,
        )

        return

    try:

        await member.remove_roles(

            role,

            reason=(
                f"Role removed by {interaction.user}"
            ),
        )

        await interaction.response.send_message(

            await t(
                str(
                    interaction.user.id
                ),
                "role_removed",
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(

            "❌ I don't have permission to remove this role.",

            ephemeral=True,
        )


# ============================================================
# NICKNAME
# ============================================================

@bot.tree.command(
    name="nickname",
    description="Change a member nickname",
)
@app_commands.describe(
    member="Select member",
    nickname="New nickname",
)
@app_commands.default_permissions(
    manage_nicknames=True
)
async def nickname(
    interaction: discord.Interaction,
    member: discord.Member,
    nickname: str = None,
):

    uid = str(
        interaction.user.id
    )

    if not await check_hierarchy(
        interaction,
        member,
    ):

        return

    try:

        await member.edit(

            nick=nickname,

            reason=(
                f"Nickname changed by {interaction.user}"
            ),
        )

        await interaction.response.send_message(

            await t(
                uid,
                "nick_changed",
            )
        )

    except Exception as e:

        await interaction.response.send_message(

            f"{await t(uid, 'error')} `{e}`",

            ephemeral=True,
        )


# ============================================================
# BADWORD
# ============================================================

@bot.tree.command(
    name="badword",
    description="Add a banned word",
)
@app_commands.default_permissions(
    manage_guild=True
)
@app_commands.describe(
    word="Word to block",
    time="Timeout duration, e.g. 10m or 1h",
)
async def badword(
    interaction: discord.Interaction,
    word: str,
    time: str,
):

    uid = str(
        interaction.user.id
    )

    seconds = parse_time(
        time
    )

    if not seconds:

        await interaction.response.send_message(

            await t(
                uid,
                "invalid_time",
            ),

            ephemeral=True,
        )

        return

    word = word.strip().lower()

    if not word:

        await interaction.response.send_message(

            "❌ Invalid word.",

            ephemeral=True,
        )

        return

    gid = str(
        interaction.guild.id
    )

    try:

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
                },
            },

            upsert=True,
        )

        badword_cache.pop(
            gid,
            None,
        )

        settings_cache.pop(
            gid,
            None,
        )

        await interaction.response.send_message(

            f"✅ Added `{word}`.",

            ephemeral=True,
        )

    except Exception as e:

        print(
            "Badword error:",
            e,
        )

        await interaction.response.send_message(

            "❌ Failed to add bad word.",

            ephemeral=True,
        )


# ============================================================
# AUTO REPLY
# ============================================================

@bot.tree.command(
    name="auto_reply",
    description="Add automatic reply",
)
@app_commands.default_permissions(
    manage_guild=True
)
@app_commands.describe(
    trigger="Trigger message",
    reply="Automatic reply",
)
async def auto_reply(
    interaction: discord.Interaction,
    trigger: str,
    reply: str,
):

    trigger = trigger.strip()

    reply = reply.strip()

    if not trigger or not reply:

        await interaction.response.send_message(

            "❌ Trigger and reply cannot be empty.",

            ephemeral=True,
        )

        return

    gid = str(
        interaction.guild.id
    )

    try:

        await guild_settings.update_one(

            {
                "guildId": gid
            },

            {
                "$push": {

                    "autoReplies": {

                        "message": trigger,

                        "reply": reply,
                    }
                },

                "$setOnInsert": {

                    "guildId": gid
                },
            },

            upsert=True,
        )

        settings_cache.pop(
            gid,
            None,
        )

        await interaction.response.send_message(

            f"✅ Auto-reply added for `{trigger}`.",

            ephemeral=True,
        )

    except Exception as e:

        print(
            "Auto reply error:",
            e,
        )

        await interaction.response.send_message(

            "❌ Failed to add auto-reply.",

            ephemeral=True,
        )


# ============================================================
# REMOVE AUTO REPLY
# ============================================================

@bot.tree.command(
    name="auto_reply_remove",
    description="Remove an automatic reply",
)
@app_commands.default_permissions(
    manage_guild=True
)
@app_commands.describe(
    trigger="Trigger message to remove",
)
async def auto_reply_remove(
    interaction: discord.Interaction,
    trigger: str,
):

    gid = str(
        interaction.guild.id
    )

    try:

        result = await guild_settings.update_one(

            {
                "guildId": gid
            },

            {
                "$pull": {

                    "autoReplies": {

                        "message": trigger
                    }
                }
            },
        )

        settings_cache.pop(
            gid,
            None,
        )

        if result.modified_count == 0:

            await interaction.response.send_message(

                "⚠️ Auto-reply not found.",

                ephemeral=True,
            )

            return

        await interaction.response.send_message(

            "✅ Auto-reply deleted.",

            ephemeral=True,
        )

    except Exception as e:

        print(
            "Auto reply remove error:",
            e,
        )

        await interaction.response.send_message(

            "❌ Failed to remove auto-reply.",

            ephemeral=True,
        )


# ============================================================
# POST TICKET PANEL
# ============================================================

async def post_ticket_panel(
    guild_id: str,
    channel_id: str,
):

    guild = bot.get_guild(
        int(guild_id)
    )

    if not guild:

        raise ValueError(
            "Bot is not in this server"
        )

    channel = guild.get_channel(
        int(channel_id)
    )

    if not channel:

        raise ValueError(
            "Channel not found"
        )

    settings = await get_settings(
        str(guild_id)
    )

    ticket = settings.get(
        "ticket",
        {},
    )

    embed = discord.Embed(

        title="Ticket",

        description=(

            ticket.get(
                "message"
            )

            or

            "Click the button below to open a new ticket."
        ),

        color=COLOR,
    )

    image = ticket.get(
        "image"
    )

    if image:

        embed.set_image(
            url=image
        )

    await channel.send(

        embed=embed,

        view=TicketView(),
    )


# ============================================================
# BOT COMMAND ERROR
# ============================================================

@bot.event
async def on_command_error(
    ctx,
    error,
):

    if isinstance(
        error,
        commands.CommandNotFound,
    ):

        return

    if isinstance(
        error,
        commands.MissingPermissions,
    ):

        await ctx.send(

            "❌ You don't have permission to use this command.",

            delete_after=5,
        )

        return

    if isinstance(
        error,
        commands.MissingRequiredArgument,
    ):

        await ctx.send(

            "❌ Missing required argument.",

            delete_after=5,
        )

        return

    if isinstance(
        error,
        commands.BadArgument,
    ):

        await ctx.send(

            "❌ Invalid argument.",

            delete_after=5,
        )

        return

    print(
        "Command error:",
        repr(error),
    )


# ============================================================
# SLASH ERROR HANDLER
# ============================================================

async def slash_error_handler(
    interaction: discord.Interaction,
    error,
):

    print(
        "Slash command error:",
        repr(error),
    )

    try:

        message = (
            "❌ An error occurred."
        )

        if interaction.response.is_done():

            await interaction.followup.send(

                message,

                ephemeral=True,
            )

        else:

            await interaction.response.send_message(

                message,

                ephemeral=True,
            )

    except Exception as e:

        print(
            "Slash error handler:",
            e,
        )


# ============================================================
# READY
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
                f"✅ Synced {len(synced)} slash command(s)"
            )

            _commands_synced = True

        except Exception as e:

            print(
                "❌ Command sync error:",
                e,
            )

    # ========================================================
    # REGISTER PERSISTENT VIEWS
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

            print(
                "✅ Persistent views registered"
            )

        except Exception as e:

            print(
                "❌ View registration error:",
                e,
            )

    # ========================================================
    # BACKGROUND TASKS
    # ========================================================

    if not _background_started:

        asyncio.create_task(
            xp_loop()
        )

        asyncio.create_task(
            check_expired_premiums()
        )

        asyncio.create_task(
            reset_leaderboards()
        )

        _background_started = True

        print(
            "✅ Background tasks started"
        )

    # ========================================================
    # READY LOG
    # ========================================================

    print(
        "=" * 50
    )

    print(
        f"✅ Lunex Bot Logged in as {bot.user}"
    )

    print(
        f"🆔 Bot ID: {bot.user.id}"
    )

    print(
        f"🏠 Servers: {len(bot.guilds)}"
    )

    print(
        "🚀 Lunex is ready!"
    )

    print(
        "=" * 50
    )


# ============================================================
# STARTUP
# ============================================================

async def main():

    print(
        "🚀 Starting Lunex Bot..."
    )

    await init_database()

    print(
        "✅ SQLite database initialized"
    )

    try:

        await bot.start(
            TOKEN
        )

    finally:

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
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "🛑 Lunex Bot stopped."
        )

    except Exception as e:

        print(
            "❌ Fatal error:",
            repr(e)
        )
