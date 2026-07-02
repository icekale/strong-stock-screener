from pathlib import Path

from app.models import SentimentDecisionResponse
from app.services.sentiment_review import score_sentiment_decision
from app.services.sentiment_review_store import SentimentReviewStore


def _decision(trade_date: str, permission: str) -> SentimentDecisionResponse:
    return SentimentDecisionResponse(
        trade_date=trade_date,
        market_state="修复",
        trade_permission=permission,
        risk_level="中",
        confidence=80,
        reasons=["情绪分数回升"],
    )


def test_sentiment_review_store_persists_decision(tmp_path: Path) -> None:
    store = SentimentReviewStore(tmp_path)
    store.save_decision(_decision("2026-07-02", "轻仓试错"))

    loaded = store.load_decisions("2026-07-02")

    assert len(loaded) == 1
    assert loaded[0].trade_date == "2026-07-02"
    assert loaded[0].trade_permission == "轻仓试错"


def test_sentiment_review_store_dedupes_same_generated_decision(tmp_path: Path) -> None:
    store = SentimentReviewStore(tmp_path)
    decision = _decision("2026-07-02", "轻仓试错")
    store.save_decision(decision)
    store.save_decision(decision)

    loaded = store.load_decisions("2026-07-02")

    assert len(loaded) == 1


def test_score_sentiment_decision_rewards_correct_risk_off_call() -> None:
    result = score_sentiment_decision(
        decision=_decision("2026-07-02", "空仓等待"),
        next_day_index_pct=-2.1,
        next_day_limit_up_count=18,
        next_day_limit_down_count=42,
    )

    assert result.hit is True
    assert result.score > 0
    assert "空仓等待规避退潮" in result.reason


def test_score_sentiment_decision_penalizes_mismatched_permission() -> None:
    result = score_sentiment_decision(
        decision=_decision("2026-07-02", "强势进攻"),
        next_day_index_pct=-1.8,
        next_day_limit_up_count=22,
        next_day_limit_down_count=34,
    )

    assert result.hit is False
    assert result.score < 0
    assert "不匹配" in result.reason
