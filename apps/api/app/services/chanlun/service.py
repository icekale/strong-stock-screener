from __future__ import annotations

from collections import defaultdict
from concurrent.futures import Future
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from statistics import mean, median
from threading import Lock, RLock
from typing import Literal
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.models import (
    ChanlunAnalysisResponse,
    ChanlunAvailability,
    ChanlunBacktestBucket,
    ChanlunBacktestResponse,
    ChanlunBacktestWindowStat,
    ChanlunCoverage,
    ChanlunPeriod,
    ChanlunPeriodSummary,
    ChanlunReplayFrame,
    ChanlunReplayResponse,
    ChanlunWorkspaceResponse,
    KlineBar,
    StrongStockSourceStatus,
)
from app.providers.tickflow import TickFlowIntradayBar
from app.services.background_jobs import CancelCheck, ProgressCallback
from app.services.chanlun.bars import aggregate_closed_intraday_bars, normalize_intraday_bars
from app.services.chanlun.confluence import derive_confluence_signals
from app.services.chanlun.coverage import (
    audit_intraday_coverage,
    open_sessions_in_calendar_window,
    required_intraday_raw_minutes,
    round_intraday_fetch_count,
)
from app.services.chanlun.store import ChanlunMinuteBarStore, StoredMinuteBar
from app.services.chanlun.structures import VISUAL_RULE_VERSION
from app.services.chanlun.symbols import normalize_chanlun_symbol
from app.services.short_term_cache import TtlCache


SHANGHAI = ZoneInfo("Asia/Shanghai")
_MIN_COMPLETED_BARS = 20
_RULE_VERSION = VISUAL_RULE_VERSION
_RAW_ADJUSTMENT = "raw_unadjusted"
_INTRADAY_PERIOD_MINUTES = {"5m": 5, "30m": 30, "60m": 60}
_DEFAULT_BACKTEST_HORIZONS = [1, 3, 5, 10]
_BUY_SIGNAL_TYPES = {"one_buy", "two_buy", "three_buy"}
_WORKSPACE_PERIODS: tuple[ChanlunPeriod, ...] = ("1d", "60m", "30m", "5m")
_CALENDAR_SOURCE = "CZSC内置交易日历"
_CALENDAR_UNAVAILABLE_DETAIL = "CZSC内置交易日历覆盖不可用，研究新鲜度按过期处理"
_ANALYSIS_STATE_INIT_GUARD = Lock()

ClosedInputFreshness = Literal["fresh", "stale", "insufficient"]


@dataclass(frozen=True)
class ClosedWorkspaceInputs:
    symbol: str
    periods: dict[ChanlunPeriod, tuple[KlineBar, ...]]
    availability: dict[ChanlunPeriod, ChanlunAvailability]
    freshness: dict[ChanlunPeriod, ClosedInputFreshness]
    last_closed_by_period: dict[ChanlunPeriod, str]
    adjustment_mode: str
    source_status: dict[ChanlunPeriod, tuple[StrongStockSourceStatus, ...]]
    adjustment_by_period: dict[ChanlunPeriod, str] = field(default_factory=dict)
    unavailable_detail_by_period: dict[ChanlunPeriod, str] = field(default_factory=dict)
    coverage: dict[ChanlunPeriod, ChanlunCoverage] = field(default_factory=dict)
    generation: int = 0


@dataclass(frozen=True)
class _ClosedPeriodData:
    bars: tuple[KlineBar, ...]
    availability: ChanlunAvailability
    freshness: ClosedInputFreshness
    source_status: tuple[StrongStockSourceStatus, ...]
    adjustment_mode: str
    unavailable_detail: str | None = None
    coverage: ChanlunCoverage = field(default_factory=ChanlunCoverage)
    generation: int = 0


class _IncompleteIntradayPayloadError(Exception):
    pass


class _ChanlunBacktestSample:
    def __init__(self, *, entry_open: float, future_bars: list[KlineBar]) -> None:
        self.entry_open = entry_open
        self.future_bars = future_bars


def _backtest_bucket(
    signal_type: str,
    samples: list[_ChanlunBacktestSample],
    horizons: list[int],
) -> ChanlunBacktestBucket:
    return ChanlunBacktestBucket(
        signal_type=signal_type,  # type: ignore[arg-type]
        sample_count=len(samples),
        windows=[_backtest_window_stat(samples, horizon) for horizon in horizons],
    )


def _backtest_window_stat(
    samples: list[_ChanlunBacktestSample],
    horizon: int,
) -> ChanlunBacktestWindowStat:
    returns: list[float] = []
    drawdowns: list[float] = []
    for sample in samples:
        bars = sample.future_bars[:horizon]
        if len(bars) < horizon or sample.entry_open <= 0:
            continue
        returns.append((bars[-1].close / sample.entry_open - 1) * 100)
        drawdowns.append((min(bar.low for bar in bars) / sample.entry_open - 1) * 100)

    wins = [value for value in returns if value > 0]
    losses = [-value for value in returns if value < 0]
    return ChanlunBacktestWindowStat(
        horizon_bars=horizon,
        sample_count=len(returns),
        win_rate_pct=round(len(wins) / len(returns) * 100, 2) if returns else None,
        avg_return_pct=_rounded_mean(returns),
        median_return_pct=round(median(returns), 2) if returns else None,
        avg_max_drawdown_pct=_rounded_mean(drawdowns),
        profit_loss_ratio=round(mean(wins) / mean(losses), 2) if wins and losses else None,
    )


def _clean_backtest_horizons(horizons: list[int] | None) -> list[int]:
    values = horizons or _DEFAULT_BACKTEST_HORIZONS
    output: list[int] = []
    seen: set[int] = set()
    for value in values:
        normalized = max(1, min(int(value), 60))
        if normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output or _DEFAULT_BACKTEST_HORIZONS


def _rounded_mean(values: list[float]) -> float | None:
    return round(mean(values), 2) if values else None


