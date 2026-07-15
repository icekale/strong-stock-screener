from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
import gc
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from app.models import StrongStockCandidate


SHANGHAI = ZoneInfo("Asia/Shanghai")


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
    source: str = "unknown"
    captured_at: str | None = None
    adjustment_mode: str = "unknown"
    invalid_row_count: int = 0
    duplicate_row_count: int = 0
    missing_row_count: int = 0


@dataclass(frozen=True)
class DatasetQuality:
    adjustment_mismatch_count: int = 0
    invalid_row_count: int = 0
    duplicate_row_count: int = 0
    missing_row_count: int = 0


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
    rule_versions: dict[str, str] | None = None
    captured_at: str | None = None


@dataclass(frozen=True)
class FrozenResearchDataset:
    root: Path
    manifest: ResearchDatasetManifest
    candidates_by_date: dict[str, list[dict[str, Any]]]
    daily_bars_by_symbol: dict[str, list[Any]]
    minute_bars_by_symbol: dict[str, list[Any]]


class ResearchDatasetBuilder:
    def __init__(
        self,
        *,
        source: object,
        max_candidates_per_date: int = 60,
        resume: bool = False,
    ) -> None:
        self.source = source
        self.max_candidates_per_date = max(1, max_candidates_per_date)
        self.resume = resume

    def build(self, *, start: str, end: str, output: Path) -> ResearchDatasetManifest:
        chunked = getattr(self.source, "daily_rows_by_year", None)
        if callable(chunked):
            return self._build_chunked(start=start, end=end, output=output)
        return self._build_rows(
            list(self.source.daily_rows(start=start, end=end)),
            start=start,
            end=end,
            output=output,
        )

    def _build_rows(
        self,
        source_rows: list[dict[str, object]],
        *,
        start: str,
        end: str,
        output: Path,
    ) -> ResearchDatasetManifest:
        daily_rows, invalid_count, duplicate_count = _normalize_daily_rows(
            source_rows
        )
        quality = DatasetQuality(
            adjustment_mismatch_count=sum(
                1 for row in daily_rows if bool(row.get("adjustment_break"))
            ),
            invalid_row_count=invalid_count,
            duplicate_row_count=duplicate_count,
        )
        available_dates = sorted(
            {
                row_date.isoformat()
                for row in daily_rows
                if (row_date := _row_date(row)) is not None
                and _parse_date(start) <= row_date <= _parse_date(end)
            }
        )
        decision_dates = available_dates[19:]
        broken_codes = {
            _raw_code(row.get("code"))
            for row in daily_rows
            if bool(row.get("adjustment_break"))
        }
        candidates_by_date: dict[str, list[ResearchCandidateRecord]] = {}
        for decision_date in decision_dates:
            candidates = reconstruct_candidates(daily_rows, trade_date=decision_date)
            candidates_by_date[decision_date] = [
                item
                for item in candidates
                if _raw_code(item.candidate.symbol) not in broken_codes
            ][: self.max_candidates_per_date]
        samples = tuple(
            DatasetSample(
                symbol=item.candidate.symbol,
                decision_date=decision_date,
                baseline_rank=index,
            )
            for decision_date in decision_dates
            for index, item in enumerate(candidates_by_date[decision_date], start=1)
        )
        digest = _dataset_digest(daily_rows, start=start, end=end)
        root = output / f"dataset-{digest[:16]}"
        root.mkdir(parents=True, exist_ok=True)
        captured_at = datetime.now(SHANGHAI).isoformat(timespec="seconds")
        source_name = type(self.source).__name__
        adjustment_mode = str(getattr(self.source, "adjustment_mode", "unknown"))
        partitions = [
            _write_parquet_partition(
                root / "daily.parquet",
                daily_rows,
                output,
                source=source_name,
                captured_at=captured_at,
                adjustment_mode=adjustment_mode,
            )
        ]
        symbols = sorted({sample.symbol for sample in samples})
        for symbol in symbols:
            bars = self.source.minute_bars(symbol, start=start, end=end)
            by_month: dict[str, list[dict[str, Any]]] = {}
            for bar in bars:
                month = str(bar.date)[:7]
                by_month.setdefault(month, []).append(bar.model_dump(mode="json"))
            for month, rows in sorted(by_month.items()):
                partitions.append(
                    _write_parquet_partition(
                        root / "minute" / f"symbol={symbol.replace('.', '_')}" / f"month={month}.parquet",
                        rows,
                        output,
                        source=source_name,
                        captured_at=captured_at,
                        adjustment_mode=adjustment_mode,
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
            rule_versions={
                "candidate_reconstruction": "limit-up-20-session-v1",
                "dataset_schema": "czsc-research-dataset-v2",
            },
            captured_at=captured_at,
        )
        _write_manifest(manifest)
        return manifest

    def _build_chunked(
        self,
        *,
        start: str,
        end: str,
        output: Path,
    ) -> ResearchDatasetManifest:
        output.mkdir(parents=True, exist_ok=True)
        staging = output / f".dataset-building-{_build_key(start, end)}"
        progress_path = staging / "progress.json"
        if staging.exists() and not self.resume:
            raise FileExistsError(f"dataset build is already in progress: {staging}")
        staging.mkdir(parents=True, exist_ok=True)
        captured_at = datetime.now(SHANGHAI).isoformat(timespec="seconds")
        source_name = type(self.source).__name__
        adjustment_mode = str(getattr(self.source, "adjustment_mode", "unknown"))
        digest = hashlib.sha256()
        digest.update(f"{start}\0{end}".encode("utf-8"))
        invalid_count = 0
        duplicate_count = 0
        adjustment_mismatch_count = 0
        partitions: list[DatasetPartition] = []
        samples: list[DatasetSample] = []
        rolling_by_date: dict[date, list[dict[str, object]]] = {}
        recent_sessions: list[date] = []
        broken_codes: set[str] = set()
        completed_chunks: list[str] = []
        chunk_hashes: dict[str, str] = {}

        if self.resume and progress_path.exists():
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
            if progress.get("start") != start or progress.get("end") != end:
                raise ValueError("dataset build progress range does not match requested range")
            captured_at = str(progress.get("captured_at") or captured_at)
            invalid_count = int(progress.get("invalid_row_count", 0))
            duplicate_count = int(progress.get("duplicate_row_count", 0))
            adjustment_mismatch_count = int(progress.get("adjustment_mismatch_count", 0))
            completed_chunks = [str(value) for value in progress.get("completed_chunks", [])]
            chunk_hashes = {str(key): str(value) for key, value in progress.get("chunk_hashes", {}).items()}
            partitions = [DatasetPartition(**item) for item in progress.get("partitions", [])]
            samples = [DatasetSample(**item) for item in progress.get("samples", [])]
            recent_sessions = [date.fromisoformat(value) for value in progress.get("recent_sessions", [])]
            rolling_by_date = {
                date.fromisoformat(key): value
                for key, value in progress.get("rolling_rows", {}).items()
            }
            broken_codes = {str(value) for value in progress.get("broken_codes", [])}
            for chunk in completed_chunks:
                digest.update(chunk_hashes[chunk].encode("ascii"))

        try:
            chunk_method = self.source.daily_rows_by_year
            parameters = inspect.signature(chunk_method).parameters
            chunk_kwargs = {"start": start, "end": end}
            if "skip_chunks" in parameters:
                chunk_kwargs["skip_chunks"] = set(completed_chunks)
            for year, source_rows in chunk_method(**chunk_kwargs):
                chunk_label = str(year)
                if chunk_label in completed_chunks:
                    continue
                daily_rows, invalid, duplicates = _normalize_daily_rows(source_rows)
                invalid_count += invalid
                duplicate_count += duplicates
                adjustment_mismatch_count += sum(
                    1 for row in daily_rows if bool(row.get("adjustment_break"))
                )
                broken_codes.update(
                    _raw_code(row.get("code"))
                    for row in daily_rows
                    if bool(row.get("adjustment_break"))
                )
                chunk_hash = hashlib.sha256(
                    json.dumps(
                        daily_rows,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
                chunk_hashes[chunk_label] = chunk_hash
                digest.update(chunk_hash.encode("ascii"))
                if chunk_label not in completed_chunks:
                    completed_chunks.append(chunk_label)
                if daily_rows:
                    partitions.append(
                        _write_parquet_partition(
                            staging / "daily" / _daily_partition_name(year),
                            daily_rows,
                            staging,
                            source=source_name,
                            captured_at=captured_at,
                            adjustment_mode=adjustment_mode,
                        )
                    )
                rows_by_date: dict[date, list[dict[str, object]]] = {}
                for row in daily_rows:
                    row_date = _row_date(row)
                    if row_date is not None:
                        rows_by_date.setdefault(row_date, []).append(row)
                for decision_date in sorted(rows_by_date):
                    rolling_by_date[decision_date] = rows_by_date[decision_date]
                    recent_sessions.append(decision_date)
                    recent_sessions = sorted(set(recent_sessions))[-20:]
                    if len(recent_sessions) < 20:
                        continue
                    window_rows = [
                        row
                        for session in recent_sessions
                        for row in rolling_by_date.get(session, [])
                    ]
                    candidates = [
                        item
                        for item in reconstruct_candidates(
                            window_rows,
                            trade_date=decision_date.isoformat(),
                        )
                        if _raw_code(item.candidate.symbol) not in broken_codes
                    ][: self.max_candidates_per_date]
                    samples.extend(
                        DatasetSample(
                            symbol=item.candidate.symbol,
                            decision_date=decision_date.isoformat(),
                            baseline_rank=index,
                        )
                        for index, item in enumerate(candidates, start=1)
                    )
                    rolling_by_date = {
                        session: rolling_by_date[session]
                        for session in recent_sessions
                        if session in rolling_by_date
                    }
                _write_build_progress(
                    progress_path,
                    start=start,
                    end=end,
                    captured_at=captured_at,
                    completed_chunks=completed_chunks,
                    chunk_hashes=chunk_hashes,
                    partitions=partitions,
                    samples=samples,
                    recent_sessions=recent_sessions,
                    rolling_by_date=rolling_by_date,
                    broken_codes=broken_codes,
                    invalid_count=invalid_count,
                    duplicate_count=duplicate_count,
                    adjustment_mismatch_count=adjustment_mismatch_count,
                )

            digest_value = digest.hexdigest()
            root = output / f"dataset-{digest_value[:16]}"
            if root.exists():
                raise FileExistsError(f"frozen dataset already exists: {root}")
            symbols = sorted({sample.symbol for sample in samples})
            for symbol in symbols:
                bars = self.source.minute_bars(symbol, start=start, end=end)
                by_month: dict[str, list[dict[str, Any]]] = {}
                for bar in bars:
                    month = str(bar.date)[:7]
                    by_month.setdefault(month, []).append(bar.model_dump(mode="json"))
                for month, rows in sorted(by_month.items()):
                    partitions.append(
                        _write_parquet_partition(
                            staging / "minute" / f"symbol={symbol.replace('.', '_')}" / f"month={month}.parquet",
                            rows,
                            staging,
                            source=source_name,
                            captured_at=captured_at,
                            adjustment_mode=adjustment_mode,
                        )
                    )
            manifest = ResearchDatasetManifest(
                dataset_id=f"sha256:{digest_value}",
                root=staging,
                start=start,
                end=end,
                source=source_name,
                adjustment_mode=adjustment_mode,
                quality=DatasetQuality(
                    adjustment_mismatch_count=adjustment_mismatch_count,
                    invalid_row_count=invalid_count,
                    duplicate_row_count=duplicate_count,
                ),
                partitions=tuple(partitions),
                samples=tuple(samples),
                rule_versions={
                    "candidate_reconstruction": "limit-up-20-session-v1",
                    "dataset_schema": "czsc-research-dataset-v2",
                    "daily_partitioning": "time-chunk-v2",
                },
                captured_at=captured_at,
            )
            _write_manifest(manifest)
            staging.replace(root)
            return replace(manifest, root=root)
        except Exception:
            raise


def load_frozen_dataset(
    root: Path,
    *,
    include_minute: bool = True,
    selected_samples: set[tuple[str, str]] | None = None,
) -> FrozenResearchDataset:
    """Load only the files referenced by a frozen manifest."""
    import pyarrow.parquet as pq

    manifest_path = root / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    partitions = tuple(
        DatasetPartition(
            path=str(item["path"]),
            sha256=str(item["sha256"]),
            row_count=int(item.get("row_count", 0)),
            start_date=item.get("start_date"),
            end_date=item.get("end_date"),
            source=str(item.get("source", "unknown")),
            captured_at=item.get("captured_at"),
            adjustment_mode=str(item.get("adjustment_mode", "unknown")),
            invalid_row_count=int(item.get("invalid_row_count", 0)),
            duplicate_row_count=int(item.get("duplicate_row_count", 0)),
            missing_row_count=int(item.get("missing_row_count", 0)),
        )
        for item in payload.get("partitions", [])
    )
    manifest = ResearchDatasetManifest(
        dataset_id=str(payload.get("dataset_id", "")),
        root=root,
        start=str(payload.get("start", "")),
        end=str(payload.get("end", "")),
        source=str(payload.get("source", "")),
        adjustment_mode=str(payload.get("adjustment_mode", "unknown")),
        quality=DatasetQuality(**payload.get("quality", {})),
        partitions=partitions,
        samples=tuple(DatasetSample(**sample) for sample in payload.get("samples", [])),
        rule_versions=payload.get("rule_versions"),
        captured_at=payload.get("captured_at"),
    )
    normalized_selection = (
        {(symbol.strip().upper(), decision_date) for symbol, decision_date in selected_samples}
        if selected_samples is not None
        else None
    )
    selected_manifest_samples = tuple(
        sample
        for sample in manifest.samples
        if normalized_selection is None or (sample.symbol, sample.decision_date) in normalized_selection
    )
    selected_symbols = {sample.symbol for sample in selected_manifest_samples}
    selected_dates = [date.fromisoformat(sample.decision_date) for sample in selected_manifest_samples]
    daily_start = min(selected_dates) - timedelta(days=400) if selected_dates else None
    minute_start = min(selected_dates) - timedelta(days=120) if selected_dates else None
    selected_end = max(selected_dates) if selected_dates else None

    candidates_by_date: dict[str, list[dict[str, Any]]] = {}
    for sample in selected_manifest_samples:
        candidates_by_date.setdefault(sample.decision_date, []).append(
            {
                "symbol": sample.symbol,
                "decision_date": sample.decision_date,
                "baseline_rank": sample.baseline_rank,
            }
        )
    for candidates in candidates_by_date.values():
        candidates.sort(key=lambda item: int(item["baseline_rank"]))

    daily_bars_by_symbol: dict[str, list[Any]] = {}
    minute_bars_by_symbol: dict[str, list[Any]] = (
        {symbol: [] for symbol in selected_symbols}
        if normalized_selection is not None and include_minute
        else {}
    )
    with _gc_disabled():
        for partition in partitions:
            path = root / partition.path
            if not path.exists():
                path = root.parent / partition.path
            is_minute_partition = "symbol=" in str(path)
            if normalized_selection is not None and not _partition_needed(
                partition,
                path=path,
                selected_symbols=selected_symbols,
                daily_start=daily_start,
                minute_start=minute_start,
                selected_end=selected_end,
            ):
                continue
            if not path.exists() or f"sha256:{_sha256_file(path)}" != partition.sha256:
                raise ValueError(f"dataset checksum mismatch: {partition.path}")
            if not include_minute and is_minute_partition:
                continue
            rows = pq.read_table(path).to_pylist()
            if "daily" in path.parts:
                for row in rows:
                    symbol = _symbol(_raw_code(row.get("code")))
                    row_date = _row_date(row)
                    if normalized_selection is not None and (
                        symbol not in selected_symbols
                        or row_date is None
                        or daily_start is None
                        or selected_end is None
                        or not daily_start <= row_date <= selected_end
                    ):
                        continue
                    bar = _daily_bar_from_row(row)
                    if bar is not None:
                        daily_bars_by_symbol.setdefault(symbol, []).append(bar)
            elif is_minute_partition:
                symbol_value = next(
                    part.removeprefix("symbol=")
                    for part in path.parts
                    if part.startswith("symbol=")
                )
                symbol = symbol_value.replace("_", ".")
                minute_bars_by_symbol.setdefault(symbol, [])
                for row in rows:
                    row_date = _row_date(row)
                    if normalized_selection is not None and (
                        row_date is None
                        or minute_start is None
                        or selected_end is None
                        or not minute_start <= row_date <= selected_end
                    ):
                        continue
                    bar = _minute_bar_from_row(row)
                    if bar is not None:
                        minute_bars_by_symbol.setdefault(symbol, []).append(bar)
        # Manifest partitions are emitted in symbol/month order, and each source
        # partition is already chronological; avoid re-sorting millions of bars.
    return FrozenResearchDataset(
        root=root,
        manifest=manifest,
        candidates_by_date=candidates_by_date,
        daily_bars_by_symbol=daily_bars_by_symbol,
        minute_bars_by_symbol=minute_bars_by_symbol,
    )


def _partition_needed(
    partition: DatasetPartition,
    *,
    path: Path,
    selected_symbols: set[str],
    daily_start: date | None,
    minute_start: date | None,
    selected_end: date | None,
) -> bool:
    if not selected_symbols or selected_end is None:
        return False
    is_minute = "symbol=" in str(path)
    if is_minute:
        symbol_value = next(
            part.removeprefix("symbol=")
            for part in path.parts
            if part.startswith("symbol=")
        )
        if symbol_value.replace("_", ".") not in selected_symbols:
            return False
    start = minute_start if is_minute else daily_start
    partition_start = _partition_date(partition.start_date)
    partition_end = _partition_date(partition.end_date)
    return bool(
        start is not None
        and (partition_end is None or partition_end >= start)
        and (partition_start is None or partition_start <= selected_end)
    )


def _partition_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return _parse_date(value)
    except ValueError:
        return None


@contextmanager
def _gc_disabled():
    was_enabled = gc.isenabled()
    if was_enabled:
        gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()


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


def _write_parquet_partition(
    path: Path,
    rows: list[dict[str, object]],
    relative_root: Path | None = None,
    *,
    source: str = "unknown",
    captured_at: str | None = None,
    adjustment_mode: str = "unknown",
) -> DatasetPartition:
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
        path=str(path.relative_to(relative_root or path.parents[1])),
        sha256=f"sha256:{digest}",
        row_count=len(rows),
        start_date=min(dates) if dates else None,
        end_date=max(dates) if dates else None,
        source=source,
        captured_at=captured_at,
        adjustment_mode=adjustment_mode,
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
        "rule_versions": manifest.rule_versions or {},
        "captured_at": manifest.captured_at,
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


def _normalize_daily_rows(rows: Iterable[dict[str, object]]) -> tuple[list[dict[str, object]], int, int]:
    normalized: dict[tuple[str, date], dict[str, object]] = {}
    invalid_count = 0
    duplicate_count = 0
    for row in rows:
        row_date = _row_date(row)
        code = _raw_code(row.get("code"))
        close = _number_or_none(row.get("close"))
        if row_date is None or not code or close is None or close <= 0:
            invalid_count += 1
            continue
        key = (code, row_date)
        if key in normalized:
            duplicate_count += 1
        normalized[key] = dict(row)
    return (
        [normalized[key] for key in sorted(normalized, key=lambda item: (item[1], item[0]))],
        invalid_count,
        duplicate_count,
    )


def _daily_partition_name(label: object) -> str:
    text = str(label)
    if len(text) == 6 and text.isdigit():
        return f"month={text}.parquet"
    return f"year={text}.parquet"


def _build_key(start: str, end: str) -> str:
    return f"{str(start)[:10].replace('-', '')}-{str(end)[:10].replace('-', '')}"


def _write_build_progress(
    path: Path,
    *,
    start: str,
    end: str,
    captured_at: str,
    completed_chunks: list[str],
    chunk_hashes: dict[str, str],
    partitions: list[DatasetPartition],
    samples: list[DatasetSample],
    recent_sessions: list[date],
    rolling_by_date: dict[date, list[dict[str, object]]],
    broken_codes: set[str],
    invalid_count: int,
    duplicate_count: int,
    adjustment_mismatch_count: int,
) -> None:
    payload = {
        "schema_version": "czsc-research-progress-v1",
        "start": start,
        "end": end,
        "captured_at": captured_at,
        "completed_chunks": completed_chunks,
        "chunk_hashes": chunk_hashes,
        "partitions": [partition.__dict__ for partition in partitions],
        "samples": [sample.__dict__ for sample in samples],
        "recent_sessions": [session.isoformat() for session in recent_sessions],
        "rolling_rows": {session.isoformat(): rows for session, rows in rolling_by_date.items()},
        "broken_codes": sorted(broken_codes),
        "invalid_row_count": invalid_count,
        "duplicate_row_count": duplicate_count,
        "adjustment_mismatch_count": adjustment_mismatch_count,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(path)


def _daily_bar_from_row(row: dict[str, object]) -> Any | None:
    from app.models import KlineBar

    row_date = _row_date(row)
    close = _number_or_none(row.get("close"))
    if row_date is None or close is None or close <= 0:
        return None
    open_price = _number_or_none(row.get("open")) or _number_or_none(row.get("prev_close")) or close
    high = _number_or_none(row.get("high")) or max(open_price, close)
    low = _number_or_none(row.get("low")) or min(open_price, close)
    return KlineBar(
        date=datetime.combine(row_date, datetime.min.time(), tzinfo=SHANGHAI).isoformat(timespec="seconds"),
        open=open_price,
        high=max(high, open_price, close),
        low=min(low, open_price, close),
        close=close,
        volume=_number_or_none(row.get("volume")) or 0,
        amount=_number_or_none(row.get("amount")),
    )


def _minute_bar_from_row(row: dict[str, object]) -> Any | None:
    from app.models import KlineBar

    values = [_number_or_none(row.get(key)) for key in ("open", "high", "low", "close", "volume")]
    if any(value is None for value in values):
        return None
    try:
        return KlineBar.model_validate(row)
    except (TypeError, ValueError):
        return None
