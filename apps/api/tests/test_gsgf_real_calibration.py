from datetime import datetime, timedelta

from app.models import GsgfAnalysis, KlineBar, StrongStockCandidate
from app.services.gsgf_real_calibration import summarize_gsgf_real_calibration


class FakeCandidateProvider:
    source_name = "fake候选池"

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        assert trade_date == "2026-06-12"
        return [
            StrongStockCandidate(symbol="603890.SH", name="确认样本", industry="消费电子"),
            StrongStockCandidate(symbol="002000.SZ", name="低吸样本", industry="化学制品"),
        ]


class FakeKlineProvider:
    source_name = "fake日K"

    def get_klines(self, symbol: str, count: int = 260) -> list[KlineBar]:
        entry_close = 10 if symbol == "603890.SH" else 20
        future = [11, 10.5, 11.2, 11.6] if symbol == "603890.SH" else [19, 19.4, 19.2, 18.8]
        return _bars(entry_close=entry_close, future_closes=future)


def test_summarize_gsgf_real_calibration_truncates_history_and_groups_target_buckets() -> None:
    latest_dates_seen: list[str] = []

    def analyzer(bars: list[KlineBar]) -> GsgfAnalysis:
        latest_dates_seen.append(bars[-1].date)
        if bars[-1].close == 10:
            return GsgfAnalysis(
                total_score=88,
                final_status="确认买点",
                setup_type="B区A点",
                confirm_type="放量突破确认",
            )
        return GsgfAnalysis(
            total_score=70,
            final_status="低吸观察",
            zone="b_zone_a_point",
            setup_type="双星止跌",
        )

    summary = summarize_gsgf_real_calibration(
        candidate_provider=FakeCandidateProvider(),
        kline_provider=FakeKlineProvider(),
        trade_dates=["2026-06-12"],
        windows=[1, 3],
        scan_limit=10,
        analyzer=analyzer,
    )

    assert latest_dates_seen == ["20260612", "20260612"]
    assert summary.trade_dates == ["2026-06-12"]
    assert summary.scanned_count == 2
    assert summary.target_sample_count == 2
    assert summary.source_status[1].status == "success"
    assert len(summary.samples) == 2
    assert summary.samples[0].symbol == "603890.SH"
    assert summary.samples[0].bucket_names == ["确认买点", "放量突破确认"]
    assert summary.samples[0].windows[0].realized_return_pct == 10
    assert summary.samples[0].windows[1].max_drawdown_pct == 2.9

    buckets = {bucket.name: bucket for bucket in summary.buckets}
    assert buckets["确认买点"].sample_count == 1
    assert buckets["确认买点"].windows[0].hit_rate == 100
    assert buckets["确认买点"].windows[0].avg_return_pct == 10
    assert buckets["低吸观察"].sample_count == 1
    assert buckets["低吸观察"].windows[0].hit_rate == 0
    assert buckets["B区A点"].sample_count == 1
    assert buckets["放量突破确认"].sample_count == 1
    assert buckets["放量突破确认"].examples[0].symbol == "603890.SH"


def test_summarize_gsgf_real_calibration_reuses_kline_fetches_across_dates() -> None:
    class RepeatedCandidateProvider:
        source_name = "fake重复候选池"

        def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
            return [StrongStockCandidate(symbol="603890.SH", name=f"重复{trade_date}")]

    class CountingKlineProvider(FakeKlineProvider):
        def __init__(self) -> None:
            self.calls = 0

        def get_klines(self, symbol: str, count: int = 260) -> list[KlineBar]:
            self.calls += 1
            return _bars(entry_close=10, future_closes=[11, 12, 13, 14])

    kline_provider = CountingKlineProvider()

    summary = summarize_gsgf_real_calibration(
        candidate_provider=RepeatedCandidateProvider(),
        kline_provider=kline_provider,
        trade_dates=["2026-06-12", "2026-06-13"],
        windows=[1],
        analyzer=lambda bars: GsgfAnalysis(
            total_score=90,
            final_status="确认买点",
            confirm_type="放量突破确认",
        ),
    )

    assert kline_provider.calls == 1
    assert summary.scanned_count == 2
    assert summary.target_sample_count == 2
    assert summary.unique_symbol_buckets[0].name == "确认买点"
    assert summary.unique_symbol_buckets[0].sample_count == 1


def test_summarize_gsgf_real_calibration_treats_b_zone_a_point_as_zone_bucket() -> None:
    summary = summarize_gsgf_real_calibration(
        candidate_provider=FakeCandidateProvider(),
        kline_provider=FakeKlineProvider(),
        trade_dates=["2026-06-12"],
        windows=[1],
        scan_limit=1,
        analyzer=lambda bars: GsgfAnalysis(
            total_score=64,
            final_status="观察",
            zone="b_zone_a_point",
        ),
    )

    assert summary.target_sample_count == 1
    assert summary.buckets[0].name == "B区A点"
    assert summary.buckets[0].sample_count == 1


def test_summarize_gsgf_real_calibration_reports_success_when_some_candidates_skip() -> None:
    class OneMissingKlineProvider(FakeKlineProvider):
        def get_klines(self, symbol: str, count: int = 260) -> list[KlineBar]:
            if symbol == "002000.SZ":
                return []
            return super().get_klines(symbol, count=count)

    summary = summarize_gsgf_real_calibration(
        candidate_provider=FakeCandidateProvider(),
        kline_provider=OneMissingKlineProvider(),
        trade_dates=["2026-06-12"],
        windows=[1],
        analyzer=lambda bars: GsgfAnalysis(
            total_score=90,
            final_status="确认买点",
            confirm_type="放量突破确认",
        ),
    )

    assert summary.target_sample_count == 1
    assert summary.skipped_count == 1
    assert summary.source_status[1].status == "success"


def test_summarize_gsgf_real_calibration_emits_progress_events() -> None:
    events: list[str] = []

    summarize_gsgf_real_calibration(
        candidate_provider=FakeCandidateProvider(),
        kline_provider=FakeKlineProvider(),
        trade_dates=["2026-06-12"],
        windows=[1],
        progress=events.append,
        analyzer=lambda bars: GsgfAnalysis(
            total_score=90,
            final_status="确认买点",
            confirm_type="放量突破确认",
        ),
    )

    assert events[0] == "2026-06-12: loaded 2 candidates"
    assert events[-1] == "completed: scanned 2 candidates, target samples 2, skipped 0"


def _bars(entry_close: float, future_closes: list[float]) -> list[KlineBar]:
    start = datetime(2026, 4, 8)
    closes = [entry_close for _ in range(66)] + future_closes
    bars: list[KlineBar] = []
    for index, close in enumerate(closes):
        date = (start + timedelta(days=index)).strftime("%Y%m%d")
        bars.append(
            KlineBar(
                date=date,
                open=close,
                close=close,
                high=close * 1.02,
                low=close * 0.98,
                volume=1_000_000 + index,
            )
        )
    assert bars[65].date == "20260612"
    return bars
