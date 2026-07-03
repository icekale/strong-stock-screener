from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.sector_workbench_sampler import SectorWorkbenchSampler, is_sector_workbench_sample_window


def test_sector_workbench_sampler_samples_only_inside_market_window() -> None:
    calls: list[str] = []
    current = datetime(2026, 7, 3, 9, 25, tzinfo=ZoneInfo("Asia/Shanghai"))

    def refresh() -> None:
        calls.append("sampled")

    sampler = SectorWorkbenchSampler(refresh=refresh, clock=lambda: current)

    assert sampler.sample_once() is False
    assert calls == []

    current = datetime(2026, 7, 3, 9, 35, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert is_sector_workbench_sample_window(current) is True
    assert sampler.sample_once() is True
    assert calls == ["sampled"]

    current = datetime(2026, 7, 3, 11, 45, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert sampler.sample_once() is False
    assert calls == ["sampled"]

    current = datetime(2026, 7, 3, 13, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert sampler.sample_once() is True
    assert calls == ["sampled", "sampled"]
