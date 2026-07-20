from __future__ import annotations

from copy import deepcopy

import httpx
import pytest

from app.providers.capital_signals import (
    CapitalProviderResult,
    OfficialCapitalDataProvider,
    parse_sse_etf_share_payload,
    parse_sse_margin_payload,
    parse_sina_holder_payload,
    parse_sina_report_dates,
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
        "metadata": {
            "subname": "2026-07-20",
            "cols": {
                "dqgm": "当前规模<br>（万份）<span>说明</span><br>（2026-07-17）"
            },
        },
        "data": [
            {
                "sys_key": "<u>159915</u>",
                "kzjcurl": "<u>创业板ETF易方达</u>",
                "dqgm": "1,492,045.49",
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


def test_provider_result_preserves_backward_compatible_metadata_defaults() -> None:
    result = CapitalProviderResult(rows=[], source_status=[])

    assert result.request_failures == 0
    assert result.available_trade_dates == ()


def test_szse_current_share_parser_does_not_invent_history() -> None:
    rows = parse_szse_etf_share_payload(
        SZSE_SHARE_FIXTURE,
        trade_date="2026-07-17",
        symbols=["159915.SZ"],
    )

    assert len(rows) == 1
    assert rows[0].symbol == "159915.SZ"
    assert rows[0].name == "创业板ETF易方达"
    assert rows[0].trade_date == "2026-07-17"
    assert rows[0].total_shares == 14_920_454_900


def test_szse_current_share_parser_rejects_a_different_exchange_date() -> None:
    rows = parse_szse_etf_share_payload(
        SZSE_SHARE_FIXTURE,
        trade_date="2026-07-16",
        symbols=["159915.SZ"],
    )

    assert rows == []


def test_szse_share_parser_uses_scale_column_date_not_page_date() -> None:
    rows = parse_szse_etf_share_payload(
        SZSE_SHARE_FIXTURE,
        trade_date="2026-07-17",
        symbols=["159915.SZ"],
    )

    assert len(rows) == 1
    assert rows[0].trade_date == "2026-07-17"
    assert rows[0].total_shares == pytest.approx(14_920_454_900)


@pytest.mark.parametrize(
    "dqgm_title",
    [
        "当前规模（万份）",
        "当前规模（2026-07-16）（2026-07-17）",
        "当前规模（2026-02-31）",
    ],
)
def test_szse_share_parser_rejects_missing_ambiguous_or_invalid_scale_date(
    dqgm_title: str,
) -> None:
    payload = deepcopy(SZSE_SHARE_FIXTURE)
    payload[0]["metadata"]["cols"]["dqgm"] = dqgm_title

    assert parse_szse_etf_share_payload(
        payload,
        trade_date="2026-07-17",
        symbols=["159915.SZ"],
    ) == []


def test_szse_share_parser_rejects_mixed_valid_and_invalid_scale_dates() -> None:
    payload = deepcopy(SZSE_SHARE_FIXTURE)
    payload[0]["metadata"]["cols"]["dqgm"] = "当前规模（2026-07-17）（2026-02-31）"

    assert parse_szse_etf_share_payload(
        payload,
        trade_date="2026-07-17",
        symbols=["159915.SZ"],
    ) == []


def test_szse_current_share_parser_rejects_missing_or_invalid_scale_date() -> None:
    missing_date = [{"metadata": {}, "data": SZSE_SHARE_FIXTURE[0]["data"]}]
    invalid_date = [
        {
            "metadata": {"subname": "2026年7月17日"},
            "data": SZSE_SHARE_FIXTURE[0]["data"],
        }
    ]

    assert (
        parse_szse_etf_share_payload(
            missing_date,
            trade_date="2026-07-17",
            symbols=["159915.SZ"],
        )
        == []
    )
    assert (
        parse_szse_etf_share_payload(
            invalid_date,
            trade_date="2026-07-17",
            symbols=["159915.SZ"],
        )
        == []
    )


def test_sse_share_parser_rejects_an_impossible_calendar_date() -> None:
    payload = {
        "result": [
            {
                "STAT_DATE": "2026-02-30",
                "SEC_CODE": "510300",
                "TOT_VOL": "100",
            }
        ]
    }

    assert parse_sse_etf_share_payload(payload, symbols=["510300.SH"]) == []


def test_szse_share_parser_rejects_impossible_metadata_and_requested_dates() -> None:
    for impossible_date in ("2026-02-30", "20260230"):
        payload = [
            {
                "metadata": {
                    "subname": "2026-07-20",
                    "cols": {"dqgm": f"当前规模（{impossible_date}）"},
                },
                "data": SZSE_SHARE_FIXTURE[0]["data"],
            }
        ]

        assert (
            parse_szse_etf_share_payload(
                payload,
                trade_date=impossible_date,
                symbols=["159915.SZ"],
            )
            == []
        )


def test_share_parsers_skip_missing_or_non_positive_sizes() -> None:
    sse = {"result": [{"STAT_DATE": "2026-07-17", "SEC_CODE": "510300", "TOT_VOL": "-"}]}
    szse = [
        {
            "metadata": {
                "subname": "2026-07-20",
                "cols": {"dqgm": "当前规模（2026-07-17）"},
            },
            "data": [{"sys_key": "159915", "dqgm": "0"}],
        }
    ]

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


def test_share_provider_marks_full_sse_coverage_success() -> None:
    requests: list[httpx.Request] = []
    symbols = ["510300.SH", "510500.SH"]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "result": [
                    {
                        "STAT_DATE": "2026-07-17",
                        "SEC_CODE": symbol.split(".", 1)[0],
                        "TOT_VOL": "100",
                    }
                    for symbol in symbols
                ]
            },
        )

    provider = OfficialCapitalDataProvider(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    result = provider.get_etf_share_rows("2026-07-17", symbols)

    assert len(requests) == 1
    assert "SEC_CODE" not in requests[0].url.params
    assert result.source_status[0].status == "success"
    assert "2/2" in result.source_status[0].detail
    assert "缺失 0" in result.source_status[0].detail


def test_share_provider_marks_partial_sse_coverage_stale() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=SSE_SHARE_FIXTURE)

    provider = OfficialCapitalDataProvider(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    result = provider.get_etf_share_rows(
        "2026-07-17", ["510300.SH", "510500.SH"]
    )

    assert len(requests) == 1
    assert "SEC_CODE" not in requests[0].url.params
    assert [row.symbol for row in result.rows] == ["510300.SH"]
    assert result.source_status[0].status == "stale"
    assert "1/2" in result.source_status[0].detail
    assert "缺失 1" in result.source_status[0].detail


def test_share_provider_preserves_all_wrong_date_sse_rows_but_marks_current_stale() -> None:
    symbols = ["510300.SH", "510500.SH"]

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": [
                    {
                        "STAT_DATE": "2026-07-16",
                        "SEC_CODE": symbol.split(".", 1)[0],
                        "TOT_VOL": "100",
                    }
                    for symbol in symbols
                ]
            },
        )

    provider = OfficialCapitalDataProvider(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    result = provider.get_etf_share_rows("2026-07-17", symbols)

    assert {row.symbol for row in result.rows} == set(symbols)
    assert {row.trade_date for row in result.rows} == {"2026-07-16"}
    assert result.source_status[0].status == "stale"
    assert "当日有效 0/2" in result.source_status[0].detail
    assert "缺失 2" in result.source_status[0].detail
    assert "2026-07-16" in result.source_status[0].detail


def test_share_provider_counts_only_current_rows_in_mixed_date_sse_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": [
                    {
                        "STAT_DATE": "2026-07-17",
                        "SEC_CODE": "510300",
                        "TOT_VOL": "100",
                    },
                    {
                        "STAT_DATE": "2026-07-16",
                        "SEC_CODE": "510500",
                        "TOT_VOL": "100",
                    },
                ]
            },
        )

    provider = OfficialCapitalDataProvider(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    result = provider.get_etf_share_rows(
        "2026-07-17", ["510300.SH", "510500.SH"]
    )

    assert [(row.symbol, row.trade_date) for row in result.rows] == [
        ("510300.SH", "2026-07-17"),
        ("510500.SH", "2026-07-16"),
    ]
    assert result.source_status[0].status == "stale"
    assert "当日有效 1/2" in result.source_status[0].detail
    assert "缺失 1" in result.source_status[0].detail
    assert "2026-07-16" in result.source_status[0].detail


def test_share_provider_collects_the_ten_etf_universe_without_live_calls() -> None:
    symbols = [
        "510050.SH",
        "510300.SH",
        "510500.SH",
        "512100.SH",
        "510230.SH",
        "588080.SH",
        "159915.SZ",
        "159919.SZ",
        "159922.SZ",
        "159845.SZ",
    ]
    sse_codes = [symbol.split(".", 1)[0] for symbol in symbols[:6]]
    szse_codes = [symbol.split(".", 1)[0] for symbol in symbols[6:]]
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "query.sse.com.cn":
            return httpx.Response(
                200,
                json={
                    "result": [
                        {
                            "STAT_DATE": "2026-07-17",
                            "SEC_CODE": code,
                            "SEC_NAME": f"ETF {code}",
                            "TOT_VOL": "100",
                        }
                        for code in [*sse_codes, "999999"]
                    ]
                },
            )
        if request.url.host == "www.szse.cn":
            code = request.url.params["txtQueryKeyAndJC"]
            assert code in szse_codes
            return httpx.Response(
                200,
                json=[
                    {
                        "metadata": {
                            "subname": "2026-07-20",
                            "cols": {"dqgm": "当前规模（2026-07-17）"},
                        },
                        "data": [
                            {
                                "sys_key": code,
                                "kzjcurl": f"ETF {code}",
                                "dqgm": "100",
                            }
                        ],
                    }
                ],
            )
        raise AssertionError(f"unexpected request: {request.url}")

    provider = OfficialCapitalDataProvider(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    result = provider.get_etf_share_rows("2026-07-17", symbols)

    sse_requests = [request for request in requests if request.url.host == "query.sse.com.cn"]
    szse_requests = [request for request in requests if request.url.host == "www.szse.cn"]
    assert len(sse_requests) == 1
    assert sse_requests[0].url.params["STAT_DATE"] == "2026-07-17"
    assert "SEC_CODE" not in sse_requests[0].url.params
    assert [request.url.params["txtQueryKeyAndJC"] for request in szse_requests] == szse_codes
    assert [row.symbol for row in result.rows] == symbols
    assert [(status.source, status.status) for status in result.source_status] == [
        ("上交所ETF份额", "success"),
        ("深交所ETF份额", "success"),
    ]
    assert "份额日期 2026-07-17" in result.source_status[1].detail
    assert result.request_failures == 0
    assert result.available_trade_dates == ("2026-07-17",)


def test_share_provider_exposes_strictly_rejected_official_metadata_dates() -> None:
    symbols = ["510300.SH", "159915.SZ"]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "query.sse.com.cn":
            return httpx.Response(
                200,
                json={
                    "result": [
                        {
                            "STAT_DATE": "2026-07-17",
                            "SEC_CODE": "510300",
                            "TOT_VOL": "100",
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json=[
                {
                    "metadata": {
                        "subname": "2026-07-20",
                        "cols": {"dqgm": "当前规模（2026-07-17）"},
                    },
                    "data": [{"sys_key": "159915", "dqgm": "100"}],
                }
            ],
        )

    provider = OfficialCapitalDataProvider(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    result = provider.get_etf_share_rows("2026-07-20", symbols)

    assert [row.symbol for row in result.rows] == ["510300.SH"]
    assert result.request_failures == 0
    assert result.available_trade_dates == ("2026-07-17",)
    assert "份额日期 2026-07-17" in result.source_status[1].detail


def test_share_provider_marks_partial_szse_coverage_stale() -> None:
    symbols = ["159915.SZ", "159919.SZ", "159922.SZ"]

    def handler(request: httpx.Request) -> httpx.Response:
        code = request.url.params["txtQueryKeyAndJC"]
        if code == "159922":
            return httpx.Response(503, json={"error": "temporary"})
        exchange_date = "2026-07-17" if code == "159915" else "2026-07-16"
        return httpx.Response(
            200,
            json=[
                {
                    "metadata": {
                        "subname": "2026-07-20",
                        "cols": {"dqgm": f"当前规模（{exchange_date}）"},
                    },
                    "data": [{"sys_key": code, "dqgm": "100"}],
                }
            ],
        )

    provider = OfficialCapitalDataProvider(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    result = provider.get_etf_share_rows("2026-07-17", symbols)

    assert [row.symbol for row in result.rows] == ["159915.SZ"]
    assert result.source_status[0].status == "stale"
    assert result.source_status[0].detail == (
        "当日有效 1/3 只；1 只请求失败；1 只日期或空数据拒绝；"
        "深市不补造历史；份额日期 2026-07-16, 2026-07-17"
    )
    assert result.request_failures == 1
    assert result.available_trade_dates == ("2026-07-16", "2026-07-17")
    assert getattr(result, "failed_symbols", ()) == ("159922.SZ",)
    assert getattr(result, "rejected_symbols", ()) == ("159919.SZ",)


def test_share_provider_reports_all_date_rejected_szse_coverage_as_stale() -> None:
    symbols = ["159915.SZ", "159919.SZ"]

    def handler(request: httpx.Request) -> httpx.Response:
        code = request.url.params["txtQueryKeyAndJC"]
        exchange_date = "2026-07-16" if code == "159915" else "2026-02-30"
        return httpx.Response(
            200,
            json=[
                {
                    "metadata": {
                        "subname": "2026-07-20",
                        "cols": {"dqgm": f"当前规模（{exchange_date}）"},
                    },
                    "data": [{"sys_key": code, "dqgm": "100"}],
                }
            ],
        )

    provider = OfficialCapitalDataProvider(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    result = provider.get_etf_share_rows("2026-07-17", symbols)

    assert result.rows == []
    assert result.source_status[0].status == "stale"
    assert result.source_status[0].detail == (
        "当日有效 0/2 只；0 只请求失败；2 只日期或空数据拒绝；"
        "深市不补造历史；份额日期 2026-07-16"
    )


def test_share_provider_keeps_all_request_failures_failed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "temporary"})

    provider = OfficialCapitalDataProvider(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    result = provider.get_etf_share_rows("2026-07-17", ["159915.SZ", "159919.SZ"])

    assert result.rows == []
    assert result.source_status[0].status == "failed"


def test_sina_report_dates_parser_reads_only_holder_period_options() -> None:
    html = """
    <select id="other"><option value="ignore">ignore</option></select>
    <select id="tc_slt">
      <option value="2025-12-31">2025-12-31</option>
      <option value="2025-06-30">2025-06-30</option>
    </select>
    """

    assert parse_sina_report_dates(html) == ["2025-12-31", "2025-06-30"]


def test_sina_holder_parser_uses_exact_entity_whitelist() -> None:
    payload = {
        "result": {
            "data": [
                {"cyrmc": "中央汇金资产管理有限责任公司", "cyfe": "37858500000", "zfeb": "42.62"},
                {"cyrmc": "中国证券金融股份有限公司", "cyfe": "1000000", "zfeb": "0.10"},
                {"cyrmc": "深圳证金投资管理有限公司", "cyfe": "900000", "zfeb": "0.09"},
                {"cyrmc": "普通联接基金", "cyfe": "800000", "zfeb": "0.08"},
            ]
        }
    }

    positions = parse_sina_holder_payload(
        payload,
        symbol="510300.SH",
        name="300ETF",
        report_period="2025-12-31",
    )

    assert [item.entity_name for item in positions] == [
        "中央汇金资产管理有限责任公司",
        "中国证券金融股份有限公司",
    ]
    assert positions[0].shares == 37_858_500_000
    assert positions[0].holding_pct == 42.62
