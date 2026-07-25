from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")


@lru_cache(maxsize=1)
def _exchange_calendar() -> tuple[date, date, frozenset[date]] | None:
    try:
        from czsc.py.calendar import calendar as calendar_frame

        calendar_dates: list[date] = []
        open_sessions: set[date] = set()
        for raw_date, is_open in calendar_frame.loc[:, ["cal_date", "is_open"]].itertuples(
            index=False, name=None
        ):
            session_date = (
                raw_date.date()
                if isinstance(raw_date, datetime)
                else date.fromisoformat(str(raw_date)[:10])
            )
            calendar_dates.append(session_date)
            if int(is_open) == 1:
                open_sessions.add(session_date)
    except Exception:
        return None
    if not calendar_dates or not open_sessions:
        return None
    return min(calendar_dates), max(calendar_dates), frozenset(open_sessions)


def is_open_session(value: date) -> bool:
    calendar_data = _exchange_calendar()
    if calendar_data is not None:
        first_date, last_date, open_sessions = calendar_data
        if first_date <= value <= last_date:
            return value in open_sessions
    return value.weekday() < 5


def previous_open_session(value: date) -> date:
    calendar_data = _exchange_calendar()
    if calendar_data is not None:
        first_date, last_date, open_sessions = calendar_data
        if first_date <= value <= last_date:
            previous = value - timedelta(days=1)
            while previous >= first_date:
                if previous in open_sessions:
                    return previous
                previous -= timedelta(days=1)

    previous = value - timedelta(days=1)
    while previous.weekday() >= 5:
        previous -= timedelta(days=1)
    return previous


def local_date(value: datetime | None = None) -> date:
    current = value or datetime.now(SHANGHAI)
    if current.tzinfo is None:
        current = current.replace(tzinfo=SHANGHAI)
    else:
        current = current.astimezone(SHANGHAI)
    return current.date()
