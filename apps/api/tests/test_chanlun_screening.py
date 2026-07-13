from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.models import (
    ChanlunAnalysisResponse,
    ChanlunConfluenceSignal,
    ChanlunDivergence,
    ChanlunPeriodSummary,
    ChanlunSignal,
    ChanlunStroke,
    KlineBar,
    ChanlunWorkspaceResponse,
)
from app.services.chanlun.screening import (
    CachedChanlunScreeningSummarizer,
    build_chanlun_screening_summary,
    passes_chanlun_screening_filters,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")


def _signal(period: str, signal_type: str, occurred_at: str) -> ChanlunSignal:
    return ChanlunSignal(
        id=f"signal:{period}:{signal_type}",
        type=signal_type,  # type: ignore[arg-type]
        occurred_at=occurred_at,
        price=10,
        stroke_id=f"stroke:{period}",
        status="confirmed",
    )


def _period(
    period: str,
    *,
    direction: str = "up",
    signal_type: str | None = None,
    occurred_at: str = "2026-07-10T14:55:00+08:00",
    availability: str = "ready",
) -> ChanlunPeriodSummary:
    return ChanlunPeriodSummary(
        period=period,  # type: ignore[arg-type]
        availability=availability,  # type: ignore[arg-type]
        direction=direction,  # type: ignore[arg-type]
        latest_signal=_signal(period, signal_type, occurred_at) if signal_type else None,
        last_closed_bar_at="2026-07-10T15:00:00+08:00",
    )


def _workspace(periods: list[ChanlunPeriodSummary]) -> ChanlunWorkspaceResponse:
    return ChanlunWorkspaceResponse(
        symbol="600000.SH",
        periods=periods,
        analysis=ChanlunAnalysisResponse(
            symbol="600000.SH",
            period="1d",
            availability="ready",
        ),
        confluence_signals=[
            ChanlunConfluenceSignal(
                id="confluence:buy",
                type="class_two_buy",
                higher_period="60m",
                lower_period="5m",
                occurred_at="2026-07-10T14:55:00+08:00",
                price=10,
                status="confirmed",
                reason="60分钟与5分钟买类结构共振",
            )
        ],
    )


def test_screening_summary_scores_confirmed_four_period_buy_confluence() -> None:
    workspace = _workspace(
        [
            _period("1d", signal_type="one_buy"),
            _period("60m", signal_type="two_buy"),
            _period("30m", signal_type="two_buy"),
            _period("5m", signal_type="three_buy"),
        ]
    )

    summary = build_chanlun_screening_summary(
        workspace,
        now=datetime(2026, 7, 10, 15, 5, tzinfo=SHANGHAI),
    )

    assert summary.availability == "ready"
    assert summary.freshness == "fresh"
    assert summary.confluence_score == 100
    assert summary.bullish_periods == 4
    assert summary.has_confirmed_buy is True
    assert summary.has_confirmed_sell is False
    assert summary.latest_confirmed_at == "2026-07-10T14:55:00+08:00"
    assert summary.periods[-1].signal_age_seconds == 600


def test_screening_summary_keeps_incomplete_periods_explicit() -> None:
    workspace = _workspace(
        [
            _period("1d", signal_type="one_buy"),
            _period("60m", availability="insufficient_bars"),
            _period("30m", availability="unavailable"),
            _period("5m", availability="insufficient_bars"),
        ]
    )

    summary = build_chanlun_screening_summary(
        workspace,
        now=datetime(2026, 7, 10, 15, 5, tzinfo=SHANGHAI),
    )

    assert summary.availability == "partial"
    assert summary.freshness == "insufficient"
    assert summary.confluence_score == 15


def test_chanlun_filters_only_reject_fully_computed_summaries() -> None:
    ready = build_chanlun_screening_summary(
        _workspace([_period(period) for period in ("1d", "60m", "30m", "5m")]),
        now=datetime(2026, 7, 10, 15, 5, tzinfo=SHANGHAI),
    )
    partial = ready.model_copy(update={"availability": "partial", "confluence_score": 0})
    stale = ready.model_copy(update={"freshness": "stale", "confluence_score": 0})

    assert passes_chanlun_screening_filters(
        ready,
        min_confluence_score=50,
        require_confirmed_buy=True,
    ) is False
    assert passes_chanlun_screening_filters(
        partial,
        min_confluence_score=50,
        require_confirmed_buy=True,
    ) is True
    assert passes_chanlun_screening_filters(
        stale,
        min_confluence_score=50,
        require_confirmed_buy=True,
    ) is True
    assert passes_chanlun_screening_filters(
        None,
        min_confluence_score=50,
        require_confirmed_buy=True,
    ) is True


def test_screening_summary_includes_latest_confirmed_divergence_time() -> None:
    period = _period("1d", signal_type="one_buy")
    period.latest_divergence = ChanlunDivergence(
        id="divergence:1d:bottom",
        type="bottom",
        occurred_at="2026-07-10T14:58:00+08:00",
        reference_occurred_at="2026-07-10T13:30:00+08:00",
        direction="down",
        reference_stroke_id="stroke:reference",
        current_stroke_id="stroke:current",
        reference_price=10,
        current_price=9.8,
        reference_macd_strength=100,
        current_macd_strength=70,
        coefficient=0.7,
        zone_count=2,
        status="confirmed",
    )

    summary = build_chanlun_screening_summary(
        _workspace([period]),
        now=datetime(2026, 7, 10, 15, 5, tzinfo=SHANGHAI),
    )

    assert summary.periods[0].latest_divergence_type == "bottom"
    assert summary.periods[0].latest_divergence_at == "2026-07-10T14:58:00+08:00"
    assert summary.latest_confirmed_at == "2026-07-10T14:58:00+08:00"


def test_cached_summarizer_uses_existing_daily_bars_and_local_minutes_without_future_bars() -> None:
    store = RecordingMinuteStore(_minute_rows())
    adapter = RecordingAdapter()
    summarizer = CachedChanlunScreeningSummarizer(
        store=store,
        adapter=adapter,
        now_provider=lambda: datetime(2026, 7, 13, 10, 0, tzinfo=SHANGHAI),
    )
    daily_bars = [
        KlineBar(date="2026-07-09", open=10, high=11, low=9, close=10.5, volume=1000),
        KlineBar(date="2026-07-10", open=10.5, high=12, low=10, close=11.5, volume=1200),
        KlineBar(date="2026-07-13", open=11.5, high=12, low=11, close=11.8, volume=800),
    ]

    summary = summarizer.summarize(
        "600000.SH",
        daily_bars=daily_bars,
        trade_date="2026-07-10",
    )
    repeated = summarizer.summarize(
        "600000.SH",
        daily_bars=daily_bars,
        trade_date="2026-07-10",
    )

    assert summary.availability == "ready"
    assert repeated == summary
    assert store.calls == [
        ("600000.SH", "2026-07-10T15:00:00+08:00"),
        ("600000.SH", "2026-07-10T15:00:00+08:00"),
    ]
    assert adapter.call_count == 4
    assert [bar.date for bar in adapter.bars_by_period["1d"]] == ["2026-07-09", "2026-07-10"]
    assert all(
        datetime.fromisoformat(bar.date) <= datetime(2026, 7, 10, 15, 0, tzinfo=SHANGHAI)
        for period in ("60m", "30m", "5m")
        for bar in adapter.bars_by_period[period]
    )


def test_cached_summarizer_marks_previous_session_minutes_stale_during_trading() -> None:
    summarizer = CachedChanlunScreeningSummarizer(
        store=RecordingMinuteStore(_minute_rows()),
        adapter=RecordingAdapter(),
        now_provider=lambda: datetime(2026, 7, 13, 10, 0, tzinfo=SHANGHAI),
    )

    summary = summarizer.summarize(
        "600000.SH",
        daily_bars=[
            KlineBar(date="2026-07-10", open=10, high=11, low=9, close=10.5, volume=1000),
        ],
        trade_date="2026-07-13",
    )

    assert summary.availability == "ready"
    assert summary.freshness == "stale"
    assert [item.availability for item in summary.periods] == ["ready", "stale", "stale", "stale"]


class RecordingMinuteStore:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, str | None]] = []

    def read(self, symbol: str, *, end_at: str | None = None) -> list[SimpleNamespace]:
        self.calls.append((symbol, end_at))
        return self.rows


