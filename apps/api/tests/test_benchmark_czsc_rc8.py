from __future__ import annotations

import importlib.util
import json
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_PATH = ROOT / "scripts" / "benchmark-czsc-rc8.py"
SPEC = importlib.util.spec_from_file_location("benchmark_czsc_rc8", BENCHMARK_PATH)
assert SPEC is not None and SPEC.loader is not None
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


def test_main_times_out_and_drains_noisy_worker(monkeypatch, tmp_path: Path) -> None:
    stop_path = tmp_path / "stop"
    worker_path = tmp_path / "noisy_worker.py"
    worker_path.write_text(
        "\n".join(
            [
                "import os",
                "import threading",
                "import time",
                "from pathlib import Path",
                "",
                f"stop_path = Path({str(stop_path)!r})",
                "",
                "def flood_stderr():",
                "    chunk = b'x' * 4096",
                "    while True:",
                "        try:",
                "            os.write(2, chunk)",
                "        except OSError:",
                "            return",
                "",
                "def flood_stdout():",
                "    time.sleep(0.02)",
                "    chunk = b'y' * 4096",
                "    while True:",
                "        try:",
                "            os.write(1, chunk)",
                "        except OSError:",
                "            return",
                "",
                "threading.Thread(target=flood_stderr, daemon=True).start()",
                "threading.Thread(target=flood_stdout, daemon=True).start()",
                "while not stop_path.exists():",
                "    time.sleep(0.01)",
                "os._exit(0)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    json_output = tmp_path / "benchmark.json"
    monkeypatch.setattr(BENCHMARK, "WORKER_PATH", worker_path)
    monkeypatch.setattr(BENCHMARK, "_RESPONSE_TIMEOUT_SECONDS", 0.05, raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(BENCHMARK_PATH),
            "--symbols",
            "1",
            "--bars",
            "8",
            "--worker-python",
            sys.executable,
            "--json-output",
            str(json_output),
        ],
    )
    result: dict[str, object] = {}
    finished = threading.Event()

    def invoke() -> None:
        try:
            result["exit_code"] = BENCHMARK.main()
        except BaseException as exc:
            result["error"] = exc
        finally:
            finished.set()

    thread = threading.Thread(target=invoke, daemon=True)
    thread.start()
    completed_before_deadline = finished.wait(0.75)
    stop_path.touch()
    thread.join(timeout=2)

    assert not thread.is_alive(), "benchmark cleanup did not stop the faulty worker"
    assert completed_before_deadline, "benchmark exceeded its response deadline"
    assert "error" not in result
    assert result["exit_code"] == 1

    summary = json.loads(json_output.read_text(encoding="utf-8"))
    assert summary["successes"] == 0
    assert summary["failures"] == 1
    assert any("timed out" in error for error in summary["errors"])
    assert all("\n" not in error and "\r" not in error for error in summary["errors"])
    stderr_errors = [error for error in summary["errors"] if error.startswith("worker stderr: ")]
    assert stderr_errors
    assert len(stderr_errors[0]) <= BENCHMARK._STDERR_TAIL_LIMIT + len("worker stderr: ")
