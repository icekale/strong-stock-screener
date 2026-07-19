from __future__ import annotations

import hashlib
import json
import statistics
from collections.abc import Iterable
from datetime import datetime, timedelta
from math import isclose
from threading import RLock
from typing import Protocol
from zoneinfo import ZoneInfo

from app.models import (
    CapitalSummaryResponse,
    EtfHolderPosition,
    EtfRadarFactorDefinition,
    EtfRadarHistoryPoint,
    EtfRadarHistoryResponse,
    EtfRadarHoldersResponse,
    EtfRadarItem,
    EtfRadarMethodologyResponse,
    EtfRadarOverviewResponse,
    EtfRadarSummary,
    EtfShareChange,
    EtfSharePoint,
    EtfSynchronization,
    HuijinEtfActivityItem,
    HuijinEtfActivitySummary,
    HuijinEtfBaseline,
    HuijinEtfValidationGroup,
    MarginMarketPoint,
    MarginSummary,
    StrongStockSourceStatus,
)
from app.providers.capital_signals import CapitalProviderResult
from app.services.capital_signal_store import CapitalSignalStore
from app.services.huijin_etf_activity import (
    ALL_ETFS,
    CORE_ETFS,
    MODEL_VERSION,
    POOL_VERSION,
    TENFOLD_BASELINE_PCT,
    VALIDATION_ETFS,
    build_baselines,
    calculate_activity,
    validate_pair,
)


class CapitalDataProvider(Protocol):
    def get_margin_rows(self, trade_date: str) -> CapitalProviderResult[MarginMarketPoint]: ...

    def get_etf_share_rows(
        self, trade_date: str, symbols: list[str] | tuple[str, ...]
    ) -> CapitalProviderResult[EtfSharePoint]: ...


class QuoteProvider(Protocol):
    def get_quotes(self, symbols: list[str]) -> list[object]: ...


class HolderProvider(Protocol):
    def get_holder_positions(
        self, symbols: dict[str, str]
    ) -> CapitalProviderResult: ...


