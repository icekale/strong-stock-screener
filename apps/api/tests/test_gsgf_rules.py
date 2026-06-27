from app.models import GsgfAnalysis, GsgfScoreBreakdown
from app.gsgf_rules import analyze_gsgf
from app.models import KlineBar


def test_gsgf_analysis_serializes_business_fields() -> None:
    analysis = GsgfAnalysis(
        model_version="gsgf-v1",
        total_score=78,
        action="watch_candidate",
        zone="b_zone_a_point",
        volume_structure="three_yang_controls_three_yin",
        scores=GsgfScoreBreakdown(
            safety_pressure=15,
            volume_thickness=22,
            ma_alignment=18,
            pattern_space=10,
            star_trigger=5,
            sector_theme=8,
        ),
        pattern_tags=["颈位回踩"],
        trigger_tags=["星线蓄势"],
        pressure_flags=["前高压力"],
        risk_flags=[],
        explanation=["B区A点，等待确认"],
    )

    payload = analysis.model_dump(mode="json")

    assert payload["model_version"] == "gsgf-v1"
    assert payload["total_score"] == 78
    assert payload["action"] == "watch_candidate"
    assert payload["zone"] == "b_zone_a_point"
    assert payload["scores"]["volume_thickness"] == 22


def _bars(closes: list[float], volumes: list[float] | None = None) -> list[KlineBar]:
    bars: list[KlineBar] = []
    for index, close in enumerate(closes):
        previous = closes[index - 1] if index else close
        is_up = close >= previous
        open_price = previous * (0.99 if is_up else 1.02)
        volume = volumes[index] if volumes else 1_000_000
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


def test_gsgf_detects_three_yang_controls_three_yin() -> None:
    closes = [10 + index * 0.03 for index in range(220)]
    volumes = [2_000_000 if index % 4 != 0 else 700_000 for index in range(220)]

    analysis = analyze_gsgf(_bars(closes, volumes), industry_strength="strong")

    assert analysis.volume_structure == "three_yang_controls_three_yin"
    assert analysis.scores.volume_thickness >= 18
    assert analysis.total_score >= 65


def test_gsgf_marks_c_zone_and_avoid_for_downtrend() -> None:
    closes = [20 - index * 0.04 for index in range(220)]

    analysis = analyze_gsgf(_bars(closes), industry_strength="weak")

    assert analysis.zone == "c_zone"
    assert analysis.action == "avoid"
    assert "C区风险" in analysis.risk_flags


def test_gsgf_detects_high_volume_upper_shadow_pressure() -> None:
    closes = [10 + index * 0.05 for index in range(219)] + [20.1]
    bars = _bars(closes, [1_000_000 for _ in range(219)] + [5_000_000])
    bars[-1] = bars[-1].model_copy(update={"high": 24.0, "open": 20.0, "close": 20.1, "low": 19.8})

    analysis = analyze_gsgf(bars)

    assert "高位巨量长上影" in analysis.risk_flags
    assert analysis.action == "avoid"
