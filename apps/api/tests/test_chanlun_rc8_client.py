from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from typing import Callable

import pytest

from app.models import KlineBar
from app.services.chanlun.rc8_client import (
    Rc8CircuitOpen,
    Rc8WorkerClient,
    Rc8WorkerUnavailable,
)
from app.services.chanlun.research_protocol import (
    CzscRc8Request,
    CzscRc8Response,
    build_research_request,
)


def _fake_worker_path() -> Path:
    return Path(__file__).parent / "fixtures" / "fake_rc8_worker.py"


def _bar(date: str) -> KlineBar:
    return KlineBar(
        date=date,
        open=10.0,
        close=10.1,
        high=10.2,
        low=9.9,
        volume=1_000,
        amount=10_000,
    )


def _request(request_id: str) -> CzscRc8Request:
    return build_research_request(
        "600000.SH",
        {
            "1d": [_bar("2026-07-10")],
            "60m": [_bar("2026-07-10T14:00:00+08:00")],
            "30m": [_bar("2026-07-10T14:30:00+08:00")],
            "5m": [_bar("2026-07-10T14:55:00+08:00")],
        },
        request_id=request_id,
        adjustment_mode="qfq",
        decision_at="2026-07-10T15:00:00+08:00",
    )


def _wait_for(predicate: Callable[[], bool], *, timeout: float = 2) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("condition was not met before timeout")


def _attempt_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _attempt_pids(path: Path) -> set[int]:
    return {int(value) for value in path.read_text(encoding="utf-8").splitlines()}


def _gate(tmp_path: Path, name: str) -> tuple[str, Path, Path]:
    gate = tmp_path / name
    return f"gate:{gate}", Path(f"{gate}.ready"), Path(f"{gate}.release")


def test_interactive_request_runs_before_next_background_item(tmp_path: Path) -> None:
    completed: list[str] = []
    callbacks_done = threading.Event()
    request_id, ready, release = _gate(tmp_path, "background-1")

    def record_completion(future: Future[CzscRc8Response]) -> None:
        completed.append(future.result().request_id)
        if len(completed) == 2:
            callbacks_done.set()

    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    ) as client:
        first = client.submit(_request(request_id), priority=10)
        _wait_for(ready.exists)
        second = client.submit(_request("background-2"), priority=10)
        interactive = client.submit(_request("interactive"), priority=0)
        second.add_done_callback(record_completion)
        interactive.add_done_callback(record_completion)
        assert client.health()["active_request_id"] == request_id
        assert client.health()["queue_depth"] == 2
        release.touch()

        assert first.result(timeout=3).request_id == request_id
        assert interactive.result(timeout=3).request_id == "interactive"
        assert second.result(timeout=3).request_id == "background-2"
        assert callbacks_done.wait(timeout=1)
        assert completed == ["interactive", "background-2"]


def test_same_priority_requests_are_fifo(tmp_path: Path) -> None:
    completed: list[str] = []
    callbacks_done = threading.Event()
    active_request_id, ready, release = _gate(tmp_path, "fifo-active")

    def record_completion(future: Future[CzscRc8Response]) -> None:
        completed.append(future.result().request_id)
        if len(completed) == 3:
            callbacks_done.set()

    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    ) as client:
        active = client.submit(_request(active_request_id), priority=10)
        _wait_for(ready.exists)
        request_ids = ["fifo-1", "fifo-2", "fifo-3"]
        futures = [client.submit(_request(request_id), priority=10) for request_id in request_ids]
        for future in futures:
            future.add_done_callback(record_completion)
        assert client.health()["active_request_id"] == active_request_id
        assert client.health()["queue_depth"] == 3
        release.touch()

        active.result(timeout=3)
        for future in futures:
            future.result(timeout=3)

        assert callbacks_done.wait(timeout=1)
        assert completed == request_ids


def test_cancel_racing_claim_cannot_kill_dispatcher(tmp_path: Path) -> None:
    request_id, ready, release = _gate(tmp_path, "cancel-race")
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    ) as client:
        active = client.submit(_request(request_id), priority=0)
        _wait_for(ready.exists)

        cancellation_succeeded = active.cancel()
        release.touch()
        if not cancellation_succeeded:
            assert active.result(timeout=3).request_id == request_id
        later = client.submit(_request("after-cancel-race"), priority=0)

        assert later.result(timeout=3).request_id == "after-cancel-race"
        assert cancellation_succeeded is False


