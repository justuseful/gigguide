from datetime import timedelta

from flask import Blueprint, abort, current_app, render_template, request, send_from_directory, url_for

from .db import get_db
from .util import today_local

bp = Blueprint("public", __name__)

BOT_HINTS = ("bot", "crawl", "spider", "slurp", "curl", "wget", "python-requests", "headless")

GIG_COLUMNS = """
    g.id, g.venue_id, g.title, g.gig_date, g.start_time, g.price, g.ticket_url,
    g.youtube_id, g.social_url, g.flyer, g.description, g.featured,
    v.name AS venue_name, v.slug AS venue_slug, v.town AS town,
    v.address AS venue_address, v.website AS venue_website, v.instagram AS venue_instagram,
    COALESCE(g.youtube_id, (
        SELECT p.youtube_id FROM gig_performers gp JOIN performers p ON p.id = gp.performer_id
        WHERE gp.gig_id = g.id AND p.youtube_id IS NOT NULL LIMIT 1
    )) AS display_youtube_id,
    COALESCE(g.social_url, (
        SELECT p.social_url FROM gig_performers gp JOIN performers p ON p.id = gp.performer_id
        WHERE gp.gig_id = g.id AND p.social_url IS NOT NULL LIMIT 1
    )) AS display_social_url
"""
GIG_FROM = "FROM gigs g JOIN venues v ON v.id = g.venue_id"


@bp.after_request
def cache_and_count(resp):
    if request.method != "GET" or resp.status_code != 200 or resp.mimetype != "text/html":
        return resp
    resp.headers.setdefault("Cache-Control", "public, max-age=300")
    ua = (request.user_agent.string or "").lower()
    if any(hint in ua for hint in BOT_HINTS):
        return resp
    try:
        db = get_db()
        db.execute(
            "INSERT INTO page_views (day, path, views) VALUES (?, ?, 1) "
            "ON CONFLICT(day, path) DO UPDATE SET views = views + 1",
            (today_local().isoformat(), request.path),
        )
        db.commit()
    except Exception:  # analytics must never break a page
        current_app.logger.exception("page view count failed")
    return resp


@bp.get("/")
def index():
    db = get_db()
    today = today_local()
    rows = db.execute(
        f"SELECT {GIG_COLUMNS} {GIG_FROM} WHERE g.gig_date >= ? "
        "ORDER BY g.gig_date, g.featured DESC, g.start_time, g.title",
        (today.isoformat(),),
    ).fetchall()
    featured = [row for row in rows if row["featured"]][:6]
    groups = []
    for row in rows:
        if not groups or groups[-1][0] != row["gig_date"]:
            groups.append((row["gig_date"], []))
        groups[-1][1].append(row)
    latest_stories = db.execute(
        "SELECT id, slug, title, category, excerpt, hero_image FROM stories "
        "WHERE published = 1 ORDER BY published_at DESC LIMIT 3"
    ).fetchall()
    return render_template(
        "index.html",
        groups=groups,
        featured=featured,
        latest_stories=latest_stories,
        today=today.isoformat(),
        tomorrow=(today + timedelta(days=1)).isoformat(),
    )


@bp.get("/gig/<int:gig_id>")
def gig(gig_id):
    db = get_db()
    row = db.execute(f"SELECT {GIG_COLUMNS} {GIG_FROM} WHERE g.id = ?", (gig_id,)).fetchone()
    if row is None:
        abort(404)
    same_night = db.execute(
        f"SELECT {GIG_COLUMNS} {GIG_FROM} WHERE g.gig_date = ? AND g.id != ? "
        "ORDER BY g.featured DESC, g.start_time, g.title LIMIT 8",
        (row["gig_date"], gig_id),
    ).fetchall()
    more_at_venue = db.execute(
        f"SELECT {GIG_COLUMNS} {GIG_FROM} WHERE g.venue_id = ? AND g.id != ? AND g.gig_date >= ? "
        "ORDER BY g.gig_date, g.start_time LIMIT 6",
        (row["venue_id"], gig_id, today_local().isoformat()),
    ).fetchall()
    performers = db.execute(
        "SELECT p.slug, p.name FROM performers p JOIN gig_performers gp ON gp.performer_id = p.id "
        "WHERE gp.gig_id = ? ORDER BY p.name",
        (gig_id,),
    ).fetchall()
    return render_template(
        "gig.html", gig=row, same_night=same_night, more_at_venue=more_at_venue, performers=performers
    )


@bp.get("/venues")
def venues():
    db = get_db()
    rows = db.execute("SELECT slug, name, town FROM venues ORDER BY name").fetchall()
    options = [
        {"id": r["slug"], "label": f"{r['name']} · {r['town']}", "url": url_for("public.venue", slug=r["slug"])}
        for r in rows
    ]
    return render_template("venues.html", options=options, count=len(options))


@bp.get("/venue/<slug>")
def venue(slug):
    db = get_db()
    row = db.execute("SELECT * FROM venues WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        abort(404)
    gigs = db.execute(
        f"SELECT {GIG_COLUMNS} {GIG_FROM} WHERE g.venue_id = ? AND g.gig_date >= ? "
        "ORDER BY g.gig_date, g.start_time",
        (row["id"], today_local().isoformat()),
    ).fetchall()
    return render_template("venue.html", venue=row, gigs=gigs)


@bp.get("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory(current_app.config["UPLOAD_DIR"], filename, max_age=86400)


@bp.get("/healthz")
def healthz():
    return {"ok": True}


# Registers additional routes (stories, comments, performers, support) onto this same blueprint.
from . import routes_stories  # noqa: E402,F401
from . import routes_performers  # noqa: E402,F401
from . import routes_support  # noqa: E402,F401
