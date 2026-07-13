from __future__ import annotations

import json
import os
import queue
import selectors
import subprocess
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic

from app.services.chanlun.research_protocol import CzscRc8Request, CzscRc8Response


class Rc8WorkerUnavailable(RuntimeError):
    """The rc8 worker cannot serve a request."""


class Rc8CircuitOpen(Rc8WorkerUnavailable):
    """The rc8 worker circuit is rejecting requests."""


class _WorkerAttemptError(RuntimeError):
    pass


@dataclass(order=True)
class _QueuedRequest:
    priority: int
    sequence: int
    payload: CzscRc8Request = field(compare=False)
    future: Future[CzscRc8Response] = field(compare=False)


class Rc8WorkerClient:
    def __init__(
        self,
        *,
        python_path: str | Path,
        worker_path: str | Path,
        hard_timeout_seconds: float = 10.0,
        circuit_failures: int = 3,
        circuit_seconds: float = 60.0,
    ) -> None:
        self._python_path = str(python_path)
        self._worker_path = str(worker_path)
        self._hard_timeout_seconds = hard_timeout_seconds
        self._circuit_failures = circuit_failures
        self._circuit_seconds = circuit_seconds

        self._queue: queue.PriorityQueue[_QueuedRequest] = queue.PriorityQueue()
        self._state_lock = threading.Lock()
        self._process_lock = threading.Lock()
        self._stop = threading.Event()
        self._process: subprocess.Popen[str] | None = None
        self._sequence = 0
        self._closed = False
        self._active_request_id: str | None = None
        self._consecutive_failures = 0
        self._circuit_opened_at: float | None = None
        self._half_open_in_flight = False
        self._engine_version: str | None = None
        self._last_error: str | None = None

        self._thread = threading.Thread(
            target=self._run,
            name="czsc-rc8-worker-client",
            daemon=True,
        )
        self._thread.start()

    def __enter__(self) -> Rc8WorkerClient:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def submit(
        self,
        request: CzscRc8Request,
        priority: int,
    ) -> Future[CzscRc8Response]:
        future: Future[CzscRc8Response] = Future()
        with self._state_lock:
            if self._closed:
                raise Rc8WorkerUnavailable("rc8 worker client is closed")
            circuit_state = self._circuit_state_locked(monotonic())
            if circuit_state == "open" or (
                circuit_state == "half_open" and self._half_open_in_flight
            ):
                raise Rc8CircuitOpen("rc8 worker circuit is open")
            if circuit_state == "half_open":
                self._half_open_in_flight = True
            sequence = self._sequence
            self._sequence += 1
            self._queue.put(_QueuedRequest(priority, sequence, request, future))

        return future

    def health(self) -> dict[str, object]:
        with self._state_lock:
            return {
                "active_request_id": self._active_request_id,
                "queue_depth": self._queue.qsize(),
                "circuit_state": self._circuit_state_locked(monotonic()),
                "consecutive_failures": self._consecutive_failures,
                "engine_version": self._engine_version,
                "last_error": self._last_error,
                "closed": self._closed,
            }

    def close(self) -> None:
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            self._stop.set()

        self._fail_queued_requests()
        self._terminate_process()
        self._thread.join()
        self._fail_queued_requests()
        self._terminate_process()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue

            try:
                if self._stop.is_set():
                    self._fail_future_closed(item.future)
                    continue
                if item.future.cancelled():
                    continue

                with self._state_lock:
                    self._active_request_id = item.payload.request_id
                try:
                    response = self._exchange(item.payload)
                except Rc8WorkerUnavailable as exc:
                    if not item.future.done():
                        item.future.set_exception(exc)
                else:
                    if not item.future.done():
                        item.future.set_result(response)
            finally:
                with self._state_lock:
                    self._active_request_id = None
                self._queue.task_done()

    def _exchange(self, request: CzscRc8Request) -> CzscRc8Response:
        last_error = "rc8 worker is unavailable"
        for attempt in range(2):
            if self._stop.is_set():
                raise Rc8WorkerUnavailable("rc8 worker client is closed")
            try:
                response = self._exchange_once(request)
            except _WorkerAttemptError as exc:
                last_error = str(exc)
            except Exception:
                last_error = "rc8 worker is unavailable"
            else:
                self._record_success(response.engine_version)
                return response
            self._terminate_process()
            if attempt == 0 and not self._stop.is_set():
                continue
            if self._stop.is_set():
                raise Rc8WorkerUnavailable("rc8 worker client is closed") from None
            break

        self._record_final_failure(last_error)
        raise Rc8WorkerUnavailable(last_error)

    def _exchange_once(self, request: CzscRc8Request) -> CzscRc8Response:
        try:
            process = self._ensure_process()
            if process.stdin is None:
                raise _WorkerAttemptError("rc8 worker input is unavailable")
            line = json.dumps(
                request.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
            process.stdin.write(line + "\n")
            process.stdin.flush()
        except _WorkerAttemptError:
            raise
        except (OSError, ValueError):
            raise _WorkerAttemptError("rc8 worker is unavailable") from None

        response_line = self._read_response_line(process)
        try:
            response = CzscRc8Response.model_validate_json(response_line)
        except Exception:
            raise _WorkerAttemptError("rc8 worker returned an invalid response") from None
        if response.request_id != request.request_id:
            raise _WorkerAttemptError("rc8 worker response request ID mismatch")
        if response.input_snapshot_id != request.input_snapshot_id:
            raise _WorkerAttemptError("rc8 worker response snapshot ID mismatch")
        return response

    def _record_success(self, engine_version: str) -> None:
        with self._state_lock:
            self._consecutive_failures = 0
            self._circuit_opened_at = None
            self._half_open_in_flight = False
            self._engine_version = engine_version
            self._last_error = None

    def _ensure_process(self) -> subprocess.Popen[str]:
        with self._process_lock:
            if self._process is not None:
                if self._process.poll() is None:
                    return self._process
                self._process.wait()
                self._close_process_streams(self._process)
                self._process = None
            self._process = subprocess.Popen(
                [self._python_path, self._worker_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            return self._process

    def _read_response_line(self, process: subprocess.Popen[str]) -> str:
        if process.stdout is None:
            raise _WorkerAttemptError("rc8 worker output is unavailable")
        deadline = monotonic() + self._hard_timeout_seconds
        chunks = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise _WorkerAttemptError("rc8 worker response timed out")
                chunk = os.read(process.stdout.fileno(), 65_536)
                if not chunk:
                    raise _WorkerAttemptError("rc8 worker exited before a response")
                newline = chunk.find(b"\n")
                if newline < 0:
                    chunks.extend(chunk)
                    continue
                chunks.extend(chunk[:newline])
                if chunk[newline + 1 :]:
                    raise _WorkerAttemptError("rc8 worker returned an invalid response")
                try:
                    return chunks.decode(process.stdout.encoding or "utf-8")
                except UnicodeDecodeError:
                    raise _WorkerAttemptError("rc8 worker returned an invalid response") from None

    def _record_final_failure(self, message: str) -> None:
        with self._state_lock:
            self._consecutive_failures += 1
            self._last_error = " ".join(message.split())[:240]
            self._half_open_in_flight = False
            if self._consecutive_failures >= self._circuit_failures:
                self._circuit_opened_at = monotonic()

    def _circuit_state_locked(self, now: float) -> str:
        if self._circuit_opened_at is None:
            return "closed"
        if now - self._circuit_opened_at < self._circuit_seconds:
            return "open"
        return "half_open"

    def _fail_queued_requests(self) -> None:
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                return
            self._fail_future_closed(item.future)
            self._queue.task_done()

    @staticmethod
    def _fail_future_closed(future: Future[CzscRc8Response]) -> None:
        if not future.done():
            future.set_exception(Rc8WorkerUnavailable("rc8 worker client is closed"))

    def _terminate_process(self) -> None:
        with self._process_lock:
            process = self._process
            self._process = None
            if process is None:
                return
            if process.poll() is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    process.wait()
            else:
                process.wait()
            self._close_process_streams(process)

    @staticmethod
    def _close_process_streams(process: subprocess.Popen[str]) -> None:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()
