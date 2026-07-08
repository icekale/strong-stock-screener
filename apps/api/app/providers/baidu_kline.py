from __future__ import annotations

from typing import Any

import httpx

from app.models import KlineBar


BAIDU_KLINE_URL = "https://finance.pae.baidu.com/selfselect/getstockquotation"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0 Safari/537.36"


class BaiduKlineProvider:
    source_name = "百度股市通K线"

    def __init__(
        self,
        timeout_seconds: float = 12,
        http_client: object | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client()

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        response = self.http_client.get(
            BAIDU_KLINE_URL,
            headers={
                "User-Agent": UA,
                "Accept": "application/vnd.finance-web.v1+json",
                "Origin": "https://gushitong.baidu.com",
                "Referer": "https://gushitong.baidu.com/",
            },
            params={
                "all": "1",
                "isIndex": "false",
                "isBk": "false",
                "isBlock": "false",
                "isFutures": "false",
                "isStock": "true",
                "newFormat": "1",
                "group": "quotation_kline_ab",
                "finClientType": "pc",
                "code": symbol.strip().split(".", 1)[0],
                "ktype": "1",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return parse_baidu_kline_payload(response.json())[-count:]


def parse_baidu_kline_payload(payload: dict[str, Any]) -> list[KlineBar]:
    market_data = payload.get("Result", {}).get("newMarketData", {})
    keys = market_data.get("keys", [])
    raw_rows = str(market_data.get("marketData") or "").split(";")
    bars: list[KlineBar] = []
    for raw in raw_rows:
        values = raw.split(",")
        if len(values) < len(keys) or not raw.strip():
            continue
        item = dict(zip(keys, values, strict=False))
        bar = KlineBar(
            date=str(item.get("time") or ""),
            open=_float(item.get("open")) or 0.0,
            close=_float(item.get("close")) or 0.0,
            high=_float(item.get("high")) or 0.0,
            low=_float(item.get("low")) or 0.0,
            volume=_float(item.get("volume")) or 0.0,
            amount=_float(item.get("amount")),
            ma5=_float(item.get("ma5avgprice")),
            ma10=_float(item.get("ma10avgprice")),
            ma20=_float(item.get("ma20avgprice")),
        )
        if bar.date and bar.close > 0:
            bars.append(bar)
    return bars


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
