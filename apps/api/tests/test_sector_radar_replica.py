from __future__ import annotations

import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import (
    SectorWorkbenchPoint,
    SectorWorkbenchResponse,
    SectorWorkbenchSeries,
    SectorWorkbenchStock,
    SectorWorkbenchTheme,
    StrongStockSourceStatus,
)
from app.services.sector_radar_replica import (
    build_reference_time_axis,
    build_sector_radar_replica_response,
    build_sector_replica_stock_rows,
)


def test_replica_response_uses_qxlive_shape_and_selected_board_series() -> None:
    response = build_sector_radar_replica_response(
        workbench=_workbench_response(),
        mode="strength",
        selected_codes=["theme:cpo"],
        sampled_at=datetime(2026, 7, 9, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert response.result == "success"
    assert response.checkplate == ["theme:cpo"]
    assert response.legend == ["CPO"]
    assert [item.name for item in response.plates][:2] == ["CPO", "机器人"]
    assert response.plates[0].ztcount == 2
    assert response.series[0].name == "CPO"
    assert response.series[0].type == "line"
    assert response.series[0].showSymbol is False
    assert response.qxlive.Aaxis[:3] == ["09:15", "09:16", "09:17"]
    assert response.qxlive.series["QX"]


def test_replica_time_axis_contains_reference_session_labels() -> None:
    axis = build_reference_time_axis()

    assert axis[:3] == ["09:15", "09:16", "09:17"]
    assert "11:30" in axis
    assert "13:00" in axis
    assert axis[-1] == "15:00"
    assert "11:31" not in axis
    assert "12:59" not in axis


def test_replica_stock_rows_keep_reference_column_order() -> None:
    rows = build_sector_replica_stock_rows(_workbench_response(), board_code="theme:cpo")

    first = rows[0]
    assert first.compat_row[0] == "603690"
    assert first.compat_row[1] == "至纯科技"
    assert first.compat_row[2] == 10.0
    assert first.compat_row[8] == 320_000_000
    assert first.compat_row[12] == "2连板"
    assert first.compat_row[13] == "龙一"
    assert first.compat_row[17] == 120_000_000


def test_replica_main_flow_displays_money_values_and_estimated_status() -> None:
    response = build_sector_radar_replica_response(
        workbench=_workbench_response(),
        mode="main_flow",
        selected_codes=[],
        sampled_at=datetime(2026, 7, 9, 10, 31, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert response.mode == "main_flow"
    assert response.plates[0].display_value == "1.6亿"
    assert response.checkplate[:2] == ["theme:cpo", "theme:robot"]
    assert any(item.source == "短线侠兼容板块雷达" and item.status == "success" for item in response.source_status)


def test_replica_board_codes_are_stable_for_unknown_chinese_theme_names() -> None:
    workbench = _workbench_response()
    workbench.themes.append(
        SectorWorkbenchTheme(
            name="先进封装",
            scope="theme",
            limit_up_count=1,
            strength_score=1200,
            main_flow_cny=30_000_000,
            turnover_cny=90_000_000,
            change_pct=2.1,
            leader="封装一号",
            member_count=1,
            source="测试题材",
            flow_status="estimated",
        )
    )

    response = build_sector_radar_replica_response(
        workbench=workbench,
        mode="strength",
        selected_codes=[],
        sampled_at=datetime(2026, 7, 9, 10, 32, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    expected = hashlib.sha1("先进封装".encode("utf-8")).hexdigest()[:10]
    assert response.plates[-1].code == f"theme:cn-{expected}"


def _workbench_response() -> SectorWorkbenchResponse:
    sampled_at = "2026-07-09T10:30:00+08:00"
    return SectorWorkbenchResponse(
        scope="theme",
        mode="strength",
        trade_date="2026-07-09",
        themes=[
            SectorWorkbenchTheme(
                name="CPO",
                scope="theme",
                limit_up_count=2,
                strength_score=7875,
                main_flow_cny=156_000_000,
                turnover_cny=480_000_000,
                change_pct=5.8,
                leader="至纯科技",
                member_count=3,
                source="测试题材",
                flow_status="estimated",
            ),
            SectorWorkbenchTheme(
                name="机器人",
                scope="theme",
                limit_up_count=1,
                strength_score=3819,
                main_flow_cny=82_000_000,
                turnover_cny=260_000_000,
                change_pct=3.2,
                leader="机器人一号",
                member_count=2,
                source="测试题材",
                flow_status="estimated",
            ),
        ],
        selected_themes=["CPO", "机器人"],
        series=[
            SectorWorkbenchSeries(
                name="CPO",
                scope="theme",
                metric="strength",
                points=[
                    SectorWorkbenchPoint(time="09:15", value=1200, sampled_at=sampled_at),
                    SectorWorkbenchPoint(time="09:16", value=1800, sampled_at=sampled_at),
                    SectorWorkbenchPoint(time="10:30", value=7875, sampled_at=sampled_at),
                ],
            ),
            SectorWorkbenchSeries(
                name="机器人",
                scope="theme",
                metric="strength",
                points=[
                    SectorWorkbenchPoint(time="09:15", value=-500, sampled_at=sampled_at),
                    SectorWorkbenchPoint(time="09:16", value=600, sampled_at=sampled_at),
                    SectorWorkbenchPoint(time="10:30", value=3819, sampled_at=sampled_at),
                ],
            ),
        ],
        related_tags=["存储", "半导体设备", "电子气体"],
        stocks=[
            SectorWorkbenchStock(
                symbol="603690.SH",
                name="至纯科技",
                industry="半导体设备",
                themes=["CPO", "半导体设备"],
                pct_change=10.0,
                turnover_cny=320_000_000,
                turnover_rate=6.8,
                limit_up=True,
                board_count=2,
                auction_pct_change=5.67,
                auction_turnover_cny=116_000_000,
                seal_amount_cny=120_000_000,
                risk_flags=["龙一"],
            ),
            SectorWorkbenchStock(
                symbol="300001.SZ",
                name="机器人一号",
                industry="机器人",
                themes=["机器人"],
                pct_change=6.2,
                turnover_cny=180_000_000,
                turnover_rate=4.2,
                limit_up=False,
                board_count=0,
                auction_pct_change=3.1,
                auction_turnover_cny=22_000_000,
                seal_amount_cny=None,
            ),
        ],
        source_status=[
            StrongStockSourceStatus(
                source="测试板块源",
                status="success",
                detail="测试数据",
            )
        ],
        generated_at=sampled_at,
    )
