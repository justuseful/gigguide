from .db import get_db
from .link_performers import get_or_create_performer, refresh_pro_featuring_for_performer

FIELDS = {
    "bio", "youtube_id", "social_url", "related_performers", "website", "instagram",
    "based_in", "booking", "is_pro", "pro_until",
}
# Fields where 0/False is a meaningful value, not "clear this field" - unlike the
# text fields, an empty string doesn't apply to them.
BOOLEAN_FIELDS = {"is_pro"}


def update_performer(slug: str, **fields) -> str:
    """Set one or more of a performer's profile fields directly (e.g. for one-off
    content added from a video/story or found via web research, rather than
    through the admin form). Pass an empty string for a text field to clear it;
    fields left out of `fields` are untouched."""
    unknown = set(fields) - FIELDS
    if unknown:
        raise ValueError(f"Unknown field(s): {', '.join(sorted(unknown))}")
    if not fields:
        raise ValueError(f"Nothing to update - pass one or more of: {', '.join(sorted(FIELDS))}")

    db = get_db()
    performer = db.execute("SELECT id, name FROM performers WHERE slug = ?", (slug,)).fetchone()
    if performer is None:
        raise ValueError(f"No performer with slug {slug!r}")

    updates = ", ".join(f"{field} = ?" for field in fields)
    params = [
        int(value) if field in BOOLEAN_FIELDS else (value or None)
        for field, value in fields.items()
    ] + [performer["id"]]
    db.execute(f"UPDATE performers SET {updates} WHERE id = ?", params)
    if fields.get("is_pro"):
        refresh_pro_featuring_for_performer(db, performer["id"])
    db.commit()
    return performer["name"]


def ensure_performer(name: str) -> tuple[str, bool]:
    """Find-or-create a performer by name. Returns (slug, was_newly_created)."""
    db = get_db()
    performer_id, created = get_or_create_performer(db, name)
    db.commit()
    slug = db.execute("SELECT slug FROM performers WHERE id = ?", (performer_id,)).fetchone()["slug"]
    return slug, created
