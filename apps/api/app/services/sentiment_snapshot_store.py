from __future__ import annotations

from pathlib import Path
from shutil import rmtree
from threading import RLock

from app.models import (
    MarketEmotionSnapshotResponse,
    SentimentSummaryResponse,
    ShortTermSentimentResponse,
    StrongStockSourceStatus,
)
from app.services.short_term_sentiment import build_sentiment_summary


_SNAPSHOT_IO_LOCK = RLock()


class SentimentSnapshotStore:
    def __init__(self, data_dir: Path, retention_days: int | None = None) -> None:
        self.root_dir = data_dir / "sentiment_snapshots"
        self.retention_days = retention_days

    def save(
        self,
        sentiment: ShortTermSentimentResponse,
        market_emotion: MarketEmotionSnapshotResponse,
    ) -> SentimentSummaryResponse:
        with _SNAPSHOT_IO_LOCK:
            trade_date = sentiment.trade_date
            date_dir = self._date_dir(trade_date)
            date_dir.mkdir(parents=True, exist_ok=True)
            summary = build_sentiment_summary(
                sentiment,
                market_emotion,
                snapshot_status="cached",
                cached_at=market_emotion.generated_at,
            )
            _write_model(date_dir / "summary.json", summary)
            _write_model(date_dir / "sentiment.json", sentiment)
            _write_model(date_dir / "market_emotion.json", market_emotion)
            self._prune_trade_dates()
            return summary

    def load_summary(self, trade_date: str) -> SentimentSummaryResponse | None:
        with _SNAPSHOT_IO_LOCK:
            path = self._date_dir(trade_date) / "summary.json"
            summary = self._load_model(path, SentimentSummaryResponse)
            if summary is None:
                return None
            deduped_status = _dedupe_source_status(summary.source_status)
            if len(deduped_status) != len(summary.source_status):
                summary = summary.model_copy(update={"source_status": deduped_status})
                _write_model(path, summary)
            return summary

    def load_sentiment(self, trade_date: str) -> ShortTermSentimentResponse | None:
        with _SNAPSHOT_IO_LOCK:
            return self._load_model(
                self._date_dir(trade_date) / "sentiment.json",
                ShortTermSentimentResponse,
            )

    def load_market_emotion(self, trade_date: str) -> MarketEmotionSnapshotResponse | None:
        with _SNAPSHOT_IO_LOCK:
            return self._load_model(
                self._date_dir(trade_date) / "market_emotion.json",
                MarketEmotionSnapshotResponse,
            )

    def _date_dir(self, trade_date: str) -> Path:
        safe_trade_date = trade_date.replace("/", "-").replace("..", "")
        return self.root_dir / safe_trade_date

    @staticmethod
    def _load_model(path: Path, model_cls):
        if not path.exists():
            return None
        try:
            return model_cls.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _prune_trade_dates(self) -> None:
        if self.retention_days is None or not self.root_dir.exists():
            return
        keep_days = max(1, self.retention_days)
        date_dirs = sorted(path for path in self.root_dir.iterdir() if path.is_dir())
        for path in date_dirs[:-keep_days]:
            rmtree(path, ignore_errors=True)


def _dedupe_source_status(items: list[StrongStockSourceStatus]) -> list[StrongStockSourceStatus]:
    output: list[StrongStockSourceStatus] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (item.source, item.status, item.detail)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _write_model(path: Path, model: object) -> None:
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    temp_path.replace(path)
