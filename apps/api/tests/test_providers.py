from app.models import KlineBar, StrongStockDataUnavailable
from app.providers.baidu_kline import parse_baidu_kline_payload
from app.providers.kline_fallback import FallbackKlineProvider
from app.providers.ifind import IfindMcpProvider
from app.providers.market_overview import EastmoneyMarketOverviewProvider
from app.providers.recent_limit_up_candidates import (
    RecentLimitUpCandidateProvider,
    parse_recent_limit_up_rows,
)
from app.providers.news_risk import analyze_negative_news_rows
from app.providers.thsdk_candidates import ThsdkCandidateProvider, parse_thsdk_candidate_rows
from app.providers.tdx_mcp import TdxMcpProvider
from app.providers.tickflow import (
    TickFlowDailyKlineProvider,
    TickFlowIntradayBar,
    TickFlowQuote,
    TickFlowQuoteProvider,
    parse_tickflow_kline_payload,
    parse_tickflow_intraday_payload,
    parse_tickflow_quote_payload,
)
from app.providers.watchlist import parse_watchlist_text


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class FakeHttpClient:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.last_request: dict[str, object] | None = None
        self.requests: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.last_request = {"url": url, **kwargs}
        return FakeResponse(self.payload)

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.last_request = {"url": url, **kwargs}
        self.requests.append(self.last_request)
        return FakeResponse(self.payload)


class FakeThsResponse:
    success = True
    error = ""
    data = []


class FakeThsClient:
    last_query: str | None = None

    def __enter__(self) -> "FakeThsClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def wencai_nlp(self, query: str) -> FakeThsResponse:
        FakeThsClient.last_query = query
        return FakeThsResponse()


class FakeMarketOverviewHttpClient:
    def __init__(self, limit_down_pool_error: Exception | None = None) -> None:
        self.requests: list[dict[str, object]] = []
        self.limit_down_pool_error = limit_down_pool_error

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.requests.append({"url": url, **kwargs})
        if "getTopicDTPool" in url:
            if self.limit_down_pool_error is not None:
                raise self.limit_down_pool_error
            return FakeResponse(
                {
                    "data": {
                        "pool": [
                            {"c": "600010", "n": "跌停一号", "zdp": -10.02},
                            {"c": "002011", "n": "跌停二号", "zdp": -10.01},
                        ],
                    }
                }
            )
        if "stock/kline/get" in url:
            return FakeResponse(
                {
                    "data": {
                        "klines": [
                            "2026-06-25,1,1,1,1,1,1000000000000,0,0,0,0",
                            "2026-06-26,1,1,1,1,1,1100000000000,0,0,0,0",
                        ]
                    }
                }
            )
        if "ulist.np/get" in url:
            params = kwargs.get("params", {})
            secids = str(params.get("secids", "")) if isinstance(params, dict) else ""
            if "399006" in secids or "000688" in secids:
                return FakeResponse(
                    {
                        "data": {
                            "diff": [
                                {"f2": 4027.26, "f3": -2.25, "f6": 10, "f12": "000001", "f14": "上证指数"},
                                {"f2": 15782.22, "f3": -3.43, "f6": 20, "f12": "399001", "f14": "深证成指"},
                                {"f2": 3188.66, "f3": 1.25, "f6": 999, "f12": "399006", "f14": "创业板指"},
                                {"f2": 1020.48, "f3": 0.86, "f6": 888, "f12": "000688", "f14": "科创50"},
                            ]
                        }
                    }
                )
            return FakeResponse(
                {
                    "data": {
                        "diff": [
                            {"f2": 4027.26, "f3": -2.25, "f6": 10, "f12": "000001", "f14": "上证指数", "f104": 100, "f105": 200, "f106": 10},
                            {"f2": 15782.22, "f3": -3.43, "f6": 20, "f12": "399001", "f14": "深证成指", "f104": 300, "f105": 400, "f106": 20},
                            {"f2": 1266.9, "f3": -0.84, "f6": 30, "f12": "899050", "f14": "北证50", "f104": 20, "f105": 30, "f106": 5},
                        ]
                    }
                }
            )
        if "clist/get" in url:
            params = kwargs.get("params", {})
            if isinstance(params, dict) and params.get("fs") == "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23":
                page = int(str(params.get("pn", "1")))
                if page > 1:
                    return FakeResponse({"data": {"diff": [], "total": 10}})
                return FakeResponse(
                    {
                        "data": {
                            "total": 10,
                            "diff": [
                                {"f3": 11.2, "f12": "300001", "f14": "超强科技", "f100": "机器人"},
                                {"f3": 8.1, "f12": "300002", "f14": "强势股份", "f100": "机器人"},
                                {"f3": 5.5, "f12": "600003", "f14": "上涨股份", "f100": "电池"},
                                {"f3": 3.2, "f12": "600004", "f14": "温和上涨", "f100": "化工"},
                                {"f3": 1.1, "f12": "600005", "f14": "微涨股份", "f100": "电子"},
                                {"f3": -1.2, "f12": "600006", "f14": "微跌股份", "f100": "电子"},
                                {"f3": -4.4, "f12": "600007", "f14": "弱势股份", "f100": "通信"},
                                {"f3": -6.6, "f12": "600008", "f14": "大跌股份", "f100": "通信"},
                                {"f3": -8.8, "f12": "600009", "f14": "深跌股份", "f100": "传媒"},
                                {"f3": -10.5, "f12": "600010", "f14": "跌停附近", "f100": "煤炭"},
                            ]
                        }
                    }
                )
            if isinstance(params, dict) and params.get("fid") == "f62":
                if params.get("po") == "0":
                    return FakeResponse(
                        {
                            "data": {
                                "diff": [
                                    {
                                        "f14": "电子",
                                        "f3": -1.44,
                                        "f6": 1_239_812_025_923,
                                        "f62": -49_914_335_232,
                                        "f104": 160,
                                        "f105": 345,
                                    },
                                    {
                                        "f14": "通信",
                                        "f3": -4.62,
                                        "f6": 291_176_504_093,
                                        "f62": -41_346_885_376,
                                        "f104": 10,
                                        "f105": 119,
                                    },
                                ]
                            }
                        }
                    )
                return FakeResponse(
                    {
                        "data": {
                            "diff": [
                                {
                                    "f14": "面板",
                                    "f3": 0.15,
                                    "f6": 97_305_368_868,
                                    "f62": 4_025_548_032,
                                    "f104": 18,
                                    "f105": 25,
                                },
                                {
                                    "f14": "光学光电子",
                                    "f3": 0.35,
                                    "f6": 162_376_940_331,
                                    "f62": 3_776_760_832,
                                    "f104": 43,
                                    "f105": 54,
                                },
                            ]
                        }
                    }
                )
            return FakeResponse(
                {
                    "data": {
                        "diff": [
                            {"f14": "有机硅", "f3": 4.72, "f6": 6_700_000_000, "f104": 8, "f105": 2},
                            {"f14": "橡胶助剂", "f3": 5.41, "f6": 3_300_000_000, "f104": 2, "f105": 0},
                        ]
                    }
                }
            )
        raise AssertionError(f"unexpected url: {url}")


