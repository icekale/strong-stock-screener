#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import selectors
import subprocess
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from time import monotonic, perf_counter
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.chanlun.research_protocol import (  # noqa: E402
    APPROVED_PERIODS,
    CzscRc8Request,
    CzscRc8Response,
    build_research_request,
)


WORKER_PATH = ROOT / "apps" / "api" / "app" / "services" / "chanlun" / "rc8_worker.py"
SHANGHAI = ZoneInfo("Asia/Shanghai")
END_DATE = date(2026, 6, 30)
_IO_CHUNK_SIZE = 65_536
_STDERR_RAW_LIMIT = 4_096
_STDERR_TAIL_LIMIT = 1_024
_RESPONSE_TIMEOUT_SECONDS = 10.0
_SHUTDOWN_WAIT_SECONDS = 2.0
_PROCESS_WAIT_SECONDS = 0.5
SESSION_CLOSES = {
    "60m": (time(10, 30), time(11, 30), time(14), time(15)),
    "30m": (
        time(10),
        time(10, 30),
        time(11),
        time(11, 30),
        time(13, 30),
        time(14),
        time(14, 30),
        time(15),
    ),
    "5m": tuple(
        [time(9, 35)]
        + [
            (
                datetime.combine(END_DATE, time(9, 35)) + timedelta(minutes=5 * index)
            ).time()
            for index in range(1, 24)
        ]
        + [
            (
                datetime.combine(END_DATE, time(13, 5)) + timedelta(minutes=5 * index)
            ).time()
            for index in range(24)
        ]
    ),
}


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _business_days_ending(end: date, count: int) -> list[date]:
    days = []
    current = end
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current -= timedelta(days=1)
    return list(reversed(days))


def _period_dates(period: str, bar_count: int) -> list[str]:
    if period == "1d":
        return [day.isoformat() for day in _business_days_ending(END_DATE, bar_count)]

    closes = SESSION_CLOSES[period]
    day_count = math.ceil(bar_count / len(closes))
    timestamps = [
        datetime.combine(day, close, tzinfo=SHANGHAI).isoformat(timespec="seconds")
        for day in _business_days_ending(END_DATE, day_count)
        for close in closes
    ]
    return timestamps[-bar_count:]


def _bars(period: str, bar_count: int, symbol_index: int) -> list[dict[str, object]]:
    bars = []
    for index, bar_date in enumerate(_period_dates(period, bar_count)):
        phase = index % 32
        triangle = phase if phase < 16 else 31 - phase
        close = round(
            10 + symbol_index * 0.05 + triangle * 0.06 + (index // 64) * 0.02, 4
        )
        open_price = round(close + (0.03 if index % 2 == 0 else -0.03), 4)
        high = round(max(open_price, close) + 0.08, 4)
        low = round(min(open_price, close) - 0.08, 4)
        volume = float(100_000 + symbol_index * 1_000 + index * 10)
        bars.append(
            {
                "date": bar_date,
                "open": open_price,
                "close": close,
                "high": high,
                "low": low,
                "volume": volume,
                "amount": round(volume * (open_price + close) / 2, 2),
                "ma5": None,
                "ma10": None,
                "ma20": None,
                "ma60": None,
            }
        )
    return bars


def _requests(symbol_count: int, bar_count: int) -> list[CzscRc8Request]:
    requests = []
    for index in range(symbol_count):
        periods = {
            period: _bars(period, bar_count, index) for period in APPROVED_PERIODS
        }
        requests.append(
            build_research_request(
                f"{600_000 + index:06d}.SH",
                periods,
                request_id=f"benchmark-{index + 1:04d}",
                adjustment_mode="qfq",
            )
        )
    return requests


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _max_child_rss_bytes() -> int | None:
    try:
        import resource
    except ImportError:
        return None

    maximum = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if maximum <= 0:
        return None
    return int(maximum if sys.platform == "darwin" else maximum * 1024)


def _select_until(
    selector: selectors.BaseSelector,
    deadline: float,
) -> list[tuple[selectors.SelectorKey, int]]:
    _require_time_remaining(deadline)
    remaining = deadline - monotonic()
    events = selector.select(remaining)
    if not events:
        raise TimeoutError("worker response timed out")
    return events


def _require_time_remaining(deadline: float) -> None:
    if monotonic() >= deadline:
        raise TimeoutError("worker response timed out")


def _drain_stderr(process: subprocess.Popen[str], tail: bytearray) -> None:
    if process.stderr is None:
        return
    for _ in range(16):
        try:
            chunk = os.read(process.stderr.fileno(), _IO_CHUNK_SIZE)
        except (BlockingIOError, OSError):
            return
        if not chunk:
            return
        tail.extend(chunk)
        if len(tail) > _STDERR_RAW_LIMIT:
            del tail[:-_STDERR_RAW_LIMIT]


def _write_request(
    process: subprocess.Popen[str],
    payload: bytes,
    deadline: float,
    stderr_tail: bytearray,
) -> None:
    if process.stdin is None or process.stdout is None or process.stderr is None:
        raise RuntimeError("worker JSONL pipes are unavailable")
    offset = 0
    view = memoryview(payload)
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdin, selectors.EVENT_WRITE)
        selector.register(process.stdout, selectors.EVENT_READ)
        selector.register(process.stderr, selectors.EVENT_READ)
        while offset < len(payload):
            _require_time_remaining(deadline)
            _drain_stderr(process, stderr_tail)
            try:
                written = os.write(process.stdin.fileno(), view[offset:])
            except BlockingIOError:
                written = 0
            except BrokenPipeError:
                raise RuntimeError(
                    "worker exited before returning a response"
                ) from None
            if written > 0:
                offset += written
                continue
            for key, _ in _select_until(selector, deadline):
                if key.fileobj is process.stderr:
                    _drain_stderr(process, stderr_tail)
                elif key.fileobj is process.stdout:
                    try:
                        unsolicited = os.read(process.stdout.fileno(), _IO_CHUNK_SIZE)
                    except BlockingIOError:
                        continue
                    if not unsolicited:
                        raise RuntimeError("worker exited before returning a response")
                    raise RuntimeError("worker returned unsolicited output")


