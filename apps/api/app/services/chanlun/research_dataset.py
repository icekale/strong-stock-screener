from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from typing import Iterable

from app.models import StrongStockCandidate


@dataclass(frozen=True)
class ResearchCandidateRecord:
    candidate: StrongStockCandidate
    last_limit_up_date: str
    limit_up_hits_20d: int
    decision_date: str


@dataclass(frozen=True)
class DatasetPartition:
    path: str
    sha256: str
    row_count: int
    start_date: str | None
    end_date: str | None


@dataclass(frozen=True)
class DatasetQuality:
    adjustment_mismatch_count: int = 0
    invalid_row_count: int = 0
    duplicate_row_count: int = 0


@dataclass(frozen=True)
class DatasetSample:
    symbol: str
    decision_date: str
    baseline_rank: int


@dataclass(frozen=True)
class ResearchDatasetManifest:
    dataset_id: str
    root: Path
    start: str
    end: str
    source: str
    adjustment_mode: str
    quality: DatasetQuality
    partitions: tuple[DatasetPartition, ...]
    samples: tuple[DatasetSample, ...]


class ResearchDatasetBuilder:
    def __init__(self, *, source: object) -> None:
        self.source = source

    def build(self, *, start: str, end: str, output: Path) -> ResearchDatasetManifest:
        daily_rows = list(self.source.daily_rows(start=start, end=end))
        quality = DatasetQuality(
            adjustment_mismatch_count=sum(
                1 for row in daily_rows if bool(row.get("adjustment_break"))
            )
        )
        candidates = reconstruct_candidates(daily_rows, trade_date=end)
        broken_codes = {
            _raw_code(row.get("code"))
            for row in daily_rows
            if bool(row.get("adjustment_break"))
        }
        candidates = [
            item
            for item in candidates
            if _raw_code(item.candidate.symbol) not in broken_codes
        ]
        samples = tuple(
            DatasetSample(
                symbol=item.candidate.symbol,
                decision_date=item.decision_date,
                baseline_rank=index,
            )
            for index, item in enumerate(candidates, start=1)
        )
        digest = _dataset_digest(daily_rows, start=start, end=end)
        root = output / f"dataset-{digest[:16]}"
        root.mkdir(parents=True, exist_ok=True)
        partitions = [_write_parquet_partition(root / "daily.parquet", daily_rows)]
        for sample in samples:
            bars = self.source.minute_bars(sample.symbol, start=start, end=end)
            if bars:
                rows = [bar.model_dump(mode="json") for bar in bars]
                partitions.append(
                    _write_parquet_partition(
                        root / "minute" / f"{sample.symbol.replace('.', '_')}.parquet",
                        rows,
                    )
                )
        manifest = ResearchDatasetManifest(
            dataset_id=f"sha256:{digest}",
            root=root,
            start=start,
            end=end,
            source=type(self.source).__name__,
            adjustment_mode=str(getattr(self.source, "adjustment_mode", "unknown")),
            quality=quality,
            partitions=tuple(partitions),
            samples=samples,
        )
        _write_manifest(manifest)
        return manifest


