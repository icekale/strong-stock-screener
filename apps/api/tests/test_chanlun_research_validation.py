from __future__ import annotations

from dataclasses import replace
from datetime import date
from itertools import pairwise

import pytest

from app.services.chanlun.research_validation import (
    DailyOutcomeBar,
    DecisionPoint,
    FrozenValidationDataset,
    PromotionMetrics,
    build_outcome,
    _build_outcome_from_series,
    _build_outcome_series,
    build_walk_forward_folds,
    evaluate_promotion,
    validate_frozen_dataset,
    summarize_returns,
)


def test_five_year_windows_use_24_6_6_and_never_overlap_forward() -> None:
    folds = build_walk_forward_folds(date(2021, 7, 1), date(2026, 6, 30))

    assert folds[0].development_months == 24
    assert folds[0].validation_months == 6
    assert folds[0].test_months == 6
    assert all(
        fold.development_end < fold.validation_start <= fold.validation_end < fold.test_start
        for fold in folds
    )
    assert all(left.test_start < right.test_start for left, right in pairwise(folds))


def test_sample_builder_enters_next_open_and_exits_third_close() -> None:
    sample = build_outcome(DecisionPoint(symbol="600000.SH", decision_date="2026-07-06"), _future_daily_bars())

    assert sample.entry_at == "2026-07-07T09:30:00+08:00"
    assert sample.exit_at == "2026-07-09T15:00:00+08:00"
    assert sample.net_return_pct == pytest.approx(sample.gross_return_pct - 0.20)


def test_outcome_series_selects_future_bars_from_unsorted_history() -> None:
    series = _build_outcome_series(list(reversed(_future_daily_bars())))

    sample = _build_outcome_from_series(
        DecisionPoint(symbol="600000.SH", decision_date="2026-07-06"),
        series,
    )

    assert sample.entry_at == "2026-07-07T09:30:00+08:00"
    assert sample.exit_at == "2026-07-09T15:00:00+08:00"


def test_untradeable_one_price_limit_up_is_recorded_as_unfilled() -> None:
    sample = build_outcome(
        DecisionPoint(symbol="600000.SH", decision_date="2026-07-06"),
        [
            DailyOutcomeBar("2026-07-07", 11, 11, 11, 11),
            DailyOutcomeBar("2026-07-08", 11, 11.5, 10.8, 11.2),
            DailyOutcomeBar("2026-07-09", 11.2, 11.6, 11, 11.4),
        ],
    )

    assert sample.filled is False
    assert sample.net_return_pct is None


def test_profit_loss_ratio_uses_average_win_over_absolute_average_loss() -> None:
    metrics = summarize_returns([3.0, 1.0, -1.0, -1.0])

    assert metrics.win_rate_pct == 50.0
    assert metrics.profit_loss_ratio == 2.0


def test_promotion_requires_every_approved_gate() -> None:
    decision = evaluate_promotion(_passing_metrics())
    assert decision.recommendation == "suggest_promotion"

    for field in [
        "sample_count",
        "win_rate_pct",
        "profit_loss_ratio",
        "excess_return_pct",
        "max_drawdown_pct",
        "recent_decay_pct",
        "leakage_passed",
    ]:
        assert evaluate_promotion(_failing_metrics(field)).recommendation == "keep_shadow"


def test_frozen_validation_compares_baseline_and_v2_top3_top5_top10() -> None:
    dataset = FrozenValidationDataset(
        candidates_by_date={
            "2026-07-06": [
                {"symbol": "600000.SH", "baseline_rank": 1},
                {"symbol": "000001.SZ", "baseline_rank": 2},
                {"symbol": "300001.SZ", "baseline_rank": 3},
                {"symbol": "600002.SH", "baseline_rank": 4},
            ],
        },
        daily_bars_by_symbol={
            "600000.SH": [
                DailyOutcomeBar("2026-07-07", 10, 10.5, 9.8, 10.2),
                DailyOutcomeBar("2026-07-08", 10.2, 10.8, 10, 10.6),
                DailyOutcomeBar("2026-07-09", 10.6, 11, 10.4, 10.8),
            ],
            "000001.SZ": [
                DailyOutcomeBar("2026-07-07", 10, 10.1, 9.5, 9.7),
                DailyOutcomeBar("2026-07-08", 9.7, 9.8, 9.2, 9.3),
                DailyOutcomeBar("2026-07-09", 9.3, 9.5, 9.0, 9.1),
            ],
            "300001.SZ": [
                DailyOutcomeBar("2026-07-07", 10, 10.4, 9.9, 10.1),
                DailyOutcomeBar("2026-07-08", 10.1, 10.7, 10.0, 10.5),
                DailyOutcomeBar("2026-07-09", 10.5, 11.2, 10.3, 11.0),
            ],
            "600002.SH": [
                DailyOutcomeBar("2026-07-07", 10, 10.3, 10, 10.2),
                DailyOutcomeBar("2026-07-08", 10.2, 10.7, 10.1, 10.6),
                DailyOutcomeBar("2026-07-09", 10.6, 11.4, 10.5, 11.2),
            ],
        },
    )

    result = validate_frozen_dataset(
        dataset,
        decision_dates=["2026-07-06"],
        score_candidate=lambda candidate: {
            "600000.SH": (30, True),
            "000001.SZ": (90, True),
            "300001.SZ": (80, True),
            "600002.SH": (95, True),
        }[candidate["symbol"]],
    )

    assert set(result.portfolios) == {"top3", "top5", "top10"}
    assert result.portfolios["top3"].v2_net_return_pct > result.portfolios["top3"].baseline_net_return_pct
    assert result.samples[0]["v2_rank"] == 1
    assert result.leakage_passed is True


def _future_daily_bars() -> list[DailyOutcomeBar]:
    return [
        DailyOutcomeBar("2026-07-07", 10, 10.5, 9.8, 10.2),
        DailyOutcomeBar("2026-07-08", 10.2, 10.8, 10, 10.6),
        DailyOutcomeBar("2026-07-09", 10.6, 11, 10.4, 10.8),
    ]


def _passing_metrics() -> PromotionMetrics:
    return PromotionMetrics(
        sample_count=300,
        win_rate_pct=55,
        profit_loss_ratio=1.5,
        baseline_top5_net_return_pct=10,
        v2_top5_net_return_pct=12,
        baseline_top10_net_return_pct=13,
        v2_top10_net_return_pct=15,
        baseline_top5_max_drawdown_pct=-10,
        v2_top5_max_drawdown_pct=-9,
        baseline_top10_max_drawdown_pct=-12,
        v2_top10_max_drawdown_pct=-11,
        recent_six_month_return_pct=3,
        recent_decay_pct=-3,
        leakage_passed=True,
    )


def _failing_metrics(field: str) -> PromotionMetrics:
    passing = _passing_metrics()
    values = {
        "sample_count": 299,
        "win_rate_pct": 50,
        "profit_loss_ratio": 1.2,
        "excess_return_pct": -1,
        "max_drawdown_pct": -2,
        "recent_decay_pct": -6,
        "leakage_passed": False,
    }
    if field == "excess_return_pct":
        return replace(passing, v2_top5_net_return_pct=9, v2_top10_net_return_pct=15)
    if field == "max_drawdown_pct":
        return replace(passing, v2_top5_max_drawdown_pct=-11)
    return replace(passing, **{field: values[field]})
