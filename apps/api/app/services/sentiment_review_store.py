from __future__ import annotations

from pathlib import Path
from threading import RLock

from app.models import SentimentDecisionResponse


class SentimentReviewStore:
    """决策复盘存储：读改写并发安全，写入采用临时文件 + 原子替换。"""

    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir / "sentiment_reviews"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def save_decision(self, decision: SentimentDecisionResponse) -> None:
        with self._lock:
            path = self.root / f"{decision.trade_date}.jsonl"
            existing = [
                item
                for item in self.load_decisions(decision.trade_date)
                if item.generated_at != decision.generated_at
            ]
            existing.append(decision)
            _atomic_write_text(
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


def _atomic_write_text(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)
