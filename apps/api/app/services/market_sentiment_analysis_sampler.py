from __future__ import annotations

import logging
from datetime import date, datetime, time
from threading import Event, Lock, Thread
from typing import Callable
from zoneinfo import ZoneInfo

from app.models import SentimentPercentileAnalysisResponse


SHANGHAI = ZoneInfo("Asia/Shanghai")
GENERATION_CUTOFF = time(15, 15)
logger = logging.getLogger(__name__)


class MarketSentimentAnalysisSampler:
    def __init__(
        self,
        *,
        latest_completed_trade_date: Callable[[datetime], str | None],
        generate_latest: Callable[[datetime], SentimentPercentileAnalysisResponse | None],
        clock: Callable[[], datetime] | None = None,
        poll_seconds: float = 300,
    ) -> None:
        self._latest_completed_trade_date = latest_completed_trade_date
        self._generate_latest = generate_latest
        self._clock = clock or (lambda: datetime.now(SHANGHAI))
        self._poll_seconds = poll_seconds
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
                        name="market-sentiment-analysis-sampler",
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
        trade_date = self._latest_completed_trade_date(current)
        if trade_date is None or not is_generation_due(current, trade_date):
            return False

        with self._sample_lock:
            response = self._generate_latest(current)
            if response is None:
                return True
            return True

    def _run(self, stop_event: Event | None = None) -> None:
        active_stop_event = stop_event or self._stop_event
        while not active_stop_event.wait(self._poll_seconds):
            try:
                self.sample_once()
            except Exception:
                logger.exception("market sentiment analysis sampling failed")


def _local_now(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=SHANGHAI)
    return value.astimezone(SHANGHAI)


def is_generation_due(current: datetime, trade_date: str) -> bool:
    try:
        target_date = date.fromisoformat(trade_date)
    except ValueError:
        return False
    if target_date < current.date():
        return True
    if target_date > current.date() or current.weekday() >= 5:
        return False
    return current.timetz().replace(tzinfo=None) >= GENERATION_CUTOFF
