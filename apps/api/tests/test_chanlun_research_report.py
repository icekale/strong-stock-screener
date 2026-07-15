from __future__ import annotations

import subprocess
import sys
import json
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.chanlun.research_score_cache import ResearchScoreableUniverse

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


def test_html_report_exposes_portfolio_curves_and_promotion_gates(tmp_path: Path) -> None:
    write_validation_report(
        _validation_result(),
        output=tmp_path / "report",
        generated_at="2026-07-13T10:00:00+08:00",
    )

    html = (tmp_path / "report/report.html").read_text(encoding="utf-8")

    assert "Top3" in html
    assert "Top5" in html
    assert "Top10" in html
    assert "累计净收益" in html
    assert "最大回撤" in html
    assert "晋级门槛" in html


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
    assert "score" in result.stdout
    assert "validate" in result.stdout


def test_research_cli_preserves_rc8_virtualenv_interpreter_path() -> None:
    repo_root = Path(__file__).parents[3]
    spec = importlib.util.spec_from_file_location(
        "czsc_research_cli",
        repo_root / "scripts/czsc-research.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    worker = module._build_worker("apps/api/rc8-worker/.venv/bin/python", object())
    assert worker is not None
    try:
        assert worker._python_path.endswith("apps/api/rc8-worker/.venv/bin/python")
    finally:
        worker.close()


def test_research_cli_score_loads_only_scoreable_pending_samples(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_research_cli()
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "manifest.json").write_text(
        json.dumps(
            {
                "dataset_id": "sha256:dataset",
                "samples": [
                    {"symbol": "600000.SH", "decision_date": "2026-06-01"},
                    {"symbol": "000001.SZ", "decision_date": "2021-07-01"},
                ],
                "partitions": [],
            }
        ),
        encoding="utf-8",
    )
    selected: list[set[tuple[str, str]]] = []
    worker = SimpleNamespace(close=lambda: None)
    frozen = SimpleNamespace(
        candidates_by_date={
            "2026-06-01": [
                {
                    "symbol": "600000.SH",
                    "decision_date": "2026-06-01",
                    "baseline_rank": 1,
                }
            ]
        }
    )
    monkeypatch.setattr(module, "verify_dataset_manifest", lambda path: None)
    monkeypatch.setattr(
        module,
        "derive_scoreable_universe",
        lambda **kwargs: ResearchScoreableUniverse(
            keys=frozenset({("600000.SH", "2026-06-01")}),
            start_date="2026-06-01",
            end_date="2026-06-01",
            dataset_candidate_count=2,
        ),
        raising=False,
    )
    monkeypatch.setattr(module, "_build_worker", lambda *args: worker)
    monkeypatch.setattr(
        module,
        "load_frozen_dataset",
        lambda root, *, selected_samples: selected.append(selected_samples) or frozen,
    )
    monkeypatch.setattr(module, "_build_score_candidate", lambda *args: lambda candidate: (75, True))

    result = module._score(
        SimpleNamespace(
            dataset=dataset,
            score_cache=tmp_path / "scores.json",
            worker_python="worker-python",
            batch_size=300,
            save_every=25,
        )
    )

    assert result == 0
    assert selected == [{("600000.SH", "2026-06-01")}]


def test_cached_validation_filters_candidates_to_scoreable_keys() -> None:
    module = _load_research_cli()

    filtered = module._filter_candidates_by_keys(
        {
            "2026-06-01": [
                {"symbol": "600000.SH", "decision_date": "2026-06-01"},
                {"symbol": "000001.SZ", "decision_date": "2026-06-01"},
            ],
            "2021-07-01": [
                {"symbol": "600000.SH", "decision_date": "2021-07-01"},
            ],
        },
        {("600000.SH", "2026-06-01")},
    )

    assert filtered == {
        "2026-06-01": [
            {"symbol": "600000.SH", "decision_date": "2026-06-01"},
        ]
    }


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


def test_research_cli_validate_reads_frozen_files_and_writes_report(tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    dataset_root = tmp_path / "datasets" / "dataset-test"
    dataset_root.mkdir(parents=True)
    partition = dataset_root / "daily.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "date": "20260101",
                    "code": "600000",
                    "close": 11.0,
                    "prev_close": 10.0,
                    "open": 10.0,
                    "high": 11.2,
                    "low": 9.9,
                    "volume": 1000.0,
                    "amount": 11000.0,
                },
                {
                    "date": "20260102",
                    "code": "600000",
                    "close": 11.2,
                    "prev_close": 11.0,
                    "open": 11.0,
                    "high": 11.4,
                    "low": 10.9,
                    "volume": 1000.0,
                    "amount": 11200.0,
                },
                {
                    "date": "20260103",
                    "code": "600000",
                    "close": 11.4,
                    "prev_close": 11.2,
                    "open": 11.2,
                    "high": 11.6,
                    "low": 11.1,
                    "volume": 1000.0,
                    "amount": 11400.0,
                },
                {
                    "date": "20260104",
                    "code": "600000",
                    "close": 11.6,
                    "prev_close": 11.4,
                    "open": 11.4,
                    "high": 11.8,
                    "low": 11.3,
                    "volume": 1000.0,
                    "amount": 11600.0,
                },
            ]
        ),
        partition,
    )
    digest = hashlib.sha256(partition.read_bytes()).hexdigest()
    (dataset_root / "manifest.json").write_text(
        json.dumps(
            {
                "dataset_id": "sha256:dataset",
                "start": "2026-01-01",
                "end": "2026-01-04",
                "source": "fixture",
                "adjustment_mode": "source_qfq",
                "quality": {},
                "partitions": [
                    {
                        "path": "dataset-test/daily.parquet",
                        "sha256": f"sha256:{digest}",
                        "row_count": 4,
                    }
                ],
                "samples": [
                    {
                        "symbol": "600000.SH",
                        "decision_date": "2026-01-01",
                        "baseline_rank": 1,
                    }
                ],
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

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "validated"
    assert (tmp_path / "report/metrics.json").exists()
    assert (tmp_path / "report/report.html").exists()


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


def _load_research_cli():
    repo_root = Path(__file__).parents[3]
    spec = importlib.util.spec_from_file_location(
        "czsc_research_cli_test",
        repo_root / "scripts/czsc-research.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
