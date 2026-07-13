from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time
from typing import Protocol, cast
from zoneinfo import ZoneInfo

from app.models import (
    ChanlunAnalysisResponse,
    ChanlunPeriod,
    ChanlunPeriodSummary,
    ChanlunScreeningPeriodSummary,
    ChanlunScreeningSummary,
    ChanlunWorkspaceResponse,
    KlineBar,
)
from app.providers.tickflow import TickFlowIntradayBar
from app.services.chanlun.bars import aggregate_closed_intraday_bars
from app.services.chanlun.confluence import derive_confluence_signals
from app.services.short_term_cache import TtlCache


_PERIODS: tuple[ChanlunPeriod, ...] = ("1d", "60m", "30m", "5m")
_BUY_SIGNAL_WEIGHTS: dict[ChanlunPeriod, int] = {
    "1d": 5,
    "60m": 10,
    "30m": 15,
    "5m": 20,
}
_CONFIRMED_STATUSES = {"confirmed", "final"}
SHANGHAI = ZoneInfo("Asia/Shanghai")


class MinuteBarStore(Protocol):
    def read(self, symbol: str, *, end_at: str | None = None) -> list[object]: ...


class ChanlunStructureAdapter(Protocol):
    def analyze(
        self,
        symbol: str,
        *,
        period: ChanlunPeriod,
        bars: list[KlineBar],
        include_observing: bool = False,
    ) -> ChanlunAnalysisResponse: ...


class CachedChanlunScreeningSummarizer:
    def __init__(
        self,
        *,
        store: MinuteBarStore,
        adapter: ChanlunStructureAdapter,
        now_provider: Callable[[], datetime] | None = None,
        cache: TtlCache[ChanlunScreeningSummary] | None = None,
        cache_seconds: int = 30,
    ) -> None:
        self.store = store
        self.adapter = adapter
        self.now_provider = now_provider or (lambda: datetime.now(tz=SHANGHAI))
        self.cache = cache or TtlCache(ttl_seconds=cache_seconds, name="chanlun_screening")

    def summarize(
        self,
        symbol: str,
        *,
        daily_bars: list[KlineBar],
        trade_date: str,
    ) -> ChanlunScreeningSummary:
        cutoff = _screening_cutoff(trade_date, self.now_provider())
        completed_daily = [
            bar
            for bar in daily_bars
            if (bar_date := _bar_date(bar.date)) is not None
            and (bar_date < cutoff.date() or (bar_date == cutoff.date() and cutoff.time() >= time(15)))
        ]
        stored_minutes = self.store.read(symbol, end_at=cutoff.isoformat(timespec="seconds"))
        cache_key = _summary_cache_key(symbol, trade_date, completed_daily, stored_minutes)
        minute_cache_stale = _minute_cache_is_stale(stored_minutes, cutoff)

        def build() -> ChanlunScreeningSummary:
            analyses: dict[ChanlunPeriod, ChanlunAnalysisResponse] = {
                "1d": self.adapter.analyze(
                    symbol,
                    period="1d",
                    bars=completed_daily,
                    include_observing=False,
                )
            }
            minute_bars = _stored_closed_minutes(stored_minutes)
            for period in cast(tuple[ChanlunPeriod, ...], ("60m", "30m", "5m")):
                bars = aggregate_closed_intraday_bars(minute_bars, period=period, now=cutoff)
                analysis = self.adapter.analyze(
                    symbol,
                    period=period,
                    bars=bars,
                    include_observing=False,
                )
                analyses[period] = (
                    analysis.model_copy(update={"availability": "stale"})
                    if minute_cache_stale and analysis.availability == "ready"
                    else analysis
                )
            workspace = ChanlunWorkspaceResponse(
                symbol=symbol,
                periods=[_period_summary(analyses[period]) for period in _PERIODS],
                analysis=analyses["1d"],
                confluence_signals=derive_confluence_signals(analyses),
            )
            return build_chanlun_screening_summary(workspace, now=cutoff)

        return self.cache.get_or_set(cache_key, build)


def build_chanlun_screening_summary(
    workspace: ChanlunWorkspaceResponse,
    *,
    now: datetime,
) -> ChanlunScreeningSummary:
    source_periods = {item.period: item for item in workspace.periods}
    periods = [
        _screening_period_summary(
            source_periods.get(period)
            or ChanlunPeriodSummary(period=period, availability="unavailable"),
            now=now,
        )
        for period in _PERIODS
    ]
    available_periods = [item for item in periods if item.availability in {"ready", "stale"}]
    availability = (
        "ready"
        if len(available_periods) == len(_PERIODS)
        else "partial"
        if available_periods
        else "unavailable"
    )
    freshness = (
        "insufficient"
        if availability != "ready"
        else "stale"
        if any(item.availability == "stale" for item in periods)
        else "fresh"
    )

    bullish_periods = sum(item.direction == "up" for item in available_periods)
    bearish_periods = sum(item.direction == "down" for item in available_periods)
    buy_periods = [
        item
        for item in available_periods
        if item.latest_signal_type is not None and item.latest_signal_type.endswith("_buy")
    ]
    sell_periods = [
        item
        for item in available_periods
        if item.latest_signal_type is not None and item.latest_signal_type.endswith("_sell")
    ]
    score = bullish_periods * 10 + sum(_BUY_SIGNAL_WEIGHTS[item.period] for item in buy_periods)
    available_period_keys = {item.period for item in available_periods}
    has_available_buy_confluence = any(
        signal.status in _CONFIRMED_STATUSES
        and signal.type.endswith("_buy")
        and signal.higher_period in available_period_keys
        and signal.lower_period in available_period_keys
        for signal in workspace.confluence_signals
    )
    if has_available_buy_confluence:
        score += 10

    confirmed_times = [
        value
        for item in periods
        for value in (item.latest_signal_at, item.latest_divergence_at)
        if value is not None
    ]
    confirmed_times.extend(
        item.occurred_at
        for item in workspace.confluence_signals
        if item.status in _CONFIRMED_STATUSES
    )
    return ChanlunScreeningSummary(
        availability=availability,
        freshness=freshness,
        periods=periods,
        confluence_score=max(0, min(100, score)),
        bullish_periods=bullish_periods,
        bearish_periods=bearish_periods,
        has_confirmed_buy=bool(buy_periods),
        has_confirmed_sell=bool(sell_periods),
        latest_confirmed_at=max(confirmed_times, key=_parse_timestamp) if confirmed_times else None,
    )


