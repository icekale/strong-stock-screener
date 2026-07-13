from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import sqlite3
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.models import ChanlunAnalysisResponse, ChanlunSignal, KlineBar
from app.services.chanlun.paper import ChanlunPaperOrderStore
from app.services.chanlun.paper_service import ChanlunPaperOrderService


SHANGHAI = ZoneInfo("Asia/Shanghai")


def test_paper_order_requires_manual_approval_before_reserving_cash(tmp_path: Path) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "chanlun" / "paper.sqlite3")
    draft = store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["5分钟确认买点"],
        created_at=datetime(2026, 7, 10, 10, 0, tzinfo=SHANGHAI),
    )

    before = store.account(initial_cash=10_000)
    approved = store.approve(draft.id, initial_cash=10_000, approved_at=datetime(2026, 7, 10, 10, 1, tzinfo=SHANGHAI))
    after = store.account(initial_cash=10_000)

    assert draft.status == "awaiting_confirmation"
    assert before.available_cash == 10_000
    assert approved.status == "simulated_open"
    assert after.reserved_cash == 1_000
    assert after.available_cash == 9_000


def test_paper_draft_requires_confirmed_multiperiod_buy_structure(tmp_path: Path) -> None:
    def analysis(period: str, signals: list[ChanlunSignal]) -> ChanlunAnalysisResponse:
        return ChanlunAnalysisResponse(
            symbol="600000.SH",
            period=period,  # type: ignore[arg-type]
            availability="ready",
            signals=signals,
            bars=[KlineBar(date="2026-07-10T10:00:00+08:00", open=10, high=10.2, low=9.8, close=10, volume=100)],
        )

    def buy_signal(signal_type: str) -> ChanlunSignal:
        return ChanlunSignal(
            id=f"signal:{signal_type}",
            type=signal_type,  # type: ignore[arg-type]
            occurred_at="2026-07-10T10:00:00+08:00",
            price=10.0,
            stroke_id="stroke:test",
            status="confirmed",
        )

    analyses = {
        "1d": analysis("1d", []),
        "60m": analysis("60m", [buy_signal("two_buy")]),
        "30m": analysis("30m", []),
        "5m": analysis("5m", [buy_signal("one_buy")]),
    }

    class AnalysisService:
        def analysis(self, _symbol, *, period, lookback, include_observing):
            return analyses[period]

    service = ChanlunPaperOrderService(
        analysis_service=AnalysisService(),
        store=ChanlunPaperOrderStore(tmp_path / "chanlun" / "paper.sqlite3"),
    )

    draft = service.create_draft("600000.SH", quantity=100, lookback=120)

    assert draft.status == "awaiting_confirmation"
    assert draft.reference_price == 10.0
    assert "5分钟确认买点" in draft.reasons
    assert draft.signal_snapshot["60m"]["signal"]["id"] == "signal:two_buy"
    assert draft.signal_snapshot["5m"]["signal"]["id"] == "signal:one_buy"


def test_cancelling_open_order_releases_reserved_cash(tmp_path: Path) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "chanlun" / "paper.sqlite3")
    draft = store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["5分钟确认买点"],
    )
    store.approve(draft.id, initial_cash=10_000)

    cancelled = store.cancel(draft.id)
    account = store.account(initial_cash=10_000)

    assert cancelled.status == "cancelled"
    assert cancelled.cancelled_at is not None
    assert account.reserved_cash == 0
    assert account.available_cash == 10_000
    assert account.audit_records[0].event == "cancelled"
    created = next(item for item in account.audit_records if item.event == "created")
    assert created.details["symbol"] == "600000.SH"
    assert created.details["quantity"] == 100
    assert created.details["rule_version"] == "cl-v1"
    assert created.details["reasons"] == ["5分钟确认买点"]


@pytest.mark.parametrize("status", ["filled", "rejected", "cancelled"])
def test_terminal_paper_order_cannot_be_cancelled(tmp_path: Path, status: str) -> None:
    store = ChanlunPaperOrderStore(tmp_path / f"{status}.sqlite3")
    draft = store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["测试"],
        status=status,
    )

    with pytest.raises(ValueError, match="待确认或模拟挂单"):
        store.cancel(draft.id)


