from datetime import date, datetime

from markupsafe import Markup, escape


def fmt_date(value, style: str = "short") -> str:
    try:
        d = date.fromisoformat(value)
    except (TypeError, ValueError):
        return value or ""
    if style == "long":
        return f"{d:%A} {d.day} {d:%B} {d.year}"
    return f"{d:%a} {d.day} {d:%b}"


def fmt_time(value) -> str:
    try:
        t = datetime.strptime(value, "%H:%M")
    except (TypeError, ValueError):
        return value or ""
    hour = t.hour % 12 or 12
    suffix = "am" if t.hour < 12 else "pm"
    return f"{hour}:{t.minute:02d}{suffix}" if t.minute else f"{hour}{suffix}"


def nl2p(value) -> Markup:
    text = str(escape(value or "")).replace("\r\n", "\n")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return Markup("".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs))


def register_filters(app):
    app.add_template_filter(fmt_date, "date")
    app.add_template_filter(fmt_time, "time")
    app.add_template_filter(nl2p, "nl2p")
