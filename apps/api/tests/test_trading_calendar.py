from datetime import date

from app.services.trading_calendar import is_open_session, previous_open_session


def test_trading_calendar_rejects_weekends_and_exchange_holidays() -> None:
    assert is_open_session(date(2026, 7, 4)) is False
    assert is_open_session(date(2026, 10, 1)) is False
    assert is_open_session(date(2026, 9, 30)) is True


def test_previous_open_session_skips_exchange_holiday_and_weekend() -> None:
    assert previous_open_session(date(2026, 10, 5)) == date(2026, 9, 30)
