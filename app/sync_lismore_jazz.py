"""Sync gigs from the Lismore Jazz Club website (a Squarespace events collection).

Every act the club books is jazz by definition, so besides adding any missing
upcoming concert this also adds the 'jazz' genre tag to each act's performer
profile (never removing an existing genre). Safe to run repeatedly - from cron."""
import html
import json
import re
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from .db import get_db
from .link_performers import link_gig_performers
from .util import today_local

SITE = "https://lismorejazz.org"
FEED = SITE + "/gigs?format=json"
VENUE_SLUG = "lismore-city-bowlo"   # every club concert is a Sunday afternoon here
SYDNEY = ZoneInfo("Australia/Sydney")


def _fetch_events() -> list[dict]:
    req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 (compatible; TheBunjSync/1.0; +https://thebunj.com)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    return (data.get("upcoming") or []) + (data.get("past") or [])


def _text(fragment: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", fragment or ""))
    return re.sub(r"\s+", " ", text).strip()


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _add_jazz(db, performer_id: int) -> bool:
    row = db.execute("SELECT genre FROM performers WHERE id = ?", (performer_id,)).fetchone()
    current = row["genre"] or ""
    if ",jazz," in current:
        return False
    new = current + "jazz," if current else ",jazz,"
    db.execute("UPDATE performers SET genre = ? WHERE id = ?", (new, performer_id))
    return True


def sync() -> dict:
    db = get_db()
    venue = db.execute("SELECT id FROM venues WHERE slug = ?", (VENUE_SLUG,)).fetchone()
    if venue is None:
        raise RuntimeError(f"venue {VENUE_SLUG!r} not found")
    today = today_local().isoformat()
    added, tagged, seen = [], [], 0

    for ev in _fetch_events():
        title = _text(ev.get("title"))
        if not title:
            continue
        seen += 1
        start = datetime.fromtimestamp(int(ev["startDate"]) / 1000, SYDNEY)
        end = datetime.fromtimestamp(int(ev["endDate"]) / 1000, SYDNEY) if ev.get("endDate") else None
        gig_date, start_time = start.date().isoformat(), start.strftime("%H:%M")

        if gig_date >= today:
            first_word = _norm(title).split()[0] if _norm(title) else ""
            clash = [
                r for r in db.execute(
                    "SELECT id, title FROM gigs WHERE venue_id = ? AND gig_date = ?", (venue["id"], gig_date)
                ).fetchall()
                if first_word and first_word in _norm(r["title"])
            ]
            if not clash:
                times = f"{start.strftime('%-I%p').lower()}" + (f"-{end.strftime('%-I%p').lower()}" if end else "")
                blurb = _text(ev.get("excerpt"))[:500]
                desc = f"Lismore Jazz Club Sunday concert, {times}.\n\n{blurb}".strip()
                cur = db.execute(
                    "INSERT INTO gigs (venue_id, title, gig_date, start_time, description, ticket_url, source) "
                    "VALUES (?,?,?,?,?,?,'auto-check')",
                    (venue["id"], title, gig_date, start_time, desc, SITE + (ev.get("fullUrl") or "/gigs")),
                )
                link_gig_performers(db, cur.lastrowid, title)
                added.append(f"{gig_date} {title}")

        # Jazz-by-definition: tag the performer profile for this act, past or future.
        perf = db.execute(
            "SELECT id, name FROM performers WHERE lower(name) = ? OR slug = ?",
            (title.lower(), re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")),
        ).fetchone()
        if perf and _add_jazz(db, perf["id"]):
            tagged.append(perf["name"])

    db.commit()
    return {"events_on_site": seen, "added": added, "tagged_jazz": tagged}
