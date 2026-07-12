from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.models import ChanlunAnalysisResponse, KlineBar, StrongStockDataUnavailable, StrongStockSourceStatus
from app.providers.tickflow import TickFlowIntradayBar
from app.services.chanlun.service import ChanlunAnalysisService
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

    def __init__(self, bars: list[TickFlowIntradayBar] | None = None, *, fails: bool = False) -> None:
        self.bars = bars or []
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
        intraday_provider=FakeQuoteProvider(),
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
    history = FakeHistoryProvider(
        [minute_bar("2026-07-09 09:30"), minute_bar("2026-07-09 09:31")]
    )
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


def test_live_failure_is_stale_only_when_closed_history_can_still_be_analyzed(tmp_path: Path) -> None:
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
    return [daily_bar((start + timedelta(days=index)).date().isoformat(), close=10 + index) for index in range(count)]