@pytest.mark.parametrize(
    "mode",
    [
        "malformed-json",
        "malformed-schema",
        "mismatch-request",
        "mismatch-snapshot",
        "exit",
    ],
)
def test_invalid_response_retries_once_then_reports_unavailable(
    tmp_path: Path,
    mode: str,
) -> None:
    attempts = tmp_path / f"{mode}.attempts"
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
        hard_timeout_seconds=0.5,
    ) as client:
        future = client.submit(_request(f"{mode}:{attempts}"), priority=0)

        with pytest.raises(Rc8WorkerUnavailable):
            future.result(timeout=3)

        assert _attempt_count(attempts) == 2
        assert len(_attempt_pids(attempts)) == 2
        assert client.health()["consecutive_failures"] == 1


def test_failed_first_attempt_restarts_process_and_returns_retry_response(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "fail-once.marker"
    request_id = f"fail-once:{marker}"
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    ) as client:
        response = client.submit(_request(request_id), priority=0).result(timeout=3)

        assert response.request_id == request_id
        assert marker.read_text(encoding="utf-8") == "failed\n"
        assert client.health()["consecutive_failures"] == 0


def test_hard_timeout_applies_after_partial_response_bytes(tmp_path: Path) -> None:
    attempts = tmp_path / "partial.attempts"
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
        hard_timeout_seconds=0.2,
    ) as client:
        future = client.submit(_request(f"partial-line:{attempts}"), priority=0)

        with pytest.raises(Rc8WorkerUnavailable):
            future.result(timeout=1)

        assert _attempt_count(attempts) == 2
        assert len(_attempt_pids(attempts)) == 2


def test_large_stderr_is_drained_and_exposed_as_bounded_sanitized_tail(
    tmp_path: Path,
) -> None:
    attempts = tmp_path / "stderr-pressure.attempts"
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
        hard_timeout_seconds=1,
    ) as client:
        response = client.submit(
            _request(f"stderr-large:{attempts}"),
            priority=0,
        ).result(timeout=4)

        assert response.status == "ready"
        assert _attempt_count(attempts) == 1
        stderr_tail = client.health()["stderr_tail"]
        assert isinstance(stderr_tail, str)
        assert len(stderr_tail) <= 1_024
        assert "\n" not in stderr_tail
        assert "\r" not in stderr_tail
        assert "Traceback" not in stderr_tail
        assert str(tmp_path) not in stderr_tail
        assert "/private/worker/secret.py" not in stderr_tail


def test_whole_exchange_timeout_bounds_blocked_stdin_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = tmp_path / "stop-reading"
    attempts = Path(f"{gate}.attempts")
    monkeypatch.setenv("FAKE_RC8_STARTUP_MODE", f"stop-reading:{gate}")
    request = _request("blocked-large-write").model_copy(update={"symbol": "6" * 2_000_000})
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
        hard_timeout_seconds=0.2,
    ) as client:
        future = client.submit(request, priority=0)

        with pytest.raises(Rc8WorkerUnavailable):
            future.result(timeout=3)

        assert _attempt_count(attempts) == 2
        assert len(_attempt_pids(attempts)) == 2
        assert client.health()["consecutive_failures"] == 1
        assert client._process is None


def test_timeout_restarts_worker_and_opens_circuit_after_three_final_failures(
    tmp_path: Path,
) -> None:
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
        hard_timeout_seconds=0.2,
        circuit_failures=3,
        circuit_seconds=60,
    ) as client:
        for index in range(3):
            attempts = tmp_path / f"slow-{index}.attempts"
            future = client.submit(_request(f"slow-{index}:{attempts}"), priority=0)

            with pytest.raises(Rc8WorkerUnavailable):
                future.result(timeout=3)

            assert _attempt_count(attempts) == 2
            assert len(_attempt_pids(attempts)) == 2
            assert client.health()["consecutive_failures"] == index + 1

        assert client.health()["circuit_state"] == "open"
        with pytest.raises(Rc8CircuitOpen):
            client.submit(_request("blocked"), priority=0)


