import re
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from .auth import admin_required, check_csrf
from .db import get_db
from .recurrence import ensure_recurring_occurrences, start_series, stop_series
from .util import slugify, today_local, unique_slug

bp = Blueprint("admin", __name__)

ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp", "gif"}
YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_URL_RE = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})")
INSTAGRAM_URL_RE = re.compile(r"^https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[A-Za-z0-9_-]+/?")
FACEBOOK_HOST_RE = re.compile(r"^https?://(?:www\.|m\.)?(?:facebook\.com|fb\.watch)/")


@bp.before_request
@admin_required
def guard():
    if request.method == "POST":
        check_csrf()


@bp.after_request
def no_store(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------- helpers ----------

def parse_youtube_id(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if YOUTUBE_ID_RE.match(value):
        return value
    match = YOUTUBE_URL_RE.search(value)
    if not match:
        raise ValueError("Couldn't find a YouTube video ID in that link.")
    return match.group(1)


def parse_social_url(value: str) -> str:
    """Accepts a public Instagram post/reel or Facebook post/video link and
    returns it cleaned up, or '' if nothing was entered. Anything else raises."""
    value = (value or "").strip()
    if not value:
        return ""
    if not re.match(r"^https?://", value):
        value = "https://" + value
    if INSTAGRAM_URL_RE.match(value) or FACEBOOK_HOST_RE.match(value):
        return value
    raise ValueError("That doesn't look like an Instagram or Facebook post/video link.")


def save_flyer(file) -> str | None:
    if file is None or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        raise ValueError("Flyer must be an image (png, jpg, webp or gif).")
    name = f"{secrets.token_hex(8)}.{ext}"
    file.save(Path(current_app.config["UPLOAD_DIR"]) / name)
    return name


def delete_flyer(name: str | None):
    if not name:
        return
    try:
        (Path(current_app.config["UPLOAD_DIR"]) / name).unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning("Could not delete flyer %s", name)


def _normalise_time(value: str) -> str:
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).strftime("%H:%M")
        except ValueError:
            continue
    raise ValueError("Start time must be a valid time (HH:MM).")


def _gig_form_data() -> dict:
    f = request.form
    return {
        "venue_id": f.get("venue_id", type=int),
        "title": (f.get("title") or "").strip(),
        "gig_date": (f.get("gig_date") or "").strip(),
        "start_time": (f.get("start_time") or "").strip() or None,
        "price": (f.get("price") or "").strip() or None,
        "ticket_url": (f.get("ticket_url") or "").strip() or None,
        "youtube": (f.get("youtube") or "").strip(),
        "social": (f.get("social") or "").strip(),
        "description": (f.get("description") or "").strip() or None,
        "featured": 1 if f.get("featured") else 0,
        "performer_ids": f.getlist("performer_ids", type=int),
        "repeat_weekly": bool(f.get("repeat_weekly")),
    }


def _validate_gig(data: dict, db) -> list[str]:
    errors = []
    if not data["title"]:
        errors.append("Title is required.")
    if not data["venue_id"] or not db.execute(
        "SELECT 1 FROM venues WHERE id = ?", (data["venue_id"],)
    ).fetchone():
        errors.append("Choose a venue.")
    try:
        date.fromisoformat(data["gig_date"])
    except ValueError:
        errors.append("Date must be a valid date.")
    if data["start_time"]:
        try:
            data["start_time"] = _normalise_time(data["start_time"])
        except ValueError as exc:
            errors.append(str(exc))
    try:
        data["youtube_id"] = parse_youtube_id(data["youtube"]) or None
    except ValueError as exc:
        errors.append(str(exc))
    try:
        data["social_url"] = parse_social_url(data["social"]) or None
    except ValueError as exc:
        errors.append(str(exc))
    return errors


def _venue_choices(db):
    return db.execute("SELECT id, name, town FROM venues ORDER BY name").fetchall()


def _performer_choices(db):
    return db.execute("SELECT id, name FROM performers ORDER BY name").fetchall()


def _set_gig_performers(db, gig_id: int, performer_ids: list[int]):
    db.execute("DELETE FROM gig_performers WHERE gig_id = ?", (gig_id,))
    if performer_ids:
        db.executemany(
            "INSERT OR IGNORE INTO gig_performers (gig_id, performer_id) VALUES (?, ?)",
            [(gig_id, pid) for pid in set(performer_ids)],
        )


# ---------- dashboard ----------

@bp.get("/")
def dashboard():
    db = get_db()
    ensure_recurring_occurrences(db)
    today = today_local().isoformat()
    week_start = (today_local() - timedelta(days=6)).isoformat()
    base = (
        "SELECT g.id, g.title, g.gig_date, g.start_time, g.featured, g.youtube_id, g.series_id, "
        "v.name AS venue_name FROM gigs g JOIN venues v ON v.id = g.venue_id "
    )
    upcoming = db.execute(base + "WHERE g.gig_date >= ? ORDER BY g.gig_date, g.start_time", (today,)).fetchall()
    past = db.execute(base + "WHERE g.gig_date < ? ORDER BY g.gig_date DESC LIMIT 20", (today,)).fetchall()
    total_views = db.execute(
        "SELECT COALESCE(SUM(views), 0) FROM page_views WHERE day >= ?", (week_start,)
    ).fetchone()[0]
    top_pages = db.execute(
        "SELECT path, SUM(views) AS views FROM page_views WHERE day >= ? "
        "GROUP BY path ORDER BY views DESC LIMIT 10",
        (week_start,),
    ).fetchall()
    venue_count = db.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
    pending_comments = db.execute("SELECT COUNT(*) FROM comments WHERE status = 'pending'").fetchone()[0]
    return render_template(
        "admin/dashboard.html",
        upcoming=upcoming,
        past=past,
        total_views=total_views,
        top_pages=top_pages,
        venue_count=venue_count,
        pending_comments=pending_comments,
    )


# ---------- gigs ----------

@bp.route("/gigs/new", methods=["GET", "POST"])
def gig_new():
    db = get_db()
    venues = _venue_choices(db)
    performers = _performer_choices(db)
    if request.method == "POST":
        data = _gig_form_data()
        errors = _validate_gig(data, db)
        flyer = None
        if not errors:
            try:
                flyer = save_flyer(request.files.get("flyer"))
            except ValueError as exc:
                errors.append(str(exc))
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template(
                "admin/gig_form.html", gig=data, venues=venues, performers=performers,
                selected_performer_ids=set(data["performer_ids"]), is_new=True,
            ), 400
        cur = db.execute(
            "INSERT INTO gigs (venue_id, title, gig_date, start_time, price, ticket_url, "
            "youtube_id, social_url, flyer, description, featured) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                data["venue_id"], data["title"], data["gig_date"], data["start_time"], data["price"],
                data["ticket_url"], data["youtube_id"], data["social_url"], flyer, data["description"],
                data["featured"],
            ),
        )
        new_id = cur.lastrowid
        _set_gig_performers(db, new_id, data["performer_ids"])
        if data["repeat_weekly"]:
            start_series(db, new_id)
        db.commit()
        if data["repeat_weekly"]:
            ensure_recurring_occurrences(db)
        flash("Gig added.", "ok")
        return redirect(url_for("admin.dashboard"))
    preset = {"venue_id": request.args.get("venue", type=int)}
    return render_template(
        "admin/gig_form.html", gig=preset, venues=venues, performers=performers,
        selected_performer_ids=set(), is_new=True,
    )


