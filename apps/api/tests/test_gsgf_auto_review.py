from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.gsgf_auto_review import GsgfAutoReviewConfig, GsgfAutoReviewService


def test_auto_review_runs_daily_review_once_after_configured_time() -> None:
    calls: list[str] = []
    service = GsgfAutoReviewService(
        config_loader=lambda: GsgfAutoReviewConfig(
            daily_review_enabled=True,
            weekly_calibration_enabled=False,
        ),
        review_runner=lambda: calls.append("review"),
        calibration_runner=lambda _dates, _windows, _scan_limit, _count: calls.append(
            "calibration"
        ),
        recent_trade_dates=lambda count: ["2026-06-24"][:count],
        notifier=lambda _title, _message: None,
        now_fn=lambda: datetime(2026, 7, 1, 15, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    service.run_once()
    service.run_once()

    assert calls == ["review"]


def test_auto_review_runs_weekly_calibration_once() -> None:
    calls: list[tuple[list[str], list[int], int, int]] = []
    service = GsgfAutoReviewService(
        config_loader=lambda: GsgfAutoReviewConfig(
            daily_review_enabled=False,
            weekly_calibration_enabled=True,
            weekly_calibration_weekday=5,
            weekly_calibration_time="16:10",
            weekly_calibration_trade_days=2,
            weekly_calibration_scan_limit=80,
            windows=[1, 3, 5, 10],
            kline_count=260,
        ),
        review_runner=lambda: None,
        calibration_runner=lambda dates, windows, scan_limit, count: calls.append(
            (dates, windows, scan_limit, count)
        ),
        recent_trade_dates=lambda count: ["2026-06-25", "2026-06-26"][:count],
        notifier=lambda _title, _message: None,
        now_fn=lambda: datetime(2026, 7, 3, 16, 20, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    service.run_once()
    service.run_once()

    assert calls == [(["2026-06-25", "2026-06-26"], [1, 3, 5, 10], 80, 260)]
