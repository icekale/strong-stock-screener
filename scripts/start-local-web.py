#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "apps" / "web-vue"
DEFAULT_LOG = Path("/tmp/strong-stock-web-3110.log")
DEFAULT_PID_FILE = Path("/tmp/strong-stock-web-3110.pid")


def listening_pids(port: int) -> list[int]:
    try:
        result = subprocess.run(
            ["lsof", "-tiTCP:%d" % port, "-sTCP:LISTEN"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError:
        return []
    return [int(line) for line in result.stdout.splitlines() if line.strip().isdigit()]


def stop_pids(pids: list[int], timeout: float = 5.0) -> None:
    if not pids:
        return
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not any(process_exists(pid) for pid in pids):
            return
        time.sleep(0.2)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_for_port(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.5)
    return False


def daemonize_web(port: int, log_path: Path, pid_file: Path) -> None:
    pnpm = shutil.which("pnpm")
    if not pnpm:
        raise RuntimeError("pnpm not found in PATH")

    first_pid = os.fork()
    if first_pid:
        os.waitpid(first_pid, 0)
        return

    os.setsid()
    second_pid = os.fork()
    if second_pid:
        os._exit(0)

    env = os.environ.copy()

    log_path.parent.mkdir(parents=True, exist_ok=True)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()), encoding="utf-8")

    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.dup2(fd, 1)
        os.dup2(fd, 2)
    finally:
        os.close(fd)
    null_fd = os.open("/dev/null", os.O_RDONLY)
    try:
        os.dup2(null_fd, 0)
    finally:
        os.close(null_fd)

    os.chdir(WEB_DIR)
    os.execve(pnpm, [pnpm, "dev", "--", "--host", "127.0.0.1", "--port", str(port)], env)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the local Vue web dev server safely.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("STRONG_STOCK_WEB_PORT", "3110")))
    parser.add_argument("--no-kill", action="store_true", help="Do not stop an existing listener on the target port.")
    parser.add_argument("--log", type=Path, default=Path(os.environ.get("STRONG_STOCK_WEB_LOG", DEFAULT_LOG)))
    parser.add_argument(
        "--pid-file",
        type=Path,
        default=Path(os.environ.get("STRONG_STOCK_WEB_PID_FILE", DEFAULT_PID_FILE)),
    )
    args = parser.parse_args()

    if not WEB_DIR.exists():
        print(f"web directory not found: {WEB_DIR}", file=sys.stderr)
        return 1

    if not args.no_kill:
        pids = listening_pids(args.port)
        if pids:
            print(f"stopping existing listener on {args.port}: {', '.join(map(str, pids))}")
            stop_pids(pids)

    daemonize_web(args.port, args.log, args.pid_file)

    if not wait_for_port(args.port):
        print(f"web server did not become ready on {args.port}; see {args.log}", file=sys.stderr)
        return 1

    print(f"web ready: http://127.0.0.1:{args.port}")
    print(f"log: {args.log}")
    print(f"pid file: {args.pid_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
