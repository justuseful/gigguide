import sqlite3

from flask import current_app, g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        g.db = conn
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# Columns added after the initial release. CREATE TABLE IF NOT EXISTS (in schema.sql)
# only covers a fresh database - existing ones need these added by hand.
MIGRATIONS = [
    ("gigs", "recurrence", "TEXT"),
    ("gigs", "recurrence_active", "INTEGER NOT NULL DEFAULT 1"),
    ("gigs", "series_id", "INTEGER"),
    ("gigs", "social_url", "TEXT"),
    ("performers", "social_url", "TEXT"),
    ("stories", "social_url", "TEXT"),
    ("venues", "facebook_page_id", "TEXT"),
]


def _table_exists(db, table: str) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone() is not None


def _migrate(db):
    for table, column, ddl in MIGRATIONS:
        if not _table_exists(db, table):
            continue  # a fresh install creates it with the column already, via schema.sql below
        existing = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db():
    db = get_db()
    # Migrate existing tables *before* schema.sql, since its CREATE INDEX statements
    # reference columns that a pre-existing table won't have yet.
    _migrate(db)
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
