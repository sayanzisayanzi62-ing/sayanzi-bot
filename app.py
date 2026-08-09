import os
import threading
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, redirect, jsonify
from flask_cors import CORS

from utils.auth import sign_token, auth_required
from db import get_settings, update_settings, serialize
from bot import bot, post_ticket_panel
import asyncio

CLIENT_ID = os.environ["DISCORD_CLIENT_ID"]
CLIENT_SECRET = os.environ["DISCORD_CLIENT_SECRET"]
REDIRECT_URI = os.environ["DISCORD_REDIRECT_URI"]
FRONTEND_URL = os.environ["FRONTEND_URL"]
ADMINISTRATOR = 0x8

app = Flask(__name__)
CORS(app, origins=[FRONTEND_URL])


@app.route("/")
def home():
    return "Lunex API is running ✅"


# ---------- تسجيل الدخول عبر Discord ----------

@app.route("/auth/login")
def login():
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds"
    }
    return redirect(f"https://discord.com/oauth2/authorize?{urlencode(params)}")


@app.route("/auth/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return redirect(f"{FRONTEND_URL}/index.html?error=no_code")

    try:
        token_res = requests.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        token_res.raise_for_status()
        access_token = token_res.json()["access_token"]

        user_res = requests.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_res.raise_for_status()
        user = user_res.json()

        token = sign_token({
            "discordId": user["id"],
            "username": user["username"],
            "accessToken": access_token
        })
        return redirect(f"{FRONTEND_URL}/dashboard.html?token={token}")
    except Exception as e:
        print("OAuth callback error:", e)
        return redirect(f"{FRONTEND_URL}/index.html?error=auth_failed")


# ---------- إدارة السيرفرات ----------

@app.route("/api/guilds")
@auth_required
def list_guilds():
    try:
        res = requests.get(
            "https://discord.com/api/users/@me/guilds",
            headers={"Authorization": f"Bearer {request.user['accessToken']}"}
        )
        res.raise_for_status()
        guilds = res.json()

        result = []
        for g in guilds:
            perms = int(g["permissions"])
            if perms & ADMINISTRATOR:
                icon = (
                    f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png"
                    if g.get("icon") else None
                )
                result.append({
                    "id": g["id"],
                    "name": g["name"],
                    "icon": icon,
                    "botPresent": bot.get_guild(int(g["id"])) is not None
                })
        return jsonify(result)
    except Exception as e:
        print("list guilds error:", e)
        return jsonify({"error": "تعذر جلب السيرفرات"}), 500


def get_bot_guild(guild_id: str):
    return bot.get_guild(int(guild_id))


@app.route("/api/guilds/<guild_id>/channels")
@auth_required
def get_channels(guild_id):
    guild = get_bot_guild(guild_id)
    if not guild:
        return jsonify({"error": "البوت مو موجود بهذا السيرفر"}), 404
    channels = [{"id": str(c.id), "name": c.name} for c in guild.text_channels]
    return jsonify(channels)


@app.route("/api/guilds/<guild_id>/categories")
@auth_required
def get_categories(guild_id):
    guild = get_bot_guild(guild_id)
    if not guild:
        return jsonify({"error": "البوت مو موجود بهذا السيرفر"}), 404
    categories = [{"id": str(c.id), "name": c.name} for c in guild.categories]
    return jsonify(categories)


@app.route("/api/guilds/<guild_id>/settings", methods=["GET"])
@auth_required
def read_settings(guild_id):
    guild = get_bot_guild(guild_id)
    if not guild:
        return jsonify({"error": "البوت مو موجود بهذا السيرفر"}), 404
    return jsonify(serialize(get_settings(guild_id)))


@app.route("/api/guilds/<guild_id>/settings", methods=["POST"])
@auth_required
def write_settings(guild_id):
    guild = get_bot_guild(guild_id)
    if not guild:
        return jsonify({"error": "البوت مو موجود بهذا السيرفر"}), 404

    body = request.get_json(force=True) or {}
    update = {k: body[k] for k in ("welcome", "leave", "ticket", "autoReplies", "commandAliases") if k in body}
    return jsonify(serialize(update_settings(guild_id, update)))


@app.route("/api/guilds/<guild_id>/known-commands")
@auth_required
def known_commands(guild_id):
    from db import EDITABLE_COMMANDS
    return jsonify(EDITABLE_COMMANDS)


@app.route("/api/guilds/<guild_id>/ticket/post", methods=["POST"])
@auth_required
def post_ticket(guild_id):
    guild = get_bot_guild(guild_id)
    if not guild:
        return jsonify({"error": "البوت مو موجود بهذا السيرفر"}), 404

    channel_id = (request.get_json(force=True) or {}).get("channelId")
    if not channel_id:
        return jsonify({"error": "اختر روم أولاً"}), 400

    try:
        future = asyncio.run_coroutine_threadsafe(
            post_ticket_panel(guild_id, channel_id), bot.loop
        )
        future.result(timeout=10)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


def run_bot():
    bot.run(os.environ["DISCORD_BOT_TOKEN"])


if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
