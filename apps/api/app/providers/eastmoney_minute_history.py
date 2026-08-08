from __future__ import annotations

from app.models import StrongStockDataUnavailable
from app.providers.eastmoney_quote import EastmoneyQuoteProvider
from app.providers.tickflow import TickFlowIntradayBar


class EastmoneyMinuteHistoryProvider:
    """chanlun 分钟历史补齐：东财趋势接口（近 5 天，免费直连）主源 + 通达信补缺。

    免费分钟历史深度上限为东财 trends2 的 ndays=5（约 1200 分钟/5 交易日）；
    更早缺口由 TDX 公共源（仅保近 5-8 日）尽力补齐，两者按时间戳合并去重、
    主源数据优先。
    """

    source_name = "东方财富分钟历史，通达信分钟历史 fallback"

    def __init__(
        self,
        *,
        enabled: bool,
        timeout_seconds: float,
        tdx_client_factory: object | None = None,
        quote_provider: object | None = None,
    ) -> None:
        # enabled 控制 TDX 补缺是否启用（chanlun_tdx_enabled）；东财主源免费直连始终可用。
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.tdx_client_factory = tdx_client_factory if enabled else None
        self.quote_provider = quote_provider or EastmoneyQuoteProvider(
            timeout_seconds=timeout_seconds,
            tdx_client_factory=self.tdx_client_factory,
        )

    def get_minute_bars(self, symbol: str, *, max_bars: int) -> list[TickFlowIntradayBar]:
        if max_bars <= 0:
            return []
        normalized_symbol = symbol.strip().upper()
        bars = self.quote_provider.get_intraday_bars(
            [normalized_symbol],
            period="1m",
            count=max_bars,
        ).get(normalized_symbol, [])
        if not bars:
            raise StrongStockDataUnavailable(
                f"东财分钟历史未返回 {normalized_symbol} 分钟线"
            )
        return bars

    def close(self) -> None:
        close = getattr(self.quote_provider, "close", None)
        if callable(close):
            close()
