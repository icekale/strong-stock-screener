from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    SentimentPercentileFactor,
    SentimentPercentileFactors,
    SentimentPercentilePoint,
    SentimentPercentileResponse,
    StrongStockDataUnavailable,
)


def percentile_response_fixture() -> SentimentPercentileResponse:
    factor = SentimentPercentileFactor(score=50, raw_value=0, raw_unit="%")
    point = SentimentPercentilePoint(
        trade_date="2026-07-21",
        score=50,
        level="中性",
        factors=SentimentPercentileFactors(
            volume=factor,
            index_move_5d=factor,
            price_position=factor,
            amplitude_5d=factor,
            volume_trend=factor,
        ),
    )
    return SentimentPercentileResponse(
        weights={
            "volume": 0.2,
            "index_move_5d": 0.2,
            "price_position": 0.2,
            "amplitude_5d": 0.2,
            "volume_trend": 0.2,
        },
        latest_complete_trade_date=point.trade_date,
        selected_trade_date=point.trade_date,
        selected=point,
        history=[point],
        generated_at="2026-07-22T15:20:00+08:00",
    )


class FakePercentileService:
    def __init__(self, response: SentimentPercentileResponse) -> None:
        self.response = response
        self.calls: list[tuple[str | None, bool]] = []

    def get(self, as_of: str | None = None, refresh: bool = False, now=None):
        self.calls.append((as_of, refresh))
        return self.response


class RaisingPercentileService:
    def __init__(self, error: StrongStockDataUnavailable) -> None:
        self.error = error

    def get(self, as_of: str | None = None, refresh: bool = False, now=None):
        raise self.error


def test_percentile_api_returns_selected_history_and_metadata(monkeypatch) -> None:
    fixture = percentile_response_fixture()
    service = FakePercentileService(fixture)
    monkeypatch.setattr(app.state, "market_sentiment_percentile_service", service, raising=False)

    with TestClient(app) as client:
        response = client.get(
            "/api/short-term/sentiment/percentile",
            params={"as_of": "2026-07-21", "refresh": "false"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_version"] == "market-sentiment-percentile-v2"
    assert payload["benchmark_symbol"] == "000985.SH"
    assert payload["selected_trade_date"] == "2026-07-21"
    assert service.calls == [("2026-07-21", False)]


def test_percentile_api_rejects_invalid_date() -> None:
    with TestClient(app) as client:
        response = client.get("/api/short-term/sentiment/percentile?as_of=2026-99-99")

    assert response.status_code == 422


def test_percentile_api_forwards_refresh_to_service(monkeypatch) -> None:
    service = FakePercentileService(percentile_response_fixture())
    monkeypatch.setattr(app.state, "market_sentiment_percentile_service", service, raising=False)

    with TestClient(app) as client:
        response = client.get("/api/short-term/sentiment/percentile?refresh=true")

    assert response.status_code == 200
    assert service.calls == [(None, True)]


def test_percentile_api_returns_503_when_data_is_unavailable(monkeypatch) -> None:
    service = RaisingPercentileService(StrongStockDataUnavailable("unavailable"))
    monkeypatch.setattr(app.state, "market_sentiment_percentile_service", service, raising=False)

    with TestClient(app) as client:
        response = client.get("/api/short-term/sentiment/percentile?refresh=true")

    assert response.status_code == 503
    assert response.json()["detail"] == "unavailable"
