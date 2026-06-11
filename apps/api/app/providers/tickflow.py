from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from app.models import StrongStockDataUnavailable, StrongStockSourceStatus


class TickFlowQuote(BaseModel):
    symbol: str
    name: str | None = None
    last_price: float | None = None
    pct_change: float | None = None
    turnover_cny: float | None = None
    volume: float | None = None
    quote_time: str | None = None


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
                detail="TICKFLOW_API_KEY 未配置",
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
            raise StrongStockDataUnavailable("TICKFLOW_API_KEY 未配置")
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
        except Exception as exc:
            raise StrongStockDataUnavailable(f"TickFlow 请求失败: {exc.__class__.__name__}") from exc


def parse_tickflow_quote_payload(payload: object) -> list[TickFlowQuote]:
    return [_quote_from_item(item) for item in _extract_items(payload)]


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
        item.get("pct_change")
        or item.get("change_percent")
        or item.get("percent")
        or ext_item.get("change_pct")
    )
    if pct_change is not None and abs(pct_change) <= 1:
        pct_change *= 100
    if pct_change is not None:
        pct_change = round(pct_change, 4)
    return TickFlowQuote(
        symbol=symbol,
        name=_optional_str(item.get("name") or ext_item.get("name")),
        last_price=_optional_float(item.get("last_price") or item.get("price") or item.get("last")),
        pct_change=pct_change,
        turnover_cny=_optional_float(item.get("turnover_cny") or item.get("turnover") or item.get("amount")),
        volume=_optional_float(item.get("volume")),
        quote_time=_optional_str(item.get("quote_time") or item.get("time") or item.get("timestamp")),
    )


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
