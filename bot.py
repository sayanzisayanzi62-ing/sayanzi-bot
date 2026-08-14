# ============================================================
# LUNEX BOT — FULL OPTIMIZED EDITION
# discord.py 2.x
# MongoDB + SQLite
# Website Integration
# Advanced Ticket System
# Multi Language
# XP + Leaderboards
# ============================================================

import discord
from discord.ext import commands
from discord import app_commands

from datetime import timedelta, datetime, timezone

import asyncio
import sqlite3
import time
import io
import os
import re
import certifi
import traceback

from pymongo import MongoClient


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

SUPPORT_INVITE = "https://discord.gg/FMEXcwAvg"

BOT_INVITE = (
    "https://discord.com/oauth2/authorize"
    "?client_id=1501541120058851348"
    "&permissions=8"
    "&integration_type=0"
    "&scope=bot"
)


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

try:

    _mongo = MongoClient(
        MONGODB_URI,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=5000,
        maxPoolSize=20,
        minPoolSize=1
    )

    _mongo.admin.command("ping")

    _mdb = _mongo.get_default_database()

    guild_settings = _mdb["guildsettings"]

    print("✅ MongoDB connected.")

except Exception as e:

    print("❌ MongoDB connection failed:")
    print(e)

    raise


# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULT_SETTINGS = {

    "welcome": {
        "enabled": False,
        "channelId": None,
        "message": "اهلا [User] فيك بالسيرفر! [Img]"
    },

    "leave": {
        "enabled": False,
        "channelId": None,
        "message": "وداعا [User] :( [Img]"
    },

    "ticket": {

        "enabled": False,

        "image": "",

        "message": (
            "اضغط الزر بالأسفل لفتح تكت جديد"
        ),

        "description": (
            "مرحبا [User]، فريق الدعم راح يرد عليك قريبا"
        ),

        "categoryId": None,

        "channelId": None,

        "supportRoleId": None,

        "closeMessage": (
            "تم إغلاق التذكرة."
        )
    },

    "autoReplies": [],

    "commandAliases": [],

    "protection": {

        "badwords": True,

        "links": True,

        "antispam": True
    }
}


# ============================================================
# SETTINGS HELPERS
# ============================================================

def deep_copy_default_settings():

    import copy

    return copy.deepcopy(DEFAULT_SETTINGS)


def get_settings(guild_id: str) -> dict:

    guild_id = str(guild_id)

    doc = guild_settings.find_one(
        {"guildId": guild_id}
    )

    if not doc:

        doc = {
            "guildId": guild_id,
            **deep_copy_default_settings()
        }

        try:
            guild_settings.insert_one(doc)
        except Exception:
            pass

        return doc

    changed = False

    for key, value in DEFAULT_SETTINGS.items():

        if key not in doc:

            doc[key] = value
            changed = True

    if changed:

        try:
            guild_settings.update_one(
                {"guildId": guild_id},
                {
                    "$set": {
                        key: doc[key]
                        for key in DEFAULT_SETTINGS
                        if key not in {
                            "_id",
                            "guildId"
                        }
                    }
                }
            )
        except Exception:
            pass

    return doc


def update_settings(
    guild_id: str,
    update: dict
) -> dict:

    guild_id = str(guild_id)

    guild_settings.update_one(

        {"guildId": guild_id},

        {
            "$set": update,
            "$setOnInsert": {
                "guildId": guild_id
            }
        },

        upsert=True
    )

    return get_settings(guild_id)


def build_message(
    template: str,
    member: discord.Member
) -> str:

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
        "[Name]",
        member.display_name
    )

    text = text.replace(
        "[name]",
        member.display_name
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
        "[MemberCount]",
        str(member.guild.member_count)
    )

    return text


# ============================================================
# INTENTS
# ============================================================

intents = discord.Intents.all()


bot = commands.Bot(

    command_prefix=["!", "#"],

    intents=intents,

    case_insensitive=True,

    help_command=None
)


# ============================================================
# GLOBAL STATE
# ============================================================

_views_registered = False

_commands_synced = False

badword_words = {}

spam_cache = {}


# ============================================================
# SQLITE
# ============================================================

db = sqlite3.connect(
    "lunex.db",
    check_same_thread=False
)

cur = db.cursor()


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
    warns INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
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


# ============================================================
# LOCALIZATION
# ============================================================

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
            "❌ Invalid time format (e.g., 10m, 1h).",

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
            "❌ صيغة الوقت غير صحيحة (مثال: 10m, 1h).",

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

        "error":
            "❌ حدث خطأ:"
    }
}


def get_lang(user_id: str) -> str:

    cur.execute(
        "SELECT lang FROM user_settings WHERE user_id=?",
        (str(user_id),)
    )

    row = cur.fetchone()

    if row and row[0] in locales:

        return row[0]

    return "en"


