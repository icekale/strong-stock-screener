from __future__ import annotations

from datetime import datetime
from threading import Event, Lock
from typing import Callable
from zoneinfo import ZoneInfo

from app.services.background_sampler import BackgroundLoopSampler
from app.services.trading_calendar import is_open_session, local_date


SHANGHAI = ZoneInfo("Asia/Shanghai")
LATE_SHARE_START_MINUTE = 19 * 60 + 35
LATE_SHARE_END_MINUTE = 23 * 60 + 31
LATE_SHARE_BUCKET_MINUTES = 15
EXPECTED_CORE_ETF_COUNT = 7


def _local_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(SHANGHAI)
    if current.tzinfo is None:
        return current.replace(tzinfo=SHANGHAI)
    return current.astimezone(SHANGHAI)


def _scan_kind(now: datetime) -> str | None:
    current = _local_now(now)
    if not is_open_session(local_date(current)):
        return None
    clock = (current.hour, current.minute)
    if (9, 30) <= clock <= (11, 30) or (13, 0) <= clock <= (15, 0):
        return "intraday"
    if (15, 5) <= clock < (19, 5):
        return "close"
    if (19, 5) <= clock < (19, 35):
        return "share_first"
    minute = current.hour * 60 + current.minute
    if LATE_SHARE_START_MINUTE <= minute < LATE_SHARE_END_MINUTE:
        return "share_retry"
    return None


def _late_share_bucket(now: datetime) -> int:
    minute = now.hour * 60 + now.minute
    return (minute - LATE_SHARE_START_MINUTE) // LATE_SHARE_BUCKET_MINUTES


def _has_complete_share_snapshot(snapshot: object, trade_date: str) -> bool:
    if getattr(snapshot, "trade_date", None) != trade_date:
        return False
    items = getattr(snapshot, "items", None)
    if not isinstance(items, list) or len(items) != EXPECTED_CORE_ETF_COUNT:
        return False
    return all(
        getattr(item, "share_change_pct", None) is not None
        and getattr(getattr(item, "share_factor", None), "status", None) == "available"
        for item in items
    )


class EtfThreeFactorSampler(BackgroundLoopSampler):
    def __init__(
        self,
        *,
        scan: Callable[..., object],
        clock: Callable[[], datetime] | None = None,
        retry_seconds: float = 60,
        idle_seconds: float = 300,
    ) -> None:
        super().__init__(
            thread_name="etf-three-factor-sampler",
            clock=clock,
            retry_seconds=retry_seconds,
            idle_seconds=idle_seconds,
            event_factory=Event,
        )
        self._scan = scan
        self._completed_intraday_minutes: set[str] = set()
        self._completed_refreshes: set[str] = set()
        self._completed_share_dates: set[str] = set()
        self._sample_lock = Lock()

    def sample_once(self) -> bool:
        current = _local_now(self._clock())
        kind = _scan_kind(current)
        if kind is None:
            return False
        key = current.strftime("%Y-%m-%dT%H:%M")
        trade_date = current.date().isoformat()
        with self._sample_lock:
            if kind in {"share_first", "share_retry"} and trade_date in self._completed_share_dates:
                return False
            completed = (
                self._completed_intraday_minutes
                if kind == "intraday"
                else self._completed_refreshes
            )
            completion_key = (
                f"{trade_date}:share_retry:{_late_share_bucket(current)}"
                if kind == "share_retry"
                else key if kind == "intraday"
                else f"{trade_date}:{kind}"
            )
            if completion_key in completed:
                return False
            result = (
                self._scan(now=current, force=True)
                if kind in {"share_first", "share_retry"}
                else self._scan(now=current)
            )
            completed.add(completion_key)
            if kind in {"share_first", "share_retry"} and _has_complete_share_snapshot(
                result, trade_date
            ):
                self._completed_share_dates.add(trade_date)
            return True

    def _wait_seconds(self, sampled: bool) -> float:
        return self._retry_seconds if sampled else min(self._idle_seconds, 60)