def test_open_circuit_rejects_requests_queued_before_final_failure(tmp_path: Path) -> None:
    failure_attempts = tmp_path / "gated-failure.attempts"
    ready = Path(f"{failure_attempts}.ready")
    release = Path(f"{failure_attempts}.release")
    queued_attempts = [tmp_path / f"queued-{index}.attempts" for index in range(2)]
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
        circuit_failures=1,
        circuit_seconds=60,
    ) as client:
        failing = client.submit(
            _request(f"gate-malformed:{failure_attempts}"),
            priority=0,
        )
        _wait_for(ready.exists)
        queued = [
            client.submit(_request(f"record-pid-{index}:{path}"), priority=10)
            for index, path in enumerate(queued_attempts)
        ]
        release.touch()

        with pytest.raises(Rc8WorkerUnavailable):
            failing.result(timeout=3)
        for future in queued:
            with pytest.raises(Rc8CircuitOpen):
                future.result(timeout=3)

        assert all(not path.exists() for path in queued_attempts)
        assert client.health()["consecutive_failures"] == 1
        assert client.health()["circuit_state"] == "open"


def test_half_open_allows_only_one_reserved_probe(tmp_path: Path) -> None:
    attempts = tmp_path / "half-open-failure.attempts"
    probe_id, ready, release = _gate(tmp_path, "half-open-probe")
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
        circuit_failures=1,
        circuit_seconds=0.05,
    ) as client:
        failed = client.submit(_request(f"malformed-json:{attempts}"), priority=0)
        with pytest.raises(Rc8WorkerUnavailable):
            failed.result(timeout=3)
        _wait_for(lambda: client.health()["circuit_state"] == "half_open")

        probe = client.submit(_request(probe_id), priority=0)
        _wait_for(ready.exists)
        with pytest.raises(Rc8CircuitOpen):
            client.submit(_request("second-half-open-probe"), priority=0)
        release.touch()

        assert probe.result(timeout=3).request_id == probe_id
        assert client.health()["circuit_state"] == "closed"


def test_cancelled_queued_half_open_probe_releases_reservation(tmp_path: Path) -> None:
    failure_attempts = tmp_path / "cancel-probe-failure.attempts"
    ready = Path(f"{failure_attempts}.ready")
    release = Path(f"{failure_attempts}.release")
    block_next_get = threading.Event()
    get_blocked = threading.Event()
    allow_get = threading.Event()
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
        circuit_failures=1,
        circuit_seconds=0.05,
    ) as client:
        original_get = client._queue.get

        def controlled_get(*args, **kwargs):
            if block_next_get.is_set():
                block_next_get.clear()
                get_blocked.set()
                allow_get.wait(timeout=2)
            return original_get(*args, **kwargs)

        client._queue.get = controlled_get
        failing = client.submit(
            _request(f"gate-malformed:{failure_attempts}"),
            priority=0,
        )
        _wait_for(ready.exists)
        block_next_get.set()
        release.touch()

        with pytest.raises(Rc8WorkerUnavailable):
            failing.result(timeout=3)
        assert get_blocked.wait(timeout=1)
        _wait_for(lambda: client.health()["circuit_state"] == "half_open")
        probe = client.submit(_request("cancelled-half-open-probe"), priority=0)
        assert probe.cancel() is True
        allow_get.set()

        deadline = time.monotonic() + 2
        replacement = None
        while replacement is None and time.monotonic() < deadline:
            try:
                replacement = client.submit(_request("replacement-half-open-probe"), priority=0)
            except Rc8CircuitOpen:
                time.sleep(0.005)

        assert replacement is not None
        assert replacement.result(timeout=3).request_id == "replacement-half-open-probe"


def test_close_clears_active_half_open_reservation(tmp_path: Path) -> None:
    attempts = tmp_path / "close-probe-failure.attempts"
    probe_id, ready, _release = _gate(tmp_path, "close-half-open-probe")
    client = Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
        circuit_failures=1,
        circuit_seconds=0.05,
    )
    failed = client.submit(_request(f"malformed-json:{attempts}"), priority=0)
    with pytest.raises(Rc8WorkerUnavailable):
        failed.result(timeout=3)
    _wait_for(lambda: client.health()["circuit_state"] == "half_open")
    probe = client.submit(_request(probe_id), priority=0)
    _wait_for(ready.exists)

    client.close()

    with pytest.raises(Rc8WorkerUnavailable, match="closed"):
        probe.result(timeout=1)
    assert client._half_open_in_flight is False


def test_success_resets_consecutive_final_failures(tmp_path: Path) -> None:
    attempts = tmp_path / "malformed.attempts"
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
        circuit_failures=3,
    ) as client:
        failed = client.submit(_request(f"malformed-json:{attempts}"), priority=0)
        with pytest.raises(Rc8WorkerUnavailable):
            failed.result(timeout=3)
        assert client.health()["consecutive_failures"] == 1

        response = client.submit(_request("recovered"), priority=0).result(timeout=3)

        assert response.request_id == "recovered"
        assert client.health()["consecutive_failures"] == 0


