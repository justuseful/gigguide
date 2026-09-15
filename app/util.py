import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import current_app


def today_local() -> date:
    return datetime.now(ZoneInfo(current_app.config["TIMEZONE"])).date()


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "item"


def unique_slug(db, table: str, base: str, exclude_id: int | None = None) -> str:
    # `table` is always a hardcoded literal from our own code, never user input.
    slug, n = base, 2
    while True:
        row = db.execute(f"SELECT id FROM {table} WHERE slug = ?", (slug,)).fetchone()
        if row is None or row["id"] == exclude_id:
            return slug
        slug = f"{base}-{n}"
        n += 1