def _read_response_line(
    process: subprocess.Popen[str],
    deadline: float,
    stderr_tail: bytearray,
) -> str:
    if process.stdout is None or process.stderr is None:
        raise RuntimeError("worker JSONL pipes are unavailable")
    chunks = bytearray()
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        selector.register(process.stderr, selectors.EVENT_READ)
        while True:
            _require_time_remaining(deadline)
            _drain_stderr(process, stderr_tail)
            try:
                chunk = os.read(process.stdout.fileno(), _IO_CHUNK_SIZE)
            except BlockingIOError:
                chunk = None
            if chunk is None:
                for key, _ in _select_until(selector, deadline):
                    if key.fileobj is process.stderr:
                        _drain_stderr(process, stderr_tail)
                continue
            if not chunk:
                raise RuntimeError("worker exited before returning a response")
            newline = chunk.find(b"\n")
            if newline < 0:
                chunks.extend(chunk)
                continue
            chunks.extend(chunk[:newline])
            if chunk[newline + 1 :]:
                raise RuntimeError("worker returned an invalid response")
            try:
                return chunks.decode(process.stdout.encoding or "utf-8")
            except UnicodeDecodeError:
                raise RuntimeError("worker returned an invalid response") from None


def _terminate_worker(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        process.wait()
        return
    try:
        process.terminate()
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=_PROCESS_WAIT_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        process.kill()
    except ProcessLookupError:
        pass
    process.wait(timeout=_PROCESS_WAIT_SECONDS)


def _stop_worker(
    process: subprocess.Popen[str],
    *,
    terminate: bool,
    stderr_tail: bytearray,
) -> int:
    if terminate:
        _terminate_worker(process)
    else:
        if process.stdin is not None and not process.stdin.closed:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=_SHUTDOWN_WAIT_SECONDS)
        except subprocess.TimeoutExpired:
            _terminate_worker(process)

    _drain_stderr(process, stderr_tail)
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is not None and not stream.closed:
            stream.close()
    return process.returncode


def _sanitize_text(value: object, *, limit: int = 500) -> str:
    return " ".join(str(value).split())[-limit:]


