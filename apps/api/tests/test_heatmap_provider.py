from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

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


def _baseline_with_fallback_quotes() -> list[HeatmapBaselineStock]:
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
            fallback_price=25.19,
            fallback_change_pct=-0.67,
            fallback_turnover_cny=50_000_000,
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
            fallback_price=41.5,
            fallback_change_pct=1.25,
            fallback_turnover_cny=35_000_000,
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


class _FakeEastmoneyResponse:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"data": {"diff": self.rows}}


class _FakeEastmoneyClient:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def get(self, *args: object, **kwargs: object) -> _FakeEastmoneyResponse:
        return _FakeEastmoneyResponse(self.rows)

    def close(self) -> None:
        return None


class _FakeHeatmapFallbackClient:
    def __init__(self, tencent_payload: str) -> None:
        self.tencent_payload = tencent_payload

    def get(self, url: str, *args: object, **kwargs: object) -> object:
        if "push2.eastmoney.com" in url:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        if "qt.gtimg.cn" in url:
            return _FakeTencentHeatmapResponse(self.tencent_payload)
        raise AssertionError(f"unexpected url: {url}")

    def close(self) -> None:
        return None


class _FakeTencentHeatmapResponse:
    def __init__(self, payload: str) -> None:
        self.content = payload.encode("gbk")

    def raise_for_status(self) -> None:
        return None


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


def test_heatmap_provider_filters_cap_bucket_markets_and_uses_plan_labels() -> None:
    provider = HeatmapProvider(
        baseline_stocks=_baseline(),
        quote_loader=lambda symbols: _quote_snapshot(),
        summary_loader=_summary_snapshot,
        now=_fixed_now,
    )

    overview = provider.get_overview(period="day")
    counts = {item.market: item.stock_count for item in overview.markets}
    labels = {item.market: item.name for item in overview.markets}
    hs300 = provider.get_treemap(
        market="hs300",
        period="day",
        size_mode="market_cap",
        trend="all",
        board=None,
        limit=20,
    )
    zza500 = provider.get_treemap(
        market="zza500",
        period="day",
        size_mode="market_cap",
        trend="all",
        board=None,
        limit=20,
    )

    assert labels["zza500"] == "中证 A500"
    assert counts["hs300"] == 1
    assert counts["zza500"] == 1
    assert hs300.summary.stock_count == 1
    assert hs300.nodes[0].children[0].symbol == "600000.SH"
    assert zza500.summary.stock_count == 1
    assert zza500.nodes[0].children[0].symbol == "603690.SH"


