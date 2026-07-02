from __future__ import annotations

from app.models import (
    MarketEmotionSnapshotResponse,
    SentimentDecisionResponse,
    SentimentMainSectorSignal,
    SentimentSummaryResponse,
)


def build_sentiment_decision(
    summary: SentimentSummaryResponse,
    market_emotion: MarketEmotionSnapshotResponse | None = None,
) -> SentimentDecisionResponse:
    score_change = _score_change(market_emotion)
    risk_count = _risk_count(summary)
    market_state = _market_state(summary, score_change)
    return SentimentDecisionResponse(
        trade_date=summary.trade_date,
        market_state=market_state,
        trade_permission=_trade_permission(market_state, risk_count),
        risk_level=_risk_level(risk_count, market_state),
        confidence=_confidence(summary, market_emotion),
        score_change=score_change,
        main_sectors=[
            SentimentMainSectorSignal(
                name=item.name,
                strength_score=item.strength_score,
                limit_up_count=item.limit_up_count,
                break_board_count=item.break_board_count,
                max_consecutive_boards=item.max_consecutive_boards,
                leader=item.leader,
                symbols=item.symbols,
            )
            for item in summary.hot_industries[:5]
        ],
        reasons=_reasons(summary, score_change),
        risks=_risks(summary, market_state),
    )


def _score_change(market_emotion: MarketEmotionSnapshotResponse | None) -> float | None:
    samples = market_emotion.samples if market_emotion else []
    if len(samples) < 2:
        return None
    return round(samples[-1].emotion_score - samples[0].emotion_score, 2)


def _risk_count(summary: SentimentSummaryResponse) -> int:
    metrics = summary.metrics
    risk_count = 0
    if metrics.break_board_count >= 20:
        risk_count += 1
    if (metrics.limit_down_count or 0) >= 20:
        risk_count += 1
    if metrics.seal_rate_pct is not None and metrics.seal_rate_pct < 50:
        risk_count += 1
    if (
        metrics.advance_count is not None
        and metrics.decline_count is not None
        and metrics.decline_count > metrics.advance_count * 2
    ):
        risk_count += 1
    return risk_count


def _risk_level(risk_count: int, market_state: str) -> str:
    if risk_count >= 3:
        return "高"
    if risk_count >= 1:
        return "中"
    if market_state == "主升":
        return "低"
    return "中"


def _market_state(summary: SentimentSummaryResponse, score_change: float | None) -> str:
    metrics = summary.metrics
    if metrics.emotion_score < 25:
        return "退潮" if _risk_count(summary) >= 2 else "冰点"
    if metrics.emotion_score >= 78:
        return "高潮"
    if _risk_count(summary) >= 3:
        return "退潮"
    if metrics.break_board_count >= 18 and (metrics.seal_rate_pct or 100) < 60:
        return "分歧"
    if score_change is not None and score_change >= 10:
        return "修复"
    if metrics.emotion_score >= 62 and metrics.limit_up_count >= 70:
        return "主升"
    if metrics.emotion_score >= 45:
        return "修复"
    return "冰点"


def _trade_permission(market_state: str, risk_count: int) -> str:
    if market_state in {"退潮", "冰点"}:
        return "空仓等待"
    if market_state == "高潮":
        return "只卖不追"
    if market_state == "分歧":
        return "只低吸"
    if market_state == "主升" and risk_count == 0:
        return "强势进攻"
    return "轻仓试错"


def _confidence(
    summary: SentimentSummaryResponse,
    market_emotion: MarketEmotionSnapshotResponse | None,
) -> float:
    confidence = 50
    metrics = summary.metrics
    if metrics.advance_count is not None and metrics.decline_count is not None:
        confidence += 15
    if metrics.turnover_change_pct is not None:
        confidence += 10
    if summary.hot_industries:
        confidence += 10
    if market_emotion and len(market_emotion.samples) >= 2:
        confidence += 15
    return float(min(confidence, 100))


def _reasons(summary: SentimentSummaryResponse, score_change: float | None) -> list[str]:
    metrics = summary.metrics
    reasons: list[str] = []
    if score_change is not None and score_change > 0:
        reasons.append("情绪分数回升")
    if metrics.limit_up_count >= 50:
        reasons.append("涨停家数达到活跃区间")
    if metrics.seal_rate_pct is not None and metrics.seal_rate_pct >= 70:
        reasons.append("封板率较强")
    if summary.hot_industries:
        reasons.append(f"主线板块集中在{summary.hot_industries[0].name}")
    return reasons or ["数据不足，保持观察"]


def _risks(summary: SentimentSummaryResponse, market_state: str) -> list[str]:
    metrics = summary.metrics
    risks: list[str] = []
    if (metrics.limit_down_count or 0) >= 20 or metrics.break_board_count >= 20:
        risks.append("跌停与炸板压力高")
    if metrics.seal_rate_pct is not None and metrics.seal_rate_pct < 50:
        risks.append("封板率偏低")
    if market_state == "高潮":
        risks.append("情绪过热，避免追高")
    if (
        metrics.decline_count is not None
        and metrics.advance_count is not None
        and metrics.decline_count > metrics.advance_count
    ):
        risks.append("下跌家数多于上涨家数")
    return risks
