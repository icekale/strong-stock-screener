from __future__ import annotations

from datetime import datetime, timedelta
from threading import Event

import pytest

import app.services.market_sentiment_analysis_sampler as sampler_module
from app.models import SentimentAnalysisResult, SentimentPercentileAnalysisResponse
from app.services.market_sentiment_analysis_sampler import MarketSentimentAnalysisSampler


class Clock:
    def __init__(self, value: str) -> None:
        self.current = datetime.fromisoformat(value)

    def __call__(self) -> datetime:
        return self.current


def analysis(
    trade_date: str,
    status: str,
    *,
    retry_after: str | None = None,
) -> SentimentPercentileAnalysisResponse:
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


def test_sampler_waits_until_1515_then_completes_current_date() -> None:
    clock = Clock("2026-07-22T15:14:00+08:00")
    calls: list[datetime] = []
    resolved: list[datetime] = []
    sampler = MarketSentimentAnalysisSampler(
        latest_completed_trade_date=lambda now: resolved.append(now) or "2026-07-22",
        generate_latest=lambda now: calls.append(now) or analysis("2026-07-22", "ready"),
        clock=clock,
    )

    assert sampler.sample_once() is False
    assert resolved == [clock.current]
    clock.current = datetime.fromisoformat("2026-07-22T15:15:00+08:00")
    assert sampler.sample_once() is True
    assert sampler.sample_once() is True
    assert resolved == [
        datetime.fromisoformat("2026-07-22T15:14:00+08:00"),
        clock.current,
        clock.current,
    ]
    assert calls == [clock.current, clock.current]


def test_sampler_catches_up_latest_completed_friday_after_weekend_restart() -> None:
    clock = Clock("2026-07-26T10:00:00+08:00")
    calls: list[datetime] = []
    sampler = MarketSentimentAnalysisSampler(
        latest_completed_trade_date=lambda _now: "2026-07-24",
        generate_latest=lambda now: calls.append(now) or analysis("2026-07-24", "ready"),
        clock=clock,
    )

    assert sampler.sample_once() is True
    assert sampler.sample_once() is True
    assert calls == [clock.current, clock.current]


def test_sampler_catches_up_prior_trade_date_on_weekday_morning() -> None:
    clock = Clock("2026-07-27T10:00:00+08:00")
    calls: list[datetime] = []
    sampler = MarketSentimentAnalysisSampler(
        latest_completed_trade_date=lambda _now: "2026-07-24",
        generate_latest=lambda now: calls.append(now) or analysis("2026-07-24", "ready"),
        clock=clock,
    )

    assert sampler.sample_once() is True
    assert sampler.sample_once() is True
    assert calls == [clock.current, clock.current]


def test_sampler_rechecks_ready_date_so_changed_generation_identity_can_run() -> None:
    clock = Clock("2026-07-22T15:15:00+08:00")
    responses = [
        analysis("2026-07-22", "ready").model_copy(update={"input_hash": "a" * 64}),
        analysis("2026-07-22", "ready").model_copy(update={"input_hash": "b" * 64}),
    ]
    calls: list[datetime] = []

    def generate_latest(now: datetime) -> SentimentPercentileAnalysisResponse:
        calls.append(now)
        return responses.pop(0)

    sampler = MarketSentimentAnalysisSampler(
        latest_completed_trade_date=lambda _now: "2026-07-22",
        generate_latest=generate_latest,
        clock=clock,
    )

    assert sampler.sample_once() is True
    assert sampler.sample_once() is True
    assert calls == [clock.current, clock.current]


def test_sampler_rechecks_failed_date_so_changed_generation_identity_can_run() -> None:
    clock = Clock("2026-07-22T15:15:00+08:00")
    responses = [
        analysis(
            "2026-07-22",
            "failed",
            retry_after="2026-07-22T15:45:00+08:00",
        ).model_copy(update={"input_hash": "a" * 64}),
        analysis("2026-07-22", "ready").model_copy(update={"input_hash": "b" * 64}),
    ]
    calls: list[datetime] = []

    def generate_latest(now: datetime) -> SentimentPercentileAnalysisResponse:
        calls.append(now)
        return responses.pop(0)

    sampler = MarketSentimentAnalysisSampler(
        latest_completed_trade_date=lambda _now: "2026-07-22",
        generate_latest=generate_latest,
        clock=clock,
    )

    assert sampler.sample_once() is True
    clock.current += timedelta(minutes=1)
    assert sampler.sample_once() is True
    assert calls == [
        datetime.fromisoformat("2026-07-22T15:15:00+08:00"),
        datetime.fromisoformat("2026-07-22T15:16:00+08:00"),
    ]


