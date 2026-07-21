from __future__ import annotations

import logging
from datetime import datetime
from threading import Event, Lock, Thread
from typing import Callable
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")
logger = logging.getLogger(__name__)


def _local_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(SHANGHAI)
    if current.tzinfo is None:
        return current.replace(tzinfo=SHANGHAI)
    return current.astimezone(SHANGHAI)


def _scan_kind(now: datetime) -> str | None:
    current = _local_now(now)
    if current.weekday() >= 5:
        return None
    clock = (current.hour, current.minute)
    if (9, 30) <= clock <= (11, 30) or (13, 0) <= clock <= (15, 0):
        return "intraday"
    if (15, 5) <= clock < (19, 5):
        return "close"
    if (19, 5) <= clock < (19, 35):
        return "share_first"
    if clock >= (19, 35):
        return "share_second"
    return None


class EtfThreeFactorSampler:
    def __init__(
        self,
        *,
        scan: Callable[..., object],
        clock: Callable[[], datetime] | None = None,
        retry_seconds: float = 60,
        idle_seconds: float = 300,
    ) -> None:
        self._scan = scan
        self._clock = clock or (lambda: datetime.now(SHANGHAI))
        self._retry_seconds = retry_seconds
        self._idle_seconds = idle_seconds
        self._completed_intraday_minutes: set[str] = set()
        self._completed_refreshes: set[str] = set()
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._lifecycle_lock = Lock()
        self._sample_lock = Lock()

    def start(self) -> None:
        while True:
            with self._lifecycle_lock:
                thread = self._thread
                stop_event = self._stop_event
                if thread is not None and thread.is_alive():
                    if not stop_event.is_set():
                        return
                    stopped_thread = thread
                else:
                    stop_event = Event()
                    thread = Thread(
                        target=self._run,
                        args=(stop_event,),
                        name="etf-three-factor-sampler",
                        daemon=True,
                    )
                    self._stop_event = stop_event
                    self._thread = thread
                    thread.start()
                    return

            stopped_thread.join()

    def stop(self, *, timeout_seconds: float = 2) -> bool:
        with self._lifecycle_lock:
            thread = self._thread
            stop_event = self._stop_event
        stop_event.set()
        if thread is None or not thread.is_alive():
            return True
        thread.join(timeout=max(0, timeout_seconds))
        return not thread.is_alive()

    def stop_and_wait(self) -> None:
        with self._lifecycle_lock:
            thread = self._thread
            stop_event = self._stop_event
        stop_event.set()
        if thread is not None and thread.is_alive():
            thread.join()

    @property
    def running(self) -> bool:
        with self._lifecycle_lock:
            return self._thread is not None and self._thread.is_alive()

    def sample_once(self) -> bool:
        current = _local_now(self._clock())
        kind = _scan_kind(current)
        if kind is None:
            return False
        key = current.strftime("%Y-%m-%dT%H:%M")
        with self._sample_lock:
            completed = (
                self._completed_intraday_minutes
                if kind == "intraday"
                else self._completed_refreshes
            )
            completion_key = key if kind == "intraday" else f"{current.date().isoformat()}:{kind}"
            if completion_key in completed:
                return False
            self._scan(now=current)
            completed.add(completion_key)
            return True

    def _run(self, stop_event: Event | None = None) -> None:
        active_stop_event = stop_event or self._stop_event
        while not active_stop_event.is_set():
            try:
                sampled = self.sample_once()
            except Exception:
                logger.exception("ETF three-factor scan failed")
                wait_seconds = self._retry_seconds
            else:
                wait_seconds = self._retry_seconds if sampled else min(self._idle_seconds, 60)
            active_stop_event.wait(wait_seconds)
