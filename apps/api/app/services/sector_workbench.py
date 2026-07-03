from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from app.models import (
    MarketRankingItem,
    MarketRankingsResponse,
    SectorRadarResponse,
    SectorWorkbenchMode,
    SectorWorkbenchPoint,
    SectorWorkbenchResponse,
    SectorWorkbenchScope,
    SectorWorkbenchScopeRequest,
    SectorWorkbenchSeries,
    SectorWorkbenchStock,
    SectorWorkbenchTheme,
    StrongStockSourceStatus,
)


def build_sector_workbench_from_radar(
    *,
    radar: SectorRadarResponse,
    mode: SectorWorkbenchMode,
    scope: SectorWorkbenchScopeRequest,
    selected: list[str],
    limit: int,
    sampled_at: datetime,
) -> SectorWorkbenchResponse:
    effective_scope: SectorWorkbenchScope = (
        "theme"
        if scope in ("auto", "theme") and any(token in radar.flow_source for token in ("概念", "题材"))
        else "industry"
    )
    items = [*radar.inflow, *radar.outflow]
    themes = [
        SectorWorkbenchTheme(
            name=item.name,
            scope=effective_scope,
            limit_up_count=item.advance_count or 0,
            strength_score=item.strength_score,
            main_flow_cny=item.net_flow_cny,
            turnover_cny=item.turnover_cny,
            change_pct=item.change_pct,
            leader=item.leader,
            member_count=(item.advance_count or 0) + (item.decline_count or 0),
            source=item.source,
            flow_status=radar.capital_flow_status,
        )
        for item in items
    ]
    themes = sorted(themes, key=lambda item: _theme_sort_key(item, mode=mode), reverse=True)[: max(1, min(limit, 50))]
    selected_themes = _selected_theme_names(selected, themes)
    series = _current_series(
        themes=themes,
        selected=selected_themes,
        scope=effective_scope,
        mode=mode,
        sampled_at=sampled_at,
    )
    return SectorWorkbenchResponse(
        scope=effective_scope,
        mode=mode,
        trade_date=radar.trade_date or sampled_at.date().isoformat(),
        themes=themes,
        selected_themes=selected_themes,
        series=series,
        related_tags=[],
        stocks=[],
        source_status=[
            StrongStockSourceStatus(
                source="板块雷达兜底",
                status="success",
                detail=f"实时排行榜不可用，使用 {radar.flow_source} 生成题材工作台",
            ),
            *radar.source_status,
        ],
        generated_at=sampled_at.isoformat(timespec="seconds"),
    )


def build_sector_workbench_response(
    *,
    rankings: MarketRankingsResponse,
    limit_up_rows: list[dict[str, Any]],
    mode: SectorWorkbenchMode,
    scope: SectorWorkbenchScopeRequest,
    selected: list[str],
    limit: int,
    stock_limit: int,
    sampled_at: datetime,
) -> SectorWorkbenchResponse:
    ranking_items = _unique_ranking_items(rankings)
    ranking_by_symbol = {item.symbol: item for item in ranking_items if item.symbol}
    bounded_limit = max(1, min(limit, 50))
    bounded_stock_limit = max(1, min(stock_limit, 200))

    theme_rows = _theme_rows(limit_up_rows, ranking_by_symbol)
    effective_scope: SectorWorkbenchScope = (
        "theme" if scope in ("auto", "theme") and theme_rows else "industry"
    )

    if effective_scope == "theme":
        themes = _themes_from_limit_up_rows(theme_rows, mode=mode)[:bounded_limit]
        status = StrongStockSourceStatus(
            source="通达信MCP涨停概念映射",
            status="success",
            detail=f"概念/题材映射返回 {len(theme_rows)} 只涨停股，聚合 {len(themes)} 个题材",
        )
        stocks = _stocks_from_theme_rows(theme_rows, selected or [item.name for item in themes[:3]])
    else:
        themes = _themes_from_industries(ranking_items, mode=mode)[:bounded_limit]
        status = StrongStockSourceStatus(
            source="TickFlow行业聚合",
            status="success",
            detail=f"概念映射不可用，使用行业兜底聚合 {len(themes)} 个行业",
        )
        stocks = _stocks_from_industries(ranking_items, selected or [item.name for item in themes[:3]])

    selected_themes = _selected_theme_names(selected, themes)
    stocks = _sort_stocks(stocks, mode=mode)[:bounded_stock_limit]
    related_tags = _related_tags(stocks, selected_themes)
    series = _current_series(
        themes=themes,
        selected=selected_themes,
        scope=effective_scope,
        mode=mode,
        sampled_at=sampled_at,
    )
    return SectorWorkbenchResponse(
        scope=effective_scope,
        mode=mode,
        trade_date=rankings.trade_date or sampled_at.date().isoformat(),
        themes=themes,
        selected_themes=selected_themes,
        series=series,
        related_tags=related_tags,
        stocks=stocks,
        source_status=[status, *rankings.source_status],
        generated_at=sampled_at.isoformat(timespec="seconds"),
    )


