from __future__ import annotations

import pytest

from app.services.capital_signals import (
    build_share_change,
    robust_z_score,
    synchronization_ratio,
)


def test_estimated_subscription_uses_share_delta_times_close() -> None:
    result = build_share_change(
        current_shares=12_000_000,
        previous_shares=10_000_000,
        close=4.25,
    )

    assert result.share_change == 2_000_000
    assert result.estimated_subscription_cny == 8_500_000


def test_missing_previous_shares_stays_missing_instead_of_zero() -> None:
    result = build_share_change(
        current_shares=12_000_000,
        previous_shares=None,
        close=4.25,
    )

    assert result.share_change is None
    assert result.estimated_subscription_cny is None


def test_missing_close_keeps_subscription_amount_missing() -> None:
    result = build_share_change(
        current_shares=12_000_000,
        previous_shares=10_000_000,
        close=None,
    )

    assert result.share_change == 2_000_000
    assert result.estimated_subscription_cny is None


def test_robust_score_uses_median_absolute_deviation() -> None:
    assert robust_z_score(16, [9, 10, 10, 11, 12]) == pytest.approx(4.047, rel=1e-3)


def test_robust_score_is_missing_when_history_has_no_dispersion() -> None:
    assert robust_z_score(11, [10, 10, 10]) is None


def test_synchronization_excludes_missing_etfs_from_denominator() -> None:
    result = synchronization_ratio([True, False, None, True])

    assert result.positive_count == 2
    assert result.valid_count == 3
    assert result.ratio == pytest.approx(2 / 3)


def test_synchronization_is_missing_without_valid_etfs() -> None:
    result = synchronization_ratio([None, None])

    assert result.positive_count == 0
    assert result.valid_count == 0
    assert result.ratio is None
