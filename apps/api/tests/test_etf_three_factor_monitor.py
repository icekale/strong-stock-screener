from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    EtfRadarOverviewResponse,
    EtfSharePoint,
    EtfThreeFactorResponse,
    HuijinEtfActivityItem,
    KlineBar,
)
from app.services.capital_signal_store import CapitalSignalStore
from app.services.etf_three_factor import INDEX_SYMBOL_BY_ETF
from app.services.etf_three_factor_monitor import EtfThreeFactorMonitor
from app.services.etf_three_factor_store import EtfThreeFactorStore
from app.services.huijin_etf_activity import CORE_ETFS


SHANGHAI = ZoneInfo("Asia/Shanghai")


class FakeQuoteProvider:
    def __init__(self, quotes: dict[str, SimpleNamespace]) -> None:
        self.quotes = quotes
        self.calls: list[list[str]] = []
        self.fail = False

    def get_quotes(self, symbols: list[str]) -> list[SimpleNamespace]:
        self.calls.append(symbols)
        if self.fail:
            raise RuntimeError("TickFlow unavailable")
        return [self.quotes[symbol] for symbol in symbols if symbol in self.quotes]


class FakeDailyKlineProvider:
    def __init__(self, bars_by_symbol: dict[str, list[KlineBar]]) -> None:
        self.bars_by_symbol = bars_by_symbol
        self.calls: list[tuple[str, int]] = []
        self.fail_symbols: set[str] = set()

    def get_klines(self, symbol: str, count: int = 40) -> list[KlineBar]:
        self.calls.append((symbol, count))
        if symbol in self.fail_symbols:
            raise RuntimeError("daily Kline unavailable")
        return self.bars_by_symbol[symbol]


class FakeShareSnapshotProvider:
    def __init__(self, overview: EtfRadarOverviewResponse) -> None:
        self.response = overview
        self.calls: list[bool] = []

    def overview(self, *, force: bool = False) -> EtfRadarOverviewResponse:
        self.calls.append(force)
        return self.response


def shanghai(value: str) -> datetime:
    return datetime.fromisoformat(f"{value}+08:00").astimezone(SHANGHAI)


def _quote(symbol: str, *, change: float, volume: float, quote_time: str) -> SimpleNamespace:
    return SimpleNamespace(
        symbol=symbol,
        pct_change=change,
        volume=volume,
        quote_time=quote_time,
    )


def _bars(*, volumes: list[float], closes: list[float], include_partial: bool = True) -> list[KlineBar]:
    completed_dates = [
        "2026-06-20", "2026-06-21", "2026-06-22", "2026-06-23", "2026-06-24",
        "2026-06-25", "2026-06-26", "2026-06-27", "2026-06-28", "2026-06-29",
        "2026-06-30", "2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04",
        "2026-07-05", "2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09",
        "2026-07-21",
    ]
    rows = [
        KlineBar(
            date=trade_date,
            open=close,
            high=close,
            low=close,
            close=close,
            volume=volume,
        )
        for trade_date, volume, close in zip(
            completed_dates[-len(volumes) :], volumes, closes, strict=True
        )
    ]
    if include_partial:
        rows.append(
            KlineBar(
                date="2026-07-22", open=200, high=200, low=200, close=200, volume=10_000
            )
        )
    return rows


def _official_overview(*, trade_date: str, share_change_pct: float | None) -> EtfRadarOverviewResponse:
    items = [
        HuijinEtfActivityItem(
            symbol=symbol,
            name=definition.name,
            index_name=definition.index_name,
            role="core",
            trade_date=trade_date,
            total_shares=1_050 if share_change_pct is not None else None,
            previous_total_shares=1_000 if share_change_pct is not None else None,
            daily_change_pct=share_change_pct,
        )
        for symbol, definition in CORE_ETFS.items()
    ]
    generated_at = f"{trade_date}T19:05:00+08:00"
    return EtfRadarOverviewResponse(
        generated_at=generated_at,
        trade_date=trade_date,
        as_of=generated_at,
        signal_stage="post_close",
        model_version="huijin-public-rule-v1",
        core_items=items,
    )


def _seed_share_history(store: CapitalSignalStore, trade_date: str) -> None:
    store.save_share_history(
        [
            EtfSharePoint(
                trade_date=date,
                symbol=symbol,
                name=definition.name,
                total_shares=total_shares,
            )
            for date, total_shares in [("2026-07-21", 1_000), (trade_date, 1_050)]
            for symbol, definition in CORE_ETFS.items()
        ]
    )


