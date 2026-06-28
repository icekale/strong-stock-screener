from __future__ import annotations

from app.models import GsgfAnalysis, GsgfTradePlan


def build_gsgf_trade_plan(analysis: GsgfAnalysis) -> GsgfTradePlan:
    holder_guidance: list[str] = []
    empty_position_guidance: list[str] = []
    risk_invalidation: list[str] = []

    if analysis.final_status == "确认买点":
        holder_guidance.append(_confirmed_holder_text(analysis))
        empty_position_guidance.append(_confirmed_empty_position_text(analysis))
    elif analysis.final_status == "低吸观察":
        holder_guidance.append("持仓可跟踪低吸确认，弱反不追，未重新站稳均线前控制仓位。")
        empty_position_guidance.append("等分歧低吸，优先看缩量回踩后的承接，不用在未确认时抢先追涨。")
    elif analysis.final_status in {"减仓", "回避"}:
        holder_guidance.append(_risk_holder_text(analysis))
        empty_position_guidance.append("空仓等待风险解除，重新出现放量确认或结构修复前不急于试错。")
    elif analysis.final_status == "候选":
        holder_guidance.append("已有仓位以观察为主，持有优于追涨，等确认信号再提高主动性。")
        empty_position_guidance.append("候选阶段先放入观察池，等分歧低吸或放量突破确认后再评估。")
    else:
        holder_guidance.append("结构仍在观察期，持仓以跟踪为主，确认不足时不扩大风险。")
        empty_position_guidance.append("空仓先等触发信号，优先选择量价确认后的机会。")

    risk_invalidation.extend(_risk_invalidation_text(analysis))
    return GsgfTradePlan(
        status=analysis.final_status,
        holder_guidance=_dedupe(holder_guidance),
        empty_position_guidance=_dedupe(empty_position_guidance),
        risk_invalidation=_dedupe(risk_invalidation),
    )


def _confirmed_holder_text(analysis: GsgfAnalysis) -> str:
    if analysis.confirm_type:
        return f"{analysis.confirm_type}已出现，持有优于追涨；盘中不能延续放量时降低主动性。"
    return "确认买点已出现，持有优于追涨；若冲高承接不足，先看确认质量。"


def _confirmed_empty_position_text(analysis: GsgfAnalysis) -> str:
    if analysis.setup_type:
        return f"{analysis.setup_type}后进入确认区，空仓等分歧低吸，避免连续拉升后追高。"
    return "确认区不代表无脑追涨，空仓等分歧低吸或回踩不破后的再确认。"


def _risk_holder_text(analysis: GsgfAnalysis) -> str:
    if "高位巨量长上影" in analysis.risk_flags:
        return "高位巨量长上影压制，冲高不封减仓，先保护利润和本金。"
    if "全局阴量压制" in analysis.risk_flags:
        return "全局阴量压制未解除，冲高不封减仓，不把反抽当成新买点。"
    return "结构转弱，冲高不封减仓，等待风险信号消退后再重新评估。"


def _risk_invalidation_text(analysis: GsgfAnalysis) -> list[str]:
    output: list[str] = []
    if analysis.confirm_type:
        output.append(f"{analysis.confirm_type}后若放量不续强或跌回突破位，视为确认失效。")
    if analysis.setup_type:
        output.append(f"{analysis.setup_type}若跌破星线低点且无法收回，低吸前提失效。")
    for flag in analysis.risk_flags:
        output.append(f"{flag}未解除前，计划以防守和降风险为先。")
    for flag in analysis.pressure_flags:
        output.append(f"{flag}附近冲高不封或放量滞涨，降低计划级别。")
    if not output:
        output.append("跌破关键承接位且无法收回，或放量滞涨转弱，原计划失效。")
    return output


def _dedupe(items: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output