class CapitalSignalService:
    def __init__(
        self,
        *,
        provider: CapitalDataProvider,
        store: CapitalSignalStore,
        quote_provider: QuoteProvider | None = None,
        holder_provider: HolderProvider | None = None,
        clock=None,
        ttl_seconds: int = 60,
    ) -> None:
        self.provider = provider
        self.store = store
        self.quote_provider = quote_provider
        self.holder_provider = holder_provider
        self.clock = clock or (lambda: datetime.now(ZoneInfo("Asia/Shanghai")))
        self.ttl_seconds = ttl_seconds
        self._lock = RLock()
        self._homepage_cache: tuple[datetime, CapitalSummaryResponse] | None = None
        self._baseline_refresh_attempts: dict[tuple[str, str, bool], datetime] = {}

    def overview(self, *, force: bool = False) -> EtfRadarOverviewResponse:
        with self._lock:
            now = self.clock()
            cached = self.store.load_snapshot()
            trade_date = _latest_weekday(now)
            _, baselines, baseline_status = self._load_or_refresh_baselines(now)
            active_baselines = _latest_applicable_baselines(baselines, trade_date)
            active_baseline_version = _baseline_version(active_baselines)
            active_baseline_fingerprint = _baseline_fingerprint(active_baselines)
            reusable_snapshot = (
                cached is not None
                and _is_compatible_snapshot(cached)
                and cached.baseline_version == active_baseline_version
                and cached.baseline_fingerprint == active_baseline_fingerprint
            )
            if (
                not force
                and reusable_snapshot
                and _is_fresh(cached.generated_at, now, self.ttl_seconds)
            ):
                if any(status.status == "stale" for status in baseline_status):
                    return cached.model_copy(
                        update={"source_status": [*cached.source_status, *baseline_status]}
                    )
                return cached

            symbols = list(ALL_ETFS)
            current_result = self.provider.get_etf_share_rows(trade_date, symbols)
            fetched_current_rows = [
                row
                for row in current_result.rows
                if row.trade_date == trade_date and row.symbol in ALL_ETFS
            ]
            history = self.store.load_share_history()
            stored_current_rows = [
                row
                for row in history
                if row.trade_date == trade_date and row.symbol in ALL_ETFS
            ]
            current_rows = _merge_share_history(stored_current_rows, fetched_current_rows)
            if not current_rows:
                if reusable_snapshot:
                    return cached.model_copy(
                        update={
                            "source_status": [
                                *cached.source_status,
                                *baseline_status,
                                *current_result.source_status,
                                StrongStockSourceStatus(
                                    source="ETF资金雷达缓存",
                                    status="stale",
                                    detail="远端刷新失败，返回最近持久化缓存",
                                ),
                            ]
                        }
                    )
                incompatible_cache_status = (
                    [
                        StrongStockSourceStatus(
                            source="ETF资金雷达缓存",
                            status="stale",
                            detail="不兼容或基准已变化的缓存已忽略，返回空的新模型响应",
                        )
                    ]
                    if cached is not None
                    else []
                )
                return self._empty_overview(
                    now,
                    trade_date,
                    [
                        *baseline_status,
                        *current_result.source_status,
                        *incompatible_cache_status,
                    ],
                    baselines,
                )

            previous_date = _previous_weekday(trade_date)
            fetched_keys = {(row.trade_date, row.symbol) for row in fetched_current_rows}
            retained_count = sum(
                (row.trade_date, row.symbol) not in fetched_keys for row in stored_current_rows
            )
            current_status = list(current_result.source_status)
            if retained_count > 0:
                current_status.append(
                    StrongStockSourceStatus(
                        source="ETF份额缓存",
                        status="stale",
                        detail=f"本次部分刷新，保留 {retained_count} 只同日缓存记录",
                    )
                )
            previous_by_symbol = _latest_share_before(history, trade_date)
            missing_sse = [
                symbol
                for symbol in (row.symbol for row in current_rows)
                if symbol.endswith(".SH") and symbol not in previous_by_symbol
            ]
            previous_status: list[StrongStockSourceStatus] = []
            if missing_sse:
                previous_result = self.provider.get_etf_share_rows(previous_date, missing_sse)
                fetched_previous_rows = [
                    row
                    for row in previous_result.rows
                    if row.symbol in missing_sse and row.trade_date < trade_date
                ]
                history = _merge_share_history(history, fetched_previous_rows)
                previous_by_symbol = _latest_share_before(history, trade_date)
                previous_status = previous_result.source_status

            current_by_symbol = {row.symbol: row for row in current_rows}
            baseline_by_symbol = _latest_applicable_baselines(baselines, trade_date)
            activity_by_symbol = _calculate_activity_rows(
                trade_date=trade_date,
                current_by_symbol=current_by_symbol,
                previous_by_symbol=previous_by_symbol,
                baseline_by_symbol=baseline_by_symbol,
            )
            core_items = [activity_by_symbol[symbol] for symbol in CORE_ETFS]
            validation_items = [activity_by_symbol[symbol] for symbol in VALIDATION_ETFS]
            validation_groups = _validation_groups(activity_by_symbol)
            activity = _activity_summary(core_items, validation_groups)
            items = [_legacy_radar_item(item) for item in core_items]

            history = _merge_share_history(history, current_rows)
            self.store.save_share_history(history)
            generated_at = now.isoformat(timespec="seconds")
            snapshot = EtfRadarOverviewResponse(
                generated_at=generated_at,
                trade_date=trade_date,
                as_of=generated_at,
                signal_stage=_signal_stage(now, trade_date),
                model_version=MODEL_VERSION,
                source_status=[*baseline_status, *current_status, *previous_status],
                valid_etf_count=activity.available_core_count,
                expected_etf_count=len(CORE_ETFS),
                items=items,
                pool_version=POOL_VERSION,
                baseline_version=_baseline_version(baseline_by_symbol),
                baseline_fingerprint=_baseline_fingerprint(baseline_by_symbol),
                activity=activity,
                core_items=core_items,
                validation_items=validation_items,
                validation_groups=validation_groups,
            )
            self.store.save_snapshot(snapshot)
            return snapshot

    def homepage_summary(self, *, force: bool = False) -> CapitalSummaryResponse:
        with self._lock:
            now = self.clock()
            if not force and self._homepage_cache is not None:
                cached_at, cached = self._homepage_cache
                if (now - cached_at).total_seconds() <= self.ttl_seconds:
                    return cached

            radar = self.overview(force=force)
            margin, margin_status = self._margin_summary(radar.trade_date)
            result = CapitalSummaryResponse(
                generated_at=radar.generated_at,
                trade_date=radar.trade_date,
                as_of=radar.as_of,
                signal_stage=radar.signal_stage,
                model_version=radar.model_version,
                source_status=[*radar.source_status, *margin_status],
                margin=margin,
                etf_radar=EtfRadarSummary(activity=radar.activity),
            )
            self._homepage_cache = (now, result)
            return result

    def history(self, *, days: int = 120) -> EtfRadarHistoryResponse:
        now = self.clock()
        trade_date = _latest_weekday(now)
        rows = [row for row in self.store.load_share_history() if row.symbol in ALL_ETFS]
        dates = sorted({row.trade_date for row in rows})[-days:]
        baselines = self.store.load_huijin_baselines()
        points: list[EtfRadarHistoryPoint] = []
        previous_by_symbol: dict[str, EtfSharePoint] = {}
        for row in sorted(rows, key=lambda item: (item.trade_date, item.symbol)):
            previous = previous_by_symbol.get(row.symbol)
            baseline = _latest_applicable_baselines(baselines, row.trade_date).get(row.symbol)
            definition = ALL_ETFS[row.symbol]
            activity = calculate_activity(
                symbol=row.symbol,
                name=definition.name,
                index_name=definition.index_name,
                role=definition.role,
                trade_date=row.trade_date,
                total_shares=row.total_shares,
                previous_total_shares=previous.total_shares if previous is not None else None,
                baseline=baseline,
            )
            if row.trade_date in dates:
                points.append(
                    EtfRadarHistoryPoint(
                        trade_date=row.trade_date,
                        symbol=row.symbol,
                        name=definition.name,
                        total_shares=row.total_shares,
                        share_change=activity.share_delta,
                        daily_change_pct=activity.daily_change_pct,
                        baseline_change_pct=activity.baseline_change_pct,
                        cumulative_baseline_change_pct=activity.cumulative_baseline_change_pct,
                        multiple=activity.multiple,
                    )
                )
            previous_by_symbol[row.symbol] = row
        generated_at = now.isoformat(timespec="seconds")
        latest_date = dates[-1] if dates else None
        archive_detail = (
            f"最新归档 {latest_date}；返回最近 {len(dates)} 个可用交易日"
            if latest_date is not None
            else "无归档数据；返回最近 0 个可用交易日"
        )
        return EtfRadarHistoryResponse(
            generated_at=generated_at,
            trade_date=trade_date,
            as_of=generated_at,
            signal_stage="post_close",
            model_version=MODEL_VERSION,
            source_status=[
                StrongStockSourceStatus(
                    source="ETF份额历史缓存",
                    status="success" if latest_date == trade_date else "stale",
                    detail=archive_detail,
                )
            ],
            points=points,
        )

    def holders(self) -> EtfRadarHoldersResponse:
        with self._lock:
            now = self.clock()
            generated_at = now.isoformat(timespec="seconds")
            positions, baselines, source_status = self._load_or_refresh_baselines(
                now, positions_required=True
            )
            return EtfRadarHoldersResponse(
                generated_at=generated_at,
                trade_date=_latest_weekday(now),
                as_of=generated_at,
                signal_stage="disclosure",
                model_version=MODEL_VERSION,
                source_status=source_status,
                positions=positions,
                baselines=_usable_baselines(baselines),
            )

    def methodology(self) -> EtfRadarMethodologyResponse:
        now = self.clock()
        generated_at = now.isoformat(timespec="seconds")
        return EtfRadarMethodologyResponse(
            generated_at=generated_at,
            trade_date=_latest_weekday(now),
            as_of=generated_at,
            signal_stage="post_close",
            model_version=MODEL_VERSION,
            source_status=[
                StrongStockSourceStatus(
                    source="资金雷达方法定义",
                    status="success",
                    detail="汇金 ETF 公开规则方法定义",
                )
            ],
            pool_version=POOL_VERSION,
            core_pool=list(ALL_ETFS),
            thresholds={"tenfold_baseline_pct": TENFOLD_BASELINE_PCT},
            factors=[
                EtfRadarFactorDefinition(
                    key="share_delta",
                    name="份额日变化",
                    description="share_delta = total_shares_today - total_shares_previous_day",
                    availability="真实相邻归档日可用",
                ),
                EtfRadarFactorDefinition(
                    key="daily_change_pct",
                    name="上日份额变化率",
                    description="daily_change_pct = share_delta / total_shares_previous_day * 100",
                    availability="真实相邻归档日可用",
                ),
                EtfRadarFactorDefinition(
                    key="baseline_change_pct",
                    name="报告基准变化率",
                    description="baseline_change_pct = share_delta / baseline_total_shares * 100",
                    availability="持仓报告基准可用时计算",
                ),
                EtfRadarFactorDefinition(
                    key="cumulative_baseline_change_pct",
                    name="报告期累计变化率",
                    description="cumulative_baseline_change_pct = (total_shares - baseline_total_shares) / baseline_total_shares * 100",
                    availability="持仓报告基准可用时计算",
                ),
                *_methodology_pair_factors(),
            ],
            limitations=[
                "深交所历史份额从本服务上线后逐日归档，不向前填充。",
                "ETF 总份额活动不能识别具体投资者或买方身份。",
                "付费内容中的“7 月 6 日新规”不实现，也不作推测。",
            ],
        )

    def _load_or_refresh_baselines(
        self, now: datetime, *, positions_required: bool = False
    ) -> tuple[
        list[EtfHolderPosition],
        list[HuijinEtfBaseline],
        list[StrongStockSourceStatus],
    ]:
        expected_period = _expected_holder_period(now)
        cached_positions = [
            row for row in self.store.load_holder_reports() if row.symbol in ALL_ETFS
        ]
        cached_baselines = self.store.load_huijin_baselines()
        baselines_complete = _has_complete_baseline_period(
            cached_baselines, expected_period
        )
        positions_complete = _has_position_coverage(
            cached_positions, cached_baselines, expected_period
        )
        if baselines_complete and (not positions_required or positions_complete):
            return (
                cached_positions,
                cached_baselines,
                [
                    StrongStockSourceStatus(
                        source="汇金 ETF 基准缓存",
                        status="success",
                        detail=(
                            f"完整报告期 {expected_period}，池版本 {POOL_VERSION}"
                            + ("，持有人记录完整" if positions_required else "")
                        ),
                    )
                ],
            )

        state_fingerprint = _holder_state_fingerprint(
            cached_positions, cached_baselines
        )
        attempt_key = (expected_period, state_fingerprint, positions_required)
        self._baseline_refresh_attempts = {
            key: attempted_at
            for key, attempted_at in self._baseline_refresh_attempts.items()
            if (now - attempted_at).total_seconds() <= self.ttl_seconds
        }
        if attempt_key in self._baseline_refresh_attempts:
            return (
                cached_positions,
                cached_baselines,
                [
                    StrongStockSourceStatus(
                        source="汇金 ETF 基准缓存",
                        status="stale",
                        detail=_refresh_incomplete_detail(
                            cached_positions,
                            cached_baselines,
                            expected_period,
                            positions_required=positions_required,
                            throttled=True,
                        ),
                    )
                ],
            )

        result = None
        if self.holder_provider is not None:
            self._baseline_refresh_attempts[attempt_key] = now
            try:
                result = self.holder_provider.get_holder_positions(
                    {symbol: definition.name for symbol, definition in ALL_ETFS.items()}
                )
            except Exception as exc:
                result = CapitalProviderResult(
                    rows=[],
                    source_status=[
                        StrongStockSourceStatus(
                            source="基金持有人披露",
                            status="failed",
                            detail=str(exc),
                        )
                    ],
                )

        if result is not None and result.rows:
            fetched_positions = [row for row in result.rows if row.symbol in ALL_ETFS]
            positions = _merge_holder_positions(cached_positions, fetched_positions)
            result_status = _position_aware_statuses(
                list(result.source_status),
                positions,
                positions_required=positions_required,
            )
            fetched_baselines = build_baselines(fetched_positions)
            baselines = _merge_baselines(cached_baselines, fetched_baselines)
            self.store.save_holder_reports(positions)
            self.store.save_huijin_baselines(baselines)
            baselines_complete = _has_complete_baseline_period(
                baselines, expected_period
            )
            positions_complete = _has_position_coverage(
                positions, baselines, expected_period
            )
            if baselines_complete and (not positions_required or positions_complete):
                return positions, baselines, result_status
            return (
                positions,
                baselines,
                [
                    *result_status,
                    StrongStockSourceStatus(
                        source="汇金 ETF 基准缓存",
                        status="stale",
                        detail=_refresh_incomplete_detail(
                            positions,
                            baselines,
                            expected_period,
                            positions_required=positions_required,
                        ),
                    ),
                ],
            )

        source_status = list(result.source_status) if result is not None else []
        source_status = _position_aware_statuses(
            source_status,
            cached_positions,
            positions_required=positions_required,
        )
        source_status.append(
            StrongStockSourceStatus(
                source="汇金 ETF 基准缓存",
                status="stale",
                detail=_refresh_incomplete_detail(
                    cached_positions,
                    cached_baselines,
                    expected_period,
                    positions_required=positions_required,
                ),
            )
        )
        return cached_positions, cached_baselines, source_status

    def _margin_summary(
        self, trade_date: str
    ) -> tuple[MarginSummary, list[StrongStockSourceStatus]]:
        history = self.store.load_margin_history()
        current_rows = [row for row in history if row.trade_date == trade_date]
        statuses: list[StrongStockSourceStatus] = []
        if not current_rows:
            current_result = self.provider.get_margin_rows(trade_date)
            current_rows = current_result.rows
            history = _merge_margin_history(history, current_rows)
            statuses.extend(current_result.source_status)

        previous_date = _previous_weekday(trade_date)
        previous_rows = [row for row in history if row.trade_date == previous_date]
        if not previous_rows:
            previous_result = self.provider.get_margin_rows(previous_date)
            previous_rows = previous_result.rows
            history = _merge_margin_history(history, previous_rows)
            statuses.extend(previous_result.source_status)
        self.store.save_margin_history(history)

        current_balance = _sum_optional(row.margin_balance_cny for row in current_rows)
        comparable_markets = {row.market for row in current_rows} & {
            row.market for row in previous_rows
        }
        comparable_current_balance = _sum_optional(
            row.margin_balance_cny for row in current_rows if row.market in comparable_markets
        )
        comparable_previous_balance = _sum_optional(
            row.margin_balance_cny for row in previous_rows if row.market in comparable_markets
        )
        change = (
            comparable_current_balance - comparable_previous_balance
            if comparable_current_balance is not None and comparable_previous_balance is not None
            else None
        )
        change_pct = (
            change / comparable_previous_balance * 100
            if change is not None and comparable_previous_balance not in {None, 0}
            else None
        )
        return (
            MarginSummary(
                balance_cny=current_balance,
                financing_balance_cny=_sum_optional(
                    row.financing_balance_cny for row in current_rows
                ),
                securities_lending_balance_cny=_sum_optional(
                    row.securities_lending_balance_cny for row in current_rows
                ),
                financing_buy_cny=_sum_optional(row.financing_buy_cny for row in current_rows),
                change_cny=change,
                change_pct=change_pct,
                available_markets=len({row.market for row in current_rows}),
            ),
            statuses,
        )

    def _quote_closes(self, symbols: list[str]) -> dict[str, float]:
        if self.quote_provider is None:
            return {}
        try:
            quotes = self.quote_provider.get_quotes(symbols)
        except Exception:
            return {}
        output: dict[str, float] = {}
        for quote in quotes:
            symbol = getattr(quote, "symbol", None)
            price = getattr(quote, "last_price", None)
            if isinstance(symbol, str) and isinstance(price, (int, float)) and price > 0:
                output[symbol] = float(price)
        return output

    @staticmethod
    def _empty_overview(
        now: datetime,
        trade_date: str,
        source_status: list[StrongStockSourceStatus],
        baselines: list[HuijinEtfBaseline],
    ) -> EtfRadarOverviewResponse:
        generated_at = now.isoformat(timespec="seconds")
        baseline_by_symbol = _latest_applicable_baselines(baselines, trade_date)
        activity_by_symbol = _calculate_activity_rows(
            trade_date=trade_date,
            current_by_symbol={},
            previous_by_symbol={},
            baseline_by_symbol=baseline_by_symbol,
        )
        core_items = [activity_by_symbol[symbol] for symbol in CORE_ETFS]
        validation_items = [activity_by_symbol[symbol] for symbol in VALIDATION_ETFS]
        validation_groups = _validation_groups(activity_by_symbol)
        return EtfRadarOverviewResponse(
            generated_at=generated_at,
            trade_date=trade_date,
            as_of=generated_at,
            signal_stage=_signal_stage(now, trade_date),
            model_version=MODEL_VERSION,
            source_status=source_status,
            items=[_legacy_radar_item(item) for item in core_items],
            pool_version=POOL_VERSION,
            baseline_version=_baseline_version(baseline_by_symbol),
            baseline_fingerprint=_baseline_fingerprint(baseline_by_symbol),
            activity=_activity_summary(core_items, validation_groups),
            core_items=core_items,
            validation_items=validation_items,
            validation_groups=validation_groups,
        )