def monitor_with(
    tmp_path: Path,
    *,
    volume: float = 300,
    historical_volumes: list[float] | None = None,
    etf_change: float = 1.2,
    index_change: float = -0.5,
    share_change_pct: float | None = 5.0,
) -> tuple[EtfThreeFactorMonitor, FakeQuoteProvider, FakeDailyKlineProvider, FakeShareSnapshotProvider]:
    historical_volumes = historical_volumes or [50, *([100] * 20)]
    closes = [90, *([100] * (len(historical_volumes) - 2)), 110]
    quote_time = "2026-07-22T10:30:00+08:00"
    quotes = {
        symbol: _quote(symbol, change=etf_change, volume=volume, quote_time=quote_time)
        for symbol in CORE_ETFS
    }
    quotes.update(
        {
            index_symbol: _quote(
                index_symbol, change=index_change, volume=0, quote_time=quote_time
            )
            for index_symbol in INDEX_SYMBOL_BY_ETF.values()
        }
    )
    daily = FakeDailyKlineProvider(
        {
            symbol: _bars(volumes=historical_volumes, closes=closes)
            for symbol in CORE_ETFS
        }
    )
    share_store = CapitalSignalStore(tmp_path)
    _seed_share_history(share_store, "2026-07-22")
    shares = FakeShareSnapshotProvider(
        _official_overview(trade_date="2026-07-22", share_change_pct=share_change_pct)
    )
    quotes_provider = FakeQuoteProvider(quotes)
    monitor = EtfThreeFactorMonitor(
        quote_provider=quotes_provider,
        daily_kline_provider=daily,
        share_snapshot_provider=shares,
        capital_store=share_store,
        store=EtfThreeFactorStore(tmp_path),
    )
    return monitor, quotes_provider, daily, shares


def by_symbol(response: EtfThreeFactorResponse, symbol: str):
    return next(item for item in response.items if item.symbol == symbol)


def test_scan_builds_two_factor_intraday_item(tmp_path: Path) -> None:
    monitor, _, _, shares = monitor_with(tmp_path, share_change_pct=5.0)

    result = monitor.scan(now=shanghai("2026-07-22T10:30:00"))

    item = by_symbol(result, "510050.SH")
    assert item.volume_ratio == 3
    assert item.volume_factor.score == 100
    assert item.direction_factor.score == 100
    assert item.share_factor.status == "pending"
    assert item.signal_score == 100
    assert item.mode == "two_factor"
    assert shares.calls == []


@pytest.mark.parametrize("refresh_time", ["2026-07-22T19:05:00", "2026-07-22T19:35:00"])
def test_post_close_share_refresh_upgrades_to_three_factor(
    tmp_path: Path, refresh_time: str
) -> None:
    monitor, quotes, _, shares = monitor_with(tmp_path, volume=150, share_change_pct=5.0)
    intraday = monitor.scan(now=shanghai("2026-07-22T10:30:00"))

    result = monitor.scan(now=shanghai(refresh_time))

    item = by_symbol(result, "510050.SH")
    intraday_item = by_symbol(intraday, "510050.SH")
    assert item.share_factor.score == 100
    assert item.share_factor.status == "available"
    assert item.mode == "three_factor"
    assert item.volume_ratio == intraday_item.volume_ratio
    assert item.direction_factor.updated_at == intraday_item.direction_factor.updated_at
    assert len(quotes.calls) == 1
    assert shares.calls == [False]


@pytest.mark.parametrize("scan_time", ["2026-07-22T12:00:00", "2026-07-25T10:30:00"])
def test_non_session_scan_reuses_snapshot_without_provider_calls_or_alerts(
    tmp_path: Path, scan_time: str
) -> None:
    monitor, quotes, daily, shares = monitor_with(tmp_path)
    previous = monitor.scan(now=shanghai("2026-07-22T10:30:00"))
    calls = (len(quotes.calls), len(daily.calls), len(shares.calls))
    alerts = monitor.store.load_alerts()

    result = monitor.scan(now=shanghai(scan_time))

    assert result == previous
    assert (len(quotes.calls), len(daily.calls), len(shares.calls)) == calls
    assert monitor.store.load_alerts() == alerts


def test_non_session_scan_without_snapshot_is_unavailable_without_quote_calls(tmp_path: Path) -> None:
    monitor, quotes, daily, shares = monitor_with(tmp_path)

    result = monitor.scan(now=shanghai("2026-07-22T12:00:00"))

    assert not result.monitor_running
    assert result.source_status[0].status == "failed"
    assert quotes.calls == []
    assert daily.calls == []
    assert shares.calls == []


