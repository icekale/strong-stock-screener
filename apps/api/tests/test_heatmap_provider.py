from __future__ import annotations

from pathlib import Path

from app.models import HeatmapBoardNode, HeatmapStockNode, HeatmapSummary, HeatmapTreemapResponse


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