def build_share_change(
    *,
    current_shares: float,
    previous_shares: float | None,
    close: float | None,
) -> EtfShareChange:
    if previous_shares is None:
        return EtfShareChange()
    share_change = current_shares - previous_shares
    return EtfShareChange(
        share_change=share_change,
        estimated_subscription_cny=(share_change * close if close is not None else None),
    )


def robust_z_score(value: float | None, history: list[float]) -> float | None:
    if value is None or len(history) < 3:
        return None
    median = statistics.median(history)
    mad = statistics.median(abs(item - median) for item in history)
    if mad == 0:
        return None
    return (value - median) / (1.4826 * mad)


def synchronization_ratio(values: Iterable[bool | None]) -> EtfSynchronization:
    valid_values = [value for value in values if value is not None]
    positive_count = sum(value is True for value in valid_values)
    return EtfSynchronization(
        positive_count=positive_count,
        valid_count=len(valid_values),
        ratio=(positive_count / len(valid_values) if valid_values else None),
    )


def _latest_weekday(now: datetime) -> str:
    value = now.date()
    while value.weekday() >= 5:
        value -= timedelta(days=1)
    return value.isoformat()


def _expected_holder_period(now: datetime) -> str:
    year = now.year
    if now.month >= 9:
        return f"{year}-06-30"
    if now.month >= 4:
        return f"{year - 1}-12-31"
    return f"{year - 1}-06-30"


