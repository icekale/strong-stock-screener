from app.models import (
    MarketEmotionMetrics,
    MarketEmotionSnapshotResponse,
    SentimentSummaryMetrics,
    SentimentSummaryResponse,
    ShortTermSentimentIndustryItem,
)
from app.services.sentiment_decision import build_sentiment_decision


def _summary(
    *,
    score: float,
    limit_up: int,
    break_board: int,
    limit_down: int,
    seal_rate: float,
    advance: int = 3000,
    decline: int = 2000,
    turnover_change_pct: float = 3,
) -> SentimentSummaryResponse:
    return SentimentSummaryResponse(
        trade_date="2026-07-02",
        metrics=SentimentSummaryMetrics(
            emotion_score=score,
            emotion_level="良好",
            limit_up_count=limit_up,
            break_board_count=break_board,
            limit_down_count=limit_down,
            advance_count=advance,
            decline_count=decline,
            seal_rate_pct=seal_rate,
            turnover_change_pct=turnover_change_pct,
        ),
        hot_industries=[
            ShortTermSentimentIndustryItem(
                name="存储芯片",
                limit_up_count=8,
                break_board_count=1,
                max_consecutive_boards=3,
                leader="德明利",
                symbols=["001309.SZ"],
                strength_score=90,
            )
        ],
    )


def _emotion(score: float, samples: list[float]) -> MarketEmotionSnapshotResponse:
    return MarketEmotionSnapshotResponse(
        trade_date="2026-07-02",
        metrics=MarketEmotionMetrics(emotion_score=score, emotion_level="良好"),
        samples=[
            {
                "trade_date": "2026-07-02",
                "sampled_at": f"2026-07-02T09:{30 + index:02d}:00+08:00",
                "emotion_score": item,
                "emotion_level": "一般",
                "limit_up_count": 10,
                "break_board_count": 2,
                "max_consecutive_boards": 2,
            }
            for index, item in enumerate(samples)
        ],
    )


def test_decision_marks_repair_as_light_trial() -> None:
    decision = build_sentiment_decision(
        summary=_summary(score=58, limit_up=55, break_board=8, limit_down=2, seal_rate=78),
        market_emotion=_emotion(58, [40, 47, 58]),
    )

    assert decision.market_state == "修复"
    assert decision.trade_permission == "轻仓试错"
    assert decision.risk_level == "中"
    assert decision.main_sectors[0].name == "存储芯片"
    assert "情绪分数回升" in decision.reasons


def test_decision_marks_retreat_as_cash_wait() -> None:
    decision = build_sentiment_decision(
        summary=_summary(
            score=22,
            limit_up=18,
            break_board=28,
            limit_down=35,
            seal_rate=39,
            advance=900,
            decline=4200,
            turnover_change_pct=-6,
        ),
        market_emotion=_emotion(22, [52, 39, 22]),
    )

    assert decision.market_state == "退潮"
    assert decision.trade_permission == "空仓等待"
    assert decision.risk_level == "高"
    assert "跌停与炸板压力高" in decision.risks


def test_decision_marks_climax_as_sell_not_chase() -> None:
    decision = build_sentiment_decision(
        summary=_summary(
            score=84,
            limit_up=130,
            break_board=22,
            limit_down=1,
            seal_rate=86,
            turnover_change_pct=12,
        ),
        market_emotion=_emotion(84, [65, 76, 84]),
    )

    assert decision.market_state == "高潮"
    assert decision.trade_permission == "只卖不追"
    assert decision.risk_level == "中"
    assert "情绪过热，避免追高" in decision.risks
