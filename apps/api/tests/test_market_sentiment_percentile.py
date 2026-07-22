import pytest
from pydantic import ValidationError

from app.models import (
    SentimentPercentileFactor,
    SentimentPercentilePoint,
    SentimentPercentileResponse,
    SentimentPercentileFactors,
)
from app.services.market_sentiment_percentile import (
    WEIGHTS,
    calculate_sentiment_percentile,
    directional_amplitude,
    midrank_percentile,
    sentiment_percentile_level,
)
from tests.market_sentiment_fixtures import make_test_bar, make_test_bars


def percentile_response_fixture() -> SentimentPercentileResponse:
    factor = SentimentPercentileFactor(score=50, raw_value=0, raw_unit="%")
    point = SentimentPercentilePoint(
        trade_date="2026-07-21",
        score=50,
        level="中性",
        factors=SentimentPercentileFactors(
            volume=factor,
            index_move_5d=factor,
            price_position=factor,
            amplitude_5d=factor,
            volume_trend=factor,
        ),
    )
    return SentimentPercentileResponse(
        weights={key: 0.2 for key in WEIGHTS},
        latest_complete_trade_date=point.trade_date,
        selected_trade_date=point.trade_date,
        selected=point,
        history=[point],
        source_status=[],
        generated_at="2026-07-22T15:20:00+08:00",
    )


def test_midrank_counts_ties_in_the_middle() -> None:
    values = [1.0] * 250 + [2.0] * 250
    assert midrank_percentile(values, 2.0) == 75.0


def test_calculator_requires_full_factor_warmup() -> None:
    bars = make_test_bars(1020)
    points = calculate_sentiment_percentile(bars)
    assert len(points) == 500
    assert points[0].trade_date == bars[520].date
    assert points[-1].trade_date == bars[-1].date


def test_factor_formulas_are_exposed_in_the_first_complete_point() -> None:
    bars = make_test_bars(1020)
    point = calculate_sentiment_percentile(bars)[0]
    index = 520
    five_day_return = bars[index].close / bars[index - 5].close - 1
    five_day_amplitude = directional_amplitude(
        bars[index - 5].close,
        max(bar.high for bar in bars[index - 4 : index + 1]),
        min(bar.low for bar in bars[index - 4 : index + 1]),
        bars[index].close,
    )
    low = min(bar.low for bar in bars[index - 499 : index + 1])
    high = max(bar.high for bar in bars[index - 499 : index + 1])
    price_position = (bars[index].close - low) / (high - low) * 100
    mean_5 = sum(bar.amount for bar in bars[index - 4 : index + 1]) / 5
    mean_20 = sum(bar.amount for bar in bars[index - 19 : index + 1]) / 20
    volume_trend = mean_5 / mean_20 - 1

    assert point.factors.volume.raw_value == bars[index].amount
    assert point.factors.index_move_5d.raw_value == pytest.approx(five_day_return * 100)
    assert point.factors.price_position.raw_value == pytest.approx(price_position)
    assert point.factors.amplitude_5d.raw_value == pytest.approx(five_day_amplitude * 100)
    assert point.factors.volume_trend.raw_value == pytest.approx(volume_trend * 100)


def test_future_bar_changes_do_not_change_prior_points() -> None:
    bars = make_test_bars(1020)
    baseline = calculate_sentiment_percentile(bars)
    mutated = [*bars, make_test_bar(1021, close=9999, amount=9_999_999_999)]
    by_date = {point.trade_date: point for point in calculate_sentiment_percentile(mutated)}
    assert all(by_date[point.trade_date] == point for point in baseline[1:])


def test_zero_price_range_skips_only_the_affected_composite_date() -> None:
    bars = make_test_bars(1020)
    bars[:519] = [
        bar.model_copy(update={"open": 100, "high": 100, "low": 100, "close": 100})
        for bar in bars[:519]
    ]

    points = calculate_sentiment_percentile(bars)
    dates = {point.trade_date for point in points}

    assert len(points) == 500
    assert bars[518].date not in dates
    assert bars[519].date not in dates
    assert bars[520].date in dates
    assert bars[-1].date in dates


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("open", 0),
        ("open", -1),
        ("high", 0),
        ("low", -1),
        ("close", 0),
        ("amount", 0),
        ("amount", -1),
        ("amount", None),
    ],
)
def test_non_positive_or_missing_required_market_values_raise_value_error(
    field: str,
    value: float | None,
) -> None:
    bar = make_test_bar(0).model_copy(update={field: value})
    with pytest.raises(ValueError, match="invalid market bar"):
        calculate_sentiment_percentile([bar])


def test_duplicate_dates_keep_the_last_record() -> None:
    bars = make_test_bars(519)
    replacement = make_test_bar(518, close=250, amount=200_000_000)
    duplicate_result = calculate_sentiment_percentile([*bars, replacement])
    expected_result = calculate_sentiment_percentile([*bars[:-1], replacement])

    assert duplicate_result == expected_result


@pytest.mark.parametrize(
    ("score", "level"),
    [(0, "冰点"), (19.9, "冰点"), (20, "偏冷"), (40, "中性"), (60, "偏热"), (80, "过热")],
)
def test_level_boundaries(score: float, level: str) -> None:
    assert sentiment_percentile_level(score) == level


@pytest.mark.parametrize("direction", [-1, 0, 1])
def test_directional_amplitude_preserves_return_direction(direction: int) -> None:
    assert directional_amplitude(100, 110, 90, 100 + direction) * direction >= 0


def test_response_contract_and_equal_weights() -> None:
    response = percentile_response_fixture()
    assert response.model_version == "market-sentiment-percentile-v1"
    assert response.benchmark_symbol == "000985.SH"
    assert response.window_size == 500
    assert response.weights == {key: 0.2 for key in WEIGHTS}


def test_response_factor_score_is_bounded() -> None:
    with pytest.raises(ValidationError):
        SentimentPercentileFactor(score=100.1, raw_value=0, raw_unit="%")
