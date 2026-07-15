from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
import json
from pathlib import Path
from typing import Mapping, Sequence


SCORE_CACHE_SCHEMA_VERSION = "czsc-research-score-cache-v1"


@dataclass(frozen=True)
class ResearchScoreRecord:
    symbol: str
    decision_date: str
    score: int | None
    eligible: bool

    @property
    def key(self) -> tuple[str, str]:
        return self.symbol, self.decision_date


@dataclass(frozen=True)
class ResearchScoreCoverage:
    completed_count: int
    scored_count: int
    total_count: int
    ratio: float
    status: str


@dataclass(frozen=True)
class ResearchScoreableUniverse:
    keys: frozenset[tuple[str, str]]
    start_date: str | None
    end_date: str | None
    dataset_candidate_count: int


class ResearchScoreCache:
    def __init__(self, path: Path, *, dataset_id: str) -> None:
        self.path = path
        self.dataset_id = dataset_id

    def load(self) -> dict[tuple[str, str], ResearchScoreRecord]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != SCORE_CACHE_SCHEMA_VERSION:
            raise ValueError("research score cache schema version mismatch")
        if payload.get("dataset_id") != self.dataset_id:
            raise ValueError("research score cache dataset ID mismatch")
        records = [ResearchScoreRecord(**item) for item in payload.get("scores", [])]
        return {record.key: record for record in records}

    def completed_keys(self) -> set[tuple[str, str]]:
        return set(self.load())

    def save_many(self, records: list[ResearchScoreRecord]) -> None:
        merged = self.load()
        merged.update((record.key, record) for record in records)
        ordered = sorted(
            merged.values(),
            key=lambda record: (record.decision_date, record.symbol),
        )
        payload = {
            "schema_version": SCORE_CACHE_SCHEMA_VERSION,
            "dataset_id": self.dataset_id,
            "scores": [asdict(record) for record in ordered],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


def pending_score_keys(
    samples: list[tuple[str, str]],
    *,
    completed_keys: set[tuple[str, str]],
    limit: int,
) -> list[tuple[str, str]]:
    if limit < 1:
        raise ValueError("score batch limit must be at least 1")
    ordered = sorted(set(samples), key=lambda item: item[0])
    ordered.sort(key=lambda item: item[1], reverse=True)
    return [
        key
        for key in ordered
        if key not in completed_keys
    ][:limit]


def derive_scoreable_universe(
    *,
    samples: Sequence[tuple[str, str]],
    partitions: Sequence[Mapping[str, object]],
    warmup_days: int = 120,
) -> ResearchScoreableUniverse:
    if warmup_days < 0:
        raise ValueError("minute warmup days must not be negative")
    minute_ranges: dict[str, tuple[date, date]] = {}
    for partition in partitions:
        symbol = _minute_partition_symbol(str(partition.get("path", "")))
        start = _date_or_none(partition.get("start_date"))
        end = _date_or_none(partition.get("end_date"))
        if symbol is None or start is None or end is None:
            continue
        current = minute_ranges.get(symbol)
        minute_ranges[symbol] = (
            min(start, current[0]) if current else start,
            max(end, current[1]) if current else end,
        )

    unique_samples = set(samples)
    selected = frozenset(
        (symbol, decision_date)
        for symbol, decision_date in unique_samples
        if (coverage := minute_ranges.get(symbol)) is not None
        and (decision := _date_or_none(decision_date)) is not None
        and coverage[0] + timedelta(days=warmup_days) <= decision <= coverage[1]
    )
    selected_dates = sorted(decision_date for _, decision_date in selected)
    return ResearchScoreableUniverse(
        keys=selected,
        start_date=selected_dates[0] if selected_dates else None,
        end_date=selected_dates[-1] if selected_dates else None,
        dataset_candidate_count=len(unique_samples),
    )


def _minute_partition_symbol(path: str) -> str | None:
    for part in Path(path).parts:
        if part.startswith("symbol="):
            return part.removeprefix("symbol=").replace("_", ".").upper()
    return None


def _date_or_none(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def score_cache_coverage(
    *,
    completed_count: int,
    scored_count: int,
    total_count: int,
) -> ResearchScoreCoverage:
    bounded_completed = max(0, min(completed_count, total_count))
    bounded_scored = max(0, min(scored_count, bounded_completed))
    ratio = bounded_scored / total_count if total_count else 1.0
    return ResearchScoreCoverage(
        completed_count=bounded_completed,
        scored_count=bounded_scored,
        total_count=max(0, total_count),
        ratio=ratio,
        status="score_cache_complete" if ratio == 1.0 else "score_cache_partial",
    )


def apply_score_cache_gate(
    *,
    recommendation: str,
    failed_gates: tuple[str, ...],
    coverage: ResearchScoreCoverage,
) -> tuple[str, tuple[str, ...]]:
    if coverage.status == "score_cache_complete":
        return recommendation, failed_gates
    return "keep_shadow", tuple(dict.fromkeys((*failed_gates, "score_cache_coverage")))
