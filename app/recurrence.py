from datetime import date, timedelta

from .util import today_local

HORIZON_WEEKS = 10


def ensure_recurring_occurrences(db, horizon_weeks: int = HORIZON_WEEKS) -> int:
    """Top up each active weekly series with real gig rows out to the horizon.

    Copies from whichever occurrence is latest in the series (not the original
    row, which may since have had its details edited or even been deleted),
    so edits to price/description/etc. carry forward. Flyers and videos are
    left blank on generated rows - those are usually specific to one date, not
    the series - but performer tags carry forward since the same act/instructor
    usually runs every occurrence."""
    horizon = today_local() + timedelta(weeks=horizon_weeks)
    series = db.execute(
        "SELECT series_id, MAX(gig_date) AS last_date FROM gigs "
        "WHERE recurrence = 'weekly' AND recurrence_active = 1 AND series_id IS NOT NULL "
        "GROUP BY series_id"
    ).fetchall()

    added = 0
    for row in series:
        latest = db.execute(
            "SELECT * FROM gigs WHERE series_id = ? AND gig_date = ? ORDER BY id DESC LIMIT 1",
            (row["series_id"], row["last_date"]),
        ).fetchone()
        performer_ids = [
            r["performer_id"] for r in
            db.execute("SELECT performer_id FROM gig_performers WHERE gig_id = ?", (latest["id"],)).fetchall()
        ]
        next_date = date.fromisoformat(row["last_date"]) + timedelta(days=7)
        while next_date <= horizon:
            cur = db.execute(
                "INSERT INTO gigs (venue_id, title, gig_date, start_time, price, ticket_url, "
                "description, featured, source, recurrence, recurrence_active, series_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    latest["venue_id"], latest["title"], next_date.isoformat(), latest["start_time"],
                    latest["price"], latest["ticket_url"], latest["description"], latest["featured"],
                    "manual", "weekly", 1, row["series_id"],
                ),
            )
            if performer_ids:
                db.executemany(
                    "INSERT OR IGNORE INTO gig_performers (gig_id, performer_id) VALUES (?, ?)",
                    [(cur.lastrowid, pid) for pid in performer_ids],
                )
            added += 1
            next_date += timedelta(days=7)

    if added:
        db.commit()
    return added


def start_series(db, gig_id: int):
    """Turn an existing one-off gig into the first occurrence of a weekly series."""
    db.execute(
        "UPDATE gigs SET recurrence = 'weekly', recurrence_active = 1, series_id = ? WHERE id = ?",
        (gig_id, gig_id),
    )


def stop_series(db, series_id: int) -> int:
    """Stop generating new occurrences and remove any not-yet-happened ones.
    Past and today's occurrences are left alone. Returns the number removed."""
    today = today_local().isoformat()
    db.execute("UPDATE gigs SET recurrence_active = 0 WHERE series_id = ?", (series_id,))
    cur = db.execute("DELETE FROM gigs WHERE series_id = ? AND gig_date > ?", (series_id, today))
    db.commit()
    return cur.rowcount
