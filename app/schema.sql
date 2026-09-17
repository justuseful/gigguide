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

CREATE TABLE IF NOT EXISTS performers (
    id          INTEGER PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    bio         TEXT,
    instagram   TEXT,
    website     TEXT,
    youtube_id  TEXT,          -- a default/featured video for their profile page
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gig_performers (
    gig_id       INTEGER NOT NULL REFERENCES gigs(id) ON DELETE CASCADE,
    performer_id INTEGER NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    PRIMARY KEY (gig_id, performer_id)
);

CREATE INDEX IF NOT EXISTS idx_gig_performers_performer ON gig_performers(performer_id);

CREATE TABLE IF NOT EXISTS page_views (
    day   TEXT NOT NULL,
    path  TEXT NOT NULL,
    views INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, path)
);

CREATE TABLE IF NOT EXISTS stories (
    id           INTEGER PRIMARY KEY,
    slug         TEXT NOT NULL UNIQUE,
    title        TEXT NOT NULL,
    category     TEXT NOT NULL DEFAULT 'Story',
    excerpt      TEXT,
    body         TEXT NOT NULL,          -- Markdown, written by the (trusted) admin
    hero_image   TEXT,                   -- filename inside the uploads dir
    youtube_id   TEXT,
    published    INTEGER NOT NULL DEFAULT 0,
    published_at TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_stories_published ON stories(published, published_at);

CREATE TABLE IF NOT EXISTS comments (
    id           INTEGER PRIMARY KEY,
    target_type  TEXT NOT NULL CHECK (target_type IN ('story', 'gig')),
    target_id    INTEGER NOT NULL,
    parent_id    INTEGER REFERENCES comments(id) ON DELETE CASCADE,  -- one level of replies
    author_name  TEXT NOT NULL,
    author_email TEXT NOT NULL,          -- never shown publicly; used to auto-approve return commenters
    body         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'spam')),
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_comments_target ON comments(target_type, target_id, status);
CREATE INDEX IF NOT EXISTS idx_comments_email  ON comments(author_email, status);
