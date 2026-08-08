from __future__ import annotations

from datetime import datetime
from threading import RLock
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.models import StrongStockDataUnavailable, StrongStockSourceStatus
from app.providers.tdx_minute_history import TdxMinuteHistoryProvider
from app.providers.tickflow import TickFlowIntradayBar

SHANGHAI = ZoneInfo("Asia/Shanghai")
_ULIST_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
# 东财对 push2 的 clist 接口存在间歇性封锁（RemoteProtocolError），延迟源 push2delay
# 返回同样的全A列表（延迟 8-10ms，对涨跌统计/排行足够实时），作为主源不可用时的兜底。
_CLIST_HOSTS = ("https://push2.eastmoney.com", "https://push2delay.eastmoney.com")
_TRENDS_URL = "https://push2his.eastmoney.com/api/qt/stock/trends2/get"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
_QUOTE_FIELDS = "f2,f3,f5,f6,f8,f12,f14,f15,f16,f17,f18"
_A_SHARE_LIST_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
# 东财对 httpx 做间歇性 TLS 指纹封锁（RemoteProtocolError），实时行情统一走 curl_cffi。
_DEFAULT_HTTP_CLIENT = None
_A_SHARE_UNIVERSE = "CN_Equity_A"
_A_SHARE_ROWS_TTL_SECONDS = 300
_ULIST_BATCH_SIZE = 100
_CLIST_PAGE_SIZE = 100
_CLIST_MAX_PAGES = 60
_TRENDS_MAX_DAYS = 5
_SESSION_MINUTES_PER_DAY = 240
_QUOTE_FETCH_RETRIES = 1


class EastmoneyQuote(BaseModel):
    symbol: str
    name: str | None = None
    last_price: float | None = None
    prev_close: float | None = None
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    pct_change: float | None = None
    turnover_rate: float | None = None
    turnover_cny: float | None = None
    volume: float | None = None
    quote_time: str | None = None


