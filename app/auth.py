import hmac
import secrets
from functools import wraps

from flask import Response, abort, current_app, request, session


def _unauthorized() -> Response:
    return Response(
        "Authentication required.",
        401,
        {"WWW-Authenticate": 'Basic realm="Gig Guide Admin"'},
    )


def _matches(given: str | None, expected: str) -> bool:
    return hmac.compare_digest((given or "").encode(), expected.encode())


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        password = current_app.config.get("ADMIN_PASSWORD")
        if not password:
            return Response("Admin is not configured (set GIGGUIDE_ADMIN_PASSWORD).", 503)
        auth = request.authorization
        if (
            auth is None
            or auth.type != "basic"
            or not _matches(auth.username, current_app.config["ADMIN_USER"])
            or not _matches(auth.password, password)
        ):
            return _unauthorized()
        return view(*args, **kwargs)

    return wrapped


def csrf_token() -> str:
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def check_csrf():
    expected = session.get("_csrf")
    given = request.form.get("_csrf")
    if not expected or not given or not hmac.compare_digest(expected, given):
        abort(400, "Invalid or missing form token. Please reload the page and try again.")
