from __future__ import annotations

from datetime import datetime
from threading import Event, Thread
from typing import Callable
from zoneinfo import ZoneInfo


def is_sector_workbench_sample_window(now: datetime | None = None) -> bool:
    current = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    seconds = current.hour * 3600 + current.minute * 60 + current.second
    morning = (9 * 3600 + 30 * 60) <= seconds <= (11 * 3600 + 30 * 60)
    afternoon = (13 * 3600) <= seconds <= (15 * 3600)
    return morning or afternoon


class SectorWorkbenchSampler:
    def __init__(
        self,
        *,
        refresh: Callable[[], object],
        clock: Callable[[], datetime] | None = None,
        interval_seconds: float = 90,
        idle_seconds: float = 300,
    ) -> None:
        self._refresh = refresh
        self._clock = clock or (lambda: datetime.now(ZoneInfo("Asia/Shanghai")))
        self._interval_seconds = interval_seconds
        self._idle_seconds = idle_seconds
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, name="sector-workbench-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)

    def sample_once(self) -> bool:
        if not is_sector_workbench_sample_window(self._clock()):
            return False
        self._refresh()
        return True

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                sampled = self.sample_once()
            except Exception:
                sampled = False
            wait_seconds = self._interval_seconds if sampled else self._idle_seconds
            self._stop_event.wait(wait_seconds)