class FakeTickFlowIndexQuoteProvider:
    def __init__(self, quotes: list[TickFlowQuote] | None = None, error: Exception | None = None) -> None:
        self.quotes = quotes or []
        self.error = error
        self.symbols: list[str] = []
        self.calls: list[list[str]] = []

    def get_quotes(self, symbols: list[str]) -> list[TickFlowQuote]:
        self.symbols = symbols
        self.calls.append(symbols)
        if self.error is not None:
            raise self.error
        return self.quotes


class FakeTickFlowRankingQuoteProvider:
    source_name = "TickFlow"

    def __init__(self, universe_error: Exception | None = None) -> None:
        self.calls: list[list[str]] = []
        self.universe_calls: list[str] = []
        self.universe_error = universe_error

    def get_quotes(self, symbols: list[str]) -> list[TickFlowQuote]:
        self.calls.append(symbols)
        return self._quotes_for_symbols(symbols)

    def get_quotes_by_universe(self, universe: str) -> list[TickFlowQuote]:
        self.universe_calls.append(universe)
        if self.universe_error is not None:
            raise self.universe_error
        return self._quotes_for_symbols(["300001.SZ", "300002.SZ", "600003.SH", "600004.SH"])

    def _quotes_for_symbols(self, symbols: list[str]) -> list[TickFlowQuote]:
        quote_map = {
            "300001.SZ": TickFlowQuote(symbol="300001.SZ", name="创业一", last_price=11, pct_change=12.0, turnover_cny=300_000_000, turnover_rate=18.0, quote_time="2026-06-30T10:00:00+08:00"),
            "300002.SZ": TickFlowQuote(symbol="300002.SZ", name="创业二", last_price=12, pct_change=8.5, turnover_cny=900_000_000, turnover_rate=9.0, quote_time="2026-06-30T10:00:00+08:00"),
            "600003.SH": TickFlowQuote(symbol="600003.SH", name="沪市三", last_price=13, pct_change=3.2, turnover_cny=1_500_000_000, turnover_rate=5.0, quote_time="2026-06-30T10:00:00+08:00"),
            "600004.SH": TickFlowQuote(symbol="600004.SH", name="沪市四", last_price=14, pct_change=-2.0, turnover_cny=200_000_000, turnover_rate=2.0, quote_time="2026-06-30T10:00:00+08:00"),
        }
        return [quote_map[symbol] for symbol in symbols if symbol in quote_map]


