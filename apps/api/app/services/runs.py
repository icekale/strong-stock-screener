from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.models import StrongStockScreeningResult


class RunStore:
    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir

    @property
    def latest_path(self) -> Path:
        return self.runs_dir / "latest.json"

    def save(self, result: StrongStockScreeningResult) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        payload = result.model_dump_json(indent=2)
        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d-%H%M%S")
        (self.runs_dir / f"{timestamp}.json").write_text(payload, encoding="utf-8")
        self.latest_path.write_text(payload, encoding="utf-8")

    def load_latest(self) -> StrongStockScreeningResult | None:
        if not self.latest_path.exists():
            return None
        return StrongStockScreeningResult.model_validate_json(
            self.latest_path.read_text(encoding="utf-8")
        )

