# =========================================================
# LUNEX BOT — FULL RAILWAY EDITION
# discord.py 2.x
# MongoDB Motor Async + SQLite
# =========================================================

import os
import re
import time
import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from discord import app_commands

import aiosqlite
import certifi
from motor.motor_asyncio import AsyncIOMotorClient


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")

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

mongo = AsyncIOMotorClient(
    MONGODB_URI,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
    socketTimeoutMS=10000,
    maxPoolSize=20,
    minPoolSize=1
)

mdb = mongo.get_default_database()

guild_settings = mdb["guildsettings"]


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

        "welcome": DEFAULT_SETTINGS["welcome"].copy(),

        "leave": DEFAULT_SETTINGS["leave"].copy(),

        "ticket": DEFAULT_SETTINGS["ticket"].copy(),

        "autoReplies": [],

        "commandAliases": [],

        "protection": DEFAULT_SETTINGS["protection"].copy(),

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

    settings["guildId"] = data.get(
        "guildId"
    )

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

    else:

        data = merge_settings(
            doc
        )

        data["guildId"] = guild_id

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
        "[Img]",
        ""
    )

    text = text.replace(
        "[img]",
        ""
    )

    text = text.replace(
        "[nember]",
        str(
            member.guild.member_count
        )
    )

    text = text.replace(
        "[member_count]",
        str(
            member.guild.member_count
        )
    )

    return text


# =========================================================
# INTENTS
# =========================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.message_content = True


# =========================================================
# BOT
# =========================================================

class LunexBot(
    commands.Bot
):

    async def setup_hook(self):

        print(
            "🔄 Syncing slash commands..."
        )

        try:

            synced = await self.tree.sync()

            print(
                f"✅ Synced {len(synced)} slash commands."
            )

        except Exception as e:

            print(
                "❌ Slash command sync error:",
                repr(e)
            )

        self.add_view(
            HelpView()
        )

        self.add_view(
            TicketView()
        )

        self.add_view(
            CloseTicketView()
        )


bot = LunexBot(
    command_prefix=["!", "#"],
    intents=intents,
    case_insensitive=True,
    help_command=None
)


# =========================================================
# GLOBAL
# =========================================================

db = None

xp_pending = {}

spam_cache = {}


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
            "❌ Invalid time format. Example: `10m`, `1h`.",

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

        "registered":
            "✅ You have been registered successfully.",

        "error":
            "❌ Error:"
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
            "❌ صيغة الوقت غير صحيحة. مثال: `10m` أو `1h`.",

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

        "registered":
            "✅ تم تسجيلك بنجاح.",

        "error":
            "❌ حدث خطأ:"
    }
}


# =========================================================
# LANGUAGE FUNCTIONS
# =========================================================

async def get_lang(
    user_id
):

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
    user_id,
    key,
    *args
):

    lang = await get_lang(
        user_id
    )

    text = locales[
        lang
    ].get(
        key,
        key
    )

    if args:
        return text.format(
            *args
        )

    return text