def t(
    user_id: str,
    key: str,
    *args
) -> str:

    lang = get_lang(user_id)

    text = locales[lang].get(
        key,
        key
    )

    if args:

        return text.format(*args)

    return text


# ============================================================
# TIME PARSER
# ============================================================

def parse_time(t_str):

    try:

        if not t_str:
            return None

        t_str = t_str.strip().lower()

        if len(t_str) < 2:
            return None

        value = int(t_str[:-1])

        unit = t_str[-1]

        if value <= 0:
            return None

        if unit == "s":
            return value

        if unit == "m":
            return value * 60

        if unit == "h":
            return value * 3600

        if unit == "d":
            return value * 86400

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

    uid = str(interaction.user.id)

    guild = interaction.guild

    me = guild.me

    if not me:

        await interaction.response.send_message(
            "❌ I cannot determine my server member.",
            ephemeral=True
        )

        return False

    if member.id == guild.owner_id:

        await interaction.response.send_message(
            "❌ You cannot moderate the server owner.",
            ephemeral=True
        )

        return False

    if member.id == me.id:

        await interaction.response.send_message(
            "❌ I cannot moderate myself.",
            ephemeral=True
        )

        return False

    if member.top_role >= me.top_role:

        await interaction.response.send_message(
            t(uid, "higher_bot"),
            ephemeral=True
        )

        return False

    if (
        member.top_role >= interaction.user.top_role
        and interaction.user.id != guild.owner_id
    ):

        await interaction.response.send_message(
            t(uid, "higher_user"),
            ephemeral=True
        )

        return False

    return True


# ============================================================
# TICKET HELPERS
# ============================================================

def ticket_channel_name(
    member: discord.Member
) -> str:

    username = re.sub(
        r"[^a-zA-Z0-9-]",
        "-",
        member.name.lower()
    )

    username = username.strip("-")

    if not username:

        username = "user"

    return f"ticket-{username}-{member.id}"[:95]


def find_existing_ticket(
    guild: discord.Guild,
    user_id: int
):

    prefix = f"ticket-"

    for channel in guild.text_channels:

        if not channel.name.startswith(prefix):
            continue

        topic = channel.topic or ""

        if f"LUNEX_TICKET:{user_id}" in topic:

            return channel

    return None


def get_ticket_category(
    guild: discord.Guild,
    ticket_settings: dict
):

    category_id = ticket_settings.get(
        "categoryId"
    )

    if not category_id:

        return None

    try:

        category_id = int(category_id)

    except Exception:

        return None

    channel = guild.get_channel(
        category_id
    )

    if isinstance(
        channel,
        discord.CategoryChannel
    ):

        return channel

    return None


def get_support_role(
    guild: discord.Guild,
    ticket_settings: dict
):

    role_id = ticket_settings.get(
        "supportRoleId"
    )

    if not role_id:

        return None

    try:

        role_id = int(role_id)

    except Exception:

        return None

    return guild.get_role(role_id)


