import re
from datetime import datetime, timezone

from flask import current_app, session

from .db import get_db

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_SECONDS_BETWEEN_COMMENTS = 20
MAX_BODY_LENGTH = 4000


def list_comments(target_type: str, target_id: int):
    """Returns (top_level_comments, {parent_id: [replies]}) - approved only."""
    db = get_db()
    rows = db.execute(
        "SELECT id, parent_id, author_name, body, created_at FROM comments "
        "WHERE target_type = ? AND target_id = ? AND status = 'approved' "
        "ORDER BY created_at",
        (target_type, target_id),
    ).fetchall()
    top = [r for r in rows if r["parent_id"] is None]
    replies: dict[int, list] = {}
    for r in rows:
        if r["parent_id"] is not None:
            replies.setdefault(r["parent_id"], []).append(r)
    return top, replies


def submit_comment(target_type: str, target_id: int, form) -> tuple[bool, str]:
    """Validates and stores a comment. Returns (accepted, message-to-show)."""
    if (form.get("website") or "").strip():
        # Honeypot field a real visitor never sees or fills in - pretend success, store nothing.
        return True, "Thanks for your comment!"

    now = datetime.now(timezone.utc).timestamp()
    if not current_app.config.get("TESTING"):
        last = session.get("_last_comment_at")
        if last and now - last < MIN_SECONDS_BETWEEN_COMMENTS:
            return False, "You're commenting too quickly - please wait a few seconds and try again."

    name = (form.get("author_name") or "").strip()[:100]
    email = (form.get("author_email") or "").strip()[:200]
    body = (form.get("body") or "").strip()
    parent_id = form.get("parent_id", type=int)

    if not name or not email or not body:
        return False, "Name, email and a comment are required."
    if not EMAIL_RE.match(email):
        return False, "Please enter a valid email address."
    if len(body) > MAX_BODY_LENGTH:
        return False, f"Comment is too long ({MAX_BODY_LENGTH} characters max)."

    db = get_db()
    if parent_id is not None:
        parent = db.execute(
            "SELECT id, parent_id FROM comments WHERE id = ? AND target_type = ? AND target_id = ?",
            (parent_id, target_type, target_id),
        ).fetchone()
        if parent is None or parent["parent_id"] is not None:
            parent_id = None  # only one level of nesting; silently flatten bad/nested replies

    already_trusted = (
        db.execute(
            "SELECT 1 FROM comments WHERE author_email = ? AND status = 'approved' LIMIT 1", (email,)
        ).fetchone()
        is not None
    )
    status = "approved" if already_trusted else "pending"

    db.execute(
        "INSERT INTO comments (target_type, target_id, parent_id, author_name, author_email, body, status) "
        "VALUES (?,?,?,?,?,?,?)",
        (target_type, target_id, parent_id, name, email, body, status),
    )
    db.commit()
    session["_last_comment_at"] = now

    if status == "approved":
        return True, "Comment posted."
    return True, "Thanks! Your first comment is held for a quick review before it appears."
