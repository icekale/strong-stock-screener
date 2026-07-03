from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.models import (
    MarketRankingItem,
    MarketRankingsResponse,
    SectorRadarItem,
    SectorRadarResponse,
    StrongStockCandidate,
)
from app.providers.tickflow import TickFlowIntradayBar
from app.services.sector_workbench_store import SectorThemeRowsStore, SectorWorkbenchSampleStore
from app.services.sector_workbench import (
    build_limit_up_theme_rows_from_candidates,
    build_sector_workbench_from_radar,
    build_sector_workbench_response,
)
from app.services.sector_workbench_intraday import build_sector_intraday_series


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
    assert response.themes[0].strength_score > 1_000
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
    assert response.themes[0].strength_score > 1_000
    assert response.themes[0].flow_status == "estimated"
    assert response.selected_themes == ["半导体"]
    assert response.series[0].metric == "main_flow"
    assert response.series[0].points[0].time == "10:31"
    assert response.stocks[0].industry == "半导体"
    assert response.source_status[0].status == "success"
    assert "行业兜底" in response.source_status[0].detail


def test_sector_workbench_builds_theme_rows_from_limit_up_candidates_and_concepts() -> None:
    rows = build_limit_up_theme_rows_from_candidates(
        candidates=[
            _candidate(
                "300001.SZ",
                "机器人一号",
                industry="自动化设备",
                board_note="涨停日期: 20260703; 连板数: 2; 封单金额: 12000",
            ),
            _candidate(
                "300002.SZ",
                "芯片一号",
                industry="半导体",
                board_note="涨停日期: 20260703; 连板数: 1; 封单金额: 8000",
            ),
            _candidate(
                "300003.SZ",
                "昨日一号",
                industry="消费电子",
                board_note="涨停日期: 20260702; 连板数: 1; 封单金额: 5000",
                last_limit_up_date="20260702",
            ),
        ],
        concept_provider=_FakeConceptProvider(
            {
                "300001.SZ": ["自动化设备", "机械设备", "昨日高振幅", "机器人概念", "减速器", "浙江板块"],
                "300002.SZ": ["半导体", "创业板综", "小盘股", "存储芯片", "先进封装", "广东板块"],
                "300003.SZ": ["消费电子", "汽车零部件", "AI眼镜"],
            }
        ),
        limit=20,
        trade_date="2026-07-03",
    )

    response = build_sector_workbench_response(
        rankings=_rankings(),
        limit_up_rows=rows,
        mode="strength",
        scope="auto",
        selected=[],
        limit=10,
        stock_limit=10,
        sampled_at=datetime(2026, 7, 3, 10, 32, tzinfo=ZoneInfo("Asia/Shanghai")),
        theme_source="东财 slist 概念归属",
    )

    assert response.scope == "theme"
    assert response.themes[0].limit_up_count > 0
    assert "机器人概念" in [item.name for item in response.themes]
    assert "存储芯片" in [item.name for item in response.themes]
    assert "AI眼镜" not in [item.name for item in response.themes]
    assert "自动化设备" not in [item.name for item in response.themes]
    assert "机械设备" not in [item.name for item in response.themes]
    assert "昨日高振幅" not in [item.name for item in response.themes]
    assert "创业板综" not in [item.name for item in response.themes]
    assert "小盘股" not in [item.name for item in response.themes]
    assert "浙江板块" not in [item.name for item in response.themes]
    assert response.source_status[0].source == "东财 slist 概念归属"


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


def test_sector_theme_rows_store_persists_latest_theme_snapshot(tmp_path: Path) -> None:
    store = SectorThemeRowsStore(tmp_path)
    rows = [
        {
            "代码": "300001.SZ",
            "名称": "机器人一号",
            "所属概念": "机器人概念;减速器",
            "连续涨停天数": 2,
            "封单金额": 12000,
        }
    ]
    store.save(
        trade_date="2026-07-03",
        rows=rows,
        status_source="东财 slist 概念归属",
        status_detail="后台补齐 1 只股票题材",
    )

    loaded_rows, status = store.load("2026-07-03")

    assert loaded_rows == rows
    assert status is not None
    assert status.source == "东财 slist 概念归属"
    assert status.status == "success"
    assert "后台补齐" in status.detail