def test_heatmap_provider_uses_seed_quote_values_when_live_quote_loader_fails(tmp_path: Path) -> None:
    data_dir = tmp_path / "heatmap"
    data_dir.mkdir()
    (data_dir / "market-heatmap-fallback.json").write_text(
        json.dumps(
            {
                "stocks": [
                    {
                        "code": "920123.BJ",
                        "exchange": "BJ",
                        "name": "芭薇股份",
                        "boardName": "美容护理",
                        "price": 12.78,
                        "changePct": 0.79,
                        "turnoverAmount": 56_000_000,
                        "totalMarketCap": 812_000_000,
                        "floatMarketCap": 812_000_000,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "market-heatmap-subboards.json").write_text(
        json.dumps(
            {
                "subboards": {
                    "920123.BJ": {
                        "sectorName": "美容护理",
                        "subBoardName": "化妆品",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    def failing_quote_loader(symbols: list[str]) -> HeatmapQuoteSnapshot:
        raise RuntimeError("network down")

    provider = HeatmapProvider(
        data_dir=data_dir,
        quote_loader=failing_quote_loader,
        summary_loader=_summary_snapshot,
        now=_fixed_now,
    )

    response = provider.get_treemap(
        market="all",
        period="day",
        size_mode="turnover",
        trend="all",
        board=None,
        limit=20,
    )
    child = response.nodes[0].children[0]

    assert child.price == 12.78
    assert child.change_pct == 0.79
    assert child.turnover_cny == 56_000_000
    assert response.nodes[0].value == 56_000_000


def test_heatmap_provider_maps_eastmoney_bj_rows_to_bj_symbols() -> None:
    provider = HeatmapProvider(
        baseline_stocks=_baseline(),
        quote_loader=lambda symbols: _quote_snapshot(),
        summary_loader=_summary_snapshot,
        now=_fixed_now,
    )

    assert provider._symbol_from_eastmoney_row({"f12": "920123", "f13": "0"}) == "920123.BJ"
    assert provider._symbol_from_eastmoney_row({"f12": "430047", "f13": "0"}) == "430047.BJ"


def test_heatmap_provider_empty_filter_does_not_borrow_summary_turnover() -> None:
    provider = HeatmapProvider(
        baseline_stocks=_baseline(),
        quote_loader=lambda symbols: _quote_snapshot(),
        summary_loader=_summary_snapshot,
        now=_fixed_now,
    )

    response = provider.get_treemap(
        market="all",
        period="day",
        size_mode="turnover",
        trend="all",
        board="不存在的板块",
        limit=20,
    )

    assert response.summary.stock_count == 0
    assert response.summary.board_count == 0
    assert response.nodes == []
    assert response.summary.turnover_cny == 0


def test_heatmap_provider_marks_empty_eastmoney_quotes_failed_and_fills_fallback() -> None:
    provider = HeatmapProvider(
        baseline_stocks=_baseline_with_fallback_quotes(),
        summary_loader=_summary_snapshot,
        now=_fixed_now,
        http_client=_FakeEastmoneyClient([]),
    )

    response = provider.get_quotes(market="all", period="day")

    assert set(response.quotes) == {"603690.SH", "300475.SZ"}
    assert response.quotes["603690.SH"].price == 25.19
    assert response.quotes["300475.SZ"].change_pct == 1.25
    assert any(status.source == "东方财富热图行情" and status.status == "failed" for status in response.source_status)
    assert not all(status.status == "success" for status in response.source_status)


def test_heatmap_provider_marks_partial_eastmoney_quotes_stale_and_fills_missing_quotes() -> None:
    provider = HeatmapProvider(
        baseline_stocks=_baseline_with_fallback_quotes(),
        summary_loader=_summary_snapshot,
        now=_fixed_now,
        http_client=_FakeEastmoneyClient(
            [
                {
                    "f2": 28.4,
                    "f3": 3.2,
                    "f6": 120_000_000,
                    "f12": "603690",
                    "f13": "1",
                    "f25": 30.5,
                    "f109": 8.1,
                    "f110": 12.4,
                    "f124": 1_783_392_200,
                }
            ]
        ),
    )

    response = provider.get_quotes(market="all", period="day")

    assert set(response.quotes) == {"603690.SH", "300475.SZ"}
    assert response.quotes["603690.SH"].price == 28.4
    assert response.quotes["300475.SZ"].price == 41.5
    assert response.quotes["300475.SZ"].turnover_cny == 35_000_000
    assert any(status.source == "东方财富热图行情" and status.status == "stale" for status in response.source_status)


def test_heatmap_provider_falls_back_to_tencent_quotes_when_eastmoney_disconnects() -> None:
    values = [""] * 88
    values[1] = "农业银行"
    values[2] = "601288"
    values[3] = "6.16"
    values[30] = "20260708152807"
    values[32] = "1.82"
    values[37] = "270733"
    payload = f'v_sh601288="{"~".join(values)}";'
    provider = HeatmapProvider(
        baseline_stocks=[
            HeatmapBaselineStock(
                symbol="601288.SH",
                code="601288",
                name="农业银行",
                exchange="SH",
                market="sse",
                industry="银行",
                sub_industry="国有大型银行",
                circulating_market_cap_cny=2_100_000_000_000,
                total_market_cap_cny=2_100_000_000_000,
                fallback_price=7.0,
                fallback_change_pct=0.0,
            )
        ],
        summary_loader=_summary_snapshot,
        now=_fixed_now,
        http_client=_FakeHeatmapFallbackClient(payload),
    )

    response = provider.get_treemap(
        market="all",
        period="day",
        size_mode="market_cap",
        trend="all",
        board=None,
        limit=20,
    )
    child = response.nodes[0].children[0]

    assert child.price == 6.16
    assert child.change_pct == 1.82
    assert child.turnover_cny == 2_707_330_000
    assert child.quote_time == "2026-07-08T15:28:07+08:00"
    assert any(status.source == "东方财富热图行情" and status.status == "failed" for status in response.source_status)
    assert any(status.source == "腾讯财经" and status.status == "success" for status in response.source_status)
    assert not any(status.source == "热图内置样本" for status in response.source_status)
