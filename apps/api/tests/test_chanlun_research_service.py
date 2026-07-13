from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date, datetime, time, timedelta
from pathlib import Path
from threading import Lock
from zoneinfo import ZoneInfo

import pytest

from app.services.chanlun import service as chanlun_service_module
from app.config import Settings
from app.models import (
    ChanlunAnalysisResponse,
    ChanlunPeriod,
    CzscResearchSnapshot,
    KlineBar,
    StrongStockSourceStatus,
)
from app.providers.tickflow import TickFlowIntradayBar
from app.services.chanlun.research_protocol import (
    APPROVED_PERIODS,
    CZSC_RC8_ENGINE_VERSION,
    CzscRc8PeriodDiagnostic,
    CzscRc8RawSignal,
    CzscRc8Request,
    CzscRc8Response,
    build_research_request,
)
from app.services.chanlun.research_service import CzscResearchService
from app.services.chanlun.service import ChanlunAnalysisService, ClosedWorkspaceInputs
from app.services.chanlun.store import ChanlunMinuteBarStore
from app.services.short_term_cache import TtlCache


SHANGHAI = ZoneInfo("Asia/Shanghai")


def _bars(period: ChanlunPeriod, count: int = 20) -> tuple[KlineBar, ...]:
    start = datetime(2026, 6, 1, 9, 30, tzinfo=SHANGHAI)
    step = {
        "1d": timedelta(days=1),
        "60m": timedelta(hours=1),
        "30m": timedelta(minutes=30),
        "5m": timedelta(minutes=5),
    }[period]
    output: list[KlineBar] = []
    for index in range(count):
        timestamp = start + step * index
        close = 10 + index / 100
        output.append(
            KlineBar(
                date=timestamp.date().isoformat()
                if period == "1d"
                else timestamp.isoformat(timespec="seconds"),
                open=close - 0.05,
                close=close,
                high=close + 0.1,
                low=close - 0.1,
                volume=100 + index,
                amount=1_000 + index,
            )
        )
    return tuple(output)


def _closed_inputs(
    *,
    availability: dict[ChanlunPeriod, str] | None = None,
    freshness: dict[ChanlunPeriod, str] | None = None,
    adjustment_mode: str = "raw_unadjusted",
    count: int = 20,
) -> ClosedWorkspaceInputs:
    periods = {period: _bars(period, count) for period in APPROVED_PERIODS}
    return ClosedWorkspaceInputs(
        symbol="600000.SH",
        periods=periods,
        availability={period: "ready" for period in APPROVED_PERIODS} | (availability or {}),
        freshness={period: "fresh" for period in APPROVED_PERIODS} | (freshness or {}),
        last_closed_by_period={period: periods[period][-1].date for period in APPROVED_PERIODS},
        adjustment_mode=adjustment_mode,
        source_status={
            period: (
                StrongStockSourceStatus(
                    source=f"fixture-{period}",
                    status="success",
                    detail="closed fixture bars",
                ),
            )
            for period in APPROVED_PERIODS
        },
    )


def _request(inputs: ClosedWorkspaceInputs) -> CzscRc8Request:
    decision_at = max(
        datetime.combine(
            datetime.fromisoformat(inputs.last_closed_by_period[period]).date(),
            time(15),
            tzinfo=SHANGHAI,
        )
        if period == "1d" and len(inputs.last_closed_by_period[period]) == 10
        else datetime.fromisoformat(inputs.last_closed_by_period[period])
        for period in APPROVED_PERIODS
    )
    return build_research_request(
        inputs.symbol,
        {period: list(inputs.periods[period]) for period in APPROVED_PERIODS},
        adjustment_mode=inputs.adjustment_mode,
        decision_at=decision_at,
        last_closed_by_period=inputs.last_closed_by_period,
    )


