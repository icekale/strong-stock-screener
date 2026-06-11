from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    KlineBar,
    StrongStockCandidate,
    StrongStockDataUnavailable,
    StrongStockSourceStatus,
)
from app.providers.watchlist import WatchlistSnapshot, WatchlistItem


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
                limit_up_evidence=["20日内涨停"],
            ),
            StrongStockCandidate(
                symbol="002000.SZ",
                name="示例股份",
                limit_up_evidence=["20日内涨停"],
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


class FakeQuoteProvider:
    source_name = "TickFlow"

    def status(self):
        from app.models import StrongStockSourceStatus

        return StrongStockSourceStatus(source="TickFlow", status="missing_key", detail="TICKFLOW_API_KEY 未配置")


def _client(tmp_path: Path, candidate_provider: object | None = None) -> TestClient:
    app.state.candidate_provider = candidate_provider or FakeCandidateProvider()
    app.state.kline_provider = FakeKlineProvider()
    app.state.quote_provider = FakeQuoteProvider()
    app.state.watchlist_snapshot = WatchlistSnapshot(
        items=[WatchlistItem(symbol="002000.SZ", name="示例股份")]
    )
    app.state.runs_dir = tmp_path
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


def test_screen_run_returns_items_and_persists_latest_without_empty_status(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/screen/runs", json={"trade_date": "2026-06-11", "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-11"
    assert payload["items"][0]["status"] == "focus"
    assert all(item["status"] != "empty" for item in payload["items"])
    assert payload["watchlist_risk_items"][0]["risk_action"] == "empty"

    latest_response = client.get("/api/screen/runs/latest")
    assert latest_response.status_code == 200
    assert latest_response.json()["trade_date"] == "2026-06-11"
    assert (tmp_path / "latest.json").exists()


def test_screen_run_rejects_candidate_source_failure(tmp_path: Path) -> None:
    client = _client(tmp_path, candidate_provider=FailingCandidateProvider())

    response = client.post("/api/screen/runs", json={"trade_date": "2026-06-11", "limit": 10})

    assert response.status_code == 503
    assert "候选池数据源失败" in response.json()["detail"]


def test_latest_returns_404_before_first_run(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/screen/runs/latest")

    assert response.status_code == 404
