import hmac
import secrets
from functools import wraps

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash

from .db import get_db
from .security_logging import log_security_event


auth = Blueprint("auth", __name__, url_prefix="/api/auth")


def ensure_csrf_token():
    token = session.get("_csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def csrf_protected(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return view(*args, **kwargs)
        payload = request.get_json(silent=True) or {}
        supplied = (
            request.form.get("csrf_token")
            or request.headers.get("X-CSRF-Token")
            or payload.get("csrf_token")
        )
        expected = session.get("_csrf_token")
        if not expected or not supplied or not hmac.compare_digest(supplied, expected):
            log_security_event("csrf.rejected", reason="missing_or_invalid_token")
            if request.is_json:
                return jsonify({"error": "csrf token required"}), 403
            return "CSRF token required", 403
        return view(*args, **kwargs)

    return wrapped


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
        log_security_event(
            "auth.login_failed",
            interface="api",
            username_present=bool(payload.get("username")),
        )
        return jsonify({"error": "invalid credentials"}), 401
    session.clear()
    session["user_id"] = user["id"]
    ensure_csrf_token()
    log_security_event("auth.login_succeeded", interface="api", role=user["role"])
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


@auth.get("/csrf")
@login_required
def csrf():
    return jsonify({"csrf_token": ensure_csrf_token()})
