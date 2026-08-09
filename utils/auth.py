import os
from functools import wraps

import jwt
from flask import request, jsonify


def sign_token(payload: dict) -> str:
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


def verify_token(token: str):
    try:
        return jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
    except Exception:
        return None


def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else None
        if not token:
            return jsonify({"error": "غير مسجل دخول"}), 401

        data = verify_token(token)
        if not data:
            return jsonify({"error": "الجلسة منتهية، سجل دخول من جديد"}), 401

        request.user = data
        return f(*args, **kwargs)
    return wrapper
