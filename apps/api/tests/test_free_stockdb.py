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


def test_free_stockdb_client_uses_vals_range_contract() -> None:
    http = RecordingHttpClient(payload=[{"code": "600000", "date": "20260710100000"}])
    client = FreeStockDbClient(base_url="http://stockdb.test:7899", http_client=http)

    rows = client.vals(
        table="分钟k",
        k1="600000",
        k2="20260701000000<20260710235959",
    )

    assert rows == [{"code": "600000", "date": "20260710100000"}]
    assert http.requests == [
        (
            "http://stockdb.test:7899/",
            {
                "cmd": "vals",
                "t": "分钟k",
                "k1": "600000",
                "k2": "20260701000000<20260710235959",
            },
        )
    ]
