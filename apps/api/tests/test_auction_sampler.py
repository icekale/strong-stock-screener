from datetime import datetime

from app.services.auction_sampler import AuctionSnapshotSampler, is_auction_sample_window


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
