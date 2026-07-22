from __future__ import annotations

from datetime import date
from pathlib import Path
from threading import RLock

from pydantic import ValidationError

from app.models import SentimentPercentileAnalysisResponse


class MarketSentimentAnalysisStore:
    def __init__(self, data_dir: Path) -> None:
        self.root_dir = data_dir / "sentiment-percentile" / "analysis"
        self._lock = RLock()

    def record_path(self, trade_date: str) -> Path:
        parsed_date = date.fromisoformat(trade_date)
        if parsed_date.isoformat() != trade_date:
            raise ValueError("trade_date must use YYYY-MM-DD")
        return self.root_dir / f"{trade_date}.json"

    def load(self, trade_date: str) -> SentimentPercentileAnalysisResponse | None:
        try:
            path = self.record_path(trade_date)
        except ValueError:
            return None
        with self._lock:
            if not path.exists():
                return None
            try:
                return SentimentPercentileAnalysisResponse.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
            except (UnicodeError, ValidationError):
                return None

    def save(
        self,
        value: SentimentPercentileAnalysisResponse,
    ) -> SentimentPercentileAnalysisResponse:
        path = self.record_path(value.trade_date)
        with self._lock:
            self.root_dir.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(value.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(path)
        return value