class ChanlunAnalysisService:
    def __init__(
        self,
        *,
        store: ChanlunMinuteBarStore,
        intraday_provider: object,
        history_provider: object | None,
        adapter: object,
        daily_provider: object | None = None,
        cache: TtlCache[ChanlunAnalysisResponse] | None = None,
        cache_seconds: int | None = None,
        minute_retention_days: int | None = None,
        history_max_bars: int | None = None,
    ) -> None:
        settings = get_settings()
        self.store = store
        self.intraday_provider = intraday_provider
        self.history_provider = history_provider
        self.adapter = adapter
        self.daily_provider = daily_provider
        self.cache = cache or TtlCache(
            ttl_seconds=cache_seconds or settings.chanlun_cache_seconds,
            name="chanlun_analysis",
        )
        self.closed_input_cache: TtlCache[ClosedWorkspaceInputs] = TtlCache(
            ttl_seconds=cache_seconds or settings.chanlun_cache_seconds,
            name="chanlun_closed_workspace_inputs",
        )
        self._analysis_cache_guard = RLock()
        self._analysis_inflight: dict[str, Future[ChanlunAnalysisResponse]] = {}
        self._cache_generation = 0
        self.minute_retention_days = minute_retention_days or settings.chanlun_minute_retention_days
        self.history_max_bars = history_max_bars or settings.chanlun_backfill_max_bars

    def _get_analysis_cache_guard(self) -> RLock:
        guard = getattr(self, "_analysis_cache_guard", None)
        if guard is None:
            with _ANALYSIS_STATE_INIT_GUARD:
                guard = getattr(self, "_analysis_cache_guard", None)
                if guard is None:
                    guard = RLock()
                    self._analysis_cache_guard = guard
        return guard

    def _get_analysis_inflight(self) -> dict[str, Future[ChanlunAnalysisResponse]]:
        inflight = getattr(self, "_analysis_inflight", None)
        if inflight is None:
            with _ANALYSIS_STATE_INIT_GUARD:
                inflight = getattr(self, "_analysis_inflight", None)
                if inflight is None:
                    inflight = {}
                    self._analysis_inflight = inflight
        return inflight

    def _cache_generation_snapshot(self) -> int:
        with self._get_analysis_cache_guard():
            return getattr(self, "_cache_generation", 0)

    def analysis(
        self,
        symbol: str,
        *,
        period: ChanlunPeriod,
        lookback: int,
        include_observing: bool,
        now: datetime | None = None,
    ) -> ChanlunAnalysisResponse:
        normalized_symbol = normalize_chanlun_symbol(symbol) or symbol.strip().upper()
        current = _to_shanghai(now or datetime.now(tz=SHANGHAI))
        generation = self._cache_generation_snapshot()
        if period == "1d":
            return self._daily_analysis(
                normalized_symbol,
                lookback=lookback,
                include_observing=include_observing,
                now=current,
                generation=generation,
            )
        return self._intraday_analysis(
            normalized_symbol,
            period=period,
            lookback=lookback,
            include_observing=include_observing,
            now=current,
            generation=generation,
        )

    def workspace(
        self,
        symbol: str,
        *,
        lookback: int,
        now: datetime | None = None,
    ) -> ChanlunWorkspaceResponse:
        if not hasattr(self, "closed_input_cache"):
            analyses = {
                period: self.analysis(
                    symbol,
                    period=period,
                    lookback=lookback,
                    include_observing=period == "1d",
                )
                for period in _WORKSPACE_PERIODS
            }
        else:
            inputs = self.closed_workspace_inputs(symbol, lookback=lookback, now=now)
            analyses = {
                period: self._analyze_closed_workspace_period(
                    inputs,
                    period=period,
                    lookback=lookback,
                    include_observing=period == "1d",
                )
                for period in _WORKSPACE_PERIODS
            }
        return ChanlunWorkspaceResponse(
            symbol=normalize_chanlun_symbol(symbol) or symbol.strip().upper(),
            periods=[_summary(analyses[period]) for period in _WORKSPACE_PERIODS],
            analysis=analyses["1d"],
            confluence_signals=derive_confluence_signals(analyses),
        )

    def closed_workspace_inputs(
        self,
        symbol: str,
        *,
        lookback: int,
        now: datetime | None = None,
    ) -> ClosedWorkspaceInputs:
        normalized_symbol = normalize_chanlun_symbol(symbol) or symbol.strip().upper()
        current = _to_shanghai(now or datetime.now(tz=SHANGHAI))
        generation = self._cache_generation_snapshot()
        cache_key = (
            f"{normalized_symbol}:{lookback}:{_expected_close_fingerprint(current)}"
            f":generation={generation}"
        )
        return self.closed_input_cache.get_or_set(
            cache_key,
            lambda: self._build_closed_workspace_inputs(
                normalized_symbol,
                lookback=lookback,
                now=current,
                generation=generation,
            ),
        )

    def _build_closed_workspace_inputs(
        self,
        symbol: str,
        *,
        lookback: int,
        now: datetime,
        generation: int,
    ) -> ClosedWorkspaceInputs:
        daily_period = self._load_closed_daily_period(
            symbol,
            lookback=lookback,
            now=now,
            generation=generation,
        )
        period_data: dict[ChanlunPeriod, _ClosedPeriodData] = {
            "1d": daily_period,
            **self._load_closed_intraday_periods(
                symbol,
                periods=("60m", "30m", "5m"),
                lookback=lookback,
                now=now,
                daily_reference=daily_period,
                generation=generation,
            ),
        }
        adjustment_by_period = {
            period: period_data[period].adjustment_mode for period in _WORKSPACE_PERIODS
        }
        adjustment_modes = set(adjustment_by_period.values())
        adjustment_mode = (
            next(iter(adjustment_modes)) if len(adjustment_modes) == 1 else "adjustment_mismatch"
        )
        calendar_status = _calendar_source_status(now.date())
        calendar_statuses = (calendar_status,) if calendar_status is not None else ()
        return ClosedWorkspaceInputs(
            symbol=symbol,
            periods={period: period_data[period].bars for period in _WORKSPACE_PERIODS},
            availability={
                period: period_data[period].availability for period in _WORKSPACE_PERIODS
            },
            freshness={period: period_data[period].freshness for period in _WORKSPACE_PERIODS},
            last_closed_by_period={
                period: _closed_bar_boundary(period, period_data[period].bars[-1].date)
                for period in _WORKSPACE_PERIODS
                if period_data[period].bars
            },
            adjustment_mode=adjustment_mode,
            source_status={
                period: (*period_data[period].source_status, *calendar_statuses)
                for period in _WORKSPACE_PERIODS
            },
            adjustment_by_period=adjustment_by_period,
            unavailable_detail_by_period={
                period: period_data[period].unavailable_detail
                for period in _WORKSPACE_PERIODS
                if period_data[period].unavailable_detail is not None
            },
            coverage={period: period_data[period].coverage for period in _WORKSPACE_PERIODS},
            generation=generation,
        )

    def _load_closed_daily_period(
        self,
        symbol: str,
        *,
        lookback: int,
        now: datetime,
        generation: int | None = None,
    ) -> _ClosedPeriodData:
        generation = (
            self._cache_generation_snapshot() if generation is None else generation
        )
        provider = self.daily_provider
        source_name = getattr(provider, "source_name", "日K线")
        adjustment_mode = _daily_adjustment_mode(provider)
        if provider is None:
            return _ClosedPeriodData(
                bars=(),
                availability="unavailable",
                freshness="insufficient",
                source_status=(
                    StrongStockSourceStatus(
                        source=source_name,
                        status="failed",
                        detail="日K线数据源未配置",
                    ),
                ),
                adjustment_mode=adjustment_mode,
                coverage=_unverified_coverage(
                    required_period_bars=lookback,
                    reason="日K线数据源未配置，覆盖未验证",
                ),
                generation=generation,
            )
        try:
            daily_bars = provider.get_klines(
                symbol,
                count=max(lookback + 1, _MIN_COMPLETED_BARS + 1),
            )
        except Exception as exc:
            return _ClosedPeriodData(
                bars=(),
                availability="unavailable",
                freshness="insufficient",
                source_status=(
                    StrongStockSourceStatus(
                        source=source_name,
                        status="failed",
                        detail=f"日K线读取失败: {_exception_detail(exc)}",
                    ),
                ),
                adjustment_mode=adjustment_mode,
                coverage=_unverified_coverage(
                    required_period_bars=lookback,
                    reason="日K线读取失败，覆盖未验证",
                ),
                generation=generation,
            )

        bars = tuple(_completed_daily_bars(daily_bars, now)[-lookback:])
        availability: ChanlunAvailability = (
            "ready" if len(bars) >= _MIN_COMPLETED_BARS else "insufficient_bars"
        )
        freshness: ClosedInputFreshness = (
            _closed_input_freshness("1d", bars, now) if availability == "ready" else "insufficient"
        )
        return _ClosedPeriodData(
            bars=bars,
            availability=availability,
            freshness=freshness,
            source_status=(
                StrongStockSourceStatus(
                    source=source_name,
                    status="success",
                    detail=f"返回 {len(bars)} 条已完成日K",
                ),
            ),
            adjustment_mode=adjustment_mode,
            coverage=_daily_coverage(lookback, bars),
            generation=generation,
        )

    def _load_closed_intraday_periods(
        self,
        symbol: str,
        *,
        periods: tuple[Literal["5m", "30m", "60m"], ...],
        lookback: int,
        now: datetime,
        daily_reference: _ClosedPeriodData | None = None,
        generation: int | None = None,
    ) -> dict[ChanlunPeriod, _ClosedPeriodData]:
        source_name = getattr(self.intraday_provider, "source_name", "TickFlow 分钟线")
        generation = (
            self._cache_generation_snapshot() if generation is None else generation
        )
        daily_reference = daily_reference or self._load_closed_daily_period(
            symbol,
            lookback=lookback,
            now=now,
            generation=generation,
        )
        expected_trade_dates = _expected_trade_dates(daily_reference)
        live_failed = False
        live_source_failed = False
        live_status: StrongStockSourceStatus
        current_bars: list[TickFlowIntradayBar] = []
        try:
            fetch_count = max(_intraday_fetch_count(period, lookback) for period in periods)
            payload = self.intraday_provider.get_intraday_bars(
                [symbol],
                period="1m",
                count=fetch_count,
            )
            raw_bars = payload.get(symbol)
            if raw_bars is None:
                raise _IncompleteIntradayPayloadError(f"响应缺少 {symbol} 分钟线")
            if not raw_bars:
                raise _IncompleteIntradayPayloadError(f"响应中 {symbol} 分钟线为空")
            current_bars = normalize_intraday_bars(raw_bars)
            if not current_bars:
                raise _IncompleteIntradayPayloadError(f"响应中 {symbol} 没有有效分钟线")
            self._upsert_live_minutes(symbol, current_bars, source=source_name, now=now)
            live_status = StrongStockSourceStatus(
                source=source_name,
                status="success",
                detail=f"读取并写入 {len(current_bars)} 条当前1分钟线",
            )
        except _IncompleteIntradayPayloadError as exc:
            live_failed = True
            live_status = StrongStockSourceStatus(
                source=source_name,
                status="failed",
                detail=f"当前1分钟线读取失败: {_exception_detail(exc)}",
            )
        except Exception as exc:
            live_failed = True
            live_source_failed = True
            live_status = StrongStockSourceStatus(
                source=source_name,
                status="failed",
                detail=f"当前1分钟线读取失败: {_exception_detail(exc)}",
            )

        minute_bars = _stored_closed_minutes(self.store.read(symbol))
        continuity_status = _continuity_reference_status(daily_reference)
        result: dict[ChanlunPeriod, _ClosedPeriodData] = {}
        for period in periods:
            completed = tuple(
                aggregate_closed_intraday_bars(minute_bars, period=period, now=now)[-lookback:]
            )
            archive_status = StrongStockSourceStatus(
                source="Chanlun SQLite分钟线",
                status="stale" if live_failed else "success",
                detail=(
                    f"从 {len(minute_bars)} 条闭合原始分钟线生成 {len(completed)} 条{period}闭合K线"
                ),
            )
            period_expected_trade_dates = expected_trade_dates
            if expected_trade_dates is not None and _has_current_latest_bucket(
                current_bars,
                period=period,
                now=now,
            ):
                period_expected_trade_dates = {*expected_trade_dates, now.date()}
            coverage = audit_intraday_coverage(
                [_minute_timestamp(bar) for bar in minute_bars],
                period=period,
                lookback=lookback,
                now=now,
                expected_trade_dates=period_expected_trade_dates,
            )
            if coverage.status != "complete":
                availability: ChanlunAvailability = (
                    "unavailable"
                    if live_source_failed and not minute_bars
                    else "insufficient_bars"
                )
                freshness: ClosedInputFreshness = "insufficient"
                unavailable_detail = (
                    f"{period}覆盖{coverage.status}: {coverage.reason}，"
                    "未调用CZSC适配器"
                )
            elif len(completed) < _MIN_COMPLETED_BARS:
                availability = "insufficient_bars"
                freshness = "insufficient"
                unavailable_detail = None
            elif live_failed:
                availability = "stale"
                freshness = "stale"
                unavailable_detail = None
            else:
                availability = "ready"
                freshness = _closed_input_freshness(period, completed, now)
                unavailable_detail = None
            source_status = (live_status, archive_status)
            if continuity_status is not None:
                source_status += (continuity_status,)
            result[period] = _ClosedPeriodData(
                bars=completed,
                availability=availability,
                freshness=freshness,
                source_status=source_status,
                adjustment_mode=_RAW_ADJUSTMENT,
                unavailable_detail=unavailable_detail,
                coverage=coverage,
                generation=generation,
            )
        return result

    def _analyze_closed_workspace_period(
        self,
        inputs: ClosedWorkspaceInputs,
        *,
        period: ChanlunPeriod,
        lookback: int,
        include_observing: bool,
    ) -> ChanlunAnalysisResponse:
        return self._analyze_closed_period_data(
            inputs.symbol,
            period=period,
            period_data=_ClosedPeriodData(
                bars=inputs.periods[period],
                availability=inputs.availability[period],
                freshness=inputs.freshness[period],
                source_status=inputs.source_status[period],
                adjustment_mode=inputs.adjustment_by_period.get(
                    period,
                    inputs.adjustment_mode,
                ),
                unavailable_detail=inputs.unavailable_detail_by_period.get(period),
                coverage=inputs.coverage.get(
                    period,
                    _unverified_coverage(
                        required_period_bars=lookback,
                        available_period_bars=len(inputs.periods[period]),
                        reason="工作区缺少覆盖审计证据",
                    ),
                ),
                generation=inputs.generation,
            ),
            lookback=lookback,
            include_observing=include_observing,
        )

    def _analyze_closed_period_data(
        self,
        symbol: str,
        *,
        period: ChanlunPeriod,
        period_data: _ClosedPeriodData,
        lookback: int,
        include_observing: bool,
    ) -> ChanlunAnalysisResponse:
        bars = list(period_data.bars)
        source_status = list(period_data.source_status)
        if period_data.availability == "unavailable":
            return _unavailable_response(
                symbol,
                period,
                bars,
                source_status,
                adjustment_mode=period_data.adjustment_mode,
                coverage=period_data.coverage,
                detail=period_data.unavailable_detail,
            )
        if period_data.coverage.status != "complete":
            detail = period_data.unavailable_detail or (
                f"{period}覆盖{period_data.coverage.status}: "
                f"{period_data.coverage.reason}，未调用CZSC适配器"
            )
            return ChanlunAnalysisResponse(
                symbol=symbol,
                period=period,
                availability="insufficient_bars",
                bars=bars,
                source_status=[
                    *source_status,
                    StrongStockSourceStatus(
                        source="Chanlun结构",
                        status="failed",
                        detail=detail,
                    ),
                ],
                coverage=period_data.coverage,
                last_closed_bar_at=bars[-1].date if bars else None,
                adjustment_mode=period_data.adjustment_mode,
                rule_version=_RULE_VERSION,
            )
        result = self._analyze_completed(
            symbol,
            period=period,
            bars=bars,
            lookback=lookback,
            include_observing=include_observing,
            source_status=source_status,
            adjustment_mode=period_data.adjustment_mode,
            coverage=period_data.coverage,
            generation=period_data.generation,
        )
        if period_data.freshness == "stale" and result.availability == "ready":
            return result.model_copy(
                deep=True,
                update={"availability": "stale", "coverage": period_data.coverage},
            )
        return result

    def replay(
        self,
        symbol: str,
        *,
        period: ChanlunPeriod,
        lookback: int,
    ) -> ChanlunReplayResponse:
        base = self.analysis(
            symbol,
            period=period,
            lookback=lookback,
            include_observing=False,
        )
        if base.availability not in {"ready", "stale"}:
            return ChanlunReplayResponse(
                symbol=base.symbol,
                period=period,
                availability=base.availability,
                source_status=base.source_status,
                adjustment_mode=base.adjustment_mode,
                rule_version=base.rule_version,
            )

        seen_divergence_ids: set[str] = set()
        seen_signal_ids: set[str] = set()
        frames: list[ChanlunReplayFrame] = []
        for prefix_size in range(_MIN_COMPLETED_BARS, len(base.bars) + 1):
            prefix = base.bars[:prefix_size]
            snapshot = self.adapter.analyze(
                base.symbol,
                period=period,
                bars=prefix,
                include_observing=False,
            )
            if snapshot.availability != "ready":
                continue
            new_divergences = [
                item
                for item in snapshot.divergences
                if item.status in {"confirmed", "final"} and item.id not in seen_divergence_ids
            ]
            new_signals = [
                item
                for item in snapshot.signals
                if item.status in {"confirmed", "final"} and item.id not in seen_signal_ids
            ]
            seen_divergence_ids.update(item.id for item in new_divergences)
            seen_signal_ids.update(item.id for item in new_signals)
            if not new_divergences and not new_signals:
                continue

            structures = snapshot.segments or snapshot.strokes
            latest_zone = next(
                (
                    zone
                    for zone in reversed(snapshot.zones)
                    if not zone.virtual and zone.status in {"confirmed", "final"}
                ),
                None,
            )
            frames.append(
                ChanlunReplayFrame(
                    closed_at=prefix[-1].date,
                    direction=structures[-1].direction if structures else "unknown",
                    latest_zone=latest_zone,
                    new_divergences=new_divergences,
                    new_signals=new_signals,
                )
            )

        return ChanlunReplayResponse(
            symbol=base.symbol,
            period=period,
            availability=base.availability,
            frames=frames,
            source_status=base.source_status,
            adjustment_mode=base.adjustment_mode,
            rule_version=base.rule_version,
        )

    def backtest(
        self,
        symbol: str,
        *,
        period: ChanlunPeriod,
        lookback: int,
        horizons: list[int] | None = None,
    ) -> ChanlunBacktestResponse:
        clean_horizons = _clean_backtest_horizons(horizons)
        base = self.analysis(
            symbol,
            period=period,
            lookback=lookback,
            include_observing=False,
        )
        if base.availability not in {"ready", "stale"}:
            return ChanlunBacktestResponse(
                symbol=base.symbol,
                period=period,
                availability=base.availability,
                horizons=clean_horizons,
                source_status=base.source_status,
                adjustment_mode=base.adjustment_mode,
                rule_version=base.rule_version,
            )

        replay = self.replay(symbol, period=period, lookback=lookback)
        index_by_date = {bar.date: index for index, bar in enumerate(base.bars)}
        max_horizon = max(clean_horizons)
        samples_by_signal: dict[str, list[_ChanlunBacktestSample]] = defaultdict(list)
        skipped = 0
        for frame in replay.frames:
            signal_index = index_by_date.get(frame.closed_at)
            if signal_index is None:
                continue
            future_bars = base.bars[signal_index + 1 : signal_index + 1 + max_horizon]
            for signal in frame.new_signals:
                if signal.type not in _BUY_SIGNAL_TYPES:
                    continue
                if len(future_bars) < max_horizon or not future_bars or future_bars[0].open <= 0:
                    skipped += 1
                    continue
                samples_by_signal[signal.type].append(
                    _ChanlunBacktestSample(entry_open=future_bars[0].open, future_bars=future_bars)
                )

        buckets = [
            _backtest_bucket(signal_type, samples, clean_horizons)
            for signal_type, samples in sorted(samples_by_signal.items())
        ]
        sample_count = sum(bucket.sample_count for bucket in buckets)
        return ChanlunBacktestResponse(
            symbol=base.symbol,
            period=period,
            availability=base.availability,
            horizons=clean_horizons,
            sample_count=sample_count,
            buckets=buckets,
            source_status=[
                *base.source_status,
                StrongStockSourceStatus(
                    source="Chanlun回测",
                    status="success",
                    detail=f"确认买类事件 {sample_count} 条，因后续K线不足跳过 {skipped} 条",
                ),
            ],
            adjustment_mode=base.adjustment_mode,
            rule_version=base.rule_version,
        )

    def backfill(
        self,
        symbol: str,
        *,
        periods: tuple[Literal["5m", "30m", "60m"], ...] = ("5m", "30m", "60m"),
        lookback: int = 220,
        history_days: int | None = None,
        progress: ProgressCallback,
        should_cancel: CancelCheck,
    ) -> dict[str, object]:
        normalized_symbol = normalize_chanlun_symbol(symbol) or symbol.strip().upper()
        if not periods:
            raise ValueError("periods must not be empty")
        if len(periods) != len(set(periods)):
            raise ValueError("periods must not contain duplicates")
        invalid_periods = [
            period for period in periods if period not in _INTRADAY_PERIOD_MINUTES
        ]
        if invalid_periods:
            raise ValueError(f"unsupported intraday period: {invalid_periods[0]}")
        if lookback < 0:
            raise ValueError("lookback must be non-negative")
        if history_days is not None and history_days < 0:
            raise ValueError("history_days must be non-negative")

        current = _to_shanghai(datetime.now(tz=SHANGHAI))
        target = max(required_intraday_raw_minutes(period, lookback) for period in periods)
        if history_days is not None:
            target = max(
                target,
                open_sessions_in_calendar_window(history_days, now=current) * 240,
            )
        target = round_intraday_fetch_count(target)
        _raise_if_canceled(should_cancel)
        progress(0, 3, f"准备补齐 {target} 条分钟历史")
        if self.history_provider is None:
            raise RuntimeError("未配置分钟历史数据源")
        if target > self.history_max_bars:
            raise RuntimeError(
                f"需要 {target} 根分钟线，当前上限为 {self.history_max_bars}"
            )

        bars = self.history_provider.get_minute_bars(
            normalized_symbol,
            max_bars=target,
        )
        _raise_if_canceled(should_cancel)
        normalized_bars = normalize_intraday_bars(bars)
        progress(1, 3, f"已读取 {len(normalized_bars)} 条分钟历史")

        self.store.upsert(
            normalized_symbol,
            normalized_bars,
            source=getattr(self.history_provider, "source_name", "分钟历史"),
            closed=True,
        )
        progress(2, 3, f"已写入 {len(normalized_bars)} 条闭合分钟线")
        _raise_if_canceled(should_cancel)
        self.store.prune(keep_days=self.minute_retention_days)
        with self._get_analysis_cache_guard():
            self._cache_generation = getattr(self, "_cache_generation", 0) + 1
            self.cache.clear()
            self.closed_input_cache.clear()
        progress(3, 3, "分钟历史补齐完成")
        daily_reference = (
            self._load_closed_daily_period(
                normalized_symbol,
                lookback=lookback,
                now=current,
            )
            if getattr(self, "daily_provider", None) is not None
            else None
        )
        expected_trade_dates = _expected_trade_dates(daily_reference)
        closed_bars = [bar for bar in normalized_bars if _minute_is_closed(bar, current)]
        if expected_trade_dates is not None and any(
            _minute_trade_date(bar) == current.date() for bar in closed_bars
        ):
            expected_trade_dates = {*expected_trade_dates, current.date()}
        stored_reader = getattr(self.store, "read", None)
        if callable(stored_reader):
            closed_bars = [
                bar
                for bar in _stored_closed_minutes(stored_reader(normalized_symbol))
                if _minute_is_closed(bar, current)
            ]
        coverage = {
            period: audit_intraday_coverage(
                [_minute_timestamp(bar) for bar in closed_bars],
                period=period,
                lookback=lookback,
                now=current,
                expected_trade_dates=expected_trade_dates,
            ).model_dump(mode="json")
            for period in periods
        }
        return {
            "symbol": normalized_symbol,
            "requested_bars": target,
            "written_bars": len(normalized_bars),
            "coverage": coverage,
        }

    def _daily_analysis(
        self,
        symbol: str,
        *,
        lookback: int,
        include_observing: bool,
        now: datetime,
        generation: int,
    ) -> ChanlunAnalysisResponse:
        return self._analyze_closed_period_data(
            symbol,
            period="1d",
            period_data=self._load_closed_daily_period(
                symbol,
                lookback=lookback,
                now=now,
                generation=generation,
            ),
            lookback=lookback,
            include_observing=include_observing,
        )

    def _intraday_analysis(
        self,
        symbol: str,
        *,
        period: Literal["5m", "30m", "60m"],
        lookback: int,
        include_observing: bool,
        now: datetime,
        generation: int,
    ) -> ChanlunAnalysisResponse:
        return self._analyze_closed_period_data(
            symbol,
            period=period,
            period_data=self._load_closed_intraday_periods(
                symbol,
                periods=(period,),
                lookback=lookback,
                now=now,
                generation=generation,
            )[period],
            lookback=lookback,
            include_observing=include_observing,
        )

    def _upsert_live_minutes(
        self,
        symbol: str,
        bars: list[TickFlowIntradayBar],
        *,
        source: str,
        now: datetime,
    ) -> None:
        closed = [bar for bar in bars if _minute_is_closed(bar, now)]
        observing = [bar for bar in bars if bar not in closed]
        self.store.upsert(symbol, closed, source=source, closed=True, captured_at=now)
        self.store.upsert(symbol, observing, source=source, closed=False, captured_at=now)

    def _analyze_completed(
        self,
        symbol: str,
        *,
        period: ChanlunPeriod,
        bars: list[KlineBar],
        lookback: int,
        include_observing: bool,
        source_status: list[StrongStockSourceStatus],
        adjustment_mode: str,
        coverage: ChanlunCoverage,
        generation: int,
    ) -> ChanlunAnalysisResponse:
        last_closed_bar_at = bars[-1].date if bars else None
        if len(bars) < _MIN_COMPLETED_BARS:
            return ChanlunAnalysisResponse(
                symbol=symbol,
                period=period,
                availability="insufficient_bars",
                bars=bars,
                source_status=[
                    *source_status,
                    StrongStockSourceStatus(
                        source="Chanlun结构",
                        status="failed",
                        detail=(
                            f"{period}已完成K线不足: {len(bars)}/{_MIN_COMPLETED_BARS}，"
                            "未调用CZSC适配器"
                        ),
                    ),
                ],
                coverage=coverage,
                last_closed_bar_at=last_closed_bar_at,
                adjustment_mode=adjustment_mode,
                rule_version=_RULE_VERSION,
            )

        cache_key = _cache_key(
            symbol=symbol,
            period=period,
            lookback=lookback,
            last_closed_bar_at=last_closed_bar_at,
            adjustment_mode=adjustment_mode,
            include_observing=include_observing,
            generation=generation,
        )

        def build() -> ChanlunAnalysisResponse:
            try:
                result = self.adapter.analyze(
                    symbol,
                    period=period,
                    bars=bars,
                    include_observing=include_observing,
                )
            except Exception as exc:
                return _unavailable_response(
                    symbol,
                    period,
                    bars,
                    [],
                    adjustment_mode=adjustment_mode,
                    coverage=coverage,
                    detail=f"CZSC适配器分析失败: {_exception_detail(exc)}",
                )
            return result.model_copy(
                deep=True,
                update={
                    "symbol": symbol,
                    "period": period,
                    "bars": bars,
                    "last_closed_bar_at": last_closed_bar_at,
                    "adjustment_mode": adjustment_mode,
                    "rule_version": _RULE_VERSION,
                    "coverage": coverage,
                },
            )

        def decorate(result: ChanlunAnalysisResponse) -> ChanlunAnalysisResponse:
            return result.model_copy(
                deep=True,
                update={
                    "source_status": [*source_status, *result.source_status],
                    "coverage": coverage,
                },
            )

        guard = self._get_analysis_cache_guard()
        inflight = self._get_analysis_inflight()
        with guard:
            cached = self.cache.get_if_fresh(cache_key)
            if cached is not None:
                return decorate(cached)
            future = inflight.get(cache_key)
            if future is None:
                future = Future()
                inflight[cache_key] = future
                is_owner = True
            else:
                is_owner = False

        if not is_owner:
            return decorate(future.result())

        try:
            built = build()
            if built.availability == "ready":
                with guard:
                    if getattr(self, "_cache_generation", 0) == generation:
                        cached = self.cache.get_or_set(cache_key, lambda: built)
                    else:
                        cached = built
            else:
                cached = built
            future.set_result(cached)
            return decorate(cached)
        except BaseException as exc:
            if not future.done():
                future.set_exception(exc)
            raise
        finally:
            with guard:
                if inflight.get(cache_key) is future:
                    del inflight[cache_key]