def _snapshot(request: CzscRc8Request) -> CzscResearchSnapshot:
    return CzscResearchSnapshot(
        status="ready",
        symbol=request.symbol,
        last_closed_by_period=dict(request.last_closed_by_period),
        input_snapshot_id=request.input_snapshot_id,
        score=12,
        engine_version=CZSC_RC8_ENGINE_VERSION,
        adjustment_mode=request.adjustment_mode,
    )


def _raw_signal(request: CzscRc8Request) -> CzscRc8RawSignal:
    boundary = request.last_closed_by_period["1d"]
    return CzscRc8RawSignal(
        catalog_id="trend.bi-status",
        period="1d",
        occurred_at=boundary,
        last_closed_bar_at=boundary,
        raw_key="日线_D1B_状态V230101",
        raw_value="向上_延伸_任意_0",
        value_fields={"v1": "向上", "v2": "延伸", "v3": "任意", "score": 0},
    )


def _response(request: CzscRc8Request) -> CzscRc8Response:
    signal = _raw_signal(request)
    return CzscRc8Response(
        request_id=request.request_id,
        input_snapshot_id=request.input_snapshot_id,
        status="ready",
        current_states=[signal],
        events=[signal],
        diagnostics={
            period: CzscRc8PeriodDiagnostic(
                bar_count=len(request.periods[period]),
                fractal_count=3,
                stroke_count=2,
                last_stroke_direction="向上",
            )
            for period in APPROVED_PERIODS
        },
    )


class StaticInputProvider:
    def __init__(self, inputs: ClosedWorkspaceInputs) -> None:
        self.inputs = inputs
        self.calls: list[tuple[str, int]] = []

    def closed_workspace_inputs(
        self,
        symbol: str,
        *,
        lookback: int,
        now: datetime | None = None,
    ) -> ClosedWorkspaceInputs:
        self.calls.append((symbol, lookback))
        return self.inputs


class FakeResearchStore:
    def __init__(
        self,
        snapshot: CzscResearchSnapshot | None = None,
        *,
        fail_load: bool = False,
        fail_save: bool = False,
    ) -> None:
        self.snapshots = {snapshot.input_snapshot_id: snapshot} if snapshot is not None else {}
        self.saved: list[CzscResearchSnapshot] = []
        self.fail_load = fail_load
        self.fail_save = fail_save
        self._lock = Lock()

    def load_snapshot(self, input_snapshot_id: str) -> CzscResearchSnapshot | None:
        if self.fail_load:
            raise RuntimeError("/private/store/load failed\nTraceback hidden")
        with self._lock:
            return self.snapshots.get(input_snapshot_id)

    def save_snapshot(self, snapshot: CzscResearchSnapshot) -> None:
        if self.fail_save:
            raise RuntimeError("/private/store/save failed\nTraceback hidden")
        with self._lock:
            self.snapshots[snapshot.input_snapshot_id] = snapshot
            self.saved.append(snapshot)


class RecordingRc8Client:
    def __init__(self, futures: list[Future[CzscRc8Response]] | None = None) -> None:
        self.futures = list(futures or [])
        self.requests: list[tuple[CzscRc8Request, int]] = []

    def submit(self, request: CzscRc8Request, priority: int) -> Future[CzscRc8Response]:
        self.requests.append((request, priority))
        if self.futures:
            return self.futures.pop(0)
        return Future()

    def health(self) -> dict[str, object]:
        return {
            "queue_depth": 0,
            "circuit_state": "closed",
            "engine_version": CZSC_RC8_ENGINE_VERSION,
            "last_error": None,
            "closed": False,
        }


class ImmediateReadyRc8Client(RecordingRc8Client):
    def submit(self, request: CzscRc8Request, priority: int) -> Future[CzscRc8Response]:
        future: Future[CzscRc8Response] = Future()
        self.requests.append((request, priority))
        future.set_result(_response(request))
        return future


class InvalidFutureRc8Client(RecordingRc8Client):
    def submit(self, request: CzscRc8Request, priority: int) -> object:
        self.requests.append((request, priority))
        return object()


