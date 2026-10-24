from urllib.parse import quote

from flask import render_template

from .routes_public import bp
from .routes_support import CONTACT_EMAIL

INSTAGRAM_HANDLE = "kirk.buttermore.videography"
PHONE_DISPLAY = "0436 381 461"
PHONE_TEL = "+61436381461"


@bp.get("/book-videography")
def book_videography():
    mailto = f"mailto:{CONTACT_EMAIL}?subject={quote('Videography booking')}"
    return render_template(
        "book.html",
        mailto=mailto,
        email=CONTACT_EMAIL,
        instagram_url=f"https://www.instagram.com/{INSTAGRAM_HANDLE}/",
        instagram_handle=INSTAGRAM_HANDLE,
        phone_display=PHONE_DISPLAY,
        phone_tel=PHONE_TEL,
    )
