from .db import get_db
from .link_performers import get_or_create_performer

FIELDS = {"bio", "youtube_id", "social_url", "related_performers"}


def update_performer(slug: str, **fields) -> str:
    """Set one or more of a performer's bio/youtube_id/social_url/related_performers
    fields directly (e.g. for one-off content added from a video/story, rather than
    through the admin form). Pass an empty string for a field to clear it; fields left
    out of `fields` are untouched."""
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
    params = [value or None for value in fields.values()] + [performer["id"]]
    db.execute(f"UPDATE performers SET {updates} WHERE id = ?", params)
    db.commit()
    return performer["name"]


def ensure_performer(name: str) -> tuple[str, bool]:
    """Find-or-create a performer by name. Returns (slug, was_newly_created)."""
    db = get_db()
    performer_id, created = get_or_create_performer(db, name)
    db.commit()
    slug = db.execute("SELECT slug FROM performers WHERE id = ?", (performer_id,)).fetchone()["slug"]
    return slug, created
