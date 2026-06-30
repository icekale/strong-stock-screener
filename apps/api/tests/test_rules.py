from app.models import KlineBar, StrongStockCandidate
from app.rules import analyze_screening_item, analyze_watchlist_risk


def _bars(closes: list[float], *, volumes: list[float] | None = None) -> list[KlineBar]:
    bars: list[KlineBar] = []
    for index, close in enumerate(closes):
        previous = closes[index - 1] if index else close
        open_price = previous * 0.99 if close >= previous else previous * 1.02
        volume = volumes[index] if volumes is not None else 1_000_000 + index * 10_000
        bars.append(
            KlineBar(
                date=f"2026-01-{(index % 28) + 1:02d}",
                open=round(open_price, 2),
                close=round(close, 2),
                high=round(max(open_price, close) * 1.03, 2),
                low=round(min(open_price, close) * 0.98, 2),
                volume=volume,
            )
        )
    return bars


def test_focus_candidate_rewards_trend_volume_and_new_high() -> None:
    candidate = StrongStockCandidate(
        symbol="603890.SH",
        name="春秋电子",
        limit_up_evidence=["20日内涨停"],
    )
    bars = _bars([10 + index * 0.05 for index in range(220)])

    item = analyze_screening_item(candidate, bars, trade_date="2026-06-11")

    assert item.status == "focus"
    assert item.score >= 70
    assert "20日内涨停" in item.rule_hits
    assert "收盘价在MA5上方" in item.rule_hits
    assert "200日新高" in item.rule_hits
    assert item.metrics["is_200d_high"] is True


def test_volume_stall_marks_reduce_risk_without_empty_status() -> None:
    closes = [10 + index * 0.05 for index in range(215)] + [20.0, 20.02, 20.03, 20.04, 20.05]
    volumes = [1_000_000 for _ in range(219)] + [4_000_000]
    candidate = StrongStockCandidate(
        symbol="002000.SZ",
        name="示例股份",
        limit_up_evidence=["20日内涨停"],
    )

    item = analyze_screening_item(candidate, _bars(closes, volumes=volumes), trade_date="2026-06-11")

    assert item.status == "reduce_risk"
    assert "放量滞涨" in item.risk_flags
    assert item.status != "empty"


def test_empty_rule_only_applies_to_watchlist_risk() -> None:
    closes = [20 - index * 0.05 for index in range(220)]
    candidate = StrongStockCandidate(
        symbol="002000.SZ",
        name="示例股份",
        limit_up_evidence=["20日内涨停"],
    )

    screening_item = analyze_screening_item(candidate, _bars(closes), trade_date="2026-06-11")
    risk_item = analyze_watchlist_risk(candidate, _bars(closes), trade_date="2026-06-11")

    assert screening_item.status in {"wait_pullback", "reduce_risk"}
    assert screening_item.status != "empty"
    assert risk_item.risk_action == "empty"
    assert "MA5拐头向下" in risk_item.risk_flags
    assert "跌在均线下方" in risk_item.risk_flags


def test_short_kline_returns_data_incomplete() -> None:
    candidate = StrongStockCandidate(
        symbol="603890.SH",
        name="春秋电子",
        limit_up_evidence=["20日内涨停"],
    )

    item = analyze_screening_item(candidate, _bars([10, 10.5, 11]), trade_date="2026-06-11")

    assert item.status == "data_incomplete"
    assert item.data_status == "incomplete"
    assert "K线不足220日" in item.risk_flags


def test_screening_item_includes_gsgf_analysis() -> None:
    candidate = StrongStockCandidate(
        symbol="603890.SH",
        name="春秋电子",
        industry="消费电子",
        limit_up_evidence=["20日内涨停"],
    )
    item = analyze_screening_item(
        candidate,
        _bars([10 + index * 0.05 for index in range(220)]),
        trade_date="2026-06-11",
    )

    assert item.gsgf is not None
    assert item.gsgf.model_version == "gsgf-v2"
    assert item.gsgf.total_score > 0
    assert item.gsgf.zone in {"a_zone", "b_zone_a_point", "unformed"}


def test_watchlist_risk_includes_gsgf_without_changing_empty_rule() -> None:
    candidate = StrongStockCandidate(symbol="002000.SZ", name="示例股份")
    risk_item = analyze_watchlist_risk(
        candidate,
        _bars([20 - index * 0.05 for index in range(220)]),
        trade_date="2026-06-11",
    )

    assert risk_item.risk_action == "empty"
    assert risk_item.gsgf is not None
    assert risk_item.gsgf.zone == "c_zone"
