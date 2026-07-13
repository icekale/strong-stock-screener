from __future__ import annotations

import json
import os
import queue
import re
import selectors
import subprocess
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import Callable, TypeVar

from app.services.chanlun.research_protocol import CzscRc8Request, CzscRc8Response


_IO_CHUNK_SIZE = 65_536
_STDERR_RAW_LIMIT = 4_096
_STDERR_TAIL_LIMIT = 1_024
_PATH_PATTERN = re.compile(r"(?:[A-Za-z]:)?(?:[/\\][^\s/\\]+)+")
_SHUTDOWN_WAIT_SECONDS = 2.0
_CALLBACK_JOIN_SECONDS = 0.05
_PROCESS_WAIT_SECONDS = 0.5
_T = TypeVar("_T")


class Rc8WorkerUnavailable(RuntimeError):
    """The rc8 worker cannot serve a request."""


class Rc8CircuitOpen(Rc8WorkerUnavailable):
    """The rc8 worker circuit is rejecting requests."""


class _WorkerAttemptError(RuntimeError):
    pass


class _CallbackFuture(Future[_T]):
    def __init__(self, dispatch: Callable[[Callable[[], None]], None]) -> None:
        super().__init__()
        self._dispatch = dispatch

    def _invoke_callbacks(self) -> None:
        if self._done_callbacks:
            self._dispatch(super()._invoke_callbacks)


