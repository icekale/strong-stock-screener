from __future__ import annotations

from datetime import datetime
from threading import Event

from app.services.etf_three_factor_sampler import EtfThreeFactorSampler


class Clock:
    def __init__(self, value: str) -> None:
        self.current = datetime.fromisoformat(value)

    def __call__(self) -> datetime:
        return self.current


def test_sampler_runs_intraday_once_per_minute() -> None:
    calls: list[dict[str, object]] = []
    current = Clock("2026-07-22T10:00:10")
    sampler = EtfThreeFactorSampler(
        scan=lambda **kwargs: calls.append(kwargs),
        clock=current,
    )

    assert sampler.sample_once() is True
    assert sampler.sample_once() is False
    assert len(calls) == 1


def test_sampler_samples_only_trading_sessions_and_scheduled_refreshes() -> None:
    calls: list[dict[str, object]] = []
    current = Clock("2026-07-22T09:29:00")
    sampler = EtfThreeFactorSampler(
        scan=lambda **kwargs: calls.append(kwargs),
        clock=current,
    )

    assert sampler.sample_once() is False
    current.current = datetime.fromisoformat("2026-07-22T09:30:00")
    assert sampler.sample_once() is True
    current.current = datetime.fromisoformat("2026-07-22T11:30:00")
    assert sampler.sample_once() is True
    current.current = datetime.fromisoformat("2026-07-22T12:00:00")
    assert sampler.sample_once() is False
    current.current = datetime.fromisoformat("2026-07-22T13:00:00")
    assert sampler.sample_once() is True
    current.current = datetime.fromisoformat("2026-07-22T15:00:00")
    assert sampler.sample_once() is True
    current.current = datetime.fromisoformat("2026-07-22T15:05:00")
    assert sampler.sample_once() is True
    assert sampler.sample_once() is False
    current.current = datetime.fromisoformat("2026-07-22T19:05:00")
    assert sampler.sample_once() is True
    assert sampler.sample_once() is False
    current.current = datetime.fromisoformat("2026-07-22T19:35:00")
    assert sampler.sample_once() is True
    assert sampler.sample_once() is False
    current.current = datetime.fromisoformat("2026-07-25T10:00:00")
    assert sampler.sample_once() is False

    assert [call["now"].strftime("%H:%M") for call in calls] == [
        "09:30",
        "11:30",
        "13:00",
        "15:00",
        "15:05",
        "19:05",
        "19:35",
    ]


def test_sampler_stops_and_joins_cleanly() -> None:
    started = Event()
    release = Event()

    def scan(**_kwargs: object) -> None:
        started.set()
        assert release.wait(timeout=1)

    sampler = EtfThreeFactorSampler(
        scan=scan,
        clock=Clock("2026-07-22T10:00:00"),
        retry_seconds=0.01,
        idle_seconds=60,
    )
    sampler.start()
    assert started.wait(timeout=1)
    release.set()

    sampler.stop_and_wait()

    assert not sampler.running


def test_sampler_thread_logs_scan_errors_and_retries() -> None:
    completed = Event()
    calls = 0

    def scan(**_kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary failure")
        completed.set()

    sampler = EtfThreeFactorSampler(
        scan=scan,
        clock=Clock("2026-07-22T10:00:00"),
        retry_seconds=0.01,
        idle_seconds=60,
    )
    sampler.start()
    assert completed.wait(timeout=1)
    sampler.stop_and_wait()

    assert calls == 2