async def create_ticket(
    interaction: discord.Interaction
):

    guild = interaction.guild

    member = interaction.user

    if not guild:

        await interaction.response.send_message(
            "❌ This command can only be used inside a server.",
            ephemeral=True
        )

        return

    settings = get_settings(
        str(guild.id)
    )

    ticket_settings = settings.get(
        "ticket",
        {}
    )

    if not ticket_settings.get(
        "enabled",
        False
    ):

        await interaction.response.send_message(
            "❌ Ticket system is disabled.",
            ephemeral=True
        )

        return

    existing = find_existing_ticket(
        guild,
        member.id
    )

    if existing:

        await interaction.response.send_message(
            f"🎫 You already have an open ticket: {existing.mention}",
            ephemeral=True
        )

        return

    me = guild.me

    if not me.guild_permissions.manage_channels:

        await interaction.response.send_message(
            "❌ I need **Manage Channels** permission to create tickets.",
            ephemeral=True
        )

        return

    category = get_ticket_category(
        guild,
        ticket_settings
    )

    support_role = get_support_role(
        guild,
        ticket_settings
    )

    name = ticket_channel_name(
        member
    )

    overwrites = {

        guild.default_role:
            discord.PermissionOverwrite(
                view_channel=False
            ),

        member:
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),

        me:
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True
            )
    }

    if support_role:

        overwrites[support_role] = (
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )
        )

    try:

        await interaction.response.defer(
            ephemeral=True
        )

        channel = await guild.create_text_channel(

            name=name,

            topic=(
                f"LUNEX_TICKET:{member.id}"
                f" | Created:{int(time.time())}"
            ),

            overwrites=overwrites,

            category=category,

            reason=f"Lunex ticket opened by {member}"
        )

        description = build_message(

            ticket_settings.get(
                "description"
            ) or
            "Hello [User], our support team will be with you shortly.",

            member
        )

        embed = discord.Embed(

            title="🎫 Lunex Support Ticket",

            description=description,

            color=COLOR,

            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(

            name="👤 User",

            value=member.mention,

            inline=True
        )

        embed.add_field(

            name="🆔 User ID",

            value=f"`{member.id}`",

            inline=True
        )

        if support_role:

            embed.add_field(

                name="👮 Support",

                value=support_role.mention,

                inline=True
            )

        image = ticket_settings.get(
            "image"
        )

        if image:

            try:
                embed.set_image(
                    url=image
                )
            except Exception:
                pass

        embed.set_footer(
            text="Lunex • Ticket System"
        )

        await channel.send(

            content=(
                f"{member.mention}"
                + (
                    f" {support_role.mention}"
                    if support_role
                    else ""
                )
            ),

            embed=embed,

            view=CloseTicketView()
        )

        await interaction.followup.send(

            f"🎫 Your ticket has been opened: "
            f"{channel.mention}",

            ephemeral=True
        )

    except discord.Forbidden:

        await interaction.followup.send(

            "❌ I don't have enough permissions to create the ticket.",

            ephemeral=True
        )

    except Exception as e:

        print(
            "Ticket creation error:",
            repr(e)
        )

        try:

            await interaction.followup.send(

                "❌ Something went wrong while creating the ticket.",

                ephemeral=True
            )

        except Exception:
            pass


# ============================================================
# CLOSE TICKET CONFIRMATION
# ============================================================

class ConfirmCloseView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=30
        )

    @discord.ui.button(
        label="Confirm",
        emoji="🗑️",
        style=discord.ButtonStyle.danger
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        channel = interaction.channel

        if not isinstance(
            channel,
            discord.TextChannel
        ):

            await interaction.response.send_message(
                "❌ This is not a ticket channel.",
                ephemeral=True
            )

            return

        topic = channel.topic or ""

        if not topic.startswith(
            "LUNEX_TICKET:"
        ):

            await interaction.response.send_message(
                "❌ This channel is not a Lunex ticket.",
                ephemeral=True
            )

            return

        if not (
            interaction.user.guild_permissions.manage_channels
            or interaction.user.guild_permissions.administrator
        ):

            try:

                owner_id = int(
                    topic.split(
                        "LUNEX_TICKET:",
                        1
                    )[1].split(
                        " ",
                        1
                    )[0]
                )

            except Exception:

                owner_id = None

            if owner_id != interaction.user.id:

                await interaction.response.send_message(
                    "❌ You cannot close this ticket.",
                    ephemeral=True
                )

                return

        await interaction.response.defer()

        await asyncio.sleep(2)

        try:

            await channel.delete(
                reason=f"Ticket closed by {interaction.user}"
            )

        except discord.Forbidden:

            try:

                await interaction.followup.send(
                    "❌ I don't have permission to delete this channel.",
                    ephemeral=True
                )
            except Exception:
                pass

        except Exception as e:

            print(
                "Ticket deletion error:",
                repr(e)
            )


    @discord.ui.button(
        label="Cancel",
        emoji="↩️",
        style=discord.ButtonStyle.secondary
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.edit_message(
            content="❎ Ticket close cancelled.",
            view=None
        )


# ============================================================
# CLOSE TICKET VIEW
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
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="lunex_close_ticket"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        channel = interaction.channel

        if not isinstance(
            channel,
            discord.TextChannel
        ):

            await interaction.response.send_message(
                "❌ Invalid ticket channel.",
                ephemeral=True
            )

            return

        topic = channel.topic or ""

        if not topic.startswith(
            "LUNEX_TICKET:"
        ):

            await interaction.response.send_message(
                "❌ This is not a Lunex ticket.",
                ephemeral=True
            )

            return

        try:

            owner_id = int(
                topic.split(
                    "LUNEX_TICKET:",
                    1
                )[1].split(
                    " ",
                    1
                )[0]
            )

        except Exception:

            owner_id = None

        is_staff = (
            interaction.user.guild_permissions.manage_channels
            or interaction.user.guild_permissions.administrator
        )

        if (
            owner_id != interaction.user.id
            and not is_staff
        ):

            await interaction.response.send_message(
                "❌ You cannot close this ticket.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(

            "⚠️ **Are you sure you want to close this ticket?**",

            view=ConfirmCloseView(),

            ephemeral=True
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
        emoji="🎫",
        style=discord.ButtonStyle.primary,
        custom_id="lunex_open_ticket"
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await create_ticket(
            interaction
        )


# ============================================================
# POST TICKET PANEL
# ============================================================

async def post_ticket_panel(
    guild_id: str,
    channel_id: str
):

    guild = bot.get_guild(
        int(guild_id)
    )

    if not guild:

        raise ValueError(
            "Bot is not in this server."
        )

    channel = guild.get_channel(
        int(channel_id)
    )

    if not channel:

        raise ValueError(
            "Channel not found."
        )

    if not isinstance(
        channel,
        discord.TextChannel
    ):

        raise ValueError(
            "Selected channel is not a text channel."
        )

    settings = get_settings(
        str(guild_id)
    )

    ticket = settings.get(
        "ticket",
        {}
    )

    if not ticket.get(
        "enabled",
        False
    ):

        raise ValueError(
            "Ticket system is disabled."
        )

    embed = discord.Embed(

        title="🎫 Lunex Ticket System",

        description=(
            ticket.get("message")
            or
            "Click the button below to open a new ticket."
        ),

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
        text="Lunex • Support System"
    )

    await channel.send(

        embed=embed,

        view=TicketView()
    )


# ============================================================
# HELP MENU
# ============================================================

class HelpSelect(
    discord.ui.Select
):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="All member",
                description="Member commands & XP",
                emoji="👥"
            ),

            discord.SelectOption(
                label="Staff member",
                description="Administration and security commands",
                emoji="👑"
            )
        ]

        super().__init__(

            placeholder="Select desired category",

            options=options,

            custom_id="help_select"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if self.values[0] == "All member":

            embed = discord.Embed(

                title="👥 ALL MEMBER COMMANDS",

                description=(
                    "**Everything available to every member.**\n\n"
                    f"🌐 **Visit us:** {SITE_URL}"
                ),

                color=COLOR
            )

            embed.add_field(

                name="⭐ XP & Leaderboards",

                value=(
                    "**!xp** / **/xp** — your XP\n"
                    "**!level** / **/level** — your level\n"
                    "**!t** — monthly top 10\n"
                    "**!t day** — daily top 10\n"
                    "**!t week** — weekly top 10"
                ),

                inline=False
            )

            embed.add_field(

                name="📌 Info",

                value=(
                    "**/me** `[member]` — profile\n"
                    "**/profile** `[member]` — avatar\n"
                    "**/server** — server info\n"
                    "**/language** — language\n"
                    "**/commands**"
                ),

                inline=False
            )

        else:

            embed = discord.Embed(

                title="👑 STAFF MEMBER COMMANDS",

                description=(
                    "**Moderation, security, and server management.**\n\n"
                    f"🌐 **Visit us:** {SITE_URL}"
                ),

                color=COLOR
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

                inline=False
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


def build_main_embed():

    embed = discord.Embed(

        title="🌙 LUNEX BOT",

        description=(
            "**Advanced, powerful, and simple server management.**\n\n"
            f"🌐 **To learn more:** {SITE_URL}"
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

    return embed


# ============================================================
# BACKGROUND TASKS
# ============================================================

async def check_expired_premiums():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            current_time = time.time()

            cur.execute(

                """
                SELECT user_id, guild_id
                FROM premium_users
                WHERE expiry_time <= ?
                """,

                (current_time,)
            )

            rows = cur.fetchall()

            for uid, gid in rows:

                cur.execute(

                    """
                    DELETE FROM premium_users
                    WHERE user_id=? AND guild_id=?
                    """,

                    (uid, gid)
                )

            db.commit()

        except Exception as e:

            print(
                "Premium expiry error:",
                repr(e)
            )

        await asyncio.sleep(60)


async def reset_leaderboards():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            now = datetime.now(
                timezone.utc
            )

            today_str = now.strftime(
                "%Y-%m-%d"
            )

            iso = now.isocalendar()

            week_str = f"{iso.year}-{iso.week}"

            month_str = now.strftime(
                "%Y-%m"
            )

            cur.execute(
                """
                SELECT last_day,
                       last_week,
                       last_month
                FROM reset_tracker
                WHERE id=1
                """
            )

            row = cur.fetchone()

            if not row:

                cur.execute(

                    """
                    INSERT INTO reset_tracker
                    VALUES (1, ?, ?, ?)
                    """,

                    (
                        today_str,
                        week_str,
                        month_str
                    )
                )

            else:

                last_day, last_week, last_month = row

                if last_day != today_str:

                    cur.execute(
                        "UPDATE xp SET day_count=0"
                    )

                if last_week != week_str:

                    cur.execute(
                        "UPDATE xp SET week_count=0"
                    )

                if last_month != month_str:

                    cur.execute(
                        "UPDATE xp SET month_count=0"
                    )

                cur.execute(

                    """
                    UPDATE reset_tracker
                    SET last_day=?,
                        last_week=?,
                        last_month=?
                    WHERE id=1
                    """,

                    (
                        today_str,
                        week_str,
                        month_str
                    )
                )

            db.commit()

        except Exception as e:

            print(
                "Leaderboard reset error:",
                repr(e)
            )

        await asyncio.sleep(
            3600
        )


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    global _views_registered
    global _commands_synced

    if not _commands_synced:

        try:

            synced = await bot.tree.sync()

            print(
                f"✅ Synced {len(synced)} slash command(s)"
            )

        except Exception as e:

            print(
                "❌ Slash command sync failed:",
                repr(e)
            )

        _commands_synced = True

    if not _views_registered:

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

        bot.loop.create_task(
            check_expired_premiums()
        )

        bot.loop.create_task(
            reset_leaderboards()
        )

    print(
        f"✅ Lunex Bot logged in as {bot.user}"
    )


# ============================================================
# WELCOME
# ============================================================

@bot.event
async def on_member_join(
    member: discord.Member
):

    try:

        settings = get_settings(
            str(member.guild.id)
        )

        welcome = settings.get(
            "welcome",
            {}
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
            repr(e)
        )


# ============================================================
# LEAVE
# ============================================================

@bot.event
async def on_member_remove(
    member: discord.Member
):

    try:

        settings = get_settings(
            str(member.guild.id)
        )

        leave = settings.get(
            "leave",
            {}
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
            repr(e)
        )


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

    gid = str(
        message.guild.id
    )

    uid = str(
        message.author.id
    )

    # --------------------------------------------------------
    # XP
    # --------------------------------------------------------

    try:

        cur.execute(

            """
            INSERT INTO xp (
                guild_id,
                user_id,
                messages,
                day_count,
                week_count,
                month_count
            )
            VALUES (?, ?, 1, 1, 1, 1)

            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET

                messages=messages+1,

                day_count=day_count+1,

                week_count=week_count+1,

                month_count=month_count+1
            """,

            (
                gid,
                uid
            )
        )

        db.commit()

    except Exception as e:

        print(
            "XP error:",
            repr(e)
        )

    # --------------------------------------------------------
    # Mongo settings
    # --------------------------------------------------------

    settings = None

    try:

        settings = get_settings(
            gid
        )

    except Exception as e:

        print(
            "Settings error:",
            repr(e)
        )

    # --------------------------------------------------------
    # Command aliases
    # --------------------------------------------------------

    if settings:

        try:

            for prefix in (
                "!",
                "#"
            ):

                if message.content.startswith(
                    prefix
                ):

                    rest = message.content[
                        len(prefix):
                    ]

                    first_word, _, remainder = (
                        rest.partition(" ")
                    )

                    for alias_entry in settings.get(
                        "commandAliases",
                        []
                    ):

                        if (
                            first_word.lower()
                            ==
                            str(
                                alias_entry.get(
                                    "alias",
                                    ""
                                )
                            ).lower()
                        ):

                            original = alias_entry.get(
                                "original"
                            )

                            if not original:
                                continue

                            new_content = (
                                f"{prefix}{original}"
                            )

                            if remainder:
                                new_content += (
                                    f" {remainder}"
                                )

                            message.content = new_content

                            break

        except Exception as e:

            print(
                "Alias error:",
                repr(e)
            )

    # --------------------------------------------------------
    # Auto replies
    # --------------------------------------------------------

    if settings:

        try:

            content_lower = (
                message.content
                .strip()
                .lower()
            )

            for reply_entry in settings.get(
                "autoReplies",
                []
            ):

                trigger = (
                    reply_entry.get(
                        "message",
                        ""
                    )
                    .strip()
                    .lower()
                )

                if (
                    trigger
                    and trigger in content_lower
                ):

                    reply_text = (
                        reply_entry.get(
                            "reply",
                            ""
                        )
                    )

                    if reply_text:

                        await message.channel.send(

                            embed=discord.Embed(

                                description=reply_text,

                                color=COLOR
                            )
                        )

                    break

        except Exception as e:

            print(
                "Auto reply error:",
                repr(e)
            )

    # --------------------------------------------------------
    # Protection
    # --------------------------------------------------------

    try:

        protection = (
            settings.get(
                "protection",
                {}
            )
            if settings
            else {}
        )

        is_admin = (
            message.author.guild_permissions
            .administrator
        )

        if not is_admin:

            # Bad words

            if protection.get(
                "badwords",
                True
            ):

                for word, seconds in list(
                    badword_words.items()
                ):

                    if word in message.content.lower():

                        try:

                            await message.delete()

                            await message.author.timeout(

                                timedelta(
                                    seconds=seconds
                                ),

                                reason="Lunex Bad Word"
                            )

                            await message.channel.send(

                                f"⛔ {message.author.mention} "
                                f"Forbidden word detected."
                            )

                        except Exception:
                            pass

                        break

            # Links

            if protection.get(
                "links",
                True
            ):

                content = (
                    message.content.lower()
                )

                if (
                    "http://"
                    in content
                    or
                    "https://"
                    in content
                ):

                    try:

                        await message.delete()

                        await message.channel.send(

                            f"🚫 {message.author.mention} "
                            "Links are not allowed in this server!"
                        )

                    except Exception:
                        pass

            # Anti spam

            if protection.get(
                "antispam",
                True
            ):

                key = (
                    gid,
                    uid
                )

                now = time.time()

                timestamps = spam_cache.get(
                    key,
                    []
                )

                timestamps.append(
                    now
                )

                timestamps = [

                    stamp

                    for stamp in timestamps

                    if now - stamp < 3
                ]

                spam_cache[key] = timestamps

                if len(timestamps) >= 5:

                    try:

                        await message.author.timeout(

                            timedelta(
                                minutes=10
                            ),

                            reason="Lunex Anti-Spam"
                        )

                        await message.channel.send(

                            f"⏱ {message.author.mention} "
                            "You have been timed out for spamming."
                        )

                    except Exception:
                        pass

                    spam_cache[key] = []

    except Exception as e:

        print(
            "Protection error:",
            repr(e)
        )

    await bot.process_commands(
        message
    )


# ============================================================
# LANGUAGE
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
async def set_language(
    interaction: discord.Interaction,
    lang: str
):

    uid = str(
        interaction.user.id
    )

    cur.execute(

        """
        INSERT INTO user_settings
        (user_id, lang)

        VALUES (?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET lang=excluded.lang
        """,

        (
            uid,
            lang
        )
    )

    db.commit()

    await interaction.response.send_message(

        t(
            uid,
            "lang_set"
        ),

        ephemeral=True
    )


# ============================================================
# PROTECTION
# ============================================================

@bot.tree.command(
    name="protection",
    description="View protection settings"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def protection_config(
    interaction: discord.Interaction
):

    settings = get_settings(
        str(interaction.guild.id)
    )

    protection = settings.get(
        "protection",
        {}
    )

    embed = discord.Embed(
        title="🛡️ Lunex Protection",
        color=COLOR
    )

    embed.add_field(
        name="🚫 Bad Words",
        value=(
            "Enabled"
            if protection.get(
                "badwords",
                True
            )
            else "Disabled"
        ),
        inline=True
    )

    embed.add_field(
        name="🔗 Links",
        value=(
            "Enabled"
            if protection.get(
                "links",
                True
            )
            else "Disabled"
        ),
        inline=True
    )

    embed.add_field(
        name="⚡ Anti Spam",
        value=(
            "Enabled"
            if protection.get(
                "antispam",
                True
            )
            else "Disabled"
        ),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
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
        view=HelpView()
    )


@bot.tree.command(
    name="commands",
    description="Display Lunex bot commands"
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
# XP
# ============================================================

@bot.command()
async def xp(
    ctx
):

    cur.execute(

        """
        SELECT messages
        FROM xp
        WHERE guild_id=?
        AND user_id=?
        """,

        (
            str(ctx.guild.id),
            str(ctx.author.id)
        )
    )

    row = cur.fetchone()

    amount = (
        row[0]
        if row
        else 0
    )

    embed = discord.Embed(

        title="⭐ XP",

        description=f"```{amount}```",

        color=COLOR
    )

    await ctx.send(
        embed=embed
    )


@bot.tree.command(
    name="xp",
    description="Check your XP"
)
async def slash_xp(
    interaction: discord.Interaction
):

    cur.execute(

        """
        SELECT messages
        FROM xp
        WHERE guild_id=?
        AND user_id=?
        """,

        (
            str(interaction.guild.id),
            str(interaction.user.id)
        )
    )

    row = cur.fetchone()

    amount = (
        row[0]
        if row
        else 0
    )

    await interaction.response.send_message(

        embed=discord.Embed(

            title="⭐ XP",

            description=f"```{amount}```",

            color=COLOR
        )
    )


# ============================================================
# LEVEL
# ============================================================

@bot.command()
async def level(
    ctx
):

    cur.execute(

        """
        SELECT messages
        FROM xp
        WHERE guild_id=?
        AND user_id=?
        """,

        (
            str(ctx.guild.id),
            str(ctx.author.id)
        )
    )

    row = cur.fetchone()

    messages = (
        row[0]
        if row
        else 0
    )

    await ctx.send(

        embed=discord.Embed(

            title="📊 LEVEL",

            description=f"```{messages // 50}```",

            color=COLOR
        )
    )


@bot.tree.command(
    name="level",
    description="Check your level"
)
async def slash_level(
    interaction: discord.Interaction
):

    cur.execute(

        """
        SELECT messages
        FROM xp
        WHERE guild_id=?
        AND user_id=?
        """,

        (
            str(interaction.guild.id),
            str(interaction.user.id)
        )
    )

    row = cur.fetchone()

    messages = (
        row[0]
        if row
        else 0
    )

    await interaction.response.send_message(

        embed=discord.Embed(

            title="📊 LEVEL",

            description=f"```{messages // 50}```",

            color=COLOR
        )
    )


# ============================================================
# LEADERBOARD
# ============================================================

@bot.command(
    name="t"
)
async def top_command(
    ctx,
    mode: str = None
):

    gid = str(
        ctx.guild.id
    )

    if mode:

        mode = mode.lower()

    if mode == "day":

        column = "day_count"

        title = "🏆 Daily Top"

    elif mode == "week":

        column = "week_count"

        title = "🏆 Weekly Top"

    else:

        column = "month_count"

        title = "🏆 Monthly Top"

    cur.execute(

        f"""
        SELECT user_id, {column}
        FROM xp
        WHERE guild_id=?
        AND {column} > 0
        ORDER BY {column} DESC
        LIMIT 10
        """,

        (
            gid,
        )
    )

    rows = cur.fetchall()

    embed = discord.Embed(
        title=title,
        color=COLOR
    )

    if not rows:

        embed.description = (
            "No data yet."
        )

    else:

        for index, (
            user_id,
            count
        ) in enumerate(
            rows,
            start=1
        ):

            embed.add_field(

                name=f"{index}. <@{user_id}>",

                value=f"💬 {count} messages",

                inline=False
            )

    await ctx.send(
        embed=embed
    )


# ============================================================
# PROFILE AVATAR
# ============================================================

@bot.tree.command(
    name="profile",
    description="Show a member's avatar"
)
@app_commands.describe(
    member="Select a member"
)
async def avatar_slash(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    member = (
        member
        or interaction.user
    )

    embed = discord.Embed(

        title=f"Avatar: {member.name}",

        color=COLOR
    )

    embed.set_image(
        url=member.display_avatar.url
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# SERVER
# ============================================================

@bot.tree.command(
    name="server",
    description="Show server information"
)
async def server_info_slash(
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


# ============================================================
# ME
# ============================================================

@bot.tree.command(
    name="me",
    description="Show a member's profile"
)
@app_commands.describe(
    member="Select a member"
)
async def profile_slash(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    member = (
        member
        or interaction.user
    )

    cur.execute(

        """
        SELECT messages
        FROM xp
        WHERE guild_id=?
        AND user_id=?
        """,

        (
            str(interaction.guild.id),
            str(member.id)
        )
    )

    row = cur.fetchone()

    messages = (
        row[0]
        if row
        else 0
    )

    embed = discord.Embed(

        title=f"Profile: {member.name}",

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
    member: discord.Member = None
):

    member = (
        member
        or ctx.author
    )

    cur.execute(

        """
        SELECT warns
        FROM warns
        WHERE guild_id=?
        AND user_id=?
        """,

        (
            str(ctx.guild.id),
            str(member.id)
        )
    )

    row = cur.fetchone()

    warns = (
        row[0]
        if row
        else 0
    )

    await ctx.send(

        embed=discord.Embed(

            title=f"📋 Records for {member.name}",

            description=(
                f"⚠️ Warnings: `{warns}`"
            ),

            color=COLOR
        )
    )


# ============================================================
# CLEAR
# ============================================================

@bot.command(
    name="clear",
    aliases=["مسح"]
)
@commands.has_permissions(
    manage_messages=True
)
async def clear(
    ctx,
    amount: int
):

    if amount <= 0:

        return await ctx.send(
            "❌ Amount must be greater than 0.",
            delete_after=3
        )

    if amount > 100:

        return await ctx.send(
            "❌ Maximum is 100 messages.",
            delete_after=3
        )

    uid = str(
        ctx.author.id
    )

    deleted = await ctx.channel.purge(
        limit=amount + 1
    )

    msg = await ctx.send(
        t(
            uid,
            "cleared",
            max(
                len(deleted) - 1,
                0
            )
        )
    )

    await asyncio.sleep(
        3
    )

    try:

        await msg.delete()

    except Exception:
        pass


# ============================================================
# BAN
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
    member: discord.Member
):

    if not await check_hierarchy(
        interaction,
        member
    ):

        return

    try:

        await member.ban(
            reason=f"Lunex | {interaction.user}"
        )

        await interaction.response.send_message(
            t(
                str(interaction.user.id),
                "banned"
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I don't have permission to ban this member.",
            ephemeral=True
        )


# ============================================================
# KICK
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
    member: discord.Member
):

    if not await check_hierarchy(
        interaction,
        member
    ):

        return

    try:

        await member.kick(
            reason=f"Lunex | {interaction.user}"
        )

        await interaction.response.send_message(
            t(
                str(interaction.user.id),
                "kicked"
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I don't have permission to kick this member.",
            ephemeral=True
        )


# ============================================================
# UNBAN
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
            t(
                uid,
                "unbanned"
            )
        )

    except ValueError:

        await interaction.response.send_message(
            "❌ Invalid user ID.",
            ephemeral=True
        )

    except Exception as e:

        await interaction.response.send_message(

            f"{t(uid, 'error')} "
            f"`{str(e)[:500]}`",

            ephemeral=True
        )


# ============================================================
# LOCK
# ============================================================

@bot.tree.command(
    name="lock",
    description="Lock channel"
)
@app_commands.default_permissions(
    manage_channels=True
)
async def lock_slash(
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

        overwrite=overwrite,

        reason=f"Lunex Lock | {interaction.user}"
    )

    await interaction.response.send_message(
        t(
            str(interaction.user.id),
            "channel_locked"
        )
    )


# ============================================================
# OPEN
# ============================================================

@bot.tree.command(
    name="open",
    description="Unlock channel"
)
@app_commands.default_permissions(
    manage_channels=True
)
async def open_slash(
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

        overwrite=overwrite,

        reason=f"Lunex Unlock | {interaction.user}"
    )

    await interaction.response.send_message(
        t(
            str(interaction.user.id),
            "channel_unlocked"
        )
    )


# ============================================================
# TIMEOUT
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
            t(
                uid,
                "invalid_time"
            ),
            ephemeral=True
        )

        return

    try:

        await member.timeout(

            timedelta(
                seconds=seconds
            ),

            reason=f"Lunex Timeout | {interaction.user}"
        )

        await interaction.response.send_message(
            t(
                uid,
                "timeout_applied"
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot timeout this member.",
            ephemeral=True
        )


# ============================================================
# REMOVE TIMEOUT
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
            None,
            reason=f"Lunex Timeout Remove | {interaction.user}"
        )

        await interaction.response.send_message(
            t(
                uid,
                "timeout_removed"
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot remove this timeout.",
            ephemeral=True
        )


# ============================================================
# ADD ROLE
# ============================================================

@bot.tree.command(
    name="add_role",
    description="Add a role"
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

    if role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ I cannot manage this role.",
            ephemeral=True
        )

        return

    try:

        await member.add_roles(
            role,
            reason=f"Lunex Add Role | {interaction.user}"
        )

        await interaction.response.send_message(
            t(
                str(interaction.user.id),
                "role_added"
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot add this role.",
            ephemeral=True
        )


# ============================================================
# REMOVE ROLE
# ============================================================

@bot.tree.command(
    name="remove_role",
    description="Remove a role"
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

    if role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ I cannot manage this role.",
            ephemeral=True
        )

        return

    try:

        await member.remove_roles(
            role,
            reason=f"Lunex Remove Role | {interaction.user}"
        )

        await interaction.response.send_message(
            t(
                str(interaction.user.id),
                "role_removed"
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot remove this role.",
            ephemeral=True
        )


# ============================================================
# NICKNAME
# ============================================================

@bot.tree.command(
    name="nickname",
    description="Change a member's nickname"
)
@app_commands.describe(
    member="Select member",
    nickname="New nickname"
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
            nick=nickname,
            reason=f"Lunex Nickname | {interaction.user}"
        )

        await interaction.response.send_message(
            t(
                uid,
                "nick_changed"
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot change this nickname.",
            ephemeral=True
        )


# ============================================================
# BADWORD
# ============================================================

@bot.tree.command(
    name="badword",
    description="Add banned word"
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
            t(
                str(interaction.user.id),
                "invalid_time"
            ),
            ephemeral=True
        )

        return

    badword_words[
        word.lower()
    ] = seconds

    await interaction.response.send_message(

        f"✅ Added `{word}` "
        f"with timeout `{time}`.",

        ephemeral=True
    )


# ============================================================
# AUTO REPLY ADD
# ============================================================

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

    guild_settings.update_one(

        {
            "guildId":
                str(interaction.guild.id)
        },

        {
            "$push": {

                "autoReplies": {

                    "message": trigger,

                    "reply": reply
                }
            },

            "$setOnInsert": {

                "guildId":
                    str(interaction.guild.id)
            }
        },

        upsert=True
    )

    await interaction.response.send_message(

        f"✅ Added auto-reply for `{trigger}`",

        ephemeral=True
    )


# ============================================================
# AUTO REPLY REMOVE
# ============================================================

@bot.tree.command(
    name="auto_reply_remove",
    description="Remove an automatic reply"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def auto_reply_remove(
    interaction: discord.Interaction,
    trigger: str
):

    guild_settings.update_one(

        {
            "guildId":
                str(interaction.guild.id)
        },

        {
            "$pull": {

                "autoReplies": {

                    "message": trigger
                }
            }
        }
    )

    await interaction.response.send_message(

        "✅ Deleted successfully.",

        ephemeral=True
    )


# ============================================================
# ERROR HANDLER
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
            "❌ You don't have permission to use this command.",
            delete_after=5
        )

        return

    if isinstance(
        error,
        commands.MissingRequiredArgument
    ):

        await ctx.send(
            "❌ Missing required argument.",
            delete_after=5
        )

        return

    if isinstance(
        error,
        commands.BadArgument
    ):

        await ctx.send(
            "❌ Invalid argument.",
            delete_after=5
        )

        return

    print(
        "Command error:",
        repr(error)
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        bot.run(
            TOKEN
        )

    except KeyboardInterrupt:

        print(
            "🛑 Bot stopped."
        )

    except Exception:

        traceback.print_exc()
