from __future__ import annotations

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import HeatmapBoardNode, HeatmapStockNode, HeatmapSummary, HeatmapTreemapResponse
from app.providers.heatmap import (
    HeatmapBaselineStock,
    HeatmapProvider,
    HeatmapQuoteSnapshot,
    HeatmapQuoteValue,
    HeatmapSummarySnapshot,
)


def test_heatmap_models_expose_source_status_and_stock_metrics() -> None:
    response = HeatmapTreemapResponse(
        market="all",
        period="day",
        size_mode="market_cap",
        trend="all",
        board=None,
        summary=HeatmapSummary(
            trade_date="2026-07-07",
            updated_at="2026-07-07T10:30:00+08:00",
            stock_count=1,
            board_count=1,
            advance_count=1,
            decline_count=0,
            unchanged_count=0,
            turnover_cny=120_000_000,
            previous_turnover_cny=100_000_000,
            turnover_change_pct=20,
        ),
        nodes=[
            HeatmapBoardNode(
                key="半导体",
                name="半导体",
                value=12_000_000_000,
                stock_count=1,
                advance_count=1,
                decline_count=0,
                unchanged_count=0,
                avg_change_pct=3.2,
                turnover_cny=120_000_000,
                children=[
                    HeatmapStockNode(
                        symbol="603690.SH",
                        code="603690",
                        name="至纯科技",
                        industry="半导体",
                        sub_industry="半导体设备",
                        exchange="SH",
                        market="sse",
                        price=28.4,
                        change_pct=3.2,
                        week_change_pct=8.1,
                        month_change_pct=12.4,
                        year_change_pct=30.5,
                        turnover_cny=120_000_000,
                        circulating_market_cap_cny=12_000_000_000,
                        total_market_cap_cny=15_000_000_000,
                        value=12_000_000_000,
                        quote_time="2026-07-07T10:30:00+08:00",
                    )
                ],
            )
        ],
        source_status=[{"source": "东方财富热图行情", "status": "success", "detail": "测试"}],
        generated_at="2026-07-07T10:30:01+08:00",
    )

    dumped = response.model_dump(mode="json")
    assert dumped["source_status"][0]["status"] == "success"
    assert dumped["nodes"][0]["children"][0]["symbol"] == "603690.SH"
    assert dumped["nodes"][0]["children"][0]["market"] == "sse"


def test_upstream_heatmap_license_seed_is_present() -> None:
    data_dir = Path(__file__).resolve().parents[1] / "app/data/heatmap"
    assert (data_dir / "market-heatmap-fallback.json").exists()
    assert (data_dir / "market-heatmap-subboards.json").exists()
    license_text = (data_dir / "LICENSE.a-share-heatmap").read_text(encoding="utf-8")
    assert "MIT License" in license_text
    assert "A-Share Heatmap contributors" in license_text


def _fixed_now() -> datetime:
    return datetime(2026, 7, 7, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))


def _baseline() -> list[HeatmapBaselineStock]:
    return [
        HeatmapBaselineStock(
            symbol="603690.SH",
            code="603690",
            name="至纯科技",
            exchange="SH",
            market="sse",
            industry="半导体",
            sub_industry="半导体设备",
            circulating_market_cap_cny=12_000_000_000,
            total_market_cap_cny=15_000_000_000,
        ),
        HeatmapBaselineStock(
            symbol="300475.SZ",
            code="300475",
            name="香农芯创",
            exchange="SZ",
            market="cyb",
            industry="半导体",
            sub_industry="存储芯片",
            circulating_market_cap_cny=8_000_000_000,
            total_market_cap_cny=10_000_000_000,
        ),
        HeatmapBaselineStock(
            symbol="600000.SH",
            code="600000",
            name="浦发银行",
            exchange="SH",
            market="sse",
            industry="银行",
            sub_industry="股份制银行",
            circulating_market_cap_cny=180_000_000_000,
            total_market_cap_cny=190_000_000_000,
        ),
    ]


