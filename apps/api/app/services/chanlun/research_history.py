from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time
from math import isfinite
from time import sleep
from zoneinfo import ZoneInfo

from app.models import KlineBar
from app.providers.free_stockdb import FreeStockDbClient, FreeStockDbRequestError


SHANGHAI = ZoneInfo("Asia/Shanghai")


class FreeStockDbResearchSource:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 180.0,
        http_client: object | None = None,
        max_workers: int = 4,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.25,
    ) -> None:
        self.client = FreeStockDbClient(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            http_client=http_client,
        )
        self.max_workers = max(1, max_workers)
        self.max_retries = max(0, max_retries)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    def daily_bars(self, symbol: str, *, start: str, end: str) -> list[KlineBar]:
        return self._bars(table="日k", symbol=symbol, start=start, end=end)

    def daily_rows(self, *, start: str, end: str) -> list[dict[str, object]]:
        start_date = _parse_date(start)
        end_date = _parse_date(end)
        if start_date > end_date:
            raise ValueError("history start must not be after end")
        rows = [
            row
            for _year, chunk in self.daily_rows_by_year(start=start, end=end)
            for row in chunk
        ]
        return sorted(rows, key=lambda row: (str(row.get("date", "")), str(row.get("code", ""))))

    def daily_rows_by_year(
        self,
        *,
        start: str,
        end: str,
        skip_chunks: set[str] | None = None,
    ):
        start_date = _parse_date(start)
        end_date = _parse_date(end)
        if start_date > end_date:
            raise ValueError("history start must not be after end")
        codes = _research_codes(self._request_with_retry(lambda: self.client.get_selector("股票代码")))
        months = [
            month
            for month in _months_between(start_date, end_date)
            if month not in (skip_chunks or set())
        ]

        def fetch(code: str, month_key: str) -> list[dict[str, object]]:
            rows = self._request_with_retry(
                lambda: self.client.get(table="日k", k1=code, k2=f"{month_key}*")
            )
            return [
                _normalize_source_row(row)
                for row in rows
                if isinstance(row, dict)
                and (row_date := _row_date(row)) is not None
                and start_date <= row_date <= end_date
            ]

        for month_key in months:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                batches = executor.map(lambda code: fetch(code, month_key), codes)
                rows = [row for batch in batches for row in batch]
            yield month_key, sorted(
                rows,
                key=lambda row: (str(row.get("date", "")), str(row.get("code", ""))),
            )

    def _request_with_retry(self, operation: Callable[[], object]) -> object:
        for attempt in range(self.max_retries + 1):
            try:
                return operation()
            except FreeStockDbRequestError:
                if attempt >= self.max_retries:
                    raise
                sleep(self.retry_backoff_seconds * (2**attempt))
        raise RuntimeError("unreachable")

    def minute_bars(self, symbol: str, *, start: str, end: str) -> list[KlineBar]:
        return self._bars(table="分钟k", symbol=symbol, start=start, end=end)

    def _bars(self, *, table: str, symbol: str, start: str, end: str) -> list[KlineBar]:
        start_date = _parse_date(start)
        end_date = _parse_date(end)
        if start_date > end_date:
            raise ValueError("history start must not be after end")
        rows: list[object] = []
        for year in range(start_date.year, end_date.year + 1):
            rows.extend(self.client.get(table=table, k1=_raw_code(symbol), k2=f"{year}*"))
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


def _row_date(row: dict[str, object]) -> date | None:
    value = row.get("date")
    if value is None:
        return None
    try:
        return _parse_date(str(value))
    except ValueError:
        return None


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


def _research_codes(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return []
    codes = {
        str(code).zfill(6)
        for values in payload.values()
        if isinstance(values, list)
        for code in values
        if _is_research_code(str(code).zfill(6))
    }
    return sorted(codes)


def _is_research_code(code: str) -> bool:
    return len(code) == 6 and code.startswith(
        ("000", "001", "002", "003", "300", "301", "600", "601", "603", "605", "688", "4", "8", "92")
    )


def _normalize_source_row(row: dict[str, object]) -> dict[str, object]:
    normalized = dict(row)
    if "prev_close" not in normalized and "pre_close" in normalized:
        normalized["prev_close"] = normalized["pre_close"]
    return normalized


def _months_between(start: date, end: date) -> list[str]:
    months: list[str] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(f"{year:04d}{month:02d}")
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return months
