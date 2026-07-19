from __future__ import annotations

from datetime import datetime
from threading import Barrier, Event, Lock, Thread
from time import monotonic
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.services.capital_signal_sampler import (
    CapitalSignalSampler,
    is_capital_signal_refresh_window,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")


def _snapshot(
    trade_date: str,
    *,
    core_shares: list[float | None] | None = None,
    validator_shares: list[float | None] | None = None,
) -> SimpleNamespace:
    core_values = core_shares if core_shares is not None else [1.0] * 7
    validator_values = validator_shares if validator_shares is not None else [1.0] * 3
    return SimpleNamespace(
        trade_date=trade_date,
        core_items=[SimpleNamespace(total_shares=value) for value in core_values],
        validation_items=[SimpleNamespace(total_shares=value) for value in validator_values],
    )


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 7, 3, 19, 4, 59, tzinfo=SHANGHAI), False),
        (datetime(2026, 7, 3, 19, 5, tzinfo=SHANGHAI), True),
        (datetime(2026, 7, 3, 23, 30, 59, tzinfo=SHANGHAI), True),
        (datetime(2026, 7, 3, 23, 31, tzinfo=SHANGHAI), False),
        (datetime(2026, 7, 4, 20, 0, tzinfo=SHANGHAI), False),
        (datetime(2026, 7, 5, 20, 0, tzinfo=SHANGHAI), False),
    ],
)
def test_capital_signal_refresh_window_boundaries(now: datetime, expected: bool) -> None:
    assert is_capital_signal_refresh_window(now) is expected


def test_partial_placeholder_snapshot_retries_until_complete() -> None:
    calls = 0
    responses = [
        _snapshot("2026-07-03", core_shares=[1.0] * 6 + [None]),
        _snapshot("2026-07-03"),
    ]

    def refresh() -> SimpleNamespace:
        nonlocal calls
        response = responses[calls]
        calls += 1
        return response

    sampler = CapitalSignalSampler(
        refresh=refresh,
        clock=lambda: datetime(2026, 7, 3, 20, 0, tzinfo=SHANGHAI),
    )

    assert sampler.sample_once() is False
    assert sampler.sample_once() is True
    assert sampler.sample_once() is False
    assert calls == 2


def test_wrong_trade_date_remains_retryable() -> None:
    calls = 0

    def refresh() -> SimpleNamespace:
        nonlocal calls
        calls += 1
        return _snapshot("2026-07-02")

    sampler = CapitalSignalSampler(
        refresh=refresh,
        clock=lambda: datetime(2026, 7, 3, 20, 0, tzinfo=SHANGHAI),
    )

    assert sampler.sample_once() is False
    assert sampler.sample_once() is False
    assert calls == 2


def test_refresh_exception_remains_retryable() -> None:
    calls = 0

    def refresh() -> SimpleNamespace:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary source failure")
        return _snapshot("2026-07-03")

    sampler = CapitalSignalSampler(
        refresh=refresh,
        clock=lambda: datetime(2026, 7, 3, 20, 0, tzinfo=SHANGHAI),
    )

    with pytest.raises(RuntimeError, match="temporary source failure"):
        sampler.sample_once()
    assert sampler.sample_once() is True
    assert calls == 2


def test_new_day_can_sample_again() -> None:
    current = datetime(2026, 7, 3, 20, 0, tzinfo=SHANGHAI)
    calls: list[str] = []

    def refresh() -> SimpleNamespace:
        trade_date = current.date().isoformat()
        calls.append(trade_date)
        return _snapshot(trade_date)

    sampler = CapitalSignalSampler(refresh=refresh, clock=lambda: current)

    assert sampler.sample_once() is True
    assert sampler.sample_once() is False

    current = datetime(2026, 7, 6, 20, 0, tzinfo=SHANGHAI)
    assert sampler.sample_once() is True
    assert calls == ["2026-07-03", "2026-07-06"]


def test_concurrent_sample_once_serializes_refresh_and_completion() -> None:
    callers_ready = Barrier(3)
    refresh_entered = Event()
    release_refresh = Event()
    calls = 0
    results: list[bool] = []

    def refresh() -> SimpleNamespace:
        nonlocal calls
        calls += 1
        refresh_entered.set()
        assert release_refresh.wait(timeout=1)
        return _snapshot("2026-07-03")

    sampler = CapitalSignalSampler(
        refresh=refresh,
        clock=lambda: datetime(2026, 7, 3, 20, 0, tzinfo=SHANGHAI),
    )

    def sample() -> None:
        callers_ready.wait()
        results.append(sampler.sample_once())

    threads = [Thread(target=sample), Thread(target=sample)]
    for thread in threads:
        thread.start()
    callers_ready.wait()
    try:
        assert refresh_entered.wait(timeout=1)
    finally:
        release_refresh.set()
        for thread in threads:
            thread.join(timeout=1)

    assert all(not thread.is_alive() for thread in threads)
    assert calls == 1
    assert sorted(results) == [False, True]


