from flask import abort, render_template, url_for

from .db import get_db
from .routes_public import GIG_COLUMNS, GIG_FROM, bp
from .util import today_local


@bp.get("/performers")
def performers():
    db = get_db()
    rows = db.execute("SELECT slug, name FROM performers ORDER BY name").fetchall()
    options = [
        {"id": r["slug"], "label": r["name"], "url": url_for("public.performer", slug=r["slug"])}
        for r in rows
    ]
    return render_template("performers.html", options=options, count=len(options))


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
    related_slugs = [s.strip() for s in (row["related_performers"] or "").split(",") if s.strip()]
    related = []
    if related_slugs:
        placeholders = ",".join("?" * len(related_slugs))
        related = db.execute(
            f"SELECT name, slug FROM performers WHERE slug IN ({placeholders}) ORDER BY name",
            related_slugs,
        ).fetchall()
    is_pro_active = bool(row["is_pro"]) and (not row["pro_until"] or row["pro_until"] >= today)
    return render_template(
        "performer.html", performer=row, upcoming=upcoming, past=past, related=related, is_pro_active=is_pro_active
    )
