from __future__ import annotations

from pathlib import Path

from app.models import AuctionReviewRecord, AuctionReviewSummary


class AuctionReviewStore:
    def __init__(self, data_dir: Path, retention_days: int | None = None) -> None:
        self.root_dir = data_dir / "auction_reviews"
        self.records_dir = self.root_dir / "records"
        self.retention_days = retention_days

    @property
    def latest_summary_path(self) -> Path:
        return self.root_dir / "latest_summary.json"

    def upsert_records(self, records: list[AuctionReviewRecord]) -> list[AuctionReviewRecord]:
        if not records:
            return []
        grouped: dict[str, list[AuctionReviewRecord]] = {}
        for record in records:
            grouped.setdefault(record.trade_date, []).append(record)

        saved: list[AuctionReviewRecord] = []
        self.records_dir.mkdir(parents=True, exist_ok=True)
        for trade_date, trade_records in grouped.items():
            existing = {_record_key(record): record for record in self.load_records(trade_date)}
            for record in trade_records:
                existing[_record_key(record)] = record
            ordered = sorted(
                existing.values(),
                key=lambda record: (
                    record.selected_at_label,
                    record.auction_snapshot.rank or 999999,
                    record.symbol,
                ),
            )
            path = self._records_path(trade_date)
            path.write_text(
                "".join(record.model_dump_json() + "\n" for record in ordered),
                encoding="utf-8",
            )
            saved.extend(trade_records)
        self._prune_trade_dates()
        return saved

    def load_records(self, trade_date: str | None = None, limit: int | None = None) -> list[AuctionReviewRecord]:
        paths = [self._records_path(trade_date)] if trade_date else sorted(self.records_dir.glob("*.jsonl"))
        records: list[AuctionReviewRecord] = []
        for path in paths:
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    records.append(AuctionReviewRecord.model_validate_json(line))
        if limit is not None:
            return records[-max(1, limit) :]
        return records

    def save_summary(self, summary: AuctionReviewSummary) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.latest_summary_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")

    def load_latest_summary(self) -> AuctionReviewSummary | None:
        if not self.latest_summary_path.exists():
            return None
        return AuctionReviewSummary.model_validate_json(self.latest_summary_path.read_text(encoding="utf-8"))

    def _records_path(self, trade_date: str) -> Path:
        return self.records_dir / f"{trade_date}.jsonl"

    def _prune_trade_dates(self) -> None:
        if self.retention_days is None or not self.records_dir.exists():
            return
        keep_days = max(1, self.retention_days)
        paths = sorted(self.records_dir.glob("*.jsonl"))
        if len(paths) <= keep_days:
            return
        for path in paths[: len(paths) - keep_days]:
            path.unlink(missing_ok=True)


def _record_key(record: AuctionReviewRecord) -> tuple[str, str, str]:
    return (record.trade_date, record.symbol, record.selected_at_label)