class UnhealthyRc8Client(RecordingRc8Client):
    def health(self) -> dict[str, object]:
        return {
            "queue_depth": 2,
            "circuit_state": "closed",
            "engine_version": None,
            "last_error": "/private/worker.py failed\nTraceback secret",
            "closed": False,
        }


def _service(
    inputs: ClosedWorkspaceInputs,
    *,
    store: FakeResearchStore | None = None,
    client: object | None = None,
    enabled: bool = True,
) -> CzscResearchService:
    return CzscResearchService(
        store=store or FakeResearchStore(),
        client=client,
        input_provider=StaticInputProvider(inputs),
        settings=Settings(
            chanlun_rc8_enabled=enabled,
            chanlun_rc8_interactive_wait_seconds=0.1,
        ),
    )


def test_service_returns_cached_snapshot_without_submitting_worker() -> None:
    inputs = _closed_inputs()
    request = _request(inputs)
    store = FakeResearchStore(_snapshot(request))
    client = RecordingRc8Client()

    result = _service(inputs, store=store, client=client).get("600000.sh", lookback=220)

    assert result.status == "ready"
    assert result.input_snapshot_id == request.input_snapshot_id
    assert client.requests == []


def test_pending_call_reuses_submission_then_resolves_to_exact_store_hit() -> None:
    inputs = _closed_inputs()
    future: Future[CzscRc8Response] = Future()
    store = FakeResearchStore()
    client = RecordingRc8Client([future])
    service = _service(inputs, store=store, client=client)

    first = service.get("600000.SH", lookback=220, wait_seconds=0.001)
    second = service.get("600000.SH", lookback=220, wait_seconds=0.001)

    assert first.status == second.status == "pending"
    assert len(client.requests) == 1
    assert future.cancelled() is False

    request = client.requests[0][0]
    future.set_result(_response(request))
    resolved = service.get("600000.SH", lookback=220, wait_seconds=0.001)

    assert resolved.status == "ready"
    assert len(store.saved) == 1
    assert len(client.requests) == 1


def test_failed_completion_clears_inflight_before_notifying_waiters() -> None:
    inputs = _closed_inputs()
    failed: Future[CzscRc8Response] = Future()
    retry: Future[CzscRc8Response] = Future()
    client = RecordingRc8Client([failed, retry])
    service = _service(inputs, client=client)

    pending = service.get("600000.SH", lookback=220, wait_seconds=0.001)
    input_snapshot_id = client.requests[0][0].input_snapshot_id
    retried: list[CzscResearchSnapshot] = []
    service._inflight[input_snapshot_id].add_done_callback(
        lambda _future: retried.append(service.get("600000.SH", lookback=220, wait_seconds=0))
    )

    failed.set_exception(RuntimeError("worker failed"))

    assert pending.status == "pending"
    assert [snapshot.status for snapshot in retried] == ["pending"]
    assert len(client.requests) == 2

    retry.set_result(_response(client.requests[1][0]))
    assert service.get("600000.SH", lookback=220).status == "ready"


def test_concurrent_callers_coalesce_one_worker_submission() -> None:
    inputs = _closed_inputs()
    future: Future[CzscRc8Response] = Future()
    client = RecordingRc8Client([future])
    service = _service(inputs, client=client)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _index: service.get(
                    "600000.SH",
                    lookback=220,
                    wait_seconds=0.001,
                ),
                range(8),
            )
        )

    assert {result.status for result in results} == {"pending"}
    assert len(client.requests) == 1


