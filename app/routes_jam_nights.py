from flask import render_template

from .db import get_db
from .routes_public import GIG_COLUMNS, GIG_FROM, bp
from .util import today_local


@bp.get("/jam-nights")
def jam_nights():
    db = get_db()
    today = today_local().isoformat()
    rows = db.execute(
        f"SELECT {GIG_COLUMNS} {GIG_FROM} "
        "JOIN (SELECT venue_id, title, MIN(gig_date) AS next_date FROM gigs "
        "      WHERE is_jam_night = 1 AND gig_date >= ? GROUP BY venue_id, title) nxt "
        "ON nxt.venue_id = g.venue_id AND nxt.title = g.title AND nxt.next_date = g.gig_date "
        "ORDER BY g.gig_date, g.start_time",
        (today,),
    ).fetchall()
    return render_template("jam_nights.html", gigs=rows)
