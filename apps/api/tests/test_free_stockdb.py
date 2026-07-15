from __future__ import annotations

from dataclasses import dataclass

from app.providers.free_stockdb import FreeStockDbClient


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
        self.requests: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, *, params: dict[str, str]) -> RecordingResponse:
        self.requests.append((url, params))
        return RecordingResponse(self.payload)


def test_free_stockdb_client_uses_documented_get_range_contract() -> None:
    http = RecordingHttpClient(payload=[{"code": "600000", "date": "20260710100000"}])
    client = FreeStockDbClient(base_url="http://stockdb.test:7899", http_client=http)

    rows = client.get(
        table="分钟k",
        k1="600000",
        k2="20260701000000<20260710235959",
    )

    assert rows == [{"code": "600000", "date": "20260710100000"}]
    assert http.requests == [
        (
            "http://stockdb.test:7899/",
            {
                "cmd": "get",
                "t": "分钟k:600000:20260701<20260710",
            },
        )
    ]


def test_free_stockdb_client_keeps_legacy_vals_contract() -> None:
    http = RecordingHttpClient(payload=[{"code": "600000"}])
    client = FreeStockDbClient(base_url="http://stockdb.test:7899", http_client=http)

    assert client.vals(table="日k", k1="all:", k2="fwd:20260701,20260703") == [
        {"code": "600000"}
    ]
    assert http.requests == [
        (
            "http://stockdb.test:7899/",
            {
                "cmd": "vals",
                "t": "日k",
                "k1": "all:",
                "k2": "fwd:20260701,20260703",
            },
        )
    ]


def test_free_stockdb_get_unwraps_wildcard_key_value_rows() -> None:
    http = RecordingHttpClient(payload=[["日k:600000:20260703", {"code": "600000"}]])
    client = FreeStockDbClient(base_url="http://stockdb.test:7899", http_client=http)

    assert client.get(table="日k", k1="600000", k2="202607*") == [{"code": "600000"}]
    assert http.requests == [
        (
            "http://stockdb.test:7899/",
            {
                "cmd": "get",
                "t": "日k:600000:202607*",
            },
        )
    ]
