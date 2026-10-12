import re

# (slug, label) - the fixed set offered in the genre filter and admin forms.
GENRES = [
    ("rock", "Rock"),
    ("pub-rock", "Pub rock"),
    ("blues", "Blues"),
    ("jazz", "Jazz"),
    ("soul", "Soul"),
    ("funk", "Funk"),
    ("country", "Country"),
    ("folk", "Folk"),
    ("singer-songwriter", "Singer-songwriter"),
    ("reggae", "Reggae"),
    ("pop", "Pop"),
    ("indie", "Indie"),
    ("punk", "Punk"),
    ("metal", "Metal"),
    ("hip-hop", "Hip hop"),
    ("electronic", "Electronic / DJ"),
    ("latin", "Latin"),
    ("world", "World"),
    ("classical", "Classical"),
]
GENRE_LABELS = dict(GENRES)

SPOTIFY_RE = re.compile(
    r"(?:open\.spotify\.com/(?:intl-[a-z]{2,3}/)?|spotify:)(track|album|playlist|artist|episode|show)[/:]([A-Za-z0-9]{22})"
)


def parse_genres(value) -> str | None:
    """Accepts a list of slugs/labels or a comma-separated string and returns the
    canonical ',jazz,blues,' storage form (commas on both ends so SQL can match
    '%,jazz,%' without false hits), or None if empty. Unknown genres raise."""
    if not value:
        return None
    items = value if isinstance(value, (list, tuple)) else str(value).split(",")
    by_label = {label.lower(): slug for slug, label in GENRES}
    slugs = []
    for raw in items:
        key = raw.strip().lower()
        if not key:
            continue
        slug = key if key in GENRE_LABELS else by_label.get(key) or key.replace(" ", "-")
        if slug not in GENRE_LABELS:
            raise ValueError(f"Unknown genre {raw.strip()!r}. Choose from: {', '.join(GENRE_LABELS)}")
        if slug not in slugs:
            slugs.append(slug)
    return "," + ",".join(slugs) + "," if slugs else None


def parse_spotify(value) -> str | None:
    """Accepts one or more Spotify links/URIs (separated by newlines, spaces or
    commas) and returns newline-separated 'type/id' entries, or None if empty."""
    if not value:
        return None
    entries = []
    for chunk in re.split(r"[\s,]+", str(value).strip()):
        if not chunk:
            continue
        m = SPOTIFY_RE.search(chunk)
        if not m:
            raise ValueError("That doesn't look like a Spotify track, album, playlist or artist link.")
        entry = f"{m.group(1)}/{m.group(2)}"
        if entry not in entries:
            entries.append(entry)
    return "\n".join(entries) if entries else None


def genre_list(stored) -> list[tuple[str, str]]:
    """Stored string (possibly several concatenated) -> de-duplicated [(slug, label)]."""
    seen = []
    for part in (stored or "").split(","):
        part = part.strip()
        if part in GENRE_LABELS and part not in seen:
            seen.append(part)
    return [(s, GENRE_LABELS[s]) for s in seen]


def spotify_embeds(stored) -> list[dict]:
    """Stored 'type/id' lines -> [{'path','height'}] for the embed iframes."""
    out = []
    for line in (stored or "").splitlines():
        line = line.strip()
        if "/" not in line:
            continue
        kind = line.split("/", 1)[0]
        out.append({"path": line, "height": 152 if kind in ("track", "episode") else 352})
    return out
