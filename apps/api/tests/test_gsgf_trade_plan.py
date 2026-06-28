from app.models import GsgfAnalysis
from app.services.gsgf_trade_plan import build_gsgf_trade_plan


def test_gsgf_trade_plan_separates_holder_and_empty_position_guidance() -> None:
    analysis = GsgfAnalysis(
        total_score=82,
        action="strong_candidate",
        final_status="确认买点",
        zone="a_zone",
        volume_structure="three_yang_controls_three_yin",
        setup_type="B区A点",
        setup_score=20,
        confirm_type="放量突破确认",
        confirm_score=35,
        trigger_tags=["放量突破确认"],
    )

    plan = build_gsgf_trade_plan(analysis)

    assert plan.status == "确认买点"
    assert any("持有优于追涨" in item for item in plan.holder_guidance)
    assert any("等分歧低吸" in item for item in plan.empty_position_guidance)
    assert plan.holder_guidance != plan.empty_position_guidance
    assert any("放量突破确认" in item for item in plan.risk_invalidation)
    assert "不构成收益承诺" in plan.research_note
    assert "必涨" not in _all_text(plan)
    assert "保证" not in _all_text(plan)


def test_gsgf_trade_plan_turns_hard_risk_into_reduce_and_invalidation_text() -> None:
    analysis = GsgfAnalysis(
        total_score=48,
        action="avoid",
        final_status="减仓",
        zone="c_zone",
        setup_type="星线蓄势",
        risk_flags=["全局阴量压制", "高位巨量长上影"],
        pressure_flags=["前高压力"],
    )

    plan = build_gsgf_trade_plan(analysis)

    assert any("冲高不封减仓" in item for item in plan.holder_guidance)
    assert any("空仓" in item and "风险解除" in item for item in plan.empty_position_guidance)
    assert any("全局阴量压制" in item for item in plan.risk_invalidation)
    assert any("高位巨量长上影" in item for item in plan.risk_invalidation)


def _all_text(plan: object) -> str:
    payload = plan.model_dump(mode="json")
    return " ".join(
        str(value)
        for value in [
            *payload["holder_guidance"],
            *payload["empty_position_guidance"],
            *payload["risk_invalidation"],
            payload["research_note"],
        ]
    )