# =========================================================
# SQLITE
# =========================================================

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
            id INTEGER PRIMARY KEY CHECK(id=1),
            last_day TEXT,
            last_week TEXT,
            last_month TEXT
        )
        """
    )

    await db.commit()

    print(
        "✅ SQLite database ready."
    )


# =========================================================
# TIME PARSER
# =========================================================

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


# =========================================================
# HIERARCHY
# =========================================================

async def check_hierarchy(
    interaction,
    member
):

    me = interaction.guild.me

    if not me:

        await interaction.response.send_message(
            "Bot member is unavailable.",
            ephemeral=True
        )

        return False

    if member == interaction.guild.owner:

        await interaction.response.send_message(
            "You cannot moderate the server owner.",
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
        != interaction.guild.owner_id
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
# HELP
# =========================================================

def build_main_embed():

    embed = discord.Embed(
        title="🌙 LUNEX BOT",
        description=(
            "Advanced, powerful and simple "
            "server management.\n\n"
            f"🌐 Website: {SITE_URL}\n"
            "📌 Select a category below."
        ),
        color=COLOR
    )

    if bot.user:

        embed.set_thumbnail(
            url=bot.user.display_avatar.url
        )

    embed.add_field(
        name="👥 Member Commands",
        value=(
            "`/xp` — XP\n"
            "`/level` — Level\n"
            "`/top` — Monthly top\n"
            "`/top_day` — Daily top\n"
            "`/top_week` — Weekly top\n"
            "`/me` — Your profile\n"
            "`/profile` — Member profile\n"
            "`/server` — Server information"
        ),
        inline=False
    )

    embed.add_field(
        name="⚙️ General",
        value=(
            "`/commands`\n"
            "`/language`\n"
            "`/register`"
        ),
        inline=False
    )

    embed.add_field(
        name="🛡️ Moderation",
        value=(
            "`/clear`\n"
            "`/ban`\n"
            "`/kick`\n"
            "`/timeout`\n"
            "`/lock`"
        ),
        inline=False
    )

    embed.set_footer(
        text="Lunex • More than a bot"
    )

    return embed


class HelpSelect(
    discord.ui.Select
):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="All Member",
                value="member",
                description="Member commands",
                emoji="👥"
            ),

            discord.SelectOption(
                label="Staff",
                value="staff",
                description="Moderation commands",
                emoji="👑"
            )
        ]

        super().__init__(
            placeholder="Select a category...",
            options=options,
            custom_id="lunex_help_select"
        )

    async def callback(
        self,
        interaction
    ):

        if self.values[0] == "member":

            embed = discord.Embed(
                title="👥 MEMBER COMMANDS",
                description=(
                    "Commands available to members."
                ),
                color=COLOR
            )

            embed.add_field(
                name="⭐ XP",
                value=(
                    "`/xp`\n"
                    "`/level`\n"
                    "`/top`\n"
                    "`/top_day`\n"
                    "`/top_week`"
                ),
                inline=False
            )

            embed.add_field(
                name="📌 Information",
                value=(
                    "`/me`\n"
                    "`/profile`\n"
                    "`/server`\n"
                    "`/register`\n"
                    "`/language`"
                ),
                inline=False
            )

        else:

            embed = discord.Embed(
                title="👑 STAFF COMMANDS",
                description=(
                    "Administration and moderation."
                ),
                color=COLOR
            )

            embed.add_field(
                name="🛡️ Moderation",
                value=(
                    "`/clear`\n"
                    "`/ban`\n"
                    "`/kick`\n"
                    "`/unban`\n"
                    "`/timeout`\n"
                    "`/timeout_remove`\n"
                    "`/lock`\n"
                    "`/open`"
                ),
                inline=False
            )

            embed.add_field(
                name="⚙️ Management",
                value=(
                    "`/add_role`\n"
                    "`/remove_role`\n"
                    "`/nickname`\n"
                    "`/badword`\n"
                    "`/protection`"
                ),
                inline=False
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
# TICKET
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

        await interaction.response.send_message(
            "Closing ticket in 5 seconds..."
        )

        await asyncio.sleep(5)

        try:

            await interaction.channel.delete()

        except Exception as e:

            print(
                "Ticket delete error:",
                e
            )


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
            return

        try:

            settings = await get_settings(
                guild.id
            )

            ticket = settings[
                "ticket"
            ]

            name = (
                f"ticket-{interaction.user.id}"
            )

            existing = discord.utils.get(
                guild.text_channels,
                name=name
            )

            if existing:

                await interaction.response.send_message(
                    f"❌ You already have a ticket: "
                    f"{existing.mention}",
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
                        int(
                            ticket[
                                "categoryId"
                            ]
                        )
                    )

                except Exception:

                    category = None

            channel = await guild.create_text_channel(
                name,
                overwrites=overwrites,
                category=category
            )

            description = build_message(
                ticket.get(
                    "description"
                ),
                interaction.user
            )

            embed = discord.Embed(
                title="🎫 Ticket",
                description=description,
                color=COLOR
            )

            if ticket.get(
                "image"
            ):

                embed.set_image(
                    url=ticket["image"]
                )

            await channel.send(
                embed=embed,
                view=CloseTicketView()
            )

            await interaction.response.send_message(
                f"✅ Ticket opened: {channel.mention}",
                ephemeral=True
            )

        except Exception as e:

            print(
                "Ticket error:",
                e
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Could not open ticket.",
                    ephemeral=True
                )


# =========================================================
# XP MEMORY
# =========================================================

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
                INSERT INTO xp
                (
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


# =========================================================
# GET XP
# =========================================================

async def get_user_xp(
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

    messages = (
        row[0]
        if row
        else 0
    )

    messages += pending.get(
        "messages",
        0
    )

    return messages


# =========================================================
# LEADERBOARD
# =========================================================

async def send_top(
    interaction_or_ctx,
    mode="month"
):

    await flush_xp()

    gid = str(
        interaction_or_ctx.guild.id
    )

    if mode == "day":

        column = "day_count"
        title = "🏆 DAILY TOP"

    elif mode == "week":

        column = "week_count"
        title = "🏆 WEEKLY TOP"

    else:

        column = "month_count"
        title = "🏆 MONTHLY TOP"

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
                else f"**{index}.**"
            )

            lines.append(
                f"{medal} <@{user_id}> — "
                f"`{count}` messages"
            )

        embed.description = "\n".join(
            lines
        )

    if isinstance(
        interaction_or_ctx,
        discord.Interaction
    ):

        await interaction_or_ctx.response.send_message(
            embed=embed
        )

    else:

        await interaction_or_ctx.send(
            embed=embed
        )


# =========================================================
# /COMMANDS
# =========================================================

@bot.tree.command(
    name="commands",
    description="Display all Lunex commands"
)
async def commands_command(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        embed=build_main_embed(),
        view=HelpView(),
        ephemeral=True
    )


# =========================================================
# !HELP
# =========================================================

@bot.command(
    name="help"
)
async def help_command(
    ctx
):

    await ctx.send(
        embed=build_main_embed(),
        view=HelpView()
    )


# =========================================================
# /LANGUAGE
# =========================================================

@bot.tree.command(
    name="language",
    description="Choose your personal language"
)
@app_commands.describe(
    language="Choose English or Arabic"
)
@app_commands.choices(
    language=[
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
async def language_command(
    interaction: discord.Interaction,
    language: app_commands.Choice[str]
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
            language.value
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


# =========================================================
# /REGISTER
# =========================================================

@bot.tree.command(
    name="register",
    description="Register yourself in Lunex"
)
async def register_command(
    interaction: discord.Interaction
):

    uid = str(
        interaction.user.id
    )

    await db.execute(
        """
        INSERT OR IGNORE INTO user_settings(
            user_id,
            lang
        )
        VALUES (?, 'en')
        """,
        (
            uid,
        )
    )

    await db.execute(
        """
        INSERT OR IGNORE INTO xp(
            guild_id,
            user_id
        )
        VALUES (?, ?)
        """,
        (
            str(
                interaction.guild.id
            ),
            uid
        )
    )

    await db.commit()

    await interaction.response.send_message(
        await t(
            uid,
            "registered"
        ),
        ephemeral=True
    )


# =========================================================
# /XP
# =========================================================

@bot.tree.command(
    name="xp",
    description="Check your XP"
)
async def slash_xp(
    interaction: discord.Interaction
):

    messages = await get_user_xp(
        interaction.guild.id,
        interaction.user.id
    )

    embed = discord.Embed(
        title="⭐ XP",
        description=f"```{messages}```",
        color=COLOR
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.command(
    name="xp"
)
async def prefix_xp(
    ctx
):

    messages = await get_user_xp(
        ctx.guild.id,
        ctx.author.id
    )

    embed = discord.Embed(
        title="⭐ XP",
        description=f"```{messages}```",
        color=COLOR
    )

    await ctx.send(
        embed=embed
    )


# =========================================================
# /LEVEL
# =========================================================

@bot.tree.command(
    name="level",
    description="Check your level"
)
async def slash_level(
    interaction: discord.Interaction
):

    messages = await get_user_xp(
        interaction.guild.id,
        interaction.user.id
    )

    level = messages // 50

    embed = discord.Embed(
        title="📊 LEVEL",
        description=f"```{level}```",
        color=COLOR
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.command(
    name="level"
)
async def prefix_level(
    ctx
):

    messages = await get_user_xp(
        ctx.guild.id,
        ctx.author.id
    )

    level = messages // 50

    embed = discord.Embed(
        title="📊 LEVEL",
        description=f"```{level}```",
        color=COLOR
    )

    await ctx.send(
        embed=embed
    )


# =========================================================
# /TOP — MONTH
# =========================================================

@bot.tree.command(
    name="top",
    description="Monthly top 10"
)
async def top(
    interaction: discord.Interaction
):

    await send_top(
        interaction,
        "month"
    )


# =========================================================
# /TOP_DAY
# =========================================================

@bot.tree.command(
    name="top_day",
    description="Daily top 10"
)
async def top_day(
    interaction: discord.Interaction
):

    await send_top(
        interaction,
        "day"
    )


# =========================================================
# /TOP_WEEK
# =========================================================

@bot.tree.command(
    name="top_week",
    description="Weekly top 10"
)
async def top_week(
    interaction: discord.Interaction
):

    await send_top(
        interaction,
        "week"
    )


# =========================================================
# PREFIX TOP
# =========================================================

@bot.command(
    name="top"
)
async def prefix_top(
    ctx
):

    await send_top(
        ctx,
        "month"
    )


@bot.command(
    name="top_day"
)
async def prefix_top_day(
    ctx
):

    await send_top(
        ctx,
        "day"
    )


@bot.command(
    name="top_week"
)
async def prefix_top_week(
    ctx
):

    await send_top(
        ctx,
        "week"
    )


# =========================================================
# /ME
# =========================================================

@bot.tree.command(
    name="me",
    description="Show your profile"
)
async def me(
    interaction: discord.Interaction
):

    member = interaction.user

    messages = await get_user_xp(
        interaction.guild.id,
        member.id
    )

    embed = discord.Embed(
        title=f"👤 {member.name}",
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
        value=f"`{messages // 50}`",
        inline=True
    )

    embed.add_field(
        name="👑 Role",
        value=member.top_role.mention,
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
    description="Show a member profile"
)
@app_commands.describe(
    member="Select a member"
)
async def profile(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    member = member or interaction.user

    messages = await get_user_xp(
        interaction.guild.id,
        member.id
    )

    embed = discord.Embed(
        title=f"👤 Profile: {member.name}",
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
        value=f"`{messages // 50}`",
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


# =========================================================
# /SERVER
# =========================================================

@bot.tree.command(
    name="server",
    description="Show server information"
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
        title=f"🖥 {guild.name}",
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


# =========================================================
# /CLEAR
# =========================================================

@bot.tree.command(
    name="clear",
    description="Delete messages"
)
@app_commands.default_permissions(
    manage_messages=True
)
@app_commands.describe(
    amount="Number of messages to delete"
)
async def clear(
    interaction: discord.Interaction,
    amount: app_commands.Range[int, 1, 100]
):

    await interaction.response.defer(
        ephemeral=True
    )

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


# =========================================================
# BAN
# =========================================================

@bot.tree.command(
    name="ban",
    description="Ban a member"
)
@app_commands.default_permissions(
    ban_members=True
)
async def ban(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not await check_hierarchy(
        interaction,
        member
    ):
        return

    await member.ban()

    await interaction.response.send_message(
        await t(
            interaction.user.id,
            "banned"
        )
    )


# =========================================================
# KICK
# =========================================================

@bot.tree.command(
    name="kick",
    description="Kick a member"
)
@app_commands.default_permissions(
    kick_members=True
)
async def kick(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not await check_hierarchy(
        interaction,
        member
    ):
        return

    await member.kick()

    await interaction.response.send_message(
        await t(
            interaction.user.id,
            "kicked"
        )
    )


# =========================================================
# TIMEOUT
# =========================================================

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
                interaction.user.id,
                "invalid_time"
            ),
            ephemeral=True
        )

        return

    await member.timeout(
        timedelta(
            seconds=seconds
        )
    )

    await interaction.response.send_message(
        await t(
            interaction.user.id,
            "timeout_applied"
        )
    )


# =========================================================
# TIMEOUT REMOVE
# =========================================================

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

    if not await check_hierarchy(
        interaction,
        member
    ):
        return

    await member.timeout(
        None
    )

    await interaction.response.send_message(
        await t(
            interaction.user.id,
            "timeout_removed"
        )
    )


# =========================================================
# LOCK
# =========================================================

@bot.tree.command(
    name="lock",
    description="Lock current channel"
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
            interaction.user.id,
            "channel_locked"
        )
    )


# =========================================================
# OPEN
# =========================================================

@bot.tree.command(
    name="open",
    description="Unlock current channel"
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
            interaction.user.id,
            "channel_unlocked"
        )
    )


# =========================================================
# PROTECTION
# =========================================================

@bot.tree.command(
    name="protection",
    description="Configure server protection"
)
@app_commands.default_permissions(
    manage_guild=True
)
@app_commands.describe(
    feature="badwords / links / antispam",
    status="on / off"
)
async def protection(
    interaction: discord.Interaction,
    feature: str,
    status: str
):

    feature = feature.lower().strip()
    status = status.lower().strip()

    if feature not in (
        "badwords",
        "links",
        "antispam"
    ):

        await interaction.response.send_message(
            "Available: `badwords`, `links`, `antispam`",
            ephemeral=True
        )

        return

    if status not in (
        "on",
        "off"
    ):

        await interaction.response.send_message(
            "Use `on` or `off`.",
            ephemeral=True
        )

        return

    enabled = status == "on"

    await update_settings(
        interaction.guild.id,
        {
            f"protection.{feature}":
                enabled
        }
    )

    await interaction.response.send_message(
        f"✅ `{feature}` → `{status}`",
        ephemeral=True
    )


# =========================================================
# BADWORD
# =========================================================

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
                interaction.user.id,
                "invalid_time"
            ),
            ephemeral=True
        )

        return

    word = word.strip().lower()

    if not word:

        await interaction.response.send_message(
            "Invalid word.",
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

    settings_cache.pop(
        gid,
        None
    )

    await interaction.response.send_message(
        f"✅ Added `{word}`",
        ephemeral=True
    )


# =========================================================
# AUTO REPLY
# =========================================================

@bot.tree.command(
    name="auto_reply",
    description="Add an automatic reply"
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
        f"✅ Auto reply added for `{trigger}`",
        ephemeral=True
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
                welcome.get("message"),
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
                leave.get("message"),
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
            "Leave error:",
            e
        )


# =========================================================
# MESSAGE EVENT
# =========================================================

@bot.event
async def on_message(
    message
):

    if message.author.bot:
        return

    if not message.guild:
        return

    gid = str(
        message.guild.id
    )

    uid = str(
        message.author.id
    )

    add_xp_memory(
        gid,
        uid
    )

    try:

        settings = await get_settings(
            gid
        )

    except Exception as e:

        print(
            "Settings error:",
            e
        )

        settings = clone_defaults()

    # -----------------------------------------------------
    # AUTO REPLIES
    # -----------------------------------------------------

    try:

        content = (
            message.content
            .strip()
            .lower()
        )

        for entry in settings.get(
            "autoReplies",
            []
        ):

            trigger = (
                entry.get(
                    "message",
                    ""
                )
                .strip()
                .lower()
            )

            reply = entry.get(
                "reply",
                ""
            )

            if (
                trigger
                and trigger in content
                and reply
            ):

                await message.channel.send(
                    embed=discord.Embed(
                        description=reply,
                        color=COLOR
                    )
                )

                break

    except Exception as e:

        print(
            "Auto reply error:",
            e
        )

    # -----------------------------------------------------
    # PROTECTION
    # -----------------------------------------------------

    try:

        protection_settings = settings.get(
            "protection",
            {}
        )

        if not message.author.guild_permissions.administrator:

            # BADWORDS

            if protection_settings.get(
                "badwords",
                True
            ):

                content_lower = (
                    message.content.lower()
                )

                for word, seconds in settings.get(
                    "badwords",
                    {}
                ).items():

                    pattern = (
                        r"(?<!\w)"
                        + re.escape(
                            word.lower()
                        )
                        + r"(?!\w)"
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
                                "Forbidden word.",
                                delete_after=5
                            )

                        except Exception as e:

                            print(
                                "Badword error:",
                                e
                            )

                        break

            # LINKS

            if protection_settings.get(
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
                            "Links are not allowed.",
                            delete_after=5
                        )

                    except Exception as e:

                        print(
                            "Link protection error:",
                            e
                        )

            # ANTISPAM

            if protection_settings.get(
                "antispam",
                True
            ):

                key = (
                    gid,
                    uid
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

                spam_cache[key] = history

                if len(history) >= 5:

                    try:

                        await message.author.timeout(
                            timedelta(
                                minutes=10
                            ),
                            reason="Spam"
                        )

                        await message.channel.send(
                            f"⏱ {message.author.mention} "
                            "You have been timed out for spam.",
                            delete_after=5
                        )

                    except Exception as e:

                        print(
                            "Antispam error:",
                            e
                        )

                    spam_cache[key] = []

    except Exception as e:

        print(
            "Protection error:",
            e
        )

    await bot.process_commands(
        message
    )


# =========================================================
# XP BACKGROUND
# =========================================================

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

        await asyncio.sleep(
            10
        )


# =========================================================
# PREMIUM EXPIRY
# =========================================================

async def premium_loop():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            await db.execute(
                """
                DELETE FROM premium_users
                WHERE expiry_time <= ?
                """,
                (
                    time.time(),
                )
            )

            await db.commit()

        except Exception as e:

            print(
                "Premium error:",
                e
            )

        await asyncio.sleep(
            60
        )


# =========================================================
# LEADERBOARD RESET
# =========================================================

async def leaderboard_reset_loop():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            now = datetime.now(
                timezone.utc
            )

            today = now.strftime(
                "%Y-%m-%d"
            )

            week = (
                f"{now.isocalendar().year}-"
                f"{now.isocalendar().week}"
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
                "Leaderboard reset error:",
                e
            )

        await asyncio.sleep(
            3600
        )


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    print(
        "===================================="
    )

    print(
        f"✅ Logged in as {bot.user}"
    )

    print(
        f"🏠 Servers: {len(bot.guilds)}"
    )

    print(
        "✅ Lunex is ready."
    )

    print(
        "===================================="
    )


# =========================================================
# START
# =========================================================

async def main():

    await init_database()

    asyncio.create_task(
        xp_loop()
    )

    asyncio.create_task(
        premium_loop()
    )

    asyncio.create_task(
        leaderboard_reset_loop()
    )

    await bot.start(
        TOKEN
    )


if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        pass
