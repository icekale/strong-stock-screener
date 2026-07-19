from __future__ import annotations

from datetime import datetime
from threading import Event, RLock, Thread
from typing import Callable
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")


def _local_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(SHANGHAI)
    if current.tzinfo is None:
        return current.replace(tzinfo=SHANGHAI)
    return current.astimezone(SHANGHAI)


def is_capital_signal_refresh_window(now: datetime | None = None) -> bool:
    current = _local_now(now)
    if current.weekday() >= 5:
        return False
    seconds = current.hour * 3600 + current.minute * 60 + current.second
    return (19 * 3600 + 5 * 60) <= seconds < (23 * 3600 + 31 * 60)


class CapitalSignalSampler:
    def __init__(
        self,
        *,
        refresh: Callable[[], object],
        clock: Callable[[], datetime] | None = None,
        retry_seconds: float = 900,
        idle_seconds: float = 1800,
    ) -> None:
        self._refresh = refresh
        self._clock = clock or (lambda: datetime.now(SHANGHAI))
        self._retry_seconds = retry_seconds
        self._idle_seconds = idle_seconds
        self._completed_date: str | None = None
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._lock = RLock()

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = Thread(
                target=self._run,
                name="capital-signal-sampler",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)

    @property
    def running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def sample_once(self) -> bool:
        current = _local_now(self._clock())
        trade_date = current.date().isoformat()
        if not is_capital_signal_refresh_window(current):
            return False
        with self._lock:
            if self._completed_date == trade_date:
                return False

        snapshot = self._refresh()
        if not self._is_complete_snapshot(snapshot, trade_date):
            return False

        with self._lock:
            self._completed_date = trade_date
        return True

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                complete = self.sample_once()
                idle = complete or self._current_date_completed()
            except Exception:
                idle = False
            wait_seconds = self._idle_seconds if idle else self._retry_seconds
            self._stop_event.wait(wait_seconds)

    def _current_date_completed(self) -> bool:
        trade_date = _local_now(self._clock()).date().isoformat()
        with self._lock:
            return self._completed_date == trade_date

    @staticmethod
    def _is_complete_snapshot(snapshot: object, trade_date: str) -> bool:
        if getattr(snapshot, "trade_date", None) != trade_date:
            return False
        core_items = getattr(snapshot, "core_items", None)
        validation_items = getattr(snapshot, "validation_items", None)
        if not isinstance(core_items, list) or len(core_items) != 7:
            return False
        if not isinstance(validation_items, list) or len(validation_items) != 3:
            return False
        return all(
            getattr(item, "total_shares", None) is not None
            for item in [*core_items, *validation_items]
        )
