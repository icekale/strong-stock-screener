from app.models import KlineBar, StrongStockDataUnavailable
from app.providers.baidu_kline import parse_baidu_kline_payload
from app.providers.kline_fallback import FallbackKlineProvider
from app.providers.ifind import IfindMcpProvider
from app.providers.recent_limit_up_candidates import (
    RecentLimitUpCandidateProvider,
    parse_recent_limit_up_rows,
)
from app.providers.news_risk import analyze_negative_news_rows
from app.providers.thsdk_candidates import ThsdkCandidateProvider, parse_thsdk_candidate_rows
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


def test_tickflow_status_reports_missing_key_without_fake_quotes() -> None:
    provider = TickFlowQuoteProvider(api_key="", base_url="https://api.tickflow.org")

    status = provider.status()

    assert status.source == "TickFlow"
    assert status.status == "missing_key"
    assert "TICKFLOW_API_KEY" in status.detail


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
            turnover_cny=350000000.0,
            volume=200000.0,
            quote_time="2026-06-11T10:00:00+08:00",
        )
    ]
    assert client.last_request is not None
    assert client.last_request["url"] == "https://api.tickflow.org/v1/quotes"


class FakeSequentialHttpClient:
    def __init__(self, payloads: list[object]) -> None:
        self.payloads = payloads
        self.requests: list[dict[str, object]] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.requests.append({"url": url, **kwargs})
        return FakeResponse(self.payloads.pop(0))


def test_tickflow_provider_maps_intraday_payload_by_symbol_requests() -> None:
    client = FakeHttpClient(
        {
            "data": {
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
    assert client.last_request["url"] == "https://api.tickflow.org/v1/klines/intraday"
    assert client.last_request["params"] == {
        "symbol": "603890.SH",
        "period": "1m",
        "count": 120,
    }


def test_tickflow_provider_requests_intraday_one_symbol_at_a_time() -> None:
    client = FakeSequentialHttpClient(
        [
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
        ]
    )
    provider = TickFlowQuoteProvider(
        api_key="tk-test",
        base_url="https://api.tickflow.org",
        http_client=client,
    )

    bars_by_symbol = provider.get_intraday_bars(["603890.SH", "002000.SZ"], period="1m", count=5)

    assert sorted(bars_by_symbol) == ["002000.SZ", "603890.SH"]
    assert [request["url"] for request in client.requests] == [
        "https://api.tickflow.org/v1/klines/intraday",
        "https://api.tickflow.org/v1/klines/intraday",
    ]
    assert [request["params"]["symbol"] for request in client.requests] == ["603890.SH", "002000.SZ"]


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
                }
            ]
        }
    )

    assert quotes[0].symbol == "002000.SZ"
    assert quotes[0].name == "示例股份"
    assert quotes[0].pct_change == 8.2
    assert quotes[0].turnover_cny == 1000000.0


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