@bp.route("/gigs/<int:gig_id>/edit", methods=["GET", "POST"])
def gig_edit(gig_id):
    db = get_db()
    gig = db.execute("SELECT * FROM gigs WHERE id = ?", (gig_id,)).fetchone()
    if gig is None:
        return render_template("404.html"), 404
    venues = _venue_choices(db)
    performers = _performer_choices(db)
    current_performer_ids = {
        row["performer_id"] for row in
        db.execute("SELECT performer_id FROM gig_performers WHERE gig_id = ?", (gig_id,)).fetchall()
    }
    if request.method == "POST":
        data = _gig_form_data()
        errors = _validate_gig(data, db)
        new_flyer = None
        if not errors:
            try:
                new_flyer = save_flyer(request.files.get("flyer"))
            except ValueError as exc:
                errors.append(str(exc))
        if errors:
            for message in errors:
                flash(message, "error")
            data["id"] = gig_id
            data["flyer"] = gig["flyer"]
            data["series_id"] = gig["series_id"]
            series_weekday = date.fromisoformat(gig["gig_date"]).strftime("%A") if gig["series_id"] else None
            return render_template(
                "admin/gig_form.html", gig=data, venues=venues, performers=performers,
                selected_performer_ids=set(data["performer_ids"]), is_new=False, series_weekday=series_weekday,
            ), 400
        flyer = gig["flyer"]
        if new_flyer or request.form.get("remove_flyer"):
            delete_flyer(gig["flyer"])
            flyer = new_flyer
        db.execute(
            "UPDATE gigs SET venue_id=?, title=?, gig_date=?, start_time=?, price=?, ticket_url=?, "
            "youtube_id=?, social_url=?, flyer=?, description=?, featured=?, updated_at=datetime('now') WHERE id=?",
            (
                data["venue_id"], data["title"], data["gig_date"], data["start_time"], data["price"],
                data["ticket_url"], data["youtube_id"], data["social_url"], flyer, data["description"],
                data["featured"], gig_id,
            ),
        )
        _set_gig_performers(db, gig_id, data["performer_ids"])
        if data["repeat_weekly"] and gig["series_id"] is None:
            start_series(db, gig_id)
        db.commit()
        if data["repeat_weekly"] and gig["series_id"] is None:
            ensure_recurring_occurrences(db)
        flash("Gig updated.", "ok")
        return redirect(url_for("admin.dashboard"))
    series_weekday = None
    if gig["series_id"] is not None:
        series_weekday = date.fromisoformat(gig["gig_date"]).strftime("%A")
    return render_template(
        "admin/gig_form.html", gig=gig, venues=venues, performers=performers,
        selected_performer_ids=current_performer_ids, is_new=False, series_weekday=series_weekday,
    )


