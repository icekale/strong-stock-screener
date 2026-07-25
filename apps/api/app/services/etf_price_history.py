from __future__ import annotations

from datetime import date, datetime
from threading import RLock
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

from app.models import (
    EtfPriceHistoryPoint,
    EtfPriceHistoryResponse,
    KlineBar,
    StrongStockSourceStatus,
)
from app.services.huijin_etf_activity import ALL_ETFS


SHANGHAI = ZoneInfo("Asia/Shanghai")
PRICE_HISTORY_MODEL_VERSION = "etf-price-history-v1"


class EtfPriceHistoryUnavailable(RuntimeError):
    """Raised when a monitored ETF has no usable daily close data."""


class DailyKlineProvider(Protocol):
    source_name: str

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]: ...


class EtfPriceHistoryService:
    def __init__(
        self,
        *,
        provider: DailyKlineProvider,
        clock: Callable[[], datetime] | None = None,
        ttl_seconds: int = 60,
    ) -> None:
        self.provider = provider
        self.clock = clock or (lambda: datetime.now(SHANGHAI))
        self.ttl_seconds = max(0, ttl_seconds)
        self._cache: dict[tuple[str, int], tuple[datetime, EtfPriceHistoryResponse]] = {}
        self._lock = RLock()

    def history(
        self,
        symbol: str,
        *,
        days: int = 120,
        force: bool = False,
    ) -> EtfPriceHistoryResponse:
        normalized_symbol = symbol.strip().upper()
        if normalized_symbol not in ALL_ETFS:
            raise ValueError(f"未监控 ETF: {normalized_symbol}")
        normalized_days = max(1, min(days, 365))
        cache_key = (normalized_symbol, normalized_days)
        now = self.clock()
        with self._lock:
            cached = self._cache.get(cache_key)
            if (
                cached is not None
                and not force
                and (now - cached[0]).total_seconds() <= self.ttl_seconds
            ):
                return cached[1]

            bars = self.provider.get_klines(normalized_symbol, count=max(normalized_days, 120))
            points = _close_points(bars)[-normalized_days:]
            if not points:
                raise EtfPriceHistoryUnavailable(f"{normalized_symbol} 没有可用的日收盘价")
            definition = ALL_ETFS[normalized_symbol]
            generated_at = now.astimezone(SHANGHAI).isoformat(timespec="seconds")
            response = EtfPriceHistoryResponse(
                generated_at=generated_at,
                trade_date=points[-1].trade_date,
                as_of=generated_at,
                signal_stage="post_close",
                model_version=PRICE_HISTORY_MODEL_VERSION,
                source_status=[
                    StrongStockSourceStatus(
                        source=getattr(self.provider, "source_name", "日K线"),
                        status="success",
                        detail=f"返回 {len(points)} 个交易日收盘价",
                    )
                ],
                symbol=normalized_symbol,
                name=definition.name,
                points=points,
            )
            self._cache[cache_key] = (now, response)
            return response


def _close_points(bars: list[KlineBar]) -> list[EtfPriceHistoryPoint]:
    by_date: dict[str, EtfPriceHistoryPoint] = {}
    for bar in bars:
        trade_date = _normalize_trade_date(bar.date)
        if trade_date is None or bar.close <= 0:
            continue
        by_date[trade_date] = EtfPriceHistoryPoint(trade_date=trade_date, close=float(bar.close))
    return [by_date[trade_date] for trade_date in sorted(by_date)]


def _normalize_trade_date(value: object) -> str | None:
    text = str(value or "").strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        text = text[:10]
        pattern = "%Y-%m-%d"
    elif len(text) >= 8 and text[:8].isdigit():
        text = text[:8]
        pattern = "%Y%m%d"
    else:
        return None
    try:
        if pattern == "%Y-%m-%d":
            return date.fromisoformat(text).isoformat()
        return datetime.strptime(text, pattern).date().isoformat()
    except ValueError:
        return None
