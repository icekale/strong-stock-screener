from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from threading import Lock
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.models import (
    ChanlunPaperAccount,
    ChanlunPaperAuditRecord,
    ChanlunPaperOrder,
    ChanlunPaperPosition,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_orders (
  id TEXT PRIMARY KEY,
  symbol TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  reference_price REAL NOT NULL,
  notional REAL NOT NULL,
  status TEXT NOT NULL,
  reasons_json TEXT NOT NULL,
  signal_snapshot_json TEXT NOT NULL DEFAULT '{}',
  rule_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  approved_at TEXT,
  fill_price REAL,
  fill_notional REAL,
  slippage_bps INTEGER,
  quote_time TEXT,
  filled_at TEXT,
  cancelled_at TEXT,
  rejection_reason TEXT
);
CREATE INDEX IF NOT EXISTS paper_orders_created_idx ON paper_orders(created_at DESC);
CREATE TABLE IF NOT EXISTS paper_order_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id TEXT NOT NULL,
  event TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  details_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS paper_order_events_time_idx
ON paper_order_events(occurred_at DESC, id DESC);
"""

_ORDER_MIGRATIONS = {
    "signal_snapshot_json": "TEXT NOT NULL DEFAULT '{}'",
    "fill_price": "REAL",
    "fill_notional": "REAL",
    "slippage_bps": "INTEGER",
    "quote_time": "TEXT",
    "filled_at": "TEXT",
    "cancelled_at": "TEXT",
}

_SCHEMA_LOCK = Lock()


class ChanlunPaperOrderStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._ensure_schema()

    def create_draft(
        self,
        *,
        symbol: str,
        quantity: int,
        reference_price: float,
        reasons: list[str],
        signal_snapshot: dict[str, object] | None = None,
        created_at: datetime | None = None,
        rule_version: str = "cl-v1",
        status: str = "awaiting_confirmation",
        rejection_reason: str | None = None,
    ) -> ChanlunPaperOrder:
        order = ChanlunPaperOrder(
            id=f"paper-{uuid4().hex}",
            symbol=symbol,
            quantity=quantity,
            reference_price=reference_price,
            notional=round(quantity * reference_price, 2),
            reasons=reasons,
            signal_snapshot=signal_snapshot or {},
            rule_version=rule_version,
            created_at=_format_timestamp(created_at or datetime.now(tz=SHANGHAI)),
            status=status,  # type: ignore[arg-type]
            rejection_reason=rejection_reason,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO paper_orders (
                  id, symbol, quantity, reference_price, notional, status, reasons_json, signal_snapshot_json,
                  rule_version, created_at, approved_at, fill_price, fill_notional,
                  slippage_bps, quote_time, filled_at, cancelled_at, rejection_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.id,
                    order.symbol,
                    order.quantity,
                    order.reference_price,
                    order.notional,
                    order.status,
                    json.dumps(order.reasons, ensure_ascii=False),
                    json.dumps(order.signal_snapshot, ensure_ascii=False),
                    order.rule_version,
                    order.created_at,
                    order.approved_at,
                    order.fill_price,
                    order.fill_notional,
                    order.slippage_bps,
                    order.quote_time,
                    order.filled_at,
                    order.cancelled_at,
                    order.rejection_reason,
                ),
            )
            _record_event(connection, order.id, "created", order.created_at, _order_snapshot(order))
        return order

    def approve(
        self,
        order_id: str,
        *,
        initial_cash: float,
        approved_at: datetime | None = None,
    ) -> ChanlunPaperOrder:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM paper_orders WHERE id = ?", (order_id,)).fetchone()
            if row is None:
                raise KeyError(order_id)
            order = _order_from_row(row)
            if order.status != "awaiting_confirmation":
                raise ValueError("只有待确认草案可以批准")
            reserved = _reserved_cash(connection)
            spent = _spent_cash(connection)
            approved = _format_timestamp(approved_at or datetime.now(tz=SHANGHAI))
            if order.notional > initial_cash - spent - reserved:
                connection.execute(
                    "UPDATE paper_orders SET status = ?, rejection_reason = ? WHERE id = ?",
                    ("rejected", "模拟账户可用现金不足", order_id),
                )
                _record_event(
                    connection,
                    order_id,
                    "rejected",
                    approved,
                    {**_order_snapshot(order), "reason": "模拟账户可用现金不足"},
                )
            else:
                connection.execute(
                    "UPDATE paper_orders SET status = ?, approved_at = ? WHERE id = ?",
                    ("simulated_open", approved, order_id),
                )
                _record_event(connection, order_id, "approved", approved, _order_snapshot(order))
            updated = connection.execute("SELECT * FROM paper_orders WHERE id = ?", (order_id,)).fetchone()
        return _order_from_row(updated)

    def get(self, order_id: str) -> ChanlunPaperOrder:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM paper_orders WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            raise KeyError(order_id)
        return _order_from_row(row)

    def cancel(self, order_id: str, *, cancelled_at: datetime | None = None) -> ChanlunPaperOrder:
        cancelled = _format_timestamp(cancelled_at or datetime.now(tz=SHANGHAI))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM paper_orders WHERE id = ?", (order_id,)).fetchone()
            if row is None:
                raise KeyError(order_id)
            order = _order_from_row(row)
            if order.status not in {"awaiting_confirmation", "simulated_open"}:
                raise ValueError("只有待确认或模拟挂单可以撤销")
            connection.execute(
                "UPDATE paper_orders SET status = 'cancelled', cancelled_at = ? WHERE id = ?",
                (cancelled, order_id),
            )
            _record_event(connection, order_id, "cancelled", cancelled, _order_snapshot(order))
            updated = connection.execute("SELECT * FROM paper_orders WHERE id = ?", (order_id,)).fetchone()
        return _order_from_row(updated)

    def fill(
        self,
        order_id: str,
        *,
        latest_price: float,
        quote_time: str,
        initial_cash: float,
        filled_at: datetime | None = None,
        slippage_bps: int = 5,
    ) -> ChanlunPaperOrder:
        if latest_price <= 0:
            raise ValueError("实时价格必须大于零")
        filled = _format_timestamp(filled_at or datetime.now(tz=SHANGHAI))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM paper_orders WHERE id = ?", (order_id,)).fetchone()
            if row is None:
                raise KeyError(order_id)
            order = _order_from_row(row)
            if order.status != "simulated_open":
                raise ValueError("只有模拟挂单可以更新成交")
            fill_price_decimal = (
                Decimal(str(latest_price))
                * (Decimal(10_000 + slippage_bps) / Decimal(10_000))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            fill_price = float(fill_price_decimal)
            fill_notional = float(
                (fill_price_decimal * order.quantity).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )
            )
            cash_after_other_orders = (
                initial_cash
                - _spent_cash(connection)
                - _reserved_cash(connection, exclude_order_id=order_id)
            )
            if fill_notional > cash_after_other_orders:
                reason = "模拟账户可用现金不足"
                connection.execute(
                    "UPDATE paper_orders SET status = 'rejected', rejection_reason = ? WHERE id = ?",
                    (reason, order_id),
                )
                _record_event(
                    connection,
                    order_id,
                    "rejected",
                    filled,
                    {**_order_snapshot(order), "reason": reason},
                )
            else:
                connection.execute(
                    """
                    UPDATE paper_orders
                    SET status = 'filled', fill_price = ?, fill_notional = ?, slippage_bps = ?,
                        quote_time = ?, filled_at = ?, rejection_reason = NULL
                    WHERE id = ?
                    """,
                    (fill_price, fill_notional, slippage_bps, quote_time, filled, order_id),
                )
                _record_event(
                    connection,
                    order_id,
                    "filled",
                    filled,
                    {
                        **_order_snapshot(order),
                        "fill_price": fill_price,
                        "fill_notional": fill_notional,
                        "quote_time": quote_time,
                        "slippage_bps": slippage_bps,
                    },
                )
            updated = connection.execute("SELECT * FROM paper_orders WHERE id = ?", (order_id,)).fetchone()
        return _order_from_row(updated)

    def account(
        self,
        *,
        initial_cash: float,
        limit: int = 100,
        latest_prices: dict[str, float] | None = None,
        latest_quote_times: dict[str, str] | None = None,
    ) -> ChanlunPaperAccount:
        with self._connect() as connection:
            connection.execute("BEGIN")
            reserved = _reserved_cash(connection)
            spent = _spent_cash(connection)
            rows = connection.execute(
                "SELECT * FROM paper_orders ORDER BY created_at DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
            filled_rows = connection.execute(
                "SELECT * FROM paper_orders WHERE status = 'filled' ORDER BY filled_at, created_at"
            ).fetchall()
            event_rows = connection.execute(
                "SELECT * FROM paper_order_events ORDER BY occurred_at DESC, id DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        positions = _positions_from_rows(
            filled_rows,
            latest_prices or {},
            latest_quote_times or {},
        )
        available = round(initial_cash - spent - reserved, 2)
        valuation_complete = all(item.valuation_status == "live" for item in positions)
        unrealized = (
            round(sum(item.unrealized_pnl or 0 for item in positions), 2)
            if valuation_complete
            else None
        )
        total_equity = round(available + reserved + sum(item.market_value for item in positions), 2)
        return ChanlunPaperAccount(
            initial_cash=initial_cash,
            reserved_cash=round(reserved, 2),
            available_cash=available,
            total_equity=total_equity,
            unrealized_pnl=unrealized,
            realized_pnl=0,
            valuation_complete=valuation_complete,
            valuation_time=max(
                (item.quote_time for item in positions if item.quote_time),
                default=None,
            ),
            positions=positions,
            orders=[_order_from_row(row) for row in rows],
            audit_records=[_audit_from_row(row) for row in event_rows],
        )

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _SCHEMA_LOCK, sqlite3.connect(self.path, timeout=30) as connection:
            connection.executescript(_SCHEMA)
            connection.execute("BEGIN EXCLUSIVE")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(paper_orders)")}
            for name, sql_type in _ORDER_MIGRATIONS.items():
                if name not in columns:
                    connection.execute(f"ALTER TABLE paper_orders ADD COLUMN {name} {sql_type}")


def _reserved_cash(connection: sqlite3.Connection, *, exclude_order_id: str | None = None) -> float:
    query = "SELECT COALESCE(SUM(notional), 0) AS value FROM paper_orders WHERE status = 'simulated_open'"
    params: tuple[str, ...] = ()
    if exclude_order_id is not None:
        query += " AND id != ?"
        params = (exclude_order_id,)
    row = connection.execute(query, params).fetchone()
    return float(row["value"])


def _spent_cash(connection: sqlite3.Connection) -> float:
    row = connection.execute(
        """
        SELECT COALESCE(SUM(COALESCE(fill_notional, notional)), 0) AS value
        FROM paper_orders WHERE status = 'filled'
        """
    ).fetchone()
    return float(row["value"])


def _record_event(
    connection: sqlite3.Connection,
    order_id: str,
    event: str,
    occurred_at: str,
    details: dict[str, object] | None = None,
) -> None:
    connection.execute(
        "INSERT INTO paper_order_events (order_id, event, occurred_at, details_json) VALUES (?, ?, ?, ?)",
        (order_id, event, occurred_at, json.dumps(details or {}, ensure_ascii=False)),
    )


def _order_snapshot(order: ChanlunPaperOrder) -> dict[str, object]:
    return {
        "symbol": order.symbol,
        "side": order.side,
        "quantity": order.quantity,
        "reference_price": order.reference_price,
        "notional": order.notional,
        "reasons": order.reasons,
        "signal_snapshot": order.signal_snapshot,
        "rule_version": order.rule_version,
        "status_before": order.status,
    }


def _positions_from_rows(
    rows: list[sqlite3.Row],
    latest_prices: dict[str, float],
    latest_quote_times: dict[str, str],
) -> list[ChanlunPaperPosition]:
    totals: dict[str, tuple[int, float]] = {}
    for row in rows:
        quantity, cost = totals.get(row["symbol"], (0, 0.0))
        totals[row["symbol"]] = (
            quantity + int(row["quantity"]),
            cost + float(row["fill_notional"] or row["notional"]),
        )
    positions: list[ChanlunPaperPosition] = []
    for symbol, (quantity, raw_cost) in sorted(totals.items()):
        cost = round(raw_cost, 2)
        average = round(cost / quantity, 4)
        latest = latest_prices.get(symbol)
        if latest is not None and latest <= 0:
            latest = None
        mark_price = latest if latest is not None else average
        market_value = round(quantity * mark_price, 2)
        unrealized = round(market_value - cost, 2) if latest is not None else None
        positions.append(
            ChanlunPaperPosition(
                symbol=symbol,
                quantity=quantity,
                average_price=average,
                latest_price=latest,
                quote_time=latest_quote_times.get(symbol) if latest is not None else None,
                valuation_status="live" if latest is not None else "unavailable",
                cost_basis=cost,
                market_value=market_value,
                unrealized_pnl=unrealized,
                unrealized_pnl_pct=(
                    round(unrealized / cost * 100, 2)
                    if unrealized is not None
                    else None
                ),
            )
        )
    return positions


def _audit_from_row(row: sqlite3.Row) -> ChanlunPaperAuditRecord:
    return ChanlunPaperAuditRecord(
        id=row["id"],
        order_id=row["order_id"],
        event=row["event"],
        occurred_at=row["occurred_at"],
        details=json.loads(row["details_json"]),
    )


def _format_timestamp(value: datetime) -> str:
    timestamp = value.replace(tzinfo=SHANGHAI) if value.tzinfo is None else value.astimezone(SHANGHAI)
    return timestamp.isoformat(timespec="seconds")


def _order_from_row(row: sqlite3.Row) -> ChanlunPaperOrder:
    return ChanlunPaperOrder(
        id=row["id"],
        symbol=row["symbol"],
        quantity=row["quantity"],
        reference_price=row["reference_price"],
        notional=row["notional"],
        status=row["status"],
        reasons=json.loads(row["reasons_json"]),
        signal_snapshot=json.loads(row["signal_snapshot_json"]),
        rule_version=row["rule_version"],
        created_at=row["created_at"],
        approved_at=row["approved_at"],
        fill_price=row["fill_price"],
        fill_notional=row["fill_notional"],
        slippage_bps=row["slippage_bps"],
        quote_time=row["quote_time"],
        filled_at=row["filled_at"],
        cancelled_at=row["cancelled_at"],
        rejection_reason=row["rejection_reason"],
    )
