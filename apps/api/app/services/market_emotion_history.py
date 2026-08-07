from __future__ import annotations
from app.services.common import sample_from_snapshot as _sample_from_snapshot

from pathlib import Path
from threading import RLock

from app.models import MarketEmotionSample, MarketEmotionSnapshotResponse

# 裁剪节流：文件行数超过保留上限的该倍率时才全量重写，避免每次 append 都 O(n) 重写。
_PRUNE_SLACK_FACTOR = 1.5


class MarketEmotionHistoryStore:
    def __init__(
        self,
        data_dir: Path,
        retention_days: int | None = None,
        samples_per_day: int | None = None,
    ) -> None:
        self.root_dir = data_dir / "market_emotion"
        self.retention_days = retention_days
        self.samples_per_day = samples_per_day
        self._lock = RLock()

    def path_for(self, trade_date: str) -> Path:
        safe_trade_date = trade_date.replace("/", "-").replace("..", "")
        return self.root_dir / f"{safe_trade_date}.jsonl"

    def append(self, snapshot: MarketEmotionSnapshotResponse) -> MarketEmotionSample:
        with self._lock:
            sample = _sample_from_snapshot(snapshot)
            path = self.path_for(snapshot.trade_date)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(sample.model_dump_json())
                handle.write("\n")
            self._prune_samples(path)
            self._prune_days()
            return sample

    def load(self, trade_date: str, limit: int = 240) -> list[MarketEmotionSample]:
        with self._lock:
            path = self.path_for(trade_date)
            if not path.exists():
                return []
            samples: list[MarketEmotionSample] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                text = line.strip()
                if not text:
                    continue
                samples.append(MarketEmotionSample.model_validate_json(text))
            return samples[-limit:]

    def _prune_samples(self, path: Path) -> None:
        if self.samples_per_day is None or not path.exists():
            return
        keep_count = max(1, self.samples_per_day)
        prune_threshold = max(keep_count + 1, int(keep_count * _PRUNE_SLACK_FACTOR))
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(lines) <= prune_threshold:
            return
        path.write_text("\n".join(lines[-keep_count:]) + "\n", encoding="utf-8")

    def _prune_days(self) -> None:
        if self.retention_days is None or not self.root_dir.exists():
            return
        keep_days = max(1, self.retention_days)
        history_paths = sorted(self.root_dir.glob("*.jsonl"))
        for path in history_paths[:-keep_days]:
            try:
                path.unlink()
            except FileNotFoundError:
                continue