def test_thread_retries_after_refresh_exception(caplog) -> None:
    completed = Event()
    calls = 0

    def refresh() -> SimpleNamespace:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary source failure")
        completed.set()
        return _snapshot("2026-07-03")

    sampler = CapitalSignalSampler(
        refresh=refresh,
        clock=lambda: datetime(2026, 7, 3, 20, 0, tzinfo=SHANGHAI),
        retry_seconds=0.001,
        idle_seconds=60,
    )

    caplog.set_level("ERROR", logger="app.services.capital_signal_sampler")
    sampler.start()
    try:
        assert completed.wait(timeout=1)
        assert calls == 2
    finally:
        sampler.stop()

    assert sampler.running is False
    assert any("capital signal refresh failed" in record.message for record in caplog.records)


def test_start_is_idempotent_and_stop_interrupts_wait() -> None:
    refreshed = Event()
    calls = 0

    def refresh() -> SimpleNamespace:
        nonlocal calls
        calls += 1
        refreshed.set()
        return _snapshot("2026-07-03")

    sampler = CapitalSignalSampler(
        refresh=refresh,
        clock=lambda: datetime(2026, 7, 3, 20, 0, tzinfo=SHANGHAI),
        idle_seconds=60,
    )

    sampler.start()
    try:
        assert refreshed.wait(timeout=1)
        sampler.start()
        assert calls == 1
        assert sampler.running is True
    finally:
        assert sampler.stop() is True
        assert sampler.stop() is True

    assert sampler.running is False


def test_bounded_stop_reports_blocked_worker_then_stop_and_wait_finishes() -> None:
    refresh_entered = Event()
    release_refresh = Event()

    def refresh() -> SimpleNamespace:
        refresh_entered.set()
        release_refresh.wait()
        return _snapshot("2026-07-03")

    sampler = CapitalSignalSampler(
        refresh=refresh,
        clock=lambda: datetime(2026, 7, 3, 20, 0, tzinfo=SHANGHAI),
    )

    sampler.start()
    assert refresh_entered.wait(timeout=1)
    try:
        started_at = monotonic()
        assert sampler.stop(timeout_seconds=0.01) is False
        assert monotonic() - started_at < 0.5
        assert sampler.running is True
    finally:
        release_refresh.set()
        stop_and_wait = getattr(sampler, "stop_and_wait", sampler.stop)
        stop_and_wait()

    assert sampler.running is False


def test_restart_waits_for_timed_out_worker_before_starting_new_generation() -> None:
    refresh_entered = Event()
    release_refresh = Event()
    active_lock = Lock()
    active_refreshes = 0
    max_active_refreshes = 0

    def refresh() -> SimpleNamespace:
        nonlocal active_refreshes, max_active_refreshes
        with active_lock:
            active_refreshes += 1
            max_active_refreshes = max(max_active_refreshes, active_refreshes)
        try:
            refresh_entered.set()
            release_refresh.wait()
            return _snapshot("2026-07-03")
        finally:
            with active_lock:
                active_refreshes -= 1

    sampler = CapitalSignalSampler(
        refresh=refresh,
        clock=lambda: datetime(2026, 7, 3, 20, 0, tzinfo=SHANGHAI),
        idle_seconds=60,
    )

    sampler.start()
    assert refresh_entered.wait(timeout=1)
    restart = Thread(target=sampler.start)
    restart_started = False
    try:
        assert sampler.stop(timeout_seconds=0.01) is False
        restart.start()
        restart_started = True
        assert restart.is_alive()

        release_refresh.set()
        restart.join(timeout=1)

        assert restart.is_alive() is False
        assert sampler.running is True
        assert max_active_refreshes == 1
    finally:
        release_refresh.set()
        if restart_started:
            restart.join(timeout=1)
        stop_and_wait = getattr(sampler, "stop_and_wait", sampler.stop)
        stop_and_wait()

    assert sampler.running is False


def test_completed_date_keeps_using_idle_wait() -> None:
    class RecordingStopEvent:
        def __init__(self) -> None:
            self.waits: list[float] = []

        def is_set(self) -> bool:
            return len(self.waits) == 2

        def wait(self, seconds: float) -> None:
            self.waits.append(seconds)

    sampler = CapitalSignalSampler(
        refresh=lambda: _snapshot("2026-07-03"),
        clock=lambda: datetime(2026, 7, 3, 20, 0, tzinfo=SHANGHAI),
        retry_seconds=15,
        idle_seconds=30,
    )
    stop_event = RecordingStopEvent()
    sampler._stop_event = stop_event

    sampler._run()

    assert stop_event.waits == [30, 30]
