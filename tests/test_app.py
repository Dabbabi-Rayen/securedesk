import re

from app import create_app


def make_client(tmp_path):
    app = create_app(
        {
            "DATABASE": str(tmp_path / "test.sqlite"),
            "TESTING": True,
        }
    )
    return app.test_client()


def login(client, username="client.demo", password="client123"):
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200


def csrf_headers(client):
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.get_json()["csrf_token"]}


def form_csrf_token(client, path):
    response = client.get(path)
    match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
    assert match is not None
    return match.group(1).decode()


def test_index_returns_application_identity():
    client = create_app({"TESTING": True}).test_client()

    response = client.get("/")

    assert response.status_code == 302
    assert response.location.endswith("/login")


def test_health_endpoint(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "healthy"}


def test_create_and_fetch_ticket(tmp_path):
    client = make_client(tmp_path)
    login(client)

    response = client.post(
        "/api/tickets",
        json={"title": "Cannot sign in", "description": "The login page rejects my account."},
        headers=csrf_headers(client),
    )

    assert response.status_code == 201
    ticket = response.get_json()
    assert ticket["title"] == "Cannot sign in"
    assert ticket["status"] == "open"

    detail = client.get(f"/api/tickets/{ticket['id']}")
    assert detail.status_code == 200
    assert detail.get_json() == ticket


def test_ticket_requires_title_and_description(tmp_path):
    client = make_client(tmp_path)
    login(client)

    response = client.post(
        "/api/tickets",
        json={"title": "Incomplete"},
        headers=csrf_headers(client),
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "title and description are required"}


def test_missing_ticket_returns_not_found(tmp_path):
    client = make_client(tmp_path)
    login(client)

    response = client.get("/api/tickets/999")

    assert response.status_code == 404
    assert response.get_json() == {"error": "ticket not found"}


def test_login_exposes_role(tmp_path):
    client = make_client(tmp_path)

    response = client.post(
        "/api/auth/login",
        json={"username": "tech.demo", "password": "tech123"},
    )

    assert response.status_code == 200
    assert response.get_json()["role"] == "technician"


