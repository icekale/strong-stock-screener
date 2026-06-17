from __future__ import annotations

from statistics import mean
from typing import Protocol

from app.models import (
    IntradayAction,
    StrongStockDataUnavailable,
    StrongStockIntradayItem,
    StrongStockIntradaySnapshot,
    StrongStockSourceStatus,
)
from app.providers.tickflow import TickFlowIntradayBar, TickFlowQuote


class IntradayQuoteProvider(Protocol):
    source_name: str

    def get_quotes(self, symbols: list[str]) -> list[TickFlowQuote]:
        ...

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        ...


class IntradayMonitor:
    def __init__(self, quote_provider: IntradayQuoteProvider) -> None:
        self.quote_provider = quote_provider

    def snapshot(
        self,
        symbols: list[str],
        name_map: dict[str, str] | None = None,
        industry_map: dict[str, str] | None = None,
        group_map: dict[str, str] | None = None,
        tag_map: dict[str, list[str]] | None = None,
        limit: int = 30,
        period: str = "1m",
        count: int = 120,
    ) -> StrongStockIntradaySnapshot:
        requested_symbols = _dedupe_symbols(symbols)[:limit]
        if not requested_symbols:
            raise StrongStockDataUnavailable("盘中监控标的为空")

        quotes = self.quote_provider.get_quotes(requested_symbols)
        if not quotes:
            raise StrongStockDataUnavailable("TickFlow 实时行情没有返回数据")

        source_status = [
            StrongStockSourceStatus(
                source="TickFlow 实时行情",
                status="success",
                detail=f"返回 {len(quotes)}/{len(requested_symbols)} 条报价",
            )
        ]
        try:
            intraday_bars = self.quote_provider.get_intraday_bars(
                requested_symbols,
                period=period,
                count=count,
            )
        except StrongStockDataUnavailable as exc:
            intraday_bars = {}
            source_status.append(
                StrongStockSourceStatus(
                    source="TickFlow 当日分钟线",
                    status="failed",
                    detail=str(exc),
                )
            )
        else:
            source_status.append(
                StrongStockSourceStatus(
                    source="TickFlow 当日分钟线",
                    status="success",
                    detail=f"period={period}, count={count}",
                )
            )

        quote_map = {quote.symbol: quote for quote in quotes}
        names = name_map or {}
        industries = industry_map or {}
        groups = group_map or {}
        tags = tag_map or {}
        return StrongStockIntradaySnapshot(
            source_status=source_status,
            items=[
                _intraday_item(
                    quote_map[symbol],
                    intraday_bars.get(symbol, []),
                    names.get(symbol, symbol),
                    industries.get(symbol),
                    groups.get(symbol),
                    tags.get(symbol, []),
                    period,
                )
                for symbol in requested_symbols
                if symbol in quote_map
            ],
        )


def _intraday_item(
    quote: TickFlowQuote,
    bars: list[TickFlowIntradayBar],
    fallback_name: str,
    industry: str | None,
    group: str | None,
    tags: list[str],
    period: str,
) -> StrongStockIntradayItem:
    intraday_ma = _intraday_ma(bars)
    latest_vs_ma = _pct_diff(quote.last_price, intraday_ma)
    action, signals = _intraday_action(quote, bars, intraday_ma)
    return StrongStockIntradayItem(
        symbol=quote.symbol,
        name=quote.name or fallback_name,
        industry=industry,
        action=action,
        group=group,
        tags=tags,
        last_price=quote.last_price,
        pct_change=quote.pct_change,
        open_gap_pct=_pct_diff(quote.open_price, quote.prev_close),
        intraday_ma=intraday_ma,
        latest_vs_intraday_ma_pct=latest_vs_ma,
        volume=quote.volume,
        turnover_cny=quote.turnover_cny,
        signals=signals,
        source_trace=["TickFlow 实时行情", f"TickFlow {period} 当日分钟线"],
    )


def _intraday_action(
    quote: TickFlowQuote,
    bars: list[TickFlowIntradayBar],
    intraday_ma: float | None,
) -> tuple[IntradayAction, list[str]]:
    signals: list[str] = []
    action: IntradayAction = "watch"

    if quote.last_price is None or quote.pct_change is None:
        return "data_incomplete", ["实时行情字段不足"]

    if quote.pct_change >= 7:
        action = "reduce"
        signals.append("早盘涨幅超过7%")
        if quote.high_price is not None and quote.last_price < quote.high_price * 0.995:
            signals.append("冲高回落，优先锁定利润")
        else:
            signals.append("高位强势，观察是否封板")
    elif quote.pct_change <= -5:
        action = "low_buy_watch"
        signals.append("早盘大跌，等待低吸确认")
    elif quote.pct_change > 0:
        signals.append("红盘不追，等待分歧承接")
    else:
        signals.append("绿盘观察承接，不跳水不买")

    if not bars:
        signals.append("分钟线未返回，盘中均线待确认")
        return action, signals

    if intraday_ma is not None and quote.last_price >= intraday_ma:
        signals.append("已站稳日内均线")
    elif intraday_ma is not None:
        signals.append("尚未站稳日内均线")
        if quote.pct_change < 0:
            action = "avoid_chase"

    return action, signals


def _intraday_ma(bars: list[TickFlowIntradayBar]) -> float | None:
    if not bars:
        return None
    window = bars[-min(len(bars), 20) :]
    return round(mean(bar.close for bar in window), 4)


def _pct_diff(value: float | None, base: float | None) -> float | None:
    if value is None or base in (None, 0):
        return None
    return round((value - base) / base * 100, 4)


def _dedupe_symbols(symbols: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output