def _summary(analysis: ChanlunAnalysisResponse) -> ChanlunPeriodSummary:
    structures = analysis.segments or analysis.strokes
    return ChanlunPeriodSummary(
        period=analysis.period,
        availability=analysis.availability,
        direction=structures[-1].direction if structures else "unknown",
        latest_zone=analysis.zones[-1] if analysis.zones else None,
        latest_divergence=analysis.divergences[-1] if analysis.divergences else None,
        latest_signal=analysis.signals[-1] if analysis.signals else None,
        last_closed_bar_at=analysis.last_closed_bar_at,
    )


def _unavailable_response(
    symbol: str,
    period: ChanlunPeriod,
    bars: list[KlineBar],
    source_status: list[StrongStockSourceStatus],
    *,
    adjustment_mode: str,
    coverage: ChanlunCoverage,
    detail: str | None = None,
) -> ChanlunAnalysisResponse:
    statuses = list(source_status)
    if detail:
        statuses.append(
            StrongStockSourceStatus(source="Chanlun结构", status="failed", detail=detail)
        )
    return ChanlunAnalysisResponse(
        symbol=symbol,
        period=period,
        availability="unavailable",
        bars=bars,
        source_status=statuses,
        coverage=coverage,
        last_closed_bar_at=bars[-1].date if bars else None,
        adjustment_mode=adjustment_mode,
        rule_version=_RULE_VERSION,
    )


