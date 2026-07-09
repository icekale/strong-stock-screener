from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Iterable

from app.models import (
    SectorReplicaChartSeries,
    SectorReplicaMode,
    SectorReplicaPlate,
    SectorReplicaQxLive,
    SectorReplicaRadarResponse,
    SectorReplicaStockRow,
    SectorWorkbenchResponse,
    SectorWorkbenchSeries,
    SectorWorkbenchStock,
    SectorWorkbenchTheme,
    StrongStockSourceStatus,
)


def build_reference_time_axis() -> list[str]:
    return [
        *_minute_labels(start_hour=9, start_minute=15, end_hour=11, end_minute=30),
        *_minute_labels(start_hour=13, start_minute=0, end_hour=15, end_minute=0),
    ]


def build_sector_radar_replica_response(
    *,
    workbench: SectorWorkbenchResponse,
    mode: SectorReplicaMode,
    selected_codes: list[str],
    sampled_at: datetime,
) -> SectorReplicaRadarResponse:
    axis = build_reference_time_axis()
    plates = [_plate_from_theme(theme, mode=mode) for theme in workbench.themes]
    name_by_code = {_board_code(theme.name): theme.name for theme in workbench.themes}
    selected = _selected_codes(selected_codes, plates)
    legend = [name_by_code[code] for code in selected if code in name_by_code]
    chart_series = [_chart_series_for_name(name, workbench.series, axis) for name in legend]
    return SectorReplicaRadarResponse(
        mode=mode,
        trade_date=workbench.trade_date,
        axis=axis,
        qxlive=_qxlive_payload(workbench, axis),
        plates=plates,
        checkplate=selected,
        legend=legend,
        series=chart_series,
        stocks=build_sector_replica_stock_rows(
            workbench,
            board_code=selected[0] if selected else None,
        ),
        related_tags=workbench.related_tags,
        source_status=[*workbench.source_status, _replica_status(mode)],
        generated_at=sampled_at.isoformat(timespec="seconds"),
    )


def build_sector_replica_stock_rows(
    workbench: SectorWorkbenchResponse,
    *,
    board_code: str | None,
    sub_theme: str | None = None,
) -> list[SectorReplicaStockRow]:
    board_name = _theme_name_for_code(workbench.themes, board_code)
    rows = [
        _stock_row(stock)
        for stock in workbench.stocks
        if _stock_matches(stock, board_name=board_name, sub_theme=sub_theme)
    ]
    return sorted(rows, key=_stock_sort_key, reverse=True)


def _minute_labels(*, start_hour: int, start_minute: int, end_hour: int, end_minute: int) -> list[str]:
    labels: list[str] = []
    total = start_hour * 60 + start_minute
    end = end_hour * 60 + end_minute
    while total <= end:
        labels.append(f"{total // 60:02d}:{total % 60:02d}")
        total += 1
    return labels


def _plate_from_theme(theme: SectorWorkbenchTheme, *, mode: SectorReplicaMode) -> SectorReplicaPlate:
    raw_value = theme.main_flow_cny if mode == "main_flow" else theme.strength_score
    value = float(raw_value or 0)
    return SectorReplicaPlate(
        code=_board_code(theme.name),
        name=theme.name,
        val=round(value, 2),
        ztcount=theme.limit_up_count,
        display_value=_money_text(value) if mode == "main_flow" else str(round(value)),
    )


def _selected_codes(selected_codes: list[str], plates: list[SectorReplicaPlate]) -> list[str]:
    available = {plate.code for plate in plates}
    selected = [code for code in selected_codes if code in available]
    if selected:
        return selected
    return [plate.code for plate in plates[:5]]


def _chart_series_for_name(
    name: str,
    source_series: Iterable[SectorWorkbenchSeries],
    axis: list[str],
) -> SectorReplicaChartSeries:
    points_by_time: dict[str, float] = {}
    for series in source_series:
        if series.name != name:
            continue
        points_by_time = {point.time: point.value for point in series.points}
        break
    return SectorReplicaChartSeries(
        name=name,
        data=[points_by_time.get(time_text) for time_text in axis],
    )


def _qxlive_payload(workbench: SectorWorkbenchResponse, axis: list[str]) -> SectorReplicaQxLive:
    latest_strength = max((theme.strength_score for theme in workbench.themes), default=0)
    qx_value = min(100, max(0, round(latest_strength / 100, 2)))
    limit_up_count = sum(theme.limit_up_count for theme in workbench.themes)
    max_board = max((stock.board_count for stock in workbench.stocks), default=0)
    rising_count = sum(1 for stock in workbench.stocks if (stock.pct_change or 0) > 0)
    falling_count = sum(1 for stock in workbench.stocks if (stock.pct_change or 0) < 0)
    main_flow_yi = round(sum(theme.main_flow_cny or 0 for theme in workbench.themes) / 100_000_000, 2)
    series = {
        "QX": _filled(axis, qx_value),
        "ZT": _filled(axis, limit_up_count),
        "DT": _filled(axis, 0),
        "KQXY": _filled(axis, falling_count * 10),
        "HSLN": _filled(axis, main_flow_yi),
        "LBGD": _filled(axis, max_board),
        "SZ": _filled(axis, rising_count),
        "XD": _filled(axis, falling_count),
        "PB": _filled(axis, 0),
        "ZTBX": _filled(axis, 0),
        "LBBX": _filled(axis, 0),
        "JRLN": _filled(axis, 0),
        "KQB": _filled(axis, falling_count),
    }
    return SectorReplicaQxLive(
        Aaxis=axis,
        zflist=[0 for _ in axis],
        series=series,
    )