def passes_chanlun_screening_filters(
    summary: ChanlunScreeningSummary | None,
    *,
    min_confluence_score: int | None,
    require_confirmed_buy: bool,
) -> bool:
    if summary is None or summary.availability != "ready" or summary.freshness != "fresh":
        return True
    if min_confluence_score is not None and summary.confluence_score < min_confluence_score:
        return False
    if require_confirmed_buy and not summary.has_confirmed_buy:
        return False
    return True


def _screening_period_summary(
    period: ChanlunPeriodSummary,
    *,
    now: datetime,
) -> ChanlunScreeningPeriodSummary:
    signal = period.latest_signal
    if signal is not None and signal.status not in _CONFIRMED_STATUSES:
        signal = None
    divergence = period.latest_divergence
    if divergence is not None and divergence.status not in _CONFIRMED_STATUSES:
        divergence = None
    signal_age_seconds = None
    if signal is not None:
        signal_age_seconds = max(0, int((now - _parse_timestamp(signal.occurred_at)).total_seconds()))
    return ChanlunScreeningPeriodSummary(
        period=period.period,
        availability=period.availability,
        direction=period.direction,
        latest_signal_type=signal.type if signal is not None else None,
        latest_signal_at=signal.occurred_at if signal is not None else None,
        latest_divergence_type=divergence.type if divergence is not None else None,
        latest_divergence_at=divergence.occurred_at if divergence is not None else None,
        signal_age_seconds=signal_age_seconds,
        last_closed_bar_at=period.last_closed_bar_at,
    )


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _period_summary(analysis: ChanlunAnalysisResponse) -> ChanlunPeriodSummary:
    structures = [
        item
        for item in (analysis.segments or analysis.strokes)
        if item.status in _CONFIRMED_STATUSES
    ]
    zones = [item for item in analysis.zones if item.status in _CONFIRMED_STATUSES]
    divergences = [item for item in analysis.divergences if item.status in _CONFIRMED_STATUSES]
    signals = [item for item in analysis.signals if item.status in _CONFIRMED_STATUSES]
    return ChanlunPeriodSummary(
        period=analysis.period,
        availability=analysis.availability,
        direction=structures[-1].direction if structures else "unknown",
        latest_zone=zones[-1] if zones else None,
        latest_divergence=divergences[-1] if divergences else None,
        latest_signal=signals[-1] if signals else None,
        last_closed_bar_at=analysis.last_closed_bar_at,
    )


def _screening_cutoff(trade_date: str, now: datetime) -> datetime:
    current = now.astimezone(SHANGHAI) if now.tzinfo is not None else now.replace(tzinfo=SHANGHAI)
    requested = date.fromisoformat(trade_date)
    if requested < current.date() or current.time() >= time(15):
        return datetime.combine(requested, time(15), tzinfo=SHANGHAI)
    return current


def _bar_date(value: str) -> date | None:
    try:
        if len(value) == 8 and value.isdigit():
            return datetime.strptime(value, "%Y%m%d").date()
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _stored_closed_minutes(rows: list[object]) -> list[TickFlowIntradayBar]:
    return [
        TickFlowIntradayBar(
            timestamp=int(datetime.fromisoformat(str(getattr(row, "timestamp"))).timestamp() * 1000),
            open=float(getattr(row, "open")),
            high=float(getattr(row, "high")),
            low=float(getattr(row, "low")),
            close=float(getattr(row, "close")),
            volume=float(getattr(row, "volume")),
            amount=float(getattr(row, "amount")),
            prev_close=getattr(row, "prev_close"),
        )
        for row in rows
        if bool(getattr(row, "closed", False))
    ]


def _summary_cache_key(
    symbol: str,
    trade_date: str,
    daily_bars: list[KlineBar],
    minute_rows: list[object],
) -> str:
    daily_tail = daily_bars[-1].date if daily_bars else "none"
    minute_tail = str(getattr(minute_rows[-1], "timestamp", "none")) if minute_rows else "none"
    return ":".join(
        (symbol, trade_date, str(len(daily_bars)), daily_tail, str(len(minute_rows)), minute_tail)
    )


def _minute_cache_is_stale(minute_rows: list[object], cutoff: datetime) -> bool:
    if cutoff.time() < time(9, 35):
        return False
    latest_date = None
    if minute_rows:
        try:
            latest_date = datetime.fromisoformat(str(getattr(minute_rows[-1], "timestamp"))).date()
        except ValueError:
            latest_date = None
    return latest_date != cutoff.date()