class FakeIfindIndexProvider:
    def __init__(self, payload: object | None = None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls: list[dict[str, object]] = []

    def call_tool(self, service_id: str, tool_name: str, arguments: dict[str, object]) -> object:
        self.calls.append(
            {"service_id": service_id, "tool_name": tool_name, "arguments": arguments}
        )
        if self.error is not None:
            raise self.error
        return self.payload


class FakeIfindIndustryProvider:
    def __init__(self, industry_by_symbol: dict[str, str]) -> None:
        self.industry_by_symbol = industry_by_symbol
        self.calls: list[list[str]] = []

    def status(self):
        from app.models import StrongStockSourceStatus

        return StrongStockSourceStatus(source="iFinD MCP", status="success", detail="fake ifind configured")

    def get_stock_industries(self, symbols: list[str]) -> dict[str, str]:
        self.calls.append(symbols)
        return {symbol: self.industry_by_symbol[symbol] for symbol in symbols if symbol in self.industry_by_symbol}


class FailingAshareIndustryHttpClient(FakeMarketOverviewHttpClient):
    def get(self, url: str, **kwargs: object) -> FakeResponse:
        params = kwargs.get("params", {})
        if (
            "clist/get" in url
            and isinstance(params, dict)
            and params.get("fs") == "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
        ):
            raise RuntimeError("eastmoney stock pool down")
        return super().get(url, **kwargs)


class BatchIndustryFallbackHttpClient(FailingAshareIndustryHttpClient):
    def get(self, url: str, **kwargs: object) -> FakeResponse:
        params = kwargs.get("params", {})
        if "ulist.np/get" in url and isinstance(params, dict) and params.get("fields") == "f12,f14,f100":
            return FakeResponse(
                {
                    "data": {
                        "diff": [
                            {"f12": "300001", "f14": "创业一", "f100": "电网设备"},
                            {"f12": "300002", "f14": "创业二", "f100": "游戏Ⅱ"},
                            {"f12": "600003", "f14": "沪市三", "f100": "电池"},
                            {"f12": "600004", "f14": "沪市四", "f100": "航空机场"},
                        ]
                    }
                }
            )
        return super().get(url, **kwargs)


def test_tickflow_status_reports_missing_key_without_fake_quotes() -> None:
    provider = TickFlowQuoteProvider(api_key="", base_url="https://api.tickflow.org")

    status = provider.status()

    assert status.source == "TickFlow"
    assert status.status == "missing_key"
    assert "TICKFLOW_API_KEY" in status.detail


def test_market_overview_prefers_ifind_realtime_index_snapshot() -> None:
    ifind_provider = FakeIfindIndexProvider(
        payload={
            "code": 1,
            "msg": "success",
            "data": (
                '{"tables":[["证券代码","证券简称","time","最新价","涨跌幅","成交额","上涨家数","下跌家数"],'
                '["000001.SH","上证指数","2026-06-26 16:01:19","4027.26","-2.25","1600000000000","369","1947"],'
                '["399001.SZ","深证成指","2026-06-26 16:00:57","15782.223","-3.43","1900000000000","396","2507"],'
                '["399006.SZ","创业板指","2026-06-26 16:00:57","3188.66","1.25","800000000000","188","412"],'
                '["000688.SH","科创50","2026-06-26 16:00:57","1020.48","0.86","300000000000","96","171"],'
                '["899050.BJ","北证50","2026-06-26 15:37:00","1266.903","-0.84","20000000000","37","284"]]}'
            ),
        }
    )
    tickflow_provider = FakeTickFlowIndexQuoteProvider(
        quotes=[TickFlowQuote(symbol="000001.SH", turnover_cny=1)]
    )
    provider = EastmoneyMarketOverviewProvider(
        http_client=FakeMarketOverviewHttpClient(),
        realtime_quote_provider=tickflow_provider,
        ifind_index_provider=ifind_provider,
    )

    overview = provider.get_overview()

    assert ifind_provider.calls == [
        {
            "service_id": "hexin-ifind-ds-index-mcp",
            "tool_name": "index_highfreq_quotes",
            "arguments": {
                "symbols": "000001.SH,399001.SZ,899050.BJ,399006.SZ,000688.SH",
                "indicators": "最新价,涨跌幅,成交额,上涨家数,下跌家数",
                "data_mode": "real_time",
            },
        }
    ]
    assert tickflow_provider.symbols == []
    assert overview.turnover.total_cny == 3_520_000_000_000
    assert overview.turnover.previous_total_cny == 3_000_000_000_000
    assert overview.turnover.change_cny == 520_000_000_000
    assert overview.turnover.change_pct == 17.33
    assert overview.trade_date == "2026-06-26"
    assert overview.advance_decline.advance_count == 802
    assert overview.advance_decline.decline_count == 4738
    assert overview.advance_decline.limit_down_count == 2
    assert [item.symbol for item in overview.indices] == [
        "000001.SH",
        "399001.SZ",
        "399006.SZ",
        "000688.SH",
    ]
    assert overview.indices[2].name == "创业板"
    assert overview.indices[2].change_pct == 1.25
    assert overview.indices[3].name == "科创50"
    assert overview.sectors[0].name == "橡胶助剂"
    assert overview.source_status[0].source == "iFinD 实时指数"
    assert overview.source_status[0].status == "success"
    assert any(status.source == "东方财富跌停池" for status in overview.source_status)


def test_market_overview_falls_back_to_tickflow_realtime_turnover() -> None:
    quote_provider = FakeTickFlowIndexQuoteProvider(
        quotes=[
            TickFlowQuote(symbol="000001.SH", turnover_cny=1_600_000_000_000, quote_time="1782457209000"),
            TickFlowQuote(symbol="399001.SZ", turnover_cny=1_900_000_000_000, quote_time="1782457203000"),
            TickFlowQuote(symbol="899050.BJ", turnover_cny=20_000_000_000, quote_time="1782457212000"),
        ]
    )
    provider = EastmoneyMarketOverviewProvider(
        http_client=FakeMarketOverviewHttpClient(),
        realtime_quote_provider=quote_provider,
        ifind_index_provider=FakeIfindIndexProvider(error=RuntimeError("ifind down")),
    )

    overview = provider.get_overview()

    assert quote_provider.calls[0] == ["000001.SH", "399001.SZ", "899050.BJ"]
    assert overview.turnover.total_cny == 3_520_000_000_000
    assert overview.turnover.previous_total_cny == 3_000_000_000_000
    assert overview.turnover.change_cny == 520_000_000_000
    assert overview.turnover.change_pct == 17.33
    assert overview.trade_date == "2026-06-26"
    assert overview.advance_decline.advance_count == 420
    assert overview.advance_decline.decline_count == 630
    assert overview.sectors[0].name == "橡胶助剂"
    assert overview.source_status[0].source == "iFinD 实时指数"
    assert overview.source_status[0].status == "failed"
    assert overview.source_status[1].source == "TickFlow 实时指数"
    assert overview.source_status[1].status == "success"


def test_market_overview_uses_tickflow_display_indices_before_eastmoney() -> None:
    quote_provider = FakeTickFlowIndexQuoteProvider(
        quotes=[
            TickFlowQuote(symbol="000001.SH", name="上证指数", last_price=4027.26, pct_change=-2.25, turnover_cny=1_600_000_000_000),
            TickFlowQuote(symbol="399001.SZ", name="深证成指", last_price=15782.22, pct_change=-3.43, turnover_cny=1_900_000_000_000),
            TickFlowQuote(symbol="399006.SZ", name="创业板指", last_price=3188.66, pct_change=1.25, turnover_cny=800_000_000_000),
            TickFlowQuote(symbol="000688.SH", name="科创50", last_price=1020.48, pct_change=0.86, turnover_cny=300_000_000_000),
            TickFlowQuote(symbol="899050.BJ", name="北证50", last_price=1266.9, pct_change=-0.84, turnover_cny=20_000_000_000),
        ]
    )
    provider = EastmoneyMarketOverviewProvider(
        http_client=FakeMarketOverviewHttpClient(),
        realtime_quote_provider=quote_provider,
        ifind_index_provider=FakeIfindIndexProvider(error=RuntimeError("ifind down")),
    )

    overview = provider.get_overview()

    assert quote_provider.calls == [
        ["000001.SH", "399001.SZ", "899050.BJ"],
        ["000001.SH", "399001.SZ", "399006.SZ", "000688.SH"],
    ]
    assert overview.turnover.total_cny == 3_520_000_000_000
    assert [item.symbol for item in overview.indices] == [
        "000001.SH",
        "399001.SZ",
        "399006.SZ",
        "000688.SH",
    ]
    assert overview.indices[2].source == "TickFlow 实时指数"


def test_market_overview_falls_back_to_eastmoney_when_tickflow_unavailable() -> None:
    provider = EastmoneyMarketOverviewProvider(
        http_client=FakeMarketOverviewHttpClient(),
        realtime_quote_provider=FakeTickFlowIndexQuoteProvider(error=RuntimeError("boom")),
        ifind_index_provider=FakeIfindIndexProvider(error=RuntimeError("ifind down")),
    )

    overview = provider.get_overview()

    assert overview.turnover.total_cny == 60
    assert overview.source_status[0].source == "iFinD 实时指数"
    assert overview.source_status[0].status == "failed"
    assert overview.source_status[1].source == "TickFlow 实时指数"
    assert overview.source_status[1].status == "failed"
    assert overview.source_status[2].source == "东方财富全A指数"
    assert "fallback" in overview.source_status[2].detail


def test_market_overview_display_indices_do_not_double_count_turnover() -> None:
    provider = EastmoneyMarketOverviewProvider(http_client=FakeMarketOverviewHttpClient())

    overview = provider.get_overview()

    assert overview.turnover.total_cny == 60
    assert [item.symbol for item in overview.indices] == [
        "000001.SH",
        "399001.SZ",
        "399006.SZ",
        "000688.SH",
    ]
    assert overview.indices[2].source == "东方财富指数行情"


def test_market_overview_provider_returns_direct_sector_capital_flow() -> None:
    provider = EastmoneyMarketOverviewProvider(http_client=FakeMarketOverviewHttpClient())

    radar = provider.get_sector_radar(limit=2)

    assert radar.capital_flow_status == "direct"
    assert radar.flow_source == "东方财富行业板块资金净额"
    assert radar.inflow[0].name == "面板"
    assert radar.inflow[0].net_flow_cny == 4_025_548_032
    assert radar.outflow[0].name == "电子"
    assert radar.outflow[0].net_flow_cny == -49_914_335_232
    capital_flow_requests = [
        request
        for request in provider.http_client.requests
        if request["params"].get("fid") == "f62"
    ]
    assert [request["params"].get("po") for request in capital_flow_requests] == ["1", "0"]


def test_market_overview_provider_returns_realtime_pct_change_distribution() -> None:
    provider = EastmoneyMarketOverviewProvider(http_client=FakeMarketOverviewHttpClient())

    buckets, status = provider.get_pct_change_distribution()

    assert status.source == "东方财富全A实时涨跌幅"
    assert status.status == "success"
    assert [bucket.label for bucket in buckets] == [
        ">10%",
        "7-10%",
        "5-7%",
        "3-5%",
        "0-3%",
        "-3-0%",
        "-5--3%",
        "-7--5%",
        "-10--7%",
        "<-10%",
    ]
    assert sum(bucket.count or 0 for bucket in buckets) == 10
    assert [bucket.count for bucket in buckets] == [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]


def test_market_overview_provider_builds_tickflow_full_a_rankings() -> None:
    quote_provider = FakeTickFlowRankingQuoteProvider()
    provider = EastmoneyMarketOverviewProvider(
        http_client=FakeMarketOverviewHttpClient(),
        realtime_quote_provider=quote_provider,
    )

    rankings = provider.get_market_rankings(limit=3, batch_size=2)

    assert quote_provider.universe_calls == ["CN_Equity_A"]
    assert quote_provider.calls == []
    assert rankings.trade_date == "2026-06-30"
    assert [item.symbol for item in rankings.pct_change_rank] == [
        "300001.SZ",
        "300002.SZ",
        "600003.SH",
    ]
    assert [item.industry for item in rankings.pct_change_rank] == ["机器人", "机器人", "电池"]
    assert [item.symbol for item in rankings.turnover_rank] == [
        "600003.SH",
        "300002.SZ",
        "300001.SZ",
    ]
    assert rankings.buckets[0].source == "TickFlow 全A实时行情"
    assert sum(bucket.count or 0 for bucket in rankings.buckets) == 4
    assert [status.source for status in rankings.source_status] == [
        "TickFlow 全A标的池",
        "TickFlow 全A实时行情",
    ]
    assert rankings.source_status[1].status == "success"


def test_market_overview_provider_supplements_missing_industries_from_ifind() -> None:
    quote_provider = FakeTickFlowRankingQuoteProvider()
    ifind_provider = FakeIfindIndustryProvider(
        {
            "300001.SZ": "人形机器人",
            "300002.SZ": "固态电池",
            "600003.SH": "算力设备",
            "600004.SH": "基础化工",
        }
    )
    provider = EastmoneyMarketOverviewProvider(
        http_client=FailingAshareIndustryHttpClient(),
        realtime_quote_provider=quote_provider,
        ifind_stock_provider=ifind_provider,
    )

    rankings = provider.get_market_rankings(limit=4, batch_size=2)

    assert ifind_provider.calls == [["300001.SZ", "300002.SZ", "600003.SH", "600004.SH"]]
    assert [item.industry for item in rankings.pct_change_rank] == ["人形机器人", "固态电池", "算力设备", "基础化工"]
    assert rankings.turnover_rank[0].industry == "算力设备"
    assert any(
        status.source == "iFinD 行业补充"
        and status.status == "success"
        and "补齐 4/4" in status.detail
        for status in rankings.source_status
    )


def test_market_overview_provider_supplements_missing_industries_from_eastmoney_batch() -> None:
    quote_provider = FakeTickFlowRankingQuoteProvider()
    ifind_provider = FakeIfindIndustryProvider({"300001.SZ": "不应调用"})
    provider = EastmoneyMarketOverviewProvider(
        http_client=BatchIndustryFallbackHttpClient(),
        realtime_quote_provider=quote_provider,
        ifind_stock_provider=ifind_provider,
    )

    rankings = provider.get_market_rankings(limit=4, batch_size=2)

    assert ifind_provider.calls == []
    assert [item.industry for item in rankings.pct_change_rank] == ["电网设备", "游戏Ⅱ", "电池", "航空机场"]
    assert any(
        status.source == "东方财富行业补充"
        and status.status == "success"
        and "补齐 4/4" in status.detail
        for status in rankings.source_status
    )


def test_market_overview_provider_falls_back_to_stock_pool_when_tickflow_universe_fails() -> None:
    quote_provider = FakeTickFlowRankingQuoteProvider(universe_error=RuntimeError("universe unavailable"))
    provider = EastmoneyMarketOverviewProvider(
        http_client=FakeMarketOverviewHttpClient(),
        realtime_quote_provider=quote_provider,
    )

    rankings = provider.get_market_rankings(limit=3, batch_size=2)

    assert quote_provider.universe_calls == ["CN_Equity_A"]
    assert quote_provider.calls == [
        ["300001.SZ", "300002.SZ"],
        ["600003.SH", "600004.SH"],
        ["600005.SH", "600006.SH"],
        ["600007.SH", "600008.SH"],
        ["600009.SH", "600010.SH"],
    ]
    assert [item.symbol for item in rankings.pct_change_rank] == [
        "300001.SZ",
        "300002.SZ",
        "600003.SH",
    ]
    assert [status.source for status in rankings.source_status] == [
        "TickFlow 全A标的池",
        "东方财富全A股票池",
        "TickFlow 全A实时行情",
    ]
    assert rankings.source_status[0].status == "failed"
    assert "fallback 到东方财富股票池" in rankings.source_status[0].detail


def test_market_overview_provider_prefers_tickflow_for_pct_change_distribution() -> None:
    provider = EastmoneyMarketOverviewProvider(
        http_client=FakeMarketOverviewHttpClient(),
        realtime_quote_provider=FakeTickFlowRankingQuoteProvider(),
    )

    buckets, status = provider.get_pct_change_distribution()

    assert status.source == "TickFlow 全A实时涨跌幅"
    assert status.status == "success"
    assert "全A实时行情返回 4 只股票" in status.detail
    assert sum(bucket.count or 0 for bucket in buckets) == 4
    assert buckets[0].source == "TickFlow 全A实时行情"


def test_market_overview_provider_uses_direct_limit_down_pool() -> None:
    provider = EastmoneyMarketOverviewProvider(http_client=FakeMarketOverviewHttpClient())

    overview = provider.get_overview()

    assert overview.advance_decline.limit_down_count == 2
    assert any(
        status.source == "东方财富跌停池"
        and status.status == "success"
        and "跌停 2 只" in status.detail
        for status in overview.source_status
    )


def test_market_overview_provider_falls_back_to_estimated_limit_down_count() -> None:
    provider = EastmoneyMarketOverviewProvider(
        http_client=FakeMarketOverviewHttpClient(limit_down_pool_error=RuntimeError("pool down"))
    )

    overview = provider.get_overview()

    assert overview.advance_decline.limit_down_count == 1
    assert any(
        status.source == "东方财富跌停池"
        and status.status == "failed"
        and "fallback 到全A实时涨跌幅估算" in status.detail
        for status in overview.source_status
    )
    assert any(
        status.source == "东方财富全A跌停估算"
        and status.status == "success"
        and "跌停 1 只" in status.detail
        for status in overview.source_status
    )


def test_market_overview_provider_reuses_realtime_rows_for_fallback_limit_down_and_distribution() -> None:
    http_client = FakeMarketOverviewHttpClient()
    provider = EastmoneyMarketOverviewProvider(http_client=http_client)

    provider._fetch_limit_down_count_from_realtime_rows()
    provider.get_overview()
    provider.get_pct_change_distribution()

    realtime_requests = [
        request
        for request in http_client.requests
        if request["url"].endswith("/api/qt/clist/get")
        and request["params"].get("fs") == "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
    ]
    assert len(realtime_requests) == 1


def test_ifind_status_reports_missing_key() -> None:
    provider = IfindMcpProvider(api_key="", base_url="https://api-mcp.51ifind.com:8643")

    status = provider.status()

    assert status.source == "iFinD MCP"
    assert status.status == "missing_key"
    assert "IFIND" in status.detail


def test_ifind_tools_probe_uses_jsonrpc_tools_list() -> None:
    client = FakeHttpClient(
        {
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
    )
    provider = IfindMcpProvider(
        api_key="ifind-test",
        base_url="https://api-mcp.51ifind.com:8643",
        http_client=client,
    )

    status = provider.probe_tools("hexin-ifind-ds-stock-mcp")

    assert status.status == "success"
    assert status.source == "iFinD A股数据"
    assert "1 个工具" in status.detail
    assert client.last_request is not None
    assert client.last_request["url"] == (
        "https://api-mcp.51ifind.com:8643/ds-mcp-servers/hexin-ifind-ds-stock-mcp"
    )
    assert client.last_request["headers"] == {
        "Authorization": "ifind-test",
        "Content-Type": "application/json",
    }
    assert client.last_request["json"] == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
    }


def test_ifind_call_tool_uses_jsonrpc_tools_call_and_parses_text_json() -> None:
    client = FakeHttpClient(
        {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": '{"公司简称":"春秋电子","所属行业":"消费电子"}',
                    }
                ]
            }
        }
    )
    provider = IfindMcpProvider(
        api_key="ifind-test",
        base_url="https://api-mcp.51ifind.com:8643",
        http_client=client,
    )

    payload = provider.call_tool(
        "hexin-ifind-ds-stock-mcp",
        "get_stock_info",
        {"query": "603890.SH 的公司简称和所属行业"},
    )

    assert payload == {"公司简称": "春秋电子", "所属行业": "消费电子"}
    assert client.last_request is not None
    assert client.last_request["url"] == (
        "https://api-mcp.51ifind.com:8643/ds-mcp-servers/hexin-ifind-ds-stock-mcp"
    )
    assert client.last_request["headers"] == {
        "Authorization": "ifind-test",
        "Content-Type": "application/json",
    }
    assert client.last_request["json"] == {
        "jsonrpc": "2.0",
        "id": "hexin-ifind-ds-stock-mcp:get_stock_info",
        "method": "tools/call",
        "params": {
            "name": "get_stock_info",
            "arguments": {"query": "603890.SH 的公司简称和所属行业"},
        },
    }


class FakeIfindResearchHttpClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.requests.append({"url": url, **kwargs})
        payload = kwargs.get("json", {})
        params = payload.get("params", {}) if isinstance(payload, dict) else {}
        tool_name = params.get("name") if isinstance(params, dict) else None
        if tool_name == "get_stock_financials":
            return FakeResponse(
                {
                    "result": {
                        "structuredContent": {
                            "总市值": 12_000_000_000,
                            "动态市盈率": 28.5,
                            "静态市盈率": 24.2,
                            "市净率": 3.2,
                        }
                    }
                }
            )
        return FakeResponse({"result": {"structuredContent": {}}})


def test_ifind_stock_research_keeps_market_cap_and_dynamic_static_pe() -> None:
    client = FakeIfindResearchHttpClient()
    provider = IfindMcpProvider(
        api_key="ifind-test",
        base_url="https://api-mcp.51ifind.com:8643",
        http_client=client,
    )

    research = provider.get_stock_research("603890.SH")

    assert research.valuation["总市值"] == 12_000_000_000
    assert research.valuation["动态市盈率"] == 28.5
    assert research.valuation["静态市盈率"] == 24.2
    financial_request = next(
        request
        for request in client.requests
        if request["json"]["params"]["name"] == "get_stock_financials"
    )
    query = financial_request["json"]["params"]["arguments"]["query"]
    assert "总市值" in query
    assert "动态市盈率" in query
    assert "静态市盈率" in query


class FakeIfindMarkdownResearchHttpClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.requests.append({"url": url, **kwargs})
        payload = kwargs.get("json", {})
        params = payload.get("params", {}) if isinstance(payload, dict) else {}
        tool_name = params.get("name") if isinstance(params, dict) else None
        if tool_name == "get_stock_financials":
            return FakeResponse(
                {
                    "result": {
                        "structuredContent": {
                            "code": 1,
                            "msg": "success",
                            "data": {
                                "answer": (
                                    "|证券代码|证券简称|总市值（单位：元）|市盈率（PE，LYR）|市盈率(PE,TTM)|\n"
                                    "|---|---|---|---|---|\n"
                                    "|603005.SH|晶方科技|351.3249亿|95.0509|95.0304|\n"
                                )
                            },
                        }
                    }
                }
            )
        return FakeResponse({"result": {"structuredContent": {}}})


def test_ifind_stock_research_extracts_valuation_from_markdown_answer_table() -> None:
    client = FakeIfindMarkdownResearchHttpClient()
    provider = IfindMcpProvider(
        api_key="ifind-test",
        base_url="https://api-mcp.51ifind.com:8643",
        http_client=client,
    )

    research = provider.get_stock_research("603005.SH")

    assert research.valuation["总市值"] == "351.3249亿"
    assert research.valuation["动态市盈率"] == "95.0304"
    assert research.valuation["静态市盈率"] == "95.0509"


class FakeIfindIndustryHttpClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.requests.append({"url": url, **kwargs})
        return FakeResponse(
            {
                "result": {
                    "structuredContent": {
                        "code": 1,
                        "msg": "success",
                        "data": {
                            "answer": (
                                "|证券代码|证券简称|所属行业|所属申万行业|\n"
                                "|---|---|---|---|\n"
                                "|300001.SZ|创业一|机器人|自动化设备|\n"
                                "|600003.SH|沪市三|电池|电池II|\n"
                            )
                        },
                    }
                }
            }
        )


def test_ifind_stock_industries_extracts_markdown_answer_table() -> None:
    client = FakeIfindIndustryHttpClient()
    provider = IfindMcpProvider(
        api_key="ifind-test",
        base_url="https://api-mcp.51ifind.com:8643",
        http_client=client,
    )

    industries = provider.get_stock_industries(["300001.SZ", "600003.SH"])

    assert industries == {"300001.SZ": "自动化设备", "600003.SH": "电池II"}
    assert client.requests[0]["json"]["params"]["name"] == "get_stock_info"
    query = client.requests[0]["json"]["params"]["arguments"]["query"]
    assert "所属行业" in query
    assert "所属申万行业" in query


def test_analyze_negative_news_rows_flags_regulatory_and_loss_keywords() -> None:
    risk = analyze_negative_news_rows(
        [
            {
                "新闻标题": "示例股份收到监管函",
                "新闻内容": "公司因信息披露问题收到交易所监管函。",
                "发布时间": "2026-06-12 09:30:00",
                "文章来源": "东方财富",
                "新闻链接": "https://example.test/news/1",
            },
            {
                "新闻标题": "示例股份发布新产品",
                "新闻内容": "公司业务进展正常。",
                "发布时间": "2026-06-12 10:30:00",
                "文章来源": "东方财富",
                "新闻链接": "https://example.test/news/2",
            },
            {
                "新闻标题": "示例股份预计业绩预亏",
                "新闻内容": "公司提示经营压力。",
                "发布时间": "2026-06-12 11:30:00",
                "文章来源": "东方财富",
                "新闻链接": "https://example.test/news/3",
            },
        ]
    )

    assert risk.status == "triggered"
    assert risk.flags == [
        "负面新闻待核验: 2026-06-12 09:30:00 示例股份收到监管函（东方财富）",
        "负面新闻待核验: 2026-06-12 11:30:00 示例股份预计业绩预亏（东方财富）",
    ]


def test_analyze_negative_news_rows_returns_clear_when_no_keywords_match() -> None:
    risk = analyze_negative_news_rows(
        [
            {
                "新闻标题": "示例股份发布新产品",
                "新闻内容": "公司业务进展正常。",
                "发布时间": "2026-06-12 10:30:00",
                "文章来源": "东方财富",
                "新闻链接": "https://example.test/news/2",
            }
        ]
    )

    assert risk.status == "clear"
    assert risk.flags == []


def test_parse_thsdk_candidate_rows_marks_clear_when_severe_abnormal_field_is_negative() -> None:
    candidates = parse_thsdk_candidate_rows(
        [
            {
                "股票简称": "春秋电子",
                "股票代码": "603890",
                "近20日涨停次数": 1,
                "近期是否触发严重异动": "否",
            }
        ]
    )

    assert candidates[0].abnormal_status == "clear"


def test_parse_recent_limit_up_rows_keeps_severe_abnormal_unknown_when_field_missing() -> None:
    candidates = parse_recent_limit_up_rows(
        [
            (
                "20260611",
                [
                    {
                        "代码": "603890",
                        "名称": "春秋电子",
                        "总市值": 12_000_000_000,
                    }
                ],
            )
        ]
    )

    assert candidates[0].abnormal_status == "unknown"


