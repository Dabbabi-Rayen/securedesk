import os

from flask import Flask, redirect, url_for

from .auth import auth, ensure_csrf_token
from .db import close_db, init_db
from .tickets import tickets
from .web import web


def create_app(test_config=None):
    app = Flask(__name__)
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key and not (test_config and test_config.get("TESTING")):
        raise RuntimeError("SECRET_KEY must be configured")

    app.config.from_mapping(
        SECRET_KEY=secret_key or "test-only-secret-key",
        DATABASE=os.environ.get("DATABASE", "instance/securedesk.sqlite"),
        TESTING=False,
    )

    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)
    app.context_processor(lambda: {"csrf_token": ensure_csrf_token()})
    with app.app_context():
        init_db()

    app.register_blueprint(tickets)
    app.register_blueprint(auth)
    app.register_blueprint(web)

    @app.get("/")
    def index():
        return redirect(url_for("web.login"))

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    return app
