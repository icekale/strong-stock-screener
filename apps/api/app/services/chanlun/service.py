from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.models import (
    ChanlunAnalysisResponse,
    ChanlunPeriod,
    ChanlunPeriodSummary,
    ChanlunWorkspaceResponse,
    KlineBar,
    StrongStockSourceStatus,
)
from app.providers.tickflow import TickFlowIntradayBar
from app.services.background_jobs import CancelCheck, ProgressCallback
from app.services.chanlun.bars import aggregate_closed_intraday_bars, normalize_intraday_bars
from app.services.chanlun.store import ChanlunMinuteBarStore, StoredMinuteBar
from app.services.chanlun.symbols import normalize_chanlun_symbol
from app.services.short_term_cache import TtlCache


SHANGHAI = ZoneInfo("Asia/Shanghai")
_MIN_COMPLETED_BARS = 20
_RULE_VERSION = "cl-v1"
_RAW_ADJUSTMENT = "raw_unadjusted"
_INTRADAY_PERIOD_MINUTES = {"5m": 5, "30m": 30, "60m": 60}


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
        self.minute_retention_days = minute_retention_days or settings.chanlun_minute_retention_days
        self.history_max_bars = history_max_bars or settings.chanlun_backfill_max_bars

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
        if period == "1d":
            return self._daily_analysis(
                normalized_symbol,
                lookback=lookback,
                include_observing=include_observing,
                now=current,
            )
        return self._intraday_analysis(
            normalized_symbol,
            period=period,
            lookback=lookback,
            include_observing=include_observing,
            now=current,
        )

    def workspace(self, symbol: str, *, lookback: int) -> ChanlunWorkspaceResponse:
        analyses = {
            period: self.analysis(
                symbol,
                period=period,
                lookback=lookback,
                include_observing=period == "1d",
            )
            for period in ("1d", "60m", "30m", "5m")
        }
        return ChanlunWorkspaceResponse(
            symbol=normalize_chanlun_symbol(symbol) or symbol.strip().upper(),
            periods=[_summary(analyses[period]) for period in ("1d", "60m", "30m", "5m")],
            analysis=analyses["1d"],
        )

    def backfill(
        self,
        symbol: str,
        *,
        progress: ProgressCallback,
        should_cancel: CancelCheck,
    ) -> dict[str, object]:
        normalized_symbol = normalize_chanlun_symbol(symbol) or symbol.strip().upper()
        _raise_if_canceled(should_cancel)
        progress(0, 3, "准备补齐分钟历史")
        if self.history_provider is None:
            raise RuntimeError("未配置分钟历史数据源")

        bars = self.history_provider.get_minute_bars(
            normalized_symbol,
            max_bars=self.history_max_bars,
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
        self.cache.clear()
        progress(3, 3, "分钟历史补齐完成")
        return {"symbol": normalized_symbol, "written_bars": len(normalized_bars)}

    def _daily_analysis(
        self,
        symbol: str,
        *,
        lookback: int,
        include_observing: bool,
        now: datetime,
    ) -> ChanlunAnalysisResponse:
        provider = self.daily_provider
        source_name = getattr(provider, "source_name", "日K线")
        adjustment_mode = _daily_adjustment_mode(provider)
        if provider is None:
            return _unavailable_response(
                symbol,
                "1d",
                [],
                [
                    StrongStockSourceStatus(
                        source=source_name,
                        status="failed",
                        detail="日K线数据源未配置",
                    )
                ],
                adjustment_mode=adjustment_mode,
            )
        try:
            daily_bars = provider.get_klines(symbol, count=max(lookback + 1, _MIN_COMPLETED_BARS + 1))
        except Exception as exc:
            return _unavailable_response(
                symbol,
                "1d",
                [],
                [
                    StrongStockSourceStatus(
                        source=source_name,
                        status="failed",
                        detail=f"日K线读取失败: {_exception_detail(exc)}",
                    )
                ],
                adjustment_mode=adjustment_mode,
            )

        bars = _completed_daily_bars(daily_bars, now)[-lookback:]
        source_status = [
            StrongStockSourceStatus(
                source=source_name,
                status="success",
                detail=f"返回 {len(bars)} 条已完成日K",
            )
        ]
        return self._analyze_completed(
            symbol,
            period="1d",
            bars=bars,
            lookback=lookback,
            include_observing=include_observing,
            source_status=source_status,
            adjustment_mode=adjustment_mode,
        )

    def _intraday_analysis(
        self,
        symbol: str,
        *,
        period: Literal["5m", "30m", "60m"],
        lookback: int,
        include_observing: bool,
        now: datetime,
    ) -> ChanlunAnalysisResponse:
        source_name = getattr(self.intraday_provider, "source_name", "TickFlow 分钟线")
        live_failed = False
        source_status: list[StrongStockSourceStatus] = []
        try:
            payload = self.intraday_provider.get_intraday_bars(
                [symbol],
                period="1m",
                count=_intraday_fetch_count(period, lookback),
            )
            current_bars = normalize_intraday_bars(payload.get(symbol, []))
            self._upsert_live_minutes(symbol, current_bars, source=source_name, now=now)
            source_status.append(
                StrongStockSourceStatus(
                    source=source_name,
                    status="success",
                    detail=f"读取并写入 {len(current_bars)} 条当前1分钟线",
                )
            )
        except Exception as exc:
            live_failed = True
            source_status.append(
                StrongStockSourceStatus(
                    source=source_name,
                    status="failed",
                    detail=f"当前1分钟线读取失败: {_exception_detail(exc)}",
                )
            )

        minute_bars = _stored_closed_minutes(self.store.read(symbol))
        completed = aggregate_closed_intraday_bars(minute_bars, period=period, now=now)[-lookback:]
        source_status.append(
            StrongStockSourceStatus(
                source="Chanlun SQLite分钟线",
                status="stale" if live_failed else "success",
                detail=f"从 {len(minute_bars)} 条闭合原始分钟线生成 {len(completed)} 条{period}闭合K线",
            )
        )

        if live_failed and len(completed) < _MIN_COMPLETED_BARS:
            return _unavailable_response(
                symbol,
                period,
                completed,
                source_status,
                adjustment_mode=_RAW_ADJUSTMENT,
                detail="实时分钟线不可用且本地闭合历史不足以生成缠论结构",
            )

        result = self._analyze_completed(
            symbol,
            period=period,
            bars=completed,
            lookback=lookback,
            include_observing=include_observing,
            source_status=source_status,
            adjustment_mode=_RAW_ADJUSTMENT,
        )
        if live_failed and result.availability == "ready":
            return result.model_copy(deep=True, update={"availability": "stale"})
        return result

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
        )

        def build() -> ChanlunAnalysisResponse:
            result = self.adapter.analyze(
                symbol,
                period=period,
                bars=bars,
                include_observing=include_observing,
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
                },
            )

        cached = self.cache.get_or_set(cache_key, build)
        return cached.model_copy(
            deep=True,
            update={"source_status": [*source_status, *cached.source_status]},
        )


