"""Daily server-side sync of the sources that publish structured gig lists.

Runs from cron on the VM so the guide never depends on the cloud routine:
  * Beach Hotel  - WordPress Events Calendar feed (looks 12 weeks ahead)
  * The Rails    - gig-guide page, one act per night
  * The Echo     - GigPress RSS feed (about the next 8 days)

It only ever ADDS gigs (never edits or deletes) and skips anything already on
the same night at the same venue. Video and genre look-ups still need web
search and stay with the cloud routine."""
import html
import json
import re
import urllib.request
from datetime import date, datetime, timedelta

from .db import get_db
from .link_performers import link_gig_performers
from .util import slugify, today_local, unique_slug

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
BEACH_FEED = "https://www.beachhotel.com.au/wp-json/tribe/events/v1/events"
RAILS_PAGE = "https://therailsbyronbay.com/portfolio_page/gig-guide/"
ECHO_FEED = "https://www.echo.net.au/?feed=gigpress"

ECHO_ALIASES = {  # Echo venue name -> our slug, where names differ
    "railway hotel": "railway-friendly-bar",
    "club lennox": "club-lennox",
    "salt stone": "salt-stone",
}
ECHO_SKIP_VENUES = {"the northern"}  # front-bar acts are loaded by hand from the Instagram lineup


def _get(url: str, timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-AU,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower().replace("&", " and ")).strip()


def _tokens(s: str) -> list[str]:
    return [t for t in _norm(s).split() if t not in ("the", "and", "with", "live", "dj")]


class Ctx:
    def __init__(self, db, dry_run: bool):
        self.db, self.dry_run = db, dry_run
        self.log: list[str] = []
        self.added = 0

    def venue_id(self, slug: str):
        row = self.db.execute("SELECT id FROM venues WHERE slug = ?", (slug,)).fetchone()
        return row["id"] if row else None

    def exists(self, venue_id: int, gig_date: str, title: str) -> bool:
        wanted = set(_tokens(title))
        norm_title = _norm(title)
        for row in self.db.execute(
            "SELECT title FROM gigs WHERE venue_id = ? AND gig_date = ?", (venue_id, gig_date)
        ).fetchall():
            other = _norm(row["title"])
            if other == norm_title:
                return True
            first = (_tokens(title) or [""])[0]
            ofirst = (_tokens(row["title"]) or [""])[0]
            if (len(first) >= 3 and first in other.split()) or (len(ofirst) >= 3 and ofirst in norm_title.split()):
                return True
            if wanted and wanted <= set(_tokens(row["title"])):
                return True
        return False

    def add(self, venue_id: int, venue_name: str, gig_date: str, start_time, title: str, description=None,
            ticket_url=None, source="auto-check") -> bool:
        if gig_date < today_local().isoformat() or self.exists(venue_id, gig_date, title):
            return False
        if "pink zinc presents" in title.lower() and not description:
            description = "Pink Zinc Presents: the band with a different line-up (Pink Zinc Entertainment)."
        self.log.append(f"ADD {gig_date} {start_time or '--:--'} {venue_name}: {title}")
        self.added += 1
        if not self.dry_run:
            cur = self.db.execute(
                "INSERT INTO gigs (venue_id, title, gig_date, start_time, description, ticket_url, source) "
                "VALUES (?,?,?,?,?,?,?)",
                (venue_id, title, gig_date, start_time, description, ticket_url, source),
            )
            link_gig_performers(self.db, cur.lastrowid, title)
        return True


# ---------------------------------------------------------------- Beach Hotel
def _tidy_beach_title(raw: str):
    t = html.unescape(raw).strip()
    t = re.sub(r"(?<=\w)�(?=\w)", "’", t)
    t = re.sub(r"\s�\s", " – ", t).replace("�", "")
    t = re.sub(r"\s*\|\s*(SOLD OUT|Sold Out).*$", "", t)
    support = None
    if " | " in t:
        t, support = [x.strip() for x in t.split(" | ", 1)]
    m = re.match(r"^(.*?)\s+supported by\s+(.*)$", t, flags=re.I)
    if m:
        t, support = m.group(1).strip(), "Supported by " + m.group(2).strip()
    if t.isupper() and len(t) > 5:
        t = t.title()
    return t, support


def sync_beach_hotel(ctx: Ctx):
    vid = ctx.venue_id("beach-hotel")
    if vid is None:
        ctx.log.append("beach-hotel venue missing")
        return
    start = today_local()
    end = start + timedelta(weeks=12)
    page, pages = 1, 1
    while page <= pages and page <= 10:
        url = f"{BEACH_FEED}?per_page=50&page={page}&start_date={start}&end_date={end}"
        data = json.loads(_get(url))
        pages = int(data.get("total_pages") or 1)
        for ev in data.get("events", []):
            cats = [c["name"] for c in ev.get("categories", [])]
            if "Gig" not in cats and (cats or re.search(r"raffle|happy hour|melbourne cup", ev["title"], re.I)):
                continue
            title, support = _tidy_beach_title(ev["title"])
            d, _, t = ev["start_date"].partition(" ")
            ctx.add(vid, "Beach Hotel", d, t[:5] or None, title, support, ev.get("url"))
        page += 1


