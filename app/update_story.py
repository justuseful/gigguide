from .db import get_db

FIELDS = {"title", "category", "excerpt", "body", "youtube_id", "social_url", "published"}
BOOLEAN_FIELDS = {"published"}


def update_story(slug: str, **fields) -> str:
    """Set one or more of a story's fields directly (e.g. swapping in a real
    YouTube video once it clears upload processing, rather than through the
    admin form). Pass an empty string for a text field to clear it; fields
    left out of `fields` are untouched."""
    unknown = set(fields) - FIELDS
    if unknown:
        raise ValueError(f"Unknown field(s): {', '.join(sorted(unknown))}")
    if not fields:
        raise ValueError(f"Nothing to update - pass one or more of: {', '.join(sorted(FIELDS))}")

    db = get_db()
    story = db.execute("SELECT id, title FROM stories WHERE slug = ?", (slug,)).fetchone()
    if story is None:
        raise ValueError(f"No story with slug {slug!r}")

    updates = ", ".join(f"{field} = ?" for field in fields) + ", updated_at = datetime('now')"
    params = [
        int(value) if field in BOOLEAN_FIELDS else (value or None)
        for field, value in fields.items()
    ] + [story["id"]]
    db.execute(f"UPDATE stories SET {updates} WHERE id = ?", params)
    db.commit()
    return story["title"]
