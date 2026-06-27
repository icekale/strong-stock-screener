from app.models import GsgfAnalysis, GsgfScoreBreakdown


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
