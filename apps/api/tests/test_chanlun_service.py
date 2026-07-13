from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.services.chanlun import service as chanlun_service_module
from app.config import Settings
from app.main import _chanlun_analysis_service, _kline_provider, app, update_runtime_settings
from app.models import (
    ChanlunAnalysisResponse,
    ChanlunSignal,
    ChanlunStroke,
    ChanlunZone,
    KlineBar,
    StrongStockDataUnavailable,
    StrongStockSourceStatus,
)
from app.providers.tickflow import (
    TickFlowDailyKlineProvider,
    TickFlowIntradayBar,
    TickFlowQuoteProvider,
)
from app.services.runtime_settings import SettingsUpdate
from app.services.chanlun.service import (
    ChanlunAnalysisService,
    _closed_input_freshness,
    _daily_adjustment_mode,
    _summary,
)
from app.services.chanlun.store import ChanlunMinuteBarStore
from app.services.chanlun.symbols import ChanlunSymbolSearchService
from app.services.short_term_cache import TtlCache


SHANGHAI = ZoneInfo("Asia/Shanghai")


def shanghai(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=SHANGHAI)


def minute_bar(value: str, *, close: float = 10.0) -> TickFlowIntradayBar:
    timestamp = shanghai(value)
    return TickFlowIntradayBar(
        timestamp=int(timestamp.timestamp() * 1000),
        open=close - 0.1,
        high=close + 0.2,
        low=close - 0.2,
        close=close,
        volume=100.0,
        amount=1_000.0,
        prev_close=9.8,
    )


def minute_range(start: str, count: int) -> list[TickFlowIntradayBar]:
    first = shanghai(start)
    return [
        minute_bar((first + timedelta(minutes=index)).isoformat(), close=10.0 + index / 100)
        for index in range(count)
    ]


def trading_day_minutes(value: str) -> list[TickFlowIntradayBar]:
    day = datetime.fromisoformat(value).date()
    timestamps = [
        datetime.combine(day, time(9, 30), tzinfo=SHANGHAI) + timedelta(minutes=index)
        for index in range(120)
    ]
    timestamps.extend(
        datetime.combine(day, time(13), tzinfo=SHANGHAI) + timedelta(minutes=index)
        for index in range(120)
    )
    return [minute_bar(timestamp.isoformat()) for timestamp in timestamps]


def service_with_current_closed_bars(
    tmp_path: Path, current_day: datetime
) -> ChanlunAnalysisService:
    daily = [
        daily_bar(
            (current_day.date() - timedelta(days=24 - index)).isoformat(),
            close=10 + index / 100,
        )
        for index in range(25)
    ]
    minutes = [
        bar
        for offset in range(5, -1, -1)
        for bar in trading_day_minutes((current_day.date() - timedelta(days=offset)).isoformat())
    ]
    return ChanlunAnalysisService(
        store=store_at(tmp_path),
        intraday_provider=FakeQuoteProvider(minutes),
        history_provider=FakeHistoryProvider(),
        adapter=FakeAdapter(),
        daily_provider=FakeDailyProvider(daily),
        cache=build_test_cache(),
        cache_seconds=60,
    )


def store_at(tmp_path: Path) -> ChanlunMinuteBarStore:
    return ChanlunMinuteBarStore(tmp_path / "chanlun" / "minute.sqlite3")


def seed_closed_5m_history(store: ChanlunMinuteBarStore) -> None:
    store.upsert(
        "600000.SH",
        minute_range("2026-07-09 09:30", 100),
        source="seed",
        closed=True,
    )


def seed_closed_60m_history(store: ChanlunMinuteBarStore) -> None:
    for day in range(19):
        date = datetime(2026, 6, 1, 9, 30, tzinfo=SHANGHAI) + timedelta(days=day)
        store.upsert(
            "600000.SH",
            minute_range(date.isoformat(), 60),
            source="seed",
            closed=True,
        )


