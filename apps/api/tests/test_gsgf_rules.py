from app.models import GsgfAnalysis, GsgfScoreBreakdown
from app.gsgf_rules import analyze_gsgf, build_gsgf_chart_annotations
from app.models import KlineBar


def test_gsgf_analysis_serializes_business_fields() -> None:
    analysis = GsgfAnalysis(
        model_version="gsgf-v2",
        total_score=78,
        action="watch_candidate",
        final_status="候选",
        zone="b_zone_a_point",
        volume_structure="three_yang_controls_three_yin",
        setup_type="B区A点",
        setup_score=18,
        confirm_type=None,
        confirm_score=0,
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
        evidence_refs=["book1-p081-600379-b-zone-a-point"],
        diagnostics={"pattern": {"score": 15, "flags": ["b_zone_a_point"]}},
        explanation=["B区A点，等待确认"],
    )

    payload = analysis.model_dump(mode="json")

    assert payload["model_version"] == "gsgf-v2"
    assert payload["total_score"] == 78
    assert payload["action"] == "watch_candidate"
    assert payload["final_status"] == "候选"
    assert payload["zone"] == "b_zone_a_point"
    assert payload["setup_type"] == "B区A点"
    assert payload["setup_score"] == 18
    assert payload["scores"]["volume_thickness"] == 22
    assert payload["evidence_refs"] == ["book1-p081-600379-b-zone-a-point"]
    assert payload["diagnostics"]["pattern"]["flags"] == ["b_zone_a_point"]


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


def test_gsgf_detects_volume_breakout_confirmation() -> None:
    closes = [10 + index * 0.02 for index in range(219)]
    bars = _bars(closes + [15.2], [1_000_000 for _ in range(219)] + [3_200_000])
    previous = bars[-2].close
    bars[-1] = bars[-1].model_copy(
        update={
            "open": round(previous * 1.02, 2),
            "close": round(previous * 1.082, 2),
            "high": round(previous * 1.09, 2),
            "low": round(previous * 1.01, 2),
            "volume": 3_200_000,
        }
    )

    analysis = analyze_gsgf(bars)

    assert analysis.model_version == "gsgf-v2"
    assert analysis.confirm_type == "放量突破确认"
    assert analysis.confirm_score >= 30
    assert analysis.final_status == "确认买点"
    assert "放量突破确认" in analysis.trigger_tags
    assert "book1-p022-600680-lift-distribute" in analysis.evidence_refs
    assert "confirmation" in analysis.diagnostics
    assert analysis.trade_plan is not None
    assert any("持有优于追涨" in item for item in analysis.trade_plan.holder_guidance)


def test_gsgf_negative_sample_flags_global_distribution_risk() -> None:
    closes = [8 + index * 0.01 for index in range(160)]
    closes += [9.6, 9.2, 9.1, 8.9, 8.8, 8.75, 8.65, 8.6, 8.55, 8.5]
    closes += [8.45 + index * 0.01 for index in range(49)]
    bars = _bars(closes + [9.0], [1_000_000 for _ in range(220)])
    for idx in range(160, 170):
        bars[idx] = bars[idx].model_copy(update={"open": bars[idx].close * 1.03, "volume": 4_000_000})
    bars[-1] = bars[-1].model_copy(update={"open": 8.65, "close": 9.0, "high": 9.05, "low": 8.6, "volume": 4_500_000})

    analysis = analyze_gsgf(bars)

    assert "全局阴量压制" in analysis.risk_flags
    assert analysis.final_status in {"减仓", "回避"}


def test_gsgf_chart_annotations_include_volume_structure_and_zone_evidence() -> None:
    closes = [10 + index * 0.03 for index in range(220)]
    volumes = [2_000_000 if index % 4 != 0 else 700_000 for index in range(220)]
    bars = _bars(closes, volumes)

    annotations = build_gsgf_chart_annotations(bars, industry_strength="strong")

    volume_annotation = next(item for item in annotations if item.type == "volume_structure")
    assert volume_annotation.label == "三阳控三阴"
    assert volume_annotation.severity == "positive"
    assert volume_annotation.start_date == bars[-40].date
    assert volume_annotation.end_date == bars[-1].date
    assert any(item.type == "zone" and item.date == bars[-1].date for item in annotations)


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


def test_gsgf_marks_high_star_platform_as_risk_not_low_absorb() -> None:
    closes = [8 + index * 0.05 for index in range(216)]
    closes += [18.0, 18.05, 18.02, 18.06]
    bars = _bars(closes, [1_000_000 for _ in range(216)] + [2_400_000, 2_500_000, 2_450_000, 2_550_000])
    for idx in range(216, 220):
        base = bars[idx - 1].close
        bars[idx] = bars[idx].model_copy(
            update={
                "open": round(base * 1.002, 2),
                "close": round(base * 1.003, 2),
                "high": round(base * 1.035, 2),
                "low": round(base * 0.986, 2),
            }
        )

    analysis = analyze_gsgf(bars)

    assert "高位星线平台" in analysis.risk_flags
    assert analysis.final_status in {"减仓", "回避"}
    assert analysis.final_status != "低吸观察"
    assert "book3-p132-002130-high-star-platform" in analysis.evidence_refs


def test_gsgf_b_zone_a_point_requires_contracting_pullback_and_reclaim() -> None:
    closes = [10 + index * 0.02 for index in range(220)]
    bars = _bars(closes)

    plain = analyze_gsgf(bars)
    assert plain.setup_type != "B区A点"

    for idx in range(214, 219):
        base = bars[idx - 1].close
        bars[idx] = bars[idx].model_copy(
            update={
                "open": round(base * 0.995, 2),
                "close": round(base * 0.992, 2),
                "high": round(base * 1.002, 2),
                "low": round(base * 0.982, 2),
                "volume": 620_000,
            }
        )
    previous = bars[-2].close
    bars[-1] = bars[-1].model_copy(
        update={
            "open": round(previous * 1.005, 2),
            "close": round(previous * 1.035, 2),
            "high": round(previous * 1.042, 2),
            "low": round(previous * 0.998, 2),
            "volume": 1_450_000,
        }
    )

    analysis = analyze_gsgf(bars)

    assert analysis.setup_type == "B区A点"
    assert analysis.final_status in {"候选", "低吸观察"}
    assert "book1-p081-600379-b-zone-a-point" in analysis.evidence_refs


def test_gsgf_chart_annotations_mark_high_volume_upper_shadow_risk() -> None:
    closes = [10 + index * 0.05 for index in range(219)] + [20.1]
    bars = _bars(closes, [1_000_000 for _ in range(219)] + [5_000_000])
    bars[-1] = bars[-1].model_copy(update={"high": 24.0, "open": 20.0, "close": 20.1, "low": 19.8})

    annotations = build_gsgf_chart_annotations(bars)

    risk_annotation = next(item for item in annotations if item.type == "risk" and item.label == "高位巨量长上影")
    assert risk_annotation.label == "高位巨量长上影"
    assert risk_annotation.severity == "danger"
    assert risk_annotation.price == bars[-1].high
