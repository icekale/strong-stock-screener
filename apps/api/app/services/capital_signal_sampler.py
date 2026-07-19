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
                        name="capital-signal-sampler",
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
        trade_date = current.date().isoformat()
        if not is_capital_signal_refresh_window(current):
            return False

        with self._sample_lock:
            if self._completed_date == trade_date:
                return False
            snapshot = self._refresh()
            if not self._is_complete_snapshot(snapshot, trade_date):
                return False
            self._completed_date = trade_date
            return True

    def _run(self, stop_event: Event | None = None) -> None:
        active_stop_event = stop_event or self._stop_event
        while not active_stop_event.is_set():
            try:
                complete = self.sample_once()
                idle = complete or self._current_date_completed()
            except Exception:
                logger.exception("capital signal refresh failed")
                idle = False
            wait_seconds = self._idle_seconds if idle else self._retry_seconds
            active_stop_event.wait(wait_seconds)

    def _current_date_completed(self) -> bool:
        trade_date = _local_now(self._clock()).date().isoformat()
        with self._sample_lock:
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
