from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    EtfHolderPosition,
    EtfRadarHistoryPoint,
    EtfRadarHoldersResponse,
    EtfRadarItem,
    EtfRadarOverviewResponse,
    EtfRadarSummary,
    EtfSharePoint,
    MarginMarketPoint,
    StrongStockSourceStatus,
)
from app.providers.capital_signals import CapitalProviderResult
from app.services.capital_signal_store import CapitalSignalStore
from app.services.capital_signals import (
    CapitalSignalService,
    build_share_change,
    robust_z_score,
    synchronization_ratio,
)
from app.services.huijin_etf_activity import ALL_ETFS, CORE_ETFS, POOL_VERSION, build_baselines


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
        deltas = {
            "510050.SH": 1,
            "510300.SH": 20,
            "510500.SH": -30,
            "512100.SH": 5,
            "159915.SZ": 0,
            "510230.SH": 40,
            "588080.SH": 2,
            "159919.SZ": 10,
            "159922.SZ": -10,
            "159845.SZ": 5,
        }
        shares = (
            {symbol: 1_000 + delta for symbol, delta in deltas.items()}
            if trade_date == "2026-07-17"
            else {symbol: 1_000 for symbol in symbols if symbol.endswith(".SH")}
            if trade_date == "2026-07-16"
            else {}
        )
        rows = [
            EtfSharePoint(
                trade_date=trade_date,
                symbol=symbol,
                name=ALL_ETFS[symbol].name if symbol in ALL_ETFS else symbol,
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


def _holder_positions(report_period: str = "2025-12-31") -> list[EtfHolderPosition]:
    return [
        EtfHolderPosition(
            symbol=symbol,
            name=definition.name,
            report_period=report_period,
            entity_name="中央汇金投资有限责任公司",
            shares=100,
            holding_pct=10,
            source="测试持有人披露",
        )
        for symbol, definition in ALL_ETFS.items()
    ]


class FakeHolderProvider:
    def __init__(self, *, fail: bool = False, positions: list[EtfHolderPosition] | None = None) -> None:
        self.fail = fail
        self.positions = positions if positions is not None else _holder_positions()
        self.calls: list[dict[str, str]] = []

    def get_holder_positions(self, symbols: dict[str, str]):
        self.calls.append(symbols)
        if self.fail:
            return CapitalProviderResult(
                rows=[],
                source_status=[
                    StrongStockSourceStatus(source="基金持有人", status="failed", detail="offline")
                ],
            )
        return CapitalProviderResult(
            rows=self.positions,
            source_status=[
                StrongStockSourceStatus(source="基金持有人", status="success", detail="fake")
            ],
        )


def _seed_prior_rows(
    store: CapitalSignalStore,
    *,
    missing: set[str] | None = None,
) -> None:
    missing = missing or set()
    store.save_share_history(
        [
            EtfSharePoint(
                trade_date="2026-07-16",
                symbol=symbol,
                name=definition.name,
                total_shares=1_000,
            )
            for symbol, definition in ALL_ETFS.items()
            if symbol not in missing
        ]
    )


def _service(
    tmp_path: Path,
    *,
    provider: FakeCapitalProvider | None = None,
    holder_provider: FakeHolderProvider | None = None,
) -> tuple[CapitalSignalService, CapitalSignalStore]:
    store = CapitalSignalStore(tmp_path)
    return (
        CapitalSignalService(
            provider=provider or FakeCapitalProvider(),
            store=store,
            quote_provider=FakeQuoteProvider(),
            holder_provider=holder_provider or FakeHolderProvider(),
            clock=_clock,
        ),
        store,
    )


def test_additive_response_models_keep_compatibility_defaults() -> None:
    metadata = {
        "generated_at": "2026-07-19T10:00:00+08:00",
        "trade_date": "2026-07-17",
        "as_of": "2026-07-19T10:00:00+08:00",
        "signal_stage": "post_close",
        "model_version": "huijin-public-rule-v1",
    }

    assert EtfRadarSummary().activity.core_count == 7
    assert EtfRadarOverviewResponse(**metadata).pool_version == POOL_VERSION
    assert EtfRadarOverviewResponse(**metadata).core_items == []
    assert EtfRadarHistoryPoint(
        trade_date="2026-07-17", symbol="510050.SH", name="上证50ETF华夏"
    ).daily_change_pct is None
    assert EtfRadarHoldersResponse(**metadata).baselines == []


def test_service_builds_complete_huijin_activity_and_legacy_mapping(tmp_path: Path) -> None:
    provider = FakeCapitalProvider()
    holder_provider = FakeHolderProvider()
    service, store = _service(tmp_path, provider=provider, holder_provider=holder_provider)
    _seed_prior_rows(store)

    snapshot = service.overview(force=True)

    assert snapshot.trade_date == "2026-07-17"
    assert snapshot.signal_stage == "post_close"
    assert snapshot.model_version == "huijin-public-rule-v1"
    assert snapshot.pool_version == POOL_VERSION
    assert snapshot.baseline_version == "2025-12-31:huijin-public-v1"
    assert len(snapshot.core_items) == 7
    assert len(snapshot.validation_items) == 3
    assert {group.index_name for group in snapshot.validation_groups} == {
        "沪深300",
        "中证500",
        "中证1000",
    }
    assert snapshot.activity.core_count == 7
    assert snapshot.activity.available_core_count == 7
    assert snapshot.activity.tenfold_increase_count == 2
    assert snapshot.activity.tenfold_decrease_count == 1
    assert snapshot.activity.confirmed_increase_group_count == 2
    assert snapshot.activity.confirmed_decrease_group_count == 1
    assert snapshot.activity.divergent_group_count == 0
    assert snapshot.activity.incomplete_group_count == 0
    assert snapshot.activity.strongest_symbol == "510230.SH"
    assert snapshot.activity.strongest_baseline_change_pct == pytest.approx(4)
    core_300 = next(row for row in snapshot.core_items if row.symbol == "510300.SH")
    assert core_300.share_delta == 20
    assert core_300.daily_change_pct == pytest.approx(2)
    assert core_300.baseline_change_pct == pytest.approx(2)
    assert core_300.multiple == pytest.approx(20)
    legacy_300 = next(row for row in snapshot.items if row.symbol == "510300.SH")
    assert legacy_300.share_change == 20
    assert legacy_300.estimated_subscription_cny is None
    assert legacy_300.robust_score is None
    assert legacy_300.evidence == []
    assert snapshot.valid_etf_count == 7
    assert snapshot.expected_etf_count == 7
    assert snapshot.evidence_strength is None
    assert snapshot.estimated_subscription_cny is None
    assert store.load_snapshot() == snapshot
    assert provider.share_calls == [("2026-07-17", tuple(ALL_ETFS))]
    assert holder_provider.calls == [
        {symbol: definition.name for symbol, definition in ALL_ETFS.items()}
    ]


def test_missing_validator_prior_history_makes_group_incomplete(tmp_path: Path) -> None:
    provider = FakeCapitalProvider()
    service, store = _service(tmp_path, provider=provider)
    _seed_prior_rows(store, missing={"159919.SZ"})

    snapshot = service.overview(force=True)

    group = next(item for item in snapshot.validation_groups if item.index_name == "沪深300")
    validator = next(item for item in snapshot.validation_items if item.symbol == "159919.SZ")
    assert validator.previous_total_shares is None
    assert group.state == "incomplete"
    assert snapshot.activity.incomplete_group_count == 1
    assert provider.share_calls == [("2026-07-17", tuple(ALL_ETFS))]


def test_stale_complete_baseline_cache_is_used_truthfully_when_refresh_fails(tmp_path: Path) -> None:
    holder_provider = FakeHolderProvider(fail=True)
    service, store = _service(tmp_path, holder_provider=holder_provider)
    _seed_prior_rows(store)
    stale_baselines = build_baselines(_holder_positions("2025-06-30"))
    store.save_huijin_baselines(stale_baselines)

    snapshot = service.overview(force=True)

    assert snapshot.baseline_version == "2025-06-30:huijin-public-v1"
    assert {item.report_period for item in snapshot.core_items} == {"2025-06-30"}
    assert holder_provider.calls
    assert any(status.status == "stale" and "2025-06-30" in status.detail for status in snapshot.source_status)


def test_fresh_snapshot_is_recomputed_when_baseline_version_changes(tmp_path: Path) -> None:
    provider = FakeCapitalProvider()
    service, store = _service(
        tmp_path,
        provider=provider,
        holder_provider=FakeHolderProvider(fail=True),
    )
    _seed_prior_rows(store)
    store.save_huijin_baselines(build_baselines(_holder_positions("2025-06-30")))
    stale = service.overview(force=True)
    store.save_huijin_baselines(build_baselines(_holder_positions()))
    refreshed_service = CapitalSignalService(
        provider=provider,
        store=store,
        holder_provider=FakeHolderProvider(),
        clock=lambda: datetime(2026, 7, 19, 10, 0, 10, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    refreshed = refreshed_service.overview()

    assert stale.baseline_version == "2025-06-30:huijin-public-v1"
    assert refreshed.baseline_version == "2025-12-31:huijin-public-v1"
    assert refreshed.generated_at != stale.generated_at


@pytest.mark.parametrize("cache_kind", ["old_pool", "partial"])
def test_incompatible_current_period_baseline_cache_triggers_refresh(
    tmp_path: Path, cache_kind: str
) -> None:
    holder_provider = FakeHolderProvider()
    service, store = _service(tmp_path, holder_provider=holder_provider)
    _seed_prior_rows(store)
    cached = build_baselines(_holder_positions())
    if cache_kind == "old_pool":
        cached = [row.model_copy(update={"pool_version": "core-a-share-v1"}) for row in cached]
    else:
        cached = cached[:7]
    store.save_huijin_baselines(cached)

    snapshot = service.overview(force=True)

    assert len(holder_provider.calls) == 1
    assert snapshot.baseline_version == "2025-12-31:huijin-public-v1"
    saved = store.load_huijin_baselines()
    current = [
        row
        for row in saved
        if row.report_period == "2025-12-31" and row.pool_version == POOL_VERSION
    ]
    assert {row.symbol for row in current} == set(ALL_ETFS)


def test_homepage_summary_combines_markets_and_reuses_hot_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeCapitalProvider()
    service, store = _service(tmp_path, provider=provider)
    _seed_prior_rows(store)

    def unexpected_detail_call(*_args, **_kwargs):
        raise AssertionError("homepage must not call ETF detail endpoints")

    monkeypatch.setattr(service, "history", unexpected_detail_call)
    monkeypatch.setattr(service, "holders", unexpected_detail_call)
    monkeypatch.setattr(service, "methodology", unexpected_detail_call)

    first = service.homepage_summary()
    second = service.homepage_summary()

    assert first == second
    assert first.margin.balance_cny == 2_000_000_000
    assert first.margin.change_cny == 200_000_000
    assert first.margin.change_pct == pytest.approx(11.1111, rel=1e-3)
    assert first.margin.available_markets == 2
    assert provider.margin_calls == ["2026-07-17", "2026-07-16"]
    assert provider.share_calls == [("2026-07-17", tuple(ALL_ETFS))]
    assert first.model_version == "huijin-public-rule-v1"
    assert first.etf_radar.activity.available_core_count == 7
    assert first.etf_radar.activity.strongest_symbol == "510230.SH"
    assert first.etf_radar.evidence_strength is None
    assert first.etf_radar.evidence == []


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
        holder_provider=FakeHolderProvider(),
        clock=_clock,
    )
    _seed_prior_rows(service.store)

    summary = service.homepage_summary()

    assert summary.margin.balance_cny == 1_100_000_000
    assert summary.margin.available_markets == 1
    assert summary.margin.change_cny == 100_000_000
    assert summary.margin.change_pct == pytest.approx(10)


def test_service_returns_cached_snapshot_as_stale_when_refresh_fails(tmp_path: Path) -> None:
    store = CapitalSignalStore(tmp_path)
    _seed_prior_rows(store)
    fresh_service = CapitalSignalService(
        provider=FakeCapitalProvider(),
        store=store,
        quote_provider=FakeQuoteProvider(),
        holder_provider=FakeHolderProvider(),
        clock=_clock,
    )
    fresh = fresh_service.overview(force=True)
    store.save_share_history(
        [row for row in store.load_share_history() if row.trade_date != "2026-07-17"]
    )
    failed_service = CapitalSignalService(
        provider=FakeCapitalProvider(fail=True),
        store=store,
        quote_provider=FakeQuoteProvider(),
        holder_provider=FakeHolderProvider(fail=True),
        clock=lambda: datetime(2026, 7, 19, 10, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    stale = failed_service.overview(force=True)

    assert stale.core_items == fresh.core_items
    assert stale.generated_at == fresh.generated_at
    assert stale.source_status[-1].status == "stale"
    assert "缓存" in stale.source_status[-1].detail


def test_zero_row_refresh_recalculates_from_real_same_day_history(tmp_path: Path) -> None:
    store = CapitalSignalStore(tmp_path)
    _seed_prior_rows(store)
    fresh_service = CapitalSignalService(
        provider=FakeCapitalProvider(),
        store=store,
        holder_provider=FakeHolderProvider(),
        clock=_clock,
    )
    cached = fresh_service.overview(force=True)
    store.save_share_history(
        [
            *[
                row
                for row in store.load_share_history()
                if row.trade_date != "2026-07-17"
            ],
            *[
                EtfSharePoint(
                    trade_date="2026-07-17",
                    symbol=symbol,
                    name=definition.name,
                    total_shares=2_000,
                )
                for symbol, definition in ALL_ETFS.items()
            ],
        ]
    )
    failed_service = CapitalSignalService(
        provider=FakeCapitalProvider(fail=True),
        store=store,
        holder_provider=FakeHolderProvider(fail=True),
        clock=lambda: datetime(2026, 7, 19, 10, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    refreshed = failed_service.overview(force=True)

    assert refreshed.generated_at != cached.generated_at
    assert refreshed.model_version == "huijin-public-rule-v1"
    assert len(refreshed.core_items) == 7
    assert len(refreshed.validation_items) == 3
    assert len(refreshed.validation_groups) == 3
    assert refreshed.activity.available_core_count == 7
    assert {item.total_shares for item in refreshed.core_items} == {2_000}
    assert any(status.status == "failed" for status in refreshed.source_status)
    assert any(status.source == "ETF份额缓存" for status in refreshed.source_status)


def test_incompatible_legacy_snapshot_is_ignored_when_no_current_rows(tmp_path: Path) -> None:
    store = CapitalSignalStore(tmp_path)
    store.save_snapshot(
        EtfRadarOverviewResponse(
            generated_at="2026-07-18T10:00:00+08:00",
            trade_date="2026-07-17",
            as_of="2026-07-18T10:00:00+08:00",
            signal_stage="post_close",
            model_version="heuristic-v1",
            pool_version="core-a-share-v1",
            evidence_strength=99,
            evidence_level="较强",
            valid_etf_count=1,
            estimated_subscription_cny=8_500_000,
            evidence=["旧启发式证据"],
            items=[
                EtfRadarItem(
                    symbol="510310.SH",
                    name="旧池ETF",
                    index_name="沪深300",
                    total_shares=12_000_000,
                    share_change=2_000_000,
                    robust_score=8,
                    evidence_strength=99,
                    evidence=["旧项目证据"],
                )
            ],
        )
    )
    service = CapitalSignalService(
        provider=FakeCapitalProvider(fail=True),
        store=store,
        holder_provider=FakeHolderProvider(fail=True),
        clock=_clock,
    )

    result = service.overview(force=True)

    assert result.model_version == "huijin-public-rule-v1"
    assert result.pool_version == POOL_VERSION
    assert len(result.core_items) == 7
    assert len(result.validation_items) == 3
    assert len(result.validation_groups) == 3
    assert all(item.total_shares is None for item in [*result.core_items, *result.validation_items])
    assert result.activity.available_core_count == 0
    assert result.evidence_strength is None
    assert result.evidence_level is None
    assert result.estimated_subscription_cny is None
    assert result.evidence == []
    assert {item.symbol for item in result.items} == set(CORE_ETFS)
    assert all(item.robust_score is None and item.evidence == [] for item in result.items)
    assert any(
        status.status == "stale" and "不兼容" in status.detail and "忽略" in status.detail
        for status in result.source_status
    )


def test_service_merges_partial_refresh_with_same_day_persisted_rows(tmp_path: Path) -> None:
    store = CapitalSignalStore(tmp_path)
    _seed_prior_rows(store)
    store.save_share_history(
        [
            *store.load_share_history(),
            *[
                EtfSharePoint(
                    trade_date="2026-07-17",
                    symbol=symbol,
                    name=definition.name,
                    total_shares=1_000,
                )
                for symbol, definition in ALL_ETFS.items()
                if symbol.endswith(".SH")
            ],
        ]
    )

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
        holder_provider=FakeHolderProvider(),
        clock=_clock,
    )

    refreshed = partial_service.overview(force=True)

    assert refreshed.activity.available_core_count == 7
    assert {item.symbol for item in refreshed.core_items} == set(CORE_ETFS)
    assert next(item for item in refreshed.core_items if item.symbol == "510050.SH").total_shares == 1_000
    assert next(item for item in refreshed.core_items if item.symbol == "159915.SZ").total_shares == 1_000
    assert any(item.source == "上交所ETF份额" and item.status == "failed" for item in refreshed.source_status)
    assert {
        row.symbol
        for row in store.load_share_history()
        if row.trade_date == "2026-07-17"
    } == set(ALL_ETFS)


def test_service_returns_unavailable_snapshot_without_cache(tmp_path: Path) -> None:
    service = CapitalSignalService(
        provider=FakeCapitalProvider(fail=True),
        store=CapitalSignalStore(tmp_path),
        quote_provider=FakeQuoteProvider(),
        holder_provider=FakeHolderProvider(fail=True),
        clock=_clock,
    )

    snapshot = service.overview(force=True)

    assert snapshot.trade_date == "2026-07-17"
    assert len(snapshot.core_items) == 7
    assert len(snapshot.validation_items) == 3
    assert all(item.total_shares is None for item in [*snapshot.core_items, *snapshot.validation_items])
    assert snapshot.items[0].total_shares is None
    assert snapshot.evidence_strength is None
    assert any(item.status == "failed" for item in snapshot.source_status)
    assert service.store.load_share_history() == []


def test_history_uses_only_real_dates_exact_pool_and_applicable_baseline(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    store.save_share_history(
        [
            EtfSharePoint(
                trade_date="2026-07-15",
                symbol="510300.SH",
                name=ALL_ETFS["510300.SH"].name,
                total_shares=1_000,
                estimated_subscription_cny=999,
                robust_score=8,
            ),
            EtfSharePoint(
                trade_date="2026-07-17",
                symbol="510300.SH",
                name=ALL_ETFS["510300.SH"].name,
                total_shares=1_020,
            ),
            EtfSharePoint(
                trade_date="2026-07-16",
                symbol="000000.SH",
                name="非池内ETF",
                total_shares=1,
            ),
        ]
    )
    store.save_huijin_baselines(
        [
            *build_baselines(_holder_positions()),
            *build_baselines(_holder_positions("2026-12-31")),
        ]
    )

    result = service.history(days=120)

    assert result.model_version == "huijin-public-rule-v1"
    assert {point.symbol for point in result.points} == {"510300.SH"}
    assert [point.trade_date for point in result.points] == ["2026-07-15", "2026-07-17"]
    latest = result.points[-1]
    assert latest.share_change == 20
    assert latest.daily_change_pct == pytest.approx(2)
    assert latest.baseline_change_pct == pytest.approx(2)
    assert latest.cumulative_baseline_change_pct == pytest.approx(2)
    assert latest.multiple == pytest.approx(20)
    assert latest.estimated_subscription_cny is None
    assert latest.robust_score is None


def test_methodology_calls_no_remote_provider(tmp_path: Path) -> None:
    provider = FakeCapitalProvider()
    service = CapitalSignalService(
        provider=provider,
        store=CapitalSignalStore(tmp_path),
        clock=_clock,
    )

    result = service.methodology()

    assert result.model_version == "huijin-public-rule-v1"
    assert result.pool_version == POOL_VERSION
    assert result.core_pool == list(ALL_ETFS)
    assert result.thresholds["tenfold_baseline_pct"] == pytest.approx(0.1)
    factor_text = " ".join(
        f"{factor.key} {factor.name} {factor.description}" for factor in result.factors
    )
    for formula in (
        "share_delta",
        "daily_change_pct",
        "baseline_change_pct",
        "cumulative_baseline_change_pct",
    ):
        assert formula in factor_text
    for pair in ("510300.SH+159919.SZ", "510500.SH+159922.SZ", "512100.SH+159845.SZ"):
        assert pair in factor_text
    limitations = " ".join(result.limitations)
    assert "不能识别具体投资者" in limitations
    assert "7 月 6 日新规" in limitations
    assert "不实现" in limitations
    assert "启发式分数" not in factor_text
    assert "估算净申购金额" not in factor_text
    assert provider.margin_calls == []
    assert provider.share_calls == []


def test_holders_fetches_exact_positions_once_then_reuses_store(tmp_path: Path) -> None:
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
    assert first.model_version == "huijin-public-rule-v1"
    assert {row.symbol for row in first.baselines} == set(ALL_ETFS)
    assert all(row.pool_version == POOL_VERSION for row in first.baselines)
    assert holder_provider.calls == [
        {symbol: definition.name for symbol, definition in ALL_ETFS.items()}
    ]
