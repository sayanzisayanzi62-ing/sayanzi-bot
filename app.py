# =========================================
# LUNEX API — WEBSITE + DISCORD BOT
# Railway Optimized
# =========================================

import os
import aiosqlite
import asyncio
import threading

import requests
import discord

from dotenv import load_dotenv
from flask import (
    Flask,
    request,
    redirect,
    jsonify
)
from flask_cors import CORS

from utils.auth import (
    sign_token,
    auth_required
)

from bot import (
    bot,
    get_settings,
    update_settings,
    post_ticket_panel
)


# =========================================
# ENV
# =========================================

load_dotenv()

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
FRONTEND_URL = os.getenv("FRONTEND_URL")
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")


# =========================================
# ENV VALIDATION
# =========================================

required_env = {
    "DISCORD_CLIENT_ID": CLIENT_ID,
    "DISCORD_CLIENT_SECRET": CLIENT_SECRET,
    "DISCORD_REDIRECT_URI": REDIRECT_URI,
    "FRONTEND_URL": FRONTEND_URL,
    "DISCORD_BOT_TOKEN": BOT_TOKEN,
}

missing_env = [
    key
    for key, value in required_env.items()
    if not value
]

if missing_env:
    raise RuntimeError(
        "Missing environment variables: "
        + ", ".join(missing_env)
    )


# =========================================
# FLASK
# =========================================

app = Flask(__name__)

CORS(
    app,
    origins=[
        FRONTEND_URL
    ],
    supports_credentials=True
)


# =========================================
# HELPERS
# =========================================

def serialize(value):
    """
    Convert MongoDB/Python values
    into JSON-safe values.
    """

    if isinstance(value, dict):

        return {
            str(k): serialize(v)
            for k, v in value.items()
            if k != "_id"
        }

    if isinstance(value, list):

        return [
            serialize(v)
            for v in value
        ]

    # ObjectId-like values
    if hasattr(value, "to_json"):

        try:
            return str(value)
        except Exception:
            pass

    # Datetime
    if hasattr(value, "isoformat"):

        try:
            return value.isoformat()
        except Exception:
            pass

    return value


def get_bot_guild(guild_id: str):

    try:

        return bot.get_guild(
            int(guild_id)
        )

    except (
        ValueError,
        TypeError,
        Exception
    ):

        return None


def bot_has_guild(guild_id: str):

    return (
        get_bot_guild(guild_id)
        is not None
    )


def current_user_can_manage_guild(guild_id: str):

    """
    Basic protection:
    make sure the logged-in Discord user
    is actually an administrator of the guild.

    This uses the guilds returned by Discord OAuth.
    """

    try:

        access_token = request.user.get(
            "accessToken"
        )

        if not access_token:
            return False

        response = requests.get(
            "https://discord.com/api/users/@me/guilds",

            headers={
                "Authorization":
                    f"Bearer {access_token}"
            },

            timeout=10
        )

        if response.status_code != 200:
            return False

        guilds = response.json()

        for guild in guilds:

            if guild.get("id") != str(guild_id):
                continue

            permissions = int(
                guild.get(
                    "permissions",
                    0
                )
            )

            return bool(
                permissions & 0x8
            )

        return False

    except Exception as e:

        print(
            "Permission check error:",
            repr(e)
        )

        return False


def require_guild_access(guild_id):

    """
    Validate:
    1. Bot is in guild.
    2. Logged-in user is administrator.
    """

    guild = get_bot_guild(
        guild_id
    )

    if not guild:

        return None, (
            jsonify({
                "error":
                    "البوت غير موجود في السيرفر."
            }),
            404
        )

    if not current_user_can_manage_guild(
        guild_id
    ):

        return None, (
            jsonify({
                "error":
                    "ليس لديك صلاحية إدارة هذا السيرفر."
            }),
            403
        )

    return guild, None


# =========================================
# HOME
# =========================================

@app.route("/")
def home():

    return jsonify({
        "ok": True,
        "name": "Lunex API",
        "status": "running"
    })


# =========================================
# HEALTH CHECK
# =========================================

@app.route("/health")
def health():

    return jsonify({
        "ok": True,
        "api": "online",
        "bot": bot.is_ready()
    })


# =========================================
# DISCORD OAUTH LOGIN
# =========================================

@app.route("/auth/login")
def login():

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds"
    }

    url = (
        "https://discord.com/oauth2/authorize?"
        + requests.compat.urlencode(
            params
        )
    )

    return redirect(url)


