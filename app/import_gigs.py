import json

from .db import get_db
from .link_performers import link_gig_performers


def import_gigs(json_file: str) -> tuple[int, int, int]:
    """Bulk-import gigs from a JSON file with a top-level "gigs" list of
    {"venue": ..., "town": ..., "title": ..., "gig_date": "YYYY-MM-DD", "start_time": "HH:MM"|null}
    objects, optionally with "description" and "presented_by" (e.g. "Pink Zinc"). A file-level
    "source" string other than a URL (e.g. "pink-zinc") is recorded as each gig's source.
    A gig with "presented_by" that's already listed for the same venue, day and title
    (e.g. from the Echo, at a slightly different time) isn't duplicated - the existing
    listing is credited to the promoter instead. Idempotent: gigs already present (matched by venue + date + time + title,
    case-insensitive) are skipped, so this is safe to re-run against a fresher export
    from the same source. Gigs whose venue isn't found in the venues table are skipped
    and reported separately so they can be added manually. Each newly-added gig also
    gets its performer(s) extracted from the title and linked (see link_performers.py)."""
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    source = data.get("source", "echo")
    if "://" in source:
        source = "echo"  # the Echo exports record their URL as "source"

    db = get_db()
    venue_by_key = {
        (row["name"].strip().lower(), row["town"].strip().lower()): row["id"]
        for row in db.execute("SELECT id, name, town FROM venues").fetchall()
    }
    rows = db.execute("SELECT id, venue_id, gig_date, start_time, title FROM gigs").fetchall()
    existing = {
        (row["venue_id"], row["gig_date"], row["start_time"], row["title"].strip().lower()) for row in rows
    }
    # Same act, venue and day, ignoring start time - for a promoter's list that
    # overlaps the Echo's (whose times sometimes differ by half an hour).
    id_by_day = {(row["venue_id"], row["gig_date"], row["title"].strip().lower()): row["id"] for row in rows}

    added = skipped = unmatched = 0
    for entry in data["gigs"]:
        venue_key = (entry["venue"].strip().lower(), entry["town"].strip().lower())
        venue_id = venue_by_key.get(venue_key)
        if venue_id is None:
            unmatched += 1
            continue

        title = entry["title"].strip()
        gig_date = entry["gig_date"]
        start_time = entry.get("start_time")
        key = (venue_id, gig_date, start_time, title.lower())
        presented_by = entry.get("presented_by")
        day_key = (venue_id, gig_date, title.lower())
        if key in existing or (presented_by and day_key in id_by_day):
            if presented_by and day_key in id_by_day:
                # Already listed (usually from the Echo): just credit the promoter.
                db.execute(
                    "UPDATE gigs SET presented_by = ? WHERE id = ? AND presented_by IS NULL",
                    (presented_by, id_by_day[day_key]),
                )
            skipped += 1
            continue

        cur = db.execute(
            "INSERT INTO gigs (venue_id, title, gig_date, start_time, description, presented_by, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (venue_id, title, gig_date, start_time, entry.get("description"), presented_by, source),
        )
        link_gig_performers(db, cur.lastrowid, title)
        existing.add(key)
        id_by_day[day_key] = cur.lastrowid
        added += 1

    db.commit()
    return added, skipped, unmatched
