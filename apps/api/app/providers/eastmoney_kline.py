"""东方财富免费日K provider。

直接封装东财 push2his kline 接口（与 market_overview/heatmap 的东财调用风格一致），
用于替代收费 TickFlow 的日K能力。免费、无需 key、前复权/不复权双口径。

注意：东财对该接口做了 TLS 指纹封锁，httpx 会被直接断连（RemoteProtocolError）；
因此默认 HTTP 客户端使用 curl_cffi（模拟浏览器 TLS 指纹）。调用方可通过
http_client 注入自定义客户端（测试用 Fake 客户端保持 .get()/.json() 契约）。

契约对齐 TickFlowDailyKlineProvider.get_klines：
- 返回 list[KlineBar]，date 为 YYYY-MM-DD（上海时区）
- volume 单位为股（东财返回手，×100 对齐 tickflow）
- amount 单位为元
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from curl_cffi import requests as cffi_requests

from app.models import KlineBar, StrongStockDataUnavailable, StrongStockSourceStatus

logger = logging.getLogger(__name__)

EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
# 东财接口需要 ut 参数（akshare 同款），缺失会返回 rc=102。
_EASTMONEY_UT = "fa5fd1943c7b386f172d6893dbfba10b"
# 日历日 ≈ 交易日 × 1.4；用 ×2 的安全系数保证任意 count 都能取满最近 N 根。
_CALENDAR_DAY_FACTOR = 2
_MAX_BACKFILL_DAYS = 2200  # 足够覆盖情绪分位的 1020 根日K


class EastmoneyKlineProvider:
    source_name = "东方财富日K"

    def __init__(
        self,
        timeout_seconds: float = 12,
        adjust: str = "forward",
        http_client: object | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.adjust = adjust
        self._owns_client = http_client is None
        self.http_client = http_client or cffi_requests.Session(impersonate="chrome")

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        if count <= 0:
            raise StrongStockDataUnavailable("K线数量必须为正数")
        secid = _to_secid(symbol)
        if secid is None:
            raise StrongStockDataUnavailable(f"无法解析证券代码: {symbol}")
        start_date = (
            date.today() - timedelta(days=min(count * _CALENDAR_DAY_FACTOR, _MAX_BACKFILL_DAYS))
        ).strftime("%Y%m%d")
        end_date = date.today().strftime("%Y%m%d")

        try:
            response = self._fetch_with_retry(secid, start_date, end_date)
            payload = response.json()
        except Exception as exc:
            raise StrongStockDataUnavailable(f"东方财富日K获取失败: {exc.__class__.__name__}") from exc

        bars = _parse_kline_payload(payload)
        if not bars:
            raise StrongStockDataUnavailable(f"东方财富日K为空: {symbol}")
        return bars[-count:]

    def _fetch_with_retry(self, secid: str, start_date: str, end_date: str, attempts: int = 2):
        """东财接口偶发 TLS 指纹断连（curl_cffi 首连可能被重置），重试一次。"""
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = self.http_client.get(
                    EASTMONEY_KLINE_URL,
                    params={
                        "secid": secid,
                        "ut": _EASTMONEY_UT,
                        "fields1": "f1,f2,f3,f4,f5,f6",
                        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                        "klt": "101",
                        "fqt": "1" if self.adjust == "forward" else "0",
                        "beg": start_date,
                        "end": end_date,
                    },
                    headers={"User-Agent": _USER_AGENT},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                return response
            except Exception as exc:
                last_error = exc
                if attempt < attempts - 1:
                    logger.warning("东方财富日K请求失败（第%d次）: %s", attempt + 1, exc.__class__.__name__)
        raise last_error if last_error is not None else RuntimeError("unreachable")

    def status(self) -> StrongStockSourceStatus:
        return StrongStockSourceStatus(
            source=self.source_name,
            status="success",
            detail="东方财富日K接口已配置（免费，无需 key）",
        )


def _to_secid(symbol: str) -> str | None:
    """股票代码 → 东财 secid（1=沪/0=深京）。"""
    text = symbol.strip().upper()
    if "." in text:
        code, exchange = text.split(".", 1)
    else:
        code, exchange = text, ""
    if not code.isdigit() or len(code) != 6:
        return None
    if exchange == "SH" or (code.startswith(("6", "9")) and not code.startswith("92")):
        return f"1.{code}"
    return f"0.{code}"


def _parse_kline_payload(payload: object) -> list[KlineBar]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    raw_rows = data.get("klines")
    if not isinstance(raw_rows, list):
        return []
    bars: list[KlineBar] = []
    for raw in raw_rows:
        if not isinstance(raw, str):
            continue
        parts = raw.split(",")
        if len(parts) < 7:
            continue
        try:
            close = float(parts[2])
        except (TypeError, ValueError):
            continue
        if close <= 0:
            continue
        bars.append(
            KlineBar(
                date=parts[0],
                open=float(parts[1]),
                close=close,
                high=float(parts[3]),
                low=float(parts[4]),
                # 东财成交量单位为手（1手=100股），×100 对齐 tickflow 的股单位。
                volume=float(parts[5]) * 100,
                amount=float(parts[6]),
            )
        )
    return bars
