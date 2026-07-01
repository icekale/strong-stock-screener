from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.models import StrongStockScreeningResult


class RunStore:
    def __init__(self, runs_dir: Path, retention_count: int | None = None) -> None:
        self.runs_dir = runs_dir
        self.retention_count = retention_count

    @property
    def latest_path(self) -> Path:
        return self.runs_dir / "latest.json"

    def save(self, result: StrongStockScreeningResult) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        payload = result.model_dump_json(indent=2)
        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d-%H%M%S-%f")
        (self.runs_dir / f"{timestamp}.json").write_text(payload, encoding="utf-8")
        self.latest_path.write_text(payload, encoding="utf-8")
        self._prune_history()

    def load_latest(self) -> StrongStockScreeningResult | None:
        if not self.latest_path.exists():
            return None
        return StrongStockScreeningResult.model_validate_json(
            self.latest_path.read_text(encoding="utf-8")
        )

    def _prune_history(self) -> None:
        if self.retention_count is None:
            return
        keep_count = max(1, self.retention_count)
        history_paths = sorted(
            path for path in self.runs_dir.glob("*.json") if path.name != self.latest_path.name
        )
        for path in history_paths[:-keep_count]:
            try:
                path.unlink()
            except FileNotFoundError:
                continue
