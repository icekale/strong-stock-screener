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
from app.services.chanlun.research_protocol import CzscRc8Request, build_research_request


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


def test_interactive_request_runs_before_next_background_item() -> None:
    completed: list[str] = []
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    ) as client:
        first = client.submit(_request("delay-background-1"), priority=10)
        _wait_for(lambda: client.health()["active_request_id"] == "delay-background-1")
        second = client.submit(_request("background-2"), priority=10)
        interactive = client.submit(_request("interactive"), priority=0)
        second.add_done_callback(lambda future: completed.append(future.result().request_id))
        interactive.add_done_callback(lambda future: completed.append(future.result().request_id))

        assert first.result(timeout=3).request_id == "delay-background-1"
        assert interactive.result(timeout=3).request_id == "interactive"
        assert second.result(timeout=3).request_id == "background-2"
        assert completed == ["interactive", "background-2"]


def test_same_priority_requests_are_fifo() -> None:
    completed: list[str] = []
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    ) as client:
        active = client.submit(_request("delay-active"), priority=10)
        _wait_for(lambda: client.health()["active_request_id"] == "delay-active")
        request_ids = ["fifo-1", "fifo-2", "fifo-3"]
        futures = [client.submit(_request(request_id), priority=10) for request_id in request_ids]
        for future in futures:
            future.add_done_callback(
                lambda completed_future: completed.append(completed_future.result().request_id)
            )

        active.result(timeout=3)
        for future in futures:
            future.result(timeout=3)

        assert completed == request_ids


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
        assert client._thread.daemon is True

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


def test_health_reports_activity_queue_version_and_sanitized_error(tmp_path: Path) -> None:
    attempts = tmp_path / "private-worker-path.attempts"
    with Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    ) as client:
        active = client.submit(_request("delay-health-active"), priority=10)
        _wait_for(lambda: client.health()["active_request_id"] == "delay-health-active")
        queued = client.submit(_request("health-queued"), priority=10)

        health = client.health()
        assert health == {
            "active_request_id": "delay-health-active",
            "queue_depth": 1,
            "circuit_state": "closed",
            "consecutive_failures": 0,
            "engine_version": None,
            "last_error": None,
            "closed": False,
        }

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


def test_close_is_idempotent_fails_queued_work_and_rejects_submit() -> None:
    client = Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
    )
    active = client.submit(_request("delay-close-active"), priority=10)
    _wait_for(lambda: client.health()["active_request_id"] == "delay-close-active")
    _wait_for(lambda: client._process is not None)
    process = client._process
    assert process is not None
    queued = client.submit(_request("close-queued"), priority=10)

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