def test_tickflow_provider_maps_quote_payload() -> None:
    client = FakeHttpClient(
        {
            "data": [
                {
                    "symbol": "603890.SH",
                    "name": "春秋电子",
                    "last_price": 16.8,
                    "prev_close": 15.26,
                    "open": 16.1,
                    "high": 16.95,
                    "low": 15.88,
                    "pct_change": 0.101,
                    "turnover_rate": 12.34,
                    "turnover_cny": 350000000,
                    "volume": 200000,
                    "quote_time": "2026-06-11T10:00:00+08:00",
                }
            ]
        }
    )
    provider = TickFlowQuoteProvider(
        api_key="tk-test",
        base_url="https://api.tickflow.org",
        http_client=client,
    )

    quotes = provider.get_quotes(["603890.SH"])

    assert quotes == [
        TickFlowQuote(
            symbol="603890.SH",
            name="春秋电子",
            last_price=16.8,
            prev_close=15.26,
            open_price=16.1,
            high_price=16.95,
            low_price=15.88,
            pct_change=10.1,
            turnover_rate=12.34,
            turnover_cny=350000000.0,
            volume=200000.0,
            quote_time="2026-06-11T10:00:00+08:00",
        )
    ]
    assert client.last_request is not None
    assert client.last_request["url"] == "https://api.tickflow.org/v1/quotes"


def test_tickflow_provider_can_query_quotes_by_universe() -> None:
    client = FakeHttpClient(
        {
            "data": [
                {
                    "symbol": "600000.SH",
                    "last_price": 8.58,
                    "prev_close": 8.61,
                    "open": 8.58,
                    "high": 8.58,
                    "low": 8.58,
                    "volume": 2790,
                    "amount": 2393800,
                    "timestamp": 1782869101000,
                    "ext": {
                        "type": "cn_equity",
                        "name": "浦发银行",
                        "change_pct": -0.003484320557491215,
                        "turnover_rate": 8.376909702344889e-6,
                    },
                }
            ]
        }
    )
    provider = TickFlowQuoteProvider(
        api_key="tk-test",
        base_url="https://api.tickflow.org",
        http_client=client,
    )

    quotes = provider.get_quotes_by_universe("CN_Equity_A")

    assert quotes[0].symbol == "600000.SH"
    assert quotes[0].name == "浦发银行"
    assert quotes[0].pct_change == -0.3484
    assert quotes[0].turnover_rate == 0.0008
    assert quotes[0].turnover_cny == 2393800.0
    assert client.last_request is not None
    assert client.last_request["url"] == "https://api.tickflow.org/v1/quotes"
    assert client.last_request["json"] == {"universes": ["CN_Equity_A"]}


def test_tickflow_provider_http_error_includes_api_error_body() -> None:
    provider = TickFlowQuoteProvider(
        api_key="tk-test",
        base_url="https://api.tickflow.org",
        http_client=FakeQuoteErrorHttpClient(
            FakeStatusResponse(
                {"code": "INVALID_SYMBOL", "message": "invalid symbol format"},
                status_code=400,
            )
        ),
    )

    try:
        provider.get_quotes(["bad"])
    except StrongStockDataUnavailable as exc:
        message = str(exc)
    else:
        raise AssertionError("expected TickFlow quote request to fail")

    assert "HTTP 400" in message
    assert "INVALID_SYMBOL" in message
    assert "invalid symbol format" in message


class FakeSequentialHttpClient:
    def __init__(self, payloads: list[object]) -> None:
        self.payloads = payloads
        self.requests: list[dict[str, object]] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.requests.append({"url": url, **kwargs})
        return FakeResponse(self.payloads.pop(0))


class FakeStatusResponse(FakeResponse):
    def __init__(self, payload: object, status_code: int = 200) -> None:
        super().__init__(payload)
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            request = httpx.Request("GET", "https://api.tickflow.org/test")
            response = httpx.Response(self.status_code, request=request, json=self.payload)
            raise httpx.HTTPStatusError("boom", request=request, response=response)


class FakeQuoteErrorHttpClient:
    def __init__(self, response: FakeStatusResponse) -> None:
        self.response = response

    def post(self, url: str, **kwargs: object) -> FakeStatusResponse:
        return self.response


class FakeIntradayBatchHttpClient:
    def __init__(self, batch_response: FakeStatusResponse, single_payloads: list[object] | None = None) -> None:
        self.batch_response = batch_response
        self.single_payloads = single_payloads or []
        self.requests: list[dict[str, object]] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.requests.append({"url": url, **kwargs})
        if url.endswith("/v1/klines/intraday/batch"):
            return self.batch_response
        return FakeResponse(self.single_payloads.pop(0))


def test_tickflow_provider_maps_intraday_payload_by_symbol_requests() -> None:
    client = FakeHttpClient(
        {
            "data": {
                "603890.SH": {
                    "timestamp": [1781141400000, 1781141460000],
                    "open": [16.1, 16.3],
                    "high": [16.4, 16.6],
                    "low": [16.0, 16.2],
                    "close": [16.3, 16.55],
                    "volume": [12000, 15000],
                    "amount": [19560000, 24825000],
                    "prev_close": [15.26, 15.26],
                }
            }
        }
    )
    provider = TickFlowQuoteProvider(
        api_key="tk-test",
        base_url="https://api.tickflow.org",
        http_client=client,
    )

    bars_by_symbol = provider.get_intraday_bars(["603890.SH"], period="1m", count=120)

    assert bars_by_symbol == {
        "603890.SH": [
            TickFlowIntradayBar(
                timestamp=1781141400000,
                open=16.1,
                high=16.4,
                low=16.0,
                close=16.3,
                volume=12000.0,
                amount=19560000.0,
                prev_close=15.26,
            ),
            TickFlowIntradayBar(
                timestamp=1781141460000,
                open=16.3,
                high=16.6,
                low=16.2,
                close=16.55,
                volume=15000.0,
                amount=24825000.0,
                prev_close=15.26,
            ),
        ]
    }
    assert client.last_request is not None
    assert client.last_request["url"] == "https://api.tickflow.org/v1/klines/intraday/batch"
    assert client.last_request["params"] == {
        "symbols": "603890.SH",
        "period": "1m",
        "count": 120,
    }


def test_tickflow_provider_prefers_intraday_batch_endpoint() -> None:
    client = FakeIntradayBatchHttpClient(
        FakeStatusResponse(
            {
                "data": {
                    "603890.SH": {
                        "timestamp": [1781141400000],
                        "open": [16.1],
                        "high": [16.4],
                        "low": [16.0],
                        "close": [16.3],
                        "volume": [12000],
                        "amount": [19560000],
                    },
                    "002000.SZ": {
                        "timestamp": [1781141400000],
                        "open": [18.1],
                        "high": [18.4],
                        "low": [18.0],
                        "close": [18.3],
                        "volume": [22000],
                        "amount": [39560000],
                    },
                }
            }
        )
    )
    provider = TickFlowQuoteProvider(
        api_key="tk-test",
        base_url="https://api.tickflow.org",
        http_client=client,
    )

    bars_by_symbol = provider.get_intraday_bars(["603890.SH", "002000.SZ"], period="1m", count=5)

    assert sorted(bars_by_symbol) == ["002000.SZ", "603890.SH"]
    assert [request["url"] for request in client.requests] == [
        "https://api.tickflow.org/v1/klines/intraday/batch",
    ]
    assert client.requests[0]["params"] == {
        "symbols": "603890.SH,002000.SZ",
        "period": "1m",
        "count": 5,
    }