# =========================================
# OAUTH CALLBACK
# =========================================

@app.route("/auth/callback")
def callback():

    code = request.args.get(
        "code"
    )

    if not code:

        return redirect(
            f"{FRONTEND_URL}/index.html"
            "?error=missing_code"
        )

    try:

        # ---------------------------------
        # Exchange code for access token
        # ---------------------------------

        token_response = requests.post(

            "https://discord.com/api/oauth2/token",

            data={
                "client_id":
                    CLIENT_ID,

                "client_secret":
                    CLIENT_SECRET,

                "grant_type":
                    "authorization_code",

                "code":
                    code,

                "redirect_uri":
                    REDIRECT_URI
            },

            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded"
            },

            timeout=10
        )

        token_response.raise_for_status()

        token_data = (
            token_response.json()
        )

        access_token = token_data.get(
            "access_token"
        )

        if not access_token:
            raise RuntimeError(
                "Discord did not return access token."
            )

        # ---------------------------------
        # Get Discord user
        # ---------------------------------

        user_response = requests.get(

            "https://discord.com/api/users/@me",

            headers={
                "Authorization":
                    f"Bearer {access_token}"
            },

            timeout=10
        )

        user_response.raise_for_status()

        user = user_response.json()

        # ---------------------------------
        # Create Lunex JWT
        # ---------------------------------

        token = sign_token({

            "discordId":
                user["id"],

            "username":
                user.get(
                    "username",
                    ""
                ),

            "accessToken":
                access_token
        })

        # ---------------------------------
        # Redirect dashboard
        # ---------------------------------

        return redirect(

            f"{FRONTEND_URL}"
            f"/dashboard?token={token}"

        )

    except Exception as e:

        print(
            "OAuth callback error:",
            repr(e)
        )

        return redirect(

            f"{FRONTEND_URL}"
            "/index.html?error=oauth_failed"

        )


# =========================================
# GET USER GUILDS
# =========================================

@app.route(
    "/api/guilds"
)
@auth_required
def list_guilds():

    try:

        access_token = request.user.get(
            "accessToken"
        )

        if not access_token:

            return jsonify({
                "error":
                    "Discord access token غير موجود."
            }), 401

        response = requests.get(

            "https://discord.com/api/users/@me/guilds",

            headers={
                "Authorization":
                    f"Bearer {access_token}"
            },

            timeout=10
        )

        response.raise_for_status()

        guilds = response.json()

        result = []

        for guild in guilds:

            permissions = int(
                guild.get(
                    "permissions",
                    0
                )
            )

            # Administrator
            if not (
                permissions & 0x8
            ):
                continue

            icon = None

            if guild.get("icon"):

                icon = (

                    "https://cdn.discordapp.com/"
                    f"icons/{guild['id']}/"
                    f"{guild['icon']}.png"

                )

            result.append({

                "id":
                    guild["id"],

                "name":
                    guild["name"],

                "icon":
                    icon,

                "botPresent":
                    bot_has_guild(
                        guild["id"]
                    )

            })

        return jsonify(
            result
        )

    except Exception as e:

        print(
            "Guild list error:",
            repr(e)
        )

        return jsonify({

            "error":
                "تعذر جلب السيرفرات."

        }), 500


# =========================================
# CHANNELS
# =========================================

@app.route(
    "/api/guilds/<guild_id>/channels"
)
@auth_required
def get_channels(guild_id):

    guild, error = require_guild_access(
        guild_id
    )

    if error:
        return error

    channels = []

    for channel in guild.channels:

        if isinstance(
            channel,
            discord.TextChannel
        ):

            channels.append({

                "id":
                    str(channel.id),

                "name":
                    channel.name,

                "type":
                    "text",

                "categoryId":
                    (
                        str(channel.category_id)
                        if channel.category_id
                        else None
                    )

            })

    return jsonify(
        channels
    )


# =========================================
# CATEGORIES
# =========================================

@app.route(
    "/api/guilds/<guild_id>/categories"
)
@auth_required
def get_categories(guild_id):

    guild, error = require_guild_access(
        guild_id
    )

    if error:
        return error

    categories = []

    for category in guild.categories:

        categories.append({

            "id":
                str(category.id),

            "name":
                category.name

        })

    return jsonify(
        categories
    )


# =========================================
# ROLES
# =========================================