def _daily_coverage(lookback: int, bars: tuple[KlineBar, ...]) -> ChanlunCoverage:
    available = len(bars)
    complete = available >= lookback
    return ChanlunCoverage(
        status="complete" if complete else "incomplete",
        required_period_bars=lookback,
        available_period_bars=available,
        earliest_at=bars[0].date if bars else None,
        latest_at=bars[-1].date if bars else None,
        reason="已完成日K覆盖完整" if complete else "已完成日K数量不足",
        backfill_required=not complete,
    )


def _unverified_coverage(
    *,
    required_period_bars: int,
    available_period_bars: int = 0,
    reason: str,
) -> ChanlunCoverage:
    return ChanlunCoverage(
        status="unverified",
        required_period_bars=required_period_bars,
        available_period_bars=available_period_bars,
        reason=reason,
        backfill_required=True,
    )


def _expected_trade_dates(period_data: _ClosedPeriodData | None) -> set[date] | None:
    if (
        period_data is None
        or period_data.availability != "ready"
        or period_data.coverage.status != "complete"
    ):
        return None
    return {
        trade_date
        for bar in period_data.bars
        if bar.volume > 0
        if (trade_date := _bar_trade_date(bar.date)) is not None
    }


def _continuity_reference_status(
    period_data: _ClosedPeriodData,
) -> StrongStockSourceStatus | None:
    if period_data.availability == "ready" and period_data.coverage.status == "complete":
        return None
    failed = next(
        (status for status in period_data.source_status if status.status == "failed"),
        None,
    )
    source = failed.source if failed is not None else (
        period_data.source_status[0].source if period_data.source_status else "日K线"
    )
    detail = (
        f"{failed.detail}；分钟连续性无法验证"
        if failed is not None
        else (
            f"{source}覆盖不足: {period_data.coverage.reason}；"
            "分钟连续性参考不足，连续性无法验证"
        )
    )
    return StrongStockSourceStatus(
        source=source,
        status="failed",
        detail=detail,
    )


