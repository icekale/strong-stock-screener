from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from app.models import (
    SectorWorkbenchMode,
    SectorWorkbenchPoint,
    SectorWorkbenchResponse,
    SectorWorkbenchSeries,
    SectorWorkbenchStock,
    StrongStockSourceStatus,
)
from app.providers.tickflow import TickFlowIntradayBar


class SectorIntradayBarProvider(Protocol):
    source_name: str

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        ...


def build_sector_intraday_series(
    *,
    response: SectorWorkbenchResponse,
    quote_provider: SectorIntradayBarProvider,
    mode: SectorWorkbenchMode,
    count: int = 260,
) -> tuple[list[SectorWorkbenchSeries], StrongStockSourceStatus]:
    selected = response.selected_themes[:5]
    stocks = _stocks_for_selected_themes(response.stocks, selected)
    symbols = _dedupe_symbols([stock.symbol for stock in stocks])[:80]
    if not selected or not symbols:
        return [], StrongStockSourceStatus(
            source="TickFlow 当日分钟线",
            status="unavailable",
            detail="缺少选中题材或成分股，无法补齐历史分时曲线",
        )

    bars_by_symbol = quote_provider.get_intraday_bars(symbols, period="1m", count=count)
    if not any(bars_by_symbol.values()):
        return [], StrongStockSourceStatus(
            source="TickFlow 当日分钟线",
            status="unavailable",
            detail=f"period=1m, count={count}, 未返回可用分钟线",
        )

    series = [
        _series_for_theme(
            name=name,
            mode=mode,
            response=response,
            stocks=[stock for stock in stocks if name in stock.themes],
            bars_by_symbol=bars_by_symbol,
        )
        for name in selected
    ]
    series = [item for item in series if item.points]
    if not series:
        return [], StrongStockSourceStatus(
            source="TickFlow 当日分钟线",
            status="unavailable",
            detail=f"period=1m, count={count}, 成分股分钟线无法聚合为选中题材",
        )
    return series, StrongStockSourceStatus(
        source="TickFlow 当日分钟线",
        status="success",
        detail=f"period=1m, count={count}, 聚合 {len(symbols)} 只成分股补齐 {len(series)} 条分时曲线；资金流为成交额估算",
    )


def _series_for_theme(
    *,
    name: str,
    mode: SectorWorkbenchMode,
    response: SectorWorkbenchResponse,
    stocks: list[SectorWorkbenchStock],
    bars_by_symbol: dict[str, list[TickFlowIntradayBar]],
) -> SectorWorkbenchSeries:
    states_by_symbol: dict[
        str,
        dict[str, tuple[SectorWorkbenchStock, TickFlowIntradayBar, float]],
    ] = defaultdict(dict)
    time_axis: set[str] = set()
    for stock in stocks:
        cumulative_amount = 0.0
        for bar in sorted(bars_by_symbol.get(stock.symbol, []), key=lambda item: item.timestamp):
            if bar.close <= 0:
                continue
            cumulative_amount += max(0.0, float(bar.amount or 0))
            time_text = _time_text(bar.timestamp)
            time_axis.add(time_text)
            states_by_symbol[stock.symbol][time_text] = (stock, bar, cumulative_amount)

    points: list[SectorWorkbenchPoint] = []
    latest_rows_by_symbol: dict[str, tuple[SectorWorkbenchStock, TickFlowIntradayBar, float]] = {}
    for time_text in sorted(time_axis):
        for symbol, states_by_time in states_by_symbol.items():
            if time_text in states_by_time:
                latest_rows_by_symbol[symbol] = states_by_time[time_text]
        rows = list(latest_rows_by_symbol.values())
        if not rows:
            continue
        if mode == "main_flow":
            value = _estimated_main_flow(rows)
        else:
            value = _strength_score(rows)
        points.append(
            SectorWorkbenchPoint(
                time=time_text,
                value=round(value, 2),
                sampled_at=f"{response.trade_date or ''} {time_text}".strip(),
            )
        )

    return SectorWorkbenchSeries(
        name=name,
        scope=response.scope,
        metric=mode,
        points=points,
    )


def _stocks_for_selected_themes(
    stocks: list[SectorWorkbenchStock],
    selected: list[str],
) -> list[SectorWorkbenchStock]:
    selected_set = set(selected)
    return [stock for stock in stocks if selected_set.intersection(stock.themes)]


def _estimated_main_flow(
    rows: list[tuple[SectorWorkbenchStock, TickFlowIntradayBar, float]],
) -> float:
    return sum(cumulative_amount * _bar_change_pct(bar) / 100 for _, bar, cumulative_amount in rows)


def _strength_score(
    rows: list[tuple[SectorWorkbenchStock, TickFlowIntradayBar, float]],
) -> float:
    return _estimated_main_flow(rows) / 100_000


def _bar_change_pct(bar: TickFlowIntradayBar) -> float:
    base = bar.prev_close if bar.prev_close and bar.prev_close > 0 else bar.open
    if base <= 0:
        return 0.0
    return (bar.close / base - 1) * 100


def _time_text(timestamp: int) -> str:
    seconds = timestamp / 1000 if timestamp > 10_000_000_000 else timestamp
    return datetime.fromtimestamp(seconds, tz=ZoneInfo("Asia/Shanghai")).strftime("%H:%M")


def _dedupe_symbols(symbols: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output
