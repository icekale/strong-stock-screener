from __future__ import annotations

from datetime import datetime
from threading import Event
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.models import (
    SentimentAnalysisResult,
    SentimentPercentileAnalysisResponse,
    SentimentPercentileFactor,
    SentimentPercentileFactors,
    SentimentPercentilePoint,
    SentimentPercentileResponse,
    StrongStockDataUnavailable,
)


ORIGINAL_EFFECTIVE_SETTINGS = main._effective_settings


def percentile_response_fixture() -> SentimentPercentileResponse:
    factor = SentimentPercentileFactor(score=50, raw_value=0, raw_unit="%")
    points = [
        SentimentPercentilePoint(
            trade_date="2026-07-21",
            score=48,
            level="中性",
            factors=SentimentPercentileFactors(
                volume=factor,
                index_move_5d=factor,
                price_position=factor,
                amplitude_5d=factor,
                volume_trend=factor,
            ),
        ),
        SentimentPercentilePoint(
            trade_date="2026-07-22",
            score=62,
            level="偏热",
            factors=SentimentPercentileFactors(
                volume=factor,
                index_move_5d=factor,
                price_position=factor,
                amplitude_5d=factor,
                volume_trend=factor,
            ),
        ),
    ]
    return SentimentPercentileResponse(
        weights={
            "volume": 0.2,
            "index_move_5d": 0.2,
            "price_position": 0.2,
            "amplitude_5d": 0.2,
            "volume_trend": 0.2,
        },
        latest_complete_trade_date="2026-07-22",
        selected_trade_date="2026-07-22",
        selected=points[-1],
        history=points,
        generated_at="2026-07-22T15:20:00+08:00",
    )


def analysis(trade_date: str, status: str, *, retry_after: str | None = None):
    result = (
        SentimentAnalysisResult(
            market_conclusion="市场情绪读数为 62。",
            key_drivers=["综合分 62", "量能分 60"],
            factor_divergence="5 日指标存在分化。",
            historical_context="历史样本为 37。",
            risk_posture="balanced",
            next_session_watch=["关注综合分 60", "关注量能分 50"],
            risk_note="仅作市场复盘参考，不构成投资建议。",
        )
        if status == "ready"
        else None
    )
    return SentimentPercentileAnalysisResponse(
        trade_date=trade_date,
        status=status,  # type: ignore[arg-type]
        input_hash="a" * 64 if status in {"pending", "ready", "failed"} else None,
        retry_after=retry_after,
        result=result,
    )


class FakePercentileService:
    def __init__(self, response: SentimentPercentileResponse) -> None:
        self.response = response
        self.calls: list[tuple[str | None, bool, datetime | None]] = []

    def get(
        self,
        as_of: str | None = None,
        refresh: bool = False,
        now: datetime | None = None,
    ) -> SentimentPercentileResponse:
        self.calls.append((as_of, refresh, now))
        selected = (
            self.response.selected
            if as_of is None
            else next((point for point in self.response.history if point.trade_date == as_of), None)
        )
        return self.response.model_copy(
            update={
                "selected": selected,
                "selected_trade_date": selected.trade_date if selected else None,
                "history": self.response.history if as_of is None else [
                    point for point in self.response.history if point.trade_date <= as_of
                ],
            },
            deep=True,
        )


class FakePercentileStore:
    def __init__(self, response: SentimentPercentileResponse | None) -> None:
        self.response = response
        self.calls = 0

    def load(self) -> SentimentPercentileResponse | None:
        self.calls += 1
        return self.response


class FakeAnalysisStore:
    def __init__(self, values: dict[str, SentimentPercentileAnalysisResponse] | None = None) -> None:
        self.values = values or {}

    def load(self, trade_date: str) -> SentimentPercentileAnalysisResponse | None:
        return self.values.get(trade_date)


class FakeAnalysisService:
    def __init__(self, response: SentimentPercentileAnalysisResponse) -> None:
        self.response = response
        self.calls: list[tuple[dict[str, object], object, bool]] = []

    def generate(self, input_payload: dict[str, object], config: object, *, force: bool = False):
        self.calls.append((input_payload, config, force))
        return self.response


class FakeSampler:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop_and_wait(self) -> None:
        self.stopped += 1


class FakeLifecycleService:
    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


