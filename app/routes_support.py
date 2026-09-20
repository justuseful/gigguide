from urllib.parse import quote

from flask import current_app, render_template

from .routes_public import bp

CONTACT_EMAIL = "humansofbundjalung@gmail.com"


def _mailto(subject: str) -> str:
    return f"mailto:{CONTACT_EMAIL}?subject={quote(subject)}"


@bp.get("/support")
def support():
    options = [
        {
            "name": "Patreon",
            "url": current_app.config["SUPPORT_PATREON_URL"],
            "blurb": "Become a monthly member and help keep the gig guide running.",
        },
        {
            "name": "Ko-fi",
            "url": current_app.config["SUPPORT_KOFI_URL"],
            "blurb": "Buy us a coffee — a quick one-off way to chip in.",
        },
        {
            "name": "PayPal",
            "url": current_app.config["SUPPORT_PAYPAL_URL"],
            "blurb": "Send a one-off contribution via PayPal.",
        },
    ]
    options = [o for o in options if o["url"]]
    return render_template(
        "support.html",
        options=options,
        artist_pro_mailto=_mailto("Artist Pro enquiry"),
        advertise_mailto=_mailto("Advertising enquiry"),
    )
