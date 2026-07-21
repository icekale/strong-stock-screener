from __future__ import annotations

from datetime import datetime, timedelta
from threading import Event

import app.services.etf_three_factor_sampler as sampler_module
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


def test_sampler_thread_reaches_close_refresh_after_1500(monkeypatch: object) -> None:
    current = Clock("2026-07-22T14:59:00")
    close_reached = Event()
    calls: list[dict[str, object]] = []

    class AdvancingStopEvent:
        def __init__(self) -> None:
            self._stopped = False

        def is_set(self) -> bool:
            return self._stopped

        def set(self) -> None:
            self._stopped = True

        def wait(self, seconds: float) -> bool:
            current.current += timedelta(seconds=seconds)
            if current.current >= datetime.fromisoformat("2026-07-22T15:06:00"):
                self.set()
            return self.is_set()

    monkeypatch.setattr(sampler_module, "Event", AdvancingStopEvent)

    def scan(**kwargs: object) -> None:
        calls.append(kwargs)
        if kwargs["now"].strftime("%H:%M") == "15:05":
            close_reached.set()

    sampler = EtfThreeFactorSampler(
        scan=scan,
        clock=current,
        retry_seconds=60,
        idle_seconds=300,
    )
    sampler.start()

    assert close_reached.wait(timeout=1)
    sampler.stop_and_wait()

    assert [call["now"].strftime("%H:%M") for call in calls] == [
        "14:59",
        "15:00",
        "15:05",
    ]