class FakeQuoteProvider:
    source_name = "Fake TickFlow"

    def __init__(
        self,
        bars: list[TickFlowIntradayBar] | None = None,
        *,
        payload: dict[str, list[TickFlowIntradayBar]] | None = None,
        fails: bool = False,
    ) -> None:
        self.bars = bars or []
        self.payload = payload
        self.fails = fails
        self.calls: list[tuple[list[str], str, int]] = []

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        self.calls.append((symbols, period, count))
        if self.fails:
            raise StrongStockDataUnavailable("live minute source failed")
        if self.payload is not None:
            return self.payload
        return {symbol: list(self.bars) for symbol in symbols}


class FakeHistoryProvider:
    source_name = "Fake minute history"

    def __init__(self, bars: list[TickFlowIntradayBar] | None = None) -> None:
        self.bars = bars or []
        self.calls: list[tuple[str, int]] = []

    def get_minute_bars(self, symbol: str, *, max_bars: int) -> list[TickFlowIntradayBar]:
        self.calls.append((symbol, max_bars))
        return list(self.bars)


class FakeDailyProvider:
    source_name = "Fake daily K"

    def __init__(self, bars: list[KlineBar]) -> None:
        self.bars = bars
        self.calls = 0

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        self.calls += 1
        return list(self.bars[-count:])


class FakeAdapter:
    source_name = "Fake CZSC"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, list[KlineBar], bool]] = []

    def analyze(
        self,
        symbol: str,
        *,
        period: str,
        bars: list[KlineBar],
        include_observing: bool = False,
    ) -> ChanlunAnalysisResponse:
        self.calls.append((symbol, period, list(bars), include_observing))
        return ChanlunAnalysisResponse(
            symbol=symbol,
            period=period,
            availability="ready",
            bars=list(bars),
            source_status=[
                StrongStockSourceStatus(source=self.source_name, status="success", detail="fake")
            ],
            last_closed_bar_at=bars[-1].date,
        )


def build_test_cache() -> TtlCache[ChanlunAnalysisResponse]:
    return TtlCache(ttl_seconds=600, name="chanlun-test")


def test_period_summary_exposes_the_latest_confirmed_signal() -> None:
    signal = ChanlunSignal(
        id="signal:two-buy",
        type="two_buy",
        occurred_at="2026-07-10T10:00:00+08:00",
        price=10.0,
        stroke_id="stroke:test",
        status="confirmed",
    )
    summary = _summary(
        ChanlunAnalysisResponse(
            symbol="600000.SH",
            period="5m",
            availability="ready",
            signals=[signal],
        )
    )

    assert summary.latest_signal == signal


def test_workspace_derives_confirmed_class_and_secondary_signals_from_multiperiod_context() -> None:
    def structure(
        period: str,
        *,
        direction: str,
        zone: ChanlunZone | None,
        signal: ChanlunSignal | None = None,
        last_stroke_direction: str | None = None,
    ) -> ChanlunAnalysisResponse:
        stroke = ChanlunStroke(
            id=f"stroke:{period}",
            start_at="2026-07-10T09:30:00+08:00",
            start_price=12.0,
            end_at="2026-07-10T10:00:00+08:00",
            end_price=13.0,
            direction=last_stroke_direction or direction,
            status="confirmed",
        )
        segment = stroke.model_copy(update={"direction": direction, "id": f"segment:{period}"})
        return ChanlunAnalysisResponse(
            symbol="600000.SH",
            period=period,  # type: ignore[arg-type]
            availability="ready",
            strokes=[stroke],
            segments=[segment],
            zones=[zone] if zone else [],
            signals=[signal] if signal else [],
        )

    daily_zone = ChanlunZone(
        id="zone:daily",
        start_at="2026-07-01T00:00:00+08:00",
        end_at="2026-07-09T00:00:00+08:00",
        high=10.0,
        low=8.0,
        status="confirmed",
    )
    sixty_zone = ChanlunZone(
        id="zone:60m",
        start_at="2026-07-10T09:30:00+08:00",
        end_at="2026-07-10T09:55:00+08:00",
        high=14.0,
        low=11.0,
        status="confirmed",
    )
    two_buy = ChanlunSignal(
        id="signal:two-buy",
        type="two_buy",
        occurred_at="2026-07-10T10:00:00+08:00",
        price=13.0,
        stroke_id="stroke:60m",
        status="confirmed",
    )
    three_buy = ChanlunSignal(
        id="signal:three-buy",
        type="three_buy",
        occurred_at="2026-07-10T10:00:00+08:00",
        price=15.0,
        stroke_id="stroke:30m",
        status="confirmed",
    )
    analyses = {
        "1d": structure("1d", direction="up", zone=daily_zone),
        "60m": structure(
            "60m",
            direction="up",
            zone=sixty_zone,
            signal=two_buy,
            last_stroke_direction="down",
        ),
        "30m": structure("30m", direction="up", zone=None, signal=three_buy),
        "5m": structure("5m", direction="up", zone=None),
    }
    service = object.__new__(ChanlunAnalysisService)
    service.analysis = lambda _symbol, *, period, lookback, include_observing: analyses[period]  # type: ignore[method-assign]

    workspace = service.workspace("600000.SH", lookback=220)

    assert {item.type for item in workspace.confluence_signals} == {
        "class_two_buy",
        "class_three_buy",
        "sub_two_buy",
        "sub_three_buy",
    }
    assert all(item.status == "confirmed" for item in workspace.confluence_signals)


