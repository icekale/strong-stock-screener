from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from app.models import KlineBar
from app.services.chanlun.research_dataset import ResearchDatasetBuilder, reconstruct_candidates


def test_candidate_reconstruction_uses_only_prior_20_sessions() -> None:
    rows: list[dict[str, object]] = []
    for index in range(20):
        trade_date = date(2026, 6, 15) + timedelta(days=index)
        rows.append(
            {
                "date": trade_date.strftime("%Y%m%d"),
                "code": "600000",
                "name": "测试股份",
                "prev_close": 10,
                "close": 11.0 if index >= 18 else 10.0,
                "float_mv": 5_000_000_000,
                "total_mv": 8_000_000_000,
                "industry": "计算机",
            }
        )
    rows.extend(
        [
            {
                "date": "20260710",
                "code": "600001",
                "name": "ST风险股份",
                "prev_close": 10,
                "close": 11,
            },
            {
                "date": "20260711",
                "code": "600002",
                "name": "未来股份",
                "prev_close": 10,
                "close": 11,
            },
        ]
    )

    candidates = reconstruct_candidates(rows, trade_date="2026-07-10")

    assert all(item.last_limit_up_date <= "2026-07-10" for item in candidates)
    assert all("ST" not in item.candidate.name.upper() for item in candidates)
    assert candidates[0].limit_up_hits_20d >= candidates[-1].limit_up_hits_20d
    assert [item.candidate.symbol for item in candidates] == ["600000.SH"]


def test_dataset_manifest_records_checksums_and_rejects_adjustment_break(tmp_path: Path) -> None:
    builder = ResearchDatasetBuilder(source=FakeHistorySource(with_adjustment_break=True))

    manifest = builder.build(start="2026-01-01", end="2026-06-30", output=tmp_path)

    assert manifest.quality.adjustment_mismatch_count > 0
    assert all(part.sha256.startswith("sha256:") for part in manifest.partitions)
    assert not any(sample.symbol == "BROKEN.SZ" for sample in manifest.samples)
    assert (manifest.root / "manifest.json").exists()


class FakeHistorySource:
    adjustment_mode = "source_qfq"

    def __init__(self, *, with_adjustment_break: bool) -> None:
        self.with_adjustment_break = with_adjustment_break

    def daily_rows(self, *, start: str, end: str) -> list[dict[str, object]]:
        return [
            {
                "date": "20260630",
                "code": "600000",
                "name": "正常股份",
                "prev_close": 10,
                "close": 11,
                "float_mv": 5_000_000_000,
                "total_mv": 8_000_000_000,
                "industry": "计算机",
            },
            {
                "date": "20260630",
                "code": "300001",
                "name": "断裂股份" if self.with_adjustment_break else "创业股份",
                "prev_close": 10,
                "close": 12,
                "float_mv": 5_000_000_000,
                "total_mv": 8_000_000_000,
                "industry": "计算机",
                "adjustment_break": self.with_adjustment_break,
            },
        ]

    def minute_bars(self, symbol: str, *, start: str, end: str) -> list[KlineBar]:
        return [
            KlineBar(
                date="2026-06-30T14:55:00+08:00",
                open=10,
                high=10.2,
                low=9.9,
                close=10.1,
                volume=1000,
                amount=10100,
            )
        ]