def test_sampler_rechecks_consecutive_exchange_holidays_for_identity_changes() -> None:
    clock = Clock("2026-10-01T15:15:00+08:00")
    calls: list[datetime] = []
    sampler = MarketSentimentAnalysisSampler(
        latest_completed_trade_date=lambda _now: "2026-09-30",
        generate_latest=lambda now: calls.append(now) or analysis("2026-09-30", "ready"),
        clock=clock,
    )

    assert sampler.sample_once() is True
    clock.current = datetime.fromisoformat("2026-10-02T15:15:00+08:00")
    assert sampler.sample_once() is True
    assert calls == [
        datetime.fromisoformat("2026-10-01T15:15:00+08:00"),
        datetime.fromisoformat("2026-10-02T15:15:00+08:00"),
    ]


def test_sampler_delegates_failed_retry_cooldown_to_generation_service() -> None:
    clock = Clock("2026-07-22T15:15:00+08:00")
    retry_after = "2026-07-22T15:45:00+08:00"
    responses = [
        analysis("2026-07-22", "failed", retry_after=retry_after),
        analysis("2026-07-22", "failed", retry_after=retry_after),
        analysis("2026-07-22", "ready"),
    ]
    calls: list[datetime] = []

    def generate_latest(now: datetime) -> SentimentPercentileAnalysisResponse:
        calls.append(now)
        return responses.pop(0)

    sampler = MarketSentimentAnalysisSampler(
        latest_completed_trade_date=lambda _now: "2026-07-22",
        generate_latest=generate_latest,
        clock=clock,
    )

    assert sampler.sample_once() is True
    clock.current += timedelta(minutes=29)
    assert sampler.sample_once() is True
    clock.current += timedelta(minutes=1)
    assert sampler.sample_once() is True
    assert calls == [
        datetime.fromisoformat("2026-07-22T15:15:00+08:00"),
        datetime.fromisoformat("2026-07-22T15:44:00+08:00"),
        datetime.fromisoformat("2026-07-22T15:45:00+08:00"),
    ]


def test_sampler_thread_logs_exception_and_keeps_running(caplog: pytest.LogCaptureFixture) -> None:
    clock = Clock("2026-07-22T15:15:00+08:00")
    completed = Event()
    calls = 0

    def generate_latest(_now: datetime) -> SentimentPercentileAnalysisResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary failure")
        completed.set()
        return analysis("2026-07-22", "ready")

    sampler = MarketSentimentAnalysisSampler(
        latest_completed_trade_date=lambda _now: "2026-07-22",
        generate_latest=generate_latest,
        clock=clock,
        poll_seconds=0.01,
    )
    sampler.start()
    assert completed.wait(timeout=1)
    sampler.stop_and_wait()

    assert calls == 2
    assert "market sentiment analysis sampling failed" in caplog.text
    assert not sampler.running


def test_sampler_stop_and_wait_joins_cleanly() -> None:
    clock = Clock("2026-07-22T15:15:00+08:00")
    started = Event()
    release = Event()

    def generate_latest(_now: datetime) -> SentimentPercentileAnalysisResponse:
        started.set()
        assert release.wait(timeout=1)
        return analysis("2026-07-22", "ready")

    sampler = MarketSentimentAnalysisSampler(
        latest_completed_trade_date=lambda _now: "2026-07-22",
        generate_latest=generate_latest,
        clock=clock,
        poll_seconds=0.01,
    )
    sampler.start()
    assert started.wait(timeout=1)
    release.set()
    sampler.stop_and_wait()

    assert not sampler.running


def test_sampler_thread_uses_its_own_stop_event_after_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = Clock("2026-07-22T15:15:00+08:00")
    completed = Event()

    class ImmediateStopEvent:
        def __init__(self) -> None:
            self._stopped = False
            self._wait_calls = 0

        def is_set(self) -> bool:
            return self._stopped

        def set(self) -> None:
            self._stopped = True

        def wait(self, _seconds: float) -> bool:
            self._wait_calls += 1
            if self._wait_calls == 1:
                return False
            self._stopped = True
            return True

    monkeypatch.setattr(sampler_module, "Event", ImmediateStopEvent)
    sampler = MarketSentimentAnalysisSampler(
        latest_completed_trade_date=lambda _now: "2026-07-22",
        generate_latest=lambda _now: completed.set() or analysis("2026-07-22", "ready"),
        clock=clock,
    )

    sampler.start()
    assert completed.wait(timeout=1)
    sampler.stop_and_wait()
