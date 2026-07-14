from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ValidationReportInput:
    manifest: dict[str, Any]
    metrics: dict[str, Any]
    folds: list[dict[str, Any]]
    samples: list[dict[str, Any]]
    recommendation: str


@dataclass(frozen=True)
class ValidationReportArtifacts:
    output: Path
    metrics_sha256: str
    samples_sha256: str
    html_sha256: str


def write_validation_report(
    result: ValidationReportInput,
    *,
    output: Path,
    generated_at: str,
) -> ValidationReportArtifacts:
    output.mkdir(parents=True, exist_ok=True)
    manifest_bytes = _json_bytes(result.manifest)
    metrics_bytes = _json_bytes(result.metrics)
    folds_bytes = _json_bytes(result.folds)
    samples_bytes = _samples_gzip_bytes(result.samples)
    html_bytes = _html_bytes(result, generated_at)

    _write_bytes(output / "manifest.json", manifest_bytes)
    _write_bytes(output / "metrics.json", metrics_bytes)
    _write_bytes(output / "folds.json", folds_bytes)
    _write_bytes(output / "samples.csv.gz", samples_bytes)
    _write_bytes(output / "report.html", html_bytes)

    checksums = {
        "manifest.json": _sha256(manifest_bytes),
        "metrics.json": _sha256(metrics_bytes),
        "folds.json": _sha256(folds_bytes),
        "samples.csv.gz": _sha256(samples_bytes),
        "report.html": _sha256(html_bytes),
    }
    checksum_text = "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items()))
    _write_bytes(output / "checksums.sha256", checksum_text.encode("utf-8"))
    return ValidationReportArtifacts(
        output=output,
        metrics_sha256=checksums["metrics.json"],
        samples_sha256=checksums["samples.csv.gz"],
        html_sha256=checksums["report.html"],
    )


def verify_dataset_manifest(manifest_path: Path) -> None:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent
    for partition in payload.get("partitions", []):
        path = root.parent / partition["path"]
        if not path.exists() or f"sha256:{_sha256(path.read_bytes())}" != partition["sha256"]:
            raise ValueError(f"dataset checksum mismatch: {partition.get('path')}")


def _samples_gzip_bytes(samples: list[dict[str, Any]]) -> bytes:
    ordered = sorted(
        samples,
        key=lambda row: (
            str(row.get("decision_date", "")),
            str(row.get("symbol", "")),
            int(row.get("baseline_rank", 0)),
        ),
    )
    fieldnames = sorted({key for row in ordered for key in row})
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(ordered)
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as handle:
        handle.write(text.getvalue().encode("utf-8"))
    return buffer.getvalue()


def _html_bytes(result: ValidationReportInput, generated_at: str) -> bytes:
    metrics = result.metrics
    rows = "".join(
        f"<tr><td>{name}</td><td>{json.dumps(value, ensure_ascii=False, sort_keys=True)}</td></tr>"
        for name, value in sorted(metrics.items())
    )
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>CZSC 研究验证报告</title></head>
<body><main>
<h1>CZSC 五年影子验证</h1>
<p>生成时间：{generated_at}</p>
<p>推荐结论：{result.recommendation}</p>
<h2>指标</h2><table><tbody>{rows}</tbody></table>
<h2>数据质量</h2><pre>{json.dumps(result.manifest.get("quality", {}), ensure_ascii=False, sort_keys=True)}</pre>
<h2>折叠</h2><pre>{json.dumps(result.folds, ensure_ascii=False, sort_keys=True)}</pre>
<h2>样本曲线</h2><p>样本数量：{len(result.samples)}</p>
</main></body></html>"""
    return html.encode("utf-8")


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _write_bytes(path: Path, payload: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
