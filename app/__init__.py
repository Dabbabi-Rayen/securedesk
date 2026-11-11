from flask import Flask, redirect, url_for

from .auth import auth
from .db import close_db, init_db
from .tickets import tickets
from .web import web


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY="dev-only-change-me",
        DATABASE="instance/securedesk.sqlite",
        TESTING=False,
    )

    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)
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