def _previous_weekday(trade_date: str) -> str:
    value = datetime.strptime(trade_date, "%Y-%m-%d").date() - timedelta(days=1)
    while value.weekday() >= 5:
        value -= timedelta(days=1)
    return value.isoformat()


def _signal_stage(now: datetime, trade_date: str) -> str:
    if trade_date == now.date().isoformat() and now.hour < 16:
        return "intraday"
    return "post_close"


def _is_fresh(generated_at: str, now: datetime, ttl_seconds: int) -> bool:
    try:
        parsed = datetime.fromisoformat(generated_at)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=now.tzinfo)
        return 0 <= (now - parsed).total_seconds() <= ttl_seconds
    except ValueError:
        return False


def _is_compatible_snapshot(snapshot: EtfRadarOverviewResponse) -> bool:
    if snapshot.model_version != MODEL_VERSION or snapshot.pool_version != POOL_VERSION:
        return False
    if len(snapshot.core_items) != len(CORE_ETFS):
        return False
    if len(snapshot.validation_items) != len(VALIDATION_ETFS):
        return False
    if len(snapshot.validation_groups) != 3:
        return False
    if {item.symbol for item in snapshot.core_items} != set(CORE_ETFS):
        return False
    if {item.symbol for item in snapshot.validation_items} != set(VALIDATION_ETFS):
        return False
    expected_groups = {
        (definition.index_name, symbol, definition.paired_symbol)
        for symbol, definition in CORE_ETFS.items()
        if definition.paired_symbol is not None
    }
    actual_groups = {
        (group.index_name, group.core_symbol, group.validator_symbol)
        for group in snapshot.validation_groups
    }
    return actual_groups == expected_groups