def test_sector_workbench_store_ignores_legacy_percent_strength_samples(tmp_path: Path) -> None:
    store = SectorWorkbenchSampleStore(tmp_path)
    (tmp_path / "2026-07-03.json").write_text(
        """
        {
          "samples": [
            {
              "trade_date": "2026-07-03",
              "mode": "strength",
              "scope": "industry",
              "name": "半导体",
              "metric": "strength",
              "time": "10:30",
              "value": 380,
              "sampled_at": "2026-07-03 10:30"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    series = store.series_for(
        trade_date="2026-07-03",
        mode="strength",
        scope="industry",
        selected=["半导体"],
        metric="strength",
    )

    assert series == []


def test_sector_workbench_store_ignores_stale_heat_unit_samples(tmp_path: Path) -> None:
    store = SectorWorkbenchSampleStore(tmp_path)
    (tmp_path / "2026-07-03.json").write_text(
        """
        {
          "samples": [
            {
              "trade_date": "2026-07-03",
              "schema_version": 3,
              "mode": "strength",
              "scope": "industry",
              "name": "自动化设备",
              "metric": "strength",
              "time": "10:30",
              "value": 435150.84,
              "sampled_at": "2026-07-03 10:30"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    series = store.series_for(
        trade_date="2026-07-03",
        mode="strength",
        scope="industry",
        selected=["自动化设备"],
        metric="strength",
    )

    assert series == []


def test_sector_workbench_can_fall_back_to_sector_radar_without_rankings() -> None:
    response = build_sector_workbench_from_radar(
        radar=SectorRadarResponse(
            trade_date="2026-07-03",
            capital_flow_status="estimated",
            flow_source="通达信MCP涨停概念集中度估算",
            inflow=[
                SectorRadarItem(
                    name="机器人",
                    source="通达信MCP涨停概念",
                    advance_count=5,
                    leader="涨幅一号",
                    net_flow_cny=500_000_000,
                    turnover_cny=1_200_000_000,
                    strength_score=88,
                )
            ],
            outflow=[],
        ),
        mode="strength",
        scope="auto",
        selected=[],
        limit=10,
        sampled_at=datetime(2026, 7, 3, 10, 32, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert response.scope == "theme"
    assert response.themes[0].name == "机器人"
    assert response.stocks == []
    assert response.series[0].points[0].time == "10:32"


def test_sector_intraday_series_rebuilds_strength_curve_from_tickflow_minutes() -> None:
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
        selected=["CPO"],
        limit=10,
        stock_limit=10,
        sampled_at=datetime(2026, 7, 3, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    series, status = build_sector_intraday_series(
        response=response,
        quote_provider=_FakeIntradayProvider(
            {
                "603690.SH": [
                    _bar("2026-07-03 09:30", close=10.2, amount=100_000_000, prev_close=10),
                    _bar("2026-07-03 09:31", close=10.5, amount=120_000_000, prev_close=10),
                ],
            }
        ),
        mode="strength",
        count=240,
    )

    assert status.status == "success"
    assert series[0].name == "CPO"
    assert [point.time for point in series[0].points] == ["09:30", "09:31"]
    assert series[0].points[1].value > series[0].points[0].value


def test_sector_intraday_series_rebuilds_estimated_main_flow_curve() -> None:
    response = build_sector_workbench_response(
        rankings=_rankings(),
        limit_up_rows=[],
        mode="main_flow",
        scope="auto",
        selected=["半导体"],
        limit=10,
        stock_limit=10,
        sampled_at=datetime(2026, 7, 3, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    series, status = build_sector_intraday_series(
        response=response,
        quote_provider=_FakeIntradayProvider(
            {
                "603690.SH": [
                    _bar("2026-07-03 09:30", close=10.2, amount=100_000_000, prev_close=10),
                    _bar("2026-07-03 09:31", close=10.5, amount=120_000_000, prev_close=10),
                ],
                "300475.SZ": [
                    _bar("2026-07-03 09:30", close=20.2, amount=80_000_000, prev_close=20),
                    _bar("2026-07-03 09:31", close=20.6, amount=90_000_000, prev_close=20),
                ],
            }
        ),
        mode="main_flow",
        count=240,
    )

    assert status.status == "success"
    assert series[0].name == "半导体"
    assert [point.time for point in series[0].points] == ["09:30", "09:31"]
    assert series[0].points[1].value > series[0].points[0].value


def test_sector_intraday_series_carries_forward_sparse_symbol_minutes() -> None:
    response = build_sector_workbench_response(
        rankings=_rankings(),
        limit_up_rows=[],
        mode="main_flow",
        scope="auto",
        selected=["半导体"],
        limit=10,
        stock_limit=10,
        sampled_at=datetime(2026, 7, 3, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    series, status = build_sector_intraday_series(
        response=response,
        quote_provider=_FakeIntradayProvider(
            {
                "603690.SH": [
                    _bar("2026-07-03 09:30", close=10.2, amount=100_000_000, prev_close=10),
                    _bar("2026-07-03 09:31", close=10.3, amount=100_000_000, prev_close=10),
                    _bar("2026-07-03 09:32", close=10.4, amount=100_000_000, prev_close=10),
                ],
                "300475.SZ": [
                    _bar("2026-07-03 09:30", close=20.2, amount=80_000_000, prev_close=20),
                    _bar("2026-07-03 09:32", close=20.6, amount=90_000_000, prev_close=20),
                ],
            }
        ),
        mode="main_flow",
        count=240,
    )

    assert status.status == "success"
    assert [point.time for point in series[0].points] == ["09:30", "09:31", "09:32"]
    assert series[0].points[1].value == 6_800_000
    assert series[0].points[2].value > series[0].points[1].value


def test_sector_intraday_strength_curve_uses_signed_heat_score_like_reference_chart() -> None:
    items = [
        MarketRankingItem(
            symbol=f"3000{index:02d}.SZ",
            name=f"强势{index}",
            industry="半导体",
            pct_change=5 + index / 10,
            current_pct_change=5 + index / 10,
            turnover_cny=200_000_000,
            turnover_rate=5,
            quote_time="2026-07-03 10:30:00",
        )
        for index in range(8)
    ]
    response = build_sector_workbench_response(
        rankings=MarketRankingsResponse(
            trade_date="2026-07-03",
            pct_change_rank=items,
            turnover_rank=items,
        ),
        limit_up_rows=[],
        mode="strength",
        scope="auto",
        selected=["半导体"],
        limit=10,
        stock_limit=10,
        sampled_at=datetime(2026, 7, 3, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    series, status = build_sector_intraday_series(
        response=response,
        quote_provider=_FakeIntradayProvider(
            {
                item.symbol: [
                    _bar("2026-07-03 09:30", close=10.5, amount=20_000_000, prev_close=10),
                ]
                for item in items
            }
        ),
        mode="strength",
        count=240,
    )

    assert status.status == "success"
    assert series[0].points[0].value > 50


def test_sector_intraday_strength_curve_can_drop_below_zero() -> None:
    response = build_sector_workbench_response(
        rankings=_rankings(),
        limit_up_rows=[],
        mode="strength",
        scope="auto",
        selected=["半导体"],
        limit=10,
        stock_limit=10,
        sampled_at=datetime(2026, 7, 3, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    series, status = build_sector_intraday_series(
        response=response,
        quote_provider=_FakeIntradayProvider(
            {
                "603690.SH": [
                    _bar("2026-07-03 09:30", close=9.8, amount=100_000_000, prev_close=10),
                ],
                "300475.SZ": [
                    _bar("2026-07-03 09:30", close=19.6, amount=80_000_000, prev_close=20),
                ],
            }
        ),
        mode="strength",
        count=240,
    )

    assert status.status == "success"
    assert series[0].points[0].value < 0


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


class _FakeIntradayProvider:
    source_name = "Fake TickFlow"

    def __init__(self, bars_by_symbol: dict[str, list[TickFlowIntradayBar]]) -> None:
        self.bars_by_symbol = bars_by_symbol
        self.requests: list[tuple[list[str], str, int]] = []

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        self.requests.append((symbols, period, count))
        return {symbol: self.bars_by_symbol.get(symbol, []) for symbol in symbols}


class _FakeConceptProvider:
    def __init__(self, tags_by_symbol: dict[str, list[str]]) -> None:
        self.tags_by_symbol = tags_by_symbol

    def get_concept_tags(self, symbol: str) -> list[str]:
        return self.tags_by_symbol.get(symbol, [])


def _candidate(
    symbol: str,
    name: str,
    *,
    industry: str,
    board_note: str,
    last_limit_up_date: str = "20260703",
) -> StrongStockCandidate:
    return StrongStockCandidate(
        symbol=symbol,
        name=name,
        industry=industry,
        limit_up_evidence=["20日内涨停", f"最近涨停: {last_limit_up_date}", "20日涨停次数: 1"],
        board_note=board_note,
    )


def _bar(
    value: str,
    *,
    close: float,
    amount: float,
    prev_close: float,
) -> TickFlowIntradayBar:
    timestamp = int(
        datetime.strptime(value, "%Y-%m-%d %H:%M")
        .replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        .timestamp()
        * 1000
    )
    return TickFlowIntradayBar(
        timestamp=timestamp,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=0,
        amount=amount,
        prev_close=prev_close,
    )
