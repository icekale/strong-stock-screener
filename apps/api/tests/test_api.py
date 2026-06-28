from pathlib import Path
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    KlineBar,
    MarketAdvanceDeclineSummary,
    MarketOverviewResponse,
    MarketSectorStrengthItem,
    MarketTurnoverSummary,
    StrongStockCandidate,
    StrongStockDataUnavailable,
    StrongStockSourceStatus,
)
from app.providers.watchlist import WatchlistSnapshot, WatchlistItem
from app.providers.tickflow import TickFlowIntradayBar, TickFlowQuote
from app.providers.news_risk import NegativeNewsRisk


def _bars(closes: list[float]) -> list[KlineBar]:
    bars: list[KlineBar] = []
    for index, close in enumerate(closes):
        previous = closes[index - 1] if index else close
        open_price = previous * 0.99 if close >= previous else previous * 1.02
        bars.append(
            KlineBar(
                date=f"2026-01-{(index % 28) + 1:02d}",
                open=round(open_price, 2),
                close=round(close, 2),
                high=round(max(open_price, close) * 1.03, 2),
                low=round(min(open_price, close) * 0.98, 2),
                volume=1_000_000 + index * 10_000,
            )
        )
    return bars


class FakeCandidateProvider:
    source_name = "fake候选池"

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        return [
            StrongStockCandidate(
                symbol="603890.SH",
                name="春秋电子",
                industry="消费电子",
                limit_up_evidence=["20日内涨停"],
                abnormal_status="triggered",
                abnormal_flags=["近期是否触发严重异动: 是"],
            ),
            StrongStockCandidate(
                symbol="002000.SZ",
                name="示例股份",
                limit_up_evidence=["20日内涨停"],
            ),
        ]


class IndustryClusterCandidateProvider:
    source_name = "fake板块候选池"

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        return [
            StrongStockCandidate(
                symbol="603890.SH",
                name="强势电子",
                industry="消费电子",
                limit_up_evidence=["20日内涨停"],
            ),
            StrongStockCandidate(
                symbol="603891.SH",
                name="弱势电子",
                industry="消费电子",
                limit_up_evidence=["20日内涨停"],
            ),
            StrongStockCandidate(
                symbol="603892.SH",
                name="跟随电子",
                industry="消费电子",
                limit_up_evidence=["20日内涨停"],
            ),
            StrongStockCandidate(
                symbol="002000.SZ",
                name="独立个股",
                industry="房地产",
                limit_up_evidence=["20日内涨停"],
            ),
        ]


class LargeCandidateProvider:
    source_name = "fake大候选池"

    def __init__(self, count: int) -> None:
        self.count = count

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        return [
            StrongStockCandidate(
                symbol=f"{600000 + index:06d}.SH",
                name=f"示例{index}",
                industry="测试行业",
                limit_up_evidence=["20日内涨停"],
            )
            for index in range(self.count)
        ]


class UnstableOrderCandidateProvider:
    source_name = "fake顺序漂移候选池"

    def __init__(self) -> None:
        self.calls = 0

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        self.calls += 1
        candidates = [
            StrongStockCandidate(
                symbol="600003.SH",
                name="示例三",
                industry="测试行业",
                limit_up_evidence=["20日内涨停"],
            ),
            StrongStockCandidate(
                symbol="600001.SH",
                name="示例一",
                industry="测试行业",
                limit_up_evidence=["20日内涨停"],
            ),
            StrongStockCandidate(
                symbol="600002.SH",
                name="示例二",
                industry="测试行业",
                limit_up_evidence=["20日内涨停"],
            ),
        ]
        if self.calls % 2 == 0:
            return list(reversed(candidates))
        return candidates


class RankedCandidateProvider:
    source_name = "fake有序候选池"
    preserve_candidate_order = True

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        return [
            StrongStockCandidate(
                symbol="600003.SH",
                name="优先三",
                industry="测试行业",
                limit_up_evidence=["20日内涨停", "最近涨停: 20260611", "20日涨停次数: 3"],
            ),
            StrongStockCandidate(
                symbol="600001.SH",
                name="优先一",
                industry="测试行业",
                limit_up_evidence=["20日内涨停", "最近涨停: 20260611", "20日涨停次数: 2"],
            ),
            StrongStockCandidate(
                symbol="600002.SH",
                name="优先二",
                industry="测试行业",
                limit_up_evidence=["20日内涨停", "最近涨停: 20260610", "20日涨停次数: 1"],
            ),
        ]