def _latest_share_before(
    history: list[EtfSharePoint], trade_date: str
) -> dict[str, EtfSharePoint]:
    output: dict[str, EtfSharePoint] = {}
    for row in sorted(history, key=lambda item: item.trade_date):
        if row.trade_date < trade_date:
            output[row.symbol] = row
    return output


def _merge_share_history(
    history: list[EtfSharePoint], rows: list[EtfSharePoint]
) -> list[EtfSharePoint]:
    merged = {(row.trade_date, row.symbol): row for row in history}
    merged.update({(row.trade_date, row.symbol): row for row in rows})
    return sorted(merged.values(), key=lambda row: (row.trade_date, row.symbol))


def _merge_margin_history(
    history: list[MarginMarketPoint], rows: list[MarginMarketPoint]
) -> list[MarginMarketPoint]:
    merged = {(row.trade_date, row.market): row for row in history}
    merged.update({(row.trade_date, row.market): row for row in rows})
    return sorted(merged.values(), key=lambda row: (row.trade_date, row.market))


def _calculate_activity_rows(
    *,
    trade_date: str,
    current_by_symbol: dict[str, EtfSharePoint],
    previous_by_symbol: dict[str, EtfSharePoint],
    baseline_by_symbol: dict[str, HuijinEtfBaseline],
) -> dict[str, HuijinEtfActivityItem]:
    output: dict[str, HuijinEtfActivityItem] = {}
    for symbol, definition in ALL_ETFS.items():
        current = current_by_symbol.get(symbol)
        previous = previous_by_symbol.get(symbol)
        output[symbol] = calculate_activity(
            symbol=symbol,
            name=definition.name,
            index_name=definition.index_name,
            role=definition.role,
            trade_date=trade_date,
            total_shares=current.total_shares if current is not None else None,
            previous_total_shares=previous.total_shares if previous is not None else None,
            baseline=baseline_by_symbol.get(symbol),
        )
    return output


