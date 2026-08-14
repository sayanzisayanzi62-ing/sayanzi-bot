# ============================================================
# LUNEX BOT — FULL CLEAN EDITION
# discord.py 2.x
# Railway + MongoDB + SQLite
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

DB_PATH = os.getenv(
    "SQLITE_PATH",
    "lunex.db"
)


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
        CREATE TABLE IF NOT EXISTS premium_users (
            user_id INTEGER PRIMARY KEY,
            expires_at REAL
        )
    """)

    conn.commit()
    conn.close()

    print("✅ SQLite database initialized.")


# ============================================================
# MONGODB SETTINGS CACHE
# ============================================================

settings_cache = {}

SETTINGS_CACHE_TTL = 300


DEFAULT_SETTINGS = {

    "language": "ar",

    "welcome": {
        "enabled": False,
        "channelId": None,
        "message": "Welcome {user}!"
    },

    "leave": {
        "enabled": False,
        "channelId": None,
        "message": "{user} has left the server."
    },

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

    "autoReplies": [],

    "commandAliases": {},

    "badwords": {},

    "protection": {
        "badwords": True,
        "links": True,
        "antispam": True
    }
}


# ============================================================
# GET SETTINGS
# ============================================================

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

        data = {
            "guildId": guild_id,
            **DEFAULT_SETTINGS
        }

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


# ============================================================
# UPDATE SETTINGS
# ============================================================

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
# LANGUAGE
# ============================================================

TEXT = {

    "ar": {

        "language_changed":
            "🇱🇾 تم تغيير لغة البوت إلى العربية.",

        "language_invalid":
            "❌ اللغة غير صحيحة.",

        "no_permission":
            "❌ ليس لديك الصلاحية.",

        "xp":
            "خبرتك الحالية",

        "level":
            "مستواك الحالي",

        "registered":
            "تم تسجيلك بنجاح.",

        "clear":
            "تم حذف الرسائل بنجاح.",

        "level_role_saved":
            "🎉 تم حفظ رتبة المستوى بنجاح.",

        "role_not_found":
            "❌ الرتبة غير موجودة.",

        "leaderboard":
            "🏆 لوحة المتصدرين",

        "empty":
            "لا توجد بيانات كافية حتى الآن.",

        "error":
            "❌ حدث خطأ."
    },

    "en": {

        "language_changed":
            "🇬🇧 Bot language changed to English.",

        "language_invalid":
            "❌ Invalid language.",

        "no_permission":
            "❌ You don't have permission.",

        "xp":
            "Your current XP",

        "level":
            "Your current level",

        "registered":
            "You have been registered successfully.",

        "clear":
            "Messages deleted successfully.",

        "level_role_saved":
            "🎉 Level role saved successfully.",

        "role_not_found":
            "❌ Role not found.",

        "leaderboard":
            "🏆 Leaderboard",

        "empty":
            "Not enough data yet.",

        "error":
            "❌ An error occurred."
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
        (
            int(guild_id),
        )
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


async def tr(
    guild_id,
    key
):

    language = await get_language(
        guild_id
    )

    return TEXT.get(
        language,
        TEXT["ar"]
    ).get(
        key,
        key
    )


# ============================================================
# XP SYSTEM
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


# ============================================================
# GET XP DATA
# ============================================================

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


# ============================================================
# ADD XP
# ============================================================

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
        SELECT
            xp,
            level,
            last_message
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

    # Anti XP spam
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

    if not row:
        return None

    return int(row[0])


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
            reason=(
                f"Lunex Level {level} reward"
            )
        )

        print(
            f"✅ Given role {role.name} "
            f"to {member} for level {level}"
        )

    except discord.Forbidden:

        print(
            "❌ Discord refused level role."
        )

    except discord.HTTPException as e:

        print(
            "❌ Level role HTTP error:",
            repr(e)
        )


# ============================================================
# HELP MENU
# ============================================================

def build_help_embed(
    category
):

    if category == "general":

        title = "🏠 Lunex — General"

        description = (
            "`/commands` — قائمة الأوامر\n"
            "`/language` — تغيير اللغة\n"
            "`/register` — تسجيل الحساب"
        )

    elif category == "xp":

        title = "⭐ Lunex — XP & Levels"

        description = (
            "`/xp` — عرض XP\n"
            "`/level` — عرض المستوى\n"
            "`/top` — متصدرين الشهر\n"
            "`/top_day` — متصدرين اليوم\n"
            "`/top_week` — متصدرين الأسبوع\n"
            "`/level_roll` — ربط مستوى برتبة"
        )

    elif category == "profile":

        title = "👤 Lunex — Profile"

        description = (
            "`/me` — معلوماتك\n"
            "`/profile` — ملفك الشخصي\n"
            "`/server` — معلومات السيرفر"
        )

    elif category == "moderation":

        title = "🛡️ Lunex — Moderation"

        description = (
            "`/clear` — حذف الرسائل"
        )

    else:

        title = "⚙️ Lunex — Administration"

        description = (
            "`/language` — إعداد اللغة\n"
            "`/level_roll` — إعداد رتب المستويات"
        )

    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blurple()
    )


class HelpCategorySelect(
    discord.ui.Select
):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="General",
                value="general",
                emoji="🏠"
            ),

            discord.SelectOption(
                label="XP & Levels",
                value="xp",
                emoji="⭐"
            ),

            discord.SelectOption(
                label="Profile",
                value="profile",
                emoji="👤"
            ),

            discord.SelectOption(
                label="Moderation",
                value="moderation",
                emoji="🛡️"
            ),

            discord.SelectOption(
                label="Administration",
                value="admin",
                emoji="⚙️"
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
        interaction
    ):

        embed = build_help_embed(
            self.values[0]
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
            timeout=120
        )

        self.add_item(
            HelpCategorySelect()
        )


# ============================================================
# /COMMANDS
# ============================================================

@bot.tree.command(
    name="commands",
    description="عرض قائمة أوامر Lunex"
)
async def commands_command(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🌙 LUNEX COMMANDS",
        description=(
            "مرحبًا بك في مركز أوامر **Lunex**.\n\n"
            "اختر القسم من القائمة بالأسفل."
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="📚 الأقسام",
        value=(
            "🏠 General\n"
            "⭐ XP & Levels\n"
            "👤 Profile\n"
            "🛡️ Moderation\n"
            "⚙️ Administration"
        ),
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
        title="🌙 LUNEX HELP CENTER",
        description=(
            "**أهلًا بك في Lunex!**\n\n"
            "اختر القسم المناسب من القائمة "
            "لعرض أوامره."
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="📂 Categories",
        value=(
            "🏠 General\n"
            "⭐ XP & Levels\n"
            "👤 Profile\n"
            "🛡️ Moderation\n"
            "⚙️ Administration"
        ),
        inline=False
    )

    embed.set_footer(
        text="Lunex • !help"
    )

    await ctx.send(
        embed=embed,
        view=HelpView()
    )


# ============================================================
# /LANGUAGE
# ============================================================

@bot.tree.command(
    name="language",
    description="تغيير لغة البوت"
)
@app_commands.describe(
    language="اختر اللغة"
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
            "❌ تحتاج صلاحية Manage Server.",
            ephemeral=True
        )

        return

    await set_language(
        interaction.guild.id,
        language.value
    )

    await interaction.response.send_message(
        TEXT[language.value][
            "language_changed"
        ]
    )


# ============================================================
# /XP
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

    language = await get_language(
        interaction.guild.id
    )

    await interaction.response.send_message(

        f"⭐ **{TEXT[language]['xp']}**\n\n"
        f"XP: **{data['xp']}**\n"
        f"Level: **{data['level']}**\n"
        f"Messages: **{data['total_messages']}**"
    )


# ============================================================
# /LEVEL
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

        f"⭐ **Level {data['level']}**\n"
        f"✨ XP: **{data['xp']}**"
    )


# ============================================================
# /ME
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
# /PROFILE
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
        color=discord.Color.blurple()
    )

    embed.set_thumbnail(
        url=interaction.user.display_avatar.url
    )

    embed.description = (
        f"**User:** {interaction.user.mention}\n\n"
        f"⭐ Level: **{data['level']}**\n"
        f"✨ XP: **{data['xp']}**\n"
        f"💬 Messages: **{data['total_messages']}**"
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /SERVER
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
        value=str(guild.member_count)
    )

    embed.add_field(
        name="💬 Channels",
        value=str(len(guild.channels))
    )

    embed.add_field(
        name="🎭 Roles",
        value=str(len(guild.roles))
    )

    embed.add_field(
        name="🆔 ID",
        value=str(guild.id)
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /REGISTER
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

    language = await get_language(
        interaction.guild.id
    )

    await interaction.response.send_message(
        "✅ " +
        TEXT[language]["registered"],
        ephemeral=True
    )


# ============================================================
# /CLEAR
# ============================================================

@bot.tree.command(
    name="clear",
    description="حذف عدد من الرسائل"
)
@app_commands.describe(
    amount="عدد الرسائل من 1 إلى 100"
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
            "❌ تحتاج صلاحية Manage Messages.",
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
            "❌ حدث خطأ أثناء حذف الرسائل.",
            ephemeral=True
        )


# ============================================================
# /LEVEL_ROLL
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
            "❌ تحتاج صلاحية Manage Server.",
            ephemeral=True
        )

        return

    if role.is_default():

        await interaction.response.send_message(
            "❌ لا يمكن اختيار رتبة @everyone.",
            ephemeral=True
        )

        return

    bot_member = interaction.guild.me

    if bot_member:

        if role >= bot_member.top_role:

            await interaction.response.send_message(
                "❌ رتبة البوت يجب أن تكون أعلى من الرتبة المحددة.",
                ephemeral=True
            )

            return

    await set_level_role(
        interaction.guild.id,
        level,
        role.id
    )

    await interaction.response.send_message(

        f"🎉 تم إعداد مكافأة المستوى!\n\n"
        f"⭐ Level: **{level}**\n"
        f"🎭 Role: {role.mention}"
    )


# ============================================================
# LEADERBOARD
# ============================================================

async def get_leaderboard(
    guild_id,
    period
):

    allowed_columns = {

        "day":
            "daily_xp",

        "week":
            "weekly_xp",

        "month":
            "monthly_xp",

        "all":
            "xp"
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
        (
            int(guild_id),
        )
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

        "day":
            "🏆 TOP DAY",

        "week":
            "🏆 TOP WEEK",

        "month":
            "🏆 TOP MONTH",

        "all":
            "🏆 TOP"
    }

    description = ""

    medals = [
        "🥇",
        "🥈",
        "🥉"
    ]

    for index, (
        user_id,
        value
    ) in enumerate(rows):

        member = interaction.guild.get_member(
            int(user_id)
        )

        if member:

            name = member.display_name

        else:

            name = f"User {user_id}"

        if index < 3:

            position = medals[index]

        else:

            position = f"`#{index + 1}`"

        description += (
            f"{position} "
            f"**{name}** — "
            f"`{value} XP`\n"
        )

    embed = discord.Embed(
        title=titles.get(
            period,
            "🏆 TOP"
        ),
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
# /TOP
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


# ============================================================
# /TOP_DAY
# ============================================================

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


# ============================================================
# /TOP_WEEK
# ============================================================

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
# MESSAGE XP
# ============================================================

@bot.event
async def on_message(
    message: discord.Message
):

    if message.author.bot:
        return

    if message.guild:

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
                        f"وصل إلى المستوى **{new_level}**!"
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
# BOT READY
# ============================================================

@bot.event
async def on_ready():

    print(
        "========================================"
    )

    print(
        f"🌙 Lunex logged in as "
        f"{bot.user} ({bot.user.id})"
    )

    print(
        f"🏠 Servers: {len(bot.guilds)}"
    )

    print(
        "========================================"
    )


# ============================================================
# STARTUP
# ============================================================

async def startup():

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
            "⚠️ MongoDB connection failed:",
            repr(e)
        )

    try:

        synced = await bot.tree.sync()

        print(
            f"✅ Synced {len(synced)} slash commands."
        )

    except Exception as e:

        print(
            "❌ Slash command sync error:",
            repr(e)
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