def test_filling_open_order_applies_slippage_and_creates_position(tmp_path: Path) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "chanlun" / "paper.sqlite3")
    draft = store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["5分钟确认买点"],
    )
    store.approve(draft.id, initial_cash=10_000)

    filled = store.fill(
        draft.id,
        latest_price=10.123,
        quote_time="2026-07-10T10:05:00+08:00",
        initial_cash=10_000,
        filled_at=datetime(2026, 7, 10, 10, 5, 1, tzinfo=SHANGHAI),
    )
    account = store.account(initial_cash=10_000, latest_prices={"600000.SH": 10.5})

    assert filled.status == "filled"
    assert filled.fill_price == 10.13
    assert filled.fill_notional == 1_013
    assert filled.slippage_bps == 5
    assert filled.quote_time == "2026-07-10T10:05:00+08:00"
    assert filled.filled_at == "2026-07-10T10:05:01+08:00"
    assert account.reserved_cash == 0
    assert account.available_cash == 8_987
    assert account.total_equity == 10_037
    assert account.unrealized_pnl == 37
    assert account.realized_pnl == 0
    assert len(account.positions) == 1
    assert account.positions[0].average_price == 10.13
    assert account.positions[0].latest_price == 10.5
    assert account.positions[0].valuation_status == "live"
    assert account.positions[0].unrealized_pnl == 37
    assert "filled" in [item.event for item in account.audit_records]


def test_fill_rechecks_actual_cash_and_rejects_order_when_quote_rises(tmp_path: Path) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "chanlun" / "paper.sqlite3")
    draft = store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["5分钟确认买点"],
    )
    store.approve(draft.id, initial_cash=1_000)

    rejected = store.fill(
        draft.id,
        latest_price=10.1,
        quote_time="2026-07-10T10:05:00+08:00",
        initial_cash=1_000,
    )

    assert rejected.status == "rejected"
    assert rejected.rejection_reason == "模拟账户可用现金不足"
    assert store.account(initial_cash=1_000).reserved_cash == 0


def test_only_open_paper_order_can_be_filled(tmp_path: Path) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "chanlun" / "paper.sqlite3")
    draft = store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["测试"],
    )

    with pytest.raises(ValueError, match="只有模拟挂单可以更新成交"):
        store.fill(
            draft.id,
            latest_price=10.0,
            quote_time="2026-07-10T10:05:00+08:00",
            initial_cash=10_000,
        )


def test_existing_paper_database_is_migrated_without_losing_orders(tmp_path: Path) -> None:
    path = tmp_path / "chanlun" / "paper.sqlite3"
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE paper_orders (
              id TEXT PRIMARY KEY,
              symbol TEXT NOT NULL,
              quantity INTEGER NOT NULL,
              reference_price REAL NOT NULL,
              notional REAL NOT NULL,
              status TEXT NOT NULL,
              reasons_json TEXT NOT NULL,
              rule_version TEXT NOT NULL,
              created_at TEXT NOT NULL,
              approved_at TEXT,
              rejection_reason TEXT
            );
            INSERT INTO paper_orders VALUES (
              'paper-old', '600000.SH', 100, 10, 1000, 'simulated_open', '[]',
              'cl-v1', '2026-07-10T10:00:00+08:00', '2026-07-10T10:01:00+08:00', NULL
            );
            """
        )

    store = ChanlunPaperOrderStore(path)
    account = store.account(initial_cash=10_000)

    assert account.orders[0].id == "paper-old"
    assert account.orders[0].fill_price is None
    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(paper_orders)")}
    assert {
        "fill_price",
        "fill_notional",
        "quote_time",
        "filled_at",
        "cancelled_at",
        "signal_snapshot_json",
    } <= columns


def test_existing_paper_database_migration_is_safe_under_concurrent_first_access(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE paper_orders (
              id TEXT PRIMARY KEY, symbol TEXT NOT NULL, quantity INTEGER NOT NULL,
              reference_price REAL NOT NULL, notional REAL NOT NULL, status TEXT NOT NULL,
              reasons_json TEXT NOT NULL, rule_version TEXT NOT NULL, created_at TEXT NOT NULL,
              approved_at TEXT, rejection_reason TEXT
            );
            """
        )

    def open_store(_index: int) -> float:
        return ChanlunPaperOrderStore(path).account(initial_cash=10_000).available_cash

    with ThreadPoolExecutor(max_workers=8) as pool:
        balances = list(pool.map(open_store, range(16)))

    assert balances == [10_000] * 16