def test_tickflow_provider_falls_back_to_single_intraday_when_batch_not_allowed() -> None:
    client = FakeIntradayBatchHttpClient(
        FakeStatusResponse({"code": "NO_INTRADAY_BATCH_PERMISSION"}, status_code=403),
        single_payloads=[
            {
                "data": {
                    "timestamp": [1781141400000],
                    "open": [16.1],
                    "high": [16.4],
                    "low": [16.0],
                    "close": [16.3],
                    "volume": [12000],
                    "amount": [19560000],
                }
            },
            {
                "data": {
                    "timestamp": [1781141400000],
                    "open": [18.1],
                    "high": [18.4],
                    "low": [18.0],
                    "close": [18.3],
                    "volume": [22000],
                    "amount": [39560000],
                }
            },
        ],
    )
    provider = TickFlowQuoteProvider(
        api_key="tk-test",
        base_url="https://api.tickflow.org",
        http_client=client,
    )

    bars_by_symbol = provider.get_intraday_bars(["603890.SH", "002000.SZ"], period="1m", count=5)

    assert sorted(bars_by_symbol) == ["002000.SZ", "603890.SH"]
    assert [request["url"] for request in client.requests] == [
        "https://api.tickflow.org/v1/klines/intraday/batch",
        "https://api.tickflow.org/v1/klines/intraday",
        "https://api.tickflow.org/v1/klines/intraday",
    ]
    assert [request["params"].get("symbol") for request in client.requests[1:]] == ["603890.SH", "002000.SZ"]


def test_tickflow_daily_kline_provider_maps_1d_payload() -> None:
    client = FakeHttpClient(
        {
            "data": {
                "timestamp": [1781020800000, 1781107200000],
                "open": [10.0, 11.0],
                "high": [11.5, 12.5],
                "low": [9.8, 10.8],
                "close": [11.0, 12.0],
                "volume": [1000, 1500],
                "amount": [11000, 18000],
            }
        }
    )
    provider = TickFlowDailyKlineProvider(
        api_key="tk-test",
        base_url="https://api.tickflow.org",
        http_client=client,
    )

    bars = provider.get_klines("000636.SZ", count=220)

    assert bars == [
        KlineBar(date="20260610", open=10.0, high=11.5, low=9.8, close=11.0, volume=1000.0),
        KlineBar(date="20260611", open=11.0, high=12.5, low=10.8, close=12.0, volume=1500.0),
    ]
    assert client.last_request is not None
    assert client.last_request["url"] == "https://api.tickflow.org/v1/klines"
    assert client.last_request["params"] == {
        "symbol": "000636.SZ",
        "period": "1d",
        "count": 220,
        "adjust": "forward",
    }


def test_parse_tickflow_kline_payload_rejects_mismatched_columns() -> None:
    try:
        parse_tickflow_kline_payload(
            {
                "data": {
                    "timestamp": [1781020800000],
                    "open": [10.0, 11.0],
                    "high": [11.5],
                    "low": [9.8],
                    "close": [11.0],
                    "volume": [1000],
                    "amount": [11000],
                }
            }
        )
    except Exception as exc:
        assert "TickFlow K线列长度不一致" in str(exc)
    else:
        raise AssertionError("expected mismatched TickFlow kline columns to fail")


class FailingKlineProvider:
    source_name = "TickFlow 日K"

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        raise StrongStockDataUnavailable("primary failed")


class WorkingKlineProvider:
    source_name = "百度股市通K线"

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        return [
            KlineBar(date="20260610", open=10.0, high=11.5, low=9.8, close=11.0, volume=1000.0),
        ]


def test_fallback_kline_provider_uses_secondary_when_tickflow_fails() -> None:
    provider = FallbackKlineProvider(primary=FailingKlineProvider(), fallback=WorkingKlineProvider())

    bars = provider.get_klines("000636.SZ", count=220)

    assert bars[0].date == "20260610"
    assert provider.source_name == "TickFlow 日K，百度股市通K线 fallback"


def test_parse_tickflow_intraday_payload_rejects_mismatched_columns() -> None:
    try:
        parse_tickflow_intraday_payload(
            {
                "data": {
                    "603890.SH": {
                        "timestamp": [1781141400000],
                        "open": [16.1, 16.2],
                        "high": [16.4],
                        "low": [16.0],
                        "close": [16.3],
                        "volume": [12000],
                        "amount": [19560000],
                    }
                }
            }
        )
    except Exception as exc:
        assert "TickFlow 分钟线列长度不一致" in str(exc)
    else:
        raise AssertionError("expected mismatched TickFlow columns to fail")


def test_parse_tickflow_quote_payload_accepts_items_shape() -> None:
    quotes = parse_tickflow_quote_payload(
        {
            "items": [
                {
                    "ticker": "002000.SZ",
                    "ext": {"name": "示例股份", "change_pct": 8.2},
                    "price": "12.3",
                    "amount": "1000000",
                    "turnoverRate": "6.78",
                }
            ]
        }
    )

    assert quotes[0].symbol == "002000.SZ"
    assert quotes[0].name == "示例股份"
    assert quotes[0].pct_change == 8.2
    assert quotes[0].turnover_rate == 6.78
    assert quotes[0].turnover_cny == 1000000.0


def test_parse_tickflow_quote_payload_normalizes_decimal_turnover_rate() -> None:
    quotes = parse_tickflow_quote_payload(
        {
            "data": [
                {
                    "symbol": "603005.SH",
                    "price": 53.87,
                    "turnover_rate": 0.14943733238252443,
                }
            ]
        }
    )

    assert quotes[0].turnover_rate == 14.9437


def test_parse_baidu_kline_payload_maps_market_rows() -> None:
    payload = {
        "Result": {
            "newMarketData": {
                "keys": ["time", "open", "close", "high", "low", "volume", "ma5avgprice"],
                "marketData": "20260610,10,11,11.5,9.8,1000,10.5;20260611,11,12,12.5,10.8,1500,11.2",
            }
        }
    }

    bars = parse_baidu_kline_payload(payload)

    assert len(bars) == 2
    assert bars[-1].date == "20260611"
    assert bars[-1].close == 12
    assert bars[-1].ma5 == 11.2


def test_parse_thsdk_candidate_rows_requires_limit_up_evidence_and_dedupes() -> None:
    rows = [
        {"股票代码": "603890", "股票简称": "春秋电子", "近20日涨停次数": 2},
        {"股票代码": "603890", "股票简称": "春秋电子", "近20日涨停次数": 2},
        {"股票代码": "000001", "股票简称": "平安银行", "近20日涨停次数": 0},
        {"股票代码": "000002", "股票简称": "ST示例", "近20日涨停次数": 1},
    ]

    candidates = parse_thsdk_candidate_rows(rows)

    assert [item.symbol for item in candidates] == ["603890.SH"]
    assert candidates[0].limit_up_evidence == ["20日内涨停"]
    assert candidates[0].board_note == "近20日涨停次数: 2"