def _validation_groups(
    activity_by_symbol: dict[str, HuijinEtfActivityItem],
) -> list[HuijinEtfValidationGroup]:
    return [
        validate_pair(activity_by_symbol[symbol], activity_by_symbol[definition.paired_symbol])
        for symbol, definition in CORE_ETFS.items()
        if definition.paired_symbol is not None
    ]


def _activity_summary(
    core_items: list[HuijinEtfActivityItem],
    groups: list[HuijinEtfValidationGroup],
) -> HuijinEtfActivitySummary:
    strongest = max(
        (item for item in core_items if item.baseline_change_pct is not None),
        key=lambda item: abs(item.baseline_change_pct or 0),
        default=None,
    )
    return HuijinEtfActivitySummary(
        core_count=len(CORE_ETFS),
        available_core_count=sum(item.total_shares is not None for item in core_items),
        tenfold_increase_count=sum(
            item.is_tenfold and item.direction == "increase" for item in core_items
        ),
        tenfold_decrease_count=sum(
            item.is_tenfold and item.direction == "decrease" for item in core_items
        ),
        confirmed_increase_group_count=sum(
            group.state == "confirmed_increase" for group in groups
        ),
        confirmed_decrease_group_count=sum(
            group.state == "confirmed_decrease" for group in groups
        ),
        divergent_group_count=sum(group.state == "divergent" for group in groups),
        incomplete_group_count=sum(group.state == "incomplete" for group in groups),
        strongest_symbol=strongest.symbol if strongest is not None else None,
        strongest_baseline_change_pct=(
            strongest.baseline_change_pct if strongest is not None else None
        ),
    )