def _unique_ranking_items(rankings: MarketRankingsResponse) -> list[MarketRankingItem]:
    output: dict[str, MarketRankingItem] = {}
    for item in [*rankings.pct_change_rank, *rankings.turnover_rank]:
        if item.symbol and item.symbol not in output:
            output[item.symbol] = item
    return list(output.values())


def _theme_rows(
    rows: list[dict[str, Any]],
    ranking_by_symbol: dict[str, MarketRankingItem],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        concepts = _concepts_from_row(row)
        symbol = _symbol_from_row(row)
        if not concepts or not symbol:
            continue
        ranking = ranking_by_symbol.get(symbol)
        row_name = _text_field(row, ["名称", "股票名称", "sec_name"])
        name = row_name or (ranking.name if ranking else None)
        output.append(
            {
                "symbol": symbol,
                "name": name,
                "industry": ranking.industry if ranking else _text_field(row, ["行业", "所属行业"]),
                "concepts": concepts,
                "board_count": _board_count(row),
                "seal_amount_cny": _seal_amount_cny(row),
                "pct_change": ranking.pct_change if ranking else _number_field(row, ["涨幅", "涨跌幅"]),
                "turnover_cny": ranking.turnover_cny if ranking else _number_field(row, ["成交额", "成交金额"]),
                "turnover_rate": ranking.turnover_rate if ranking else _number_field(row, ["换手率", "换手"]),
            }
        )
    return output


def _themes_from_limit_up_rows(
    rows: list[dict[str, Any]],
    *,
    mode: SectorWorkbenchMode,
) -> list[SectorWorkbenchTheme]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for concept in row["concepts"]:
            grouped[concept].append(row)

    themes: list[SectorWorkbenchTheme] = []
    for concept, members in grouped.items():
        turnover = sum(float(item.get("turnover_cny") or 0) for item in members)
        avg_change = _average(item.get("pct_change") for item in members)
        main_flow = _estimated_flow(members)
        leader = max(
            members,
            key=lambda item: (
                int(item.get("board_count") or 0),
                float(item.get("pct_change") or 0),
                float(item.get("turnover_cny") or 0),
            ),
        )
        max_boards = max(int(item.get("board_count") or 0) for item in members)
        seal_amount = sum(float(item.get("seal_amount_cny") or 0) for item in members)
        strength = round(
            len(members) * 30
            + max_boards * 12
            + (avg_change or 0) * 4
            + min(turnover / 100_000_000, 30)
            + min(seal_amount / 100_000_000, 20),
            2,
        )
        themes.append(
            SectorWorkbenchTheme(
                name=concept,
                scope="theme",
                limit_up_count=len(members),
                strength_score=strength,
                main_flow_cny=round(main_flow, 2),
                turnover_cny=round(turnover, 2),
                change_pct=round(avg_change, 2) if avg_change is not None else None,
                leader=leader.get("name"),
                member_count=len(members),
                source="通达信MCP涨停概念映射",
                flow_status="estimated",
            )
        )
    return sorted(themes, key=lambda item: _theme_sort_key(item, mode=mode), reverse=True)


def _themes_from_industries(
    items: list[MarketRankingItem],
    *,
    mode: SectorWorkbenchMode,
) -> list[SectorWorkbenchTheme]:
    grouped: dict[str, list[MarketRankingItem]] = defaultdict(list)
    for item in items:
        if item.industry:
            grouped[item.industry].append(item)

    themes: list[SectorWorkbenchTheme] = []
    for industry, members in grouped.items():
        turnover = sum(item.turnover_cny or 0 for item in members)
        avg_change = _average(item.pct_change for item in members)
        main_flow = sum(
            (item.turnover_cny or 0) * (item.pct_change or 0) / 100
            for item in members
            if item.turnover_cny is not None and item.pct_change is not None
        )
        advance_count = sum(1 for item in members if (item.pct_change or 0) > 0)
        leader = max(members, key=lambda item: (item.pct_change or -999, item.turnover_cny or 0))
        strength = round(
            advance_count * 12
            + (avg_change or 0) * 8
            + min(turnover / 100_000_000, 30)
            + len(members) * 2,
            2,
        )
        themes.append(
            SectorWorkbenchTheme(
                name=industry,
                scope="industry",
                limit_up_count=0,
                strength_score=strength,
                main_flow_cny=round(main_flow, 2),
                turnover_cny=round(turnover, 2),
                change_pct=round(avg_change, 2) if avg_change is not None else None,
                leader=leader.name or leader.symbol,
                member_count=len(members),
                source="TickFlow全A实时行情行业聚合",
                flow_status="estimated",
            )
        )
    return sorted(themes, key=lambda item: _theme_sort_key(item, mode=mode), reverse=True)


def _stocks_from_theme_rows(
    rows: list[dict[str, Any]],
    selected: list[str],
) -> list[SectorWorkbenchStock]:
    selected_set = set(selected)
    stocks: list[SectorWorkbenchStock] = []
    for row in rows:
        themes = [theme for theme in row["concepts"] if not selected_set or theme in selected_set]
        if not themes:
            continue
        stocks.append(
            SectorWorkbenchStock(
                symbol=row["symbol"],
                name=row.get("name"),
                industry=row.get("industry"),
                themes=row["concepts"],
                pct_change=row.get("pct_change"),
                turnover_cny=row.get("turnover_cny"),
                turnover_rate=row.get("turnover_rate"),
                limit_up=True,
                board_count=int(row.get("board_count") or 1),
                seal_amount_cny=row.get("seal_amount_cny"),
            )
        )
    return stocks


def _stocks_from_industries(
    items: list[MarketRankingItem],
    selected: list[str],
) -> list[SectorWorkbenchStock]:
    selected_set = set(selected)
    stocks: list[SectorWorkbenchStock] = []
    for item in items:
        if selected_set and item.industry not in selected_set:
            continue
        stocks.append(
            SectorWorkbenchStock(
                symbol=item.symbol,
                name=item.name,
                industry=item.industry,
                themes=[item.industry] if item.industry else [],
                pct_change=item.pct_change,
                turnover_cny=item.turnover_cny,
                turnover_rate=item.turnover_rate,
                limit_up=(item.pct_change or 0) >= 9.8,
                board_count=1 if (item.pct_change or 0) >= 9.8 else 0,
            )
        )
    return stocks


def _selected_theme_names(selected: list[str], themes: list[SectorWorkbenchTheme]) -> list[str]:
    available = {item.name for item in themes}
    cleaned = [name.strip() for name in selected if name.strip() in available]
    if cleaned:
        return cleaned[:5]
    return [item.name for item in themes[:3]]


def _current_series(
    *,
    themes: list[SectorWorkbenchTheme],
    selected: list[str],
    scope: SectorWorkbenchScope,
    mode: SectorWorkbenchMode,
    sampled_at: datetime,
) -> list[SectorWorkbenchSeries]:
    theme_by_name = {item.name: item for item in themes}
    sampled_text = sampled_at.isoformat(timespec="seconds")
    time_text = sampled_at.strftime("%H:%M")
    series: list[SectorWorkbenchSeries] = []
    for name in selected:
        theme = theme_by_name.get(name)
        if not theme:
            continue
        value = theme.strength_score if mode == "strength" else theme.main_flow_cny or 0
        series.append(
            SectorWorkbenchSeries(
                name=name,
                scope=scope,
                metric=mode,
                points=[
                    SectorWorkbenchPoint(
                        time=time_text,
                        value=round(float(value), 2),
                        sampled_at=sampled_text,
                    )
                ],
            )
        )
    return series


def _related_tags(stocks: list[SectorWorkbenchStock], selected: list[str]) -> list[str]:
    selected_set = set(selected)
    output: list[str] = []
    seen: set[str] = set(selected)
    for stock in stocks:
        for theme in stock.themes:
            if theme in seen or theme in selected_set:
                continue
            seen.add(theme)
            output.append(theme)
            if len(output) >= 12:
                return output
    return output


def _sort_stocks(stocks: list[SectorWorkbenchStock], *, mode: SectorWorkbenchMode) -> list[SectorWorkbenchStock]:
    if mode == "main_flow":
        return sorted(
            stocks,
            key=lambda item: (
                item.turnover_cny or 0,
                item.pct_change or 0,
                item.turnover_rate or 0,
            ),
            reverse=True,
        )
    return sorted(
        stocks,
        key=lambda item: (
            item.board_count,
            item.pct_change or 0,
            item.turnover_cny or 0,
        ),
        reverse=True,
    )


def _theme_sort_key(theme: SectorWorkbenchTheme, *, mode: SectorWorkbenchMode) -> tuple[float, float, float]:
    if mode == "main_flow":
        return (theme.main_flow_cny or 0, theme.strength_score, theme.turnover_cny or 0)
    return (theme.strength_score, float(theme.limit_up_count), theme.turnover_cny or 0)


def _estimated_flow(rows: list[dict[str, Any]]) -> float:
    return sum(
        float(row.get("turnover_cny") or 0) * float(row.get("pct_change") or 0) / 100
        for row in rows
        if row.get("turnover_cny") is not None and row.get("pct_change") is not None
    )


def _average(values: Any) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return sum(numeric) / len(numeric)


def _concepts_from_row(row: dict[str, Any]) -> list[str]:
    raw = _text_field(row, ["所属概念", "所属通达信概念", "概念板块", "涨停原因"]) or ""
    output: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[;；,，、/|【】\s]+", raw):
        concept = part.replace("@", "").strip()
        if not concept or concept in seen:
            continue
        seen.add(concept)
        output.append(concept)
    return output[:8]


def _symbol_from_row(row: dict[str, Any]) -> str | None:
    raw = _text_field(row, ["代码", "股票代码", "证券代码", "sec_code", "symbol"])
    if not raw:
        return None
    text = raw.strip().upper()
    if re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", text):
        return text
    digits = re.search(r"\d{6}", text)
    if not digits:
        return None
    code = digits.group(0)
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return code


def _board_count(row: dict[str, Any]) -> int:
    value = _number_field(row, ["连续涨停天数", "连板", "几板"])
    return max(1, int(value or 1))


def _seal_amount_cny(row: dict[str, Any]) -> float | None:
    value = _number_field(row, ["封单金额", "涨停最大封单额(万)", "封单额", "封单金额(万)"])
    if value is None:
        return None
    return value * 10_000


def _text_field(row: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    for key, value in row.items():
        if any(name in str(key) for name in keys) and value not in (None, ""):
            return str(value).strip()
    return None


def _number_field(row: dict[str, Any], keys: list[str]) -> float | None:
    value = _text_field(row, keys)
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).replace(",", "").replace("%", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))
