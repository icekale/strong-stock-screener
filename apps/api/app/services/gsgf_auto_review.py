from __future__ import annotations

from datetime import datetime, time
from threading import Event, RLock, Thread
from typing import Callable
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field


class GsgfAutoReviewConfig(BaseModel):
    auto_snapshot_enabled: bool = True
    daily_review_enabled: bool = True
    daily_review_time: str = "15:40"
    weekly_calibration_enabled: bool = True
    weekly_calibration_weekday: int = Field(default=5, ge=1, le=7)
    weekly_calibration_time: str = "16:10"
    weekly_calibration_trade_days: int = Field(default=5, ge=1, le=20)
    weekly_calibration_scan_limit: int = Field(default=80, ge=1, le=300)
    windows: list[int] = Field(default_factory=lambda: [1, 3, 5, 10])
    kline_count: int = Field(default=260, ge=70, le=260)
    notify_on_success: bool = True
    notify_on_degradation: bool = True


ReviewRunner = Callable[[], object]
CalibrationRunner = Callable[[list[str], list[int], int, int], object]
TradeDatesProvider = Callable[[int], list[str]]
Notifier = Callable[[str, str], object]
ConfigLoader = Callable[[], GsgfAutoReviewConfig]
NowFactory = Callable[[], datetime]


class GsgfAutoReviewService:
    def __init__(
        self,
        *,
        config_loader: ConfigLoader,
        review_runner: ReviewRunner,
        calibration_runner: CalibrationRunner,
        recent_trade_dates: TradeDatesProvider,
        notifier: Notifier,
        now_fn: NowFactory | None = None,
    ) -> None:
        self._config_loader = config_loader
        self._review_runner = review_runner
        self._calibration_runner = calibration_runner
        self._recent_trade_dates = recent_trade_dates
        self._notifier = notifier
        self._now = now_fn or _now
        self._lock = RLock()
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._last_daily_review_key: str | None = None
        self._last_weekly_calibration_key: str | None = None

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = Thread(target=self._loop, name="gsgf-auto-review", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._stop_event.set()
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)

    def run_once(self) -> None:
        config = self._config_loader()
        now = _normalize_now(self._now())
        if config.daily_review_enabled and _is_after_time(now, config.daily_review_time):
            self._run_daily_review_once(now)
        if (
            config.weekly_calibration_enabled
            and now.isoweekday() == config.weekly_calibration_weekday
            and _is_after_time(now, config.weekly_calibration_time)
        ):
            self._run_weekly_calibration_once(now, config)

    def _run_daily_review_once(self, now: datetime) -> None:
        key = now.date().isoformat()
        with self._lock:
            if self._last_daily_review_key == key:
                return
            self._last_daily_review_key = key
        self._review_runner()

    def _run_weekly_calibration_once(self, now: datetime, config: GsgfAutoReviewConfig) -> None:
        year, week, _weekday = now.isocalendar()
        key = f"{year}-W{week:02d}"
        with self._lock:
            if self._last_weekly_calibration_key == key:
                return
            self._last_weekly_calibration_key = key
        trade_dates = self._recent_trade_dates(config.weekly_calibration_trade_days)
        if trade_dates:
            self._calibration_runner(
                trade_dates,
                config.windows,
                config.weekly_calibration_scan_limit,
                config.kline_count,
            )

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self.run_once()
            self._stop_event.wait(30)


def _normalize_now(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return now.astimezone(ZoneInfo("Asia/Shanghai"))


def _is_after_time(now: datetime, value: str) -> bool:
    target = _parse_time(value)
    return now.time() >= target


def _parse_time(value: str) -> time:
    hour_text, minute_text = value.split(":", 1)
    return time(max(0, min(int(hour_text), 23)), max(0, min(int(minute_text), 59)))


def _now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Shanghai"))
