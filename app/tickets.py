from flask import Blueprint, jsonify, request, Response
from markupsafe import escape

from .auth import can_access_ticket, current_user, login_required
from .db import get_db


tickets = Blueprint("tickets", __name__, url_prefix="/api/tickets")


def serialize_ticket(ticket):
    return dict(ticket)


@tickets.post("")
@login_required
def create_ticket():
    payload = request.get_json(silent=True) or {}
    title = payload.get("title", "").strip()
    description = payload.get("description", "").strip()

    if not title or not description:
        return jsonify({"error": "title and description are required"}), 400

    database = get_db()
    cursor = database.execute(
        "INSERT INTO tickets (title, description, client_id) VALUES (?, ?, ?)",
        (title, description, current_user()["id"]),
    )
    database.commit()
    ticket = database.execute(
        "SELECT * FROM tickets WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return jsonify(serialize_ticket(ticket)), 201


@tickets.get("")
@login_required
def list_tickets():
    ticket_rows = get_db().execute(
        "SELECT * FROM tickets ORDER BY id DESC"
    ).fetchall()
    return jsonify([serialize_ticket(ticket) for ticket in ticket_rows])


@tickets.get("/search")
@login_required
def search_tickets():
    query = request.args.get("q", "")
    rows = get_db().execute(
        f"SELECT * FROM tickets WHERE title LIKE '%{query}%' "
        "OR description LIKE '%{query}%' ORDER BY id DESC"
    ).fetchall()
    return jsonify([serialize_ticket(ticket) for ticket in rows])


@tickets.get("/<int:ticket_id>")
@login_required
def get_ticket(ticket_id):
    ticket = get_db().execute(
        "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
    ).fetchone()
    if ticket is None:
        return jsonify({"error": "ticket not found"}), 404
    if not can_access_ticket(ticket):
        return jsonify({"error": "ticket not found"}), 404
    return jsonify(serialize_ticket(ticket))


@tickets.post("/<int:ticket_id>/comments")
@login_required
def add_comment(ticket_id):
    payload = request.get_json(silent=True) or {}
    body = payload.get("body", "").strip()
    if not body:
        return jsonify({"error": "comment body is required"}), 400
    ticket = get_db().execute(
        "SELECT id, client_id FROM tickets WHERE id = ?", (ticket_id,)
    ).fetchone()
    if ticket is None:
        return jsonify({"error": "ticket not found"}), 404
    if not can_access_ticket(ticket):
        return jsonify({"error": "ticket not found"}), 404
    database = get_db()
    cursor = database.execute(
        "INSERT INTO comments (ticket_id, author_id, body) VALUES (?, ?, ?)",
        (ticket_id, current_user()["id"], body),
    )
    database.commit()
    comment = database.execute(
        "SELECT * FROM comments WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return jsonify(dict(comment)), 201


@tickets.get("/<int:ticket_id>/view")
@login_required
def view_ticket(ticket_id):
    ticket = get_db().execute(
        "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
    ).fetchone()
    if ticket is None:
        return jsonify({"error": "ticket not found"}), 404
    if not can_access_ticket(ticket):
        return jsonify({"error": "ticket not found"}), 404
    comments = get_db().execute(
        "SELECT body FROM comments WHERE ticket_id = ? ORDER BY id", (ticket_id,)
    ).fetchall()
    comment_html = "".join(
        f"<li>{escape(comment['body'])}</li>" for comment in comments
    )
    html = (
        f"<h1>{escape(ticket['title'])}</h1>"
        f"<p>{escape(ticket['description'])}</p>"
        f"<ul>{comment_html}</ul>"
    )
    return Response(html, mimetype="text/html")