def test_concurrent_approval_only_transitions_order_once(tmp_path: Path) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "paper.sqlite3")
    draft = store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["测试"],
    )

    def approve(_index: int) -> str:
        try:
            return store.approve(draft.id, initial_cash=10_000).status
        except ValueError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(approve, range(16)))

    account = store.account(initial_cash=10_000)
    assert results.count("simulated_open") == 1
    assert [item.event for item in account.audit_records].count("approved") == 1


def test_concurrent_fill_and_cancel_only_transition_order_once(tmp_path: Path) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "paper.sqlite3")
    draft = store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["测试"],
    )
    store.approve(draft.id, initial_cash=10_000)
    barrier = Barrier(2)

    def fill() -> str:
        barrier.wait()
        try:
            return store.fill(
                draft.id,
                latest_price=10.0,
                quote_time="2026-07-10T10:05:00+08:00",
                initial_cash=10_000,
            ).status
        except ValueError:
            return "conflict"

    def cancel() -> str:
        barrier.wait()
        try:
            return store.cancel(draft.id).status
        except ValueError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(fill), pool.submit(cancel)]
        statuses = [item.result() for item in results]

    events = [item.event for item in store.account(initial_cash=10_000).audit_records]
    assert statuses.count("conflict") == 1
    assert sum(events.count(event) for event in ("filled", "cancelled")) == 1


def test_account_aggregation_uses_one_sqlite_read_snapshot(tmp_path: Path, monkeypatch) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "paper.sqlite3")
    statements: list[str] = []
    original_connect = sqlite3.connect

    def traced_connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(sqlite3, "connect", traced_connect)
    store.account(initial_cash=10_000)

    first_select = next(index for index, sql in enumerate(statements) if sql.startswith("SELECT"))
    assert any(sql == "BEGIN" for sql in statements[:first_select])


def test_account_marks_position_valuation_unavailable_without_live_quote(tmp_path: Path) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "paper.sqlite3")
    store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["历史成交"],
        status="filled",
    )

    account = store.account(initial_cash=10_000)

    assert account.valuation_complete is False
    assert account.unrealized_pnl is None
    assert account.positions[0].valuation_status == "unavailable"
    assert account.positions[0].latest_price is None
    assert account.positions[0].unrealized_pnl is None


def test_account_preserves_negative_cash_instead_of_overstating_equity(tmp_path: Path) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "paper.sqlite3")
    store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["历史成交"],
        status="filled",
    )

    account = store.account(initial_cash=500, latest_prices={"600000.SH": 10.0})

    assert account.available_cash == -500
    assert account.total_equity == 500


def test_fill_uses_financial_half_up_rounding_for_five_bps_slippage(tmp_path: Path) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "paper.sqlite3")
    draft = store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["测试"],
    )
    store.approve(draft.id, initial_cash=10_000)

    filled = store.fill(
        draft.id,
        latest_price=10.0,
        quote_time="2026-07-10T10:05:00+08:00",
        initial_cash=10_000,
    )

    assert filled.fill_price == 10.01
    assert filled.fill_notional == 1_001