@app.route(
    "/api/guilds/<guild_id>/roles"
)
@auth_required
def get_roles(guild_id):

    guild, error = require_guild_access(
        guild_id
    )

    if error:
        return error

    roles = []

    for role in guild.roles:

        if role.is_default():
            continue

        roles.append({

            "id":
                str(role.id),

            "name":
                role.name,

            "position":
                role.position,

            "color":
                role.color.value

        })

    return jsonify(
        roles
    )


# =========================================
# GET SETTINGS
# =========================================

@app.route(
    "/api/guilds/<guild_id>/settings",
    methods=["GET"]
)
@auth_required
def read_settings(guild_id):

    guild, error = require_guild_access(
        guild_id
    )

    if error:
        return error

    try:

        settings = get_settings(
            guild_id
        )

        # If get_settings somehow
        # returns None
        if settings is None:
            settings = {}

        return jsonify(
            serialize(settings)
        )

    except Exception as e:

        print(
            "Read settings error:",
            repr(e)
        )

        return jsonify({

            "error":
                "تعذر قراءة إعدادات السيرفر."

        }), 500


# =========================================
# UPDATE SETTINGS
# =========================================

@app.route(
    "/api/guilds/<guild_id>/settings",
    methods=["POST", "PUT"]
)
@auth_required
def write_settings(guild_id):

    guild, error = require_guild_access(
        guild_id
    )

    if error:
        return error

    body = request.get_json(
        silent=True
    ) or {}

    allowed = {

        "welcome":
            body.get("welcome"),

        "leave":
            body.get("leave"),

        "ticket":
            body.get("ticket"),

        "autoReplies":
            body.get("autoReplies"),

        "commandAliases":
            body.get("commandAliases")

    }

    update = {

        key: value

        for key, value in allowed.items()

        if value is not None

    }

    if not update:

        return jsonify({

            "error":
                "لا توجد إعدادات للتحديث."

        }), 400

    try:

        result = update_settings(

            guild_id,
            update

        )

        return jsonify(
            serialize(result)
        )

    except Exception as e:

        print(
            "Update settings error:",
            repr(e)
        )

        return jsonify({

            "error":
                "تعذر تحديث الإعدادات."

        }), 500


# =========================================
# TICKET SETTINGS
# =========================================

@app.route(
    "/api/guilds/<guild_id>/ticket",
    methods=["GET"]
)
@auth_required
def ticket_settings(guild_id):

    guild, error = require_guild_access(
        guild_id
    )

    if error:
        return error

    try:

        settings = get_settings(
            guild_id
        )

        if not settings:
            settings = {}

        ticket = settings.get(
            "ticket",
            {}
        )

        return jsonify(
            serialize(ticket)
        )

    except Exception as e:

        print(
            "Ticket settings error:",
            repr(e)
        )

        return jsonify({

            "error":
                "تعذر قراءة إعدادات التذاكر."

        }), 500


# =========================================
# UPDATE TICKET SETTINGS
# =========================================

@app.route(
    "/api/guilds/<guild_id>/ticket",
    methods=["POST", "PUT"]
)
@auth_required
def update_ticket_settings(guild_id):

    guild, error = require_guild_access(
        guild_id
    )

    if error:
        return error

    body = request.get_json(
        silent=True
    ) or {}

    allowed_fields = [

        "enabled",
        "channelId",
        "image",
        "message",
        "description",

        "categoryId",
        "closedCategoryId",

        "supportRoleId",

        "allowUserClose",
        "deleteAfterClose"

    ]

    ticket_update = {}

    for field in allowed_fields:

        if field in body:

            ticket_update[field] = body[field]

    if not ticket_update:

        return jsonify({

            "error":
                "لم يتم إرسال إعدادات."

        }), 400

    # =====================================
    # Validate channel
    # =====================================

    if ticket_update.get(
        "channelId"
    ):

        try:

            channel_id = int(
                ticket_update[
                    "channelId"
                ]
            )

        except (
            ValueError,
            TypeError
        ):

            return jsonify({

                "error":
                    "channelId غير صحيح."

            }), 400

        channel = guild.get_channel(
            channel_id
        )

        if not channel:

            return jsonify({

                "error":
                    "روم التذاكر غير موجود."

            }), 400

        if not isinstance(
            channel,
            discord.TextChannel
        ):

            return jsonify({

                "error":
                    "روم التذاكر يجب أن يكون روم نصي."

            }), 400

    # =====================================
    # Validate categories
    # =====================================

    for field in (
        "categoryId",
        "closedCategoryId"
    ):

        value = ticket_update.get(
            field
        )

        if value:

            try:

                category_id = int(
                    value
                )

            except (
                ValueError,
                TypeError
            ):

                return jsonify({

                    "error":
                        f"{field} غير صحيح."

                }), 400

            category = guild.get_channel(
                category_id
            )

            if not isinstance(
                category,
                discord.CategoryChannel
            ):

                return jsonify({

                    "error":
                        f"{field} غير صحيح."

                }), 400

    # =====================================
    # Validate support role
    # =====================================

    role_id = ticket_update.get(
        "supportRoleId"
    )

    if role_id:

        try:

            role = guild.get_role(
                int(role_id)
            )

        except (
            ValueError,
            TypeError
        ):

            role = None

        if not role:

            return jsonify({

                "error":
                    "رتبة الدعم غير موجودة."

            }), 400

    # =====================================
    # Save
    # =====================================

    try:

        old_settings = get_settings(
            guild_id
        ) or {}

        old_ticket = old_settings.get(
            "ticket",
            {}
        ) or {}

        new_ticket = {
            **old_ticket,
            **ticket_update
        }

        result = update_settings(

            guild_id,

            {
                "ticket":
                    new_ticket
            }

        )

        return jsonify({

            "ok":
                True,

            "ticket":
                serialize(
                    result.get(
                        "ticket",
                        new_ticket
                    )
                )

        })

    except Exception as e:

        print(
            "Update ticket settings error:",
            repr(e)
        )

        return jsonify({

            "error":
                "تعذر حفظ إعدادات التذاكر."

        }), 500