def reconstruct_candidates(
    rows: Iterable[dict[str, object]],
    *,
    trade_date: str,
) -> list[ResearchCandidateRecord]:
    decision = _parse_date(trade_date)
    usable_rows = [row for row in rows if _row_date(row) is not None and _row_date(row) <= decision]
    sessions = sorted({_row_date(row) for row in usable_rows if _row_date(row) is not None})[-20:]
    session_set = set(sessions)
    by_code: dict[str, list[dict[str, object]]] = {}
    for row in usable_rows:
        row_date = _row_date(row)
        code = _raw_code(row.get("code"))
        if row_date in session_set and code:
            by_code.setdefault(code, []).append(row)

    records: list[ResearchCandidateRecord] = []
    for code, code_rows in by_code.items():
        latest = max(code_rows, key=lambda row: _row_date(row) or date.min)
        name = str(latest.get("name") or code)
        if "ST" in name.upper() or not _is_common_a_share_code(code):
            continue
        limit_dates = [
            _row_date(row)
            for row in code_rows
            if _is_limit_up(row, code)
        ]
        if not limit_dates:
            continue
        records.append(
            ResearchCandidateRecord(
                candidate=StrongStockCandidate(
                    symbol=_symbol(code),
                    name=name,
                    industry=_text_or_none(latest.get("industry")),
                    circulating_market_cap_cny=_number_or_none(latest.get("float_mv")),
                    total_market_cap_cny=_number_or_none(latest.get("total_mv")),
                ),
                last_limit_up_date=max(limit_dates).isoformat(),
                limit_up_hits_20d=len(limit_dates),
                decision_date=decision.isoformat(),
            )
        )
    return sorted(
        records,
        key=lambda item: (-item.limit_up_hits_20d, item.last_limit_up_date, item.candidate.symbol),
    )


def _dataset_digest(rows: list[dict[str, object]], *, start: str, end: str) -> str:
    payload = json.dumps(
        {"start": start, "end": end, "rows": rows},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_parquet_partition(path: Path, rows: list[dict[str, object]]) -> DatasetPartition:
    import pyarrow as pa
    import pyarrow.parquet as pq

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, temporary)
    temporary.replace(path)
    digest = _sha256_file(path)
    dates = [str(row.get("date"))[:10] for row in rows if row.get("date")]
    return DatasetPartition(
        path=str(path.relative_to(path.parents[1])),
        sha256=f"sha256:{digest}",
        row_count=len(rows),
        start_date=min(dates) if dates else None,
        end_date=max(dates) if dates else None,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(manifest: ResearchDatasetManifest) -> None:
    payload = {
        "dataset_id": manifest.dataset_id,
        "start": manifest.start,
        "end": manifest.end,
        "source": manifest.source,
        "adjustment_mode": manifest.adjustment_mode,
        "quality": manifest.quality.__dict__,
        "partitions": [partition.__dict__ for partition in manifest.partitions],
        "samples": [sample.__dict__ for sample in manifest.samples],
    }
    temporary = manifest.root / "manifest.json.tmp"
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    temporary.replace(manifest.root / "manifest.json")


def _is_limit_up(row: dict[str, object], code: str) -> bool:
    close = _number_or_none(row.get("close"))
    previous = _number_or_none(row.get("prev_close"))
    if close is None or previous is None or previous <= 0:
        return False
    threshold = 0.195 if code.startswith(("300", "301", "688")) else 0.295 if code.startswith(("4", "8", "92")) else 0.095
    return close / previous - 1 >= threshold


def _row_date(row: dict[str, object]) -> date | None:
    value = row.get("date")
    if value is None:
        return None
    text = str(value).strip()
    try:
        if len(text) >= 8 and text[:8].isdigit():
            return datetime.strptime(text[:8], "%Y%m%d").date()
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_date(value: str) -> date:
    text = str(value).strip()
    if len(text) >= 8 and text[:8].isdigit():
        return datetime.strptime(text[:8], "%Y%m%d").date()
    return date.fromisoformat(text[:10])


def _raw_code(value: object) -> str:
    text = str(value or "").strip().upper()
    return text.split(".", 1)[0].removeprefix("SH").removeprefix("SZ").removeprefix("BJ")


def _symbol(code: str) -> str:
    suffix = "BJ" if code.startswith(("4", "8", "92")) else "SH" if code.startswith(("6", "9")) else "SZ"
    return f"{code}.{suffix}"


def _is_common_a_share_code(code: str) -> bool:
    return len(code) == 6 and code.startswith(("000", "001", "002", "003", "300", "301", "600", "601", "603", "605", "688", "4", "8", "92"))


def _number_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _text_or_none(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
