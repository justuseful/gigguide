import hmac

from flask import Blueprint, current_app, jsonify, request

from .db import get_db
from .link_performers import link_gig_performers
from .routes_admin import parse_social_url, parse_youtube_id

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
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    cur = db.execute(
        "INSERT INTO gigs (venue_id, title, gig_date, start_time, price, ticket_url, "
        "description, is_jam_night, youtube_id, social_url, source) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,'auto-check')",
        (
            venue["id"], title, gig_date,
            (data.get("start_time") or None),
            (data.get("price") or None),
            (data.get("ticket_url") or None),
            (data.get("description") or None),
            1 if data.get("is_jam_night") else 0,
            youtube_id,
            social_url,
        ),
    )
    link_gig_performers(db, cur.lastrowid, title)
    db.commit()
    return jsonify({"status": "added", "id": cur.lastrowid}), 201