def test_completed_day_baseline_excludes_current_partial_day(tmp_path: Path) -> None:
    monitor, _, _, _ = monitor_with(tmp_path)

    item = by_symbol(monitor.scan(now=shanghai("2026-07-22T10:30:00")), "510050.SH")

    assert item.average_volume_20d == 100
    assert item.volume_ratio == 3


def test_insufficient_completed_history_leaves_volume_unavailable(tmp_path: Path) -> None:
    monitor, _, _, _ = monitor_with(tmp_path, historical_volumes=[100] * 19)

    item = by_symbol(monitor.scan(now=shanghai("2026-07-22T10:30:00")), "510050.SH")

    assert item.average_volume_20d is None
    assert item.volume_factor.status == "missing"
    assert item.volume_factor.detail == "当前成交量或20个已完成交易日成交量不足"
    assert item.mode == "incomplete"


def test_daily_kline_provider_error_is_cached_for_completed_date_context(tmp_path: Path) -> None:
    monitor, _, daily, _ = monitor_with(tmp_path)
    daily.fail_symbols.add("510050.SH")

    item = by_symbol(monitor.scan(now=shanghai("2026-07-22T10:30:00")), "510050.SH")
    monitor.scan(now=shanghai("2026-07-22T10:31:00"))

    assert item.volume_factor.status == "missing"
    assert item.volume_factor.detail == "日K线请求失败: RuntimeError"
    assert daily.calls.count(("510050.SH", 40)) == 1


@pytest.mark.parametrize("missing_symbol", ["510050.SH", "000016.SH"])
def test_missing_quote_keeps_old_snapshot_and_creates_no_alert(
    tmp_path: Path, missing_symbol: str
) -> None:
    monitor, quotes, _, _ = monitor_with(tmp_path, volume=100)
    previous = monitor.scan(now=shanghai("2026-07-22T10:30:00"))
    quotes.quotes.pop(missing_symbol)

    result = monitor.scan(now=shanghai("2026-07-22T10:31:00"))

    assert result == previous
    assert monitor.store.load_alerts() == []


def test_stale_quote_keeps_old_snapshot_and_creates_no_alert(tmp_path: Path) -> None:
    monitor, quotes, _, _ = monitor_with(tmp_path, volume=100)
    previous = monitor.scan(now=shanghai("2026-07-22T10:30:00"))
    quotes.quotes["510050.SH"].quote_time = "2026-07-21T14:59:00+08:00"

    result = monitor.scan(now=shanghai("2026-07-22T10:31:00"))

    assert result == previous
    assert monitor.store.load_alerts() == []


def test_completed_close_change_uses_the_last_two_completed_bars(tmp_path: Path) -> None:
    monitor, _, _, _ = monitor_with(tmp_path)

    item = by_symbol(monitor.scan(now=shanghai("2026-07-22T10:30:00")), "510050.SH")

    assert item.close_change_pct == pytest.approx(10)
    assert item.close_change_trade_date == "2026-07-21"


def test_post_close_close_change_uses_completed_current_day_not_cached_partial_bar(
    tmp_path: Path,
) -> None:
    monitor, quotes, daily, _ = monitor_with(tmp_path)
    monitor.scan(now=shanghai("2026-07-22T10:30:00"))
    for symbol, bars in daily.bars_by_symbol.items():
        bars[-1] = KlineBar(
            date="2026-07-22",
            open=132,
            high=132,
            low=132,
            close=132,
            volume=300,
        )

    result = monitor.scan(now=shanghai("2026-07-22T15:05:00"))

    item = by_symbol(result, "510050.SH")
    assert item.close_change_pct == pytest.approx(20)
    assert item.close_change_trade_date == "2026-07-22"
    assert len(quotes.calls) == 1
    assert len(daily.calls) == 2 * len(CORE_ETFS)

    monitor.scan(now=shanghai("2026-07-22T15:06:00"))

    assert len(daily.calls) == 2 * len(CORE_ETFS)


def test_scan_caches_daily_bars_and_upserts_one_history_point_per_trade_date(tmp_path: Path) -> None:
    monitor, _, daily, _ = monitor_with(tmp_path)

    monitor.scan(now=shanghai("2026-07-22T10:30:00"))
    monitor.scan(now=shanghai("2026-07-22T10:31:00"))

    assert len(daily.calls) == len(CORE_ETFS)
    assert len(monitor.store.load_history("510050.SH", days=40)) == 1