@pytest.mark.parametrize(
    ("input_kind", "expected_status"),
    [
        ("stale", "stale"),
        ("insufficient", "insufficient_bars"),
        ("adjustment", "adjustment_mismatch"),
        ("unavailable", "unavailable"),
    ],
)
def test_non_scoreable_inputs_never_submit(
    input_kind: str,
    expected_status: str,
) -> None:
    inputs = (
        _closed_inputs(
            availability={"30m": "stale"},
            freshness={"30m": "stale"},
        )
        if input_kind == "stale"
        else _closed_inputs(
            availability={"5m": "insufficient_bars"},
            freshness={"5m": "insufficient"},
            count=10,
        )
        if input_kind == "insufficient"
        else _closed_inputs(
            availability={"1d": "unavailable"},
            freshness={"1d": "insufficient"},
        )
        if input_kind == "unavailable"
        else _closed_inputs(adjustment_mode="adjustment_mismatch")
    )
    client = RecordingRc8Client()

    result = _service(inputs, client=client).get("600000.SH", lookback=220)

    assert result.status == expected_status
    assert result.score is None
    assert client.requests == []


def test_disabled_or_missing_worker_returns_unavailable_without_raising() -> None:
    inputs = _closed_inputs()
    disabled_client = RecordingRc8Client()

    disabled = _service(inputs, client=disabled_client, enabled=False).get(
        "600000.SH",
        lookback=220,
    )
    missing = _service(inputs, client=None, enabled=True).get("600000.SH", lookback=220)

    assert disabled.status == missing.status == "unavailable"
    assert disabled_client.requests == []


def test_worker_failure_returns_sanitized_unavailable_and_retry_can_submit() -> None:
    inputs = _closed_inputs()
    failed: Future[CzscRc8Response] = Future()
    failed.set_exception(RuntimeError("/private/worker.py failed\nTraceback secret"))
    retry: Future[CzscRc8Response] = Future()
    client = RecordingRc8Client([failed, retry])
    service = _service(inputs, client=client)

    first = service.get("600000.SH", lookback=220, wait_seconds=0.1)
    second = service.get("600000.SH", lookback=220, wait_seconds=0.001)

    assert first.status == "unavailable"
    assert all(
        "Traceback" not in item.detail and "\n" not in item.detail for item in first.source_status
    )
    assert second.status == "pending"
    assert len(client.requests) == 2

    retry.set_result(_response(client.requests[1][0]))
    assert service.get("600000.SH", lookback=220).status == "ready"


def test_mapping_scoring_and_save_ready_path_handles_already_completed_future() -> None:
    inputs = _closed_inputs()
    store = FakeResearchStore()
    client = ImmediateReadyRc8Client()

    result = _service(inputs, store=store, client=client).get("600000.SH", lookback=220)

    assert result.status == "ready"
    assert result.score == 12
    assert result.eligible is False
    assert result.current_states[0].catalog_id == "trend.bi-status"
    assert result.current_states[0].params["v1"] == "向上"
    assert result.events[0].input_snapshot_id == result.input_snapshot_id
    assert store.saved == [result]
    assert len(client.requests) == 1


def test_store_failure_returns_unavailable_and_cleans_inflight_for_retry() -> None:
    inputs = _closed_inputs()
    store = FakeResearchStore(fail_save=True)
    client = ImmediateReadyRc8Client()
    service = _service(inputs, store=store, client=client)

    first = service.get("600000.SH", lookback=220)
    second = service.get("600000.SH", lookback=220)

    assert first.status == second.status == "unavailable"
    assert len(client.requests) == 2
    assert all("/private/" not in item.detail for item in first.source_status)


def test_callback_registration_failure_returns_unavailable_and_allows_retry() -> None:
    client = InvalidFutureRc8Client()
    service = _service(_closed_inputs(), client=client)

    first = service.get("600000.SH", lookback=220)
    second = service.get("600000.SH", lookback=220)

    assert first.status == second.status == "unavailable"
    assert len(client.requests) == 2


def test_health_marks_client_errors_unavailable_and_sanitizes_details() -> None:
    health = _service(_closed_inputs(), client=UnhealthyRc8Client()).health()

    assert health["status"] == "unavailable"
    assert health["queue_depth"] == 2
    assert "/private/" not in str(health["error"])
    assert "Traceback" not in str(health["error"])


def test_service_enforces_workspace_lookback_bounds() -> None:
    service = _service(_closed_inputs(), client=RecordingRc8Client())

    with pytest.raises(ValueError, match="between 20 and 260"):
        service.get("600000.SH", lookback=19)
    with pytest.raises(ValueError, match="between 20 and 260"):
        service.get("600000.SH", lookback=261)


