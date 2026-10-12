from flask import render_template

from .db import get_db
from .routes_public import GIG_COLUMNS, GIG_FROM, bp
from .util import today_local

# gigs.event_kind values shown on the Doofs & Pop-ups page: 'doof', 'house-party', 'pop-up'


@bp.get("/doofs")
def doofs():
    db = get_db()
    today = today_local().isoformat()
    events = db.execute(
        f"SELECT {GIG_COLUMNS} {GIG_FROM} WHERE g.event_kind IS NOT NULL AND g.event_kind != '' "
        "AND g.gig_date >= ? ORDER BY g.gig_date, g.start_time",
        (today,),
    ).fetchall()
    roaming = db.execute(
        "SELECT slug, name, bio, based_in, instagram, booking, youtube_id FROM performers "
        "WHERE is_roaming = 1 ORDER BY name"
    ).fetchall()
    return render_template("doofs.html", events=events, roaming=roaming)