def _quote_snapshot() -> HeatmapQuoteSnapshot:
    return HeatmapQuoteSnapshot(
        updated_at="2026-07-07T10:30:00+08:00",
        values={
            "603690.SH": HeatmapQuoteValue(
                price=28.4,
                changes={"day": 3.2, "week": 8.1, "month": 12.4, "year": 30.5},
                turnover_cny=120_000_000,
                quote_time="2026-07-07T10:30:00+08:00",
            ),
            "300475.SZ": HeatmapQuoteValue(
                price=54.2,
                changes={"day": -1.8, "week": 2.1, "month": 7.4, "year": 18.0},
                turnover_cny=90_000_000,
                quote_time="2026-07-07T10:30:00+08:00",
            ),
            "600000.SH": HeatmapQuoteValue(
                price=9.8,
                changes={"day": 0.0, "week": -1.0, "month": 1.2, "year": 6.0},
                turnover_cny=60_000_000,
                quote_time="2026-07-07T10:30:00+08:00",
            ),
        },
        source_status=[{"source": "fake quotes", "status": "success", "detail": "3 rows"}],
    )


def _summary_snapshot() -> HeatmapSummarySnapshot:
    return HeatmapSummarySnapshot(
        trade_date="2026-07-07",
        updated_at="2026-07-07T10:30:00+08:00",
        advance_count=1,
        decline_count=1,
        unchanged_count=1,
        turnover_cny=270_000_000,
        previous_turnover_cny=300_000_000,
        source_status=[{"source": "fake summary", "status": "success", "detail": "ok"}],
    )


def test_heatmap_provider_builds_board_nodes_from_quotes() -> None:
    provider = HeatmapProvider(
        baseline_stocks=_baseline(),
        quote_loader=lambda symbols: _quote_snapshot(),
        summary_loader=_summary_snapshot,
        now=_fixed_now,
    )

    response = provider.get_treemap(
        market="all",
        period="day",
        size_mode="market_cap",
        trend="all",
        board=None,
        limit=20,
    )

    assert response.summary.stock_count == 3
    assert response.summary.board_count == 2
    assert response.nodes[0].name == "银行"
    assert response.nodes[0].value == 180_000_000_000
    assert response.nodes[1].name == "半导体"
    assert {child.symbol for child in response.nodes[1].children} == {"603690.SH", "300475.SZ"}
    assert response.source_status[0].status == "success"


def test_heatmap_provider_applies_market_board_trend_and_size_filters() -> None:
    provider = HeatmapProvider(
        baseline_stocks=_baseline(),
        quote_loader=lambda symbols: _quote_snapshot(),
        summary_loader=_summary_snapshot,
        now=_fixed_now,
    )

    response = provider.get_treemap(
        market="sse",
        period="day",
        size_mode="turnover",
        trend="rise",
        board="半导体",
        limit=20,
    )

    assert response.summary.stock_count == 1
    assert response.nodes[0].name == "半导体"
    assert response.nodes[0].value == 120_000_000
    assert response.nodes[0].children[0].symbol == "603690.SH"


def test_heatmap_provider_returns_fallback_status_when_live_quote_loader_fails() -> None:
    def failing_quote_loader(symbols: list[str]) -> HeatmapQuoteSnapshot:
        raise RuntimeError("network down")

    provider = HeatmapProvider(
        baseline_stocks=_baseline(),
        quote_loader=failing_quote_loader,
        summary_loader=_summary_snapshot,
        now=_fixed_now,
    )

    response = provider.get_treemap(
        market="all",
        period="day",
        size_mode="market_cap",
        trend="all",
        board=None,
        limit=20,
    )

    assert response.nodes
    assert any(status.source == "东方财富热图行情" and status.status == "failed" for status in response.source_status)
    assert any(status.source == "热图内置样本" and status.status == "stale" for status in response.source_status)