# ------------------------------------------------------------------ The Rails
def sync_rails(ctx: Ctx):
    vid = ctx.venue_id("railway-friendly-bar")
    if vid is None:
        ctx.log.append("railway-friendly-bar venue missing")
        return
    text = _get(RAILS_PAGE).decode("utf8", "ignore")
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", "\n", text))
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    try:
        start_idx = next(i for i, l in enumerate(lines) if "UPCOMING GIGS" in l.upper()) + 1
    except StopIteration:
        ctx.log.append("rails: UPCOMING GIGS heading not found")
        return
    prev = None
    for line in lines[start_idx:]:
        m = re.match(r"^(\d{1,2})/0?(\d{1,2})/(\d{4})\s+(.+)$", line)
        if not m:
            if prev is not None and re.match(r"^\d", line) is None and len(line) < 3:
                continue
            continue
        day, mon, yr, act = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4).strip()
        parsed = None
        try:
            parsed = date(yr, mon, day)
        except ValueError:
            pass
        expected = (prev + timedelta(days=1)) if prev else parsed
        # The Rails page has date typos (e.g. 02/09 between 01/10 and 03/10): trust the
        # one-act-per-night sequence unless the date is a plausible forward jump.
        if expected is None:
            continue
        gig_date = parsed if parsed and expected <= parsed <= expected + timedelta(days=7) else expected
        prev = gig_date
        ctx.add(vid, "The Rails", gig_date.isoformat(), None, act)


# ------------------------------------------------------------------- The Echo
def _echo_items(xml: str):
    for item in re.findall(r"<item>(.*?)</item>", xml, flags=re.S):
        t = html.unescape(re.sub(r"<[^>]+>", "|", item))
        t = re.sub(r"\s+", " ", t)

        def g(label):
            m = re.search(label + r":\s*\|*\s*([^|]*?)\s*\|", t)
            return m.group(1).strip() if m else ""

        yield {"artist": g("Artist"), "date": g("Date"), "time": g("Time"), "city": g("City"), "venue": g("Venue")}


def _echo_date(s: str):
    m = re.search(r"([A-Za-z]+) (\d+)\w* (\d{4})", s)
    return datetime.strptime(f"{m[1]} {m[2]} {m[3]}", "%B %d %Y").date().isoformat() if m else None


def _echo_time(s: str):
    m = re.match(r"(\d+):(\d+)\s*(am|pm)", s or "", flags=re.I)
    if not m:
        return None
    return f"{int(m[1]) % 12 + (12 if m[3].lower() == 'pm' else 0):02d}:{m[2]}"


def sync_echo(ctx: Ctx):
    xml = _get(ECHO_FEED).decode("utf8", "ignore")
    venues = {}
    for r in ctx.db.execute("SELECT id, slug, name FROM venues").fetchall():
        venues[_norm(r["name"])] = r
        venues[_norm(r["slug"].replace("-", " "))] = r
    for it in _echo_items(xml):
        if not it["artist"] or not it["venue"]:
            continue
        gig_date = _echo_date(it["date"])
        if not gig_date:
            continue
        key = _norm(it["venue"])
        if key in ECHO_SKIP_VENUES:
            continue
        row = venues.get(key)
        if row is None and key in ECHO_ALIASES:
            row = ctx.db.execute("SELECT id, slug, name FROM venues WHERE slug = ?", (ECHO_ALIASES[key],)).fetchone()
        if row is None:
            if gig_date < today_local().isoformat():
                continue
            ctx.log.append(f"NEW VENUE {it['venue']} ({it['city']}) from the Echo")
            if ctx.dry_run:
                continue
            slug = unique_slug(ctx.db, "venues", slugify(it["venue"]))
            cur = ctx.db.execute("INSERT INTO venues (slug, name, town) VALUES (?,?,?)", (slug, it["venue"], it["city"] or "Northern Rivers"))
            row = {"id": cur.lastrowid, "slug": slug, "name": it["venue"]}
            venues[key] = row
        title = it["artist"].replace("\\’", "’").replace("\\", "")
        ctx.add(row["id"], row["name"], gig_date, _echo_time(it["time"]), title, source="echo")


SOURCES = {"beach": sync_beach_hotel, "rails": sync_rails, "echo": sync_echo}


def sync_all(only=None, dry_run=False) -> dict:
    db = get_db()
    ctx = Ctx(db, dry_run)
    for name, fn in SOURCES.items():
        if only and name not in only:
            continue
        before = ctx.added
        try:
            fn(ctx)
            ctx.log.append(f"-- {name}: {ctx.added - before} new")
        except Exception as exc:  # one broken source must not stop the others
            ctx.log.append(f"-- {name}: FAILED {type(exc).__name__}: {exc}")
    if not dry_run:
        db.commit()
    return {"added": ctx.added, "log": ctx.log}
