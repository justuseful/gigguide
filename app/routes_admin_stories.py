from datetime import datetime, timezone

from flask import flash, redirect, render_template, request, url_for

from .db import get_db
from .images import delete_image, save_image
from .routes_admin import bp, parse_youtube_id
from .util import slugify, unique_slug

CATEGORIES = ["Human of Bundjalung", "Interview", "News", "Story"]


def _story_form_data() -> dict:
    f = request.form
    return {
        "title": (f.get("title") or "").strip(),
        "category": (f.get("category") or "Story").strip(),
        "excerpt": (f.get("excerpt") or "").strip() or None,
        "body": (f.get("body") or "").strip(),
        "youtube": (f.get("youtube") or "").strip(),
        "published": 1 if f.get("published") else 0,
    }


def _validate_story(data: dict) -> list[str]:
    errors = []
    if not data["title"]:
        errors.append("Title is required.")
    if not data["body"]:
        errors.append("Body is required.")
    try:
        data["youtube_id"] = parse_youtube_id(data["youtube"]) or None
    except ValueError as exc:
        errors.append(str(exc))
    return errors


# ---------- stories ----------

@bp.get("/stories")
def stories():
    db = get_db()
    rows = db.execute(
        "SELECT s.id, s.slug, s.title, s.category, s.published, s.published_at, s.created_at, "
        "(SELECT COUNT(*) FROM comments c WHERE c.target_type='story' AND c.target_id=s.id "
        " AND c.status='approved') AS comment_count "
        "FROM stories s ORDER BY s.created_at DESC"
    ).fetchall()
    return render_template("admin/stories.html", stories=rows)


@bp.route("/stories/new", methods=["GET", "POST"])
def story_new():
    if request.method == "POST":
        data = _story_form_data()
        errors = _validate_story(data)
        hero_image = None
        if not errors:
            try:
                hero_image = save_image(request.files.get("hero_image"))
            except ValueError as exc:
                errors.append(str(exc))
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("admin/story_form.html", story=data, categories=CATEGORIES, is_new=True), 400
        db = get_db()
        slug = unique_slug(db, "stories", slugify(data["title"]))
        published_at = datetime.now(timezone.utc).isoformat() if data["published"] else None
        db.execute(
            "INSERT INTO stories (slug, title, category, excerpt, body, hero_image, youtube_id, "
            "published, published_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (slug, data["title"], data["category"], data["excerpt"], data["body"], hero_image,
             data["youtube_id"], data["published"], published_at),
        )
        db.commit()
        flash("Story added.", "ok")
        return redirect(url_for("admin.stories"))
    return render_template("admin/story_form.html", story={}, categories=CATEGORIES, is_new=True)


@bp.route("/stories/<int:story_id>/edit", methods=["GET", "POST"])
def story_edit(story_id):
    db = get_db()
    story = db.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()
    if story is None:
        return render_template("404.html"), 404
    if request.method == "POST":
        data = _story_form_data()
        errors = _validate_story(data)
        new_hero = None
        if not errors:
            try:
                new_hero = save_image(request.files.get("hero_image"))
            except ValueError as exc:
                errors.append(str(exc))
        if errors:
            for message in errors:
                flash(message, "error")
            data["id"] = story_id
            data["hero_image"] = story["hero_image"]
            return render_template("admin/story_form.html", story=data, categories=CATEGORIES, is_new=False), 400
        hero_image = story["hero_image"]
        if new_hero or request.form.get("remove_hero_image"):
            delete_image(story["hero_image"])
            hero_image = new_hero
        published_at = story["published_at"]
        if data["published"] and not published_at:
            published_at = datetime.now(timezone.utc).isoformat()
        elif not data["published"]:
            published_at = None
        db.execute(
            "UPDATE stories SET title=?, category=?, excerpt=?, body=?, hero_image=?, youtube_id=?, "
            "published=?, published_at=?, updated_at=datetime('now') WHERE id=?",
            (data["title"], data["category"], data["excerpt"], data["body"], hero_image,
             data["youtube_id"], data["published"], published_at, story_id),
        )
        db.commit()
        flash("Story updated.", "ok")
        return redirect(url_for("admin.stories"))
    return render_template("admin/story_form.html", story=story, categories=CATEGORIES, is_new=False)


@bp.post("/stories/<int:story_id>/delete")
def story_delete(story_id):
    db = get_db()
    story = db.execute("SELECT hero_image FROM stories WHERE id = ?", (story_id,)).fetchone()
    if story is not None:
        delete_image(story["hero_image"])
        db.execute("DELETE FROM stories WHERE id = ?", (story_id,))
        db.execute("DELETE FROM comments WHERE target_type = 'story' AND target_id = ?", (story_id,))
        db.commit()
        flash("Story deleted.", "ok")
    return redirect(url_for("admin.stories"))


# ---------- comment moderation ----------

@bp.get("/comments")
def comments():
    db = get_db()
    pending = db.execute(
        "SELECT c.*, s.title AS story_title, s.slug AS story_slug FROM comments c "
        "LEFT JOIN stories s ON s.id = c.target_id AND c.target_type = 'story' "
        "WHERE c.status = 'pending' ORDER BY c.created_at"
    ).fetchall()
    recent = db.execute(
        "SELECT c.*, s.title AS story_title, s.slug AS story_slug FROM comments c "
        "LEFT JOIN stories s ON s.id = c.target_id AND c.target_type = 'story' "
        "WHERE c.status != 'pending' ORDER BY c.created_at DESC LIMIT 30"
    ).fetchall()
    return render_template("admin/comments.html", pending=pending, recent=recent)


@bp.post("/comments/<int:comment_id>/approve")
def comment_approve(comment_id):
    db = get_db()
    db.execute("UPDATE comments SET status = 'approved' WHERE id = ?", (comment_id,))
    db.commit()
    flash("Comment approved.", "ok")
    return redirect(url_for("admin.comments"))


@bp.post("/comments/<int:comment_id>/reject")
def comment_reject(comment_id):
    db = get_db()
    db.execute("UPDATE comments SET status = 'spam' WHERE id = ?", (comment_id,))
    db.commit()
    flash("Comment marked as spam.", "ok")
    return redirect(url_for("admin.comments"))


@bp.post("/comments/<int:comment_id>/delete")
def comment_delete(comment_id):
    db = get_db()
    db.execute("DELETE FROM comments WHERE id = ? OR parent_id = ?", (comment_id, comment_id))
    db.commit()
    flash("Comment deleted.", "ok")
    return redirect(url_for("admin.comments"))