class AdvancedFilterCandidateProvider:
    source_name = "fake高级筛选候选池"

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        return [
            StrongStockCandidate(
                symbol="603890.SH",
                name="主板电子",
                industry="消费电子",
                limit_up_evidence=["20日内涨停"],
                total_market_cap_cny=12_000_000_000,
            ),
            StrongStockCandidate(
                symbol="300001.SZ",
                name="创业电子",
                industry="消费电子",
                limit_up_evidence=["20日内涨停"],
                total_market_cap_cny=12_000_000_000,
            ),
            StrongStockCandidate(
                symbol="688001.SH",
                name="科创半导体",
                industry="半导体",
                limit_up_evidence=["20日内涨停"],
                total_market_cap_cny=12_000_000_000,
            ),
            StrongStockCandidate(
                symbol="000001.SZ",
                name="超大银行",
                industry="银行",
                limit_up_evidence=["20日内涨停"],
                total_market_cap_cny=200_000_000_000,
            ),
        ]


class FailingCandidateProvider:
    source_name = "fake候选池"

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        raise StrongStockDataUnavailable("候选池数据源失败")


class UnavailableStatusCandidateProvider(FakeCandidateProvider):
    def status(self) -> StrongStockSourceStatus:
        return StrongStockSourceStatus(
            source=self.source_name,
            status="failed",
            detail="候选池不可用",
        )


class FakeKlineProvider:
    source_name = "fake K线"

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        if symbol == "002000.SZ":
            return _bars([20 - index * 0.05 for index in range(220)])
        return _bars([10 + index * 0.05 for index in range(220)])


class FakeCalibrationKlineProvider:
    source_name = "fake校准K线"

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        entry_close = 20 if symbol == "002000.SZ" else 10
        future_closes = [19, 19.4, 19.2, 18.8] if symbol == "002000.SZ" else [11, 10.5, 11.2, 11.6]
        return _calibration_bars(entry_close=entry_close, future_closes=future_closes)


def _calibration_bars(entry_close: float, future_closes: list[float]) -> list[KlineBar]:
    start = datetime(2025, 11, 24)
    closes = [entry_close for _ in range(66)] + future_closes
    bars: list[KlineBar] = []
    for index, close in enumerate(closes):
        bars.append(
            KlineBar(
                date=(start + timedelta(days=index)).strftime("%Y%m%d"),
                open=close,
                close=close,
                high=round(close * 1.02, 2),
                low=round(close * 0.98, 2),
                volume=1_000_000 + index,
            )
        )
    assert bars[65].date == "20260128"
    return bars


class IndustryClusterKlineProvider(FakeKlineProvider):
    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        if symbol == "603891.SH":
            return _bars([20 - index * 0.05 for index in range(220)])
        return _bars([10 + index * 0.05 for index in range(220)])


class CountingKlineProvider(FakeKlineProvider):
    def __init__(self) -> None:
        self.symbols: list[str] = []

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        self.symbols.append(symbol)
        return super().get_klines(symbol, count=count)


class FakeQuoteProvider:
    source_name = "TickFlow"

    def status(self):
        from app.models import StrongStockSourceStatus

        return StrongStockSourceStatus(source="TickFlow", status="missing_key", detail="TICKFLOW_API_KEY 未配置")


class FakeNewsRiskProvider:
    source_name = "fake新闻风险"

    def __init__(self) -> None:
        self.symbols: list[str] = []

    def get_negative_news_risk(self, symbol: str) -> NegativeNewsRisk:
        self.symbols.append(symbol)
        if symbol == "603890.SH":
            return NegativeNewsRisk(
                status="triggered",
                flags=["负面新闻待核验: 2026-06-12 春秋电子收到监管函（东方财富）"],
            )
        return NegativeNewsRisk(status="clear", flags=[])


class FakeLiveQuoteProvider:
    source_name = "TickFlow"

    def status(self) -> StrongStockSourceStatus:
        return StrongStockSourceStatus(source="TickFlow", status="success", detail="fake quotes")

    def get_quotes(self, symbols: list[str]) -> list[TickFlowQuote]:
        return [
            TickFlowQuote(
                symbol=symbol,
                name="春秋电子" if symbol == "603890.SH" else "示例股份",
                last_price=16.55 if symbol == "603890.SH" else 18.5,
                prev_close=15.26 if symbol == "603890.SH" else 20.0,
                open_price=16.3 if symbol == "603890.SH" else 19.1,
                high_price=16.8 if symbol == "603890.SH" else 19.4,
                low_price=16.0 if symbol == "603890.SH" else 18.2,
                pct_change=8.45 if symbol == "603890.SH" else -7.5,
                turnover_cny=360_000_000,
                volume=220_000,
                quote_time="2026-06-11T10:05:00+08:00",
            )
            for symbol in symbols
        ]

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        return {
            symbol: [
                TickFlowIntradayBar(
                    timestamp=1781141400000,
                    open=16.3,
                    high=16.4,
                    low=16.0,
                    close=16.2,
                    volume=12000,
                    amount=19_440_000,
                    prev_close=15.26,
                ),
                TickFlowIntradayBar(
                    timestamp=1781141460000,
                    open=16.2,
                    high=16.65,
                    low=16.2,
                    close=16.55,
                    volume=15000,
                    amount=24_825_000,
                    prev_close=15.26,
                ),
            ]
            for symbol in symbols
        }