def _completed_daily_bars(bars: list[KlineBar], now: datetime) -> list[KlineBar]:
    completed: list[tuple[date, KlineBar]] = []
    current_date = now.date()
    current_time = now.timetz().replace(tzinfo=None)
    for bar in bars:
        trade_date = _bar_trade_date(bar.date)
        if trade_date is None:
            continue
        if trade_date < current_date or (trade_date == current_date and current_time >= time(15)):
            completed.append((trade_date, bar))
    return [bar for _trade_date, bar in sorted(completed, key=lambda value: value[0])]


def _closed_bar_boundary(period: ChanlunPeriod, value: str) -> str:
    if period != "1d":
        return value
    trade_date = _bar_trade_date(value)
    if trade_date is None:
        return value
    return datetime.combine(trade_date, time(15), tzinfo=SHANGHAI).isoformat(timespec="seconds")


def _closed_input_freshness(
    period: ChanlunPeriod,
    bars: tuple[KlineBar, ...],
    now: datetime,
) -> ClosedInputFreshness:
    if not bars:
        return "insufficient"
    if not _calendar_coverage_available(now.date()):
        return "stale"
    try:
        last_closed = datetime.fromisoformat(
            _closed_bar_boundary(period, bars[-1].date).replace("Z", "+00:00")
        )
    except ValueError:
        return "stale"
    if last_closed.tzinfo is None:
        last_closed = last_closed.replace(tzinfo=SHANGHAI)
    else:
        last_closed = last_closed.astimezone(SHANGHAI)
    return "fresh" if last_closed >= _expected_latest_close(period, now) else "stale"


