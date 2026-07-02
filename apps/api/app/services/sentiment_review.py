from __future__ import annotations

from app.models import SentimentDecisionOutcome, SentimentDecisionResponse


def score_sentiment_decision(
    decision: SentimentDecisionResponse,
    next_day_index_pct: float | None,
    next_day_limit_up_count: int | None,
    next_day_limit_down_count: int | None,
) -> SentimentDecisionOutcome:
    weak_next_day = (next_day_index_pct or 0) < -1 or (next_day_limit_down_count or 0) >= 30
    strong_next_day = (next_day_index_pct or 0) > 1 or (next_day_limit_up_count or 0) >= 70
    hit = False
    score = 0.0
    reason = "结果中性"

    if decision.trade_permission == "空仓等待" and weak_next_day:
        hit = True
        score = 1.0
        reason = "空仓等待规避退潮"
    elif decision.trade_permission in {"轻仓试错", "强势进攻"} and strong_next_day:
        hit = True
        score = 1.0
        reason = "进攻许可匹配次日强势"
    elif decision.trade_permission == "只卖不追" and not strong_next_day:
        hit = True
        score = 0.7
        reason = "高潮降温提示有效"
    else:
        score = -0.5
        reason = "情绪许可与次日表现不匹配"

    return SentimentDecisionOutcome(
        trade_date=decision.trade_date,
        next_day_index_pct=next_day_index_pct,
        next_day_limit_up_count=next_day_limit_up_count,
        next_day_limit_down_count=next_day_limit_down_count,
        hit=hit,
        score=score,
        reason=reason,
    )