# =========================================
# POST TICKET PANEL
# =========================================

@app.route(
    "/api/guilds/<guild_id>/ticket/post",
    methods=["POST"]
)
@auth_required
def post_ticket(guild_id):

    guild, error = require_guild_access(
        guild_id
    )

    if error:
        return error

    body = request.get_json(
        silent=True
    ) or {}

    channel_id = body.get(
        "channelId"
    )

    if not channel_id:

        return jsonify({

            "error":
                "يجب اختيار روم التذاكر."

        }), 400

    try:

        channel_id_int = int(
            channel_id
        )

    except (
        ValueError,
        TypeError
    ):

        return jsonify({

            "error":
                "معرف الروم غير صحيح."

        }), 400

    channel = guild.get_channel(
        channel_id_int
    )

    if not channel:

        return jsonify({

            "error":
                "الروم غير موجود."

        }), 404

    if not isinstance(
        channel,
        discord.TextChannel
    ):

        return jsonify({

            "error":
                "الروم يجب أن يكون روم نصي."

        }), 400

    # =====================================
    # Discord event loop
    # =====================================

    if not bot.is_ready():

        return jsonify({

            "error":
                "Discord bot غير جاهز بعد."

        }), 503

    loop = bot.loop

    if loop is None:

        return jsonify({

            "error":
                "Discord bot event loop غير جاهز."

        }), 503

    try:

        future = (
            asyncio
            .run_coroutine_threadsafe(

                post_ticket_panel(

                    guild_id,
                    str(channel_id)

                ),

                loop

            )
        )

        future.result(
            timeout=20
        )

        return jsonify({

            "ok":
                True,

            "message":
                "تم نشر لوحة التذاكر بنجاح."

        })

    except asyncio.TimeoutError:

        return jsonify({

            "error":
                "انتهى وقت انتظار Discord."

        }), 504

    except Exception as e:

        print(
            "Post ticket error:",
            repr(e)
        )

        return jsonify({

            "error":
                "تعذر نشر لوحة التذاكر."

        }), 500


# =========================================
# BOT THREAD
# =========================================

def run_bot():

    print(
        "🚀 Starting Discord bot..."
    )

    try:

        bot.run(
            BOT_TOKEN
        )

    except Exception as e:

        print(
            "❌ Discord bot crashed:",
            repr(e)
        )


# =========================================
# START
# =========================================

if __name__ == "__main__":

    # -------------------------------------
    # Start Discord bot
    # -------------------------------------

    bot_thread = threading.Thread(

        target=run_bot,

        daemon=True,

        name="DiscordBotThread"

    )

    bot_thread.start()

    print(
        "🌐 Starting Lunex API..."
    )

    # -------------------------------------
    # Railway PORT
    # -------------------------------------

    port = int(
        os.getenv(
            "PORT",
            "5000"
        )
    )

    # -------------------------------------
    # Start Flask
    # -------------------------------------

    app.run(

        host="0.0.0.0",

        port=port,

        debug=False,

        use_reloader=False,

        threaded=True

    )
