from __future__ import annotations

import json
import os
import re
import selectors
import sys
import time
from pathlib import Path
from typing import Any


PROTOCOL_VERSION = "czsc-rc8-jsonl-v1"
CATALOG_VERSION = "czsc-v2-catalog-1"
ENGINE_VERSION = "1.0.0rc8"
PERIODS = ("1d", "60m", "30m", "5m")
GATE_TIMEOUT_SECONDS = 5.0
LARGE_STDERR_BYTES = 1_048_576
WIRE_ID_SEPARATOR = "::rc8-wire:"
WIRE_ID_PATTERN = re.compile(rf"^(?P<logical>.*){re.escape(WIRE_ID_SEPARATOR)}[0-9a-f]{{32}}$")


def _write(payload: object) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _path_suffix(request_id: str) -> Path | None:
    _, separator, value = request_id.partition(":")
    return Path(value) if separator and value else None


def _logical_request_id(wire_request_id: str) -> str:
    match = WIRE_ID_PATTERN.fullmatch(wire_request_id)
    return match.group("logical") if match is not None else wire_request_id


def _record_attempt(request_id: str) -> None:
    path = _path_suffix(request_id)
    if path is None:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{os.getpid()}\n")


def _response(payload: dict[str, Any]) -> dict[str, Any]:
    diagnostic = {
        "bar_count": 1,
        "fractal_count": 0,
        "stroke_count": 0,
        "last_stroke_direction": "unknown",
    }
    return {
        "schema_version": PROTOCOL_VERSION,
        "catalog_version": CATALOG_VERSION,
        "engine_version": ENGINE_VERSION,
        "request_id": payload["request_id"],
        "input_snapshot_id": payload["input_snapshot_id"],
        "status": "ready",
        "current_states": [],
        "events": [],
        "diagnostics": {period: diagnostic for period in PERIODS},
        "error": None,
    }


def _handle(payload: dict[str, Any]) -> None:
    wire_request_id = str(payload["request_id"])
    request_id = _logical_request_id(wire_request_id)

    if request_id.startswith(("gate:", "gate-malformed:")):
        gate = _path_suffix(request_id)
        if gate is None:
            raise SystemExit(20)
        Path(f"{gate}.ready").write_text("ready\n", encoding="utf-8")
        release = Path(f"{gate}.release")
        deadline = time.monotonic() + GATE_TIMEOUT_SECONDS
        while not release.exists():
            if time.monotonic() >= deadline:
                raise SystemExit(20)
            time.sleep(0.005)
        if request_id.startswith("gate-malformed:"):
            _record_attempt(request_id)
            sys.stdout.write("{not-json\n")
            sys.stdout.flush()
            return
    if request_id.startswith("delay-"):
        time.sleep(0.2)
    if request_id.startswith("slow-"):
        _record_attempt(request_id)
        time.sleep(1)
    if request_id.startswith("record-pid"):
        _record_attempt(request_id)
    if request_id.startswith("stderr-large"):
        _record_attempt(request_id)
        prefix = f"Traceback /private/worker/secret.py {request_id}\n"
        body_size = max(0, LARGE_STDERR_BYTES - (2 * len(prefix)))
        sys.stderr.write(prefix + ("x" * body_size) + prefix)
        sys.stderr.flush()
        _write(_response(payload))
        return
    if request_id.startswith("delayed-extra:"):
        marker = _path_suffix(request_id)
        if marker is None:
            raise SystemExit(22)
        _record_attempt(request_id)
        _write(_response(payload))
        time.sleep(0.05)
        next_attempts = Path(f"{marker}.next.attempts")
        extra = _response(payload)
        extra["request_id"] = f"record-pid-next:{next_attempts}"
        encoded = json.dumps(extra, ensure_ascii=False, separators=(",", ":")) + "\n"
        split = len(encoded) // 2
        sys.stdout.write(encoded[:split])
        sys.stdout.flush()
        time.sleep(0.02)
        sys.stdout.write(encoded[split:])
        sys.stdout.flush()
        Path(f"{marker}.ready").write_text("ready\n", encoding="utf-8")
        return
    if request_id.startswith("correlation-race:"):
        marker = _path_suffix(request_id)
        if marker is None:
            raise SystemExit(23)
        _record_attempt(request_id)
        _write(_response(payload))
        with selectors.DefaultSelector() as selector:
            selector.register(sys.stdin, selectors.EVENT_READ)
            if not selector.select(GATE_TIMEOUT_SECONDS):
                raise SystemExit(23)
        next_attempts = Path(f"{marker}.next.attempts")
        predicted = _response(payload)
        predicted["request_id"] = f"record-pid-correlated:{next_attempts}"
        _write(predicted)
        Path(f"{marker}.forged").write_text("forged\n", encoding="utf-8")
        release = Path(f"{marker}.release")
        deadline = time.monotonic() + GATE_TIMEOUT_SECONDS
        while not release.exists():
            if time.monotonic() >= deadline:
                raise SystemExit(23)
            time.sleep(0.005)
        return

    if request_id.startswith("malformed-json"):
        _record_attempt(request_id)
        sys.stdout.write("{not-json\n")
        sys.stdout.flush()
        return
    if request_id.startswith("malformed-schema"):
        _record_attempt(request_id)
        _write({"request_id": request_id})
        return
    if request_id.startswith("partial-line"):
        _record_attempt(request_id)
        sys.stdout.write("{")
        sys.stdout.flush()
        time.sleep(1)
        return
    if request_id.startswith("mismatch-request"):
        _record_attempt(request_id)
        response = _response(payload)
        response["request_id"] = "unexpected-request-id"
        _write(response)
        return
    if request_id.startswith("mismatch-snapshot"):
        _record_attempt(request_id)
        response = _response(payload)
        response["input_snapshot_id"] = "sha256:mismatched"
        _write(response)
        return
    if request_id.startswith(("exit-", "exit:", "process-exit-")):
        _record_attempt(request_id)
        raise SystemExit(17)
    if request_id.startswith("fail-once:"):
        marker = _path_suffix(request_id)
        if marker is not None:
            with Path(f"{marker}.wire-ids").open("a", encoding="utf-8") as handle:
                handle.write(wire_request_id + "\n")
        if marker is not None and not marker.exists():
            marker.write_text("failed\n", encoding="utf-8")
            raise SystemExit(18)
    if request_id.startswith("valid-then-exit"):
        _write(_response(payload))
        raise SystemExit(19)

    _write(_response(payload))


def main() -> None:
    startup_mode = os.environ.get("FAKE_RC8_STARTUP_MODE", "")
    if startup_mode.startswith("stop-reading:"):
        gate = _path_suffix(startup_mode)
        if gate is None:
            raise SystemExit(21)
        with Path(f"{gate}.attempts").open("a", encoding="utf-8") as handle:
            handle.write(f"{os.getpid()}\n")
        Path(f"{gate}.ready").write_text("ready\n", encoding="utf-8")
        deadline = time.monotonic() + GATE_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            time.sleep(0.005)
        raise SystemExit(21)

    for line in sys.stdin:
        payload = json.loads(line)
        request_id = _logical_request_id(str(payload["request_id"]))
        if request_id.startswith("capture-line:"):
            path = _path_suffix(request_id)
            if path is not None:
                path.write_text(line, encoding="utf-8")
        _handle(payload)


if __name__ == "__main__":
    main()
