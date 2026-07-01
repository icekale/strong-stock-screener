from app.models import (
    GsgfCalibrationBucket,
    GsgfRealCalibrationSummary,
    GsgfReviewBucket,
    GsgfReviewSummary,
)
from app.services.gsgf_model_health import build_gsgf_model_health


def test_gsgf_model_health_marks_best_and_insufficient_signals() -> None:
    review = GsgfReviewSummary(
        record_count=8,
        buckets=[
            GsgfReviewBucket(
                signal_type="放量突破确认",
                status="确认买点",
                sample_count=6,
                confirmed_count=5,
                avg_return_pct=2.4,
                avg_max_drawdown_pct=-1.8,
            ),
            GsgfReviewBucket(
                signal_type="星线后确认",
                status="确认买点",
                sample_count=2,
                confirmed_count=2,
                avg_return_pct=1.2,
                avg_max_drawdown_pct=-0.5,
            ),
        ],
    )
    calibration = GsgfRealCalibrationSummary(
        buckets=[
            GsgfCalibrationBucket(
                name="放量突破确认",
                sample_count=8,
                composite_score=63,
                calibration_rating="中强",
            ),
        ]
    )

    health = build_gsgf_model_health(review, calibration)

    assert "放量突破确认" in health.best_signals
    assert "星线后确认" in health.insufficient_sample_signals
    assert health.last_review_at == review.generated_at
    assert health.last_calibration_at == calibration.generated_at


def test_gsgf_model_health_marks_degraded_core_signal() -> None:
    review = GsgfReviewSummary(
        record_count=6,
        buckets=[
            GsgfReviewBucket(
                signal_type="放量突破确认",
                status="确认买点",
                sample_count=6,
                confirmed_count=1,
                avg_return_pct=-1.1,
                avg_max_drawdown_pct=-6.2,
            )
        ],
    )

    health = build_gsgf_model_health(review, None)

    assert "放量突破确认" in health.degraded_signals
    assert "仅供复盘与模型校准" in health.summary_text