@pytest.fixture(autouse=True)
def isolate_analysis_sampler(monkeypatch: pytest.MonkeyPatch) -> FakeSampler:
    sampler = FakeSampler()
    monkeypatch.setattr(app.state, "market_sentiment_analysis_sampler", sampler, raising=False)
    monkeypatch.setattr(app.state, "sentiment_monitor", FakeLifecycleService(), raising=False)
    monkeypatch.setattr(app.state, "gsgf_auto_review_service", FakeLifecycleService(), raising=False)
    for name in (
        "auction_sampler_disabled",
        "sector_workbench_sampler_disabled",
        "capital_signal_sampler_disabled",
        "etf_three_factor_sampler_disabled",
    ):
        monkeypatch.setattr(app.state, name, True, raising=False)
    return sampler


def configured_settings(*, enabled: bool = True, api_key: str = "test-key") -> object:
    settings = ORIGINAL_EFFECTIVE_SETTINGS()
    return settings.model_copy(
        update={
            "ai_analysis": settings.ai_analysis.model_copy(
                update={
                    "enabled": enabled,
                    "api_key": api_key,
                    "provider": "openai_compatible",
                    "model": "test-model",
                }
            )
        }
    )


@pytest.mark.parametrize("status", ["pending", "ready", "failed"])
def test_analysis_get_returns_persisted_lifecycle_states(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    service = FakePercentileService(percentile_response_fixture())
    percentile_store = FakePercentileStore(percentile_response_fixture())
    store = FakeAnalysisStore({"2026-07-22": analysis("2026-07-22", status)})
    monkeypatch.setattr(app.state, "market_sentiment_percentile_service", service, raising=False)
    monkeypatch.setattr(app.state, "market_sentiment_percentile_store", percentile_store, raising=False)
    monkeypatch.setattr(app.state, "market_sentiment_analysis_store", store, raising=False)
    monkeypatch.setattr(main, "_effective_settings", configured_settings)

    with TestClient(app) as client:
        response = client.get("/api/short-term/sentiment/percentile/analysis?trade_date=2026-07-22")

    assert response.status_code == 200
    assert response.json()["status"] == status
    assert service.calls == []
    assert percentile_store.calls == 1


def test_analysis_get_reports_not_generated_and_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePercentileService(percentile_response_fixture())
    monkeypatch.setattr(app.state, "market_sentiment_percentile_service", service, raising=False)
    monkeypatch.setattr(
        app.state,
        "market_sentiment_percentile_store",
        FakePercentileStore(percentile_response_fixture()),
        raising=False,
    )
    monkeypatch.setattr(app.state, "market_sentiment_analysis_store", FakeAnalysisStore(), raising=False)
    monkeypatch.setattr(main, "_effective_settings", configured_settings)

    with TestClient(app) as client:
        response = client.get("/api/short-term/sentiment/percentile/analysis?trade_date=2026-07-22")

    assert response.status_code == 200
    assert response.json()["status"] == "not_generated"

    monkeypatch.setattr(main, "_effective_settings", lambda: configured_settings(enabled=False, api_key=""))
    with TestClient(app) as client:
        response = client.get("/api/short-term/sentiment/percentile/analysis?trade_date=2026-07-22")

    assert response.status_code == 200
    assert response.json()["status"] == "unconfigured"


def test_analysis_get_rejects_date_outside_percentile_history(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakePercentileService(percentile_response_fixture())
    monkeypatch.setattr(app.state, "market_sentiment_percentile_service", service, raising=False)
    monkeypatch.setattr(
        app.state,
        "market_sentiment_percentile_store",
        FakePercentileStore(percentile_response_fixture()),
        raising=False,
    )
    monkeypatch.setattr(app.state, "market_sentiment_analysis_store", FakeAnalysisStore(), raising=False)

    with TestClient(app) as client:
        response = client.get("/api/short-term/sentiment/percentile/analysis?trade_date=2026-07-20")

    assert response.status_code == 404
    assert service.calls == []


def test_generate_analysis_builds_context_and_forwards_force(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    percentile_service = FakePercentileService(percentile_response_fixture())
    analysis_service = FakeAnalysisService(analysis("2026-07-22", "ready"))
    monkeypatch.setattr(app.state, "market_sentiment_percentile_service", percentile_service, raising=False)
    monkeypatch.setattr(app.state, "market_sentiment_analysis_service", analysis_service, raising=False)
    monkeypatch.setattr(app.state, "runs_dir", tmp_path, raising=False)
    monkeypatch.setattr(main, "_effective_settings", configured_settings)
    monkeypatch.setattr(
        main,
        "_build_and_persist_sentiment_snapshots",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/short-term/sentiment/percentile/analysis/generate?trade_date=2026-07-22&force=true"
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert len(analysis_service.calls) == 1
    payload, _config, force = analysis_service.calls[0]
    assert force is True
    assert payload["trade_date"] == "2026-07-22"
    assert payload["market"]["status"] == "unavailable"
    assert payload["validation"] == {
        "source_date": None,
        "status": "unavailable",
        "sample_count": 0,
        "sample_counts": {},
        "conclusion": None,
    }


def test_generate_analysis_reports_percentile_provider_failure_as_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnavailablePercentileService:
        def get(self, **_kwargs: object) -> SentimentPercentileResponse:
            raise StrongStockDataUnavailable("市场情绪分位数据不可用")

    monkeypatch.setattr(
        app.state,
        "market_sentiment_percentile_service",
        UnavailablePercentileService(),
        raising=False,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/short-term/sentiment/percentile/analysis/generate"
            "?trade_date=2026-07-22&force=false"
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "市场情绪分位数据不可用"}


def test_percentile_get_schedules_analysis_without_waiting_for_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = Event()
    release = Event()
    percentile_service = FakePercentileService(percentile_response_fixture())
    sampler = FakeSampler()
    calls = 0

    def generate_latest(_now: datetime):
        nonlocal calls
        calls += 1
        started.set()
        assert release.wait(timeout=1)
        return analysis("2026-07-22", "ready")

    monkeypatch.setattr(app.state, "market_sentiment_percentile_service", percentile_service, raising=False)
    monkeypatch.setattr(app.state, "market_sentiment_analysis_store", FakeAnalysisStore(), raising=False)
    monkeypatch.setattr(app.state, "market_sentiment_analysis_sampler", sampler, raising=False)
    monkeypatch.setattr(main, "_market_sentiment_analysis_now", lambda: datetime.fromisoformat("2026-07-22T15:16:00+08:00"))
    monkeypatch.setattr(main, "_generate_latest_market_sentiment_analysis", generate_latest)
    monkeypatch.setattr(main, "_effective_settings", configured_settings)
    main._MARKET_SENTIMENT_ANALYSIS_CATCHUP_DATES.discard("2026-07-22")

    with TestClient(app) as client:
        response = client.get("/api/short-term/sentiment/percentile")
        assert response.status_code == 200
        assert started.wait(timeout=1)
        duplicate = client.get("/api/short-term/sentiment/percentile")
        assert duplicate.status_code == 200
        assert calls == 1
        assert sampler.started == 1
        release.set()

    assert sampler.stopped == 1


def test_percentile_get_retries_catchup_after_transient_thread_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    class InlineThread:
        def __init__(self, *, target, **_kwargs: object) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    def generate_latest(_now: datetime):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary provider failure")
        return analysis("2026-07-22", "ready")

    monkeypatch.setattr(
        app.state,
        "market_sentiment_percentile_service",
        FakePercentileService(percentile_response_fixture()),
        raising=False,
    )
    monkeypatch.setattr(app.state, "market_sentiment_analysis_store", FakeAnalysisStore(), raising=False)
    monkeypatch.setattr(
        main,
        "_market_sentiment_analysis_now",
        lambda: datetime.fromisoformat("2026-07-22T15:16:00+08:00"),
    )
    monkeypatch.setattr(main, "_generate_latest_market_sentiment_analysis", generate_latest)
    monkeypatch.setattr(main, "_effective_settings", configured_settings)
    monkeypatch.setattr(main, "Thread", InlineThread)
    main._MARKET_SENTIMENT_ANALYSIS_CATCHUP_DATES.discard("2026-07-22")

    try:
        with TestClient(app) as client:
            first = client.get("/api/short-term/sentiment/percentile")
            second = client.get("/api/short-term/sentiment/percentile")
    finally:
        main._MARKET_SENTIMENT_ANALYSIS_CATCHUP_DATES.discard("2026-07-22")

    assert first.status_code == 200
    assert second.status_code == 200
    assert attempts == 2
