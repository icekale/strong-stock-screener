from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from math import isfinite
from zoneinfo import ZoneInfo

from app.models import StrongStockDataUnavailable
from app.providers.tickflow import TickFlowIntradayBar


SHANGHAI = ZoneInfo("Asia/Shanghai")
_PAGE_SIZE = 800
_ONE_MINUTE_CATEGORY = 7


class TdxMinuteHistoryProvider:
    source_name = "通达信分钟历史"

    def __init__(
        self,
        *,
        client_factory: Callable[[], object] | None = None,
        enabled: bool,
        timeout_seconds: float,
    ) -> None:
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.client_factory = client_factory or (
            lambda: _default_client_factory(timeout_seconds=timeout_seconds)
        )

    def get_minute_bars(self, symbol: str, *, max_bars: int) -> list[TickFlowIntradayBar]:
        if not self.enabled:
            raise StrongStockDataUnavailable("通达信分钟历史未启用")

        client = self.client_factory()
        try:
            frames = [
                client.bars(
                    symbol=_normalize_code(symbol),
                    frequency=_ONE_MINUTE_CATEGORY,
                    start=start,
                    offset=min(_PAGE_SIZE, max_bars - start),
                )
                for start in range(0, max_bars, _PAGE_SIZE)
            ]
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()
        return normalize_tdx_frames(frames)[:max_bars]


def normalize_tdx_frames(frames: Iterable[object]) -> list[TickFlowIntradayBar]:
    normalized: dict[int, TickFlowIntradayBar] = {}
    for frame in frames:
        for row in _frame_records(frame):
            bar = _bar_from_row(row)
            if bar is not None:
                normalized[bar.timestamp] = bar
    return [normalized[timestamp] for timestamp in sorted(normalized)]


def _default_client_factory(*, timeout_seconds: float) -> object:
    from mootdx.quotes import Quotes

    return Quotes.factory(timeout=timeout_seconds)


def _normalize_code(symbol: str) -> str:
    return symbol.strip().split(".", maxsplit=1)[0]


def _frame_records(frame: object) -> list[Mapping[str, object]]:
    if frame is None:
        return []
    to_dict = getattr(frame, "to_dict", None)
    if not callable(to_dict):
        return []
    try:
        records = to_dict(orient="records")
    except TypeError:
        records = to_dict("records")
    if not isinstance(records, list):
        return []
    return [row for row in records if isinstance(row, Mapping)]


def _bar_from_row(row: Mapping[str, object]) -> TickFlowIntradayBar | None:
    try:
        open_price = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        volume = float(row["vol"])
        amount = float(row["amount"])
        timestamp = _timestamp_ms(row["datetime"])
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        return None
    if not _valid_bar(open_price, high, low, close, volume, amount):
        return None
    return TickFlowIntradayBar(
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=amount,
    )


def _timestamp_ms(value: object) -> int:
    timestamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=SHANGHAI)
    return int(timestamp.timestamp() * 1000)


def _valid_bar(
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    amount: float,
) -> bool:
    values = (open_price, high, low, close, volume, amount)
    return (
        all(isfinite(value) for value in values)
        and open_price > 0
        and high > 0
        and low > 0
        and close > 0
        and volume >= 0
        and amount >= 0
        and low <= min(open_price, close)
        and high >= max(open_price, close)
    )
