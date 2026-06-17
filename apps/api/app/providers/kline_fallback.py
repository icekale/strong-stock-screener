from __future__ import annotations

from app.models import KlineBar


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
        except Exception:
            return self.fallback.get_klines(symbol, count=count)
