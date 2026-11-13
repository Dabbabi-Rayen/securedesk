from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash

from .auth import can_access_ticket, current_user
from .db import get_db


web = Blueprint("web", __name__)


def web_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("web.login"))
        return view(*args, **kwargs)

    return wrapped


def staff_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return redirect(url_for("web.staff_login"))
        if user["role"] not in ("technician", "admin"):
            flash("This area is for support staff.", "error")
            return redirect(url_for("web.dashboard"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return redirect(url_for("web.staff_login"))
        if user["role"] != "admin":
            flash("Administrator access is required.", "error")
            return redirect(url_for("web.staff_dashboard"))
        return view(*args, **kwargs)

    return wrapped


@web.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?",
            (request.form.get("username", ""),),
        ).fetchone()
        if user is not None and user["role"] == "client" and check_password_hash(
            user["password_hash"], request.form.get("password", "")
        ):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("web.dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@web.route("/signup", methods=("GET", "POST"))
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirmation = request.form.get("confirmation", "")
        if len(username) < 3 or len(password) < 8:
            flash("Username must have 3 characters and password 8 characters.", "error")
        elif password != confirmation:
            flash("Passwords do not match.", "error")
        else:
            database = get_db()
            try:
                cursor = database.execute(
                    """
                    INSERT INTO users (username, password_hash, role)
                    VALUES (?, ?, 'client')
                    """,
                    (username, generate_password_hash(password)),
                )
                database.commit()
            except database.IntegrityError:
                flash("That username is already in use.", "error")
            else:
                session.clear()
                session["user_id"] = cursor.lastrowid
                return redirect(url_for("web.dashboard"))
    return render_template("signup.html")


@web.route("/staff/login", methods=("GET", "POST"))
def staff_login():
    if request.method == "POST":
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?",
            (request.form.get("username", ""),),
        ).fetchone()
        if user is not None and user["role"] in ("technician", "admin") and check_password_hash(
            user["password_hash"], request.form.get("password", "")
        ):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("web.staff_dashboard"))
        flash("Invalid staff credentials.", "error")
    return render_template("staff_login.html")


@web.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("web.login"))


@web.get("/dashboard")
@web_login_required
def dashboard():
    tickets = get_db().execute(
        """
        SELECT tickets.*, users.username AS client_username
        FROM tickets
        JOIN users ON users.id = tickets.client_id
        WHERE tickets.client_id = ?
           OR ? IN ('technician', 'admin')
        ORDER BY tickets.id DESC
        """,
        (current_user()["id"], current_user()["role"]),
    ).fetchall()
    return render_template("dashboard.html", tickets=tickets, user=current_user())


@web.get("/staff")
@staff_required
def staff_dashboard():
    tickets = get_db().execute(
        """
        SELECT tickets.*, users.username AS client_username
        FROM tickets JOIN users ON users.id = tickets.client_id
        ORDER BY tickets.id DESC
        """
    ).fetchall()
    user_count = get_db().execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    return render_template(
        "staff_dashboard.html",
        tickets=tickets,
        user=current_user(),
        user_count=user_count,
    )


@web.get("/admin")
@admin_required
def admin_dashboard():
    users = get_db().execute(
        "SELECT id, username, role FROM users ORDER BY role, username"
    ).fetchall()
    return render_template("admin_dashboard.html", users=users, user=current_user())


@web.route("/tickets/new", methods=("GET", "POST"))
@web_login_required
def new_ticket():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        if not title or not description:
            flash("Title and description are required.", "error")
        else:
            database = get_db()
            cursor = database.execute(
                "INSERT INTO tickets (title, description, client_id) VALUES (?, ?, ?)",
                (title, description, current_user()["id"]),
            )
            database.commit()
            return redirect(url_for("web.ticket_detail", ticket_id=cursor.lastrowid))
    return render_template("new_ticket.html", user=current_user())


@web.route("/tickets/<int:ticket_id>", methods=("GET", "POST"))
@web_login_required
def ticket_detail(ticket_id):
    database = get_db()
    ticket = database.execute(
        """
        SELECT tickets.*, users.username AS client_username
        FROM tickets JOIN users ON users.id = tickets.client_id
        WHERE tickets.id = ?
        """,
        (ticket_id,),
    ).fetchone()
    if ticket is None:
        return "Ticket not found", 404
    if not can_access_ticket(ticket):
        return "Ticket not found", 404

    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if not body:
            flash("Comment cannot be empty.", "error")
        else:
            database.execute(
                "INSERT INTO comments (ticket_id, author_id, body) VALUES (?, ?, ?)",
                (ticket_id, current_user()["id"], body),
            )
            database.commit()
            return redirect(url_for("web.ticket_detail", ticket_id=ticket_id))

    comments = database.execute(
        """
        SELECT comments.*, users.username AS author_username
        FROM comments JOIN users ON users.id = comments.author_id
        WHERE ticket_id = ? ORDER BY comments.id
        """,
        (ticket_id,),
    ).fetchall()
    return render_template(
        "ticket_detail.html",
        ticket=ticket,
        comments=comments,
        user=current_user(),
    )