def test_workspace_does_not_emit_confluence_when_any_period_is_not_ready() -> None:
    analyses = {
        period: ChanlunAnalysisResponse(
            symbol="600000.SH",
            period=period,  # type: ignore[arg-type]
            availability="stale" if period == "60m" else "ready",
        )
        for period in ("1d", "60m", "30m", "5m")
    }
    service = object.__new__(ChanlunAnalysisService)
    service.analysis = lambda _symbol, *, period, lookback, include_observing: analyses[period]  # type: ignore[method-assign]

    workspace = service.workspace("600000.SH", lookback=220)

    assert workspace.confluence_signals == []


def test_replay_uses_only_bar_prefixes_and_emits_each_confirmed_signal_once() -> None:
    start_at = datetime.fromisoformat("2026-06-01T00:00:00+08:00")
    bars = [
        KlineBar(
            date=(start_at + timedelta(days=index)).isoformat(timespec="seconds"),
            open=10.0,
            close=10.0 + index / 10,
            high=10.2 + index / 10,
            low=9.8 + index / 10,
            volume=100,
        )
        for index in range(24)
    ]

    class ReplayAdapter:
        calls: list[int] = []

        def analyze(self, symbol, *, period, bars, include_observing=False):
            self.calls.append(len(bars))
            signals = []
            if len(bars) >= 22:
                signals = [
                    ChanlunSignal(
                        id="signal:one-buy",
                        type="one_buy",
                        occurred_at=bars[-1].date,
                        price=bars[-1].close,
                        stroke_id="stroke:test",
                        status="confirmed",
                    )
                ]
            return ChanlunAnalysisResponse(
                symbol=symbol,
                period=period,
                availability="ready",
                bars=bars,
                signals=signals,
            )

    adapter = ReplayAdapter()
    base = ChanlunAnalysisResponse(
        symbol="600000.SH",
        period="1d",
        availability="ready",
        bars=bars,
        source_status=[
            StrongStockSourceStatus(source="fixture", status="success", detail="fixture")
        ],
    )
    service = object.__new__(ChanlunAnalysisService)
    service.adapter = adapter
    service.analysis = lambda _symbol, *, period, lookback, include_observing: base  # type: ignore[method-assign]

    assert hasattr(service, "replay")
    replay = service.replay("600000.SH", period="1d", lookback=24)

    assert adapter.calls == [20, 21, 22, 23, 24]
    assert len(replay.frames) == 1
    assert replay.frames[0].closed_at == bars[21].date
    assert [signal.id for signal in replay.frames[0].new_signals] == ["signal:one-buy"]


