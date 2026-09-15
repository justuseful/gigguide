from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import current_app


def today_local() -> date:
    return datetime.now(ZoneInfo(current_app.config["TIMEZONE"])).date()
