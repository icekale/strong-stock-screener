from __future__ import annotations

import operator
from collections.abc import Mapping

import pytest

from app.models import HuijinEtfActivityItem, HuijinEtfBaseline
from app.services.huijin_etf_activity import (
    ALL_ETFS,
    CORE_ETFS,
    VALIDATION_ETFS,
    EtfDefinition,
    calculate_activity,
    validate_pair,
)


def _baseline(
    *,
    symbol: str = "159915.SZ",
    total_shares: float = 31_500_000_000,
) -> HuijinEtfBaseline:
    return HuijinEtfBaseline(
        baseline_id="2026-q2-159915",
        pool_version="huijin-public-v1",
        symbol=symbol,
        name="创业板ETF易方达",
        index_name="创业板",
        role="core",
        paired_symbol=None,
        report_period="2026Q2",
        baseline_total_shares=total_shares,
        confirmed_huijin_shares=5_000_000_000,
        confirmed_huijin_holding_pct=15.873,
        source_kind="reported",
        source="基金定期报告",
    )


def _activity(
    *,
    symbol: str,
    direction: str,
    daily_change_pct: float | None,
    baseline_change_pct: float | None,
    multiple: float | None,
) -> HuijinEtfActivityItem:
    definition = ALL_ETFS[symbol]
    return HuijinEtfActivityItem(
        symbol=symbol,
        name=definition.name,
        index_name=definition.index_name,
        role=definition.role,
        paired_symbol=definition.paired_symbol,
        trade_date="2026-07-17",
        daily_change_pct=daily_change_pct,
        baseline_change_pct=baseline_change_pct,
        multiple=multiple,
        direction=direction,
    )


def test_public_pool_contains_exact_core_and_validator_symbols() -> None:
    assert tuple(CORE_ETFS) == (
        "510050.SH",
        "510300.SH",
        "510500.SH",
        "512100.SH",
        "159915.SZ",
        "510230.SH",
        "588080.SH",
    )
    assert tuple(VALIDATION_ETFS) == (
        "159919.SZ",
        "159922.SZ",
        "159845.SZ",
    )
    assert tuple(ALL_ETFS) == (*CORE_ETFS, *VALIDATION_ETFS)


@pytest.mark.parametrize("mapping", [CORE_ETFS, VALIDATION_ETFS, ALL_ETFS])
def test_exported_etf_mappings_are_immutable(
    mapping: Mapping[str, EtfDefinition],
) -> None:
    symbol = next(iter(mapping))

    with pytest.raises(TypeError):
        operator.setitem(mapping, symbol, mapping[symbol])


def test_calculate_activity_matches_2026_07_17_chinext_fixture() -> None:
    result = calculate_activity(
        symbol="159915.SZ",
        name="创业板ETF易方达",
        index_name="创业板",
        role="core",
        trade_date="2026-07-17",
        total_shares=14_916_000_000,
        previous_total_shares=13_020_000_000,
        baseline=_baseline(),
    )

    assert result.share_delta == 1_896_000_000
    assert result.daily_change_pct == pytest.approx(14.5622, rel=1e-5)
    assert result.baseline_change_pct == pytest.approx(6.0190, rel=1e-5)
    assert result.multiple == pytest.approx(60.1904, rel=1e-5)
    assert result.direction == "increase"
    assert result.is_tenfold is True
    assert result.paired_symbol is None
    assert result.report_period == "2026Q2"
    assert result.confirmed_huijin_holding_pct == 15.873
    assert result.baseline_source_kind == "reported"


def test_missing_previous_day_keeps_daily_metrics_unknown() -> None:
    result = calculate_activity(
        symbol="159915.SZ",
        name="创业板ETF易方达",
        index_name="创业板",
        role="core",
        trade_date="2026-07-17",
        total_shares=14_916_000_000,
        previous_total_shares=None,
        baseline=_baseline(),
    )

    assert result.share_delta is None
    assert result.daily_change_pct is None
    assert result.baseline_change_pct is None
    assert result.multiple is None
    assert result.direction == "unknown"


