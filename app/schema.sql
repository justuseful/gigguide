CREATE TABLE IF NOT EXISTS venues (
    id          INTEGER PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    town        TEXT NOT NULL,
    address     TEXT,
    website     TEXT,
    instagram   TEXT,
    description TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gigs (
    id          INTEGER PRIMARY KEY,
    venue_id    INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    gig_date    TEXT NOT NULL,              -- ISO date, YYYY-MM-DD (local time)
    start_time  TEXT,                       -- HH:MM
    price       TEXT,
    ticket_url  TEXT,
    youtube_id  TEXT,
    flyer       TEXT,                       -- filename inside the uploads dir
    description TEXT,
    featured    INTEGER NOT NULL DEFAULT 0,
    source      TEXT NOT NULL DEFAULT 'manual',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gigs_date  ON gigs(gig_date);
CREATE INDEX IF NOT EXISTS idx_gigs_venue ON gigs(venue_id);

CREATE TABLE IF NOT EXISTS page_views (
    day   TEXT NOT NULL,
    path  TEXT NOT NULL,
    views INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, path)
);
