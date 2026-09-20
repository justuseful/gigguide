from urllib.parse import quote

from flask import current_app, render_template

from .routes_public import bp

CONTACT_EMAIL = "humansofbundjalung@gmail.com"
ARTIST_PRO_MONTHLY_PRICE = 10
ARTIST_PRO_ANNUAL_PRICE = 96


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

    # Artist Pro is a fixed price, so it pays directly via a Stripe payment
    # link with the amount baked in - no need to email first. Advertising is
    # priced per placement, so that still goes through the enquiry email to
    # get a quote.
    artist_pro_monthly_url = current_app.config["ARTIST_PRO_MONTHLY_URL"] or None
    artist_pro_annual_url = current_app.config["ARTIST_PRO_ANNUAL_URL"] or None

    return render_template(
        "support.html",
        options=options,
        artist_pro_monthly_price=ARTIST_PRO_MONTHLY_PRICE,
        artist_pro_annual_price=ARTIST_PRO_ANNUAL_PRICE,
        artist_pro_monthly_url=artist_pro_monthly_url,
        artist_pro_annual_url=artist_pro_annual_url,
        artist_pro_mailto=_mailto("Artist Pro enquiry"),
        advertise_mailto=_mailto("Advertising enquiry"),
    )