def test_missing_current_shares_keeps_all_calculated_metrics_unknown() -> None:
    result = calculate_activity(
        symbol="159915.SZ",
        name="创业板ETF易方达",
        index_name="创业板",
        role="core",
        trade_date="2026-07-17",
        total_shares=None,
        previous_total_shares=13_020_000_000,
        baseline=_baseline(),
    )

    assert result.share_delta is None
    assert result.daily_change_pct is None
    assert result.baseline_change_pct is None
    assert result.multiple is None
    assert result.cumulative_baseline_change_pct is None
    assert result.direction == "unknown"


def test_cumulative_baseline_change_works_without_previous_day() -> None:
    result = calculate_activity(
        symbol="159915.SZ",
        name="创业板ETF易方达",
        index_name="创业板",
        role="core",
        trade_date="2026-07-17",
        total_shares=14_916_000_000,
        previous_total_shares=None,
        baseline=_baseline(),
    )

    assert result.cumulative_baseline_change_pct == pytest.approx(-52.6476, rel=1e-5)


def test_missing_baseline_keeps_daily_delta_and_rate() -> None:
    result = calculate_activity(
        symbol="159915.SZ",
        name="创业板ETF易方达",
        index_name="创业板",
        role="core",
        trade_date="2026-07-17",
        total_shares=11_000,
        previous_total_shares=10_000,
        baseline=None,
    )

    assert result.share_delta == 1_000
    assert result.daily_change_pct == pytest.approx(10)
    assert result.baseline_change_pct is None
    assert result.cumulative_baseline_change_pct is None
    assert result.multiple is None
    assert result.direction == "increase"
    assert result.is_tenfold is False


def test_flat_delta_is_not_tenfold() -> None:
    result = calculate_activity(
        symbol="510300.SH",
        name="沪深300ETF华泰柏瑞",
        index_name="沪深300",
        role="core",
        trade_date="2026-07-17",
        total_shares=10_000,
        previous_total_shares=10_000,
        baseline=_baseline(symbol="510300.SH", total_shares=10_000),
    )

    assert result.share_delta == 0
    assert result.direction == "flat"
    assert result.multiple == 0
    assert result.is_tenfold is False
    assert result.paired_symbol == "159919.SZ"


@pytest.mark.parametrize(
    ("core_direction", "validator_direction", "expected_state"),
    [
        ("increase", "increase", "confirmed_increase"),
        ("decrease", "decrease", "confirmed_decrease"),
        ("increase", "decrease", "divergent"),
        ("flat", "increase", "divergent"),
        ("unknown", "increase", "incomplete"),
    ],
)
def test_validate_pair_states(
    core_direction: str,
    validator_direction: str,
    expected_state: str,
) -> None:
    core = _activity(
        symbol="510300.SH",
        direction=core_direction,
        daily_change_pct=4,
        baseline_change_pct=2,
        multiple=20,
    )
    validator = _activity(
        symbol="159919.SZ",
        direction=validator_direction,
        daily_change_pct=3,
        baseline_change_pct=1,
        multiple=10,
    )

    result = validate_pair(core, validator)

    assert result.state == expected_state
    if expected_state in {"divergent", "incomplete"}:
        assert result.conservative_daily_change_pct is None
        assert result.conservative_baseline_change_pct is None
        assert result.conservative_multiple is None


def test_pair_conservative_values_use_smaller_absolute_magnitude() -> None:
    core = _activity(
        symbol="510300.SH",
        direction="decrease",
        daily_change_pct=-8,
        baseline_change_pct=-4,
        multiple=40,
    )
    validator = _activity(
        symbol="159919.SZ",
        direction="decrease",
        daily_change_pct=-3,
        baseline_change_pct=-2,
        multiple=20,
    )

    result = validate_pair(core, validator)

    assert result.state == "confirmed_decrease"
    assert result.conservative_daily_change_pct == -3
    assert result.conservative_baseline_change_pct == -2
    assert result.conservative_multiple == 20


def test_unknown_symbol_calculates_metrics_without_a_pair() -> None:
    result = calculate_activity(
        symbol="999999.SH",
        name="测试ETF",
        index_name="测试指数",
        role="core",
        trade_date="2026-07-17",
        total_shares=11_000,
        previous_total_shares=10_000,
        baseline=_baseline(symbol="999999.SH", total_shares=10_000),
    )

    assert result.paired_symbol is None
    assert result.share_delta == 1_000
    assert result.daily_change_pct == pytest.approx(10)
    assert result.baseline_change_pct == pytest.approx(10)
    assert result.multiple == pytest.approx(100)
    assert result.direction == "increase"
