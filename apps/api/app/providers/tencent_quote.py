from __future__ import annotations

import httpx
from pydantic import BaseModel

from app.models import StrongStockDataUnavailable, StrongStockSourceStatus


class TencentQuote(BaseModel):
    symbol: str
    name: str | None = None
    price: float | None = None
    total_market_cap_cny: float | None = None
    circulating_market_cap_cny: float | None = None
    pe_ttm: float | None = None
    pe_static: float | None = None
    pb: float | None = None


class TencentQuoteProvider:
    source_name = "腾讯财经"

    def __init__(self, timeout_seconds: float = 10, http_client: object | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client()

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    def status(self) -> StrongStockSourceStatus:
        return StrongStockSourceStatus(
            source=self.source_name,
            status="success",
            detail="qt.gtimg.cn 实时估值",
        )

    def get_quotes(self, symbols: list[str]) -> list[TencentQuote]:
        prefixed = [_tencent_symbol(symbol) for symbol in symbols if _tencent_symbol(symbol)]
        if not prefixed:
            return []
        try:
            response = self.http_client.get(
                "https://qt.gtimg.cn/q=" + ",".join(prefixed),
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            content = getattr(response, "content", None)
            if isinstance(content, bytes):
                text = content.decode("gbk", errors="ignore")
            else:
                text = getattr(response, "text", "")
            return parse_tencent_quote_payload(text)
        except StrongStockDataUnavailable:
            raise
        except httpx.HTTPStatusError as exc:
            raise StrongStockDataUnavailable(
                f"腾讯财经请求失败: HTTP {exc.response.status_code}"
            ) from exc
        except Exception as exc:
            raise StrongStockDataUnavailable(f"腾讯财经请求失败: {exc.__class__.__name__}") from exc


def parse_tencent_quote_payload(payload: str) -> list[TencentQuote]:
    quotes: list[TencentQuote] = []
    for line in payload.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=", 1)[0].split("_")[-1]
        values = line.split('"', 2)[1].split("~")
        if len(values) < 53:
            continue
        symbol = _symbol_from_tencent_key(key)
        if not symbol:
            continue
        quotes.append(
            TencentQuote(
                symbol=symbol,
                name=values[1] or None,
                price=_float_or_none(values[3]),
                total_market_cap_cny=_yi_to_cny(values[44]),
                circulating_market_cap_cny=_yi_to_cny(values[45]),
                pe_ttm=_float_or_none(values[39]),
                pe_static=_float_or_none(values[52]),
                pb=_float_or_none(values[46]),
            )
        )
    return quotes


def _tencent_symbol(symbol: str) -> str:
    text = symbol.strip().lower()
    if not text:
        return ""
    if "." in text:
        code, suffix = text.split(".", 1)
        if suffix == "sh":
            return f"sh{code}"
        if suffix == "sz":
            return f"sz{code}"
        if suffix == "bj":
            return f"bj{code}"
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) != 6:
        return ""
    if digits.startswith(("6", "9")):
        return f"sh{digits}"
    if digits.startswith(("4", "8")):
        return f"bj{digits}"
    return f"sz{digits}"


def _symbol_from_tencent_key(key: str) -> str:
    text = key.strip().lower()
    if len(text) != 8:
        return ""
    prefix = text[:2]
    code = text[2:]
    if not code.isdigit():
        return ""
    if prefix == "sh":
        return f"{code}.SH"
    if prefix == "sz":
        return f"{code}.SZ"
    if prefix == "bj":
        return f"{code}.BJ"
    return ""


def _float_or_none(value: str) -> float | None:
    text = str(value or "").strip()
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _yi_to_cny(value: str) -> float | None:
    number = _float_or_none(value)
    if number is None:
        return None
    return round(number * 100_000_000, 2)