def _filled(axis: list[str], value: float | int) -> list[float | None]:
    return [float(value) for _ in axis]


def _stock_matches(stock: SectorWorkbenchStock, *, board_name: str | None, sub_theme: str | None) -> bool:
    if board_name and board_name not in stock.themes and board_name != stock.industry:
        return False
    if sub_theme and sub_theme not in stock.themes and sub_theme != stock.industry:
        return False
    return True


def _stock_row(stock: SectorWorkbenchStock) -> SectorReplicaStockRow:
    code = _plain_code(stock.symbol)
    leader_tag = _leader_tag(stock)
    board_label = _board_label(stock)
    buy_ratio = _estimated_buy_ratio(stock)
    auction_volume_ratio = _estimated_auction_volume_ratio(stock)
    circulating_value = _estimated_circulating_value(stock)
    compat_row = [
        code,
        stock.name,
        stock.pct_change,
        stock.auction_pct_change,
        None,
        None,
        "+".join(stock.themes[:2]),
        circulating_value,
        stock.turnover_cny,
        None,
        None,
        None,
        board_label,
        leader_tag,
        buy_ratio,
        auction_volume_ratio,
        stock.auction_turnover_cny,
        stock.seal_amount_cny,
    ]
    return SectorReplicaStockRow(
        symbol=stock.symbol,
        code=code,
        name=stock.name,
        pct_change=stock.pct_change,
        turnover_cny=stock.turnover_cny,
        circulating_value_cny=circulating_value,
        board_label=board_label,
        auction_pct_change=stock.auction_pct_change,
        auction_amount_cny=stock.auction_turnover_cny,
        auction_volume_ratio=auction_volume_ratio,
        buy_ratio_pct=buy_ratio,
        seal_amount_cny=stock.seal_amount_cny,
        leader_tag=leader_tag,
        themes=stock.themes,
        industry=stock.industry,
        compat_row=compat_row,
    )


def _stock_sort_key(row: SectorReplicaStockRow) -> tuple[float, float, float, str]:
    return (
        row.pct_change or -999,
        row.seal_amount_cny or 0,
        row.turnover_cny or 0,
        row.symbol,
    )


def _theme_name_for_code(themes: list[SectorWorkbenchTheme], board_code: str | None) -> str | None:
    if not board_code:
        return None
    for theme in themes:
        if _board_code(theme.name) == board_code:
            return theme.name
    return None


def _board_code(name: str) -> str:
    normalized = name.strip().lower()
    aliases = {
        "cpo": "cpo",
        "机器人": "robot",
        "机器人概念": "robot",
        "芯片": "chip",
        "半导体": "semiconductor",
    }
    token = aliases.get(normalized)
    if token is None:
        ascii_token = "".join(ch for ch in normalized if ch.isascii() and ch.isalnum())
        token = ascii_token or f"cn-{hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:10]}"
    return f"theme:{token}"


def _plain_code(symbol: str) -> str:
    return symbol.split(".", 1)[0]


def _board_label(stock: SectorWorkbenchStock) -> str:
    if stock.board_count > 1:
        return f"{stock.board_count}连板"
    if stock.board_count == 1 or stock.limit_up:
        return "首板"
    return "--"


def _leader_tag(stock: SectorWorkbenchStock) -> str | None:
    for flag in stock.risk_flags:
        if flag.startswith("龙"):
            return flag
    return None


def _estimated_buy_ratio(stock: SectorWorkbenchStock) -> float | None:
    if stock.pct_change is None:
        return None
    return round(min(99.0, max(1.0, 50 + stock.pct_change * 1.2)), 2)


def _estimated_auction_volume_ratio(stock: SectorWorkbenchStock) -> float | None:
    if not stock.auction_turnover_cny or not stock.turnover_cny:
        return None
    return round(stock.auction_turnover_cny / stock.turnover_cny, 2)


def _estimated_circulating_value(stock: SectorWorkbenchStock) -> float | None:
    if not stock.turnover_cny or not stock.turnover_rate:
        return None
    if stock.turnover_rate <= 0:
        return None
    return round(stock.turnover_cny / (stock.turnover_rate / 100), 2)


def _money_text(value: float) -> str:
    abs_value = abs(value)
    if abs_value >= 100_000_000:
        text = f"{value / 100_000_000:.1f}亿"
    elif abs_value >= 10_000:
        text = f"{value / 10_000:.0f}万"
    else:
        text = f"{value:.0f}"
    return text.replace("-0.0", "0.0")


def _replica_status(mode: SectorReplicaMode) -> StrongStockSourceStatus:
    detail = "按短线侠 qxlive 兼容结构输出；板块强度为自有校准分"
    if mode == "main_flow":
        detail = "按短线侠 qxlive 兼容结构输出；主力流入优先真实资金流，缺失时使用成交额估算"
    return StrongStockSourceStatus(
        source="短线侠兼容板块雷达",
        status="success",
        detail=detail,
    )
