from __future__ import annotations

import gc
from datetime import date, timedelta
from pathlib import Path
import pytest

from app.models import KlineBar
import app.services.chanlun.research_dataset as research_dataset
from app.services.chanlun.research_dataset import (
    ResearchDatasetBuilder,
    load_frozen_dataset,
    reconstruct_candidates,
)



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


def test_dataset_keeps_each_decision_date_and_symbol_month_minute_partitions(tmp_path: Path) -> None:
    manifest = ResearchDatasetBuilder(source=MultiDayHistorySource()).build(
        start="2026-06-01",
        end="2026-07-10",
        output=tmp_path,
    )

    decision_dates = {sample.decision_date for sample in manifest.samples}
    assert decision_dates == {"2026-06-20", "2026-06-21"}
    assert any(
        "minute/symbol=600000_SH/month=2026-06.parquet" in partition.path
        for partition in manifest.partitions
    )
    assert any(partition.path == "daily/year=2026.parquet" for partition in manifest.partitions)

    frozen = load_frozen_dataset(manifest.root)
    assert frozen.candidates_by_date["2026-06-21"][0]["baseline_rank"] == 1
    assert frozen.daily_bars_by_symbol["600000.SH"][-1].date == "2026-06-21T00:00:00+08:00"


def test_frozen_dataset_loading_temporarily_disables_cyclic_gc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = ResearchDatasetBuilder(source=MultiDayHistorySource()).build(
        start="2026-06-01",
        end="2026-07-10",
        output=tmp_path,
    )
    observed: list[bool] = []
    original = research_dataset._daily_bar_from_row

    def observe_gc(row: dict[str, object]) -> object:
        observed.append(gc.isenabled())
        return original(row)

    monkeypatch.setattr(research_dataset, "_daily_bar_from_row", observe_gc)
    assert gc.isenabled()

    load_frozen_dataset(manifest.root)

    assert observed
    assert not any(observed)
    assert gc.isenabled()


def test_frozen_dataset_can_skip_minute_partitions(tmp_path: Path) -> None:
    manifest = ResearchDatasetBuilder(source=MultiDayHistorySource()).build(
        start="2026-06-01",
        end="2026-07-10",
        output=tmp_path,
    )

    frozen = load_frozen_dataset(manifest.root, include_minute=False)

    assert frozen.daily_bars_by_symbol["600000.SH"]
    assert frozen.minute_bars_by_symbol == {}


def test_frozen_dataset_can_load_only_selected_samples(tmp_path: Path) -> None:
    manifest = ResearchDatasetBuilder(source=MultiDayHistorySource()).build(
        start="2026-06-01",
        end="2026-07-10",
        output=tmp_path,
    )

    frozen = load_frozen_dataset(
        manifest.root,
        selected_samples={("600000.SH", "2026-06-21")},
    )

    assert set(frozen.candidates_by_date) == {"2026-06-21"}
    assert frozen.candidates_by_date["2026-06-21"][0]["symbol"] == "600000.SH"
    assert set(frozen.daily_bars_by_symbol) == {"600000.SH"}
    assert set(frozen.minute_bars_by_symbol) == {"600000.SH"}


def test_chunked_dataset_resume_skips_completed_source_chunks(tmp_path: Path) -> None:
    source = ResumableHistorySource(fail_on="202607")
    builder = ResearchDatasetBuilder(source=source)

    with pytest.raises(RuntimeError, match="simulated month failure"):
        builder.build(start="2026-06-01", end="2026-07-03", output=tmp_path)

    progress_files = list(tmp_path.glob(".dataset-building-*/progress.json"))
    assert len(progress_files) == 1

    resumed_source = ResumableHistorySource()
    manifest = ResearchDatasetBuilder(source=resumed_source, resume=True).build(
        start="2026-06-01",
        end="2026-07-03",
        output=tmp_path,
    )

    assert resumed_source.requested_chunks == ["202607"]
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


class MultiDayHistorySource:
    adjustment_mode = "source_qfq"

    def daily_rows(self, *, start: str, end: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for index in range(21):
            trade_date = date(2026, 6, 1) + timedelta(days=index)
            rows.append(
                {
                    "date": trade_date.strftime("%Y%m%d"),
                    "code": "600000",
                    "name": "正常股份",
                    "prev_close": 10,
                    "close": 11,
                    "float_mv": 5_000_000_000,
                    "total_mv": 8_000_000_000,
                    "industry": "计算机",
                }
            )
        return rows

    def daily_rows_by_year(self, *, start: str, end: str):
        yield 2026, self.daily_rows(start=start, end=end)

    def minute_bars(self, symbol: str, *, start: str, end: str) -> list[KlineBar]:
        return [
            KlineBar(
                date="2026-06-30T09:30:00+08:00",
                open=10,
                high=10.2,
                low=9.9,
                close=10.1,
                volume=1000,
                amount=10100,
            )
        ]


class ResumableHistorySource:
    adjustment_mode = "source_qfq"

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.requested_chunks: list[str] = []

    def daily_rows_by_year(self, *, start: str, end: str, skip_chunks: set[str] | None = None):
        for chunk, rows in (("202606", _resumable_rows("2026-06-01", 20)), ("202607", _resumable_rows("2026-07-01", 1))):
            if chunk in (skip_chunks or set()):
                continue
            self.requested_chunks.append(chunk)
            if chunk == self.fail_on:
                raise RuntimeError("simulated month failure")
            yield chunk, rows

    def minute_bars(self, symbol: str, *, start: str, end: str) -> list[KlineBar]:
        return []


def _resumable_rows(start: str, count: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    first = date.fromisoformat(start)
    for index in range(count):
        trade_date = first + timedelta(days=index)
        rows.append(
            {
                "date": trade_date.strftime("%Y%m%d"),
                "code": "600000",
                "name": "正常股份",
                "prev_close": 10,
                "close": 11,
            }
        )
    return rows