def test_circuit_expiry_allows_half_open_success(tmp_path: Path) -> None:
    attempts = tmp_path / "open-circuit.attempts"
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
        circuit_failures=1,
        circuit_seconds=0.1,
    ) as client:
        failed = client.submit(_request(f"malformed-json:{attempts}"), priority=0)
        with pytest.raises(Rc8WorkerUnavailable):
            failed.result(timeout=3)
        with pytest.raises(Rc8CircuitOpen):
            client.submit(_request("still-open"), priority=0)

        _wait_for(lambda: client.health()["circuit_state"] == "half_open")
        response = client.submit(_request("half-open-probe"), priority=0).result(timeout=3)

        assert response.request_id == "half-open-probe"
        assert client.health()["circuit_state"] == "closed"
        assert client.health()["consecutive_failures"] == 0


def test_worker_starts_lazily_and_receives_one_compact_json_line(tmp_path: Path) -> None:
    captured = tmp_path / "request.jsonl"
    request = _request(f"capture-line:{captured}")
    expected = (
        json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    )
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    ) as client:
        assert client._process is None

        response = client.submit(request, priority=0).result(timeout=3)

        assert response.request_id == request.request_id
        assert captured.read_text(encoding="utf-8") == expected


def test_successive_requests_reuse_one_persistent_process(tmp_path: Path) -> None:
    attempts = tmp_path / "persistent-process.attempts"
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    ) as client:
        first = client.submit(_request(f"record-pid-1:{attempts}"), priority=0)
        second = client.submit(_request(f"record-pid-2:{attempts}"), priority=0)

        assert first.result(timeout=3).status == "ready"
        assert second.result(timeout=3).status == "ready"
        assert _attempt_count(attempts) == 2
        assert len(_attempt_pids(attempts)) == 1


def test_process_that_exits_between_requests_is_reaped_before_replacement() -> None:
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    ) as client:
        first = client.submit(_request("valid-then-exit"), priority=0).result(timeout=3)
        exited_process = client._process
        assert exited_process is not None
        _wait_for(lambda: exited_process.poll() is not None)

        second = client.submit(_request("after-idle-exit"), priority=0).result(timeout=3)

        assert first.request_id == "valid-then-exit"
        assert second.request_id == "after-idle-exit"
        assert all(
            stream is None or stream.closed
            for stream in (exited_process.stdin, exited_process.stdout, exited_process.stderr)
        )


def test_delayed_split_stdout_is_rejected_before_next_request(tmp_path: Path) -> None:
    first_attempts = tmp_path / "delayed-extra.attempts"
    ready = Path(f"{first_attempts}.ready")
    next_attempts = Path(f"{first_attempts}.next.attempts")
    next_request_id = f"record-pid-next:{next_attempts}"
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    ) as client:
        first = client.submit(
            _request(f"delayed-extra:{first_attempts}"),
            priority=0,
        ).result(timeout=3)
        first_process = client._process
        assert first_process is not None
        _wait_for(ready.exists)

        second = client.submit(_request(next_request_id), priority=0).result(timeout=3)

        assert first.status == "ready"
        assert second.request_id == next_request_id
        assert client._process is not first_process
        assert _attempt_count(first_attempts) == 1
        assert _attempt_count(next_attempts) == 1
        assert _attempt_pids(first_attempts).isdisjoint(_attempt_pids(next_attempts))


def test_health_reports_activity_queue_version_and_sanitized_error(tmp_path: Path) -> None:
    attempts = tmp_path / "private-worker-path.attempts"
    active_request_id, ready, release = _gate(tmp_path, "health-active")
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    ) as client:
        active = client.submit(_request(active_request_id), priority=10)
        _wait_for(ready.exists)
        queued = client.submit(_request("health-queued"), priority=10)

        health = client.health()
        assert health == {
            "active_request_id": active_request_id,
            "queue_depth": 1,
            "circuit_state": "closed",
            "consecutive_failures": 0,
            "engine_version": None,
            "last_error": None,
            "stderr_tail": None,
            "closed": False,
        }
        release.touch()

        active.result(timeout=3)
        queued.result(timeout=3)
        failed = client.submit(_request(f"malformed-json:{attempts}"), priority=0)
        with pytest.raises(Rc8WorkerUnavailable):
            failed.result(timeout=3)

        health = client.health()
        assert health["active_request_id"] is None
        assert health["queue_depth"] == 0
        assert health["consecutive_failures"] == 1
        assert health["engine_version"] == "1.0.0rc8"
        assert isinstance(health["last_error"], str)
        assert "\n" not in health["last_error"]
        assert "\r" not in health["last_error"]
        assert "Traceback" not in health["last_error"]
        assert str(tmp_path) not in health["last_error"]


