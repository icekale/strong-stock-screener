from app.providers.baidu_kline import parse_baidu_kline_payload
from app.providers.thsdk_candidates import ThsdkCandidateProvider, parse_thsdk_candidate_rows
from app.providers.tickflow import TickFlowQuote, TickFlowQuoteProvider, parse_tickflow_quote_payload
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

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.last_request = {"url": url, **kwargs}
        return FakeResponse(self.payload)


def test_tickflow_status_reports_missing_key_without_fake_quotes() -> None:
    provider = TickFlowQuoteProvider(api_key="", base_url="https://api.tickflow.org")

    status = provider.status()

    assert status.source == "TickFlow"
    assert status.status == "missing_key"
    assert "TICKFLOW_API_KEY" in status.detail


def test_tickflow_provider_maps_quote_payload() -> None:
    client = FakeHttpClient(
        {
            "data": [
                {
                    "symbol": "603890.SH",
                    "name": "春秋电子",
                    "last_price": 16.8,
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
            pct_change=10.1,
            turnover_cny=350000000.0,
            volume=200000.0,
            quote_time="2026-06-11T10:00:00+08:00",
        )
    ]
    assert client.last_request is not None
    assert client.last_request["url"] == "https://api.tickflow.org/v1/quotes"


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


def test_thsdk_status_reports_unavailable_when_package_missing() -> None:
    provider = ThsdkCandidateProvider(client_factory=None)

    status = provider.status()

    assert status.source == "THSDK 问财"
    assert status.status == "failed"
    assert "THSDK 未安装" in status.detail


def test_parse_watchlist_text_supports_symbols_and_names() -> None:
    items = parse_watchlist_text("603890 春秋电子\n000001\n# comment\n")

    assert len(items) == 2
    assert items[0].symbol == "603890.SH"
    assert items[0].name == "春秋电子"
    assert items[1].symbol == "000001.SZ"