class FakeGsgfConfirmQuoteProvider(FakeLiveQuoteProvider):
    def get_quotes(self, symbols: list[str]) -> list[TickFlowQuote]:
        return [
            TickFlowQuote(
                symbol=symbol,
                name="春秋电子",
                last_price=16.55,
                prev_close=15.26,
                open_price=16.2,
                high_price=16.56,
                low_price=16.0,
                pct_change=5.7,
                turnover_cny=360_000_000,
                volume=220_000,
                quote_time="2026-06-11T10:05:00+08:00",
            )
            for symbol in symbols
        ]


class FakeGsgfLowBuyQuoteProvider(FakeLiveQuoteProvider):
    def get_quotes(self, symbols: list[str]) -> list[TickFlowQuote]:
        return [
            TickFlowQuote(
                symbol=symbol,
                name="春秋电子",
                last_price=15.15,
                prev_close=15.26,
                open_price=14.5,
                high_price=15.2,
                low_price=14.4,
                pct_change=-0.72,
                turnover_cny=220_000_000,
                volume=180_000,
                quote_time="2026-06-11T10:05:00+08:00",
            )
            for symbol in symbols
        ]

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        return {
            symbol: [
                TickFlowIntradayBar(
                    timestamp=1781141400000,
                    open=14.8,
                    high=14.9,
                    low=14.4,
                    close=14.6,
                    volume=12000,
                    amount=17_520_000,
                    prev_close=15.26,
                ),
                TickFlowIntradayBar(
                    timestamp=1781141460000,
                    open=14.6,
                    high=15.2,
                    low=14.6,
                    close=15.15,
                    volume=15000,
                    amount=22_725_000,
                    prev_close=15.26,
                ),
            ]
            for symbol in symbols
        }


class FakeIfindHealthClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> object:
        self.calls.append({"url": url, **kwargs})

        class _Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> object:
                return {
                    "result": {
                        "tools": [
                            {
                                "name": "stock.profile",
                                "description": "A股基础资料",
                                "inputSchema": {"type": "object", "properties": {}},
                            }
                        ]
                    }
                }

        return _Response()


class FakeIfindResearchProvider:
    def get_stock_research(self, symbol: str):
        from app.models import StockResearchResponse

        return StockResearchResponse(
            symbol=symbol,
            source_status=[
                StrongStockSourceStatus(source="iFinD A股数据", status="success", detail="fake profile"),
                StrongStockSourceStatus(source="iFinD 新闻公告", status="success", detail="fake news"),
                StrongStockSourceStatus(source="iFinD 指数板块", status="success", detail="fake sector"),
            ],
            profile={"公司简称": "春秋电子", "所属行业": "消费电子"},
            valuation={"市盈率TTM": "28.5", "市净率": "3.2"},
            financials={"ROE": "12.4%", "营业收入同比": "18.1%"},
            events=[{"title": "近期严重异动核查", "level": "warning"}],
            news=[{"title": "春秋电子获机构关注", "sentiment": "neutral"}],
            notices=[{"title": "春秋电子风险提示公告"}],
            sector={"板块": "消费电子", "强度": "strong"},
        )


class FakeMarketOverviewProvider:
    def get_overview(self) -> MarketOverviewResponse:
        return MarketOverviewResponse(
            trade_date="2026-06-26",
            turnover=MarketTurnoverSummary(
                total_cny=3_575_720_000_000,
                previous_total_cny=3_618_100_000_000,
                change_cny=-42_380_000_000,
                change_pct=-1.17,
            ),
            advance_decline=MarketAdvanceDeclineSummary(
                advance_count=802,
                decline_count=4738,
                unchanged_count=51,
                limit_up_count=None,
                limit_down_count=None,
            ),
            sectors=[
                MarketSectorStrengthItem(
                    name="存储芯片",
                    change_pct=3.26,
                    turnover_cny=86_500_000_000,
                    advance_count=38,
                    decline_count=6,
                    leader="香农芯创",
                    source="东方财富行业板块",
                ),
                MarketSectorStrengthItem(
                    name="电力",
                    change_pct=1.42,
                    turnover_cny=54_200_000_000,
                    advance_count=42,
                    decline_count=18,
                    leader="豫能控股",
                    source="东方财富行业板块",
                ),
                MarketSectorStrengthItem(
                    name="消费电子",
                    change_pct=-2.18,
                    turnover_cny=61_400_000_000,
                    advance_count=9,
                    decline_count=58,
                    leader="春秋电子",
                    source="东方财富行业板块",
                ),
            ],
            source_status=[
                StrongStockSourceStatus(
                    source="东方财富全A指数",
                    status="success",
                    detail="沪深北指数成交额和涨跌家数",
                ),
                StrongStockSourceStatus(
                    source="东方财富行业板块",
                    status="success",
                    detail="返回 2 个板块",
                ),
            ],
        )


