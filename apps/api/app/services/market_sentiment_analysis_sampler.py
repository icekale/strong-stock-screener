from __future__ import annotations

from datetime import date, datetime, time
from threading import Event, Lock
from typing import Callable
from zoneinfo import ZoneInfo

from app.models import SentimentPercentileAnalysisResponse
from app.services.background_sampler import BackgroundLoopSampler
from app.services.trading_calendar import is_open_session


SHANGHAI = ZoneInfo("Asia/Shanghai")
GENERATION_CUTOFF = time(15, 15)


class MarketSentimentAnalysisSampler(BackgroundLoopSampler):
    def __init__(
        self,
        *,
        latest_completed_trade_date: Callable[[datetime], str | None],
        generate_latest: Callable[[datetime], SentimentPercentileAnalysisResponse | None],
        clock: Callable[[], datetime] | None = None,
        poll_seconds: float = 300,
    ) -> None:
        super().__init__(
            thread_name="market-sentiment-analysis-sampler",
            clock=clock,
            poll_seconds=poll_seconds,
            event_factory=Event,
            error_message="market sentiment analysis sampling failed",
        )
        self._latest_completed_trade_date = latest_completed_trade_date
        self._generate_latest = generate_latest
        self._sample_lock = Lock()

    def sample_once(self) -> bool:
        current = _local_now(self._clock())
        trade_date = self._latest_completed_trade_date(current)
        if trade_date is None or not is_generation_due(current, trade_date):
            return False

        with self._sample_lock:
            self._generate_latest(current)
            return True


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
    if target_date > current.date() or not is_open_session(current.date()):
        return False
    return current.timetz().replace(tzinfo=None) >= GENERATION_CUTOFF