def test_ticket_requires_authentication(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/api/tickets")

    assert response.status_code == 401


def test_authenticated_user_can_add_comment(tmp_path):
    client = make_client(tmp_path)
    login(client)
    ticket = client.post(
        "/api/tickets",
        json={"title": "VPN issue", "description": "Connection fails."},
        headers=csrf_headers(client),
    ).get_json()

    response = client.post(
        f"/api/tickets/{ticket['id']}/comments",
        json={"body": "Please restart the router."},
        headers=csrf_headers(client),
    )

    assert response.status_code == 201
    assert response.get_json()["body"] == "Please restart the router."


def test_client_cannot_access_another_clients_ticket(tmp_path, caplog):
    client = make_client(tmp_path)
    login(client)
    ticket = client.post(
        "/api/tickets",
        json={"title": "Private issue", "description": "Client-only detail."},
        headers=csrf_headers(client),
    ).get_json()

    other_client = make_client(tmp_path)
    signup_token = form_csrf_token(other_client, "/signup")
    other_client.post(
        "/signup",
        data={
            "username": "another.client",
            "password": "another123",
            "confirmation": "another123",
            "csrf_token": signup_token,
        },
    )

    response = other_client.get(f"/api/tickets/{ticket['id']}")

    assert response.status_code == 404
    assert response.get_json() == {"error": "ticket not found"}
    assert any("ticket.access_denied" in record.message for record in caplog.records)


def test_staff_can_access_client_ticket(tmp_path):
    client = make_client(tmp_path)
    login(client)
    ticket = client.post(
        "/api/tickets",
        json={"title": "Support issue", "description": "Needs staff access."},
        headers=csrf_headers(client),
    ).get_json()

    technician = make_client(tmp_path)
    login(technician, "tech.demo", "tech123")

    response = technician.get(f"/api/tickets/{ticket['id']}")

    assert response.status_code == 200
    assert response.get_json()["title"] == "Support issue"


def test_ticket_view_escapes_comment_markup(tmp_path):
    client = make_client(tmp_path)
    login(client)
    ticket = client.post(
        "/api/tickets",
        json={"title": "Browser issue", "description": "Needs investigation."},
        headers=csrf_headers(client),
    ).get_json()
    client.post(
        f"/api/tickets/{ticket['id']}/comments",
        json={"body": "<script>alert('demo')</script>"},
        headers=csrf_headers(client),
    )

    response = client.get(f"/api/tickets/{ticket['id']}/view")

    assert response.status_code == 200
    assert b"<script>alert('demo')</script>" not in response.data
    assert b"&lt;script&gt;alert(&#39;demo&#39;)&lt;/script&gt;" in response.data


def test_ticket_search_treats_sql_payload_as_literal_text(tmp_path, caplog):
    client = make_client(tmp_path)
    login(client)
    client.post(
        "/api/tickets",
        json={"title": "Private ticket", "description": "Internal details."},
        headers=csrf_headers(client),
    )

    normal_response = client.get("/api/tickets/search?q=Private")
    response = client.get("/api/tickets/search?q=%27%20OR%201%3D1%20--")

    assert response.status_code == 200
    assert len(normal_response.get_json()) == 1
    assert response.get_json() == []
    assert any(
        "ticket.search_suspicious" in record.message for record in caplog.records
    )


def test_state_change_requires_csrf_token(tmp_path):
    client = make_client(tmp_path)
    login(client)

    response = client.post(
        "/api/tickets",
        json={"title": "No CSRF token", "description": "Request is accepted."},
    )

    assert response.status_code == 403
    assert response.get_json() == {"error": "csrf token required"}


def test_production_requires_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    try:
        create_app()
    except RuntimeError as error:
        assert str(error) == "SECRET_KEY must be configured"
    else:
        raise AssertionError("create_app() must reject missing SECRET_KEY")


def test_web_login_and_dashboard(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/login")
    assert response.status_code == 200
    assert b"Support, simplified" in response.data
    token = form_csrf_token(client, "/login")

    response = client.post(
        "/login",
        data={
            "username": "client.demo",
            "password": "client123",
            "csrf_token": token,
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Tickets" in response.data
    assert b"New ticket" in response.data


def test_web_can_create_and_comment_on_ticket(tmp_path):
    client = make_client(tmp_path)
    login_token = form_csrf_token(client, "/login")
    client.post(
        "/login",
        data={"username": "client.demo", "password": "client123", "csrf_token": login_token},
    )

    token = form_csrf_token(client, "/tickets/new")
    response = client.post(
        "/tickets/new",
        data={
            "title": "Web ticket",
            "description": "Created in the browser.",
            "csrf_token": token,
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Web ticket" in response.data
    token = form_csrf_token(client, "/tickets/1")
    response = client.post(
        "/tickets/1",
        data={"body": "Browser comment", "csrf_token": token},
        follow_redirects=True,
    )
    assert b"Browser comment" in response.data


def test_client_can_register_and_staff_has_separate_login(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/signup")
    assert response.status_code == 200
    assert b"Create your account" in response.data

    response = client.post(
        "/signup",
        data={
            "username": "new.client",
            "password": "clientpass",
            "confirmation": "clientpass",
            "csrf_token": form_csrf_token(client, "/signup"),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Tickets" in response.data

    client = make_client(tmp_path)
    staff_login_token = form_csrf_token(client, "/login")
    response = client.post(
        "/login",
        data={
            "username": "admin.demo",
            "password": "admin123",
            "csrf_token": staff_login_token,
        },
    )
    assert response.status_code == 200
    assert b"Invalid username or password" in response.data

    response = client.post(
        "/staff/login",
        data={
            "username": "admin.demo",
            "password": "admin123",
            "csrf_token": form_csrf_token(client, "/staff/login"),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    response = client.get("/admin")
    assert response.status_code == 200
    assert b"User directory" in response.data