def _client(
    tmp_path: Path,
    candidate_provider: object | None = None,
    kline_provider: object | None = None,
    quote_provider: object | None = None,
    news_risk_provider: object | None = None,
    market_overview_provider: object | None = None,
) -> TestClient:
    app.state.candidate_provider = candidate_provider or FakeCandidateProvider()
    app.state.kline_provider = kline_provider or FakeKlineProvider()
    app.state.quote_provider = quote_provider or FakeQuoteProvider()
    app.state.news_risk_provider = news_risk_provider or FakeNewsRiskProvider()
    app.state.market_overview_provider = market_overview_provider or FakeMarketOverviewProvider()
    app.state.watchlist_snapshot = WatchlistSnapshot(
        items=[WatchlistItem(symbol="002000.SZ", name="示例股份")]
    )
    app.state.runs_dir = tmp_path
    app.state.watchlist_path = tmp_path / "watchlist.txt"
    app.state.runtime_config_path = tmp_path / "runtime_config.json"
    return TestClient(app)


def test_health_returns_ok(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_data_source_status_reports_tickflow_missing_key(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/data-sources/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["source"] == "fake候选池"
    assert payload["items"][2]["source"] == "TickFlow"
    assert payload["items"][2]["status"] == "missing_key"


def test_data_source_status_uses_candidate_provider_status(tmp_path: Path) -> None:
    client = _client(tmp_path, candidate_provider=UnavailableStatusCandidateProvider())

    response = client.get("/api/data-sources/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["source"] == "fake候选池"
    assert payload["items"][0]["status"] == "failed"
    assert payload["items"][0]["detail"] == "候选池不可用"


def test_settings_can_be_saved_and_read_without_exposing_full_key(tmp_path: Path) -> None:
    client = _client(tmp_path)

    save_response = client.put(
        "/api/settings",
        json={
            "candidate_provider": "recent_limit_up",
            "kline_provider": "tickflow",
            "quote_provider": "tickflow",
            "tickflow_api_key": "tk_saved_secret",
            "tickflow_base_url": "https://api.example.test",
            "provider_timeout_seconds": 3.5,
        },
    )

    assert save_response.status_code == 200
    payload = save_response.json()
    assert payload["config"]["tickflow_api_key_configured"] is True
    assert payload["config"]["tickflow_api_key_preview"] != "tk_saved_secret"
    assert payload["config"]["tickflow_base_url"] == "https://api.example.test"
    assert "tickflow_api_key" not in payload["saved"]

    get_response = client.get("/api/settings")
    assert get_response.status_code == 200
    assert get_response.json()["config"]["provider_timeout_seconds"] == 3.5
    assert "tk_saved_secret" not in get_response.text


def test_settings_can_be_saved_with_ifind_configuration(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.put(
        "/api/settings",
        json={
            "candidate_provider": "recent_limit_up",
            "kline_provider": "tickflow",
            "quote_provider": "tickflow",
            "tickflow_api_key": "tk_saved_secret",
            "tickflow_base_url": "https://api.example.test",
            "provider_timeout_seconds": 3.5,
            "ifind_api_key": "ifind_saved_secret",
            "ifind_base_url": "https://api-mcp.51ifind.com:8643",
            "ifind_service_id": "hexin-ifind-ds-stock-mcp",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["ifind_api_key_configured"] is True
    assert payload["config"]["ifind_api_key_preview"] != "ifind_saved_secret"
    assert payload["config"]["ifind_base_url"] == "https://api-mcp.51ifind.com:8643"
    assert payload["config"]["ifind_service_id"] == "hexin-ifind-ds-stock-mcp"
    assert "ifind_api_key" not in payload["saved"]


def test_settings_health_check_reports_ifind_mcp_probe(tmp_path: Path) -> None:
    client = _client(tmp_path)
    app.state.ifind_http_client = FakeIfindHealthClient()
    save_response = client.put(
        "/api/settings",
        json={
            "candidate_provider": "recent_limit_up",
            "kline_provider": "tickflow",
            "quote_provider": "tickflow",
            "tickflow_api_key": "tk_saved_secret",
            "tickflow_base_url": "https://api.example.test",
            "provider_timeout_seconds": 3.5,
            "ifind_api_key": "ifind_saved_secret",
            "ifind_base_url": "https://api-mcp.51ifind.com:8643",
            "ifind_service_id": "hexin-ifind-ds-stock-mcp",
        },
    )
    assert save_response.status_code == 200

    response = client.get("/api/settings/health?symbol=603890.SH")

    assert response.status_code == 200
    payload = response.json()
    probe_names = [item["name"] for item in payload["probes"]]
    assert "iFinD MCP" in probe_names
    assert "iFinD A股数据" in probe_names
    assert all(isinstance(item["latency_ms"], int) for item in payload["probes"])


def test_settings_health_check_reports_provider_probes(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        kline_provider=FakeKlineProvider(),
        quote_provider=FakeLiveQuoteProvider(),
    )

    response = client.get("/api/settings/health?symbol=603890.SH")

    assert response.status_code == 200
    payload = response.json()
    probe_names = [item["name"] for item in payload["probes"]]
    assert "fake K线" in probe_names
    assert "TickFlow 实时行情" in probe_names
    assert "TickFlow 当日分钟线" in probe_names
    assert all(isinstance(item["latency_ms"], int) for item in payload["probes"])


def test_stock_kline_endpoint_returns_daily_bars(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/stocks/603890.SH/kline?count=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "603890.SH"
    assert payload["source_status"]["source"] == "fake K线"
    assert len(payload["bars"]) == 5
    assert payload["bars"][-1]["close"] > payload["bars"][0]["close"]
    assert payload["gsgf_annotations"] == []


def test_stock_kline_endpoint_returns_gsgf_chart_annotations(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/stocks/603890.SH/kline?count=220")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["type"] == "volume_structure" for item in payload["gsgf_annotations"])
    assert any(item["type"] == "zone" for item in payload["gsgf_annotations"])


def test_stock_research_reports_missing_ifind_key_without_breaking(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/stocks/603890.SH/research")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "603890.SH"
    assert payload["source_status"][0]["source"] == "iFinD MCP"
    assert payload["source_status"][0]["status"] == "missing_key"
    assert payload["profile"] == {}
    assert payload["financials"] == {}
    assert payload["news"] == []
    assert payload["sector"] == {}


def test_stock_research_returns_ifind_payload_from_provider(tmp_path: Path) -> None:
    client = _client(tmp_path)
    app.state.ifind_provider = FakeIfindResearchProvider()

    response = client.get("/api/stocks/603890.SH/research")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "603890.SH"
    assert payload["profile"]["公司简称"] == "春秋电子"
    assert payload["valuation"]["市盈率TTM"] == "28.5"
    assert payload["financials"]["ROE"] == "12.4%"
    assert payload["events"][0]["level"] == "warning"
    assert payload["news"][0]["title"] == "春秋电子获机构关注"
    assert payload["notices"][0]["title"] == "春秋电子风险提示公告"
    assert payload["sector"]["强度"] == "strong"


def test_market_overview_returns_full_a_share_metrics(tmp_path: Path) -> None:
    client = _client(tmp_path, market_overview_provider=FakeMarketOverviewProvider())

    response = client.get("/api/market/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-26"
    assert payload["turnover"]["total_cny"] == 3_575_720_000_000
    assert payload["turnover"]["previous_total_cny"] == 3_618_100_000_000
    assert payload["turnover"]["change_cny"] == -42_380_000_000
    assert payload["turnover"]["change_pct"] == -1.17
    assert payload["advance_decline"]["advance_count"] == 802
    assert payload["advance_decline"]["decline_count"] == 4738
    assert payload["advance_decline"]["unchanged_count"] == 51
    assert payload["sectors"][0]["name"] == "存储芯片"
    assert payload["sectors"][0]["source"] == "东方财富行业板块"
    assert payload["source_status"][0]["source"] == "东方财富全A指数"


def test_sector_radar_returns_inflow_and_outflow_rankings(tmp_path: Path) -> None:
    client = _client(tmp_path, market_overview_provider=FakeMarketOverviewProvider())

    response = client.get("/api/sectors/radar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-26"
    assert payload["capital_flow_status"] == "estimated"
    assert payload["flow_source"] == "东方财富行业板块涨跌额估算"
    assert payload["inflow"][0]["name"] == "存储芯片"
    assert payload["inflow"][0]["net_flow_cny"] > 0
    assert payload["outflow"][0]["name"] == "消费电子"
    assert payload["outflow"][0]["net_flow_cny"] < 0
    assert payload["source_status"][0]["source"] == "东方财富全A指数"


def test_screen_run_returns_items_and_persists_latest_without_empty_status(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/screen/runs", json={"trade_date": "2026-06-11", "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-11"
    assert payload["items"][0]["status"] == "focus"
    assert payload["items"][0]["industry"] == "消费电子"
    assert payload["items"][0]["severe_abnormal_warning"] == "triggered"
    assert payload["items"][0]["negative_news_status"] == "triggered"
    assert payload["items"][0]["negative_news_flags"] == [
        "负面新闻待核验: 2026-06-12 春秋电子收到监管函（东方财富）"
    ]
    assert all(item["status"] != "empty" for item in payload["items"])
    assert payload["watchlist_risk_items"][0]["risk_action"] == "empty"
    assert payload["watchlist_risk_items"][0]["severe_abnormal_warning"] == "unknown"
    assert payload["watchlist_risk_items"][0]["negative_news_status"] == "clear"

    latest_response = client.get("/api/screen/runs/latest")
    assert latest_response.status_code == 200
    assert latest_response.json()["trade_date"] == "2026-06-11"
    assert (tmp_path / "latest.json").exists()


def test_screen_run_respects_scan_limit_before_fetching_klines(tmp_path: Path) -> None:
    kline_provider = CountingKlineProvider()
    client = _client(
        tmp_path,
        candidate_provider=LargeCandidateProvider(count=50),
        kline_provider=kline_provider,
    )

    response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 12},
    )

    assert response.status_code == 200
    scanned_candidates = [symbol for symbol in kline_provider.symbols if symbol.startswith("600")]
    assert len(scanned_candidates) == 12
    assert "002000.SZ" in kline_provider.symbols
    payload = response.json()
    assert len(payload["items"]) == 10
    assert "本次分析 12/50" in payload["source_status"][0]["detail"]


def test_screen_run_is_stable_when_candidate_source_order_changes(tmp_path: Path) -> None:
    client = _client(tmp_path, candidate_provider=UnstableOrderCandidateProvider())

    first_response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 2, "scan_limit": 2},
    )
    second_response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 2, "scan_limit": 2},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_symbols = [item["symbol"] for item in first_response.json()["items"]]
    second_symbols = [item["symbol"] for item in second_response.json()["items"]]
    assert first_symbols == ["600001.SH", "600002.SH"]
    assert second_symbols == first_symbols


def test_screen_run_preserves_ranked_candidate_order_before_scan_limit(tmp_path: Path) -> None:
    kline_provider = CountingKlineProvider()
    client = _client(
        tmp_path,
        candidate_provider=RankedCandidateProvider(),
        kline_provider=kline_provider,
    )

    response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 2, "scan_limit": 2},
    )

    assert response.status_code == 200
    scanned_candidates = [symbol for symbol in kline_provider.symbols if symbol.startswith("600")]
    assert scanned_candidates == ["600003.SH", "600001.SH"]


def test_screen_run_filters_by_market_cap_industry_and_market_type(tmp_path: Path) -> None:
    client = _client(tmp_path, candidate_provider=AdvancedFilterCandidateProvider())

    response = client.post(
        "/api/screen/runs",
        json={
            "trade_date": "2026-06-11",
            "limit": 10,
            "scan_limit": 10,
            "filters": {
                "min_market_cap_billion": 100,
                "max_market_cap_billion": 150,
                "industries": ["消费电子"],
                "market_types": ["main"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["symbol"] for item in payload["items"]] == ["603890.SH"]
    assert "筛选后 1/4" in payload["source_status"][0]["detail"]


def test_screen_run_filters_by_kdj_j_max_after_kline_analysis(tmp_path: Path) -> None:
    client = _client(tmp_path, candidate_provider=AdvancedFilterCandidateProvider())

    response = client.post(
        "/api/screen/runs",
        json={
            "trade_date": "2026-06-11",
            "limit": 10,
            "scan_limit": 10,
            "filters": {"kdj_j_max": 0},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert "KDJ-J<0" in payload["source_status"][0]["detail"]


def test_screen_run_scores_industry_strength_without_overriding_trend_risk(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        candidate_provider=IndustryClusterCandidateProvider(),
        kline_provider=IndustryClusterKlineProvider(),
    )

    response = client.post("/api/screen/runs", json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 4})

    assert response.status_code == 200
    payload = response.json()
    clustered_item = next(item for item in payload["items"] if item["symbol"] == "603890.SH")
    weak_item = next(item for item in payload["items"] if item["symbol"] == "603891.SH")
    solo_item = next(item for item in payload["items"] if item["symbol"] == "002000.SZ")
    assert clustered_item["industry_strength"] == "strong"
    assert clustered_item["industry_score"] == 15
    assert clustered_item["industry_rank"] == 1
    assert "板块强度加分" in clustered_item["rule_hits"]
    assert weak_item["industry_strength"] == "strong"
    assert weak_item["status"] == "wait_pullback"
    assert solo_item["industry_strength"] == "neutral"
    assert solo_item["industry_score"] == 0


def test_screen_run_accepts_gsgf_strategy_and_returns_metadata(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 10, "strategy": "gsgf"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy"] == "gsgf"
    assert payload["gsgf_model_version"] == "gsgf-v1"
    assert payload["sort_version"] == "gsgf-sort-v1"
    assert payload["items"][0]["gsgf"]["total_score"] >= 0
    assert payload["items"][0]["gsgf"]["final_status"] in {"确认买点", "候选", "低吸观察", "观察", "减仓", "回避"}
    assert "setup_score" in payload["items"][0]["gsgf"]
    assert "confirm_score" in payload["items"][0]["gsgf"]


def test_gsgf_backtest_returns_bucketed_forward_stats(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/gsgf/backtest",
        json={"symbols": ["603890.SH"], "windows": [1, 3], "min_history": 60, "count": 90},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["windows"] == [1, 3]
    assert payload["sample_count"] > 0
    assert payload["source_status"][0]["source"] == "股是股非回测"
    assert payload["buckets"][0]["status"] in {"确认买点", "候选", "低吸观察", "观察", "减仓", "回避"}
    assert payload["buckets"][0]["windows"][0]["window_days"] == 1
    assert payload["buckets"][0]["windows"][0]["sample_count"] > 0
    assert "avg_return_pct" in payload["buckets"][0]["windows"][0]


def test_gsgf_calibration_returns_real_data_bucket_summary(tmp_path: Path) -> None:
    client = _client(tmp_path, kline_provider=FakeCalibrationKlineProvider())

    response = client.post(
        "/api/gsgf/calibration",
        json={"trade_dates": ["2026-01-28"], "windows": [1, 3], "scan_limit": 2, "count": 90},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_dates"] == ["2026-01-28"]
    assert payload["windows"] == [1, 3]
    assert payload["scanned_count"] == 2
    assert payload["target_sample_count"] > 0
    assert payload["buckets"][0]["sample_count"] > 0
    assert payload["unique_symbol_buckets"][0]["sample_count"] > 0
    assert payload["samples"][0]["symbol"] in {"603890.SH", "002000.SZ"}
    assert "realized_return_pct" in payload["samples"][0]["windows"][0]


def test_gsgf_trade_plan_endpoint_returns_operational_guidance(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/gsgf/trade-plan",
        json={
            "analysis": {
                "total_score": 76,
                "action": "strong_candidate",
                "final_status": "确认买点",
                "zone": "a_zone",
                "volume_structure": "three_yang_controls_three_yin",
                "setup_type": "B区A点",
                "setup_score": 20,
                "confirm_type": "放量突破确认",
                "confirm_score": 35,
                "risk_flags": [],
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "确认买点"
    assert any("持有优于追涨" in item for item in payload["holder_guidance"])
    assert any("等分歧低吸" in item for item in payload["empty_position_guidance"])
    assert payload["holder_guidance"] != payload["empty_position_guidance"]
    assert "不构成收益承诺" in payload["research_note"]


def test_gsgf_review_endpoints_persist_and_recheck_latest_screen_run(tmp_path: Path) -> None:
    client = _client(tmp_path)
    screen_response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 10, "strategy": "gsgf"},
    )
    assert screen_response.status_code == 200

    snapshot_response = client.post("/api/gsgf/review/snapshots/latest")
    assert snapshot_response.status_code == 200
    snapshot_payload = snapshot_response.json()
    assert snapshot_payload["saved_count"] > 0
    assert snapshot_payload["records"][0]["trade_date"] == "2026-06-11"

    summary_response = client.post("/api/gsgf/review/recheck", json={"windows": [1, 3], "count": 90})
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["record_count"] > 0
    assert summary_payload["windows"] == [1, 3]
    assert summary_payload["buckets"][0]["sample_count"] > 0
    assert "realized_return_pct" in summary_payload["items"][0]["windows"][0]
    assert (tmp_path / "gsgf_review" / "snapshots.jsonl").exists()


def test_screen_run_accepts_combined_strategy(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 10, "strategy": "combined"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy"] == "combined"
    assert payload["sort_version"] == "combined-sort-v1"


def test_screen_run_rejects_candidate_source_failure(tmp_path: Path) -> None:
    client = _client(tmp_path, candidate_provider=FailingCandidateProvider())

    response = client.post("/api/screen/runs", json={"trade_date": "2026-06-11", "limit": 10})

    assert response.status_code == 503
    assert "候选池数据源失败" in response.json()["detail"]


def test_watchlist_gsgf_status_returns_structure_triggers(tmp_path: Path) -> None:
    client = _client(tmp_path)
    app.state.watchlist_path.write_text(
        "603890.SH 春秋电子 | group=观察 | industry=消费电子",
        encoding="utf-8",
    )

    response = client.get("/api/watchlist/gsgf-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["symbol"] == "603890.SH"
    assert payload["items"][0]["gsgf"]["model_version"] == "gsgf-v1"


def test_latest_returns_404_before_first_run(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/screen/runs/latest")

    assert response.status_code == 404


def test_intraday_snapshot_uses_latest_screen_run_symbols_without_empty_status(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeLiveQuoteProvider())
    screen_response = client.post("/api/screen/runs", json={"trade_date": "2026-06-11", "limit": 10})
    assert screen_response.status_code == 200

    response = client.post("/api/intraday/snapshot", json={"limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"][0]["source"] == "TickFlow 实时行情"
    assert payload["source_status"][1]["source"] == "TickFlow 当日分钟线"
    assert payload["items"][0]["symbol"] == "603890.SH"
    assert payload["items"][0]["industry"] == "消费电子"
    assert payload["items"][0]["action"] == "reduce"
    assert "早盘涨幅超过7%" in payload["items"][0]["signals"]
    assert all(item["action"] != "empty" for item in payload["items"])


def test_intraday_snapshot_confirms_gsgf_buy_point_with_intraday_ma(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeGsgfConfirmQuoteProvider())

    response = client.post(
        "/api/intraday/snapshot",
        json={
            "symbols": ["603890.SH"],
            "limit": 10,
            "gsgf_context": {
                "603890.SH": {
                    "final_status": "确认买点",
                    "confirm_type": "放量突破确认",
                    "risk_flags": [],
                }
            },
        },
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["gsgf_intraday_confirmation"] == "盘中确认"
    assert "GSGF确认买点：站稳日内均线" in item["signals"]
    assert "GSGF确认信号：放量突破确认" in item["signals"]


def test_intraday_snapshot_confirms_gsgf_low_buy_after_recovery(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeGsgfLowBuyQuoteProvider())

    response = client.post(
        "/api/intraday/snapshot",
        json={
            "symbols": ["603890.SH"],
            "limit": 10,
            "gsgf_context": {
                "603890.SH": {
                    "final_status": "低吸观察",
                    "setup_type": "双星止跌",
                    "risk_flags": [],
                }
            },
        },
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["gsgf_intraday_confirmation"] == "低吸确认"
    assert item["action"] == "low_buy_watch"
    assert "GSGF低吸观察：急跌后收回日内均线" in item["signals"]


def test_intraday_snapshot_confirms_gsgf_reduce_when_strength_fades(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeLiveQuoteProvider())

    response = client.post(
        "/api/intraday/snapshot",
        json={
            "symbols": ["603890.SH"],
            "limit": 10,
            "gsgf_context": {
                "603890.SH": {
                    "final_status": "减仓",
                    "risk_flags": ["高位巨量长上影"],
                }
            },
        },
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["gsgf_intraday_confirmation"] in {"减仓确认", "风险失效"}
    assert item["action"] in {"reduce", "avoid_chase"}
    assert any("GSGF" in signal for signal in item["signals"])


def test_intraday_snapshot_requires_symbols_or_latest_screen_run(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeLiveQuoteProvider())

    response = client.post("/api/intraday/snapshot", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "no screen run"


def test_intraday_snapshot_accepts_watchlist_text_groups_and_tags(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeLiveQuoteProvider())

    response = client.post(
        "/api/intraday/snapshot",
        json={"watchlist_text": "[高标]\n603890 春秋电子 #AI #回踩 行业=消费电子", "limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["symbol"] == "603890.SH"
    assert payload["items"][0]["name"] == "春秋电子"
    assert payload["items"][0]["industry"] == "消费电子"
    assert payload["items"][0]["group"] == "高标"
    assert payload["items"][0]["tags"] == ["AI", "回踩"]


def test_watchlist_pool_can_be_saved_and_used_for_intraday(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeLiveQuoteProvider())

    save_response = client.put(
        "/api/watchlist/pool",
        json={"content": "[高标]\n603890 春秋电子 #AI #回踩"},
    )
    assert save_response.status_code == 200
    assert save_response.json()["items"][0]["group"] == "高标"

    get_response = client.get("/api/watchlist/pool")
    assert get_response.status_code == 200
    assert get_response.json()["content"] == "[高标]\n603890 春秋电子 #AI #回踩"

    intraday_response = client.post(
        "/api/intraday/snapshot",
        json={"use_watchlist_pool": True, "limit": 10},
    )

    assert intraday_response.status_code == 200
    payload = intraday_response.json()
    assert payload["items"][0]["symbol"] == "603890.SH"
    assert payload["items"][0]["group"] == "高标"
    assert payload["items"][0]["tags"] == ["AI", "回踩"]


def test_watchlist_pool_item_can_be_added_to_custom_group_and_updated(tmp_path: Path) -> None:
    client = _client(tmp_path)

    first_response = client.post(
        "/api/watchlist/pool/items",
        json={
            "symbol": "603890.SH",
            "name": "春秋电子",
            "industry": "消费电子",
            "group": "mlcc",
            "note": "观察10日线承接",
        },
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert "[mlcc]" in first_payload["content"]
    assert first_payload["items"][0]["symbol"] == "603890.SH"
    assert first_payload["items"][0]["group"] == "mlcc"
    assert first_payload["items"][0]["industry"] == "消费电子"
    assert first_payload["items"][0]["note"] == "观察10日线承接"

    second_response = client.post(
        "/api/watchlist/pool/items",
        json={
            "symbol": "603890",
            "name": "春秋电子",
            "industry": "元器件",
            "group": "存储芯片",
            "tags": ["强势"],
            "note": "更新为存储芯片观察",
        },
    )

    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["content"].count("603890.SH") == 1
    assert "[存储芯片]" in second_payload["content"]
    assert second_payload["items"][0]["group"] == "存储芯片"
    assert second_payload["items"][0]["industry"] == "元器件"
    assert second_payload["items"][0]["tags"] == ["强势"]
    assert second_payload["items"][0]["note"] == "更新为存储芯片观察"
