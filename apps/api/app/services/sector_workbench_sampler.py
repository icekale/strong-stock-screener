from __future__ import annotations

from datetime import datetime
from threading import Event
from typing import Callable
from zoneinfo import ZoneInfo

from app.services.background_sampler import BackgroundLoopSampler
from app.services.trading_calendar import is_open_session, local_date


def is_sector_workbench_sample_window(now: datetime | None = None) -> bool:
    current = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    if not is_open_session(local_date(current)):
        return False
    seconds = current.hour * 3600 + current.minute * 60 + current.second
    morning = (9 * 3600 + 30 * 60) <= seconds <= (11 * 3600 + 30 * 60)
    afternoon = (13 * 3600) <= seconds <= (15 * 3600)
    return morning or afternoon


class SectorWorkbenchSampler(BackgroundLoopSampler):
    def __init__(
        self,
        *,
        refresh: Callable[[], object],
        clock: Callable[[], datetime] | None = None,
        interval_seconds: float = 90,
        idle_seconds: float = 300,
    ) -> None:
        super().__init__(
            thread_name="sector-workbench-sampler",
            clock=clock,
            interval_seconds=interval_seconds,
            idle_seconds=idle_seconds,
            event_factory=Event,
        )
        self._refresh = refresh

    def sample_once(self) -> bool:
        if not is_sector_workbench_sample_window(self._clock()):
            return False
        self._refresh()
        return True
