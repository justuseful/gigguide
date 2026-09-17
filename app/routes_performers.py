from flask import abort, render_template

from .db import get_db
from .routes_public import GIG_COLUMNS, GIG_FROM, bp
from .util import today_local


@bp.get("/performers")
def performers():
    db = get_db()
    rows = db.execute(
        "SELECT p.*, "
        "(SELECT COUNT(*) FROM gig_performers gp JOIN gigs g ON g.id = gp.gig_id "
        " WHERE gp.performer_id = p.id AND g.gig_date >= ?) AS upcoming "
        "FROM performers p ORDER BY p.name",
        (today_local().isoformat(),),
    ).fetchall()
    return render_template("performers.html", performers=rows)


@bp.get("/performer/<slug>")
def performer(slug):
    db = get_db()
    row = db.execute("SELECT * FROM performers WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        abort(404)
    today = today_local().isoformat()
    upcoming = db.execute(
        f"SELECT {GIG_COLUMNS} {GIG_FROM} JOIN gig_performers gp ON gp.gig_id = g.id "
        "WHERE gp.performer_id = ? AND g.gig_date >= ? ORDER BY g.gig_date, g.start_time",
        (row["id"], today),
    ).fetchall()
    past = db.execute(
        f"SELECT {GIG_COLUMNS} {GIG_FROM} JOIN gig_performers gp ON gp.gig_id = g.id "
        "WHERE gp.performer_id = ? AND g.gig_date < ? ORDER BY g.gig_date DESC LIMIT 12",
        (row["id"], today),
    ).fetchall()
    return render_template("performer.html", performer=row, upcoming=upcoming, past=past)
