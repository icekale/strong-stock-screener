from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import httpx

from app.models import (
    HeatmapBoardNode,
    HeatmapMarketKey,
    HeatmapOverviewItem,
    HeatmapOverviewResponse,
    HeatmapPeriodKey,
    HeatmapQuoteItem,
    HeatmapQuotesResponse,
    HeatmapSizeMode,
    HeatmapStockNode,
    HeatmapSummary,
    HeatmapTreemapResponse,
    HeatmapTrendFilter,
    StrongStockSourceStatus,
)
from app.providers.tencent_quote import TencentQuoteProvider


QUOTE_CACHE_SECONDS = 8
SUMMARY_CACHE_SECONDS = 8
FLAT_THRESHOLD = 0.1
MARKET_LABELS: dict[HeatmapMarketKey, str] = {
    "all": "全 A",
    "sse": "上证 A 股",
    "szse": "深证 A 股",
    "hs300": "沪深 300",
    "zza500": "中证 A500",
    "cyb": "创业板",
    "kcb": "科创板",
}
EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


@dataclass(frozen=True)
class HeatmapBaselineStock:
    symbol: str
    code: str
    name: str
    exchange: str
    market: HeatmapMarketKey
    industry: str
    sub_industry: str | None
    circulating_market_cap_cny: float | None
    total_market_cap_cny: float | None
    fallback_price: float | None = None
    fallback_change_pct: float | None = None
    fallback_turnover_cny: float | None = None


@dataclass(frozen=True)
class HeatmapQuoteValue:
    price: float | None
    changes: dict[HeatmapPeriodKey, float]
    turnover_cny: float | None
    quote_time: str | None = None


