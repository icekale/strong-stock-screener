from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.models import EtfHolderPosition, EtfSharePoint, MarginMarketPoint, StrongStockSourceStatus
from app.providers.capital_signals import CapitalProviderResult
from app.services.capital_signal_store import CapitalSignalStore
from app.services.capital_signals import (
    CapitalSignalService,
    build_share_change,
    robust_z_score,
    synchronization_ratio,
)


def test_estimated_subscription_uses_share_delta_times_close() -> None:
    result = build_share_change(
        current_shares=12_000_000,
        previous_shares=10_000_000,
        close=4.25,
    )

    assert result.share_change == 2_000_000
    assert result.estimated_subscription_cny == 8_500_000


def test_missing_previous_shares_stays_missing_instead_of_zero() -> None:
    result = build_share_change(
        current_shares=12_000_000,
        previous_shares=None,
        close=4.25,
    )

    assert result.share_change is None
    assert result.estimated_subscription_cny is None


def test_missing_close_keeps_subscription_amount_missing() -> None:
    result = build_share_change(
        current_shares=12_000_000,
        previous_shares=10_000_000,
        close=None,
    )

    assert result.share_change == 2_000_000
    assert result.estimated_subscription_cny is None


def test_robust_score_uses_median_absolute_deviation() -> None:
    assert robust_z_score(16, [9, 10, 10, 11, 12]) == pytest.approx(4.047, rel=1e-3)


def test_robust_score_is_missing_when_history_has_no_dispersion() -> None:
    assert robust_z_score(11, [10, 10, 10]) is None


def test_synchronization_excludes_missing_etfs_from_denominator() -> None:
    result = synchronization_ratio([True, False, None, True])

    assert result.positive_count == 2
    assert result.valid_count == 3
    assert result.ratio == pytest.approx(2 / 3)


def test_synchronization_is_missing_without_valid_etfs() -> None:
    result = synchronization_ratio([None, None])

    assert result.positive_count == 0
    assert result.valid_count == 0
    assert result.ratio is None


class FakeCapitalProvider:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.margin_calls: list[str] = []
        self.share_calls: list[tuple[str, tuple[str, ...]]] = []

    def get_margin_rows(self, trade_date: str) -> CapitalProviderResult[MarginMarketPoint]:
        self.margin_calls.append(trade_date)
        if self.fail:
            return CapitalProviderResult(
                rows=[],
                source_status=[StrongStockSourceStatus(source="两融", status="failed", detail="offline")],
            )
        values = {
            "2026-07-17": (1_100_000_000, 900_000_000),
            "2026-07-16": (1_000_000_000, 800_000_000),
        }.get(trade_date)
        rows = (
            [
                MarginMarketPoint(
                    trade_date=trade_date,
                    market="SSE",
                    financing_balance_cny=values[0] - 10_000_000,
                    securities_lending_balance_cny=10_000_000,
                    margin_balance_cny=values[0],
                    financing_buy_cny=100_000_000,
                ),
                MarginMarketPoint(
                    trade_date=trade_date,
                    market="SZSE",
                    financing_balance_cny=values[1] - 5_000_000,
                    securities_lending_balance_cny=5_000_000,
                    margin_balance_cny=values[1],
                    financing_buy_cny=80_000_000,
                ),
            ]
            if values
            else []
        )
        return CapitalProviderResult(
            rows=rows,
            source_status=[StrongStockSourceStatus(source="两融", status="success", detail="fake")],
        )

    def get_etf_share_rows(
        self,
        trade_date: str,
        symbols: list[str] | tuple[str, ...],
    ) -> CapitalProviderResult[EtfSharePoint]:
        self.share_calls.append((trade_date, tuple(symbols)))
        if self.fail:
            return CapitalProviderResult(
                rows=[],
                source_status=[StrongStockSourceStatus(source="ETF份额", status="failed", detail="offline")],
            )
        shares = {
            "2026-07-17": {"510300.SH": 12_000_000, "159915.SZ": 9_000_000},
            "2026-07-16": {"510300.SH": 10_000_000},
        }.get(trade_date, {})
        rows = [
            EtfSharePoint(
                trade_date=trade_date,
                symbol=symbol,
                name="测试ETF",
                total_shares=total_shares,
            )
            for symbol, total_shares in shares.items()
            if symbol in symbols
        ]
        return CapitalProviderResult(
            rows=rows,
            source_status=[StrongStockSourceStatus(source="ETF份额", status="success", detail="fake")],
        )


