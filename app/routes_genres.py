from datetime import timedelta

from flask import abort, render_template

from .db import get_db
from .genres import GENRE_LABELS, GENRES, genre_list
from .routes_public import GIG_COLUMNS, GIG_FROM, bp
from .util import today_local


def _upcoming_rows(db):
    today = today_local()
    return today, db.execute(
        f"SELECT {GIG_COLUMNS} {GIG_FROM} WHERE g.gig_date >= ? "
        "ORDER BY g.gig_date, g.featured DESC, g.start_time, g.title",
        (today.isoformat(),),
    ).fetchall()


@bp.get("/genres")
def genres():
    db = get_db()
    _, rows = _upcoming_rows(db)
    counts = {}
    for row in rows:
        for slug, _label in genre_list(row["display_genre"]):
            counts[slug] = counts.get(slug, 0) + 1
    options = [(slug, label, counts.get(slug, 0)) for slug, label in GENRES]
    return render_template("genres.html", options=options)


@bp.get("/genres/<slug>")
def genre(slug):
    if slug not in GENRE_LABELS:
        abort(404)
    db = get_db()
    today, rows = _upcoming_rows(db)
    rows = [r for r in rows if slug in dict(genre_list(r["display_genre"]))]
    groups = []
    for row in rows:
        if not groups or groups[-1][0] != row["gig_date"]:
            groups.append((row["gig_date"], []))
        groups[-1][1].append(row)
    return render_template(
        "genre.html",
        slug=slug,
        label=GENRE_LABELS[slug],
        groups=groups,
        count=len(rows),
        today=today.isoformat(),
        tomorrow=(today + timedelta(days=1)).isoformat(),
    )
