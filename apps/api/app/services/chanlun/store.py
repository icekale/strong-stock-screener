from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.providers.tickflow import TickFlowIntradayBar


SHANGHAI = ZoneInfo("Asia/Shanghai")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS minute_bars (
  symbol TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  trade_date TEXT NOT NULL,
  open REAL NOT NULL,
  high REAL NOT NULL,
  low REAL NOT NULL,
  close REAL NOT NULL,
  volume REAL NOT NULL,
  amount REAL NOT NULL,
  prev_close REAL,
  source TEXT NOT NULL,
  adjustment_mode TEXT NOT NULL,
  captured_at TEXT NOT NULL,
  closed INTEGER NOT NULL,
  PRIMARY KEY (symbol, timestamp, adjustment_mode)
);
CREATE INDEX IF NOT EXISTS minute_bars_symbol_date_idx
  ON minute_bars(symbol, trade_date, timestamp);
"""


@dataclass(frozen=True)
class StoredMinuteBar:
    symbol: str
    timestamp: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    prev_close: float | None
    source: str
    adjustment_mode: str
    captured_at: str
    closed: bool


class ChanlunMinuteBarStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def upsert(
        self,
        symbol: str,
        bars: list[TickFlowIntradayBar],
        *,
        source: str,
        closed: bool,
        adjustment_mode: str = "raw_unadjusted",
        captured_at: datetime | None = None,
    ) -> None:
        captured = _format_timestamp(captured_at or datetime.now(tz=SHANGHAI))
        rows = [
            _bar_values(
                symbol=symbol,
                bar=bar,
                source=source,
                adjustment_mode=adjustment_mode,
                captured_at=captured,
                closed=closed,
            )
            for bar in bars
        ]
        if not rows:
            return

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO minute_bars (
                  symbol, timestamp, trade_date, open, high, low, close, volume, amount,
                  prev_close, source, adjustment_mode, captured_at, closed
                ) VALUES (
                  :symbol, :timestamp, :trade_date, :open, :high, :low, :close, :volume, :amount,
                  :prev_close, :source, :adjustment_mode, :captured_at, :closed
                )
                ON CONFLICT(symbol, timestamp, adjustment_mode) DO UPDATE SET
                  open = excluded.open,
                  high = excluded.high,
                  low = excluded.low,
                  close = excluded.close,
                  volume = excluded.volume,
                  amount = excluded.amount,
                  prev_close = excluded.prev_close,
                  source = excluded.source,
                  captured_at = excluded.captured_at,
                  closed = CASE WHEN excluded.closed = 1 THEN 1 ELSE minute_bars.closed END
                WHERE minute_bars.closed = 0
                """,
                rows,
            )

    def read(
        self,
        symbol: str,
        *,
        start_at: str | None = None,
        end_at: str | None = None,
        adjustment_mode: str = "raw_unadjusted",
    ) -> list[StoredMinuteBar]:
        clauses = ["symbol = ?", "adjustment_mode = ?"]
        parameters: list[str] = [symbol, adjustment_mode]
        if start_at is not None:
            clauses.append("timestamp >= ?")
            parameters.append(start_at)
        if end_at is not None:
            clauses.append("timestamp <= ?")
            parameters.append(end_at)

        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM minute_bars WHERE {' AND '.join(clauses)} ORDER BY timestamp ASC",
                parameters,
            ).fetchall()
        return [_stored_bar_from_row(row) for row in rows]

    def prune(self, keep_days: int = 60) -> None:
        cutoff = date.today() - timedelta(days=max(1, keep_days))
        with self._connect() as connection:
            connection.execute("DELETE FROM minute_bars WHERE trade_date < ?", (cutoff.isoformat(),))

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.executescript(_SCHEMA)
        return connection


def _bar_values(
    *,
    symbol: str,
    bar: TickFlowIntradayBar,
    source: str,
    adjustment_mode: str,
    captured_at: str,
    closed: bool,
) -> dict[str, str | float | int | None]:
    timestamp = datetime.fromtimestamp(bar.timestamp / 1000, tz=SHANGHAI)
    return {
        "symbol": symbol,
        "timestamp": _format_timestamp(timestamp),
        "trade_date": timestamp.date().isoformat(),
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "amount": bar.amount,
        "prev_close": bar.prev_close,
        "source": source,
        "adjustment_mode": adjustment_mode,
        "captured_at": captured_at,
        "closed": int(closed),
    }


def _format_timestamp(timestamp: datetime) -> str:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=SHANGHAI)
    else:
        timestamp = timestamp.astimezone(SHANGHAI)
    return timestamp.isoformat(timespec="seconds")


def _stored_bar_from_row(row: sqlite3.Row) -> StoredMinuteBar:
    return StoredMinuteBar(
        symbol=row["symbol"],
        timestamp=row["timestamp"],
        trade_date=row["trade_date"],
        open=row["open"],
        high=row["high"],
        low=row["low"],
        close=row["close"],
        volume=row["volume"],
        amount=row["amount"],
        prev_close=row["prev_close"],
        source=row["source"],
        adjustment_mode=row["adjustment_mode"],
        captured_at=row["captured_at"],
        closed=bool(row["closed"]),
    )