class FakeQuoteProvider:
    def get_quotes(self, symbols: list[str]) -> list[SimpleNamespace]:
        return [SimpleNamespace(symbol=symbol, last_price=4.25) for symbol in symbols]


def _clock() -> datetime:
    return datetime(2026, 7, 19, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def test_service_builds_and_persists_share_evidence(tmp_path: Path) -> None:
    provider = FakeCapitalProvider()
    store = CapitalSignalStore(tmp_path)
    service = CapitalSignalService(
        provider=provider,
        store=store,
        quote_provider=FakeQuoteProvider(),
        clock=_clock,
    )

    snapshot = service.overview(force=True)

    item = next(row for row in snapshot.items if row.symbol == "510300.SH")
    assert snapshot.trade_date == "2026-07-17"
    assert snapshot.signal_stage == "post_close"
    assert item.share_change == 2_000_000
    assert item.estimated_subscription_cny == 8_500_000
    assert snapshot.valid_etf_count == 1
    assert store.load_snapshot() == snapshot
    assert provider.share_calls[0][0] == "2026-07-17"
    assert provider.share_calls[1][0] == "2026-07-16"
    assert provider.share_calls[1][1] == (
        "510300.SH",
        "510310.SH",
        "510500.SH",
        "512100.SH",
        "563360.SH",
        "588000.SH",
    )


def test_homepage_summary_combines_markets_and_reuses_hot_cache(tmp_path: Path) -> None:
    provider = FakeCapitalProvider()
    service = CapitalSignalService(
        provider=provider,
        store=CapitalSignalStore(tmp_path),
        quote_provider=FakeQuoteProvider(),
        clock=_clock,
    )

    first = service.homepage_summary()
    second = service.homepage_summary()

    assert first == second
    assert first.margin.balance_cny == 2_000_000_000
    assert first.margin.change_cny == 200_000_000
    assert first.margin.change_pct == pytest.approx(11.1111, rel=1e-3)
    assert first.margin.available_markets == 2
    assert provider.margin_calls == ["2026-07-17", "2026-07-16"]
    assert len(provider.share_calls) == 2


def test_margin_change_compares_only_markets_available_on_both_dates(tmp_path: Path) -> None:
    class CurrentSseOnlyProvider(FakeCapitalProvider):
        def get_margin_rows(self, trade_date: str) -> CapitalProviderResult[MarginMarketPoint]:
            result = super().get_margin_rows(trade_date)
            if trade_date == "2026-07-17":
                return CapitalProviderResult(
                    rows=[row for row in result.rows if row.market == "SSE"],
                    source_status=result.source_status,
                )
            return result

    service = CapitalSignalService(
        provider=CurrentSseOnlyProvider(),
        store=CapitalSignalStore(tmp_path),
        quote_provider=FakeQuoteProvider(),
        clock=_clock,
    )

    summary = service.homepage_summary()

    assert summary.margin.balance_cny == 1_100_000_000
    assert summary.margin.available_markets == 1
    assert summary.margin.change_cny == 100_000_000
    assert summary.margin.change_pct == pytest.approx(10)


def test_service_returns_cached_snapshot_as_stale_when_refresh_fails(tmp_path: Path) -> None:
    store = CapitalSignalStore(tmp_path)
    fresh_service = CapitalSignalService(
        provider=FakeCapitalProvider(),
        store=store,
        quote_provider=FakeQuoteProvider(),
        clock=_clock,
    )
    fresh = fresh_service.overview(force=True)
    failed_service = CapitalSignalService(
        provider=FakeCapitalProvider(fail=True),
        store=store,
        quote_provider=FakeQuoteProvider(),
        clock=_clock,
    )

    stale = failed_service.overview(force=True)

    assert stale.items == fresh.items
    assert stale.generated_at == fresh.generated_at
    assert stale.source_status[-1].status == "stale"
    assert "缓存" in stale.source_status[-1].detail


def test_service_merges_partial_refresh_with_same_day_persisted_rows(tmp_path: Path) -> None:
    store = CapitalSignalStore(tmp_path)
    initial_service = CapitalSignalService(
        provider=FakeCapitalProvider(),
        store=store,
        quote_provider=FakeQuoteProvider(),
        clock=_clock,
    )
    initial = initial_service.overview(force=True)

    class SzseOnlyRefreshProvider(FakeCapitalProvider):
        def get_etf_share_rows(
            self,
            trade_date: str,
            symbols: list[str] | tuple[str, ...],
        ) -> CapitalProviderResult[EtfSharePoint]:
            result = super().get_etf_share_rows(trade_date, symbols)
            return CapitalProviderResult(
                rows=[row for row in result.rows if row.symbol.endswith(".SZ")],
                source_status=[
                    StrongStockSourceStatus(source="上交所ETF份额", status="failed", detail="timeout"),
                    StrongStockSourceStatus(source="深交所ETF份额", status="success", detail="fresh"),
                ],
            )

    partial_service = CapitalSignalService(
        provider=SzseOnlyRefreshProvider(),
        store=store,
        quote_provider=FakeQuoteProvider(),
        clock=_clock,
    )

    refreshed = partial_service.overview(force=True)

    assert {item.symbol for item in initial.items} == {"510300.SH", "159915.SZ"}
    assert {item.symbol for item in refreshed.items} == {"510300.SH", "159915.SZ"}
    assert any(item.source == "上交所ETF份额" and item.status == "failed" for item in refreshed.source_status)


def test_service_returns_unavailable_snapshot_without_cache(tmp_path: Path) -> None:
    service = CapitalSignalService(
        provider=FakeCapitalProvider(fail=True),
        store=CapitalSignalStore(tmp_path),
        quote_provider=FakeQuoteProvider(),
        clock=_clock,
    )

    snapshot = service.overview(force=True)

    assert snapshot.trade_date == "2026-07-17"
    assert snapshot.items == []
    assert snapshot.evidence_strength is None
    assert any(item.status == "failed" for item in snapshot.source_status)


def test_methodology_calls_no_remote_provider(tmp_path: Path) -> None:
    provider = FakeCapitalProvider()
    service = CapitalSignalService(
        provider=provider,
        store=CapitalSignalStore(tmp_path),
        clock=_clock,
    )

    result = service.methodology()

    assert result.model_version == "heuristic-v1"
    assert len(result.core_pool) == 7
    assert result.thresholds["strong"] == 70
    assert provider.margin_calls == []
    assert provider.share_calls == []


def test_holders_fetches_exact_positions_once_then_reuses_store(tmp_path: Path) -> None:
    class FakeHolderProvider:
        def __init__(self) -> None:
            self.calls = 0

        def get_holder_positions(self, symbols: dict[str, str]):
            self.calls += 1
            assert symbols["510300.SH"] == "沪深300ETF"
            return CapitalProviderResult(
                rows=[
                    EtfHolderPosition(
                        symbol="510300.SH",
                        name="沪深300ETF",
                        report_period="2025-12-31",
                        entity_name="中央汇金投资有限责任公司",
                        shares=35_654_600_000,
                        holding_pct=40.14,
                        change_shares=1_000_000,
                        source="新浪财经基金持有人",
                    )
                ],
                source_status=[
                    StrongStockSourceStatus(source="新浪基金持有人", status="success", detail="fake")
                ],
            )

    holder_provider = FakeHolderProvider()
    service = CapitalSignalService(
        provider=FakeCapitalProvider(),
        holder_provider=holder_provider,
        store=CapitalSignalStore(tmp_path),
        clock=_clock,
    )

    first = service.holders()
    second = service.holders()

    assert first.positions == second.positions
    assert first.positions[0].report_period == "2025-12-31"
    assert first.signal_stage == "disclosure"
    assert holder_provider.calls == 1