def test_paper_service_fills_open_order_from_tickflow_quote(tmp_path: Path) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "paper.sqlite3")
    draft = store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["测试"],
    )
    store.approve(draft.id, initial_cash=10_000)

    class Quote:
        symbol = "600000.SH"
        last_price = 10.123
        quote_time = "2026-07-10T10:05:00+08:00"

    class QuoteProvider:
        def get_quotes(self, symbols):
            assert symbols == ["600000.SH"]
            return [Quote()]

    service = ChanlunPaperOrderService(
        analysis_service=object(),
        quote_provider=QuoteProvider(),
        store=store,
        initial_cash=10_000,
    )

    filled = service.fill(draft.id)
    account = service.account()

    assert filled.status == "filled"
    assert filled.fill_price == 10.13
    assert account.valuation_complete is True
    assert account.positions[0].latest_price == 10.123
    assert account.positions[0].quote_time == "2026-07-10T10:05:00+08:00"


def test_paper_service_does_not_fill_without_a_valid_realtime_quote(tmp_path: Path) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "paper.sqlite3")
    draft = store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["测试"],
    )
    store.approve(draft.id, initial_cash=10_000)

    class QuoteProvider:
        def get_quotes(self, _symbols):
            return []

    service = ChanlunPaperOrderService(
        analysis_service=object(),
        quote_provider=QuoteProvider(),
        store=store,
        initial_cash=10_000,
    )

    with pytest.raises(ValueError, match="TickFlow 未返回有效实时行情"):
        service.fill(draft.id)

    assert store.account(initial_cash=10_000).orders[0].status == "simulated_open"


def test_paper_service_rejects_non_open_order_before_requesting_quote(tmp_path: Path) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "paper.sqlite3")
    draft = store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["测试"],
    )

    class QuoteProvider:
        def get_quotes(self, _symbols):
            raise AssertionError("quote provider should not be called")

    service = ChanlunPaperOrderService(
        analysis_service=object(),
        quote_provider=QuoteProvider(),
        store=store,
        initial_cash=10_000,
    )

    with pytest.raises(ValueError, match="只有模拟挂单可以更新成交"):
        service.fill(draft.id)


def test_paper_service_persists_normalized_analysis_symbol(tmp_path: Path) -> None:
    def analysis(period: str) -> ChanlunAnalysisResponse:
        signal = ChanlunSignal(
            id=f"signal:{period}",
            type="one_buy",
            occurred_at="2026-07-10T10:00:00+08:00",
            price=10.0,
            stroke_id=f"stroke:{period}",
            status="confirmed",
        )
        return ChanlunAnalysisResponse(
            symbol="600000.SH",
            period=period,  # type: ignore[arg-type]
            availability="ready",
            signals=[] if period == "1d" else [signal],
            bars=[KlineBar(date="2026-07-10", open=10, high=10, low=10, close=10, volume=100)],
        )

    analyses = {period: analysis(period) for period in ("1d", "60m", "30m", "5m")}

    class AnalysisService:
        def analysis(self, _symbol, *, period, lookback, include_observing):
            return analyses[period]

    service = ChanlunPaperOrderService(
        analysis_service=AnalysisService(),
        store=ChanlunPaperOrderStore(tmp_path / "paper.sqlite3"),
    )

    draft = service.create_draft("600000", quantity=100, lookback=120)

    assert draft.symbol == "600000.SH"


def test_paper_service_requires_quote_timestamp_for_live_valuation(tmp_path: Path) -> None:
    store = ChanlunPaperOrderStore(tmp_path / "paper.sqlite3")
    store.create_draft(
        symbol="600000.SH",
        quantity=100,
        reference_price=10.0,
        reasons=["历史成交"],
        status="filled",
    )

    class Quote:
        symbol = "600000.SH"
        last_price = 10.5
        quote_time = None

    class QuoteProvider:
        def get_quotes(self, _symbols):
            return [Quote()]

    service = ChanlunPaperOrderService(
        analysis_service=object(),
        quote_provider=QuoteProvider(),
        store=store,
        initial_cash=10_000,
    )

    account = service.account()

    assert account.valuation_complete is False
    assert account.positions[0].valuation_status == "unavailable"
    assert account.positions[0].latest_price is None
