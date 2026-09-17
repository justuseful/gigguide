"""End-to-end smoke test using Flask's test client. Run: python tests/test_smoke.py"""
import base64
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402

AUTH = {"Authorization": "Basic " + base64.b64encode(b"admin:pw").decode()}


def _csrf(html: str) -> str:
    return re.search(r'name="_csrf" value="([^"]+)"', html).group(1)


def test_smoke():
    tmp = tempfile.mkdtemp()
    app = create_app({"DATA_DIR": tmp, "ADMIN_PASSWORD": "pw", "TESTING": True})
    c = app.test_client()

    assert c.get("/").status_code == 200
    assert c.get("/venues").status_code == 200
    assert c.get("/healthz").json == {"ok": True}
    assert c.get("/nope").status_code == 404

    # support page: hidden when no links are configured, shown once one is set
    assert "Support options are coming soon" in c.get("/support").get_data(as_text=True)
    app.config["SUPPORT_PATREON_URL"] = "https://patreon.com/example"
    support_html = c.get("/support").get_data(as_text=True)
    assert "Support on Patreon" in support_html and 'href="https://patreon.com/example"' in support_html
    app.config["SUPPORT_PATREON_URL"] = ""

    # admin is protected
    assert c.get("/admin/").status_code == 401
    assert c.get("/admin/", headers={"Authorization": "Basic " + base64.b64encode(b"admin:wrong").decode()}).status_code == 401
    assert c.get("/admin/", headers=AUTH).status_code == 200

    # create a venue
    page = c.get("/admin/venues/new", headers=AUTH).get_data(as_text=True)
    r = c.post("/admin/venues/new", headers=AUTH, follow_redirects=True,
               data={"_csrf": _csrf(page), "name": "Test Venue", "town": "Byron Bay", "instagram": "@testvenue"})
    assert r.status_code == 200 and "Venue added" in r.get_data(as_text=True)

    # CSRF is enforced
    assert c.post("/admin/gigs/new", headers=AUTH, data={"title": "x"}).status_code == 400

    # create a featured gig with a YouTube link
    page = c.get("/admin/gigs/new", headers=AUTH).get_data(as_text=True)
    r = c.post("/admin/gigs/new", headers=AUTH, follow_redirects=True, data={
        "_csrf": _csrf(page), "venue_id": "1", "title": "Test Band", "gig_date": "2099-01-01",
        "start_time": "19:30", "price": "Free", "youtube": "https://youtu.be/dQw4w9WgXcQ",
        "description": "Line one\n\nLine two", "featured": "1",
    })
    assert r.status_code == 200 and "Gig added" in r.get_data(as_text=True)

    # bad YouTube link is rejected
    page = c.get("/admin/gigs/new", headers=AUTH).get_data(as_text=True)
    r = c.post("/admin/gigs/new", headers=AUTH, data={
        "_csrf": _csrf(page), "venue_id": "1", "title": "Bad", "gig_date": "2099-01-02", "youtube": "not a link",
    })
    assert r.status_code == 400

    home = c.get("/").get_data(as_text=True)
    assert "Test Band" in home and "Featured" in home and "7:30pm" in home
    gig = c.get("/gig/1").get_data(as_text=True)
    assert "yt-facade" in gig and "dQw4w9WgXcQ" in gig and "<p>Line one</p><p>Line two</p>" in gig
    assert "instagram.com/testvenue" in gig
    assert c.get("/venue/test-venue").status_code == 200
    assert c.get("/gig/999").status_code == 404

    # edit + delete
    page = c.get("/admin/gigs/1/edit", headers=AUTH).get_data(as_text=True)
    assert 'value="dQw4w9WgXcQ"' in page
    r = c.post("/admin/gigs/1/edit", headers=AUTH, follow_redirects=True, data={
        "_csrf": _csrf(page), "venue_id": "1", "title": "Test Band (renamed)", "gig_date": "2099-01-01",
    })
    assert "Test Band (renamed)" in c.get("/").get_data(as_text=True)
    r = c.post("/admin/gigs/1/delete", headers=AUTH, follow_redirects=True, data={"_csrf": _csrf(page)})
    assert "Gig deleted" in r.get_data(as_text=True)
    assert c.get("/gig/1").status_code == 404

    # page views were counted (test client UA isn't a bot)
    dash = c.get("/admin/", headers=AUTH).get_data(as_text=True)
    assert "page views, last 7 days" in dash

    # --- stories ---
    assert c.get("/stories").status_code == 200

    page = c.get("/admin/stories/new", headers=AUTH).get_data(as_text=True)
    r = c.post("/admin/stories/new", headers=AUTH, follow_redirects=True, data={
        "_csrf": _csrf(page), "title": "Meet the Buttermores", "category": "Human of Bundjalung",
        "excerpt": "A chat with a local family.", "body": "Line one\n\nLine two",
        "youtube": "https://youtu.be/dQw4w9WgXcQ", "published": "1",
    })
    assert r.status_code == 200 and "Story added" in r.get_data(as_text=True)

    assert "Meet the Buttermores" in c.get("/stories").get_data(as_text=True)
    assert "Meet the Buttermores" in c.get("/").get_data(as_text=True)  # shows on home page too

    story_resp = c.get("/stories/meet-the-buttermores")
    assert story_resp.status_code == 200
    story_html = story_resp.get_data(as_text=True)
    assert "<p>Line one</p>" in story_html and "<p>Line two</p>" in story_html and "dQw4w9WgXcQ" in story_html
    assert c.get("/stories/does-not-exist").status_code == 404

    token = _csrf(story_html)

    # comment CSRF is enforced
    assert c.post("/stories/meet-the-buttermores/comments", data={"author_name": "x"}).status_code == 400

    # honeypot trips silently - nothing is stored
    c.post("/stories/meet-the-buttermores/comments", follow_redirects=True, data={
        "_csrf": token, "author_name": "Bot", "author_email": "bot@example.com",
        "body": "buy cheap stuff now", "website": "http://spam.example",
    })
    assert "buy cheap stuff now" not in c.get("/admin/comments", headers=AUTH).get_data(as_text=True)

    # a real first-time comment is held for moderation, not shown publicly yet
    r = c.post("/stories/meet-the-buttermores/comments", follow_redirects=True, data={
        "_csrf": token, "author_name": "Jamie", "author_email": "jamie@example.com", "body": "Great read!",
    })
    assert "held for a quick review" in r.get_data(as_text=True)
    assert "Great read!" not in c.get("/stories/meet-the-buttermores").get_data(as_text=True)

    admin_comments = c.get("/admin/comments", headers=AUTH).get_data(as_text=True)
    assert "Jamie" in admin_comments and "Great read!" in admin_comments
    comment_id = re.search(r"/admin/comments/(\d+)/approve", admin_comments).group(1)
    c.post(f"/admin/comments/{comment_id}/approve", headers=AUTH, data={"_csrf": token})
    assert "Great read!" in c.get("/stories/meet-the-buttermores").get_data(as_text=True)

    # a returning (now-trusted) commenter is auto-approved
    r = c.post("/stories/meet-the-buttermores/comments", follow_redirects=True, data={
        "_csrf": token, "author_name": "Jamie", "author_email": "jamie@example.com", "body": "Second comment.",
    })
    assert "Comment posted" in r.get_data(as_text=True)
    assert "Second comment." in c.get("/stories/meet-the-buttermores").get_data(as_text=True)

    # a reply from an already-trusted email is auto-approved and nests under the parent
    r = c.post("/stories/meet-the-buttermores/comments", follow_redirects=True, data={
        "_csrf": token, "author_name": "Jamie", "author_email": "jamie@example.com",
        "body": "Replying to my own comment.", "parent_id": comment_id,
    })
    reply_html = c.get("/stories/meet-the-buttermores").get_data(as_text=True)
    assert 'comment--reply' in reply_html and "Replying to my own comment." in reply_html

    # deleting the story removes its comments too, not just the story
    c.post("/admin/stories/1/delete", headers=AUTH, data={"_csrf": token})
    assert "Replying to my own comment." not in c.get("/admin/comments", headers=AUTH).get_data(as_text=True)
    assert c.get("/stories/meet-the-buttermores").status_code == 404

    print("smoke test OK")


if __name__ == "__main__":
    test_smoke()
