from __future__ import annotations

from datetime import datetime

from app.services.auction_sampler import AuctionSnapshotSampler
from app.services.background_sampler import BackgroundLoopSampler
from app.services.capital_signal_sampler import CapitalSignalSampler
from app.services.etf_three_factor_sampler import EtfThreeFactorSampler
from app.services.sector_workbench_sampler import SectorWorkbenchSampler


def test_background_loop_sampler_defaults_clock_when_omitted() -> None:
    class Probe(BackgroundLoopSampler):
        def sample_once(self) -> bool:
            now = self._clock()
            assert isinstance(now, datetime)
            return False

    assert Probe(thread_name="probe").sample_once() is False


def test_production_samplers_can_sample_once_without_injected_clock() -> None:
    AuctionSnapshotSampler(refresh=lambda: None).sample_once()
    SectorWorkbenchSampler(refresh=lambda: None).sample_once()
    CapitalSignalSampler(refresh=lambda: None).sample_once()
    EtfThreeFactorSampler(scan=lambda **_kwargs: None).sample_once()
