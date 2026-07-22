from __future__ import annotations

from datetime import datetime, time
from typing import Protocol
from zoneinfo import ZoneInfo

from app.models import (
    KlineBar,
    SentimentPercentilePoint,
    SentimentPercentileResponse,
    StrongStockDataUnavailable,
    StrongStockSourceStatus,
)
from app.services.market_sentiment_percentile import (
    MODEL_VERSION,
    WEIGHTS,
    calculate_sentiment_percentile,
)
from app.services.market_sentiment_percentile_store import MarketSentimentPercentileStore


SHANGHAI = ZoneInfo("Asia/Shanghai")
BENCHMARK_SYMBOL = "000985.SH"
KLINE_COUNT = 1020
COMPLETION_CUTOFF = time(15, 10)


class DailyKlineProvider(Protocol):
    source_name: str

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]: ...


class MarketSentimentPercentileService:
    def __init__(
        self,
        *,
        provider: DailyKlineProvider,
        store: MarketSentimentPercentileStore,
    ) -> None:
        self.provider = provider
        self.store = store

    def get(
        self,
        as_of: str | None = None,
        refresh: bool = False,
        now: datetime | None = None,
    ) -> SentimentPercentileResponse:
        local_now = _shanghai_now(now)
        cached = self.store.load()
        if cached is not None and not refresh and _is_current_local_day(cached, local_now):
            return _select_as_of(
                cached.model_copy(update={"cache_status": "cached"}, deep=True), as_of
            )

        try:
            canonical = self._refresh(local_now)
        except Exception as exc:
            if cached is None:
                raise StrongStockDataUnavailable(
                    f"市场情绪分位数据不可用: {exc.__class__.__name__}"
                ) from exc
            stale = cached.model_copy(
                update={
                    "cache_status": "stale",
                    "source_status": [
                        *cached.source_status,
                        StrongStockSourceStatus(
                            source=self.provider.source_name,
                            status="failed",
                            detail=f"刷新失败: {exc.__class__.__name__}",
                        ),
                    ],
                    "notes": [*cached.notes, "最新快照刷新失败，已返回最近成功快照。"],
                },
                deep=True,
            )
            return _select_as_of(stale, as_of)

        return _select_as_of(canonical.model_copy(deep=True), as_of)

    def _refresh(self, now: datetime) -> SentimentPercentileResponse:
        bars = filter_completed_daily_bars(
            self.provider.get_klines(BENCHMARK_SYMBOL, count=KLINE_COUNT),
            now=now,
        )
        points = calculate_sentiment_percentile(bars)[-500:]
        if not points:
            raise StrongStockDataUnavailable("市场情绪分位历史不足")

        latest = points[-1]
        response = SentimentPercentileResponse(
            model_version=MODEL_VERSION,
            weights=WEIGHTS,
            latest_complete_trade_date=latest.trade_date,
            selected_trade_date=latest.trade_date,
            selected=latest,
            history=points,
            cache_status="fresh",
            source_status=[
                StrongStockSourceStatus(
                    source=self.provider.source_name,
                    status="success",
                    detail=f"已加载 {len(bars)} 根完整日K线",
                )
            ],
            generated_at=now.isoformat(timespec="seconds"),
        )
        return self.store.save(response)


def filter_completed_daily_bars(
    bars: list[KlineBar], *, now: datetime | None = None
) -> list[KlineBar]:
    local_now = _shanghai_now(now)
    if _is_after_completion_cutoff(local_now):
        return list(bars)
    current_date = local_now.date().isoformat()
    return [bar for bar in bars if bar.date != current_date]


def _shanghai_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(SHANGHAI)
    if now.tzinfo is None:
        return now.replace(tzinfo=SHANGHAI)
    return now.astimezone(SHANGHAI)


def _is_current_local_day(response: SentimentPercentileResponse, now: datetime) -> bool:
    try:
        generated_at = datetime.fromisoformat(response.generated_at)
    except ValueError:
        return False
    generated_local = _shanghai_now(generated_at)
    return generated_local.date() == now.date() and (
        _is_after_completion_cutoff(generated_local) == _is_after_completion_cutoff(now)
    )


def _is_after_completion_cutoff(value: datetime) -> bool:
    return value.timetz().replace(tzinfo=None) >= COMPLETION_CUTOFF


def _select_as_of(
    response: SentimentPercentileResponse,
    as_of: str | None,
) -> SentimentPercentileResponse:
    history = (
        response.history
        if as_of is None
        else [point for point in response.history if point.trade_date <= as_of]
    )
    selected: SentimentPercentilePoint | None = history[-1] if history else None
    return response.model_copy(
        update={
            "history": history,
            "selected": selected,
            "selected_trade_date": selected.trade_date if selected is not None else None,
        },
        deep=True,
    )
