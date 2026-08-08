from __future__ import annotations

import httpx

from app.models import KlineBar, StrongStockDataUnavailable, StrongStockSourceStatus


class TencentDailyKlineProvider:
    """腾讯免费日K：push2his（东财日K）被 IP 级 TLS 封锁时的兜底源。

    前复权走 fqkline/get（qfqday，约 800 根，不限近期），不复权走 kline/kline
    （day，chanlun 需不复权口径）。腾讯不受东财 TLS 指纹封锁影响。
    """

    source_name = "腾讯日K"

    def __init__(
        self,
        timeout_seconds: float = 12,
        adjust: str = "forward",
        http_client: object | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.adjust = adjust
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client()

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    def status(self) -> StrongStockSourceStatus:
        return StrongStockSourceStatus(
            source=self.source_name,
            status="success",
            detail=f"web.ifzq.gtimg.cn 日K，adjust={self.adjust}",
        )

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        code = _tencent_kline_symbol(symbol)
        if not code:
            return []
        try:
            if self.adjust == "forward":
                response = self.http_client.get(
                    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
                    params={"param": f"{code},day,,,{count},qfq"},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                rows = _extract_kline_rows(response.json(), code, "qfqday")
            else:
                response = self.http_client.get(
                    "https://web.ifzq.gtimg.cn/appstock/app/kline/kline",
                    params={"param": f"{code},day,,,{count}"},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                rows = _extract_kline_rows(response.json(), code, "day")
            return [_kline_from_row(row) for row in rows][-count:]
        except StrongStockDataUnavailable:
            raise
        except httpx.HTTPStatusError as exc:
            raise StrongStockDataUnavailable(
                f"腾讯日K请求失败: HTTP {exc.response.status_code}"
            ) from exc
        except Exception as exc:
            raise StrongStockDataUnavailable(
                f"腾讯日K请求失败: {exc.__class__.__name__}"
            ) from exc


def _extract_kline_rows(payload: object, code: str, key: str) -> list[list[object]]:
    if not isinstance(payload, dict):
        raise StrongStockDataUnavailable("腾讯日K响应结构异常")
    node = payload.get("data", {}).get(code, {})
    if not isinstance(node, dict):
        raise StrongStockDataUnavailable("腾讯日K响应缺少标的节点")
    rows = node.get(key)
    if not isinstance(rows, list):
        raise StrongStockDataUnavailable("腾讯日K响应缺少K线列表")
    return [row for row in rows if isinstance(row, list)]


def _kline_from_row(row: list[object]) -> KlineBar:
    # 腾讯行字段：日期, 开盘, 收盘, 最高, 最低, 成交量(手)
    if len(row) < 6:
        raise StrongStockDataUnavailable("腾讯日K行字段不足")
    close = float(row[2])
    if close <= 0:
        raise StrongStockDataUnavailable("腾讯日K收盘价异常")
    return KlineBar(
        date=str(row[0]),
        open=float(row[1]),
        high=float(row[3]),
        low=float(row[4]),
        close=close,
        volume=float(row[5]) * 100,  # 手 → 股
        amount=None,
    )


def _tencent_kline_symbol(symbol: str) -> str:
    text = symbol.strip().upper()
    if "." in text:
        code, suffix = text.split(".", 1)
        prefix = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(suffix)
        if prefix and len(code) == 6 and code.isdigit():
            return f"{prefix}{code}"
        return ""
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) != 6:
        return ""
    if digits.startswith(("6", "9")):
        return f"sh{digits}"
    if digits.startswith(("4", "8", "92")):
        return f"bj{digits}"
    return f"sz{digits}"