def test_latest_reads_persisted_snapshot_without_provider_calls(tmp_path: Path) -> None:
    monitor, quotes, daily, shares = monitor_with(tmp_path)
    monitor.scan(now=shanghai("2026-07-22T10:30:00"))
    scanned = monitor.scan(now=shanghai("2026-07-22T19:05:00"))
    calls = (len(quotes.calls), len(daily.calls), len(shares.calls))

    assert monitor.latest() == scanned
    assert (len(quotes.calls), len(daily.calls), len(shares.calls)) == calls


def test_alerts_are_created_only_on_high_entry_and_three_factor_upgrade(tmp_path: Path) -> None:
    monitor, quotes, _, _ = monitor_with(tmp_path, volume=150)

    monitor.scan(now=shanghai("2026-07-22T10:30:00"))
    initial_alerts = monitor.store.load_alerts()
    monitor.scan(now=shanghai("2026-07-22T19:05:00"))
    alerts = monitor.store.load_alerts()
    monitor.scan(now=shanghai("2026-07-22T19:06:00"))

    assert initial_alerts == []
    assert len(alerts) == len(CORE_ETFS) + 1
    assert {alert.alert_type for alert in alerts} == {"single_upgrade", "market_high"}
    assert monitor.store.load_alerts() == alerts
    assert all("疑似活动" in alert.title for alert in alerts)
    assert all("量比" in alert.message and "行情时间" in alert.message for alert in alerts)
    market_alert = next(alert for alert in alerts if alert.alert_type == "market_high")
    assert "量能时间 2026-07-22T10:30:00+08:00" in market_alert.message
    assert "行情时间 2026-07-22T10:30:00+08:00" in market_alert.message
    assert "份额时间 2026-07-22T19:05:00+08:00" in market_alert.message
    assert len(quotes.calls) == 1


def test_market_watch_alert_is_created_only_when_entering_watch(tmp_path: Path) -> None:
    monitor, quotes, _, _ = monitor_with(tmp_path, volume=100)
    monitor.scan(now=shanghai("2026-07-22T10:30:00"))
    for symbol in list(CORE_ETFS)[:3]:
        quotes.quotes[symbol].volume = 300

    monitor.scan(now=shanghai("2026-07-22T10:31:00"))
    alerts = monitor.store.load_alerts()
    monitor.scan(now=shanghai("2026-07-22T10:32:00"))

    assert {alert.alert_type for alert in alerts} == {"single_high", "market_watch"}
    assert monitor.store.load_alerts() == alerts


def test_post_close_missing_share_data_is_not_marked_pending(tmp_path: Path) -> None:
    monitor, _, _, _ = monitor_with(tmp_path, share_change_pct=None)
    monitor.scan(now=shanghai("2026-07-22T10:30:00"))

    item = by_symbol(monitor.scan(now=shanghai("2026-07-22T19:05:00")), "510050.SH")

    assert item.share_factor.status == "missing"
    assert item.mode == "incomplete"


def test_post_close_stale_share_data_is_not_marked_pending(tmp_path: Path) -> None:
    monitor, _, _, shares = monitor_with(tmp_path)
    monitor.scan(now=shanghai("2026-07-22T10:30:00"))
    shares.response = _official_overview(trade_date="2026-07-21", share_change_pct=5.0)

    item = by_symbol(monitor.scan(now=shanghai("2026-07-22T19:05:00")), "510050.SH")

    assert item.share_factor.status == "stale"
    assert item.mode == "incomplete"


def test_history_returns_persisted_symbol_points(tmp_path: Path) -> None:
    monitor, _, _, _ = monitor_with(tmp_path)
    monitor.scan(now=shanghai("2026-07-22T10:30:00"))

    history = monitor.history("510050.SH")

    assert history.symbol == "510050.SH"
    assert [point.trade_date for point in history.points] == ["2026-07-22"]


def test_enrich_overview_uses_close_changes_without_mutating_capital_snapshot(tmp_path: Path) -> None:
    monitor, _, _, shares = monitor_with(tmp_path)
    overview = shares.response
    monitor.scan(now=shanghai("2026-07-22T10:30:00"))

    enriched = monitor.enrich_overview(overview)

    original = next(item for item in overview.core_items if item.symbol == "510050.SH")
    updated = next(item for item in enriched.core_items if item.symbol == "510050.SH")
    assert original.close_change_pct is None
    assert updated.close_change_pct == pytest.approx(10)
    assert updated.close_change_trade_date == "2026-07-21"


def test_enrich_overview_returns_original_when_monitor_snapshot_is_unavailable(tmp_path: Path) -> None:
    monitor, _, _, shares = monitor_with(tmp_path)

    assert monitor.enrich_overview(shares.response) is shares.response
