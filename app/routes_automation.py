import hmac

from flask import Blueprint, current_app, jsonify, request

from .db import get_db
from .genres import GENRES, parse_genres
from .link_performers import link_gig_performers
from .routes_admin import parse_social_url, parse_youtube_id
from .util import today_local

bp = Blueprint("automation", __name__)


def _authorized() -> bool:
    token = current_app.config.get("AUTOMATION_TOKEN")
    if not token:
        return False
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    return hmac.compare_digest(auth.removeprefix("Bearer ").strip(), token)


@bp.post("/gigs")
def add_gig():
    """Insert-only endpoint for the scheduled venue-website cross-check agent.

    Deliberately narrow: bearer-token gated, can only add a gig (never edit
    or delete), and reuses the same dedup key the admin form and importers
    use (venue + date + title) so a re-run is always safe to repeat.
    """
    if not _authorized():
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True, silent=True) or {}
    venue_slug = (data.get("venue_slug") or "").strip()
    title = (data.get("title") or "").strip()
    gig_date = (data.get("gig_date") or "").strip()
    if not venue_slug or not title or not gig_date:
        return jsonify({"error": "venue_slug, title and gig_date are required"}), 400

    db = get_db()
    venue = db.execute("SELECT id FROM venues WHERE slug = ?", (venue_slug,)).fetchone()
    if venue is None:
        return jsonify({"error": f"no venue with slug '{venue_slug}'"}), 404

    exists = db.execute(
        "SELECT id FROM gigs WHERE venue_id = ? AND gig_date = ? AND title = ?",
        (venue["id"], gig_date, title),
    ).fetchone()
    if exists:
        return jsonify({"status": "skipped", "reason": "already exists", "id": exists["id"]}), 200

    try:
        youtube_id = parse_youtube_id(data.get("youtube_id") or "") or None
        social_url = parse_social_url(data.get("social_url") or "") or None
        genre = parse_genres(data.get("genre")) if data.get("genre") else None
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    cur = db.execute(
        "INSERT INTO gigs (venue_id, title, gig_date, start_time, price, ticket_url, "
        "description, is_jam_night, youtube_id, social_url, genre, source) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,'auto-check')",
        (
            venue["id"], title, gig_date,
            (data.get("start_time") or None),
            (data.get("price") or None),
            (data.get("ticket_url") or None),
            (data.get("description") or None),
            1 if data.get("is_jam_night") else 0,
            youtube_id,
            social_url,
            genre,
        ),
    )
    link_gig_performers(db, cur.lastrowid, title)
    db.commit()
    return jsonify({"status": "added", "id": cur.lastrowid}), 201


@bp.get("/untagged-performers")
def untagged_performers():
    """Performers with upcoming gigs but no genre yet, busiest first, so the
    scheduled agent can look each one up and tag it via the endpoint below."""
    if not _authorized():
        return jsonify({"error": "unauthorized"}), 401
    limit = min(request.args.get("limit", 40, type=int), 100)
    rows = get_db().execute(
        "SELECT p.slug, p.name, COUNT(*) AS upcoming FROM performers p "
        "JOIN gig_performers gp ON gp.performer_id = p.id JOIN gigs g ON g.id = gp.gig_id "
        "WHERE g.gig_date >= ? AND (p.genre IS NULL OR p.genre = '') "
        "GROUP BY p.id ORDER BY upcoming DESC, p.name LIMIT ?",
        (today_local().isoformat(), limit),
    ).fetchall()
    return jsonify({
        "genres": [slug for slug, _ in GENRES],
        "performers": [{"slug": r["slug"], "name": r["name"], "upcoming": r["upcoming"]} for r in rows],
    })


@bp.post("/performers/<slug>/genre")
def set_performer_genre(slug):
    """Tag a performer's genre, but only if it has none yet - it never overwrites a
    genre a human set. Same narrow, safe-to-repeat contract as the gig endpoint."""
    if not _authorized():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    try:
        genre = parse_genres(data.get("genre"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not genre:
        return jsonify({"error": "genre is required"}), 400
    db = get_db()
    row = db.execute("SELECT id, genre FROM performers WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        return jsonify({"error": f"no performer with slug '{slug}'"}), 404
    if row["genre"]:
        return jsonify({"status": "skipped", "reason": "already tagged", "genre": row["genre"]}), 200
    db.execute("UPDATE performers SET genre = ? WHERE id = ?", (genre, row["id"]))
    db.commit()
    return jsonify({"status": "tagged", "genre": genre}), 200
