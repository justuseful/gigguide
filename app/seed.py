from datetime import timedelta

from .db import get_db
from .util import today_local

# Starter venues. Address/website/Instagram are left blank on purpose so they can
# be filled in from the admin with verified details.
VENUES = [
    ("railway-friendly-bar", "Railway Friendly Bar (The Rails)", "Byron Bay",
     "Byron's long-running live music pub, with bands most nights of the week."),
    ("the-northern", "The Northern", "Byron Bay",
     "Byron Bay's iconic live music room in the Hotel Great Northern."),
    ("beach-hotel", "Beach Hotel", "Byron Bay",
     "Beachfront pub on Main Beach with regular live music."),
]

SAMPLE_GIGS = [
    (0, 1, "19:30", "Free", "Sample gig - delete me: Friday Sessions"),
    (0, 2, "20:00", "$15", "Sample gig - delete me: Saturday Night Live"),
    (1, 3, "18:00", "Free", "Sample gig - delete me: Sunday Session"),
]


def seed(with_samples: bool = False) -> tuple[int, int]:
    db = get_db()
    added_venues = 0
    for slug, name, town, description in VENUES:
        if db.execute("SELECT 1 FROM venues WHERE slug = ?", (slug,)).fetchone():
            continue
        db.execute(
            "INSERT INTO venues (slug, name, town, description) VALUES (?, ?, ?, ?)",
            (slug, name, town, description),
        )
        added_venues += 1

    added_gigs = 0
    if with_samples and db.execute("SELECT COUNT(*) FROM gigs").fetchone()[0] == 0:
        venue_ids = [row["id"] for row in db.execute("SELECT id FROM venues ORDER BY id")]
        today = today_local()
        for venue_index, days_ahead, start, price, title in SAMPLE_GIGS:
            db.execute(
                "INSERT INTO gigs (venue_id, title, gig_date, start_time, price, description) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    venue_ids[venue_index % len(venue_ids)],
                    title,
                    (today + timedelta(days=days_ahead)).isoformat(),
                    start,
                    price,
                    "This is sample data so the site isn't empty. Delete it from the admin.",
                ),
            )
            added_gigs += 1

    db.commit()
    return added_venues, added_gigs
