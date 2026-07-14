from __future__ import annotations

from datetime import date, datetime, time
from math import isfinite
from zoneinfo import ZoneInfo

from app.models import KlineBar
from app.providers.free_stockdb import FreeStockDbClient


SHANGHAI = ZoneInfo("Asia/Shanghai")


class FreeStockDbResearchSource:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 180.0,
        http_client: object | None = None,
    ) -> None:
        self.client = FreeStockDbClient(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            http_client=http_client,
        )

    def daily_bars(self, symbol: str, *, start: str, end: str) -> list[KlineBar]:
        return self._bars(table="日k", symbol=symbol, start=start, end=end)

    def minute_bars(self, symbol: str, *, start: str, end: str) -> list[KlineBar]:
        return self._bars(table="分钟k", symbol=symbol, start=start, end=end)

    def _bars(self, *, table: str, symbol: str, start: str, end: str) -> list[KlineBar]:
        start_date = _parse_date(start)
        end_date = _parse_date(end)
        if start_date > end_date:
            raise ValueError("history start must not be after end")
        rows = self.client.vals(
            table=table,
            k1=_raw_code(symbol),
            k2=f"{start_date:%Y%m%d}000000<{end_date:%Y%m%d}235959",
        )
        normalized: dict[str, KlineBar] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            bar = _bar_from_row(row, daily=table == "日k")
            if bar is None:
                continue
            timestamp = _parse_timestamp(bar.date)
            if not start_date <= timestamp.date() <= end_date:
                continue
            normalized[bar.date] = bar
        return [normalized[key] for key in sorted(normalized)]


def _bar_from_row(row: dict[str, object], *, daily: bool) -> KlineBar | None:
    try:
        values = tuple(float(row[key]) for key in ("open", "high", "low", "close", "volume", "amount"))
        open_price, high, low, close, volume, amount = values
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not all(isfinite(value) for value in values):
        return None
    if min(open_price, high, low, close) <= 0 or volume < 0 or amount < 0:
        return None
    if low > min(open_price, close) or high < max(open_price, close):
        return None
    try:
        timestamp = _parse_timestamp(str(row["date"]))
    except (KeyError, TypeError, ValueError):
        return None
    if daily:
        timestamp = datetime.combine(timestamp.date(), time.min, tzinfo=SHANGHAI)
    return KlineBar(
        date=timestamp.isoformat(timespec="seconds"),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=amount,
    )


def _parse_date(value: str | date) -> date:
    text = str(value).strip()
    if len(text) >= 8 and text[:8].isdigit():
        return datetime.strptime(text[:8], "%Y%m%d").date()
    return date.fromisoformat(text[:10])


def _parse_timestamp(value: str) -> datetime:
    text = value.strip()
    if len(text) >= 14 and text[:14].isdigit():
        parsed = datetime.strptime(text[:14], "%Y%m%d%H%M%S")
        return parsed.replace(tzinfo=SHANGHAI)
    if len(text) == 8 and text.isdigit():
        parsed = datetime.strptime(text, "%Y%m%d")
        return parsed.replace(tzinfo=SHANGHAI)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI)


def _raw_code(symbol: str) -> str:
    text = symbol.strip().upper()
    return text.split(".", 1)[0]
