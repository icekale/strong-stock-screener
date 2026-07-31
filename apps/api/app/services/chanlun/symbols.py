from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import httpx
from pypinyin import Style, lazy_pinyin

from app.models import ChanlunSymbolMatch, StrongStockSourceStatus
from app.services.short_term_cache import TtlCache


_SYMBOL_SOURCE = "A股证券代码主表"
_EXCHANGES = {"SH", "SZ", "BJ"}
_TDX_TIMEOUT_SECONDS = 5.0
_BSE_TIMEOUT_SECONDS = 5.0
_BSE_URL = "https://www.bse.cn/nqxxController/nqxxCnzq.do"
_BSE_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
)
_BSE_PAYLOAD = {
    "typejb": "T",
    "xxfcbj[]": "2",
    "xxzqdm": "",
    "sortfield": "xxzqdm",
    "sorttype": "asc",
}
_TDX_MARKETS = (
    (0, "SZ", ("000", "001", "002", "003", "300", "301")),
    (1, "SH", ("600", "601", "603", "605", "688", "689")),
)


@dataclass(frozen=True)
class _SymbolSearchEntry:
    match: ChanlunSymbolMatch
    full_pinyin: str
    initials: str


@dataclass(frozen=True)
class _SymbolLoaderResult:
    rows: list[dict[str, str]]
    status: StrongStockSourceStatus


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
        self.loader = loader or _load_default_symbols
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
        source_status: StrongStockSourceStatus | None = None
        try:
            loaded = self.loader()
            if isinstance(loaded, _SymbolLoaderResult):
                rows = loaded.rows
                source_status = loaded.status
            else:
                rows = _rows_from_value(loaded)
            matches = _matches_from_rows(rows)
            entries = [_index_match(match) for match in matches]
        except Exception as exc:
            return [], StrongStockSourceStatus(
                source=_SYMBOL_SOURCE,
                status="failed",
                detail=f"股票代码表读取失败: {_exception_detail(exc)}",
            )
        if source_status is None:
            source_status = StrongStockSourceStatus(
                source=_SYMBOL_SOURCE,
                status="success",
                detail=f"已缓存 {len(entries)} 只A股代码",
            )
        return entries, source_status


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


def _load_tdx_symbols() -> list[dict[str, str]]:
    from mootdx.quotes import Quotes

    client = Quotes.factory(timeout=_TDX_TIMEOUT_SECONDS)
    try:
        market_rows = [
            (exchange, prefixes, _rows_from_value(client.stocks(market)))
            for market, exchange, prefixes in _TDX_MARKETS
        ]
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()

    rows: list[dict[str, str]] = []
    for exchange, prefixes, candidates in market_rows:
        for candidate in candidates:
            code = _clean_symbol_text(_row_value(candidate, "code", "symbol", "证券代码"))
            if not re.fullmatch(r"\d{6}", code) or not code.startswith(prefixes):
                continue
            symbol = f"{code}.{exchange}"
            name = _clean_symbol_text(_row_value(candidate, "name", "名称", "证券简称"))
            rows.append({"symbol": symbol, "name": name or symbol})
    return rows


def _load_bse_symbols() -> list[dict[str, str]]:
    client = httpx.Client(
        timeout=_BSE_TIMEOUT_SECONDS,
        headers={"User-Agent": _BSE_USER_AGENT},
    )
    rows: list[dict[str, str]] = []
    try:
        page = 0
        total_pages = 1
        while page < total_pages:
            response = client.post(
                _BSE_URL,
                data={**_BSE_PAYLOAD, "page": str(page)},
            )
            response.raise_for_status()
            payload = _parse_bse_page(response.text)
            if page == 0:
                total_pages = max(1, _bse_total_pages(payload))
            content = payload.get("content")
            if isinstance(content, list):
                for candidate in content:
                    if not isinstance(candidate, Mapping):
                        continue
                    code = _clean_symbol_text(_row_value(candidate, "xxzqdm"))
                    if not re.fullmatch(r"\d{6}", code):
                        continue
                    symbol = f"{code}.BJ"
                    name = _clean_symbol_text(_row_value(candidate, "xxzqjc"))
                    rows.append({"symbol": symbol, "name": name or symbol})
            page += 1
    finally:
        client.close()
    return rows


def _load_default_symbols() -> _SymbolLoaderResult:
    rows: list[dict[str, str]] = []
    failures: list[str] = []
    for source, loader in (("TDX", _load_tdx_symbols), ("BSE", _load_bse_symbols)):
        try:
            source_rows = loader()
            if not source_rows:
                raise RuntimeError("未返回代码")
        except Exception as exc:
            failures.append(f"{source}: {_exception_detail(exc)}")
        else:
            rows.extend(source_rows)

    if not rows:
        raise RuntimeError(f"A股代码源读取失败: {'; '.join(failures)}")
    if failures:
        status = StrongStockSourceStatus(
            source=_SYMBOL_SOURCE,
            status="stale",
            detail=f"部分代码源读取失败（{'; '.join(failures)}）；已缓存 {len(rows)} 只A股代码",
        )
    else:
        status = StrongStockSourceStatus(
            source=_SYMBOL_SOURCE,
            status="success",
            detail=f"已缓存 {len(rows)} 只A股代码",
        )
    return _SymbolLoaderResult(rows=rows, status=status)


def _parse_bse_page(text: str) -> Mapping[str, object]:
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < start:
        raise ValueError("BSE响应格式无效")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], Mapping):
        raise ValueError("BSE响应缺少分页数据")
    return payload[0]


def _bse_total_pages(payload: Mapping[str, object]) -> int:
    try:
        return int(payload["totalPages"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("BSE响应缺少总页数") from exc


def _clean_symbol_text(value: str) -> str:
    return value.replace("\x00", "").strip()



def _safe_rows(loader: Callable[[], object]) -> list[object]:
    try:
        return _rows_from_loader(loader)
    except Exception:
        return []


def _rows_from_loader(loader: Callable[[], object]) -> list[object]:
    return _rows_from_value(loader())


def _rows_from_value(value: object) -> list[object]:
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

    best_by_symbol: dict[str, tuple[int, ChanlunSymbolMatch]] = {}
    for entry in entries:
        rank = _match_rank(entry, needle)
        symbol = entry.match.symbol
        if rank is None:
            continue
        current = best_by_symbol.get(symbol)
        if current is None or rank < current[0]:
            best_by_symbol[symbol] = (rank, entry.match)
    ranked = [
        (rank, symbol, match)
        for symbol, (rank, match) in best_by_symbol.items()
    ]
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
