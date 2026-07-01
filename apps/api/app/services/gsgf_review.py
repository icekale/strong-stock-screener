from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from statistics import mean

from app.models import (
    GsgfReviewBucket,
    GsgfReviewItem,
    GsgfReviewRecord,
    GsgfReviewSnapshotResponse,
    GsgfReviewSummary,
    GsgfReviewWindowResult,
    KlineBar,
    StrongStockScreeningResult,
)
from app.services.gsgf_backtest import DEFAULT_BACKTEST_WINDOWS


class GsgfReviewStore:
    def __init__(self, data_dir: Path) -> None:
        self.root_dir = data_dir / "gsgf_review"

    @property
    def snapshots_path(self) -> Path:
        return self.root_dir / "snapshots.jsonl"

    @property
    def latest_summary_path(self) -> Path:
        return self.root_dir / "latest_summary.json"

    def persist_snapshot(
        self,
        result: StrongStockScreeningResult,
        *,
        dedupe: bool = False,
    ) -> GsgfReviewSnapshotResponse:
        records = [_record_from_item(result.trade_date, item) for item in result.items if item.gsgf is not None]
        if dedupe and records:
            existing_keys = {_record_key(record) for record in self.load_records()}
            records = [record for record in records if _record_key(record) not in existing_keys]
        self.root_dir.mkdir(parents=True, exist_ok=True)
        if records:
            with self.snapshots_path.open("a", encoding="utf-8") as handle:
                for record in records:
                    handle.write(record.model_dump_json() + "\n")
        return GsgfReviewSnapshotResponse(saved_count=len(records), records=records)

    def load_records(self) -> list[GsgfReviewRecord]:
        if not self.snapshots_path.exists():
            return []
        records: list[GsgfReviewRecord] = []
        for line in self.snapshots_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(GsgfReviewRecord.model_validate_json(line))
        return records

    def recheck_snapshots(
        self,
        symbol_bars: dict[str, list[KlineBar]],
        *,
        windows: list[int] | None = None,
    ) -> GsgfReviewSummary:
        clean_windows = _clean_windows(windows)
        items = [
            _review_item(record, sorted(symbol_bars.get(record.symbol, []), key=lambda bar: bar.date), clean_windows)
            for record in self.load_records()
        ]
        return GsgfReviewSummary(
            windows=clean_windows,
            record_count=len(items),
            items=items,
            buckets=_buckets(items, clean_windows),
        )

    def save_latest_summary(self, summary: GsgfReviewSummary) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.latest_summary_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")

    def load_latest_summary(self) -> GsgfReviewSummary | None:
        if not self.latest_summary_path.exists():
            return None
        return GsgfReviewSummary.model_validate_json(
            self.latest_summary_path.read_text(encoding="utf-8")
        )


def _record_from_item(trade_date: str, item) -> GsgfReviewRecord:
    gsgf = item.gsgf
    signal_type = gsgf.confirm_type or gsgf.setup_type or gsgf.final_status
    return GsgfReviewRecord(
        trade_date=trade_date,
        symbol=item.symbol,
        name=item.name,
        signal_type=signal_type,
        status=gsgf.final_status,
        score=gsgf.total_score,
        setup_type=gsgf.setup_type,
        confirm_type=gsgf.confirm_type,
    )


def _record_key(record: GsgfReviewRecord) -> tuple[str, str, str, str]:
    return (record.trade_date, record.symbol, record.signal_type, record.status)


def _review_item(record: GsgfReviewRecord, bars: list[KlineBar], windows: list[int]) -> GsgfReviewItem:
    signal_index = _signal_index(record.trade_date, bars)
    future_bars = bars[signal_index + 1 :] if signal_index is not None else []
    entry_close = bars[signal_index].close if signal_index is not None and bars[signal_index].close > 0 else None
    results = [_window_result(entry_close, future_bars, window) for window in windows]
    confirmed = record.status == "确认买点" and any(
        result.realized_return_pct is not None and result.realized_return_pct > 0 for result in results
    )
    return GsgfReviewItem(record=record, confirmed=confirmed, windows=results)


def _window_result(entry_close: float | None, future_bars: list[KlineBar], window: int) -> GsgfReviewWindowResult:
    if entry_close is None or len(future_bars) < window:
        return GsgfReviewWindowResult(window_days=window)
    scoped = future_bars[:window]
    realized_return_pct = (scoped[-1].close / entry_close - 1) * 100
    max_drawdown_pct = (min(bar.low for bar in scoped) / entry_close - 1) * 100
    return GsgfReviewWindowResult(
        window_days=window,
        realized_return_pct=round(realized_return_pct, 2),
        max_drawdown_pct=round(max_drawdown_pct, 2),
    )


def _signal_index(trade_date: str, bars: list[KlineBar]) -> int | None:
    for index, bar in enumerate(bars):
        if bar.date == trade_date:
            return index
    return 0 if bars else None


def _buckets(items: list[GsgfReviewItem], windows: list[int]) -> list[GsgfReviewBucket]:
    grouped: dict[tuple[str, str], list[GsgfReviewItem]] = defaultdict(list)
    for item in items:
        grouped[(item.record.signal_type, item.record.status)].append(item)

    output: list[GsgfReviewBucket] = []
    first_window = windows[0] if windows else DEFAULT_BACKTEST_WINDOWS[0]
    for (signal_type, status), group_items in sorted(grouped.items()):
        returns: list[float] = []
        drawdowns: list[float] = []
        for item in group_items:
            window = next((result for result in item.windows if result.window_days == first_window), None)
            if window and window.realized_return_pct is not None:
                returns.append(window.realized_return_pct)
            if window and window.max_drawdown_pct is not None:
                drawdowns.append(window.max_drawdown_pct)
        output.append(
            GsgfReviewBucket(
                signal_type=signal_type,
                status=status,
                sample_count=len(group_items),
                confirmed_count=sum(1 for item in group_items if item.confirmed),
                avg_return_pct=round(mean(returns), 2) if returns else None,
                avg_max_drawdown_pct=round(mean(drawdowns), 2) if drawdowns else None,
            )
        )
    return output


def _clean_windows(windows: list[int] | None) -> list[int]:
    values = windows or DEFAULT_BACKTEST_WINDOWS
    output: list[int] = []
    seen: set[int] = set()
    for value in values:
        normalized = max(1, min(int(value), 60))
        if normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output or DEFAULT_BACKTEST_WINDOWS