class RecordingAdapter:
    def __init__(self) -> None:
        self.bars_by_period: dict[str, list[KlineBar]] = {}
        self.call_count = 0

    def analyze(
        self,
        symbol: str,
        *,
        period: str,
        bars: list[KlineBar],
        include_observing: bool = False,
    ) -> ChanlunAnalysisResponse:
        self.call_count += 1
        self.bars_by_period[period] = bars
        direction = "up" if period in {"1d", "60m"} else "down"
        return ChanlunAnalysisResponse(
            symbol=symbol,
            period=period,  # type: ignore[arg-type]
            availability="ready",
            bars=bars,
            strokes=[
                ChanlunStroke(
                    id=f"stroke:{period}",
                    start_at=bars[0].date if bars else "2026-07-10T09:30:00+08:00",
                    start_price=10,
                    end_at=bars[-1].date if bars else "2026-07-10T15:00:00+08:00",
                    end_price=11,
                    direction=direction,  # type: ignore[arg-type]
                    status="confirmed",
                )
            ],
            last_closed_bar_at=bars[-1].date if bars else None,
        )


def _minute_rows() -> list[SimpleNamespace]:
    start = datetime(2026, 7, 10, 9, 30, tzinfo=SHANGHAI)
    rows: list[SimpleNamespace] = []
    for offset in range(60):
        timestamp = start + timedelta(minutes=offset)
        rows.append(
            SimpleNamespace(
                timestamp=timestamp.isoformat(timespec="seconds"),
                open=10,
                high=11,
                low=9,
                close=10.5,
                volume=100,
                amount=1000,
                prev_close=10,
                closed=True,
            )
        )
    return rows