def run_benchmark(
    *,
    requests: list[CzscRc8Request],
    worker_python: str,
) -> tuple[dict[str, Any], bool]:
    wire_requests = [
        (
            request,
            json.dumps(
                request.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ),
        )
        for request in requests
    ]
    latencies_ms = []
    successes = 0
    failures = 0
    errors = []
    process: subprocess.Popen[str] | None = None
    worker_exit_code: int | None = None
    stderr_tail = bytearray()
    terminate_worker = False
    total_started = perf_counter()

    try:
        process = subprocess.Popen(
            [worker_python, str(WORKER_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        if process.stdin is None or process.stdout is None or process.stderr is None:
            raise RuntimeError("worker JSONL pipes are unavailable")
        for stream in (process.stdin, process.stdout, process.stderr):
            os.set_blocking(stream.fileno(), False)

        for index, (request, payload) in enumerate(wire_requests):
            request_started = perf_counter()
            try:
                deadline = monotonic() + _RESPONSE_TIMEOUT_SECONDS
                wire_payload = (payload + "\n").encode(
                    process.stdin.encoding or "utf-8"
                )
                _write_request(process, wire_payload, deadline, stderr_tail)
                response_line = _read_response_line(process, deadline, stderr_tail)
                response = CzscRc8Response.model_validate_json(response_line)
                if response.status != "ready":
                    raise ValueError(
                        response.error or "worker returned an error response"
                    )
                if response.request_id != request.request_id:
                    raise ValueError("worker response request ID mismatch")
                if response.input_snapshot_id != request.input_snapshot_id:
                    raise ValueError("worker response snapshot ID mismatch")
            except TimeoutError as exc:
                failures += len(wire_requests) - index
                errors.append(f"{request.request_id}: {_sanitize_text(exc)}")
                remaining = len(wire_requests) - index - 1
                if remaining:
                    errors.append(
                        f"worker timed out with {remaining} requests unprocessed"
                    )
                terminate_worker = True
                break
            except Exception as exc:
                failures += 1
                errors.append(f"{request.request_id}: {_sanitize_text(exc)}")
                if process.poll() is not None:
                    remaining = len(wire_requests) - index - 1
                    failures += remaining
                    if remaining:
                        errors.append(
                            f"worker exited with {remaining} requests unprocessed"
                        )
                    break
            else:
                successes += 1
                latencies_ms.append((perf_counter() - request_started) * 1_000)
    except Exception as exc:
        failures = len(wire_requests)
        errors.append(f"benchmark setup failed: {_sanitize_text(exc)}")
        terminate_worker = True
    finally:
        if process is not None:
            worker_exit_code = _stop_worker(
                process,
                terminate=terminate_worker,
                stderr_tail=stderr_tail,
            )
        total_elapsed_seconds = perf_counter() - total_started

    if worker_exit_code not in (None, 0):
        errors.append(f"worker exited with code {worker_exit_code}")
    stderr = _sanitize_text(
        stderr_tail.decode("utf-8", errors="replace"),
        limit=_STDERR_TAIL_LIMIT,
    )
    if stderr:
        errors.append(f"worker stderr: {stderr}")

    p50 = _percentile(latencies_ms, 0.50)
    p95 = _percentile(latencies_ms, 0.95)
    summary = {
        "mode": "cache-free-sequential-jsonl",
        "symbols": len(requests),
        "bars_per_period": len(requests[0].periods["1d"]) if requests else 0,
        "p50_latency_ms": round(p50, 3) if p50 is not None else None,
        "p95_latency_ms": round(p95, 3) if p95 is not None else None,
        "total_elapsed_seconds": round(total_elapsed_seconds, 3),
        "successes": successes,
        "failures": failures,
        "max_rss_bytes": _max_child_rss_bytes(),
        "worker_exit_code": worker_exit_code,
        "errors": errors,
    }
    valid = failures == 0 and successes == len(requests) and worker_exit_code == 0
    return summary, valid


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark the standalone CZSC rc8 JSONL worker."
    )
    parser.add_argument("--symbols", type=_positive_int, required=True)
    parser.add_argument("--bars", type=_positive_int, required=True)
    parser.add_argument("--worker-python", required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    args = parser.parse_args()

    requests = _requests(args.symbols, args.bars)
    summary, valid = run_benchmark(
        requests=requests,
        worker_python=args.worker_python,
    )
    output = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
