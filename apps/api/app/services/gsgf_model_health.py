from __future__ import annotations

from app.models import GsgfModelHealth, GsgfRealCalibrationSummary, GsgfReviewSummary


def build_gsgf_model_health(
    review: GsgfReviewSummary | None,
    calibration: GsgfRealCalibrationSummary | None,
) -> GsgfModelHealth:
    best: list[str] = []
    weak: list[str] = []
    insufficient: list[str] = []
    degraded: list[str] = []

    if review is not None:
        for bucket in review.buckets:
            name = bucket.signal_type
            if bucket.sample_count < 5:
                insufficient.append(name)
                continue
            confirmation_rate = bucket.confirmed_count / max(bucket.sample_count, 1)
            if (bucket.avg_return_pct or 0) < 0 or (bucket.avg_max_drawdown_pct or 0) <= -5:
                degraded.append(name)
            elif (bucket.avg_return_pct or 0) > 0 and confirmation_rate >= 0.6:
                best.append(name)
            else:
                weak.append(name)

    if calibration is not None:
        for bucket in calibration.buckets:
            if bucket.sample_count < 5:
                insufficient.append(bucket.name)
            elif bucket.calibration_rating in {"强", "中强"}:
                best.append(bucket.name)
            elif bucket.calibration_rating == "弱":
                weak.append(bucket.name)

    return GsgfModelHealth(
        best_signals=_dedupe(best),
        weak_signals=_dedupe(weak),
        insufficient_sample_signals=_dedupe(insufficient),
        degraded_signals=_dedupe(degraded),
        last_review_at=review.generated_at if review else None,
        last_calibration_at=calibration.generated_at if calibration else None,
        summary_text=_summary_text(best, weak, insufficient, degraded),
    )


def _summary_text(
    best: list[str],
    weak: list[str],
    insufficient: list[str],
    degraded: list[str],
) -> str:
    lines: list[str] = []
    if degraded:
        lines.append(f"退化信号：{'、'.join(_dedupe(degraded))}")
    if best:
        lines.append(f"较可靠信号：{'、'.join(_dedupe(best))}")
    if weak:
        lines.append(f"偏弱信号：{'、'.join(_dedupe(weak))}")
    if insufficient:
        lines.append(f"样本不足：{'、'.join(_dedupe(insufficient))}")
    if not lines:
        lines.append("暂无足够 GSGF 复盘样本。")
    lines.append("仅供复盘与模型校准，不构成投资建议。")
    return "\n".join(lines)


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output
