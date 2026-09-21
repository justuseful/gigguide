from datetime import datetime, timezone

from .db import get_db
from .util import slugify, unique_slug


def create_story(
    title: str,
    body: str,
    category: str = "Story",
    excerpt: str | None = None,
    youtube_id: str | None = None,
    social_url: str | None = None,
    published: bool = True,
) -> str:
    """Create a new story (e.g. a longer first-person writeup with video, for
    the Stories section rather than just a performer-page embed). Returns the
    new story's slug."""
    db = get_db()
    slug = unique_slug(db, "stories", slugify(title))
    published_at = datetime.now(timezone.utc).isoformat() if published else None
    db.execute(
        "INSERT INTO stories (slug, title, category, excerpt, body, youtube_id, social_url, "
        "published, published_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (slug, title, category, excerpt, body, youtube_id, social_url, int(published), published_at),
    )
    db.commit()
    return slug
