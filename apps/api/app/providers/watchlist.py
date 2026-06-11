from __future__ import annotations

from pydantic import BaseModel

from app.providers.thsdk_candidates import normalize_symbol


class WatchlistItem(BaseModel):
    symbol: str
    name: str | None = None


class WatchlistSnapshot(BaseModel):
    items: list[WatchlistItem]


def parse_watchlist_text(content: str) -> list[WatchlistItem]:
    items: list[WatchlistItem] = []
    seen: set[str] = set()
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.replace(",", " ").split()
        symbol = normalize_symbol(parts[0])
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        name = parts[1] if len(parts) > 1 else None
        items.append(WatchlistItem(symbol=symbol, name=name))
    return items
