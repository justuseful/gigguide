import html
import json
import re
from datetime import date, datetime
from urllib.parse import unquote_plus

import requests

GIG_GUIDE_URL = "https://www.echo.net.au/gig-guide-2/"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0 Safari/537.36"
)

# The Echo's gig guide is a WordPress GigPress listing: one page per week,
# grouped by day (<summary class="gigpress-day-heading">) then town
# (<h4 class="gigpress-city-heading">), with one <article> per show. These
# patterns are matched in document order so each show picks up the day and
# town heading above it.
TOKEN = re.compile(
    r'<summary class="gigpress-day-heading">(?P<day>[^<]+)</summary>'
    r'|<h4 class="gigpress-city-heading">(?P<city>[^<]+)</h4>'
    r'|<article class="gigpress-show[^"]*">(?P<show>.*?)</article>',
    re.S,
)
SHOW_TIME = re.compile(r'<time class="gigpress-show-time">([^<]+)</time>')
SHOW_ARTIST = re.compile(r'<span class="gigpress-show-artist">(.*?)</span>', re.S)
SHOW_VENUE = re.compile(r'<span class="gigpress-show-venue">(.*?)</span>', re.S)
# The "Add to Google Calendar" link carries the town in its proper case
# ("location=Railway+Hotel%2C+Byron+Bay%2C+AU"), unlike the upper-cased heading.
CALENDAR_LOCATION = re.compile(r"[?&;]location=([^&\"]+)")
WEEK_OPTION = re.compile(r'<option value="[^"]*gpy=(\d{4})&(?:amp;)?gpw=(\d+)"')
CITY_OPTION = re.compile(r'<option value="[^"]*cityid=(\d+)">([^<]+)</option>')
ORDINAL = re.compile(r"(\d+)(st|nd|rd|th)\b")


class ScrapeBlocked(RuntimeError):
    """The Echo (via Cloudflare) served a bot challenge instead of the listing."""


def _clean(text: str) -> str:
    # Titles come through with WordPress-escaped quotes, e.g. "\’More Salt Please\’"
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\\", "")
    return re.sub(r"\s+", " ", text).strip()


def _parse_day(heading: str) -> str:
    # "Monday 21st Sep 2026" -> "2026-09-21"
    return datetime.strptime(ORDINAL.sub(r"\1", heading.strip()), "%A %d %b %Y").date().isoformat()


def _parse_time(text: str) -> str | None:
    # "5:00pm" -> "17:00"
    try:
        return datetime.strptime(text.strip().lower().replace(" ", ""), "%I:%M%p").strftime("%H:%M")
    except ValueError:
        return None


def parse_week(page_html: str) -> list[dict]:
    """Extract gigs from one week's gig guide page, in the same shape as
    app/data/echo_gigs.json entries."""
    if "gigpress" not in page_html:
        raise ScrapeBlocked("page has no gig listings (Cloudflare challenge?)")

    gigs = []
    day = city = None
    for m in TOKEN.finditer(page_html):
        if m["day"]:
            day = _parse_day(m["day"])
        elif m["city"]:
            city = _clean(m["city"]).title()
        elif day:
            show = m["show"]
            venue = _clean(SHOW_VENUE.search(show).group(1))
            town = city
            loc = CALENDAR_LOCATION.search(html.unescape(show))
            if loc:
                parts = [p.strip() for p in unquote_plus(loc.group(1)).split(",")]
                if len(parts) >= 2 and parts[-2]:
                    town = parts[-2]
            time_match = SHOW_TIME.search(show)
            gigs.append({
                "venue": venue,
                "town": town,
                "title": _clean(SHOW_ARTIST.search(show).group(1)),
                "gig_date": day,
                "start_time": _parse_time(time_match.group(1)) if time_match else None,
            })
    return gigs


def list_weeks(page_html: str) -> list[tuple[int, int]]:
    """(year, ISO week) pairs offered in the page's "Select Week" menu."""
    return sorted({(int(y), int(w)) for y, w in WEEK_OPTION.findall(page_html)})


def city_id(page_html: str, town: str) -> str | None:
    """The Echo's numeric cityid for a town name, from the "All Towns" menu."""
    for cid, name in CITY_OPTION.findall(page_html):
        if name.strip().lower() == town.strip().lower():
            return cid
    return None


def fetch(params: dict | None = None, session: requests.Session | None = None) -> str:
    session = session or requests.Session()
    resp = session.get(GIG_GUIDE_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    if resp.status_code in (403, 503) or "gigpress" not in resp.text:
        raise ScrapeBlocked(
            f"echo.net.au returned HTTP {resp.status_code} without a gig listing - "
            "Cloudflare is likely blocking this IP. Save the weekly pages from a browser "
            "and pass them with --html instead."
        )
    resp.raise_for_status()
    return resp.text


def scrape(town: str | None = None) -> list[dict]:
    """Fetch every week the Echo currently publishes (optionally filtered to
    one town) and return the combined, de-duplicated gig list."""
    session = requests.Session()
    first = fetch(session=session)
    params = {}
    if town:
        cid = city_id(first, town)
        if cid is None:
            raise ValueError(f"The Echo has no town called {town!r} in its gig guide")
        params["cityid"] = cid
    pages = [fetch({**params, "gpy": y, "gpw": w}, session) for y, w in list_weeks(first)]
    return merge_gigs(pages, town)


def merge_gigs(pages: list[str], town: str | None = None) -> list[dict]:
    seen, gigs = set(), []
    for page in pages:
        for gig in parse_week(page):
            if town and gig["town"].lower() != town.lower():
                continue
            key = (gig["venue"].lower(), gig["gig_date"], gig["start_time"], gig["title"].lower())
            if key not in seen:
                seen.add(key)
                gigs.append(gig)
    gigs.sort(key=lambda g: (g["gig_date"], g["start_time"] or "", g["venue"], g["title"]))
    return gigs


def write_gigs(gigs: list[dict], out_file: str, town: str | None = None) -> None:
    dates = [g["gig_date"] for g in gigs]
    span = f"{min(dates)} to {max(dates)}" if dates else "no dates"
    data = {
        "source": GIG_GUIDE_URL,
        "scraped": date.today().isoformat(),
        "note": f"{town or 'All towns'} gigs from the weeks the Echo publishes ahead ({span}). "
                "Re-scrape periodically to keep listings current.",
        "gigs": gigs,
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