def _summary(analysis: ChanlunAnalysisResponse) -> ChanlunPeriodSummary:
    structures = analysis.segments or analysis.strokes
    return ChanlunPeriodSummary(
        period=analysis.period,
        availability=analysis.availability,
        direction=structures[-1].direction if structures else "unknown",
        latest_zone=analysis.zones[-1] if analysis.zones else None,
        last_closed_bar_at=analysis.last_closed_bar_at,
    )


def _unavailable_response(
    symbol: str,
    period: ChanlunPeriod,
    bars: list[KlineBar],
    source_status: list[StrongStockSourceStatus],
    *,
    adjustment_mode: str,
    detail: str | None = None,
) -> ChanlunAnalysisResponse:
    statuses = list(source_status)
    if detail:
        statuses.append(StrongStockSourceStatus(source="Chanlun结构", status="failed", detail=detail))
    return ChanlunAnalysisResponse(
        symbol=symbol,
        period=period,
        availability="unavailable",
        bars=bars,
        source_status=statuses,
        last_closed_bar_at=bars[-1].date if bars else None,
        adjustment_mode=adjustment_mode,
        rule_version=_RULE_VERSION,
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
) -> str:
    return (
        f"chanlun:{symbol}:{period}:{lookback}:{last_closed_bar_at or 'none'}:"
        f"{adjustment_mode}:{_RULE_VERSION}:observing={int(include_observing)}"
    )


def _raise_if_canceled(should_cancel: CancelCheck) -> None:
    if should_cancel():
        raise RuntimeError("缠论分钟历史补齐已取消")


def _to_shanghai(value: datetime) -> datetime:
    return value.replace(tzinfo=SHANGHAI) if value.tzinfo is None else value.astimezone(SHANGHAI)


def _exception_detail(exc: Exception) -> str:
    message = str(exc).strip()
    return f"{exc.__class__.__name__}: {message}" if message else exc.__class__.__name__
