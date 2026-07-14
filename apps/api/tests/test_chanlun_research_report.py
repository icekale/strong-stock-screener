from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path

from app.services.chanlun.research_report import (
    ValidationReportInput,
    write_validation_report,
)


def test_report_payload_and_sample_hashes_are_reproducible(tmp_path: Path) -> None:
    result = _validation_result()

    first = write_validation_report(
        result,
        output=tmp_path / "first",
        generated_at="2026-07-13T10:00:00+08:00",
    )
    second = write_validation_report(
        result,
        output=tmp_path / "second",
        generated_at="2026-07-13T11:00:00+08:00",
    )

    assert first.metrics_sha256 == second.metrics_sha256
    assert first.samples_sha256 == second.samples_sha256
    assert first.html_sha256 != second.html_sha256
    assert (tmp_path / "first/checksums.sha256").exists()
    assert (tmp_path / "first/samples.csv.gz").exists()


def test_research_cli_help_lists_dataset_and_validation_commands() -> None:
    repo_root = Path(__file__).parents[3]
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts/czsc-research.py"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "build-dataset" in result.stdout
    assert "validate" in result.stdout


def test_research_cli_validate_rejects_a_tampered_partition(tmp_path: Path) -> None:
    dataset_root = tmp_path / "datasets" / "dataset-test"
    dataset_root.mkdir(parents=True)
    partition = dataset_root / "daily.parquet"
    partition.write_bytes(b"tampered")
    (dataset_root / "manifest.json").write_text(
        json.dumps(
            {
                "partitions": [
                    {"path": "dataset-test/daily.parquet", "sha256": "sha256:wrong"}
                ]
            }
        ),
        encoding="utf-8",
    )
    repo_root = Path(__file__).parents[3]

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts/czsc-research.py"),
            "validate",
            "--dataset",
            str(dataset_root),
            "--output",
            str(tmp_path / "report"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "checksum mismatch" in result.stderr


def _validation_result() -> ValidationReportInput:
    return ValidationReportInput(
        manifest={"dataset_id": "sha256:dataset", "quality": {"adjustment_mismatch_count": 0}},
        metrics={
            "top3": {"baseline_net_return_pct": 1.0, "v2_net_return_pct": 2.0},
            "top5": {"baseline_net_return_pct": 2.0, "v2_net_return_pct": 3.0},
            "top10": {"baseline_net_return_pct": 3.0, "v2_net_return_pct": 4.0},
            "win_rate_pct": 55.0,
            "profit_loss_ratio": 1.5,
            "max_drawdown_pct": -8.0,
        },
        folds=[{"test_start": "2026-01-01", "test_end": "2026-06-30"}],
        samples=[
            {"decision_date": "2026-01-02", "symbol": "600000.SH", "baseline_rank": 1, "net_return_pct": 1.2},
            {"decision_date": "2026-01-03", "symbol": "000001.SZ", "baseline_rank": 2, "net_return_pct": -0.4},
        ],
        recommendation="keep_shadow",
    )
