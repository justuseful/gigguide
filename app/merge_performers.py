from .db import get_db


def merge_performers(keep_slug: str, remove_slug: str) -> tuple[int, str, str]:
    """Move all gig links from one performer onto another, then delete the
    emptied-out performer. For when the same act ends up as two rows - e.g.
    a typo'd or "Matt"/"Matthew"-style name variant picked up by the Echo
    scrape. Keeps whichever performer's slug/name/bio you point it at;
    doesn't try to guess which is "correct"."""
    db = get_db()
    keep = db.execute("SELECT id, name FROM performers WHERE slug = ?", (keep_slug,)).fetchone()
    remove = db.execute("SELECT id, name FROM performers WHERE slug = ?", (remove_slug,)).fetchone()
    if keep is None:
        raise ValueError(f"No performer with slug {keep_slug!r}")
    if remove is None:
        raise ValueError(f"No performer with slug {remove_slug!r}")
    if keep["id"] == remove["id"]:
        raise ValueError("Both slugs point at the same performer.")

    gigs = db.execute("SELECT gig_id FROM gig_performers WHERE performer_id = ?", (remove["id"],)).fetchall()
    moved = 0
    for row in gigs:
        cur = db.execute(
            "INSERT OR IGNORE INTO gig_performers (gig_id, performer_id) VALUES (?, ?)",
            (row["gig_id"], keep["id"]),
        )
        moved += cur.rowcount
    db.execute("DELETE FROM performers WHERE id = ?", (remove["id"],))
    db.commit()
    return moved, keep["name"], remove["name"]
