import json

from .db import get_db
from .util import slugify, unique_slug


def import_venues(json_file: str) -> tuple[int, int]:
    """Bulk-import venues from a JSON file with a top-level "venues" list of
    {"town": ..., "name": ...} objects. Idempotent: venues already present
    (matched by name + town, case-insensitive) are skipped, so this is safe
    to re-run against a fresher export from the same source."""
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    db = get_db()
    existing = {
        (row["name"].strip().lower(), row["town"].strip().lower())
        for row in db.execute("SELECT name, town FROM venues").fetchall()
    }

    added = skipped = 0
    for entry in data["venues"]:
        name = entry["name"].strip()
        town = entry["town"].strip()
        key = (name.lower(), town.lower())
        if key in existing:
            skipped += 1
            continue
        slug = unique_slug(db, "venues", slugify(name))
        db.execute(
            "INSERT INTO venues (slug, name, town) VALUES (?, ?, ?)",
            (slug, name, town),
        )
        existing.add(key)
        added += 1

    db.commit()
    return added, skipped