def test_closed_workspace_cache_reuses_implicit_calls_across_a_minute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = object.__new__(ChanlunAnalysisService)
    service.closed_input_cache = TtlCache(ttl_seconds=60, name="closed-input-test")
    inputs = _closed_inputs()
    build_calls: list[datetime] = []

    def build(symbol: str, *, lookback: int, now: datetime) -> ClosedWorkspaceInputs:
        build_calls.append(now)
        return inputs

    service._build_closed_workspace_inputs = build  # type: ignore[method-assign]

    class SequencedDatetime(datetime):
        values = iter(
            (
                datetime(2026, 7, 10, 10, 0, 59, tzinfo=SHANGHAI),
                datetime(2026, 7, 10, 10, 1, 0, tzinfo=SHANGHAI),
            )
        )

        @classmethod
        def now(cls, tz: ZoneInfo | None = None) -> datetime:
            return next(cls.values)

    monkeypatch.setattr(chanlun_service_module, "datetime", SequencedDatetime)

    first = service.closed_workspace_inputs("600000.SH", lookback=220)
    second = service.closed_workspace_inputs("600000.SH", lookback=220)

    assert first is second
    assert len(build_calls) == 1
    assert service.closed_input_cache.snapshot()["size"] == 1


def test_backfill_clears_the_closed_workspace_cache() -> None:
    class EmptyHistoryProvider:
        source_name = "empty history"

        def get_minute_bars(self, symbol: str, *, max_bars: int) -> list[TickFlowIntradayBar]:
            return []

    class RecordingStore:
        def upsert(self, *args: object, **kwargs: object) -> None:
            pass

        def prune(self, *, keep_days: int) -> None:
            pass

    service = object.__new__(ChanlunAnalysisService)
    service.history_provider = EmptyHistoryProvider()
    service.history_max_bars = 100
    service.minute_retention_days = 30
    service.store = RecordingStore()
    service.cache = TtlCache(ttl_seconds=60, name="analysis-test")
    service.closed_input_cache = TtlCache(ttl_seconds=60, name="closed-input-test")
    service.closed_input_cache.get_or_set("cached", _closed_inputs)

    service.backfill(
        "600000.SH",
        progress=lambda _current, _total, _message: None,
        should_cancel=lambda: False,
    )

    assert service.closed_input_cache.snapshot()["size"] == 0


def _minute_bar(timestamp: datetime, close: float) -> TickFlowIntradayBar:
    return TickFlowIntradayBar(
        timestamp=int(timestamp.timestamp() * 1000),
        open=close - 0.02,
        high=close + 0.05,
        low=close - 0.05,
        close=close,
        volume=100,
        amount=1_000,
        prev_close=close - 0.1,
    )


def _trading_minutes(day: date) -> list[TickFlowIntradayBar]:
    timestamps = [
        datetime.combine(day, time(9, 30), tzinfo=SHANGHAI) + timedelta(minutes=index)
        for index in range(120)
    ]
    timestamps.extend(
        datetime.combine(day, time(13), tzinfo=SHANGHAI) + timedelta(minutes=index)
        for index in range(120)
    )
    return [
        _minute_bar(timestamp, 10 + index / 10_000) for index, timestamp in enumerate(timestamps)
    ]


class CountingDailyProvider:
    source_name = "counting daily"
    adjust = "raw"

    def __init__(self, bars: list[KlineBar]) -> None:
        self.bars = bars
        self.calls = 0
        self._lock = Lock()

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        with self._lock:
            self.calls += 1
        return list(self.bars[-count:])


class CountingIntradayProvider:
    source_name = "counting intraday"

    def __init__(self, bars: list[TickFlowIntradayBar]) -> None:
        self.bars = bars
        self.calls = 0
        self._lock = Lock()

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        with self._lock:
            self.calls += 1
        return {symbol: list(self.bars[-count:]) for symbol in symbols}


