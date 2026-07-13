from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.models import (
    CzscResearchSnapshot,
    CzscV2BatchResult,
    CzscV2BatchStatus,
    CzscV2CandidateScore,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")
_BUSY_TIMEOUT_MS = 30_000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_snapshots (
  input_snapshot_id TEXT PRIMARY KEY,
  symbol TEXT NOT NULL,
  status TEXT NOT NULL,
  calculated_at TEXT NOT NULL,
  engine_version TEXT NOT NULL,
  catalog_version TEXT NOT NULL,
  rule_version TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS research_snapshots_latest_idx
  ON research_snapshots(symbol, calculated_at DESC, input_snapshot_id DESC);
CREATE INDEX IF NOT EXISTS research_snapshots_retention_idx
  ON research_snapshots(
    symbol, engine_version, catalog_version, rule_version,
    calculated_at DESC, input_snapshot_id DESC
  );

CREATE TABLE IF NOT EXISTS signal_evidence (
  id TEXT PRIMARY KEY,
  input_snapshot_id TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  engine_version TEXT NOT NULL,
  catalog_version TEXT NOT NULL,
  rule_version TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS signal_evidence_retention_idx
  ON signal_evidence(occurred_at, input_snapshot_id);

CREATE TABLE IF NOT EXISTS shadow_batches (
  batch_id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  trade_date TEXT NOT NULL,
  status TEXT NOT NULL,
  pool_size INTEGER NOT NULL,
  baseline_symbols_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS shadow_batches_retention_idx
  ON shadow_batches(trade_date, batch_id);

CREATE TABLE IF NOT EXISTS shadow_scores (
  batch_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  baseline_rank INTEGER NOT NULL,
  status TEXT NOT NULL,
  score INTEGER,
  payload_json TEXT NOT NULL,
  PRIMARY KEY (batch_id, symbol),
  FOREIGN KEY (batch_id) REFERENCES shadow_batches(batch_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS shadow_scores_order_idx
  ON shadow_scores(batch_id, baseline_rank);
"""


class ChanlunResearchStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._ensure_schema()

    def save_snapshot(self, snapshot: CzscResearchSnapshot) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            _validate_snapshot_evidence(snapshot)
            connection.execute(
                """
                INSERT INTO research_snapshots (
                  input_snapshot_id, symbol, status, calculated_at,
                  engine_version, catalog_version, rule_version, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(input_snapshot_id) DO UPDATE SET
                  symbol = excluded.symbol,
                  status = excluded.status,
                  calculated_at = excluded.calculated_at,
                  engine_version = excluded.engine_version,
                  catalog_version = excluded.catalog_version,
                  rule_version = excluded.rule_version,
                  payload_json = excluded.payload_json
                """,
                (
                    snapshot.input_snapshot_id,
                    snapshot.symbol,
                    snapshot.status,
                    _timestamp_key(snapshot.calculated_at),
                    snapshot.engine_version,
                    snapshot.catalog_version,
                    snapshot.rule_version,
                    _dump_json(snapshot),
                ),
            )
            for event in snapshot.events:
                connection.execute(
                    """
                    INSERT INTO signal_evidence (
                      id, input_snapshot_id, occurred_at, engine_version,
                      catalog_version, rule_version, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO NOTHING
                    """,
                    (
                        event.id,
                        event.input_snapshot_id,
                        _timestamp_key(event.occurred_at),
                        event.engine_version,
                        event.catalog_version,
                        event.rule_version,
                        _dump_json(event),
                    ),
                )

    def load_snapshot(self, input_snapshot_id: str) -> CzscResearchSnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM research_snapshots WHERE input_snapshot_id = ?",
                (input_snapshot_id,),
            ).fetchone()
        if row is None:
            return None
        return _snapshot_from_row(row)

    def latest_snapshot(self, symbol: str) -> CzscResearchSnapshot | None:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM research_snapshots
                WHERE symbol = ?
                ORDER BY calculated_at DESC, input_snapshot_id DESC
                """,
                (symbol,),
            ).fetchall()
        for row in rows:
            snapshot = _snapshot_from_row(row)
            if snapshot is not None:
                return snapshot
        return None

    def count_events(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM signal_evidence").fetchone()
        return int(row["count"])

    def create_batch(
        self,
        batch_id: str,
        trade_date: str,
        baseline_symbols: list[str],
    ) -> None:
        _validate_batch_identity(batch_id, baseline_symbols)
        baseline_json = _dump_value(baseline_symbols)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM shadow_batches WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
            if existing is not None:
                identity = (
                    existing["job_id"],
                    existing["trade_date"],
                    existing["pool_size"],
                    existing["baseline_symbols_json"],
                )
                expected = (batch_id, trade_date, len(baseline_symbols), baseline_json)
                if identity != expected:
                    raise ValueError("batch baseline is immutable once created")
                return
            connection.execute(
                """
                INSERT INTO shadow_batches (
                  batch_id, job_id, trade_date, status, pool_size, baseline_symbols_json
                ) VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (batch_id, batch_id, trade_date, len(baseline_symbols), baseline_json),
            )

    def save_batch_score(self, batch_id: str, score: CzscV2CandidateScore) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            batch = connection.execute(
                "SELECT * FROM shadow_batches WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
            if batch is None:
                raise ValueError(f"batch does not exist: {batch_id}")
            if batch["status"] != "pending":
                raise ValueError("batch must be pending to save scores")
            baseline_symbols = _baseline_symbols(batch)
            try:
                expected_rank = baseline_symbols.index(score.symbol) + 1
            except ValueError as error:
                raise ValueError(f"symbol is not in the batch baseline: {score.symbol}") from error
            if score.baseline_rank != expected_rank:
                raise ValueError(f"baseline rank for {score.symbol} must remain {expected_rank}")
            connection.execute(
                """
                INSERT INTO shadow_scores (
                  batch_id, symbol, baseline_rank, status, score, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(batch_id, symbol) DO UPDATE SET
                  baseline_rank = excluded.baseline_rank,
                  status = excluded.status,
                  score = excluded.score,
                  payload_json = excluded.payload_json
                """,
                (
                    batch_id,
                    score.symbol,
                    score.baseline_rank,
                    score.status,
                    score.score,
                    _dump_json(score),
                ),
            )

    def load_batch(self, batch_id: str) -> CzscV2BatchResult | None:
        with self._connect() as connection:
            connection.execute("BEGIN")
            batch = connection.execute(
                "SELECT * FROM shadow_batches WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
            if batch is None:
                return None
            score_rows = connection.execute(
                """
                SELECT * FROM shadow_scores
                WHERE batch_id = ?
                ORDER BY baseline_rank, symbol
                """,
                (batch_id,),
            ).fetchall()

        baseline_symbols = _baseline_symbols(batch)
        items = [_score_from_row(row, baseline_symbols) for row in score_rows]
        if batch["status"] in {"ready", "partial", "unavailable"}:
            _validate_terminal_batch_status(batch["status"], items, len(baseline_symbols))
        return CzscV2BatchResult(
            batch_id=batch["batch_id"],
            job_id=batch["job_id"],
            status=batch["status"],
            trade_date=batch["trade_date"],
            pool_size=batch["pool_size"],
            completed_count=len(items),
            items=items,
        )

    def finish_batch(self, batch_id: str, status: CzscV2BatchStatus) -> None:
        terminal_statuses = {"ready", "partial", "unavailable"}
        if status not in terminal_statuses:
            raise ValueError("finish_batch requires a terminal status")

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            batch = connection.execute(
                "SELECT * FROM shadow_batches WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
            if batch is None:
                raise ValueError(f"batch does not exist: {batch_id}")
            current_status = batch["status"]
            if current_status not in {"pending", status}:
                raise ValueError(f"invalid batch status transition: {current_status} -> {status}")
            score_rows = connection.execute(
                """
                SELECT * FROM shadow_scores
                WHERE batch_id = ?
                ORDER BY baseline_rank, symbol
                """,
                (batch_id,),
            ).fetchall()
            baseline_symbols = _baseline_symbols(batch)
            items = [_score_from_row(row, baseline_symbols) for row in score_rows]
            _validate_terminal_batch_status(status, items, len(baseline_symbols))
            if current_status == status:
                return
            connection.execute(
                "UPDATE shadow_batches SET status = ? WHERE batch_id = ?",
                (status, batch_id),
            )

    def prune(
        self,
        now: datetime,
        snapshot_days: int,
        evidence_days: int,
    ) -> None:
        if snapshot_days <= 0 or evidence_days <= 0:
            raise ValueError("retention windows must be positive")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("retention time must be timezone-aware")

        shanghai_now = now.astimezone(SHANGHAI)
        snapshot_cutoff = shanghai_now - timedelta(days=snapshot_days)
        evidence_cutoff = shanghai_now - timedelta(days=evidence_days)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                DELETE FROM research_snapshots
                WHERE calculated_at < ?
                  AND input_snapshot_id NOT IN (
                    SELECT input_snapshot_id
                    FROM (
                      SELECT
                        input_snapshot_id,
                        ROW_NUMBER() OVER (
                          PARTITION BY symbol, engine_version, catalog_version, rule_version
                          ORDER BY calculated_at DESC, input_snapshot_id DESC
                        ) AS version_rank
                      FROM research_snapshots
                    )
                    WHERE version_rank = 1
                  )
                """,
                (_timestamp_key(snapshot_cutoff),),
            )
            connection.execute(
                """
                DELETE FROM signal_evidence
                WHERE occurred_at < ?
                  AND NOT EXISTS (
                    SELECT 1
                    FROM research_snapshots AS snapshot,
                         json_each(snapshot.payload_json, '$.events') AS event
                    WHERE json_extract(event.value, '$.id') = signal_evidence.id
                  )
                """,
                (_timestamp_key(evidence_cutoff),),
            )
            connection.execute(
                "DELETE FROM shadow_batches WHERE trade_date < ?",
                (snapshot_cutoff.date().isoformat(),),
            )

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=_BUSY_TIMEOUT_MS / 1_000)
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)


def _dump_json(model: BaseModel) -> str:
    payload: dict[str, Any] = model.model_dump(mode="json")
    return _dump_value(payload)


def _dump_value(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _timestamp_key(value: str | datetime) -> str:
    timestamp = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=SHANGHAI)
    return timestamp.astimezone(SHANGHAI).isoformat(timespec="microseconds")


def _validate_snapshot_evidence(snapshot: CzscResearchSnapshot) -> None:
    expected_identity = (
        snapshot.input_snapshot_id,
        snapshot.engine_version,
        snapshot.catalog_version,
        snapshot.rule_version,
    )
    for evidence in [*snapshot.current_states, *snapshot.events]:
        identity = (
            evidence.input_snapshot_id,
            evidence.engine_version,
            evidence.catalog_version,
            evidence.rule_version,
        )
        if identity != expected_identity:
            raise ValueError("evidence does not match the snapshot input snapshot or versions")


def _snapshot_from_row(row: sqlite3.Row) -> CzscResearchSnapshot | None:
    snapshot = CzscResearchSnapshot.model_validate_json(row["payload_json"])
    indexed_identity = (
        row["input_snapshot_id"],
        row["symbol"],
        row["status"],
        row["engine_version"],
        row["catalog_version"],
        row["rule_version"],
        row["calculated_at"],
    )
    payload_identity = (
        snapshot.input_snapshot_id,
        snapshot.symbol,
        snapshot.status,
        snapshot.engine_version,
        snapshot.catalog_version,
        snapshot.rule_version,
        _timestamp_key(snapshot.calculated_at),
    )
    if indexed_identity != payload_identity:
        return None
    return snapshot


def _validate_batch_identity(batch_id: str, baseline_symbols: list[str]) -> None:
    if not batch_id.strip():
        raise ValueError("batch ID cannot be empty")
    if any(not symbol.strip() for symbol in baseline_symbols):
        raise ValueError("baseline symbol cannot be empty")
    if len(baseline_symbols) != len(set(baseline_symbols)):
        raise ValueError("batch baseline contains duplicate symbols")


def _baseline_symbols(row: sqlite3.Row) -> list[str]:
    payload = json.loads(row["baseline_symbols_json"])
    if (
        not isinstance(payload, list)
        or any(not isinstance(symbol, str) or not symbol for symbol in payload)
        or len(payload) != row["pool_size"]
        or len(payload) != len(set(payload))
    ):
        raise ValueError("stored batch baseline is invalid")
    return payload


def _score_from_row(
    row: sqlite3.Row,
    baseline_symbols: list[str],
) -> CzscV2CandidateScore:
    score = CzscV2CandidateScore.model_validate_json(row["payload_json"])
    rank = row["baseline_rank"]
    if not 1 <= rank <= len(baseline_symbols):
        raise ValueError("stored baseline rank is invalid")
    indexed_identity = (row["symbol"], rank, row["status"], row["score"])
    payload_identity = (score.symbol, score.baseline_rank, score.status, score.score)
    if indexed_identity != payload_identity or score.symbol != baseline_symbols[rank - 1]:
        raise ValueError("stored score does not match its immutable baseline")
    return score


def _validate_terminal_batch_status(
    status: CzscV2BatchStatus,
    items: list[CzscV2CandidateScore],
    pool_size: int,
) -> None:
    ready_count = sum(item.status == "ready" and item.score is not None for item in items)
    complete_all_ready = len(items) == pool_size and ready_count == pool_size
    if status == "ready":
        if not complete_all_ready:
            raise ValueError("ready batch requires every baseline symbol to have a ready score")
        return
    if status == "partial":
        if not items:
            raise ValueError("partial batch requires at least one processed item")
        if ready_count == 0:
            raise ValueError("partial batch requires at least one ready score")
        if complete_all_ready:
            raise ValueError("partial batch cannot contain a complete all-ready baseline")
        return
    if status == "unavailable" and ready_count:
        raise ValueError("unavailable batch cannot contain a ready score")
