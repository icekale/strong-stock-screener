from __future__ import annotations

from datetime import datetime
from threading import Event, RLock
from typing import Callable
from zoneinfo import ZoneInfo

from app.services.background_sampler import BackgroundLoopSampler
from app.services.trading_calendar import is_open_session, local_date


def _local_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    if current.tzinfo is None:
        return current.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return current.astimezone(ZoneInfo("Asia/Shanghai"))


def _seconds_since_midnight(current: datetime) -> int:
    return current.hour * 3600 + current.minute * 60 + current.second


def is_trading_day(now: datetime | None = None) -> bool:
    return is_open_session(local_date(_local_now(now)))


def is_auction_sample_window(now: datetime | None = None) -> bool:
    current = _local_now(now)
    if not is_trading_day(current):
        return False
    seconds = _seconds_since_midnight(current)
    return (9 * 3600 + 14 * 60 + 30) <= seconds <= (9 * 3600 + 25 * 60 + 30)


def is_auction_top3_lock_window(now: datetime | None = None) -> bool:
    current = _local_now(now)
    if not is_trading_day(current):
        return False
    seconds = _seconds_since_midnight(current)
    return (9 * 3600 + 25 * 60 + 3) <= seconds < (9 * 3600 + 30 * 60)


class AuctionSnapshotSampler(BackgroundLoopSampler):
    def __init__(
        self,
        *,
        refresh: Callable[[], object],
        run_top3: Callable[[str], object] | None = None,
        clock: Callable[[], datetime] | None = None,
        interval_seconds: float = 5,
        idle_seconds: float = 30,
    ) -> None:
        super().__init__(
            thread_name="auction-snapshot-sampler",
            clock=clock,
            interval_seconds=interval_seconds,
            idle_seconds=idle_seconds,
            event_factory=Event,
        )
        self._refresh = refresh
        self._run_top3 = run_top3
        self._lock = RLock()
        self._top3_trade_dates: set[str] = set()
        self._last_top3_trade_date: str | None = None
        self._last_top3_status = "waiting"
        self._last_top3_error: str | None = None
        self._last_top3_at: str | None = None

    def sample_once(self) -> bool:
        now = self._clock()
        sampled = False
        if is_auction_sample_window(now):
            self._refresh()
            sampled = True
        generated = self._maybe_generate_top3(now)
        return sampled or generated

    def top3_status(self) -> dict[str, object]:
        with self._lock:
            return {
                "status": self._last_top3_status,
                "last_trade_date": self._last_top3_trade_date,
                "last_generated_at": self._last_top3_at,
                "last_error": self._last_top3_error,
                "generated_trade_dates": sorted(self._top3_trade_dates),
            }

    def _maybe_generate_top3(self, now: datetime) -> bool:
        if self._run_top3 is None or not is_auction_top3_lock_window(now):
            return False
        local = _local_now(now)
        trade_date = local.date().isoformat()
        with self._lock:
            if trade_date in self._top3_trade_dates:
                return False
            self._last_top3_trade_date = trade_date
            self._last_top3_status = "running"
            self._last_top3_error = None
        try:
            self._run_top3(trade_date)
        except Exception as exc:
            with self._lock:
                self._last_top3_status = "failed"
                self._last_top3_error = str(exc) or exc.__class__.__name__
            return True
        with self._lock:
            self._top3_trade_dates.add(trade_date)
            self._last_top3_status = "generated"
            self._last_top3_error = None
            self._last_top3_at = _local_now(now).isoformat(timespec="seconds")
        return True
