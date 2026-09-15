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
    print("smoke test OK")


if __name__ == "__main__":
    test_smoke()
