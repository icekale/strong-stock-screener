from app.models import KlineBar
from app.services.gsgf_backtest import summarize_gsgf_backtest


def _trend_bars(count: int = 90) -> list[KlineBar]:
    bars: list[KlineBar] = []
    for index in range(count):
        close = 10 + index * 0.12
        bars.append(
            KlineBar(
                date=f"2026-01-{(index % 28) + 1:02d}",
                open=round(close * 0.99, 2),
                close=round(close, 2),
                high=round(close * 1.02, 2),
                low=round(close * 0.98, 2),
                volume=1_000_000 + index * 20_000,
            )
        )
    return bars


def test_summarize_gsgf_backtest_groups_forward_returns_by_status() -> None:
    result = summarize_gsgf_backtest(
        {"603890.SH": _trend_bars()},
        windows=[1, 3],
        min_history=60,
    )

    assert result.windows == [1, 3]
    assert result.sample_count > 0
    assert result.source_status[0].source == "股是股非回测"
    assert {bucket.status for bucket in result.buckets} <= {"确认买点", "候选", "低吸观察", "观察", "减仓", "回避"}
    assert all(bucket.sample_count > 0 for bucket in result.buckets)
    first_bucket = result.buckets[0]
    assert first_bucket.avg_score is not None
    assert [item.window_days for item in first_bucket.windows] == [1, 3]
    assert first_bucket.windows[0].sample_count > 0
    assert first_bucket.windows[0].avg_return_pct is not None
    assert first_bucket.windows[0].avg_max_drawdown_pct is not None


def test_summarize_gsgf_backtest_skips_symbols_without_enough_future_bars() -> None:
    result = summarize_gsgf_backtest(
        {"603890.SH": _trend_bars(count=60)},
        windows=[1, 5],
        min_history=60,
    )

    assert result.sample_count == 0
    assert result.buckets == []
    assert "有效样本 0" in result.source_status[0].detail
