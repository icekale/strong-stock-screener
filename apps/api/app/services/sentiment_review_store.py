from __future__ import annotations

from pathlib import Path

from app.models import SentimentDecisionResponse
from app.services.json_file_store import JsonFileStore


class SentimentReviewStore(JsonFileStore):
    """决策复盘存储：读改写并发安全，写入采用临时文件 + 原子替换。"""

    def __init__(self, data_dir: Path) -> None:
        super().__init__()
        self.root = data_dir / "sentiment_reviews"
        self.root.mkdir(parents=True, exist_ok=True)

    def save_decision(self, decision: SentimentDecisionResponse) -> None:
        with self._lock:
            path = self.root / f"{decision.trade_date}.jsonl"
            existing = [
                item
                for item in self.load_decisions(decision.trade_date)
                if item.generated_at != decision.generated_at
            ]
            existing.append(decision)
            self.write_text(
                path,
                "\n".join(item.model_dump_json() for item in existing) + "\n",
            )

    def load_decisions(self, trade_date: str) -> list[SentimentDecisionResponse]:
        with self._lock:
            path = self.root / f"{trade_date}.jsonl"
            if not path.exists():
                return []
            return [
                SentimentDecisionResponse.model_validate_json(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
