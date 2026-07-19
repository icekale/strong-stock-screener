from __future__ import annotations

import httpx

from app.providers.capital_signals import (
    OfficialCapitalDataProvider,
    parse_sse_etf_share_payload,
    parse_sse_margin_payload,
    parse_szse_etf_share_payload,
    parse_szse_margin_payload,
)


SSE_MARGIN_FIXTURE = {
    "result": [
        {
            "opDate": "20260717",
            "rzye": 1_392_832_663_141,
            "rqylje": 12_531_345_321,
            "rzmre": 107_304_029_411,
            "rzrqjyzl": 1_405_364_008_462,
        }
    ]
}

SZSE_MARGIN_FIXTURE = [
    {
        "metadata": {"subname": "2026-07-16"},
        "data": [
            {
                "jrrzmr": "1,014.15",
                "jrrzye": "13,982.04",
                "jrrjye": "72.31",
                "jrrzrjye": "14,054.35",
            }
        ],
    }
]

SSE_SHARE_FIXTURE = {
    "result": [
        {
            "STAT_DATE": "2026-07-17",
            "SEC_CODE": "510300",
            "SEC_NAME": "300ETF",
            "TOT_VOL": "836,989.77",
        },
        {
            "STAT_DATE": "2026-07-17",
            "SEC_CODE": "510050",
            "SEC_NAME": "50ETF",
            "TOT_VOL": "501,234.5",
        },
    ]
}

SZSE_SHARE_FIXTURE = [
    {
        "metadata": {"subname": "2026-07-17"},
        "data": [
            {
                "sys_key": "<a href='?code=159915'><u>159915</u></a>",
                "kzjcurl": "<a href='?name=创业板ETF'><u>创业板ETF</u></a>",
                "dqgm": "481,234.56",
            }
        ],
    }
]


def test_sse_margin_parser_keeps_yuan_values_and_normalizes_trade_date() -> None:
    rows = parse_sse_margin_payload(SSE_MARGIN_FIXTURE)

    assert rows[0].trade_date == "2026-07-17"
    assert rows[0].market == "SSE"
    assert rows[0].financing_balance_cny == 1_392_832_663_141
    assert rows[0].securities_lending_balance_cny == 12_531_345_321
    assert rows[0].margin_balance_cny == 1_405_364_008_462
    assert rows[0].financing_buy_cny == 107_304_029_411


def test_szse_margin_parser_converts_hundred_million_yuan() -> None:
    rows = parse_szse_margin_payload(SZSE_MARGIN_FIXTURE, trade_date="2026-07-16")

    assert rows[0].trade_date == "2026-07-16"
    assert rows[0].market == "SZSE"
    assert rows[0].financing_balance_cny == 1_398_204_000_000
    assert rows[0].securities_lending_balance_cny == 7_231_000_000
    assert rows[0].margin_balance_cny == 1_405_435_000_000
    assert rows[0].financing_buy_cny == 101_415_000_000


def test_sse_share_parser_keeps_exchange_trade_date_without_utc_shift() -> None:
    rows = parse_sse_etf_share_payload(SSE_SHARE_FIXTURE, symbols=["510300.SH"])

    assert len(rows) == 1
    assert rows[0].trade_date == "2026-07-17"
    assert rows[0].symbol == "510300.SH"
    assert rows[0].name == "300ETF"
    assert rows[0].total_shares == 8_369_897_700


def test_szse_current_share_parser_does_not_invent_history() -> None:
    rows = parse_szse_etf_share_payload(
        SZSE_SHARE_FIXTURE,
        trade_date="2026-07-17",
        symbols=["159915.SZ"],
    )

    assert len(rows) == 1
    assert rows[0].symbol == "159915.SZ"
    assert rows[0].name == "创业板ETF"
    assert rows[0].trade_date == "2026-07-17"
    assert rows[0].total_shares == 4_812_345_600


def test_share_parsers_skip_missing_or_non_positive_sizes() -> None:
    sse = {"result": [{"STAT_DATE": "2026-07-17", "SEC_CODE": "510300", "TOT_VOL": "-"}]}
    szse = [{"metadata": {"subname": "2026-07-17"}, "data": [{"sys_key": "159915", "dqgm": "0"}]}]

    assert parse_sse_etf_share_payload(sse, symbols=["510300.SH"]) == []
    assert parse_szse_etf_share_payload(szse, trade_date="2026-07-17", symbols=["159915.SZ"]) == []


def test_margin_provider_keeps_sse_rows_when_szse_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "query.sse.com.cn":
            return httpx.Response(200, json=SSE_MARGIN_FIXTURE)
        return httpx.Response(503, json={"error": "temporary"})

    provider = OfficialCapitalDataProvider(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    result = provider.get_margin_rows("2026-07-17")

    assert len(result.rows) == 1
    assert result.rows[0].market == "SSE"
    assert [(item.source, item.status) for item in result.source_status] == [
        ("上交所两融", "success"),
        ("深交所两融", "failed"),
    ]


def test_share_provider_fetches_only_requested_exchange_symbols() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=SSE_SHARE_FIXTURE)

    provider = OfficialCapitalDataProvider(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    result = provider.get_etf_share_rows("2026-07-17", ["510300.SH"])

    assert [row.symbol for row in result.rows] == ["510300.SH"]
    assert len(requests) == 1
    assert requests[0].url.host == "query.sse.com.cn"
    assert requests[0].url.params["STAT_DATE"] == "2026-07-17"
    assert result.source_status[0].status == "success"
