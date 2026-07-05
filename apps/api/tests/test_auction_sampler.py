from datetime import datetime

from app.services.auction_sampler import (
    AuctionSnapshotSampler,
    is_auction_sample_window,
    is_auction_top3_lock_window,
    is_trading_day,
)


def test_auction_sample_window_covers_0925_lock_period() -> None:
    assert not is_auction_sample_window(datetime(2026, 7, 1, 9, 14, 29))
    assert is_auction_sample_window(datetime(2026, 7, 1, 9, 14, 30))
    assert is_auction_sample_window(datetime(2026, 7, 1, 9, 25, 0))
    assert is_auction_sample_window(datetime(2026, 7, 1, 9, 25, 30))
    assert not is_auction_sample_window(datetime(2026, 7, 1, 9, 25, 31))
    assert not is_auction_sample_window(datetime(2026, 7, 1, 9, 30, 30))


def test_auction_sampler_samples_only_inside_window() -> None:
    calls: list[str] = []
    current = datetime(2026, 7, 1, 9, 13, 0)

    def refresh() -> None:
        calls.append("refresh")

    sampler = AuctionSnapshotSampler(refresh=refresh, clock=lambda: current)

    assert sampler.sample_once() is False
    assert calls == []

    current = datetime(2026, 7, 1, 9, 24, 50)
    assert sampler.sample_once() is True
    assert calls == ["refresh"]


def test_auction_top3_lock_window_runs_after_0925_and_before_0930_on_trading_day() -> None:
    assert is_trading_day(datetime(2026, 7, 1, 9, 25, 3))
    assert not is_trading_day(datetime(2026, 7, 5, 9, 25, 3))
    assert not is_auction_top3_lock_window(datetime(2026, 7, 1, 9, 25, 2))
    assert is_auction_top3_lock_window(datetime(2026, 7, 1, 9, 25, 3))
    assert is_auction_top3_lock_window(datetime(2026, 7, 1, 9, 29, 59))
    assert not is_auction_top3_lock_window(datetime(2026, 7, 1, 9, 30, 0))
    assert not is_auction_top3_lock_window(datetime(2026, 7, 5, 9, 25, 3))


def test_auction_sampler_generates_top3_once_per_trade_date_after_lock_time() -> None:
    calls: list[str] = []
    current = datetime(2026, 7, 1, 9, 25, 2)

    def refresh() -> None:
        pass

    sampler = AuctionSnapshotSampler(
        refresh=refresh,
        run_top3=lambda trade_date: calls.append(trade_date),
        clock=lambda: current,
    )

    assert sampler.sample_once() is True
    assert calls == []

    current = datetime(2026, 7, 1, 9, 25, 3)
    assert sampler.sample_once() is True
    assert calls == ["2026-07-01"]

    current = datetime(2026, 7, 1, 9, 25, 20)
    assert sampler.sample_once() is True
    assert calls == ["2026-07-01"]

    current = datetime(2026, 7, 2, 9, 25, 3)
    assert sampler.sample_once() is True
    assert calls == ["2026-07-01", "2026-07-02"]


def test_auction_sampler_does_not_generate_top3_on_weekends() -> None:
    calls: list[str] = []

    sampler = AuctionSnapshotSampler(
        refresh=lambda: None,
        run_top3=lambda trade_date: calls.append(trade_date),
        clock=lambda: datetime(2026, 7, 5, 9, 25, 3),
    )

    assert sampler.sample_once() is True
    assert calls == []


def test_auction_sampler_retries_top3_after_failure_inside_lock_window() -> None:
    attempts: list[str] = []
    current = datetime(2026, 7, 1, 9, 25, 3)

    def run_top3(trade_date: str) -> None:
        attempts.append(trade_date)
        if len(attempts) == 1:
            raise RuntimeError("source temporarily unavailable")

    sampler = AuctionSnapshotSampler(
        refresh=lambda: None,
        run_top3=run_top3,
        clock=lambda: current,
    )

    assert sampler.sample_once() is True
    assert attempts == ["2026-07-01"]
    assert sampler.top3_status()["status"] == "failed"

    current = datetime(2026, 7, 1, 9, 25, 10)
    assert sampler.sample_once() is True
    assert attempts == ["2026-07-01", "2026-07-01"]
    assert sampler.top3_status()["status"] == "generated"
