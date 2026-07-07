from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    HeatmapBoardNode,
    HeatmapOverviewItem,
    HeatmapOverviewResponse,
    HeatmapQuoteItem,
    HeatmapQuotesResponse,
    HeatmapStockNode,
    HeatmapSummary,
    HeatmapTreemapResponse,
    StrongStockSourceStatus,
)


class FakeHeatmapProvider:
    def get_treemap(self, *, market, period, size_mode, trend, board, limit):
        return HeatmapTreemapResponse(
            market=market,
            period=period,
            size_mode=size_mode,
            trend=trend,
            board=board,
            summary=HeatmapSummary(
                trade_date="2026-07-07",
                updated_at="2026-07-07T10:30:00+08:00",
                stock_count=1,
                board_count=1,
                advance_count=1,
                decline_count=0,
                unchanged_count=0,
                turnover_cny=120_000_000,
            ),
            nodes=[
                HeatmapBoardNode(
                    key="半导体",
                    name="半导体",
                    value=120_000_000,
                    stock_count=1,
                    advance_count=1,
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
                            turnover_cny=120_000_000,
                            value=120_000_000,
                        )
                    ],
                )
            ],
            source_status=[StrongStockSourceStatus(source="fake", status="success", detail="ok")],
            generated_at="2026-07-07T10:30:01+08:00",
        )

    def get_quotes(self, *, market, period):
        return HeatmapQuotesResponse(
            market=market,
            period=period,
            quotes={
                "603690.SH": HeatmapQuoteItem(
                    symbol="603690.SH",
                    price=28.4,
                    change_pct=3.2,
                    turnover_cny=120_000_000,
                )
            },
            source_status=[StrongStockSourceStatus(source="fake", status="success", detail="ok")],
            generated_at="2026-07-07T10:30:01+08:00",
        )

    def get_overview(self, *, period):
        return HeatmapOverviewResponse(
            period=period,
            markets=[
                HeatmapOverviewItem(
                    market="all",
                    name="全 A",
                    change_pct=1.2,
                    stock_count=1,
                    updated_at="2026-07-07T10:30:00+08:00",
                )
            ],
            source_status=[StrongStockSourceStatus(source="fake", status="success", detail="ok")],
            generated_at="2026-07-07T10:30:01+08:00",
        )


@pytest.fixture(autouse=True)
def restore_heatmap_provider():
    original = getattr(app.state, "heatmap_provider", None)
    had_original = hasattr(app.state, "heatmap_provider")
    try:
        yield
    finally:
        if had_original:
            app.state.heatmap_provider = original
        elif hasattr(app.state, "heatmap_provider"):
            del app.state.heatmap_provider


def test_heatmap_treemap_endpoint_returns_schema_and_filters() -> None:
    app.state.heatmap_provider = FakeHeatmapProvider()
    client = TestClient(app)
    response = client.get(
        "/api/heatmap/treemap?market=sse&period=day&size_mode=turnover&trend=rise&board=%E5%8D%8A%E5%AF%BC%E4%BD%93&limit=50"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "sse"
    assert payload["size_mode"] == "turnover"
    assert payload["trend"] == "rise"
    assert payload["board"] == "半导体"
    assert payload["nodes"][0]["children"][0]["symbol"] == "603690.SH"
    assert payload["source_status"][0]["status"] == "success"


def test_heatmap_rejects_invalid_period() -> None:
    app.state.heatmap_provider = FakeHeatmapProvider()
    client = TestClient(app)
    response = client.get("/api/heatmap/treemap?period=quarter")

    assert response.status_code == 422


def test_heatmap_quotes_and_overview_endpoints_return_source_status() -> None:
    app.state.heatmap_provider = FakeHeatmapProvider()
    client = TestClient(app)

    quotes = client.get("/api/heatmap/quotes?market=all&period=day")
    overview = client.get("/api/heatmap/overview?period=week")

    assert quotes.status_code == 200
    assert quotes.json()["quotes"]["603690.SH"]["change_pct"] == 3.2
    assert quotes.json()["source_status"][0]["status"] == "success"
    assert overview.status_code == 200
    assert overview.json()["markets"][0]["market"] == "all"
    assert overview.json()["source_status"][0]["status"] == "success"
