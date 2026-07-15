from __future__ import annotations

from pathlib import Path

import pytest

from app.services.chanlun.research_score_cache import (
    ResearchScoreCache,
    ResearchScoreRecord,
    apply_score_cache_gate,
    derive_scoreable_universe,
    pending_score_keys,
    score_cache_coverage,
)


def test_score_cache_resumes_and_overwrites_by_candidate_key(tmp_path: Path) -> None:
    path = tmp_path / "scores.json"
    cache = ResearchScoreCache(path, dataset_id="sha256:dataset")
    cache.save_many(
        [
            ResearchScoreRecord("600000.SH", "2026-07-01", 70, True),
            ResearchScoreRecord("000001.SZ", "2026-07-01", None, False),
        ]
    )
    cache.save_many([ResearchScoreRecord("600000.SH", "2026-07-01", 82, True)])

    loaded = cache.load()

    assert loaded[("600000.SH", "2026-07-01")].score == 82
    assert loaded[("000001.SZ", "2026-07-01")].score is None
    assert cache.completed_keys() == {
        ("600000.SH", "2026-07-01"),
        ("000001.SZ", "2026-07-01"),
    }


def test_score_cache_rejects_a_different_dataset(tmp_path: Path) -> None:
    path = tmp_path / "scores.json"
    ResearchScoreCache(path, dataset_id="sha256:first").save_many(
        [ResearchScoreRecord("600000.SH", "2026-07-01", 70, True)]
    )

    with pytest.raises(ValueError, match="dataset ID"):
        ResearchScoreCache(path, dataset_id="sha256:second").load()


def test_pending_score_keys_are_deterministic_and_skip_completed() -> None:
    samples = [
        ("600001.SH", "2026-07-02"),
        ("600000.SH", "2026-07-01"),
        ("000001.SZ", "2026-07-01"),
    ]

    selected = pending_score_keys(
        samples,
        completed_keys={("600000.SH", "2026-07-01")},
        limit=1,
    )

    assert selected == [("600001.SH", "2026-07-02")]


def test_partial_score_cache_is_labeled_and_cannot_promote() -> None:
    coverage = score_cache_coverage(completed_count=3, scored_count=1, total_count=3)

    recommendation, failed_gates = apply_score_cache_gate(
        recommendation="suggest_promotion",
        failed_gates=(),
        coverage=coverage,
    )

    assert coverage.status == "score_cache_partial"
    assert coverage.completed_count == 3
    assert coverage.scored_count == 1
    assert coverage.ratio == pytest.approx(1 / 3)
    assert recommendation == "keep_shadow"
    assert failed_gates == ("score_cache_coverage",)


def test_complete_score_cache_preserves_promotion_result() -> None:
    coverage = score_cache_coverage(completed_count=3, scored_count=3, total_count=3)

    recommendation, failed_gates = apply_score_cache_gate(
        recommendation="suggest_promotion",
        failed_gates=(),
        coverage=coverage,
    )

    assert coverage.status == "score_cache_complete"
    assert recommendation == "suggest_promotion"
    assert failed_gates == ()


def test_scoreable_universe_uses_each_symbols_minute_warmup_window() -> None:
    universe = derive_scoreable_universe(
        samples=[
            ("600000.SH", "2026-04-30"),
            ("600000.SH", "2026-05-01"),
            ("000001.SZ", "2026-07-01"),
            ("300001.SZ", "2026-06-01"),
        ],
        partitions=[
            {
                "path": "minute/symbol=600000_SH/month=2026-01.parquet",
                "start_date": "2026-01-01",
                "end_date": "2026-07-03",
            },
            {
                "path": "minute/symbol=000001_SZ/month=2026-03.parquet",
                "start_date": "2026-03-17",
                "end_date": "2026-07-03",
            },
        ],
        warmup_days=120,
    )

    assert universe.keys == frozenset({("600000.SH", "2026-05-01")})
    assert universe.start_date == "2026-05-01"
    assert universe.end_date == "2026-05-01"
    assert universe.dataset_candidate_count == 4
