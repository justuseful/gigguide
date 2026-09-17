from flask import abort, flash, redirect, render_template, request, url_for

from .auth import check_csrf
from .comments import list_comments, submit_comment
from .db import get_db
from .routes_public import bp

STORY_COLUMNS = "id, slug, title, category, excerpt, body, hero_image, youtube_id, social_url, published_at"


@bp.get("/stories")
def stories():
    db = get_db()
    rows = db.execute(
        f"SELECT {STORY_COLUMNS} FROM stories WHERE published = 1 ORDER BY published_at DESC"
    ).fetchall()
    return render_template("stories.html", stories=rows)


@bp.get("/stories/<slug>")
def story(slug):
    db = get_db()
    row = db.execute(
        f"SELECT {STORY_COLUMNS} FROM stories WHERE slug = ? AND published = 1", (slug,)
    ).fetchone()
    if row is None:
        abort(404)
    top_comments, replies = list_comments("story", row["id"])
    return render_template("story.html", story=row, top_comments=top_comments, replies=replies)


@bp.post("/stories/<slug>/comments")
def story_comment(slug):
    check_csrf()
    db = get_db()
    row = db.execute("SELECT id FROM stories WHERE slug = ? AND published = 1", (slug,)).fetchone()
    if row is None:
        abort(404)
    accepted, message = submit_comment("story", row["id"], request.form)
    flash(message, "ok" if accepted else "error")
    return redirect(url_for("public.story", slug=slug) + "#comments")