@bp.post("/gigs/<int:gig_id>/stop-recurring")
def gig_stop_recurring(gig_id):
    db = get_db()
    gig = db.execute("SELECT series_id FROM gigs WHERE id = ?", (gig_id,)).fetchone()
    if gig is None or gig["series_id"] is None:
        flash("This gig isn't part of a weekly series.", "error")
        return redirect(url_for("admin.dashboard"))
    removed = stop_series(db, gig["series_id"])
    flash(f"Stopped the weekly series ({removed} upcoming occurrence(s) removed).", "ok")
    return redirect(url_for("admin.dashboard"))


@bp.post("/gigs/<int:gig_id>/delete")
def gig_delete(gig_id):
    db = get_db()
    gig = db.execute("SELECT flyer FROM gigs WHERE id = ?", (gig_id,)).fetchone()
    if gig is not None:
        delete_flyer(gig["flyer"])
        db.execute("DELETE FROM gigs WHERE id = ?", (gig_id,))
        db.commit()
        flash("Gig deleted.", "ok")
    return redirect(url_for("admin.dashboard"))


# ---------- venues ----------

def _venue_form_data() -> dict:
    f = request.form
    return {
        "name": (f.get("name") or "").strip(),
        "town": (f.get("town") or "").strip(),
        "address": (f.get("address") or "").strip() or None,
        "website": (f.get("website") or "").strip() or None,
        "instagram": (f.get("instagram") or "").strip().lstrip("@") or None,
        "description": (f.get("description") or "").strip() or None,
        "facebook_page_id": (f.get("facebook_page_id") or "").strip() or None,
    }


def _validate_venue(data: dict) -> list[str]:
    errors = []
    if not data["name"]:
        errors.append("Venue name is required.")
    if not data["town"]:
        errors.append("Town is required.")
    return errors


@bp.get("/venues")
def venues():
    db = get_db()
    rows = db.execute(
        "SELECT v.*, (SELECT COUNT(*) FROM gigs g WHERE g.venue_id = v.id AND g.gig_date >= ?) AS upcoming "
        "FROM venues v ORDER BY v.town, v.name",
        (today_local().isoformat(),),
    ).fetchall()
    return render_template("admin/venues.html", venues=rows)


@bp.route("/venues/new", methods=["GET", "POST"])
def venue_new():
    db = get_db()
    if request.method == "POST":
        data = _venue_form_data()
        errors = _validate_venue(data)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("admin/venue_form.html", venue=data, is_new=True), 400
        slug = unique_slug(db, "venues", slugify(data["name"]))
        db.execute(
            "INSERT INTO venues (slug, name, town, address, website, instagram, description, "
            "facebook_page_id) VALUES (?,?,?,?,?,?,?,?)",
            (slug, data["name"], data["town"], data["address"], data["website"],
             data["instagram"], data["description"], data["facebook_page_id"]),
        )
        db.commit()
        flash("Venue added.", "ok")
        return redirect(url_for("admin.venues"))
    return render_template("admin/venue_form.html", venue={}, is_new=True)


@bp.route("/venues/<int:venue_id>/edit", methods=["GET", "POST"])
def venue_edit(venue_id):
    db = get_db()
    venue = db.execute("SELECT * FROM venues WHERE id = ?", (venue_id,)).fetchone()
    if venue is None:
        return render_template("404.html"), 404
    if request.method == "POST":
        data = _venue_form_data()
        errors = _validate_venue(data)
        if errors:
            for message in errors:
                flash(message, "error")
            data["id"] = venue_id
            return render_template("admin/venue_form.html", venue=data, is_new=False), 400
        db.execute(
            "UPDATE venues SET name=?, town=?, address=?, website=?, instagram=?, description=?, "
            "facebook_page_id=? WHERE id=?",
            (data["name"], data["town"], data["address"], data["website"], data["instagram"],
             data["description"], data["facebook_page_id"], venue_id),
        )
        db.commit()
        flash("Venue updated.", "ok")
        return redirect(url_for("admin.venues"))
    return render_template("admin/venue_form.html", venue=venue, is_new=False)


# Registers additional routes (stories, comment moderation, performers) onto this same blueprint.
from . import routes_admin_stories  # noqa: E402,F401
from . import routes_admin_performers  # noqa: E402,F401
