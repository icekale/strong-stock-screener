from __future__ import annotations

from threading import Event, Lock, Thread
from time import sleep

from app.services.short_term_cache import TtlCache


def test_get_or_refresh_returns_stale_value_while_refreshing_in_background() -> None:
    cache = TtlCache[str](ttl_seconds=0.05)
    refresh_started = Event()
    release_refresh = Event()
    values = iter(["fresh-1", "fresh-2"])

    assert cache.get_or_refresh("key", lambda: next(values)) == "fresh-1"
    sleep(0.06)

    def slow_factory() -> str:
        refresh_started.set()
        release_refresh.wait(timeout=1)
        return next(values)

    assert cache.get_or_refresh("key", slow_factory) == "fresh-1"
    assert refresh_started.wait(timeout=1)

    release_refresh.set()
    refreshed_value: str | None = None
    for _ in range(100):
        refreshed_value = cache.get_if_fresh("key")
        if refreshed_value == "fresh-2":
            break
        sleep(0.001)

    assert refreshed_value == "fresh-2"


def test_get_or_set_does_not_hold_lock_while_factory_runs() -> None:
    cache = TtlCache[str](ttl_seconds=60, name="test-cache")
    factory_started = Event()
    release_factory = Event()
    fast_finished = Event()
    thread_errors: list[BaseException] = []

    def slow_factory() -> str:
        factory_started.set()
        release_factory.wait()
        return "slow"

    def run_slow_call() -> None:
        try:
            assert cache.get_or_set("slow", slow_factory) == "slow"
        except BaseException as exc:
            thread_errors.append(exc)

    def fast_factory() -> str:
        return "fast"

    def run_fast_call() -> None:
        try:
            assert cache.get_or_set("fast", fast_factory) == "fast"
            fast_finished.set()
        except BaseException as exc:
            thread_errors.append(exc)

    slow_thread = Thread(target=run_slow_call)
    slow_thread.start()
    assert factory_started.wait(timeout=1)

    fast_thread = Thread(target=run_fast_call)
    fast_thread.start()
    try:
        assert fast_finished.wait(timeout=0.2)
    finally:
        release_factory.set()
        slow_thread.join(timeout=1)
        fast_thread.join(timeout=1)

    assert not thread_errors


def test_cache_snapshot_records_hits_misses_and_refresh_error() -> None:
    cache = TtlCache[str](ttl_seconds=0.01, name="quotes")

    assert cache.get_or_set("key", lambda: "v1") == "v1"
    assert cache.get_or_set("key", lambda: "unused") == "v1"
    sleep(0.02)

    def failing_factory() -> str:
        raise RuntimeError("provider down")

    assert cache.get_or_refresh("key", failing_factory) == "v1"
    for _ in range(100):
        snapshot = cache.snapshot()
        if snapshot["refresh_error_count"] == 1:
            break
        sleep(0.01)

    snapshot = cache.snapshot()
    assert snapshot["name"] == "quotes"
    assert snapshot["hits"] >= 1
    assert snapshot["misses"] >= 1
    assert snapshot["stale_hits"] >= 1
    assert snapshot["refresh_error_count"] == 1
    assert snapshot["last_error"] == "provider down"


def test_get_or_refresh_returns_stale_none_while_refreshing() -> None:
    cache = TtlCache[str | None](ttl_seconds=0.01, name="nullable")
    refresh_started = Event()
    release_refresh = Event()

    assert cache.get_or_refresh("key", lambda: None) is None
    sleep(0.02)

    def slow_factory() -> str:
        refresh_started.set()
        release_refresh.wait()
        return "refreshed"

    assert cache.get_or_refresh("key", slow_factory) is None
    assert refresh_started.wait(timeout=1)

    def unexpected_factory() -> str:
        raise AssertionError("factory should not run while stale None is refreshing")

    try:
        assert cache.get_or_refresh("key", unexpected_factory) is None
    finally:
        release_refresh.set()


def test_same_key_get_or_set_cold_miss_only_runs_factory_once() -> None:
    cache = TtlCache[str](ttl_seconds=60, name="test-cache")
    factory_started = Event()
    factory_called_twice = Event()
    release_factory = Event()
    calls: list[int] = []
    results: list[str] = []
    thread_errors: list[BaseException] = []
    lock = Lock()

    def factory() -> str:
        with lock:
            call_number = len(calls) + 1
            calls.append(call_number)
            if call_number > 1:
                factory_called_twice.set()
        factory_started.set()
        release_factory.wait()
        return f"value-{call_number}"

    def run_call() -> None:
        try:
            result = cache.get_or_set("same-key", factory)
            with lock:
                results.append(result)
        except BaseException as exc:
            thread_errors.append(exc)

    first_thread = Thread(target=run_call)
    second_thread = Thread(target=run_call)
    first_thread.start()
    assert factory_started.wait(timeout=1)
    second_thread.start()

    try:
        assert not factory_called_twice.wait(timeout=0.2)
    finally:
        release_factory.set()
        first_thread.join(timeout=1)
        second_thread.join(timeout=1)

    assert not thread_errors
    assert calls == [1]
    assert sorted(results) == ["value-1", "value-1"]


def test_clear_during_background_refresh_keeps_cache_empty() -> None:
    cache = TtlCache[str](ttl_seconds=0.01, name="test-cache")
    refresh_started = Event()
    release_refresh = Event()

    assert cache.get_or_refresh("key", lambda: "initial") == "initial"
    sleep(0.02)
    previous_finished = cache.snapshot()["last_refresh_finished_at"]

    def slow_factory() -> str:
        refresh_started.set()
        release_refresh.wait()
        return "refreshed"

    assert cache.get_or_refresh("key", slow_factory) == "initial"
    assert refresh_started.wait(timeout=1)

    cache.clear()
    release_refresh.set()

    for _ in range(100):
        snapshot = cache.snapshot()
        if snapshot["last_refresh_finished_at"] != previous_finished:
            break
        sleep(0.01)

    snapshot = cache.snapshot()
    assert snapshot["last_refresh_finished_at"] != previous_finished
    assert snapshot["size"] == 0
    assert cache.get_if_fresh("key") is None
