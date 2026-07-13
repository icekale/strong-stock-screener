from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.models import ChanlunAlertItem, ChanlunSignal


SHANGHAI = ZoneInfo("Asia/Shanghai")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alert_watches (
  symbol TEXT NOT NULL,
  period TEXT NOT NULL,
  initialized_at TEXT NOT NULL,
  PRIMARY KEY (symbol, period)
);
CREATE TABLE IF NOT EXISTS observed_alert_signals (
  alert_key TEXT PRIMARY KEY,
  symbol TEXT NOT NULL,
  period TEXT NOT NULL,
  signal_type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  price REAL NOT NULL,
  rule_version TEXT NOT NULL,
  observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chanlun_alerts (
  alert_key TEXT PRIMARY KEY,
  symbol TEXT NOT NULL,
  period TEXT NOT NULL,
  signal_type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  price REAL NOT NULL,
  rule_version TEXT NOT NULL,
  first_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS chanlun_alerts_symbol_seen_idx
  ON chanlun_alerts(symbol, first_seen_at DESC);
"""


@dataclass(frozen=True)
class AlertObservation:
    baselined: bool
    created: list[ChanlunAlertItem]


class ChanlunAlertStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def observe(
        self,
        symbol: str,
        period: str,
        signals: list[ChanlunSignal],
        *,
        now: datetime | None = None,
    ) -> AlertObservation:
        observed_at = _format_timestamp(now or datetime.now(tz=SHANGHAI))
        confirmed = [signal for signal in signals if signal.status in {"confirmed", "final"}]
        with self._connect() as connection:
            watch = connection.execute(
                "SELECT 1 FROM alert_watches WHERE symbol = ? AND period = ?",
                (symbol, period),
            ).fetchone()
            baselined = watch is None
            if baselined:
                connection.execute(
                    "INSERT INTO alert_watches (symbol, period, initialized_at) VALUES (?, ?, ?)",
                    (symbol, period, observed_at),
                )

            created: list[ChanlunAlertItem] = []
            for signal in confirmed:
                key = _alert_key(symbol, period, signal)
                inserted = connection.execute(
                    """
                    INSERT OR IGNORE INTO observed_alert_signals (
                      alert_key, symbol, period, signal_type, occurred_at, price, rule_version, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key,
                        symbol,
                        period,
                        signal.type,
                        signal.occurred_at,
                        signal.price,
                        signal.rule_version,
                        observed_at,
                    ),
                )
                if baselined or inserted.rowcount == 0:
                    continue
                item = ChanlunAlertItem(
                    key=key,
                    symbol=symbol,
                    period=period,  # type: ignore[arg-type]
                    signal_type=signal.type,
                    occurred_at=signal.occurred_at,
                    price=signal.price,
                    rule_version=signal.rule_version,
                    first_seen_at=observed_at,
                )
                connection.execute(
                    """
                    INSERT INTO chanlun_alerts (
                      alert_key, symbol, period, signal_type, occurred_at, price, rule_version, first_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.key,
                        item.symbol,
                        item.period,
                        item.signal_type,
                        item.occurred_at,
                        item.price,
                        item.rule_version,
                        item.first_seen_at,
                    ),
                )
                created.append(item)
        return AlertObservation(baselined=baselined, created=created)

    def list(self, *, symbol: str | None = None, limit: int = 100) -> list[ChanlunAlertItem]:
        where = ""
        parameters: list[object] = []
        if symbol:
            where = "WHERE symbol = ?"
            parameters.append(symbol)
        parameters.append(max(1, min(limit, 500)))
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM chanlun_alerts {where} ORDER BY first_seen_at DESC LIMIT ?",
                parameters,
            ).fetchall()
        return [_item_from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.executescript(_SCHEMA)
        return connection


def _alert_key(symbol: str, period: str, signal: ChanlunSignal) -> str:
    return f"{symbol}:{period}:{signal.type}:{signal.occurred_at}:{signal.rule_version}"


def _format_timestamp(value: datetime) -> str:
    timestamp = value.replace(tzinfo=SHANGHAI) if value.tzinfo is None else value.astimezone(SHANGHAI)
    return timestamp.isoformat(timespec="seconds")


def _item_from_row(row: sqlite3.Row) -> ChanlunAlertItem:
    return ChanlunAlertItem(
        key=row["alert_key"],
        symbol=row["symbol"],
        period=row["period"],
        signal_type=row["signal_type"],
        occurred_at=row["occurred_at"],
        price=row["price"],
        rule_version=row["rule_version"],
        first_seen_at=row["first_seen_at"],
    )