def _expected_latest_close(period: ChanlunPeriod, now: datetime) -> datetime:
    current = _to_shanghai(now)
    if period == "1d":
        if _is_open_session(current.date()) and current.time() >= time(15):
            return datetime.combine(current.date(), time(15), tzinfo=SHANGHAI)
        return datetime.combine(
            _previous_open_session(current.date()),
            time(15),
            tzinfo=SHANGHAI,
        )

    if not _is_open_session(current.date()):
        return datetime.combine(
            _previous_open_session(current.date()),
            time(15),
            tzinfo=SHANGHAI,
        )

    period_minutes = _INTRADAY_PERIOD_MINUTES[period]
    latest: datetime | None = None
    for session_start, session_end in ((time(9, 30), time(11, 30)), (time(13), time(15))):
        boundary = datetime.combine(current.date(), session_start, tzinfo=SHANGHAI) + timedelta(
            minutes=period_minutes
        )
        session_close = datetime.combine(current.date(), session_end, tzinfo=SHANGHAI)
        while boundary <= session_close and boundary <= current:
            latest = boundary
            boundary += timedelta(minutes=period_minutes)
    if latest is not None:
        return latest
    return datetime.combine(
        _previous_open_session(current.date()),
        time(15),
        tzinfo=SHANGHAI,
    )


