from __future__ import annotations

import logging

from app.models import KlineBar

logger = logging.getLogger(__name__)


class FallbackKlineProvider:
    def __init__(self, primary: object, fallback: object) -> None:
        self.primary = primary
        self.fallback = fallback
        self.source_name = (
            f"{getattr(primary, 'source_name', 'primary')}，"
            f"{getattr(fallback, 'source_name', 'fallback')} fallback"
        )

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        try:
            return self.primary.get_klines(symbol, count=count)
        except Exception as exc:
            # 记录主源失败原因，避免把主源的真实 bug（如解析错误）静默掩盖成 fallback 数据。
            logger.warning(
                "kline fallback: primary %s failed for %s (%s): %s",
                getattr(self.primary, "source_name", "primary"),
                symbol,
                type(exc).__name__,
                exc,
            )
            return self.fallback.get_klines(symbol, count=count)
