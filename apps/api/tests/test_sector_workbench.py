from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.models import MarketRankingItem, MarketRankingsResponse
from app.services.sector_workbench_store import SectorWorkbenchSampleStore
from app.services.sector_workbench import build_sector_workbench_response


def test_sector_workbench_prefers_theme_rows_over_industry_fallback() -> None:
    response = build_sector_workbench_response(
        rankings=_rankings(),
        limit_up_rows=[
            {
                "代码": "603690.SH",
                "名称": "至纯科技",
                "所属概念": "CPO;半导体设备",
                "连续涨停天数": 2,
                "封单金额": 12000,
            },
            {
                "代码": "300475.SZ",
                "名称": "香农芯创",
                "所属概念": "存储芯片;半导体",
                "连续涨停天数": 1,
                "封单金额": 8000,
            },
        ],
        mode="strength",
        scope="auto",
        selected=[],
        limit=10,
        stock_limit=10,
        sampled_at=datetime(2026, 7, 3, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert response.scope == "theme"
    assert response.mode == "strength"
    assert response.themes[0].name == "CPO"
    assert response.themes[0].limit_up_count == 1
    assert response.themes[0].leader == "至纯科技"
    assert response.selected_themes[:3] == ["CPO", "半导体设备", "存储芯片"]
    assert response.series[0].metric == "strength"
    assert response.series[0].points[0].time == "10:30"
    assert response.stocks[0].themes
    assert response.stocks[0].board_count == 2
    assert response.source_status[0].status == "success"


def test_sector_workbench_falls_back_to_industry_when_theme_rows_are_missing() -> None:
    response = build_sector_workbench_response(
        rankings=_rankings(),
        limit_up_rows=[],
        mode="main_flow",
        scope="auto",
        selected=["半导体"],
        limit=10,
        stock_limit=10,
        sampled_at=datetime(2026, 7, 3, 10, 31, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert response.scope == "industry"
    assert response.mode == "main_flow"
    assert response.themes[0].name == "半导体"
    assert response.themes[0].flow_status == "estimated"
    assert response.selected_themes == ["半导体"]
    assert response.series[0].metric == "main_flow"
    assert response.series[0].points[0].time == "10:31"
    assert response.stocks[0].industry == "半导体"
    assert response.source_status[0].status == "success"
    assert "行业兜底" in response.source_status[0].detail


def test_sector_workbench_store_dedupes_same_minute_and_builds_series(tmp_path: Path) -> None:
    store = SectorWorkbenchSampleStore(tmp_path)
    response = build_sector_workbench_response(
        rankings=_rankings(),
        limit_up_rows=[
            {
                "代码": "603690.SH",
                "名称": "至纯科技",
                "所属概念": "CPO;半导体设备",
                "连续涨停天数": 2,
                "封单金额": 12000,
            }
        ],
        mode="strength",
        scope="auto",
        selected=["CPO"],
        limit=10,
        stock_limit=10,
        sampled_at=datetime(2026, 7, 3, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    store.append(response)
    store.append(response)

    series = store.series_for(
        trade_date=response.trade_date,
        mode="strength",
        scope="theme",
        selected=response.selected_themes,
        metric="strength",
    )

    assert len(series) == 1
    assert series[0].name == "CPO"
    assert len(series[0].points) == 1
    assert series[0].points[0].time == "10:30"


def _rankings() -> MarketRankingsResponse:
    items = [
        MarketRankingItem(
            symbol="603690.SH",
            name="至纯科技",
            industry="半导体",
            pct_change=10.01,
            current_pct_change=10.01,
            turnover_cny=820_000_000,
            turnover_rate=8.2,
            quote_time="2026-07-03 10:30:00",
        ),
        MarketRankingItem(
            symbol="300475.SZ",
            name="香农芯创",
            industry="半导体",
            pct_change=7.12,
            current_pct_change=7.12,
            turnover_cny=560_000_000,
            turnover_rate=6.1,
            quote_time="2026-07-03 10:30:00",
        ),
        MarketRankingItem(
            symbol="600900.SH",
            name="长江电力",
            industry="电力",
            pct_change=1.25,
            current_pct_change=1.25,
            turnover_cny=300_000_000,
            turnover_rate=0.8,
            quote_time="2026-07-03 10:30:00",
        ),
    ]
    return MarketRankingsResponse(
        trade_date="2026-07-03",
        pct_change_rank=items,
        turnover_rank=list(reversed(items)),
    )
