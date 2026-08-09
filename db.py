import os
from pymongo import MongoClient

_client = MongoClient(os.environ["MONGODB_URI"])
db = _client.get_default_database()
guild_settings = db["guildsettings"]

DEFAULT_SETTINGS = {
    "welcome": {
        "enabled": False,
        "channelId": None,
        "message": "اهلا [user] فيك بالسيرفر! [ing]"
    },
    "leave": {
        "enabled": False,
        "channelId": None,
        "message": "وداعا [user] :( [ing]"
    },
    "ticket": {
        "enabled": False,
        "image": "",
        "message": "اضغط الزر بالأسفل لفتح تكت جديد",
        "description": "مرحبا [User]، فريق الدعم راح يرد عليك قريبا",
        "categoryId": None,
        "channelId": None
    },
    "autoReplies": [],
    "commandAliases": []
}

# القائمة الثابتة للأوامر اللي ممكن تعطيها اختصار مخصص (أوامر بريفكس ! أو #)
EDITABLE_COMMANDS = [
    {"name": "xp", "description": "XP / النقاط"},
    {"name": "level", "description": "Level / المستوى"},
    {"name": "i", "description": "Profile / الملف الشخصي"},
    {"name": "سيرفر", "description": "Server Info / معلومات السيرفر"},
    {"name": "سجل", "description": "Records / السجل"},
    {"name": "clear", "description": "Clear Messages / مسح رسائل"},
    {"name": "help", "description": "Help Menu / قائمة الأوامر"}
]


def get_settings(guild_id: str) -> dict:
    doc = guild_settings.find_one({"guildId": guild_id})
    if not doc:
        doc = {"guildId": guild_id, **DEFAULT_SETTINGS}
        guild_settings.insert_one(doc)
    return doc


def update_settings(guild_id: str, update: dict) -> dict:
    guild_settings.update_one(
        {"guildId": guild_id},
        {"$set": update, "$setOnInsert": {"guildId": guild_id}},
        upsert=True
    )
    return get_settings(guild_id)


def serialize(doc: dict) -> dict:
    """يحول _id إلى نص عشان يرجع بصيغة JSON بدون مشاكل"""
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc
