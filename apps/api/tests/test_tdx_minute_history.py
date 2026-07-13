from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings
from app.main import _chanlun_history_provider, app
from app.models import StrongStockDataUnavailable
from app.providers.tdx_minute_history import TdxMinuteHistoryProvider


SHANGHAI = ZoneInfo("Asia/Shanghai")


class FakeFrame:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def to_dict(self, orient: str) -> list[dict[str, object]]:
        assert orient == "records"
        return self.rows


class FakeMootdxClient:
    def __init__(self, pages: list[FakeFrame]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, int, int, int]] = []
        self.closed = False

    def bars(self, *, symbol: str, frequency: int, start: int, offset: int) -> FakeFrame:
        self.calls.append((symbol, frequency, start, offset))
        return self.pages[len(self.calls) - 1]

    def close(self) -> None:
        self.closed = True


def frame_for(*rows: dict[str, object]) -> FakeFrame:
    return FakeFrame(list(rows))


def tdx_row(
    value: str,
    *,
    close: float = 10.0,
    low: float = 9.8,
    high: float = 10.2,
) -> dict[str, object]:
    return {
        "datetime": value,
        "open": 9.9,
        "high": high,
        "low": low,
        "close": close,
        "vol": 100,
        "amount": 1_000,
    }


def test_provider_requests_one_minute_category_in_pages_and_normalizes_bars() -> None:
    client = FakeMootdxClient(
        pages=[
            frame_for(
                tdx_row("2026-07-10 09:31"),
                tdx_row("2026-07-10 09:32", close=0),
            ),
            frame_for(
                tdx_row("2026-07-10 09:31", close=10.5, high=10.7),
                tdx_row("2026-07-10 09:32", close=11.0, high=11.2),
            ),
        ]
    )
    provider = TdxMinuteHistoryProvider(
        client_factory=lambda: client,
        enabled=True,
        timeout_seconds=3,
    )

    bars = provider.get_minute_bars("600000.SH", max_bars=1600)

    assert client.calls == [("600000", 7, 0, 800), ("600000", 7, 800, 800)]
    assert client.closed is True
    assert [bar.timestamp for bar in bars] == sorted(bar.timestamp for bar in bars)
    assert [bar.close for bar in bars] == [10.5, 11.0]
    assert datetime.fromtimestamp(bars[0].timestamp / 1000, tz=SHANGHAI).isoformat() == (
        "2026-07-10T09:30:00+08:00"
    )


def test_provider_sizes_final_page_and_caps_returned_bars() -> None:
    start = datetime(2026, 7, 10, 9, 30)
    client = FakeMootdxClient(
        pages=[
            frame_for(
                *[
                    tdx_row(start + timedelta(minutes=index))
                    for index in range(800)
                ]
            ),
            frame_for(
                *[
                    tdx_row(start + timedelta(minutes=index))
                    for index in range(800, 1600)
                ]
            ),
        ]
    )
    provider = TdxMinuteHistoryProvider(
        client_factory=lambda: client,
        enabled=True,
        timeout_seconds=3,
    )

    bars = provider.get_minute_bars("600000.SH", max_bars=1000)

    assert client.calls == [("600000", 7, 0, 800), ("600000", 7, 800, 200)]
    assert len(bars) == 1000


def test_disabled_provider_never_constructs_a_client() -> None:
    provider = TdxMinuteHistoryProvider(
        client_factory=lambda: (_ for _ in ()).throw(AssertionError("client constructed")),
        enabled=False,
        timeout_seconds=3,
    )

    with pytest.raises(StrongStockDataUnavailable, match="通达信分钟历史未启用"):
        provider.get_minute_bars("600000.SH", max_bars=800)


def test_chanlun_history_provider_uses_enabled_default_from_base_settings(monkeypatch) -> None:
    monkeypatch.delenv("STRONG_STOCK_CHANLUN_TDX_ENABLED", raising=False)
    monkeypatch.delattr(app.state, "chanlun_history_provider", raising=False)
    monkeypatch.setattr("app.main.get_settings", lambda: Settings(_env_file=None))

    provider = _chanlun_history_provider()

    assert provider.enabled is True


def test_chanlun_history_provider_reads_disabled_environment_setting(monkeypatch) -> None:
    monkeypatch.setenv("STRONG_STOCK_CHANLUN_TDX_ENABLED", "false")
    monkeypatch.delattr(app.state, "chanlun_history_provider", raising=False)
    monkeypatch.setattr("app.main.get_settings", lambda: Settings(_env_file=None))

    provider = _chanlun_history_provider()

    assert provider.enabled is False
