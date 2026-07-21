import pytest

from app.models import EtfFactorEvidence, EtfThreeFactorItem
from app.services.etf_three_factor import (
    INDEX_SYMBOL_BY_ETF,
    combine_factor_scores,
    direction_factor_score,
    share_factor_score,
    signal_level,
    summarize_three_factor,
    volume_factor_score,
)


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [(3.0, 100), (2.5, 85), (2.0, 70), (1.5, 50), (1.4999, 0), (None, None)],
)
def test_volume_factor_score_boundaries(ratio, expected):
    assert volume_factor_score(ratio) == expected


@pytest.mark.parametrize(
    ("etf", "index", "expected"),
    [
        (1, -1, 100),
        (1, 1, 70),
        (-1, 1, 20),
        (-1, -1, 0),
        (None, 1, None),
        (1, None, None),
    ],
)
def test_direction_factor_score_matrix(etf, index, expected):
    assert direction_factor_score(etf, index) == expected


@pytest.mark.parametrize(
    ("change", "expected"),
    [(5.0, 100), (3.0, 80), (1.0, 60), (0.9999, 0), (0.0, 0), (-1.0, 0), (None, None)],
)
def test_share_factor_score_boundaries(change, expected):
    assert share_factor_score(change) == expected


def test_intraday_two_factor_mode_uses_70_30_weights():
    score, mode = combine_factor_scores(100, 70, None, share_pending=True)
    assert score == 91
    assert mode == "two_factor"


def test_full_mode_uses_50_20_30_weights():
    score, mode = combine_factor_scores(100, 70, 60, share_pending=False)
    assert score == 82
    assert mode == "three_factor"


def test_missing_share_score_is_incomplete_when_share_is_not_pending():
    score, mode = combine_factor_scores(100, 70, None, share_pending=False)
    assert score is None
    assert mode == "incomplete"


def test_non_share_failure_does_not_renormalize_one_factor():
    score, mode = combine_factor_scores(100, None, None, share_pending=True)
    assert score is None
    assert mode == "incomplete"


@pytest.mark.parametrize(
    ("score", "expected"),
    [(None, "incomplete"), (49.99, "low"), (50, "medium"), (69.99, "medium"), (70, "high")],
)
def test_signal_level_boundaries(score, expected):
    assert signal_level(score) == expected


def _item(score, level=None):
    return EtfThreeFactorItem(
        symbol="510050.SH",
        name="ETF",
        index_name="上证50",
        index_symbol="000016.SH",
        volume_factor=EtfFactorEvidence(status="available", source="test"),
        direction_factor=EtfFactorEvidence(status="available", source="test"),
        share_factor=EtfFactorEvidence(status="available", source="test"),
        signal_score=score,
        mode="three_factor",
        level=level or signal_level(score),
        updated_at="2026-07-22T10:00:00+08:00",
    )


def test_summary_is_incomplete_with_fewer_than_five_valid_items():
    summary = summarize_three_factor([_item(80), _item(None)])
    assert summary.signal_score == 80
    assert summary.valid_count == 1
    assert summary.high_count == 1
    assert summary.market_state == "incomplete"


def test_summary_is_high_with_average_70_and_five_high_items():
    summary = summarize_three_factor([_item(70) for _ in range(5)])
    assert summary.signal_score == 70
    assert summary.level == "high"
    assert summary.valid_count == 5
    assert summary.high_count == 5
    assert summary.market_state == "high"


def test_summary_is_watch_with_average_50_and_three_high_items():
    summary = summarize_three_factor([_item(70) for _ in range(3)] + [_item(20), _item(20)])
    assert summary.signal_score == 50
    assert summary.high_count == 3
    assert summary.medium_count == 0
    assert summary.market_state == "watch"


def test_summary_is_watch_with_high_average_but_fewer_than_five_high_items():
    summary = summarize_three_factor([_item(100) for _ in range(4)] + [_item(40)])
    assert summary.signal_score == 88
    assert summary.high_count == 4
    assert summary.market_state == "watch"


def test_summary_is_normal_with_watch_average_but_fewer_than_three_high_items():
    summary = summarize_three_factor([_item(100) for _ in range(2)] + [_item(40) for _ in range(3)])
    assert summary.signal_score == 64
    assert summary.high_count == 2
    assert summary.market_state == "normal"


def test_summary_is_normal_when_valid_but_below_watch_threshold():
    summary = summarize_three_factor([_item(40) for _ in range(5)])
    assert summary.level == "low"
    assert summary.market_state == "normal"


def test_index_mapping_contains_the_seven_core_etfs():
    assert len(INDEX_SYMBOL_BY_ETF) == 7
    assert INDEX_SYMBOL_BY_ETF["510300.SH"] == "000300.SH"