def test_backtest_enters_at_next_bar_open_and_uses_only_confirmed_replay_events() -> None:
    start_at = datetime.fromisoformat("2026-06-01T00:00:00+08:00")
    bars = [
        KlineBar(
            date=(start_at + timedelta(days=index)).isoformat(timespec="seconds"),
            open=10.0,
            close=10.0,
            high=10.2,
            low=9.8,
            volume=100,
        )
        for index in range(25)
    ]
    bars[22] = bars[22].model_copy(update={"open": 10.0, "close": 11.0, "high": 11.2, "low": 9.0})
    bars[23] = bars[23].model_copy(update={"open": 11.0, "close": 12.0, "high": 12.2, "low": 10.5})

    class BacktestAdapter:
        calls: list[int] = []

        def analyze(self, symbol, *, period, bars, include_observing=False):
            self.calls.append(len(bars))
            signals = []
            if len(bars) >= 22:
                signals = [
                    ChanlunSignal(
                        id="signal:one-buy",
                        type="one_buy",
                        occurred_at=bars[21].date,
                        price=bars[21].close,
                        stroke_id="stroke:test",
                        status="confirmed",
                    )
                ]
            return ChanlunAnalysisResponse(
                symbol=symbol,
                period=period,
                availability="ready",
                bars=bars,
                signals=signals,
            )

    adapter = BacktestAdapter()
    base = ChanlunAnalysisResponse(
        symbol="600000.SH",
        period="1d",
        availability="ready",
        bars=bars,
        source_status=[
            StrongStockSourceStatus(source="fixture", status="success", detail="fixture")
        ],
    )
    service = object.__new__(ChanlunAnalysisService)
    service.adapter = adapter
    service.analysis = lambda _symbol, *, period, lookback, include_observing: base  # type: ignore[method-assign]

    result = service.backtest("600000.SH", period="1d", lookback=25, horizons=[1, 2])

    assert adapter.calls == [20, 21, 22, 23, 24, 25]
    assert result.entry_rule == "next_bar_open"
    assert result.sample_count == 1
    assert result.buckets[0].signal_type == "one_buy"
    assert result.buckets[0].windows[0].avg_return_pct == 10.0
    assert result.buckets[0].windows[0].avg_max_drawdown_pct == -10.0
    assert result.buckets[0].windows[1].avg_return_pct == 20.0


def test_settings_update_evicts_chanlun_service_and_rebuilds_tickflow_providers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.main.get_settings", lambda: Settings(data_dir=tmp_path))
    monkeypatch.setattr(
        app.state, "runtime_config_path", tmp_path / "runtime_config.json", raising=False
    )
    for attribute in (
        "chanlun_analysis_service",
        "chanlun_minute_store",
        "chanlun_adapter",
        "chanlun_history_provider",
        "quote_provider",
        "kline_provider",
    ):
        monkeypatch.delattr(app.state, attribute, raising=False)

    update_runtime_settings(
        SettingsUpdate(
            candidate_provider="recent_limit_up",
            kline_provider="tickflow",
            quote_provider="tickflow",
            tickflow_api_key="old-key",
            tickflow_base_url="https://old.tickflow.test",
            provider_timeout_seconds=3,
        )
    )
    stale_service = _chanlun_analysis_service()

    update_runtime_settings(
        SettingsUpdate(
            candidate_provider="recent_limit_up",
            kline_provider="tickflow",
            quote_provider="tickflow",
            tickflow_api_key="new-key",
            tickflow_base_url="https://new.tickflow.test",
            provider_timeout_seconds=3,
        )
    )

    assert not hasattr(app.state, "chanlun_analysis_service")

    rebuilt_service = _chanlun_analysis_service()

    assert rebuilt_service is not stale_service
    assert isinstance(rebuilt_service.intraday_provider, TickFlowQuoteProvider)
    assert rebuilt_service.intraday_provider.base_url == "https://new.tickflow.test"
    assert isinstance(rebuilt_service.daily_provider, TickFlowDailyKlineProvider)
    assert rebuilt_service.daily_provider.base_url == "https://new.tickflow.test"


def test_default_chanlun_daily_provider_is_raw_without_changing_general_kline_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.main.get_settings", lambda: Settings(data_dir=tmp_path))
    for attribute in (
        "chanlun_analysis_service",
        "chanlun_minute_store",
        "chanlun_adapter",
        "chanlun_history_provider",
        "quote_provider",
        "kline_provider",
    ):
        monkeypatch.delattr(app.state, attribute, raising=False)

    general_provider = _kline_provider()
    chanlun_provider = _chanlun_analysis_service().daily_provider

    assert isinstance(general_provider, TickFlowDailyKlineProvider)
    assert isinstance(chanlun_provider, TickFlowDailyKlineProvider)
    assert general_provider.adjust == "forward"
    assert chanlun_provider.adjust == "none"
    assert _daily_adjustment_mode(chanlun_provider) == "raw_unadjusted"


