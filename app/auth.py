from functools import wraps

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash

from .db import get_db


auth = Blueprint("auth", __name__, url_prefix="/api/auth")


def current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return get_db().execute(
        "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
    ).fetchone()


def can_access_ticket(ticket, user=None):
    user = user or current_user()
    return user is not None and (
        user["role"] in ("technician", "admin")
        or ticket["client_id"] == user["id"]
    )


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return jsonify({"error": "authentication required"}), 401
        return view(*args, **kwargs)

    return wrapped


@auth.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    user = get_db().execute(
        "SELECT * FROM users WHERE username = ?", (payload.get("username", ""),)
    ).fetchone()
    if user is None or not check_password_hash(
        user["password_hash"], payload.get("password", "")
    ):
        return jsonify({"error": "invalid credentials"}), 401
    session.clear()
    session["user_id"] = user["id"]
    return jsonify({"id": user["id"], "username": user["username"], "role": user["role"]})


@auth.post("/logout")
def logout():
    session.clear()
    return jsonify({"status": "logged out"})


@auth.get("/me")
@login_required
def me():
    user = current_user()
    return jsonify(dict(user))
