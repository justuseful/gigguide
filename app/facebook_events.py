import re
from datetime import datetime

import requests

from .db import get_db

GRAPH_API = "https://graph.facebook.com/v21.0"


def _parse_fb_datetime(value: str) -> datetime:
    # Facebook sends e.g. "2026-10-05T19:00:00+1100" - Python's fromisoformat
    # wants a colon in the offset on older versions, so normalise it first.
    value = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", value)
    return datetime.fromisoformat(value)


def fetch_page_events(page_id: str, access_token: str) -> list[dict]:
    resp = requests.get(
        f"{GRAPH_API}/{page_id}/events",
        params={
            "access_token": access_token,
            "fields": "id,name,description,start_time,end_time,ticket_uri",
            "time_filter": "upcoming",
        },
        timeout=15,
    )
    if resp.status_code != 200:
        try:
            detail = resp.json()["error"]["message"]
        except (ValueError, KeyError):
            detail = resp.text
        raise RuntimeError(detail)
    return resp.json().get("data", [])


def import_facebook_events(app_id: str, app_secret: str) -> dict[str, dict]:
    """For every venue with a facebook_page_id set, pull its upcoming public
    events and add any not already present. Returns a per-venue report so
    failures are visible rather than silently skipped.

    Each venue can carry its own facebook_page_token (a Page Access Token) -
    that's what lets a Page *you* admin work today, before Meta approves
    anything. Venues without one fall back to the app access token
    (app_id|app_secret), which only works for Pages your app has been
    granted "Page Public Content Access" for."""
    app_access_token = f"{app_id}|{app_secret}" if app_id and app_secret else None
    db = get_db()
    venues = db.execute(
        "SELECT id, name, facebook_page_id, facebook_page_token FROM venues "
        "WHERE facebook_page_id IS NOT NULL AND facebook_page_id != ''"
    ).fetchall()

    report: dict[str, dict] = {}
    for venue in venues:
        token = venue["facebook_page_token"] or app_access_token
        if not token:
            report[venue["name"]] = {
                "error": "No Page Access Token set on this venue, and no FACEBOOK_APP_ID/"
                "FACEBOOK_APP_SECRET configured to fall back to."
            }
            continue
        try:
            events = fetch_page_events(venue["facebook_page_id"], token)
        except Exception as exc:  # noqa: BLE001 - report per venue, don't abort the whole run
            report[venue["name"]] = {"error": str(exc)}
            continue

        existing = {
            (row["gig_date"], row["start_time"], row["title"].strip().lower())
            for row in db.execute(
                "SELECT gig_date, start_time, title FROM gigs WHERE venue_id = ?", (venue["id"],)
            ).fetchall()
        }
        added = 0
        for event in events:
            if not event.get("start_time") or not event.get("name"):
                continue
            dt = _parse_fb_datetime(event["start_time"])
            title = event["name"].strip()
            key = (dt.date().isoformat(), dt.strftime("%H:%M"), title.lower())
            if key in existing:
                continue
            db.execute(
                "INSERT INTO gigs (venue_id, title, gig_date, start_time, ticket_url, description, source) "
                "VALUES (?, ?, ?, ?, ?, ?, 'facebook')",
                (
                    venue["id"], title, dt.date().isoformat(), dt.strftime("%H:%M"),
                    event.get("ticket_uri"), event.get("description"),
                ),
            )
            existing.add(key)
            added += 1
        db.commit()
        report[venue["name"]] = {"added": added, "found": len(events)}

    return report
