import os
import secrets
from pathlib import Path

from flask import Flask, render_template

from . import db as database
from .auth import csrf_token
from .cli import register_cli
from .filters import register_filters
from .routes_admin import bp as admin_bp
from .routes_public import bp as public_bp


def _secret_key(data_dir: Path) -> str:
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    # Dev fallback: persist a generated key so sessions survive restarts.
    key_file = data_dir / "secret_key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32))
        try:
            key_file.chmod(0o600)
        except OSError:
            pass
    return key_file.read_text().strip()


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)

    data_dir = Path(os.environ.get("GIGGUIDE_DATA_DIR") or Path(app.root_path).parent / "data")
    if test_config and test_config.get("DATA_DIR"):
        data_dir = Path(test_config["DATA_DIR"])
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "uploads").mkdir(exist_ok=True)

    app.config.update(
        SECRET_KEY=_secret_key(data_dir),
        DATABASE=str(data_dir / "gigguide.sqlite3"),
        UPLOAD_DIR=str(data_dir / "uploads"),
        ADMIN_USER=os.environ.get("GIGGUIDE_ADMIN_USER", "admin"),
        ADMIN_PASSWORD=os.environ.get("GIGGUIDE_ADMIN_PASSWORD", ""),
        SITE_NAME=os.environ.get("GIGGUIDE_SITE_NAME", "Humans of Bundjalung Gig Guide"),
        SITE_TAGLINE=os.environ.get(
            "GIGGUIDE_SITE_TAGLINE", "Live music across Byron Bay and the Northern Rivers"
        ),
        TIMEZONE=os.environ.get("GIGGUIDE_TIMEZONE", "Australia/Sydney"),
        FACEBOOK_APP_ID=os.environ.get("FACEBOOK_APP_ID", ""),
        FACEBOOK_APP_SECRET=os.environ.get("FACEBOOK_APP_SECRET", ""),
        SUPPORT_PATREON_URL=os.environ.get("GIGGUIDE_PATREON_URL", ""),
        SUPPORT_KOFI_URL=os.environ.get("GIGGUIDE_KOFI_URL", ""),
        SUPPORT_PAYPAL_URL=os.environ.get("GIGGUIDE_PAYPAL_URL", ""),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=os.environ.get("GIGGUIDE_FORCE_HTTPS", "1") == "1",
    )
    if test_config:
        app.config.update(test_config)

    database.init_app(app)
    register_filters(app)
    register_cli(app)
    app.jinja_env.globals["csrf_token"] = csrf_token

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    with app.app_context():
        database.init_db()

    return app