@dataclass(order=True)
class _QueuedRequest:
    priority: int
    sequence: int
    payload: CzscRc8Request = field(compare=False)
    future: Future[CzscRc8Response] = field(compare=False)
    half_open_probe: bool = field(default=False, compare=False)


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
        self._callback_lock = threading.Lock()
        self._stop = threading.Event()
        self._shutdown_complete = threading.Event()
        self._process: subprocess.Popen[str] | None = None
        self._callback_queue: queue.Queue[Callable[[], None] | None] = queue.Queue()
        self._callback_thread: threading.Thread | None = None
        self._callbacks_stopping = False
        self._sequence = 0
        self._closed = False
        self._closing = False
        self._shutdown_error: str | None = None
        self._active_request_id: str | None = None
        self._consecutive_failures = 0
        self._circuit_opened_at: float | None = None
        self._half_open_in_flight = False
        self._engine_version: str | None = None
        self._last_error: str | None = None
        self._stderr_raw = bytearray()
        self._stderr_tail: str | None = None

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
        future: Future[CzscRc8Response] = _CallbackFuture(self._dispatch_callbacks)
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
            half_open_probe = circuit_state == "half_open"
            sequence = self._sequence
            self._sequence += 1
            self._queue.put(
                _QueuedRequest(
                    priority,
                    sequence,
                    request,
                    future,
                    half_open_probe,
                )
            )

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
                "stderr_tail": self._stderr_tail,
                "closed": self._closed,
            }

    def close(self) -> None:
        with self._state_lock:
            if self._shutdown_complete.is_set():
                shutdown_error = self._shutdown_error
                if shutdown_error is not None:
                    raise Rc8WorkerUnavailable(shutdown_error)
                return
            shutdown_owner = not self._closing
            if shutdown_owner:
                self._closing = True
                self._closed = True
                self._half_open_in_flight = False
                self._stop.set()

        if not shutdown_owner:
            if not self._shutdown_complete.wait(timeout=_SHUTDOWN_WAIT_SECONDS):
                raise Rc8WorkerUnavailable("rc8 worker shutdown timed out")
            with self._state_lock:
                shutdown_error = self._shutdown_error
            if shutdown_error is not None:
                raise Rc8WorkerUnavailable(shutdown_error)
            return

        shutdown_error = None
        try:
            self._fail_queued_requests()
            self._terminate_process()
            self._thread.join(timeout=_SHUTDOWN_WAIT_SECONDS)
            if self._thread.is_alive():
                shutdown_error = "rc8 worker dispatcher shutdown timed out"
            else:
                self._fail_queued_requests()
                self._terminate_process()
        except Exception:
            shutdown_error = "rc8 worker shutdown failed"
        finally:
            self._stop_callback_dispatcher()
            with self._state_lock:
                self._shutdown_error = shutdown_error
            self._shutdown_complete.set()

        if shutdown_error is not None:
            raise Rc8WorkerUnavailable(shutdown_error)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.05)
            except queue.Empty:
                self._drain_idle_stderr()
                continue

            try:
                if not item.future.set_running_or_notify_cancel():
                    self._release_probe_reservation(item)
                    continue
                if self._stop.is_set():
                    self._fail_future_closed(item.future)
                    continue
                dispatch_error = self._dispatch_error(item)
                if dispatch_error is not None:
                    item.future.set_exception(dispatch_error)
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

    def _dispatch_error(self, item: _QueuedRequest) -> Rc8WorkerUnavailable | None:
        with self._state_lock:
            if self._closed:
                if item.half_open_probe:
                    self._half_open_in_flight = False
                return Rc8WorkerUnavailable("rc8 worker client is closed")
            circuit_state = self._circuit_state_locked(monotonic())
            if circuit_state == "closed" or (circuit_state == "half_open" and item.half_open_probe):
                return None
            if item.half_open_probe:
                self._half_open_in_flight = False
            return Rc8CircuitOpen("rc8 worker circuit is open")

    def _release_probe_reservation(self, item: _QueuedRequest) -> None:
        if not item.half_open_probe:
            return
        with self._state_lock:
            self._half_open_in_flight = False

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
        deadline = monotonic() + self._hard_timeout_seconds
        try:
            process = self._ensure_process()
            if process.stdin is None:
                raise _WorkerAttemptError("rc8 worker input is unavailable")
            self._require_time_remaining(deadline)
            line = json.dumps(
                request.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
            self._require_time_remaining(deadline)
            self._preflight_process(process)
            payload = (line + "\n").encode(process.stdin.encoding or "utf-8")
            self._write_request(process, payload, deadline)
        except _WorkerAttemptError:
            raise
        except (OSError, ValueError):
            raise _WorkerAttemptError("rc8 worker is unavailable") from None

        response_line = self._read_response_line(process, deadline)
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
            for stream in (self._process.stdin, self._process.stdout, self._process.stderr):
                if stream is not None:
                    os.set_blocking(stream.fileno(), False)
            self._stderr_raw.clear()
            with self._state_lock:
                self._stderr_tail = None
            return self._process

    def _preflight_process(self, process: subprocess.Popen[str]) -> None:
        self._drain_stderr(process)
        if process.stdout is None:
            raise _WorkerAttemptError("rc8 worker output is unavailable")
        try:
            unsolicited = os.read(process.stdout.fileno(), _IO_CHUNK_SIZE)
        except BlockingIOError:
            unsolicited = None
        if unsolicited == b"":
            raise _WorkerAttemptError("rc8 worker exited before a response")
        if unsolicited:
            raise _WorkerAttemptError("rc8 worker returned unsolicited output")
        if process.poll() is not None:
            raise _WorkerAttemptError("rc8 worker exited before a response")

    def _write_request(
        self,
        process: subprocess.Popen[str],
        payload: bytes,
        deadline: float,
    ) -> None:
        if process.stdin is None or process.stdout is None or process.stderr is None:
            raise _WorkerAttemptError("rc8 worker pipes are unavailable")
        offset = 0
        view = memoryview(payload)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdin, selectors.EVENT_WRITE)
            selector.register(process.stdout, selectors.EVENT_READ)
            selector.register(process.stderr, selectors.EVENT_READ)
            while offset < len(payload):
                self._require_time_remaining(deadline)
                self._drain_stderr(process)
                try:
                    written = os.write(process.stdin.fileno(), view[offset:])
                except BlockingIOError:
                    written = 0
                if written > 0:
                    offset += written
                    continue
                events = self._select_until(selector, deadline)
                for key, _ in events:
                    if key.fileobj is process.stderr:
                        self._drain_stderr(process)
                    elif key.fileobj is process.stdout:
                        try:
                            unsolicited = os.read(process.stdout.fileno(), _IO_CHUNK_SIZE)
                        except BlockingIOError:
                            continue
                        if unsolicited == b"":
                            raise _WorkerAttemptError("rc8 worker exited before a response")
                        if unsolicited:
                            raise _WorkerAttemptError("rc8 worker returned unsolicited output")

    def _read_response_line(
        self,
        process: subprocess.Popen[str],
        deadline: float,
    ) -> str:
        if process.stdout is None:
            raise _WorkerAttemptError("rc8 worker output is unavailable")
        chunks = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            if process.stderr is not None:
                selector.register(process.stderr, selectors.EVENT_READ)
            while True:
                self._drain_stderr(process)
                try:
                    chunk = os.read(process.stdout.fileno(), _IO_CHUNK_SIZE)
                except BlockingIOError:
                    chunk = None
                if chunk is None:
                    events = self._select_until(selector, deadline)
                    for key, _ in events:
                        if process.stderr is not None and key.fileobj is process.stderr:
                            self._drain_stderr(process)
                    continue
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

    def _select_until(
        self,
        selector: selectors.BaseSelector,
        deadline: float,
    ) -> list[tuple[selectors.SelectorKey, int]]:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise _WorkerAttemptError("rc8 worker response timed out")
        events = selector.select(remaining)
        if not events:
            raise _WorkerAttemptError("rc8 worker response timed out")
        return events

    @staticmethod
    def _require_time_remaining(deadline: float) -> None:
        if monotonic() >= deadline:
            raise _WorkerAttemptError("rc8 worker response timed out")

    def _drain_idle_stderr(self) -> None:
        with self._process_lock:
            if self._process is not None:
                self._drain_stderr(self._process)

    def _drain_stderr(self, process: subprocess.Popen[str]) -> None:
        if process.stderr is None:
            return
        for _ in range(16):
            try:
                chunk = os.read(process.stderr.fileno(), _IO_CHUNK_SIZE)
            except (BlockingIOError, OSError):
                return
            if not chunk:
                return
            self._stderr_raw.extend(chunk)
            if len(self._stderr_raw) > _STDERR_RAW_LIMIT:
                del self._stderr_raw[:-_STDERR_RAW_LIMIT]
            tail = self._stderr_raw.decode(
                process.stderr.encoding or "utf-8",
                errors="replace",
            )
            sanitized = self._sanitize_text(tail, limit=_STDERR_TAIL_LIMIT)
            with self._state_lock:
                self._stderr_tail = sanitized or None

    @staticmethod
    def _sanitize_text(value: str, *, limit: int) -> str:
        scrubbed = re.sub(r"traceback", "worker-error", value, flags=re.IGNORECASE)
        scrubbed = _PATH_PATTERN.sub("<path>", scrubbed)
        return " ".join(scrubbed.split())[-limit:]

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
            self._release_probe_reservation(item)
            if item.future.set_running_or_notify_cancel():
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
                    process.wait(timeout=_PROCESS_WAIT_SECONDS)
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    try:
                        process.wait(timeout=_PROCESS_WAIT_SECONDS)
                    except subprocess.TimeoutExpired:
                        self._close_process_streams(process)
                        raise Rc8WorkerUnavailable("rc8 worker process reap timed out") from None
            else:
                process.wait()
            self._close_process_streams(process)

    @staticmethod
    def _close_process_streams(process: subprocess.Popen[str]) -> None:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()

    def _dispatch_callbacks(self, callback: Callable[[], None]) -> None:
        with self._callback_lock:
            if self._callback_thread is None:
                self._callback_thread = threading.Thread(
                    target=self._run_callbacks,
                    name="czsc-rc8-future-callbacks",
                    daemon=True,
                )
                self._callback_thread.start()
            self._callback_queue.put(callback)

    def _run_callbacks(self) -> None:
        while True:
            callback = self._callback_queue.get()
            try:
                if callback is None:
                    return
                callback()
            finally:
                self._callback_queue.task_done()

    def _stop_callback_dispatcher(self) -> None:
        with self._callback_lock:
            if self._callbacks_stopping:
                thread = self._callback_thread
            else:
                self._callbacks_stopping = True
                thread = self._callback_thread
                if thread is not None:
                    self._callback_queue.put(None)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=_CALLBACK_JOIN_SECONDS)
