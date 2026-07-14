from __future__ import annotations

from dataclasses import dataclass

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

    assert http.requests[0]["cmd"] == "vals"
    assert http.requests[0]["t"] == "分钟k"
    assert http.requests[0]["k1"] == "600000"
    assert http.requests[0]["k2"] == "20260701000000<20260710235959"
    assert rows[0].date == "2026-07-10T10:00:00+08:00"


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