def _expected_close_fingerprint(now: datetime) -> str:
    return ",".join(
        f"{period}={_expected_latest_close(period, now).isoformat(timespec='seconds')}"
        for period in _WORKSPACE_PERIODS
    )


@lru_cache(maxsize=1)
def _bundled_exchange_calendar() -> tuple[date, date, frozenset[date]] | None:
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


def _is_open_session(value: date) -> bool:
    calendar_data = _bundled_exchange_calendar()
    if calendar_data is not None:
        first_date, last_date, open_sessions = calendar_data
        if first_date <= value <= last_date:
            return value in open_sessions
    return value.weekday() < 5


def _calendar_coverage_available(value: date) -> bool:
    calendar_data = _bundled_exchange_calendar()
    if calendar_data is None:
        return False
    first_date, last_date, _open_sessions = calendar_data
    return first_date <= value <= last_date


def _calendar_source_status(value: date) -> StrongStockSourceStatus | None:
    if _calendar_coverage_available(value):
        return None
    return StrongStockSourceStatus(
        source=_CALENDAR_SOURCE,
        status="failed",
        detail=_CALENDAR_UNAVAILABLE_DETAIL,
    )


def _previous_open_session(value: date) -> date:
    calendar_data = _bundled_exchange_calendar()
    if calendar_data is not None:
        first_date, last_date, open_sessions = calendar_data
        if first_date <= value <= last_date:
            previous = value - timedelta(days=1)
            while previous >= first_date:
                if previous in open_sessions:
                    return previous
                previous -= timedelta(days=1)
    return _previous_weekday(value)


