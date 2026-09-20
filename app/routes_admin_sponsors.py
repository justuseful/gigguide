from flask import flash, redirect, render_template, request, url_for

from .db import get_db
from .routes_admin import bp


def _sponsor_form_data() -> dict:
    f = request.form
    return {
        "name": (f.get("name") or "").strip(),
        "url": (f.get("url") or "").strip(),
        "blurb": (f.get("blurb") or "").strip() or None,
        "active": 1 if f.get("active") else 0,
    }


def _validate_sponsor(data: dict) -> list[str]:
    errors = []
    if not data["name"]:
        errors.append("Sponsor name is required.")
    if not data["url"]:
        errors.append("Sponsor link is required.")
    return errors


@bp.get("/sponsors")
def sponsors():
    db = get_db()
    rows = db.execute("SELECT * FROM sponsors ORDER BY active DESC, name").fetchall()
    return render_template("admin/sponsors.html", sponsors=rows)


@bp.route("/sponsors/new", methods=["GET", "POST"])
def sponsor_new():
    if request.method == "POST":
        data = _sponsor_form_data()
        errors = _validate_sponsor(data)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("admin/sponsor_form.html", sponsor=data, is_new=True), 400
        db = get_db()
        db.execute(
            "INSERT INTO sponsors (name, url, blurb, active) VALUES (?,?,?,?)",
            (data["name"], data["url"], data["blurb"], data["active"]),
        )
        db.commit()
        flash("Sponsor added.", "ok")
        return redirect(url_for("admin.sponsors"))
    return render_template("admin/sponsor_form.html", sponsor={"active": 1}, is_new=True)


@bp.route("/sponsors/<int:sponsor_id>/edit", methods=["GET", "POST"])
def sponsor_edit(sponsor_id):
    db = get_db()
    sponsor = db.execute("SELECT * FROM sponsors WHERE id = ?", (sponsor_id,)).fetchone()
    if sponsor is None:
        return render_template("404.html"), 404
    if request.method == "POST":
        data = _sponsor_form_data()
        errors = _validate_sponsor(data)
        if errors:
            for message in errors:
                flash(message, "error")
            data["id"] = sponsor_id
            return render_template("admin/sponsor_form.html", sponsor=data, is_new=False), 400
        db.execute(
            "UPDATE sponsors SET name=?, url=?, blurb=?, active=? WHERE id=?",
            (data["name"], data["url"], data["blurb"], data["active"], sponsor_id),
        )
        db.commit()
        flash("Sponsor updated.", "ok")
        return redirect(url_for("admin.sponsors"))
    return render_template("admin/sponsor_form.html", sponsor=sponsor, is_new=False)


@bp.post("/sponsors/<int:sponsor_id>/delete")
def sponsor_delete(sponsor_id):
    db = get_db()
    db.execute("DELETE FROM sponsors WHERE id = ?", (sponsor_id,))
    db.commit()
    flash("Sponsor deleted.", "ok")
    return redirect(url_for("admin.sponsors"))
