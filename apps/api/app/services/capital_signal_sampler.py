from __future__ import annotations

import logging
from datetime import datetime
from threading import Event, Lock
from typing import Callable
from zoneinfo import ZoneInfo

from app.services.background_sampler import BackgroundLoopSampler
from app.services.trading_calendar import is_open_session, local_date


SHANGHAI = ZoneInfo("Asia/Shanghai")
logger = logging.getLogger(__name__)


def _local_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(SHANGHAI)
    if current.tzinfo is None:
        return current.replace(tzinfo=SHANGHAI)
    return current.astimezone(SHANGHAI)


def is_capital_signal_refresh_window(now: datetime | None = None) -> bool:
    current = _local_now(now)
    if not is_open_session(local_date(current)):
        return False
    seconds = current.hour * 3600 + current.minute * 60 + current.second
    return (19 * 3600 + 5 * 60) <= seconds < (23 * 3600 + 31 * 60)


class CapitalSignalSampler(BackgroundLoopSampler):
    def __init__(
        self,
        *,
        refresh: Callable[[], object],
        clock: Callable[[], datetime] | None = None,
        retry_seconds: float = 900,
        idle_seconds: float = 1800,
    ) -> None:
        super().__init__(
            thread_name="capital-signal-sampler",
            clock=clock,
            retry_seconds=retry_seconds,
            idle_seconds=idle_seconds,
            event_factory=Event,
            error_logger=logger,
            error_message="capital signal refresh failed",
        )
        self._refresh = refresh
        self._completed_date: str | None = None
        self._sample_lock = Lock()

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

    def _wait_seconds(self, sampled: bool) -> float:
        complete = sampled or self._current_date_completed()
        return self._idle_seconds if complete else self._retry_seconds

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