def test_successful_daily_payload_is_stale_when_previous_day_is_missing_at_close(
    tmp_path: Path,
) -> None:
    service = ChanlunAnalysisService(
        store=store_at(tmp_path),
        intraday_provider=FakeQuoteProvider(),
        history_provider=FakeHistoryProvider(),
        adapter=FakeAdapter(),
        daily_provider=FakeDailyProvider(daily_bars(43)),
        cache=build_test_cache(),
    )

    period_data = service._load_closed_daily_period(
        "600000.SH",
        lookback=20,
        now=shanghai("2026-07-14 15:00"),
    )

    assert period_data.availability == "ready"
    assert period_data.bars[-1].date == "2026-07-13T15:00:00+08:00"
    assert period_data.freshness == "stale"


@pytest.mark.parametrize(
    ("period", "now", "current_minutes", "last_close"),
    [
        ("5m", "2026-07-14 10:02", 25, "2026-07-14T09:55:00+08:00"),
        ("30m", "2026-07-14 12:15", 90, "2026-07-14T11:00:00+08:00"),
        ("60m", "2026-07-14 14:30", 120, "2026-07-14T11:30:00+08:00"),
    ],
)
def test_successful_intraday_payload_is_stale_when_latest_session_bucket_is_missing(
    tmp_path: Path,
    period: str,
    now: str,
    current_minutes: int,
    last_close: str,
) -> None:
    history = [
        bar
        for day in (
            "2026-07-06",
            "2026-07-07",
            "2026-07-08",
            "2026-07-09",
            "2026-07-10",
            "2026-07-13",
        )
        for bar in trading_day_minutes(day)
    ]
    current = minute_range("2026-07-14 09:30", current_minutes)
    service = ChanlunAnalysisService(
        store=store_at(tmp_path),
        intraday_provider=FakeQuoteProvider([*history, *current]),
        history_provider=FakeHistoryProvider(),
        adapter=FakeAdapter(),
        cache=build_test_cache(),
    )

    period_data = service._load_closed_intraday_periods(
        "600000.SH",
        periods=(period,),
        lookback=20,
        now=shanghai(now),
    )[period]

    assert period_data.availability == "ready"
    assert period_data.bars[-1].date == last_close
    assert period_data.freshness == "stale"


@pytest.mark.parametrize("period", ["1d", "60m", "30m", "5m"])
def test_previous_open_session_bar_is_fresh_on_bundled_exchange_holiday(
    period: str,
) -> None:
    bars = (daily_bar("2026-02-13", close=10.0),)

    freshness = _closed_input_freshness(
        period,
        bars,
        shanghai("2026-02-17 15:00"),
    )

    assert freshness == "fresh"


@pytest.mark.parametrize(
    ("decision_at", "calendar_load_fails"),
    [
        (shanghai("2027-01-04 15:00"), False),
        (shanghai("2026-07-14 15:00"), True),
    ],
    ids=["after-coverage", "calendar-load-failure"],
)
def test_calendar_coverage_unavailable_fails_closed_with_source_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    decision_at: datetime,
    calendar_load_fails: bool,
) -> None:
    if calendar_load_fails:
        monkeypatch.setattr(
            chanlun_service_module,
            "_bundled_exchange_calendar",
            lambda: None,
        )
    service = service_with_current_closed_bars(tmp_path, decision_at)

    first = service.closed_workspace_inputs("600000.SH", lookback=20, now=decision_at)
    second = service.closed_workspace_inputs("600000.SH", lookback=20, now=decision_at)

    assert first is second
    assert set(first.availability.values()) == {"ready"}
    assert set(first.freshness.values()) == {"stale"}
    calendar_statuses = [
        status
        for period in ("1d", "60m", "30m", "5m")
        for status in first.source_status[period]
        if status.source == "CZSC内置交易日历"
    ]
    assert len(calendar_statuses) == 4
    assert {status.status for status in calendar_statuses} == {"failed"}
    assert all("覆盖不可用" in status.detail for status in calendar_statuses)
    assert all(
        "/" not in status.detail and "\\" not in status.detail and "Traceback" not in status.detail
        for status in calendar_statuses
    )