@dataclass(frozen=True)
class HeatmapQuoteSnapshot:
    updated_at: str
    values: dict[str, HeatmapQuoteValue]
    source_status: list[StrongStockSourceStatus | dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class HeatmapSummarySnapshot:
    trade_date: str | None
    updated_at: str
    advance_count: int | None
    decline_count: int | None
    unchanged_count: int | None
    turnover_cny: float | None
    previous_turnover_cny: float | None
    source_status: list[StrongStockSourceStatus | dict[str, str]] = field(default_factory=list)


class HeatmapProvider:
    source_name = "东方财富热图行情"

    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        baseline_stocks: list[HeatmapBaselineStock] | None = None,
        quote_loader: Callable[[list[str]], HeatmapQuoteSnapshot] | None = None,
        summary_loader: Callable[[], HeatmapSummarySnapshot] | None = None,
        timeout_seconds: float = 8,
        now: Callable[[], datetime] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.data_dir = data_dir or Path(__file__).resolve().parents[1] / "data/heatmap"
        self.baseline_stocks = baseline_stocks or self._load_baseline_stocks()
        use_default_quote_loader = quote_loader is None
        self.quote_loader = quote_loader or self._fetch_eastmoney_quotes
        self.quote_fallback_loader = self._fetch_tencent_quotes if use_default_quote_loader else None
        self.summary_loader = summary_loader or self._fetch_summary
        self.timeout_seconds = timeout_seconds
        self.now = now or (lambda: datetime.now(ZoneInfo("Asia/Shanghai")))
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client()
        self._quote_cache: tuple[float, tuple[str, ...], HeatmapQuoteSnapshot] | None = None
        self._summary_cache: tuple[float, HeatmapSummarySnapshot] | None = None

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    def get_treemap(
        self,
        market: HeatmapMarketKey,
        period: HeatmapPeriodKey,
        size_mode: HeatmapSizeMode,
        trend: HeatmapTrendFilter,
        board: str | None,
        limit: int,
    ) -> HeatmapTreemapResponse:
        stocks = self._filter_baseline(self.baseline_stocks, market, board)
        snapshot = self._safe_quote_snapshot([stock.symbol for stock in stocks])
        summary_snapshot = self._safe_summary_snapshot()
        nodes = self._build_stock_nodes(stocks, snapshot, period, size_mode)
        nodes = [node for node in nodes if self._matches_trend(node.change_pct, trend)]
        boards = self._build_board_nodes(nodes, limit)
        turnover_cny = self._summary_turnover(nodes, market, trend, board, summary_snapshot)
        previous_turnover_cny = summary_snapshot.previous_turnover_cny if nodes else None

        return HeatmapTreemapResponse(
            market=market,
            period=period,
            size_mode=size_mode,
            trend=trend,
            board=board,
            summary=HeatmapSummary(
                trade_date=summary_snapshot.trade_date,
                updated_at=summary_snapshot.updated_at or snapshot.updated_at,
                stock_count=len(nodes),
                board_count=len(boards),
                advance_count=sum(1 for node in nodes if node.change_pct > FLAT_THRESHOLD),
                decline_count=sum(1 for node in nodes if node.change_pct < -FLAT_THRESHOLD),
                unchanged_count=sum(1 for node in nodes if abs(node.change_pct) <= FLAT_THRESHOLD),
                turnover_cny=turnover_cny,
                previous_turnover_cny=previous_turnover_cny,
                turnover_change_pct=self._change_pct(turnover_cny, previous_turnover_cny),
            ),
            nodes=boards,
            source_status=self._dedupe_statuses([*snapshot.source_status, *summary_snapshot.source_status]),
            generated_at=self._now_iso(),
        )

    def get_quotes(self, market: HeatmapMarketKey, period: HeatmapPeriodKey) -> HeatmapQuotesResponse:
        stocks = self._filter_baseline(self.baseline_stocks, market, None)
        snapshot = self._safe_quote_snapshot([stock.symbol for stock in stocks])
        quotes: dict[str, HeatmapQuoteItem] = {}
        for stock in stocks:
            quote = snapshot.values.get(stock.symbol) or self._fallback_quote_value(stock)
            quotes[stock.symbol] = HeatmapQuoteItem(
                symbol=stock.symbol,
                price=quote.price,
                change_pct=quote.changes.get(period, 0),
                turnover_cny=quote.turnover_cny,
                quote_time=quote.quote_time,
            )
        return HeatmapQuotesResponse(
            market=market,
            period=period,
            quotes=quotes,
            source_status=self._dedupe_statuses(snapshot.source_status),
            generated_at=self._now_iso(),
        )

    def get_overview(self, period: HeatmapPeriodKey) -> HeatmapOverviewResponse:
        snapshot = self._safe_quote_snapshot([stock.symbol for stock in self.baseline_stocks])
        markets: list[HeatmapOverviewItem] = []
        for market, name in MARKET_LABELS.items():
            stocks = self._filter_baseline(self.baseline_stocks, market, None)
            changes = [
                snapshot.values[stock.symbol].changes.get(period, 0)
                for stock in stocks
                if stock.symbol in snapshot.values
            ]
            markets.append(
                HeatmapOverviewItem(
                    market=market,
                    name=name,
                    change_pct=round(sum(changes) / len(changes), 2) if changes else None,
                    stock_count=len(stocks),
                    updated_at=snapshot.updated_at,
                )
            )
        return HeatmapOverviewResponse(
            period=period,
            markets=markets,
            source_status=self._dedupe_statuses(snapshot.source_status),
            generated_at=self._now_iso(),
        )

    def _safe_quote_snapshot(self, symbols: list[str]) -> HeatmapQuoteSnapshot:
        cache_key = tuple(symbols)
        now_ts = time.monotonic()
        if self._quote_cache is not None:
            cached_at, cached_symbols, cached = self._quote_cache
            if cached_symbols == cache_key and now_ts - cached_at <= QUOTE_CACHE_SECONDS:
                return cached

        try:
            snapshot = self.quote_loader(symbols)
        except Exception as exc:
            snapshot = self._quote_snapshot_after_primary_failure(symbols, exc)
        self._quote_cache = (now_ts, cache_key, snapshot)
        return snapshot

    def _quote_snapshot_after_primary_failure(
        self,
        symbols: list[str],
        primary_error: Exception,
    ) -> HeatmapQuoteSnapshot:
        primary_status = StrongStockSourceStatus(
            source="东方财富热图行情",
            status="failed",
            detail=f"实时行情获取失败: {primary_error.__class__.__name__}; 尝试腾讯财经",
        )
        if self.quote_fallback_loader is not None:
            try:
                fallback = self.quote_fallback_loader(symbols)
                return HeatmapQuoteSnapshot(
                    updated_at=fallback.updated_at,
                    values=fallback.values,
                    source_status=[primary_status, *fallback.source_status],
                )
            except Exception as fallback_error:
                return HeatmapQuoteSnapshot(
                    updated_at=self._now_iso(),
                    values=self._fallback_quote_values(symbols),
                    source_status=[
                        primary_status,
                        StrongStockSourceStatus(
                            source="腾讯财经",
                            status="failed",
                            detail=f"腾讯财经实时行情获取失败: {fallback_error.__class__.__name__}",
                        ),
                        StrongStockSourceStatus(
                            source="热图内置样本",
                            status="stale",
                            detail="来自 wenyuanw/a-share-heatmap MIT 样本数据，仅用于降级展示",
                        ),
                    ],
                )

        return HeatmapQuoteSnapshot(
            updated_at=self._now_iso(),
            values=self._fallback_quote_values(symbols),
            source_status=[
                StrongStockSourceStatus(
                    source="东方财富热图行情",
                    status="failed",
                    detail=f"实时行情获取失败: {primary_error.__class__.__name__}; 使用内置样本",
                ),
                StrongStockSourceStatus(
                    source="热图内置样本",
                    status="stale",
                    detail="来自 wenyuanw/a-share-heatmap MIT 样本数据，仅用于降级展示",
                ),
            ],
        )

    def _safe_summary_snapshot(self) -> HeatmapSummarySnapshot:
        now_ts = time.monotonic()
        if self._summary_cache is not None:
            cached_at, cached = self._summary_cache
            if now_ts - cached_at <= SUMMARY_CACHE_SECONDS:
                return cached

        try:
            snapshot = self.summary_loader()
        except Exception as exc:
            snapshot = HeatmapSummarySnapshot(
                trade_date=self.now().date().isoformat(),
                updated_at=self._now_iso(),
                advance_count=None,
                decline_count=None,
                unchanged_count=None,
                turnover_cny=None,
                previous_turnover_cny=None,
                source_status=[
                    StrongStockSourceStatus(
                        source=self.source_name,
                        status="failed",
                        detail=f"热图摘要获取失败: {exc.__class__.__name__}",
                    )
                ],
            )
        self._summary_cache = (now_ts, snapshot)
        return snapshot

    def _fetch_eastmoney_quotes(self, symbols: list[str]) -> HeatmapQuoteSnapshot:
        values: dict[str, HeatmapQuoteValue] = {}
        statuses: list[StrongStockSourceStatus] = []
        for batch in _chunks(symbols, 180):
            secids = ",".join(self._to_eastmoney_secid(symbol) for symbol in batch)
            response = self.http_client.get(
                EASTMONEY_QUOTE_URL,
                params={
                    "fltt": "2",
                    "invt": "2",
                    "fields": "f2,f3,f6,f12,f13,f14,f24,f25,f109,f110,f124,f127,f160",
                    "secids": secids,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            rows = (data.get("data") or {}).get("diff") or []
            for row in rows:
                symbol = self._symbol_from_eastmoney_row(row)
                quote_time = self._quote_time(row.get("f124"))
                values[symbol] = HeatmapQuoteValue(
                    price=_number(row.get("f2")),
                    changes={
                        "day": _number(row.get("f3")) or 0,
                        "week": _number(row.get("f109")) or 0,
                        "month": _number(row.get("f110")) or 0,
                        "year": _number(row.get("f25")) or _number(row.get("f127")) or _number(row.get("f160")) or 0,
                    },
                    turnover_cny=_number(row.get("f6")),
                    quote_time=quote_time,
                )
        requested_count = len(set(symbols))
        returned_count = len(values)
        if requested_count == 0 or returned_count == requested_count:
            statuses.append(
                StrongStockSourceStatus(
                    source=self.source_name,
                    status="success",
                    detail=f"东方财富 push2 返回 {returned_count} 条热图行情",
                )
            )
        elif returned_count == 0:
            statuses.append(
                StrongStockSourceStatus(
                    source=self.source_name,
                    status="failed",
                    detail=f"东方财富行情未返回报价行 0/{requested_count}，缺失使用样本兜底",
                )
            )
        else:
            statuses.append(
                StrongStockSourceStatus(
                    source=self.source_name,
                    status="stale",
                    detail=f"东方财富行情部分返回 {returned_count}/{requested_count}，缺失使用样本兜底",
                )
            )
        return HeatmapQuoteSnapshot(
            updated_at=self._now_iso(),
            values=values,
            source_status=statuses,
        )

    def _fetch_tencent_quotes(self, symbols: list[str]) -> HeatmapQuoteSnapshot:
        provider = TencentQuoteProvider(
            timeout_seconds=self.timeout_seconds,
            http_client=self.http_client,
            batch_size=180,
        )
        quotes = provider.get_quotes(symbols)
        values: dict[str, HeatmapQuoteValue] = {}
        for quote in quotes:
            change_pct = quote.pct_change or 0
            values[quote.symbol] = HeatmapQuoteValue(
                price=quote.price,
                changes={
                    "day": change_pct,
                    "week": change_pct,
                    "month": change_pct,
                    "year": change_pct,
                },
                turnover_cny=quote.turnover_cny,
                quote_time=quote.quote_time,
            )

        requested_count = len(set(symbols))
        returned_count = len(values)
        if requested_count == 0 or returned_count == requested_count:
            status = StrongStockSourceStatus(
                source="腾讯财经",
                status="success",
                detail=f"qt.gtimg.cn 返回 {returned_count} 条热图行情",
            )
        elif returned_count == 0:
            status = StrongStockSourceStatus(
                source="腾讯财经",
                status="failed",
                detail=f"腾讯财经未返回报价行 0/{requested_count}，缺失使用样本兜底",
            )
        else:
            status = StrongStockSourceStatus(
                source="腾讯财经",
                status="stale",
                detail=f"腾讯财经部分返回 {returned_count}/{requested_count}，缺失使用样本兜底",
            )
        return HeatmapQuoteSnapshot(
            updated_at=self._now_iso(),
            values=values,
            source_status=[status],
        )

    def _fetch_summary(self) -> HeatmapSummarySnapshot:
        return HeatmapSummarySnapshot(
            trade_date=self.now().date().isoformat(),
            updated_at=self._now_iso(),
            advance_count=None,
            decline_count=None,
            unchanged_count=None,
            turnover_cny=None,
            previous_turnover_cny=None,
            source_status=[
                StrongStockSourceStatus(
                    source="东方财富热图摘要",
                    status="failed",
                    detail="未配置可用摘要端点，使用热图节点聚合摘要",
                )
            ],
        )

    def _build_stock_nodes(
        self,
        stocks: list[HeatmapBaselineStock],
        snapshot: HeatmapQuoteSnapshot,
        period: HeatmapPeriodKey,
        size_mode: HeatmapSizeMode,
    ) -> list[HeatmapStockNode]:
        nodes: list[HeatmapStockNode] = []
        for stock in stocks:
            quote = snapshot.values.get(stock.symbol) or self._fallback_quote_value(stock)
            value = (
                stock.circulating_market_cap_cny
                if size_mode == "market_cap"
                else quote.turnover_cny
            )
            nodes.append(
                HeatmapStockNode(
                    symbol=stock.symbol,
                    code=stock.code,
                    name=stock.name,
                    industry=stock.industry,
                    sub_industry=stock.sub_industry,
                    exchange=stock.exchange,
                    market=stock.market,
                    price=quote.price,
                    change_pct=quote.changes.get(period, 0),
                    week_change_pct=quote.changes.get("week"),
                    month_change_pct=quote.changes.get("month"),
                    year_change_pct=quote.changes.get("year"),
                    turnover_cny=quote.turnover_cny,
                    circulating_market_cap_cny=stock.circulating_market_cap_cny,
                    total_market_cap_cny=stock.total_market_cap_cny,
                    value=value or 0,
                    quote_time=quote.quote_time,
                )
            )
        return sorted(nodes, key=lambda node: node.value, reverse=True)

    def _build_board_nodes(self, nodes: list[HeatmapStockNode], limit: int) -> list[HeatmapBoardNode]:
        grouped: dict[str, list[HeatmapStockNode]] = {}
        for node in nodes:
            grouped.setdefault(node.industry, []).append(node)

        boards: list[HeatmapBoardNode] = []
        for name, children in grouped.items():
            sorted_children = sorted(children, key=lambda child: child.value, reverse=True)[:limit]
            turnover_cny = sum((child.turnover_cny or 0) for child in sorted_children)
            boards.append(
                HeatmapBoardNode(
                    key=name,
                    name=name,
                    value=sum(child.value for child in sorted_children),
                    stock_count=len(sorted_children),
                    advance_count=sum(1 for child in sorted_children if child.change_pct > FLAT_THRESHOLD),
                    decline_count=sum(1 for child in sorted_children if child.change_pct < -FLAT_THRESHOLD),
                    unchanged_count=sum(1 for child in sorted_children if abs(child.change_pct) <= FLAT_THRESHOLD),
                    avg_change_pct=round(sum(child.change_pct for child in sorted_children) / len(sorted_children), 2),
                    turnover_cny=turnover_cny or None,
                    children=sorted_children,
                )
            )
        return sorted(boards, key=lambda board: board.value, reverse=True)

    def _filter_baseline(
        self,
        stocks: list[HeatmapBaselineStock],
        market: HeatmapMarketKey,
        board: str | None,
    ) -> list[HeatmapBaselineStock]:
        filtered = [stock for stock in stocks if self._matches_market(stock, market)]
        if board:
            filtered = [stock for stock in filtered if stock.industry == board or stock.sub_industry == board]
        return filtered

    def _summary_turnover(
        self,
        nodes: list[HeatmapStockNode],
        market: HeatmapMarketKey,
        trend: HeatmapTrendFilter,
        board: str | None,
        summary_snapshot: HeatmapSummarySnapshot,
    ) -> float | None:
        if not nodes:
            return 0
        node_turnover = sum((node.turnover_cny or 0) for node in nodes)
        if node_turnover:
            return node_turnover
        if market == "all" and trend == "all" and board is None:
            return summary_snapshot.turnover_cny
        return 0

    def _load_baseline_stocks(self) -> list[HeatmapBaselineStock]:
        heatmap_path = self.data_dir / "market-heatmap-fallback.json"
        subboard_path = self.data_dir / "market-heatmap-subboards.json"
        fallback = json.loads(heatmap_path.read_text(encoding="utf-8"))
        subboards = json.loads(subboard_path.read_text(encoding="utf-8")).get("subboards", {})
        stocks: list[HeatmapBaselineStock] = []
        for row in fallback.get("stocks", []):
            symbol, code, exchange = self._parse_symbol_code(row)
            subboard = subboards.get(symbol) or subboards.get(code) or {}
            stocks.append(
                HeatmapBaselineStock(
                    symbol=symbol,
                    code=code,
                    name=str(row.get("name") or code),
                    exchange=exchange,
                    market=self._market_from_symbol(symbol),
                    industry=str(subboard.get("sectorName") or row.get("boardName") or "未分类"),
                    sub_industry=subboard.get("subBoardName"),
                    circulating_market_cap_cny=_number(row.get("floatMarketCap")),
                    total_market_cap_cny=_number(row.get("totalMarketCap")),
                    fallback_price=_number(row.get("price")),
                    fallback_change_pct=_number(row.get("changePct")),
                    fallback_turnover_cny=_number(row.get("turnoverAmount")),
                )
            )
        return stocks

    def _parse_symbol_code(self, row: dict[str, Any]) -> tuple[str, str, str]:
        raw_code = str(row.get("code") or "")
        exchange = str(row.get("exchange") or "").upper()
        if "." in raw_code:
            code, suffix = raw_code.split(".", 1)
            exchange = exchange or suffix.upper()
            return f"{code}.{suffix.upper()}", code, exchange
        symbol = f"{raw_code}.{exchange}" if exchange else raw_code
        return symbol, raw_code, exchange

    def _fallback_quote_values(self, symbols: list[str]) -> dict[str, HeatmapQuoteValue]:
        by_symbol = {stock.symbol: stock for stock in self.baseline_stocks}
        return {symbol: self._fallback_quote_value(by_symbol[symbol]) for symbol in symbols if symbol in by_symbol}

    def _fallback_quote_value(self, stock: HeatmapBaselineStock) -> HeatmapQuoteValue:
        change_pct = stock.fallback_change_pct or 0
        return HeatmapQuoteValue(
            price=stock.fallback_price,
            changes={"day": change_pct, "week": change_pct, "month": change_pct, "year": change_pct},
            turnover_cny=stock.fallback_turnover_cny,
            quote_time=None,
        )

    def _dedupe_statuses(
        self,
        statuses: list[StrongStockSourceStatus | dict[str, str]],
    ) -> list[StrongStockSourceStatus]:
        deduped: list[StrongStockSourceStatus] = []
        seen: set[tuple[str, str]] = set()
        for status in statuses:
            parsed = status if isinstance(status, StrongStockSourceStatus) else StrongStockSourceStatus(**status)
            key = (parsed.source, parsed.status)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(parsed)
        return deduped

    def _matches_trend(self, change_pct: float, trend: HeatmapTrendFilter) -> bool:
        if trend == "rise":
            return change_pct > FLAT_THRESHOLD
        if trend == "fall":
            return change_pct < -FLAT_THRESHOLD
        return True

    def _matches_market(self, stock: HeatmapBaselineStock, market: HeatmapMarketKey) -> bool:
        if market == "all":
            return True
        if market == "hs300":
            return (stock.total_market_cap_cny or 0) >= 80_000_000_000
        if market == "zza500":
            total_cap = stock.total_market_cap_cny or 0
            return 15_000_000_000 <= total_cap < 80_000_000_000
        return stock.market == market

    def _market_from_symbol(self, symbol: str) -> HeatmapMarketKey:
        code, _, exchange = symbol.partition(".")
        if exchange == "SH" and code.startswith("688"):
            return "kcb"
        if exchange == "SZ" and code.startswith("3"):
            return "cyb"
        if exchange == "SH":
            return "sse"
        if exchange == "SZ":
            return "szse"
        return "all"

    def _to_eastmoney_secid(self, symbol: str) -> str:
        code, _, exchange = symbol.partition(".")
        market_id = "1" if exchange == "SH" else "0"
        return f"{market_id}.{code}"

    def _symbol_from_eastmoney_row(self, row: dict[str, Any]) -> str:
        code = str(row.get("f12") or "")
        market_id = str(row.get("f13") or "")
        if market_id == "1":
            exchange = "SH"
        elif code.startswith(("8", "4", "9")):
            exchange = "BJ"
        else:
            exchange = "SZ"
        return f"{code}.{exchange}"

    def _quote_time(self, timestamp: Any) -> str | None:
        value = _number(timestamp)
        if value is None or value <= 0:
            return None
        return datetime.fromtimestamp(value, ZoneInfo("Asia/Shanghai")).isoformat()

    def _now_iso(self) -> str:
        return self.now().isoformat()

    def _change_pct(self, current: float | None, previous: float | None) -> float | None:
        if current is None or not previous:
            return None
        return round((current - previous) / previous * 100, 2)


def _number(value: Any) -> float | None:
    if value is None or value == "-":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]