def test_close_is_idempotent_fails_queued_work_and_rejects_submit(tmp_path: Path) -> None:
    active_request_id, ready, _release = _gate(tmp_path, "close-active")
    client = Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    )
    active = client.submit(_request(active_request_id), priority=10)
    _wait_for(ready.exists)
    process = client._process
    assert process is not None
    queued = client.submit(_request("close-queued"), priority=10)
    assert client.health()["active_request_id"] == active_request_id
    assert client.health()["queue_depth"] == 1

    client.close()
    client.close()

    with pytest.raises(Rc8WorkerUnavailable, match="closed"):
        active.result(timeout=1)
    with pytest.raises(Rc8WorkerUnavailable, match="closed"):
        queued.result(timeout=1)
    with pytest.raises(Rc8WorkerUnavailable, match="closed"):
        client.submit(_request("after-close"), priority=0)
    assert client.health()["closed"] is True
    assert client.health()["queue_depth"] == 0
    assert not client._thread.is_alive()
    assert client._process is None
    assert process.returncode is not None
    assert all(
        stream is None or stream.closed
        for stream in (process.stdin, process.stdout, process.stderr)
    )


def test_concurrent_close_is_a_barrier_and_does_not_wait_for_user_callback(
    tmp_path: Path,
) -> None:
    request_id, ready, release = _gate(tmp_path, "blocking-callback")
    callback_started = threading.Event()
    release_callback = threading.Event()
    close_barrier = threading.Barrier(3)
    all_close_calls_done = threading.Event()
    close_states: list[tuple[bool, object]] = []
    close_states_lock = threading.Lock()
    client = Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    )

    def blocking_callback(_future: Future[CzscRc8Response]) -> None:
        callback_started.set()
        release_callback.wait(timeout=5)

    def close_and_record_state() -> None:
        close_barrier.wait(timeout=2)
        client.close()
        with close_states_lock:
            close_states.append((client._thread.is_alive(), client._process))
            if len(close_states) == 2:
                all_close_calls_done.set()

    active = client.submit(_request(request_id), priority=0)
    active.add_done_callback(blocking_callback)
    _wait_for(ready.exists)
    release.touch()
    assert active.result(timeout=3).request_id == request_id
    assert callback_started.wait(timeout=1)
    close_threads = [threading.Thread(target=close_and_record_state) for _ in range(2)]
    for thread in close_threads:
        thread.start()
    close_barrier.wait(timeout=2)

    try:
        assert all_close_calls_done.wait(timeout=1)
    finally:
        release_callback.set()
        for thread in close_threads:
            thread.join(timeout=3)
        client.close()

    assert close_states == [(False, None), (False, None)]


def test_concurrent_submit_cannot_enqueue_after_close_drains_queue() -> None:
    client = Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    )
    put_started = threading.Event()
    both_drains_finished = threading.Event()
    drain_count = 0
    drain_lock = threading.Lock()
    original_put = client._queue.put
    original_fail_queued = client._fail_queued_requests

    def delayed_put(item: object) -> None:
        put_started.set()
        both_drains_finished.wait(timeout=0.2)
        original_put(item)

    def observed_fail_queued() -> None:
        nonlocal drain_count
        original_fail_queued()
        with drain_lock:
            drain_count += 1
            if drain_count == 2:
                both_drains_finished.set()

    client._queue.put = delayed_put
    client._fail_queued_requests = observed_fail_queued
    submitted: list[Future[object]] = []

    submit_thread = threading.Thread(
        target=lambda: submitted.append(client.submit(_request("submit-close-race"), priority=0))
    )
    submit_thread.start()
    assert put_started.wait(timeout=1)
    close_thread = threading.Thread(target=client.close)
    close_thread.start()

    submit_thread.join(timeout=2)
    close_thread.join(timeout=2)

    assert not submit_thread.is_alive()
    assert not close_thread.is_alive()
    assert len(submitted) == 1
    with pytest.raises(Rc8WorkerUnavailable, match="closed"):
        submitted[0].result(timeout=1)