def _legacy_radar_item(item: HuijinEtfActivityItem) -> EtfRadarItem:
    return EtfRadarItem(
        symbol=item.symbol,
        name=item.name,
        index_name=item.index_name,
        total_shares=item.total_shares,
        share_change=item.share_delta,
    )


def _usable_baselines(baselines: list[HuijinEtfBaseline]) -> list[HuijinEtfBaseline]:
    return [
        row
        for row in baselines
        if row.pool_version == POOL_VERSION and row.symbol in ALL_ETFS
    ]


def _latest_applicable_baselines(
    baselines: list[HuijinEtfBaseline], trade_date: str
) -> dict[str, HuijinEtfBaseline]:
    output: dict[str, HuijinEtfBaseline] = {}
    for row in sorted(_usable_baselines(baselines), key=lambda item: item.report_period):
        if row.report_period <= trade_date:
            output[row.symbol] = row
    return output


def _baseline_version(baselines: dict[str, HuijinEtfBaseline]) -> str | None:
    if set(baselines) != set(ALL_ETFS):
        return None
    report_periods = {row.report_period for row in baselines.values()}
    if len(report_periods) != 1:
        return None
    return f"{next(iter(report_periods))}:{POOL_VERSION}"


def _baseline_fingerprint(baselines: dict[str, HuijinEtfBaseline]) -> str:
    payload = [
        {
            "symbol": row.symbol,
            "baseline_id": row.baseline_id,
            "report_period": row.report_period,
            "pool_version": row.pool_version,
            "baseline_total_shares": row.baseline_total_shares,
            "confirmed_huijin_shares": row.confirmed_huijin_shares,
            "confirmed_huijin_holding_pct": row.confirmed_huijin_holding_pct,
            "source_kind": row.source_kind,
            "source": row.source,
        }
        for _, row in sorted(baselines.items())
    ]
    return _stable_fingerprint(payload)


def _stable_fingerprint(payload: object) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _has_complete_baseline_period(
    baselines: list[HuijinEtfBaseline], report_period: str
) -> bool:
    symbols = {
        row.symbol
        for row in baselines
        if row.pool_version == POOL_VERSION and row.report_period == report_period
    }
    return symbols == set(ALL_ETFS)


def _has_position_coverage(
    positions: list[EtfHolderPosition],
    baselines: list[HuijinEtfBaseline],
    report_period: str,
) -> bool:
    expected_rows = [
        row
        for row in baselines
        if row.pool_version == POOL_VERSION and row.report_period == report_period
    ]
    expected_by_symbol = {row.symbol: row for row in expected_rows}
    if (
        len(expected_rows) != len(ALL_ETFS)
        or set(expected_by_symbol) != set(ALL_ETFS)
    ):
        return False
    position_baselines = build_baselines(
        [
            row
            for row in positions
            if row.report_period == report_period and row.symbol in expected_by_symbol
        ]
    )
    position_by_symbol = {
        row.symbol: row
        for row in position_baselines
        if row.pool_version == POOL_VERSION and row.report_period == report_period
    }
    if set(position_by_symbol) != set(expected_by_symbol):
        return False
    return all(
        isclose(
            position_by_symbol[symbol].confirmed_huijin_shares,
            baseline.confirmed_huijin_shares,
            rel_tol=1e-12,
            abs_tol=1e-9,
        )
        and isclose(
            position_by_symbol[symbol].confirmed_huijin_holding_pct,
            baseline.confirmed_huijin_holding_pct,
            rel_tol=1e-12,
            abs_tol=1e-9,
        )
        for symbol, baseline in expected_by_symbol.items()
    )