def _previous_weekday(value: date) -> date:
    previous = value - timedelta(days=1)
    while previous.weekday() >= 5:
        previous -= timedelta(days=1)
    return previous


def _bar_trade_date(value: str) -> date | None:
    try:
        if len(value) == 8 and value.isdigit():
            return datetime.strptime(value, "%Y%m%d").date()
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(SHANGHAI).date()
    except ValueError:
        return None


def _stored_closed_minutes(bars: list[StoredMinuteBar]) -> list[TickFlowIntradayBar]:
    return [
        TickFlowIntradayBar(
            timestamp=int(datetime.fromisoformat(bar.timestamp).timestamp() * 1000),
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            amount=bar.amount,
            prev_close=bar.prev_close,
        )
        for bar in bars
        if bar.closed
    ]


def _minute_timestamp(bar: TickFlowIntradayBar) -> str:
    return datetime.fromtimestamp(bar.timestamp / 1000, tz=SHANGHAI).isoformat(
        timespec="seconds"
    )


def _minute_trade_date(bar: TickFlowIntradayBar) -> date:
    return datetime.fromtimestamp(bar.timestamp / 1000, tz=SHANGHAI).date()


def _has_current_latest_bucket(
    bars: list[TickFlowIntradayBar],
    *,
    period: Literal["5m", "30m", "60m"],
    now: datetime,
) -> bool:
    latest_close = _expected_latest_close(period, now)
    if latest_close.date() != now.date():
        return False
    return any(
        bar.date == latest_close.isoformat(timespec="seconds")
        for bar in aggregate_closed_intraday_bars(bars, period=period, now=now)
    )


def _minute_is_closed(bar: TickFlowIntradayBar, now: datetime) -> bool:
    timestamp = datetime.fromtimestamp(bar.timestamp / 1000, tz=SHANGHAI)
    return timestamp + timedelta(minutes=1) <= now


def _intraday_fetch_count(period: Literal["5m", "30m", "60m"], lookback: int) -> int:
    return min(2400, max(120, lookback * _INTRADAY_PERIOD_MINUTES[period]))


def _daily_adjustment_mode(provider: object | None) -> str:
    adjustment = str(getattr(provider, "adjust", "")).lower()
    if adjustment == "forward":
        return "forward_adjusted"
    if adjustment == "backward":
        return "backward_adjusted"
    return _RAW_ADJUSTMENT


def _cache_key(
    *,
    symbol: str,
    period: ChanlunPeriod,
    lookback: int,
    last_closed_bar_at: str | None,
    adjustment_mode: str,
    include_observing: bool,
    generation: int,
) -> str:
    return (
        f"chanlun:{symbol}:{period}:{lookback}:{last_closed_bar_at or 'none'}:"
        f"{adjustment_mode}:{_RULE_VERSION}:generation={generation}:"
        f"observing={int(include_observing)}"
    )


def _raise_if_canceled(should_cancel: CancelCheck) -> None:
    if should_cancel():
        raise RuntimeError("缠论分钟历史补齐已取消")


def _to_shanghai(value: datetime) -> datetime:
    return value.replace(tzinfo=SHANGHAI) if value.tzinfo is None else value.astimezone(SHANGHAI)


def _exception_detail(exc: Exception) -> str:
    message = str(exc).strip()
    return f"{exc.__class__.__name__}: {message}" if message else exc.__class__.__name__