def test_parse_recent_limit_up_rows_dedupes_and_preserves_evidence() -> None:
    rows_by_date = [
        (
            "20260611",
            [
                {
                    "代码": "000636",
                    "名称": "风华高科",
                    "所属行业": "电子元件",
                    "涨停统计": "2/1",
                    "连板数": 1,
                    "首次封板时间": "093118",
                    "炸板次数": 0,
                    "总市值": 12_000_000_000,
                    "流通市值": 8_000_000_000,
                },
                {
                    "代码": "000002",
                    "名称": "ST示例",
                    "所属行业": "房地产",
                    "涨停统计": "1/1",
                    "连板数": 1,
                },
            ],
        ),
        (
            "20260610",
            [
                {
                    "代码": "000636",
                    "名称": "风华高科",
                    "所属行业": "电子元件",
                    "涨停统计": "1/1",
                    "连板数": 1,
                    "首次封板时间": "101507",
                    "炸板次数": 2,
                }
            ],
        ),
    ]

    candidates = parse_recent_limit_up_rows(rows_by_date)

    assert [item.symbol for item in candidates] == ["000636.SZ"]
    assert candidates[0].name == "风华高科"
    assert candidates[0].industry == "电子元件"
    assert candidates[0].total_market_cap_cny == 12_000_000_000
    assert candidates[0].circulating_market_cap_cny == 8_000_000_000
    assert candidates[0].limit_up_evidence == [
        "20日内涨停",
        "最近涨停: 20260611",
        "20日涨停次数: 2",
    ]
    assert (
        candidates[0].board_note
        == "涨停日期: 20260611,20260610; 涨停统计: 2/1; 连板数: 1; 炸板次数: 0; 首次封板时间: 093118"
    )


class FakeLimitUpPoolFetcher:
    def __init__(self) -> None:
        self.dates: list[str] = []

    def __call__(self, date: str) -> list[dict[str, object]]:
        self.dates.append(date)
        if date in {"20260612", "20260611"}:
            return []
        if date == "20260610":
            return [{"代码": "603890", "名称": "春秋电子", "所属行业": "消费电子"}]
        return []


def test_recent_limit_up_candidate_provider_walks_calendar_until_trading_days_found() -> None:
    fetcher = FakeLimitUpPoolFetcher()
    provider = RecentLimitUpCandidateProvider(pool_fetcher=fetcher, trading_days=1, calendar_day_factor=5)

    candidates = provider.get_candidates("2026-06-12")

    assert [item.symbol for item in candidates] == ["603890.SH"]
    assert fetcher.dates == ["20260612", "20260611", "20260610"]
    assert provider.status().source == "近20日涨停池"
    assert provider.status().status == "success"


def test_parse_thsdk_candidate_rows_marks_recent_severe_abnormal() -> None:
    rows = [
        {
            "股票代码": "603890",
            "股票简称": "春秋电子",
            "近20日涨停次数": 2,
            "近期是否触发严重异动": "是",
        }
    ]

    candidates = parse_thsdk_candidate_rows(rows)

    assert candidates[0].abnormal_flags == ["近期是否触发严重异动: 是"]


def test_parse_thsdk_candidate_rows_maps_industry() -> None:
    rows = [
        {
            "股票代码": "603890",
            "股票简称": "春秋电子",
            "近20日涨停次数": 2,
            "所属同花顺行业": "消费电子",
        }
    ]

    candidates = parse_thsdk_candidate_rows(rows)

    assert candidates[0].industry == "消费电子"


def test_thsdk_status_reports_unavailable_when_package_missing() -> None:
    provider = ThsdkCandidateProvider(client_factory=None)

    status = provider.status()

    assert status.source == "THSDK 问财"
    assert status.status == "failed"
    assert "THSDK 未安装" in status.detail


def test_thsdk_candidate_query_requests_severe_abnormal_field() -> None:
    provider = ThsdkCandidateProvider(client_factory=FakeThsClient)

    provider.get_candidates("2026-06-11")

    assert FakeThsClient.last_query is not None
    assert "严重异动" in FakeThsClient.last_query
    assert "行业" in FakeThsClient.last_query


def test_parse_watchlist_text_supports_symbols_and_names() -> None:
    items = parse_watchlist_text("603890 春秋电子\n000001\n# comment\n")

    assert len(items) == 2
    assert items[0].symbol == "603890.SH"
    assert items[0].name == "春秋电子"
    assert items[1].symbol == "000001.SZ"


def test_parse_watchlist_text_supports_groups_and_tags() -> None:
    items = parse_watchlist_text(
        "[高标]\n"
        "603890 春秋电子 #AI #回踩 行业=消费电子 备注=关注10日线承接\n"
        "002000 示例股份 @低吸 标签=消费,强势"
    )

    assert items[0].symbol == "603890.SH"
    assert items[0].group == "高标"
    assert items[0].tags == ["AI", "回踩"]
    assert items[0].industry == "消费电子"
    assert items[0].note == "关注10日线承接"
    assert items[1].symbol == "002000.SZ"
    assert items[1].group == "低吸"
    assert items[1].tags == ["消费", "强势"]


class FakeTdxMcpHttpClient:
    def __init__(self, payloads: list[object]) -> None:
        self.payloads = list(payloads)
        self.requests: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.requests.append({"url": url, **kwargs})
        if not self.payloads:
            raise AssertionError("no fake TDX payload left")
        return FakeResponse(self.payloads.pop(0))


def _tdx_tool_payload(rows: list[dict[str, object]]) -> dict[str, object]:
    headers = list(rows[0].keys()) if rows else []
    data = [[row.get(header) for header in headers] for row in rows]
    return {
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": __import__("json").dumps(
                        {
                            "meta": {"code": 0, "total": len(rows), "message": "ok"},
                            "headers": headers,
                            "data": data,
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }
    }


def test_tdx_mcp_provider_builds_sector_radar_from_limit_up_concepts() -> None:
    provider = TdxMcpProvider(
        api_key="TDX-test",
        http_client=FakeTdxMcpHttpClient(
            [
                {"headers": {"Mcp-Session-Id": "s1"}},
                {},
                _tdx_tool_payload(
                    [
                        {"sec_name": "华亚智能", "sec_code": "003043", "涨停原因": "半导体+设备", "连续涨停天数": "2", "所属概念": "半导体;机器人", "封单金额": "120000"},
                        {"sec_name": "新洁能", "sec_code": "605111", "涨停原因": "半导体", "连续涨停天数": "1", "所属概念": "半导体", "封单金额": "90000"},
                        {"sec_name": "惠康科技", "sec_code": "001237", "涨停原因": "通用设备", "连续涨停天数": "2", "所属概念": "机器人", "封单金额": "80000"},
                    ]
                ),
            ]
        ),
    )

    radar = provider.get_sector_radar(limit=5)

    assert radar.capital_flow_status == "estimated"
    assert radar.flow_source == "通达信MCP涨停概念集中度估算"
    assert radar.inflow[0].name == "半导体"
    assert radar.inflow[0].leader == "华亚智能"
    assert radar.inflow[0].advance_count == 2
    assert radar.inflow[0].net_flow_cny is not None
    assert radar.source_status[0].source == "通达信MCP涨停概念"
    assert radar.source_status[0].status == "success"


def test_tdx_mcp_provider_status_reports_missing_key() -> None:
    provider = TdxMcpProvider(api_key="")

    status = provider.status()

    assert status.source == "通达信MCP"
    assert status.status == "missing_key"
    assert "TDX_API_KEY" in status.detail
