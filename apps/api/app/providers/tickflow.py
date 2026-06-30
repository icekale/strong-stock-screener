from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel

from app.models import KlineBar, StrongStockDataUnavailable, StrongStockSourceStatus


class TickFlowQuote(BaseModel):
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


class TickFlowIntradayBar(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    prev_close: float | None = None


class TickFlowDailyKlineProvider:
    source_name = "TickFlow 日K"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout_seconds: float = 12,
        adjust: str = "forward",
        http_client: object | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.adjust = adjust
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client()

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    def status(self) -> StrongStockSourceStatus:
        if not self.api_key:
            return StrongStockSourceStatus(
                source=self.source_name,
                status="missing_key",
                detail="STRONG_STOCK_TICKFLOW_API_KEY 或 TICKFLOW_API_KEY 未配置",
            )
        return StrongStockSourceStatus(
            source=self.source_name,
            status="success",
            detail=f"base_url={self.base_url}, period=1d, adjust={self.adjust}",
        )

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        if not self.api_key:
            raise StrongStockDataUnavailable("STRONG_STOCK_TICKFLOW_API_KEY 或 TICKFLOW_API_KEY 未配置")
        try:
            response = self.http_client.get(
                f"{self.base_url}/v1/klines",
                headers={"x-api-key": self.api_key},
                params={
                    "symbol": symbol,
                    "period": "1d",
                    "count": count,
                    "adjust": self.adjust,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return parse_tickflow_kline_payload(response.json())[-count:]
        except StrongStockDataUnavailable:
            raise
        except httpx.HTTPStatusError as exc:
            raise StrongStockDataUnavailable(
                f"TickFlow 日K请求失败: HTTP {exc.response.status_code}"
            ) from exc
        except Exception as exc:
            raise StrongStockDataUnavailable(f"TickFlow 日K请求失败: {exc.__class__.__name__}") from exc


class TickFlowQuoteProvider:
    source_name = "TickFlow"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout_seconds: float = 12,
        http_client: object | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client()

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    def status(self) -> StrongStockSourceStatus:
        if not self.api_key:
            return StrongStockSourceStatus(
                source=self.source_name,
                status="missing_key",
                detail="STRONG_STOCK_TICKFLOW_API_KEY 或 TICKFLOW_API_KEY 未配置",
            )
        return StrongStockSourceStatus(
            source=self.source_name,
            status="success",
            detail=f"base_url={self.base_url}",
        )

    def get_quotes(self, symbols: list[str]) -> list[TickFlowQuote]:
        if not symbols:
            return []
        if not self.api_key:
            raise StrongStockDataUnavailable("STRONG_STOCK_TICKFLOW_API_KEY 或 TICKFLOW_API_KEY 未配置")
        try:
            response = self.http_client.post(
                f"{self.base_url}/v1/quotes",
                headers={"x-api-key": self.api_key},
                json={"symbols": symbols},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return parse_tickflow_quote_payload(response.json())
        except StrongStockDataUnavailable:
            raise
        except httpx.HTTPStatusError as exc:
            raise StrongStockDataUnavailable(
                f"TickFlow 请求失败: HTTP {exc.response.status_code}"
            ) from exc
        except Exception as exc:
            raise StrongStockDataUnavailable(f"TickFlow 请求失败: {exc.__class__.__name__}") from exc

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        if not symbols:
            return {}
        if not self.api_key:
            raise StrongStockDataUnavailable("STRONG_STOCK_TICKFLOW_API_KEY 或 TICKFLOW_API_KEY 未配置")
        unique_symbols = _dedupe_symbols(symbols)
        try:
            return self._get_intraday_bars_batch(unique_symbols, period=period, count=count)
        except StrongStockDataUnavailable:
            raise
        except httpx.HTTPStatusError as exc:
            code = _payload_code(exc.response)
            if exc.response.status_code == 403 and "NO_INTRADAY_BATCH_PERMISSION" in code:
                return self._get_intraday_bars_one_by_one(unique_symbols, period=period, count=count)
            raise StrongStockDataUnavailable(
                f"TickFlow 分钟线请求失败: HTTP {exc.response.status_code}"
            ) from exc
        except Exception as exc:
            raise StrongStockDataUnavailable(f"TickFlow 分钟线请求失败: {exc.__class__.__name__}") from exc

    def _get_intraday_bars_batch(
        self,
        symbols: list[str],
        period: str,
        count: int,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        response = self.http_client.get(
            f"{self.base_url}/v1/klines/intraday/batch",
            headers={"x-api-key": self.api_key},
            params={
                "symbols": ",".join(symbols),
                "period": period,
                "count": count,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return parse_tickflow_intraday_payload(response.json())

    def _get_intraday_bars_one_by_one(
        self,
        symbols: list[str],
        period: str,
        count: int,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        bars_by_symbol: dict[str, list[TickFlowIntradayBar]] = {}
        for symbol in symbols:
            response = self.http_client.get(
                f"{self.base_url}/v1/klines/intraday",
                headers={"x-api-key": self.api_key},
                params={
                    "symbol": symbol,
                    "period": period,
                    "count": count,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            bars_by_symbol[symbol] = parse_tickflow_intraday_bars(response.json())
        return bars_by_symbol


def parse_tickflow_quote_payload(payload: object) -> list[TickFlowQuote]:
    return [_quote_from_item(item) for item in _extract_items(payload)]


def parse_tickflow_intraday_payload(payload: object) -> dict[str, list[TickFlowIntradayBar]]:
    if isinstance(payload, dict) and "data" in payload:
        data = payload["data"]
    else:
        data = payload
    if not isinstance(data, dict):
        raise StrongStockDataUnavailable("TickFlow 分钟线响应结构异常")
    return {
        str(symbol): _intraday_bars_from_item(item)
        for symbol, item in data.items()
        if isinstance(item, (dict, list))
    }


def parse_tickflow_intraday_bars(payload: object) -> list[TickFlowIntradayBar]:
    if isinstance(payload, dict) and "data" in payload:
        data = payload["data"]
    else:
        data = payload
    if not isinstance(data, (dict, list)):
        raise StrongStockDataUnavailable("TickFlow 分钟线响应结构异常")
    return _intraday_bars_from_item(data)


def parse_tickflow_kline_payload(payload: object) -> list[KlineBar]:
    if isinstance(payload, dict) and "data" in payload:
        data = payload["data"]
    else:
        data = payload
    if not isinstance(data, dict):
        raise StrongStockDataUnavailable("TickFlow K线响应结构异常")

    required_names = ["timestamp", "open", "high", "low", "close", "volume"]
    columns = {name: data.get(name) for name in required_names}
    if not all(isinstance(value, list) for value in columns.values()):
        raise StrongStockDataUnavailable("TickFlow K线响应缺少列式数据")

    lengths = {len(value) for value in columns.values() if isinstance(value, list)}
    if len(lengths) != 1:
        raise StrongStockDataUnavailable("TickFlow K线列长度不一致")

    bars: list[KlineBar] = []
    for index in range(lengths.pop() if lengths else 0):
        close = float(columns["close"][index])
        if close <= 0:
            continue
        bars.append(
            KlineBar(
                date=_date_from_timestamp_ms(int(columns["timestamp"][index])),
                open=float(columns["open"][index]),
                high=float(columns["high"][index]),
                low=float(columns["low"][index]),
                close=close,
                volume=float(columns["volume"][index]),
            )
        )
    return bars


def _extract_items(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if "data" in payload:
            data = payload["data"]
        elif "items" in payload:
            data = payload["items"]
        else:
            data = payload.get("results")
    else:
        data = payload
    if not isinstance(data, list):
        raise StrongStockDataUnavailable("TickFlow 响应结构异常")
    return [item for item in data if isinstance(item, dict)]


def _quote_from_item(item: dict[str, Any]) -> TickFlowQuote:
    symbol = str(item.get("symbol") or item.get("ticker") or item.get("code") or "")
    if not symbol:
        raise StrongStockDataUnavailable("TickFlow 响应缺少 symbol")
    ext = item.get("ext")
    ext_item = ext if isinstance(ext, dict) else {}
    pct_change = _optional_float(
        _first_present(
            item.get("pct_change"),
            item.get("change_percent"),
            item.get("percent"),
            ext_item.get("change_pct"),
        )
    )
    if pct_change is not None and abs(pct_change) <= 1:
        pct_change *= 100
    if pct_change is not None:
        pct_change = round(pct_change, 4)
    turnover_rate = _optional_float(
        _first_present(
            item.get("turnover_rate"),
            item.get("turnoverRate"),
            item.get("turnover_ratio"),
            item.get("turnoverRatio"),
            ext_item.get("turnover_rate"),
            ext_item.get("turnoverRate"),
        )
    )
    if turnover_rate is not None and abs(turnover_rate) <= 1:
        turnover_rate *= 100
    if turnover_rate is not None:
        turnover_rate = round(turnover_rate, 4)
    return TickFlowQuote(
        symbol=symbol,
        name=_optional_str(_first_present(item.get("name"), ext_item.get("name"))),
        last_price=_optional_float(_first_present(item.get("last_price"), item.get("price"), item.get("last"))),
        prev_close=_optional_float(item.get("prev_close")),
        open_price=_optional_float(_first_present(item.get("open"), item.get("open_price"))),
        high_price=_optional_float(_first_present(item.get("high"), item.get("high_price"))),
        low_price=_optional_float(_first_present(item.get("low"), item.get("low_price"))),
        pct_change=pct_change,
        turnover_rate=turnover_rate,
        turnover_cny=_optional_float(_first_present(item.get("turnover_cny"), item.get("turnover"), item.get("amount"))),
        volume=_optional_float(item.get("volume")),
        quote_time=_optional_str(_first_present(item.get("quote_time"), item.get("time"), item.get("timestamp"))),
    )


def _intraday_bars_from_item(item: dict[str, Any] | list[object]) -> list[TickFlowIntradayBar]:
    if isinstance(item, list):
        return [_intraday_bar_from_row(row) for row in item if isinstance(row, dict)]

    required_names = ["timestamp", "open", "high", "low", "close", "volume", "amount"]
    columns = {name: item.get(name) for name in required_names}
    if not all(isinstance(value, list) for value in columns.values()):
        raise StrongStockDataUnavailable("TickFlow 分钟线响应缺少列式数据")

    lengths = {len(value) for value in columns.values() if isinstance(value, list)}
    prev_close = item.get("prev_close")
    if isinstance(prev_close, list):
        lengths.add(len(prev_close))
    if len(lengths) != 1:
        raise StrongStockDataUnavailable("TickFlow 分钟线列长度不一致")

    rows: list[TickFlowIntradayBar] = []
    for index in range(lengths.pop() if lengths else 0):
        rows.append(
            TickFlowIntradayBar(
                timestamp=int(columns["timestamp"][index]),
                open=float(columns["open"][index]),
                high=float(columns["high"][index]),
                low=float(columns["low"][index]),
                close=float(columns["close"][index]),
                volume=float(columns["volume"][index]),
                amount=float(columns["amount"][index]),
                prev_close=(
                    float(prev_close[index])
                    if isinstance(prev_close, list) and prev_close[index] is not None
                    else None
                ),
            )
        )
    return rows


def _intraday_bar_from_row(row: dict[str, Any]) -> TickFlowIntradayBar:
    return TickFlowIntradayBar(
        timestamp=int(row["timestamp"]),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=float(row["volume"]),
        amount=float(row.get("amount", 0)),
        prev_close=_optional_float(row.get("prev_close")),
    )


def _date_from_timestamp_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000).strftime("%Y%m%d")


def _first_present(*values: object) -> object | None:
    for value in values:
        if value is not None:
            return value
    return None


def _dedupe_symbols(symbols: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def _payload_code(response: object) -> str:
    try:
        payload = response.json()
    except Exception:
        return ""
    if isinstance(payload, dict):
        return str(payload.get("code") or payload.get("error") or "")
    return ""


def _optional_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
