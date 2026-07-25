from datetime import datetime

import pytest

from app.models import KlineBar
from app.services.etf_price_history import EtfPriceHistoryService, EtfPriceHistoryUnavailable


class FakeProvider:
    source_name = "测试日K"

    def __init__(self) -> None:
        self.calls = 0

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        self.calls += 1
        return [
            KlineBar(date="2026-07-16", open=2.0, close=2.1, high=2.2, low=1.9, volume=1),
            KlineBar(date="2026-07-17", open=2.1, close=2.2, high=2.3, low=2.0, volume=1),
            KlineBar(date="2026-07-18", open=2.2, close=2.3, high=2.4, low=2.1, volume=1),
        ]


def test_returns_real_close_points_and_uses_short_cache() -> None:
    provider = FakeProvider()
    service = EtfPriceHistoryService(
        provider=provider,
        clock=lambda: datetime.fromisoformat("2026-07-18T16:00:00+08:00"),
    )

    first = service.history("510050.SH", days=2)
    second = service.history("510050.SH", days=2)

    assert [point.model_dump() for point in first.points] == [
        {"trade_date": "2026-07-17", "close": 2.2},
        {"trade_date": "2026-07-18", "close": 2.3},
    ]
    assert first.symbol == "510050.SH"
    assert first.source_status[0].source == "测试日K"
    assert second == first
    assert provider.calls == 1


def test_raises_when_provider_returns_no_valid_close_points() -> None:
    class EmptyProvider(FakeProvider):
        def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
            self.calls += 1
            return []

    with pytest.raises(EtfPriceHistoryUnavailable, match="没有可用的日收盘价"):
        EtfPriceHistoryService(provider=EmptyProvider()).history("510050.SH")


def test_normalizes_compact_provider_trade_dates() -> None:
    class CompactDateProvider(FakeProvider):
        def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
            return [
                KlineBar(date="20260723", open=3.0, close=3.08, high=3.1, low=3.0, volume=1),
                KlineBar(date="20260724", open=3.08, close=3.05, high=3.1, low=3.0, volume=1),
            ]

    response = EtfPriceHistoryService(provider=CompactDateProvider()).history("510050.SH", days=2)

    assert [point.trade_date for point in response.points] == ["2026-07-23", "2026-07-24"]