def _holder_state_fingerprint(
    positions: list[EtfHolderPosition], baselines: list[HuijinEtfBaseline]
) -> str:
    return _stable_fingerprint(
        {
            "positions": [
                row.model_dump(mode="json")
                for row in sorted(
                    positions,
                    key=lambda item: (
                        item.report_period,
                        item.symbol,
                        item.entity_name,
                    ),
                )
            ],
            "baselines": [
                row.model_dump(mode="json")
                for row in sorted(
                    baselines,
                    key=lambda item: (
                        item.report_period,
                        item.pool_version,
                        item.symbol,
                    ),
                )
            ],
        }
    )


def _merge_baselines(
    cached: list[HuijinEtfBaseline], fetched: list[HuijinEtfBaseline]
) -> list[HuijinEtfBaseline]:
    merged = {
        (row.pool_version, row.report_period, row.symbol): row
        for row in cached
        if row.symbol in ALL_ETFS
    }
    merged.update(
        {
            (row.pool_version, row.report_period, row.symbol): row
            for row in fetched
            if row.symbol in ALL_ETFS
        }
    )
    return sorted(
        merged.values(),
        key=lambda row: (row.report_period, row.pool_version, row.symbol),
    )


def _merge_holder_positions(
    cached: list[EtfHolderPosition], fetched: list[EtfHolderPosition]
) -> list[EtfHolderPosition]:
    fetched_groups = {(row.report_period, row.symbol) for row in fetched}
    merged = {
        (row.report_period, row.symbol, row.entity_name): row
        for row in cached
        if row.symbol in ALL_ETFS
        and (row.report_period, row.symbol) not in fetched_groups
    }
    merged.update(
        {
            (row.report_period, row.symbol, row.entity_name): row
            for row in fetched
            if row.symbol in ALL_ETFS
        }
    )
    return sorted(
        merged.values(),
        key=lambda row: (row.report_period, row.symbol, row.entity_name),
    )


def _baseline_fallback_detail(
    baselines: list[HuijinEtfBaseline], expected_period: str
) -> str:
    usable_periods = sorted({row.report_period for row in _usable_baselines(baselines)})
    if usable_periods:
        return f"应有报告期 {expected_period} 不完整，保留可用报告期 {usable_periods[-1]}"
    return f"应有报告期 {expected_period} 不完整，且无当前池版本可用基准"


def _refresh_incomplete_detail(
    positions: list[EtfHolderPosition],
    baselines: list[HuijinEtfBaseline],
    expected_period: str,
    *,
    positions_required: bool,
    throttled: bool = False,
) -> str:
    if positions_required and _has_complete_baseline_period(baselines, expected_period):
        expected_symbols = {
            row.symbol
            for row in baselines
            if row.pool_version == POOL_VERSION and row.report_period == expected_period
        }
        available_symbols = {
            row.symbol
            for row in positions
            if row.report_period == expected_period and row.symbol in expected_symbols
        }
        detail = (
            f"报告期 {expected_period} 持有人记录不完整，"
            f"当前 {len(available_symbols)}/{len(expected_symbols)} 只"
        )
    else:
        detail = _baseline_fallback_detail(baselines, expected_period)
    return f"{detail}；刷新尝试已限流" if throttled else detail


def _position_aware_statuses(
    statuses: list[StrongStockSourceStatus],
    positions: list[EtfHolderPosition],
    *,
    positions_required: bool,
) -> list[StrongStockSourceStatus]:
    if not positions_required or positions:
        return statuses
    return [
        status.model_copy(
            update={
                "status": "stale",
                "detail": f"{status.detail}；未返回持有人记录",
            }
        )
        if status.status == "success"
        else status
        for status in statuses
    ]


def _methodology_pair_factors() -> list[EtfRadarFactorDefinition]:
    return [
        EtfRadarFactorDefinition(
            key=f"validation_{definition.index_name}",
            name=f"{definition.index_name}成对验证",
            description=f"{symbol}+{definition.paired_symbol} 同向确认，分歧不相加",
            availability="两只 ETF 均有真实今日及前日份额时可用",
        )
        for symbol, definition in CORE_ETFS.items()
        if definition.paired_symbol is not None
    ]


def _sum_optional(values: Iterable[float | None]) -> float | None:
    available = [value for value in values if value is not None]
    return sum(available) if available else None