class ReadyAdapter:
    def analyze(
        self,
        symbol: str,
        *,
        period: ChanlunPeriod,
        bars: list[KlineBar],
        include_observing: bool = False,
    ) -> ChanlunAnalysisResponse:
        return ChanlunAnalysisResponse(
            symbol=symbol,
            period=period,
            availability="ready",
            bars=bars,
            last_closed_bar_at=bars[-1].date,
        )


class FixedNowInputProvider:
    def __init__(self, service: ChanlunAnalysisService, now: datetime) -> None:
        self.service = service
        self.now = now

    def closed_workspace_inputs(
        self,
        symbol: str,
        *,
        lookback: int,
        now: datetime | None = None,
    ) -> ClosedWorkspaceInputs:
        return self.service.closed_workspace_inputs(symbol, lookback=lookback, now=self.now)


def test_formal_and_research_parallel_calls_share_closed_fetch_and_exclude_open_bars(
    tmp_path: Path,
) -> None:
    current_day = date(2026, 7, 10)
    now = datetime.combine(current_day, time(14, 59), tzinfo=SHANGHAI)
    daily_bars = [
        KlineBar(
            date=(current_day - timedelta(days=20 - index)).isoformat(),
            open=10,
            close=10.1,
            high=10.2,
            low=9.9,
            volume=100,
        )
        for index in range(20)
    ]
    daily_bars.append(
        KlineBar(
            date=current_day.isoformat(),
            open=10.1,
            close=10.2,
            high=10.3,
            low=10,
            volume=100,
        )
    )
    minute_bars = [
        bar
        for day_offset in (9, 8, 7, 6, 5, 0)
        for bar in _trading_minutes(current_day - timedelta(days=day_offset))
    ]
    daily_provider = CountingDailyProvider(daily_bars)
    intraday_provider = CountingIntradayProvider(minute_bars)
    analysis_service = ChanlunAnalysisService(
        store=ChanlunMinuteBarStore(tmp_path / "minute.sqlite3"),
        intraday_provider=intraday_provider,
        history_provider=None,
        adapter=ReadyAdapter(),
        daily_provider=daily_provider,
        cache_seconds=60,
    )
    research_service = CzscResearchService(
        store=FakeResearchStore(),
        client=None,
        input_provider=FixedNowInputProvider(analysis_service, now),
        settings=Settings(chanlun_rc8_enabled=True),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        formal_future = executor.submit(
            analysis_service.workspace,
            "600000.SH",
            lookback=24,
            now=now,
        )
        research_future = executor.submit(
            research_service.get,
            "600000.SH",
            24,
        )
        workspace = formal_future.result(timeout=2)
        research = research_future.result(timeout=2)

    closed = analysis_service.closed_workspace_inputs("600000.SH", lookback=24, now=now)

    assert research.status == "unavailable"
    assert daily_provider.calls == 1
    assert intraday_provider.calls == 1
    assert set(closed.periods) == set(APPROVED_PERIODS)
    assert set(closed.availability) == set(APPROVED_PERIODS)
    assert set(closed.freshness) == set(APPROVED_PERIODS)
    assert set(closed.last_closed_by_period) == set(APPROVED_PERIODS)
    assert set(closed.source_status) == set(APPROVED_PERIODS)
    assert set(closed.adjustment_by_period) == set(APPROVED_PERIODS)
    assert set(closed.availability.values()) == {"ready"}
    assert set(closed.freshness.values()) == {"fresh"}
    assert closed.adjustment_mode == "raw_unadjusted"
    assert closed.last_closed_by_period["1d"] == "2026-07-09T15:00:00+08:00"
    assert all(bar.date != current_day.isoformat() for bar in closed.periods["1d"])
    assert all(bar.date != current_day.isoformat() for bar in workspace.analysis.bars)
    assert closed.periods["5m"][-1].date == "2026-07-10T14:55:00+08:00"