def test_service_uses_closed_store_bars_before_observing_tail(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    seed_closed_5m_history(store)
    store.upsert(
        "600000.SH",
        minute_range("2026-07-10 09:30", 30),
        source="seed",
        closed=True,
    )
    service = ChanlunAnalysisService(
        store=store,
        intraday_provider=FakeQuoteProvider(
            [minute_bar("2026-07-10 10:00"), minute_bar("2026-07-10 10:01")]
        ),
        history_provider=FakeHistoryProvider(),
        adapter=FakeAdapter(),
        cache=build_test_cache(),
    )

    result = service.analysis(
        "600000.SH",
        period="5m",
        lookback=120,
        include_observing=True,
        now=shanghai("2026-07-10 10:02"),
    )

    assert result.last_closed_bar_at == "2026-07-10T10:00:00+08:00"
    assert result.bars[-1].date == "2026-07-10T10:00:00+08:00"


def test_service_returns_insufficient_60m_bars_without_calling_adapter(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    store = store_at(tmp_path)
    seed_closed_60m_history(store)
    service = ChanlunAnalysisService(
        store=store,
        intraday_provider=FakeQuoteProvider([minute_bar("2026-07-10 10:30")]),
        history_provider=FakeHistoryProvider(),
        adapter=adapter,
        cache=build_test_cache(),
    )

    result = service.analysis(
        "600000.SH",
        period="60m",
        lookback=120,
        include_observing=False,
        now=shanghai("2026-07-10 10:30"),
    )

    assert result.availability == "insufficient_bars"
    assert adapter.calls == []


def test_backfill_writes_history_once_and_reports_progress(tmp_path: Path) -> None:
    progress: list[tuple[int, int, str]] = []
    history = FakeHistoryProvider([minute_bar("2026-07-09 09:30"), minute_bar("2026-07-09 09:31")])
    store = store_at(tmp_path)
    service = ChanlunAnalysisService(
        store=store,
        intraday_provider=FakeQuoteProvider(),
        history_provider=history,
        adapter=FakeAdapter(),
        cache=build_test_cache(),
    )

    result = service.backfill(
        "600000.SH",
        progress=lambda current, total, message: progress.append((current, total, message)),
        should_cancel=lambda: False,
    )

    assert result["written_bars"] == 2
    assert history.calls == [("600000.SH", 4800)]
    assert len(store.read("600000.SH")) == 2
    assert progress[-1][0] == progress[-1][1]


def test_analysis_cache_invalidates_when_last_closed_bar_changes(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    daily = FakeDailyProvider(daily_bars(20))
    service = ChanlunAnalysisService(
        store=store_at(tmp_path),
        intraday_provider=FakeQuoteProvider(),
        history_provider=FakeHistoryProvider(),
        adapter=adapter,
        daily_provider=daily,
        cache=build_test_cache(),
    )

    service.analysis(
        "600000.SH",
        period="1d",
        lookback=120,
        include_observing=False,
        now=shanghai("2026-07-20 16:00"),
    )
    service.analysis(
        "600000.SH",
        period="1d",
        lookback=120,
        include_observing=False,
        now=shanghai("2026-07-20 16:00"),
    )
    daily.bars.append(daily_bar("2026-07-21", close=31.0))
    service.analysis(
        "600000.SH",
        period="1d",
        lookback=120,
        include_observing=False,
        now=shanghai("2026-07-22 16:00"),
    )

    assert len(adapter.calls) == 2


def test_live_failure_is_stale_only_when_closed_history_can_still_be_analyzed(
    tmp_path: Path,
) -> None:
    adapter = FakeAdapter()
    store = store_at(tmp_path)
    seed_closed_5m_history(store)
    service = ChanlunAnalysisService(
        store=store,
        intraday_provider=FakeQuoteProvider(fails=True),
        history_provider=FakeHistoryProvider(),
        adapter=adapter,
        cache=build_test_cache(),
    )

    stale = service.analysis(
        "600000.SH",
        period="5m",
        lookback=120,
        include_observing=False,
        now=shanghai("2026-07-10 10:02"),
    )
    unavailable = ChanlunAnalysisService(
        store=store_at(tmp_path / "empty"),
        intraday_provider=FakeQuoteProvider(fails=True),
        history_provider=FakeHistoryProvider(),
        adapter=adapter,
        cache=build_test_cache(),
    ).analysis(
        "600000.SH",
        period="5m",
        lookback=120,
        include_observing=False,
        now=shanghai("2026-07-10 10:02"),
    )

    assert stale.availability == "stale"
    assert unavailable.availability == "unavailable"
    assert len(adapter.calls) == 1


def test_empty_live_intraday_payload_is_stale_with_closed_sqlite_history(tmp_path: Path) -> None:
    for index, (payload, detail) in enumerate(
        (({}, "响应缺少"), ({"600000.SH": []}, "分钟线为空"))
    ):
        store = store_at(tmp_path / str(index))
        seed_closed_5m_history(store)
        service = ChanlunAnalysisService(
            store=store,
            intraday_provider=FakeQuoteProvider(payload=payload),
            history_provider=FakeHistoryProvider(),
            adapter=FakeAdapter(),
            cache=build_test_cache(),
        )

        result = service.analysis(
            "600000.SH",
            period="5m",
            lookback=120,
            include_observing=False,
            now=shanghai("2026-07-10 10:02"),
        )

        assert result.availability == "stale"
        live_status = next(
            status for status in result.source_status if status.source == "Fake TickFlow"
        )
        assert live_status.status == "failed"
        assert detail in live_status.detail
        assert (
            next(
                status for status in result.source_status if status.source == "Chanlun SQLite分钟线"
            ).status
            == "stale"
        )


def test_empty_live_intraday_payload_is_unavailable_without_sqlite_history(tmp_path: Path) -> None:
    result = ChanlunAnalysisService(
        store=store_at(tmp_path),
        intraday_provider=FakeQuoteProvider(payload={}),
        history_provider=FakeHistoryProvider(),
        adapter=FakeAdapter(),
        cache=build_test_cache(),
    ).analysis(
        "600000.SH",
        period="5m",
        lookback=120,
        include_observing=False,
        now=shanghai("2026-07-10 10:02"),
    )

    assert result.availability == "unavailable"
    live_status = next(
        status for status in result.source_status if status.source == "Fake TickFlow"
    )
    assert live_status.status == "failed"
    assert "响应缺少" in live_status.detail
    assert (
        next(
            status for status in result.source_status if status.source == "Chanlun SQLite分钟线"
        ).status
        == "stale"
    )


def test_symbol_search_normalizes_local_results_and_fails_safely() -> None:
    def failing_loader() -> object:
        raise RuntimeError("akshare unavailable")

    service = ChanlunSymbolSearchService(
        loader=failing_loader,
        watchlist_loader=lambda: [{"symbol": "600000", "name": "浦发银行"}],
        latest_screen_loader=lambda: [{"symbol": "430047", "name": "诺思兰德"}],
    )

    matches, source_status = service.search("", limit=10)

    assert [item.symbol for item in matches] == ["600000.SH", "430047.BJ"]
    assert source_status[0].source == "Akshare 股票代码表"
    assert source_status[0].status == "failed"


def daily_bar(value: str, *, close: float) -> KlineBar:
    return KlineBar(
        date=f"{value}T15:00:00+08:00",
        open=close - 0.2,
        high=close + 0.3,
        low=close - 0.4,
        close=close,
        volume=1_000.0,
        amount=10_000.0,
    )


def daily_bars(count: int) -> list[KlineBar]:
    start = datetime(2026, 6, 1, tzinfo=SHANGHAI)
    return [
        daily_bar((start + timedelta(days=index)).date().isoformat(), close=10 + index)
        for index in range(count)
    ]
