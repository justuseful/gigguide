from flask import flash, redirect, render_template, request, url_for

from .db import get_db
from .routes_admin import bp, parse_social_url, parse_youtube_id
from .util import slugify, unique_slug


def _performer_form_data() -> dict:
    f = request.form
    return {
        "name": (f.get("name") or "").strip(),
        "bio": (f.get("bio") or "").strip() or None,
        "instagram": (f.get("instagram") or "").strip().lstrip("@") or None,
        "website": (f.get("website") or "").strip() or None,
        "youtube": (f.get("youtube") or "").strip(),
        "social": (f.get("social") or "").strip(),
    }


def _validate_performer(data: dict) -> list[str]:
    errors = []
    if not data["name"]:
        errors.append("Performer name is required.")
    try:
        data["youtube_id"] = parse_youtube_id(data["youtube"]) or None
    except ValueError as exc:
        errors.append(str(exc))
    try:
        data["social_url"] = parse_social_url(data["social"]) or None
    except ValueError as exc:
        errors.append(str(exc))
    return errors


@bp.get("/performers")
def performers():
    db = get_db()
    rows = db.execute(
        "SELECT p.*, "
        "(SELECT COUNT(*) FROM gig_performers gp JOIN gigs g ON g.id = gp.gig_id "
        " WHERE gp.performer_id = p.id) AS gig_count "
        "FROM performers p ORDER BY p.name"
    ).fetchall()
    return render_template("admin/performers.html", performers=rows)


@bp.route("/performers/new", methods=["GET", "POST"])
def performer_new():
    db = get_db()
    if request.method == "POST":
        data = _performer_form_data()
        errors = _validate_performer(data)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("admin/performer_form.html", performer=data, is_new=True), 400
        slug = unique_slug(db, "performers", slugify(data["name"]))
        db.execute(
            "INSERT INTO performers (slug, name, bio, instagram, website, youtube_id, social_url) "
            "VALUES (?,?,?,?,?,?,?)",
            (slug, data["name"], data["bio"], data["instagram"], data["website"], data["youtube_id"],
             data["social_url"]),
        )
        db.commit()
        flash("Performer added.", "ok")
        return redirect(request.args.get("next") or url_for("admin.performers"))
    return render_template("admin/performer_form.html", performer={}, is_new=True)


@bp.route("/performers/<int:performer_id>/edit", methods=["GET", "POST"])
def performer_edit(performer_id):
    db = get_db()
    performer = db.execute("SELECT * FROM performers WHERE id = ?", (performer_id,)).fetchone()
    if performer is None:
        return render_template("404.html"), 404
    if request.method == "POST":
        data = _performer_form_data()
        errors = _validate_performer(data)
        if errors:
            for message in errors:
                flash(message, "error")
            data["id"] = performer_id
            return render_template("admin/performer_form.html", performer=data, is_new=False), 400
        db.execute(
            "UPDATE performers SET name=?, bio=?, instagram=?, website=?, youtube_id=?, social_url=? WHERE id=?",
            (data["name"], data["bio"], data["instagram"], data["website"], data["youtube_id"],
             data["social_url"], performer_id),
        )
        db.commit()
        flash("Performer updated.", "ok")
        return redirect(url_for("admin.performers"))
    return render_template("admin/performer_form.html", performer=performer, is_new=False)


@bp.post("/performers/<int:performer_id>/delete")
def performer_delete(performer_id):
    db = get_db()
    db.execute("DELETE FROM performers WHERE id = ?", (performer_id,))
    db.commit()
    flash("Performer deleted.", "ok")
    return redirect(url_for("admin.performers"))
