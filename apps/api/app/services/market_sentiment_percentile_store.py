from __future__ import annotations

from pathlib import Path
from threading import RLock

from app.models import SentimentPercentileResponse
from app.services.market_sentiment_percentile import MODEL_VERSION


class MarketSentimentPercentileStore:
    def __init__(self, data_dir: Path) -> None:
        self.root_dir = data_dir / "sentiment-percentile"
        self.latest_path = self.root_dir / "latest.json"
        self._lock = RLock()

    def load(self) -> SentimentPercentileResponse | None:
        with self._lock:
            if not self.latest_path.exists():
                return None
            try:
                value = SentimentPercentileResponse.model_validate_json(
                    self.latest_path.read_text(encoding="utf-8")
                )
            except Exception:
                return None
            return value if value.model_version == MODEL_VERSION else None

    def save(self, value: SentimentPercentileResponse) -> SentimentPercentileResponse:
        with self._lock:
            self.root_dir.mkdir(parents=True, exist_ok=True)
            temporary = self.latest_path.with_suffix(".json.tmp")
            temporary.write_text(value.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(self.latest_path)
            return value
