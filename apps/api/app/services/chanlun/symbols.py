from __future__ import annotations

import re
from collections.abc import Callable, Mapping

from app.models import ChanlunSymbolMatch, StrongStockSourceStatus
from app.services.short_term_cache import TtlCache


_SYMBOL_SOURCE = "Akshare 股票代码表"
_EXCHANGES = {"SH", "SZ", "BJ"}


class ChanlunSymbolSearchService:
    def __init__(
        self,
        *,
        loader: Callable[[], object] | None = None,
        watchlist_loader: Callable[[], object] | None = None,
        latest_screen_loader: Callable[[], object] | None = None,
        cache: TtlCache[tuple[list[ChanlunSymbolMatch], StrongStockSourceStatus]] | None = None,
    ) -> None:
        self.loader = loader or _load_akshare_symbols
        self.watchlist_loader = watchlist_loader or (lambda: [])
        self.latest_screen_loader = latest_screen_loader or (lambda: [])
        self.cache = cache or TtlCache(ttl_seconds=24 * 60 * 60, name="chanlun_symbols")

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
    ) -> tuple[list[ChanlunSymbolMatch], list[StrongStockSourceStatus]]:
        remote_matches, status = self.cache.get_or_set("a-share-symbols", self._load_remote_matches)
        local_matches = [
            *_matches_from_rows(_safe_rows(self.watchlist_loader)),
            *_matches_from_rows(_safe_rows(self.latest_screen_loader)),
        ]
        matched = _filter_matches([*local_matches, *remote_matches], query)
        return matched[: max(1, min(limit, 100))], [status]

    def _load_remote_matches(self) -> tuple[list[ChanlunSymbolMatch], StrongStockSourceStatus]:
        try:
            matches = _matches_from_rows(_rows_from_loader(self.loader))
        except Exception as exc:
            return [], StrongStockSourceStatus(
                source=_SYMBOL_SOURCE,
                status="failed",
                detail=f"股票代码表读取失败: {_exception_detail(exc)}",
            )
        return matches, StrongStockSourceStatus(
            source=_SYMBOL_SOURCE,
            status="success",
            detail=f"已缓存 {len(matches)} 只A股代码",
        )


def normalize_chanlun_symbol(value: str) -> str:
    text = value.strip().upper()
    if not text:
        return ""
    code, separator, exchange = text.partition(".")
    code = re.sub(r"\D", "", code)
    if len(code) != 6:
        return ""
    if separator and exchange in _EXCHANGES:
        return f"{code}.{exchange}"
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return f"{code}.SZ"


def _load_akshare_symbols() -> object:
    import akshare

    return akshare.stock_info_a_code_name()


def _safe_rows(loader: Callable[[], object]) -> list[object]:
    try:
        return _rows_from_loader(loader)
    except Exception:
        return []


def _rows_from_loader(loader: Callable[[], object]) -> list[object]:
    value = loader()
    if isinstance(value, list):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            rows = to_dict(orient="records")
        except TypeError:
            rows = to_dict("records")
        return rows if isinstance(rows, list) else []
    return []


def _matches_from_rows(rows: list[object]) -> list[ChanlunSymbolMatch]:
    matches: list[ChanlunSymbolMatch] = []
    for row in rows:
        code = _row_value(row, "symbol", "code", "代码", "证券代码")
        name = _row_value(row, "name", "名称", "证券简称", "股票简称")
        symbol = normalize_chanlun_symbol(code)
        if symbol:
            matches.append(ChanlunSymbolMatch(symbol=symbol, name=name or symbol))
    return matches


def _filter_matches(matches: list[ChanlunSymbolMatch], query: str) -> list[ChanlunSymbolMatch]:
    needle = query.strip().casefold()
    output: list[ChanlunSymbolMatch] = []
    seen: set[str] = set()
    for match in matches:
        if match.symbol in seen:
            continue
        if needle and needle not in match.symbol.casefold() and needle not in match.name.casefold():
            continue
        seen.add(match.symbol)
        output.append(match)
    return output


def _row_value(row: object, *names: str) -> str:
    if isinstance(row, Mapping):
        for name in names:
            value = row.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""
    for name in names:
        value = getattr(row, name, None)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _exception_detail(exc: Exception) -> str:
    message = str(exc).strip()
    return f"{exc.__class__.__name__}: {message}" if message else exc.__class__.__name__
