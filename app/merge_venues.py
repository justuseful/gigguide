from .db import get_db


def merge_venues(keep_slug: str, remove_slug: str) -> tuple[int, str, str]:
    """Move all gigs from one venue onto another, then delete the emptied-out
    venue. For when the same real-world venue ends up as two rows - e.g. a
    manually-entered venue and a differently-named one picked up by the Echo
    scrape. Keeps whichever venue's slug/name/description you point it at;
    doesn't try to guess which is "correct"."""
    db = get_db()
    keep = db.execute("SELECT id, name FROM venues WHERE slug = ?", (keep_slug,)).fetchone()
    remove = db.execute("SELECT id, name FROM venues WHERE slug = ?", (remove_slug,)).fetchone()
    if keep is None:
        raise ValueError(f"No venue with slug {keep_slug!r}")
    if remove is None:
        raise ValueError(f"No venue with slug {remove_slug!r}")
    if keep["id"] == remove["id"]:
        raise ValueError("Both slugs point at the same venue.")

    moved = db.execute(
        "UPDATE gigs SET venue_id = ? WHERE venue_id = ?", (keep["id"], remove["id"])
    ).rowcount
    db.execute("DELETE FROM venues WHERE id = ?", (remove["id"],))
    db.commit()
    return moved, keep["name"], remove["name"]
