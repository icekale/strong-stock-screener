from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.services.chanlun.research_history import FreeStockDbResearchSource


@dataclass
class RecordingResponse:
    payload: object

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class RecordingHttpClient:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.requests: list[dict[str, str]] = []

    def get(self, _url: str, *, params: dict[str, str]) -> RecordingResponse:
        self.requests.append(params)
        return RecordingResponse(self.payload)


def test_minute_source_uses_stockdb_range_contract() -> None:
    http = RecordingHttpClient(payload=[_minute_row("20260710100000")])
    source = FreeStockDbResearchSource(
        base_url="http://stockdb.test:7899",
        http_client=http,
    )

    rows = source.minute_bars("600000.SH", start="20260701", end="20260710")

    assert http.requests[0]["cmd"] == "get"
    assert http.requests[0]["t"] == "分钟k:600000:2026*"
    assert rows[0].date == "2026-07-10T10:00:00+08:00"


def test_daily_source_exposes_raw_rows_for_candidate_reconstruction() -> None:
    http = RoutingHttpClient()
    source = FreeStockDbResearchSource(base_url="http://stockdb.test:7899", http_client=http)

    rows = source.daily_rows(start="20260701", end="20260710")

    assert rows[0]["code"] == "600000"
    assert http.requests[0]["t"] == "股票代码"


def test_daily_source_reads_codes_by_year_and_unwraps_rows() -> None:
    http = RoutingHttpClient()
    source = FreeStockDbResearchSource(base_url="http://stockdb.test:7899", http_client=http)

    rows = source.daily_rows(start="20260701", end="20260710")

    assert rows[0]["code"] == "600000"
    assert [request["t"] for request in http.requests] == [
        "股票代码",
        "日k:600000:202607*",
    ]


def test_daily_source_skips_completed_months_on_resume() -> None:
    http = RoutingHttpClient()
    source = FreeStockDbResearchSource(base_url="http://stockdb.test:7899", http_client=http)

    rows = list(
        source.daily_rows_by_year(
            start="20260701",
            end="20260810",
            skip_chunks={"202607"},
        )
    )

    assert [label for label, _rows in rows] == ["202608"]
    assert [request["t"] for request in http.requests] == [
        "股票代码",
        "日k:600000:202608*",
    ]


def test_daily_source_retries_transient_timeout() -> None:
    http = FlakyHttpClient()
    source = FreeStockDbResearchSource(
        base_url="http://stockdb.test:7899",
        http_client=http,
        max_workers=1,
        retry_backoff_seconds=0,
    )

    rows = source.daily_rows(start="20260701", end="20260710")

    assert rows[0]["code"] == "600000"
    assert len(http.requests) == 4


def test_history_source_discards_invalid_rows_and_future_bars() -> None:
    http = RecordingHttpClient(
        payload=[
            _minute_row("20260710100000"),
            _minute_row("20260711100000"),
            {"date": "20260710100500", "open": 0, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 1},
        ]
    )
    source = FreeStockDbResearchSource(base_url="http://stockdb.test:7899", http_client=http)

    rows = source.minute_bars("600000.SH", start="20260701", end="20260710")

    assert [row.date for row in rows] == ["2026-07-10T10:00:00+08:00"]


def _minute_row(timestamp: str) -> dict[str, object]:
    return {
        "date": timestamp,
        "open": 10,
        "high": 10.2,
        "low": 9.9,
        "close": 10.1,
        "volume": 1000,
        "amount": 10100,
    }


class RoutingHttpClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, str]] = []

    def get(self, _url: str, *, params: dict[str, str]) -> RecordingResponse:
        self.requests.append(params)
        if params["t"] == "股票代码":
            return RecordingResponse({"6": ["600000"], "0": []})
        return RecordingResponse(
            [[
                "日k:600000:20260703",
                {
                    "date": 20260703,
                    "code": "600000",
                    "name": "测试股份",
                    "open": 10,
                    "high": 11,
                    "low": 9.8,
                    "close": 10.8,
                    "pre_close": 10,
                    "volume": 1000,
                    "amount": 10800,
                },
            ]]
        )


class FlakyHttpClient(RoutingHttpClient):
    def get(self, _url: str, *, params: dict[str, str]) -> RecordingResponse:
        self.requests.append(params)
        if params["t"] == "股票代码":
            if len(self.requests) == 1:
                raise httpx.ReadTimeout("temporary selector timeout")
            return RecordingResponse({"6": ["600000"], "0": []})
        if len(self.requests) == 3:
            raise httpx.ReadTimeout("temporary timeout")
        return RecordingResponse(
            [[
                "日k:600000:20260703",
                {
                    "date": 20260703,
                    "code": "600000",
                    "name": "测试股份",
                    "open": 10,
                    "high": 11,
                    "low": 9.8,
                    "close": 10.8,
                    "pre_close": 10,
                    "volume": 1000,
                    "amount": 10800,
                },
            ]]
        )
