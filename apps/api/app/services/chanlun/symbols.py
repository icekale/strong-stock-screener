from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from pypinyin import Style, lazy_pinyin

from app.models import ChanlunSymbolMatch, StrongStockSourceStatus
from app.services.short_term_cache import TtlCache


_SYMBOL_SOURCE = "Akshare 股票代码表"
_EXCHANGES = {"SH", "SZ", "BJ"}


@dataclass(frozen=True)
class _SymbolSearchEntry:
    match: ChanlunSymbolMatch
    full_pinyin: str
    initials: str


def _index_match(match: ChanlunSymbolMatch) -> _SymbolSearchEntry:
    name = match.name.casefold()
    return _SymbolSearchEntry(
        match=match,
        full_pinyin="".join(lazy_pinyin(name, style=Style.NORMAL)).casefold(),
        initials="".join(lazy_pinyin(name, style=Style.FIRST_LETTER)).casefold(),
    )


class ChanlunSymbolSearchService:
    def __init__(
        self,
        *,
        loader: Callable[[], object] | None = None,
        watchlist_loader: Callable[[], object] | None = None,
        latest_screen_loader: Callable[[], object] | None = None,
        cache: TtlCache[tuple[list[_SymbolSearchEntry], StrongStockSourceStatus]] | None = None,
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
        remote_entries, status = self.cache.get_or_set("a-share-symbols", self._load_remote_matches)
        local_matches = [
            *_matches_from_rows(_safe_rows(self.watchlist_loader)),
            *_matches_from_rows(_safe_rows(self.latest_screen_loader)),
        ]
        local_entries = [_index_match(match) for match in local_matches]
        matched = _filter_matches([*local_entries, *remote_entries], query)
        return matched[: max(1, min(limit, 100))], [status]

    def _load_remote_matches(self) -> tuple[list[_SymbolSearchEntry], StrongStockSourceStatus]:
        try:
            matches = _matches_from_rows(_rows_from_loader(self.loader))
            entries = [_index_match(match) for match in matches]
        except Exception as exc:
            return [], StrongStockSourceStatus(
                source=_SYMBOL_SOURCE,
                status="failed",
                detail=f"股票代码表读取失败: {_exception_detail(exc)}",
            )
        return entries, StrongStockSourceStatus(
            source=_SYMBOL_SOURCE,
            status="success",
            detail=f"已缓存 {len(entries)} 只A股代码",
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


def _filter_matches(entries: list[_SymbolSearchEntry], query: str) -> list[ChanlunSymbolMatch]:
    needle = query.strip().casefold()
    if not needle:
        output: list[ChanlunSymbolMatch] = []
        seen: set[str] = set()
        for entry in entries:
            if entry.match.symbol in seen:
                continue
            seen.add(entry.match.symbol)
            output.append(entry.match)
        return output

    ranked: list[tuple[int, str, ChanlunSymbolMatch]] = []
    seen: set[str] = set()
    for entry in entries:
        rank = _match_rank(entry, needle)
        symbol = entry.match.symbol
        if rank is None or symbol in seen:
            continue
        seen.add(symbol)
        ranked.append((rank, symbol, entry.match))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked]


def _match_rank(entry: _SymbolSearchEntry, needle: str) -> int | None:
    symbol = entry.match.symbol.casefold()
    code = symbol.partition(".")[0]
    name = entry.match.name.casefold()
    if needle == symbol or needle == code:
        return 0
    if symbol.startswith(needle) or code.startswith(needle):
        return 1
    if needle == name:
        return 2
    if name.startswith(needle):
        return 3
    if entry.initials.startswith(needle):
        return 4
    if entry.full_pinyin.startswith(needle):
        return 5
    if any(needle in value for value in (symbol, name, entry.initials, entry.full_pinyin)):
        return 6
    return None


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
