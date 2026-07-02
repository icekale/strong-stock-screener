from __future__ import annotations

from pathlib import Path

from app.models import SentimentDecisionResponse


class SentimentReviewStore:
    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir / "sentiment_reviews"
        self.root.mkdir(parents=True, exist_ok=True)

    def save_decision(self, decision: SentimentDecisionResponse) -> None:
        path = self.root / f"{decision.trade_date}.jsonl"
        existing = [
            item
            for item in self.load_decisions(decision.trade_date)
            if item.generated_at != decision.generated_at
        ]
        existing.append(decision)
        path.write_text(
            "\n".join(item.model_dump_json() for item in existing) + "\n",
            encoding="utf-8",
        )

    def load_decisions(self, trade_date: str) -> list[SentimentDecisionResponse]:
        path = self.root / f"{trade_date}.jsonl"
        if not path.exists():
            return []
        return [
            SentimentDecisionResponse.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