class EastmoneyQuoteProvider:
    source_name = "东方财富实时行情"

    def __init__(
        self,
        timeout_seconds: float = 12,
        http_client: object | None = None,
        tdx_client_factory: object | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._owns_client = http_client is None
        if http_client is None:
            from curl_cffi import requests as cffi_requests

            http_client = cffi_requests.Session(impersonate="chrome")
        self.http_client = http_client
        self.tdx_client_factory = tdx_client_factory
        self._a_share_rows_cache: tuple[float, list[dict[str, Any]]] | None = None
        self._a_share_rows_lock = RLock()

    def close(self) -> None:
        if self._owns_client:
            close = getattr(self.http_client, "close", None)
            if callable(close):
                close()

    def status(self) -> StrongStockSourceStatus:
        return StrongStockSourceStatus(
            source=self.source_name,
            status="success",
            detail="push2 实时行情 + push2his 分钟线（免费）",
        )

    def get_quotes(self, symbols: list[str]) -> list[EastmoneyQuote]:
        unique_symbols = _dedupe_symbols(symbols)
        if not unique_symbols:
            return []
        quotes: list[EastmoneyQuote] = []
        for start in range(0, len(unique_symbols), _ULIST_BATCH_SIZE):
            batch = unique_symbols[start : start + _ULIST_BATCH_SIZE]
            secids = [secid for symbol in batch if (secid := _stock_secid(symbol))]
            if not secids:
                continue
            response = self._get(
                _ULIST_URL,
                params={
                    "secids": ",".join(secids),
                    "fields": _QUOTE_FIELDS,
                    "fltt": "2",
                    "invt": "2",
                },
            )
            rows = _extract_diff_rows(response)
            quotes.extend(parse_eastmoney_quote_rows(rows))
        return quotes

    def get_quotes_by_universe(self, universe: str) -> list[EastmoneyQuote]:
        if universe.strip() != _A_SHARE_UNIVERSE:
            raise StrongStockDataUnavailable(f"东方财富实时行情不支持标的池 {universe}")
        rows = self._fetch_a_share_rows()
        return parse_eastmoney_quote_rows(rows)

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        if period != "1m":
            raise StrongStockDataUnavailable("东方财富实时行情仅支持 1 分钟原始线")
        unique_symbols = _dedupe_symbols(symbols)
        if not unique_symbols:
            return {}
        bounded_count = max(1, min(count, 2400))
        output: dict[str, list[TickFlowIntradayBar]] = {}
        for symbol in unique_symbols:
            output[symbol] = self._intraday_bars_for_symbol(symbol, bounded_count)
        return output

    def _intraday_bars_for_symbol(self, symbol: str, count: int) -> list[TickFlowIntradayBar]:
        secid = _stock_secid(symbol)
        if not secid:
            return []
        bars = self._fetch_trends_bars(secid, count)
        if len(bars) < count:
            # 主源（东财分钟线）优先，TDX 仅补更早的历史缺口；时间戳重复时保留主源数据。
            bars = _merge_bars(self._fetch_tdx_fallback(symbol, count), bars)
        return bars[-count:]

    def _fetch_trends_bars(self, secid: str, count: int) -> list[TickFlowIntradayBar]:
        days = max(1, min(_TRENDS_MAX_DAYS, (count + _SESSION_MINUTES_PER_DAY - 1) // _SESSION_MINUTES_PER_DAY))
        response = self._get(
            _TRENDS_URL,
            params={
                "secid": secid,
                "ndays": str(days),
                "iscr": "0",
                "iscca": "0",
                "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            },
        )
        trends = _extract_trends_rows(response)
        return parse_eastmoney_trends(trends)

    def _fetch_tdx_fallback(self, symbol: str, count: int) -> list[TickFlowIntradayBar]:
        if self.tdx_client_factory is None:
            return []
        provider = TdxMinuteHistoryProvider(
            enabled=True,
            timeout_seconds=self.timeout_seconds,
            client_factory=self.tdx_client_factory,
        )
        try:
            return provider.get_minute_bars(symbol, max_bars=count)
        except Exception:
            return []

    def _fetch_a_share_rows(self) -> list[dict[str, Any]]:
        with self._a_share_rows_lock:
            cached = self._a_share_rows_cache
            if cached is not None and monotonic() - cached[0] < _A_SHARE_ROWS_TTL_SECONDS:
                return cached[1]
        rows: list[dict[str, Any]] = []
        total: int | None = None
        consecutive_failures = 0
        for page in range(1, _CLIST_MAX_PAGES + 1):
            page_rows = self._fetch_clist_page(page)
            if page_rows is None:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    break
                continue
            consecutive_failures = 0
            if total is None:
                total = self._fetch_clist_total()
            rows.extend(page_rows)
            if not page_rows or (total is not None and len(rows) >= total):
                break
        if not rows:
            raise StrongStockDataUnavailable("东方财富全A实时列表为空")
        with self._a_share_rows_lock:
            self._a_share_rows_cache = (monotonic(), rows)
        return rows

    def _fetch_clist_page(self, page: int) -> list[dict[str, Any]] | None:
        last_error: Exception | None = None
        for host in _CLIST_HOSTS:
            try:
                response = self._get(
                    f"{host}/api/qt/clist/get",
                    params={
                        "pn": str(page),
                        "pz": str(_CLIST_PAGE_SIZE),
                        "po": "1",
                        "fid": "f3",
                        "np": "1",
                        "fltt": "2",
                        "invt": "2",
                        "fs": _A_SHARE_LIST_FS,
                        "fields": _QUOTE_FIELDS,
                    },
                )
                return _extract_diff_rows(_payload_object(response))
            except Exception as exc:
                last_error = exc
        raise StrongStockDataUnavailable(
            f"东方财富全A列表第 {page} 页失败: {last_error.__class__.__name__}"
        ) from last_error

    def _fetch_clist_total(self) -> int | None:
        for host in _CLIST_HOSTS:
            try:
                response = self._get(
                    f"{host}/api/qt/clist/get",
                    params={
                        "pn": "1",
                        "pz": "1",
                        "po": "1",
                        "fid": "f3",
                        "np": "1",
                        "fltt": "2",
                        "invt": "2",
                        "fs": _A_SHARE_LIST_FS,
                        "fields": "f12",
                    },
                )
                return _extract_total(_payload_object(response))
            except Exception:
                continue
        return None

    def _get(self, url: str, params: dict[str, str]) -> object:
        last_error: Exception | None = None
        for attempt in range(_QUOTE_FETCH_RETRIES + 1):
            try:
                response = self.http_client.get(
                    url,
                    params=params,
                    headers={"User-Agent": _USER_AGENT},
                    timeout=self.timeout_seconds,
                )
                getattr(response, "raise_for_status")()
                return response
            except Exception as exc:
                last_error = exc
        raise StrongStockDataUnavailable(
            f"东方财富请求失败: {last_error.__class__.__name__}" if last_error else "东方财富请求失败"
        ) from last_error


def parse_eastmoney_quote_rows(rows: list[dict[str, Any]]) -> list[EastmoneyQuote]:
    quotes: list[EastmoneyQuote] = []
    for row in rows:
        symbol = _eastmoney_stock_symbol(row.get("f12"))
        if not symbol:
            continue
        pct_change = _optional_float(row.get("f3"))
        quotes.append(
            EastmoneyQuote(
                symbol=symbol,
                name=_optional_str(row.get("f14")),
                last_price=_optional_float(row.get("f2")),
                prev_close=_optional_float(row.get("f18")),
                open_price=_optional_float(row.get("f17")),
                high_price=_optional_float(row.get("f15")),
                low_price=_optional_float(row.get("f16")),
                pct_change=pct_change,
                turnover_rate=_optional_float(row.get("f8")),
                turnover_cny=_optional_float(row.get("f6")),
                volume=_optional_float(row.get("f5")),
                quote_time=datetime.now(SHANGHAI).isoformat(timespec="seconds"),
            )
        )
    return quotes


def parse_eastmoney_trends(trends: list[str]) -> list[TickFlowIntradayBar]:
    bars: list[TickFlowIntradayBar] = []
    for line in trends:
        parts = line.split(",")
        if len(parts) < 8:
            continue
        try:
            timestamp = _trend_timestamp_ms(parts[0])
            open_price = float(parts[1])
            high = float(parts[3])
            low = float(parts[4])
            close = float(parts[2])
            volume = float(parts[5]) * 100  # 手 → 股
            amount = float(parts[6])
        except (TypeError, ValueError, OverflowError, OSError):
            continue
        bars.append(
            TickFlowIntradayBar(
                timestamp=timestamp,
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                amount=amount,
            )
        )
    return bars


def _trend_timestamp_ms(value: str) -> int:
    parsed = datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=SHANGHAI)
    return int(parsed.timestamp() * 1000)


def _merge_bars(*batches: list[TickFlowIntradayBar]) -> list[TickFlowIntradayBar]:
    merged: dict[int, TickFlowIntradayBar] = {}
    for batch in batches:
        for bar in batch:
            merged[bar.timestamp] = bar
    return [merged[timestamp] for timestamp in sorted(merged)]


def _payload_object(response: object) -> object:
    if hasattr(response, "json"):
        return response.json()
    return response


def _extract_diff_rows(payload: object) -> list[dict[str, Any]]:
    data = _payload_data(payload)
    if not isinstance(data, dict):
        return []
    diff = data.get("diff")
    return [row for row in diff if isinstance(row, dict)] if isinstance(diff, list) else []


def _extract_total(payload: object) -> int | None:
    data = _payload_data(payload)
    if not isinstance(data, dict):
        return None
    total = _optional_int(data.get("total"))
    return total if total and total > 0 else None


def _extract_trends_rows(payload: object) -> list[str]:
    data = _payload_data(payload)
    if not isinstance(data, dict):
        return []
    trends = data.get("trends")
    return [str(line) for line in trends if isinstance(line, str)] if isinstance(trends, list) else []


def _payload_data(payload: object) -> object:
    if isinstance(payload, dict):
        return payload.get("data")
    try:
        value = payload.json()
    except Exception:
        return None
    return value.get("data") if isinstance(value, dict) else None


def _stock_secid(symbol: str) -> str:
    text = symbol.strip().upper()
    if "." in text:
        code, exchange = text.split(".", 1)
    else:
        code, exchange = text, ""
    if len(code) != 6 or not code.isdigit():
        return ""
    if exchange in {"SZ", "BJ"}:
        return f"0.{code}"
    if exchange == "SH":
        return f"1.{code}"
    if code.startswith("92"):
        return f"0.{code}"
    if code.startswith(("6", "9")):
        return f"1.{code}"
    return f"0.{code}"


def _eastmoney_stock_symbol(value: object) -> str:
    code = str(value or "").strip()
    if len(code) != 6 or not code.isdigit():
        return ""
    if code.startswith("92"):
        return f"{code}.BJ"
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return ""


def _dedupe_symbols(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for symbol in symbols:
        normalized = (symbol or "").strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def _optional_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _optional_int(value: object) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
