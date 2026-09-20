import re

from .util import slugify, today_local, unique_slug

# Echo gig titles often list several acts on one bill, e.g. "A + B + C" or
# "A, B, C & D". Splitting on "+"/"," catches the common cases; "&" is left
# alone since it's frequently part of a single act's own name
# (e.g. "Joe Camilleri & The Black Sorrows"), so a lineup written as
# "A, B & C" ends up as two performers ("A", "B & C") rather than three -
# an acceptable imperfection given how ambiguous "&" is on its own.
SPLIT_ON_PLUS_AND_COMMA = re.compile(r"\s*[+,]\s*")
SPLIT_ON_PLUS_ONLY = re.compile(r"\s*\+\s*")

# Titles that describe a screening/exhibition rather than a performing act -
# not worth creating a "performer" entity for.
SKIP_PATTERNS = [
    re.compile(r"film festival", re.I),
    re.compile(r"^screening\b", re.I),
    re.compile(r"^exhibition\b", re.I),
]


def extract_performer_names(title: str) -> list[str]:
    if any(p.search(title) for p in SKIP_PATTERNS):
        return []
    # A colon usually means "Show name: descriptive subtitle" rather than a
    # lineup, and that subtitle often has its own comma
    # (e.g. "ReWilding Red Riding Hood: Ancestral Tales of Daring, Difficult
    # Women") - splitting on comma there would wrongly carve up the subtitle.
    splitter = SPLIT_ON_PLUS_ONLY if ":" in title else SPLIT_ON_PLUS_AND_COMMA
    return [p.strip() for p in splitter.split(title) if p.strip()]


def get_or_create_performer(db, name: str) -> tuple[int, bool]:
    """Returns (performer_id, was_newly_created)."""
    row = db.execute("SELECT id FROM performers WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    if row:
        return row["id"], False
    slug = unique_slug(db, "performers", slugify(name))
    cur = db.execute("INSERT INTO performers (slug, name) VALUES (?, ?)", (slug, name))
    return cur.lastrowid, True


def link_gig_performers(db, gig_id: int, title: str) -> int:
    """Find-or-create a performer for each act named in `title` and link them
    to `gig_id`. Returns the number of new links added (0 if already linked
    or the title didn't look like a performing act)."""
    added = 0
    for name in extract_performer_names(title):
        performer_id, _ = get_or_create_performer(db, name)
        cur = db.execute(
            "INSERT OR IGNORE INTO gig_performers (gig_id, performer_id) VALUES (?, ?)",
            (gig_id, performer_id),
        )
        added += cur.rowcount
    apply_pro_featuring(db, gig_id)
    return added


def refresh_pro_featuring_for_performer(db, performer_id: int) -> None:
    """Re-apply Pro auto-featuring to every gig this performer is already linked
    to - covers becoming Pro after gigs were already added, not just gigs
    linked from this point on."""
    gig_ids = [
        r["gig_id"] for r in
        db.execute("SELECT gig_id FROM gig_performers WHERE performer_id = ?", (performer_id,)).fetchall()
    ]
    for gig_id in gig_ids:
        apply_pro_featuring(db, gig_id)


def apply_pro_featuring(db, gig_id: int) -> None:
    """Auto-feature a gig if any linked performer is an active Artist Pro
    subscriber - that's the paid perk of the subscription. Never un-features a
    gig that was featured for some other reason (e.g. a venue paid directly)."""
    today = today_local().isoformat()
    has_active_pro = db.execute(
        "SELECT 1 FROM gig_performers gp JOIN performers p ON p.id = gp.performer_id "
        "WHERE gp.gig_id = ? AND p.is_pro = 1 AND (p.pro_until IS NULL OR p.pro_until >= ?)",
        (gig_id, today),
    ).fetchone()
    if has_active_pro:
        db.execute("UPDATE gigs SET featured = 1 WHERE id = ?", (gig_id,))


def link_performers_from_titles(db) -> dict:
    """Backfill performer links for every existing gig from its title. Safe
    to re-run - already-linked (gig, performer) pairs are skipped."""
    gigs = db.execute("SELECT id, title FROM gigs").fetchall()
    performers_before = db.execute("SELECT COUNT(*) FROM performers").fetchone()[0]
    links_added = 0
    gigs_with_performers = 0
    for gig in gigs:
        added = link_gig_performers(db, gig["id"], gig["title"])
        links_added += added
        if extract_performer_names(gig["title"]):
            gigs_with_performers += 1
    db.commit()
    performers_after = db.execute("SELECT COUNT(*) FROM performers").fetchone()[0]
    return {
        "gigs_processed": len(gigs),
        "gigs_with_performers": gigs_with_performers,
        "performers_created": performers_after - performers_before,
        "links_added": links_added,
    }
