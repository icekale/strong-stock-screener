from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Callable, Protocol

from app.gsgf_rules import analyze_gsgf
from app.models import (
    GsgfAnalysis,
    GsgfCalibrationBucket,
    GsgfCalibrationExample,
    GsgfCalibrationSample,
    GsgfCalibrationSampleWindow,
    GsgfCalibrationWindowStat,
    GsgfRealCalibrationSummary,
    KlineBar,
    StrongStockCandidate,
    StrongStockDataUnavailable,
    StrongStockSourceStatus,
)
from app.services.gsgf_backtest import DEFAULT_BACKTEST_WINDOWS

TARGET_BUCKETS = ["确认买点", "低吸观察", "B区A点", "放量突破确认"]


class CandidateProvider(Protocol):
    source_name: str

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        ...


class KlineProvider(Protocol):
    source_name: str

    def get_klines(self, symbol: str, count: int = 260) -> list[KlineBar]:
        ...


Analyzer = Callable[[list[KlineBar]], GsgfAnalysis]
ProgressReporter = Callable[[str], None]


def summarize_gsgf_real_calibration(
    *,
    candidate_provider: CandidateProvider,
    kline_provider: KlineProvider,
    trade_dates: list[str],
    windows: list[int] | None = None,
    scan_limit: int = 80,
    kline_count: int = 260,
    analyzer: Analyzer = analyze_gsgf,
    progress: ProgressReporter | None = None,
) -> GsgfRealCalibrationSummary:
    clean_windows = _clean_windows(windows)
    samples: list[_CalibrationSample] = []
    scanned_count = 0
    skipped_count = 0
    source_status: list[StrongStockSourceStatus] = []
    bars_cache: dict[str, list[KlineBar]] = {}

    for trade_date in _dedupe_dates(trade_dates):
        try:
            candidates = candidate_provider.get_candidates(trade_date)
        except StrongStockDataUnavailable as exc:
            source_status.append(
                StrongStockSourceStatus(
                    source=candidate_provider.source_name,
                    status="failed",
                    detail=f"{trade_date}: {exc}",
                )
            )
            continue
        _report(progress, f"{trade_date}: loaded {len(candidates[:scan_limit])} candidates")
        for candidate in candidates[:scan_limit]:
            scanned_count += 1
            if scanned_count == 1 or scanned_count % 25 == 0:
                _report(progress, f"scanned {scanned_count} candidates, target samples {len(samples)}")
            try:
                bars = bars_cache.get(candidate.symbol)
                if bars is None:
                    bars = sorted(
                        kline_provider.get_klines(candidate.symbol, count=kline_count),
                        key=lambda bar: bar.date,
                    )
                    bars_cache[candidate.symbol] = bars
            except Exception:
                skipped_count += 1
                continue
            sample = _sample_from_bars(
                trade_date=trade_date,
                candidate=candidate,
                bars=bars,
                windows=clean_windows,
                analyzer=analyzer,
            )
            if sample is None:
                skipped_count += 1
                continue
            samples.append(sample)

    target_sample_count = sum(1 for sample in samples if sample.bucket_names)
    _report(progress, f"completed: scanned {scanned_count} candidates, target samples {target_sample_count}, skipped {skipped_count}")
    return GsgfRealCalibrationSummary(
        trade_dates=_dedupe_dates(trade_dates),
        windows=clean_windows,
        scanned_count=scanned_count,
        target_sample_count=target_sample_count,
        skipped_count=skipped_count,
        buckets=_build_buckets(samples, clean_windows),
        unique_symbol_buckets=_build_buckets(_unique_symbol_samples(samples), clean_windows),
        samples=[_sample_payload(sample, clean_windows) for sample in samples if sample.bucket_names],
        source_status=[
            StrongStockSourceStatus(
                source=getattr(candidate_provider, "source_name", "候选池"),
                status="success",
                detail=f"样本日 {len(_dedupe_dates(trade_dates))} 个，本次扫描 {scanned_count} 条候选",
            ),
            StrongStockSourceStatus(
                source=getattr(kline_provider, "source_name", "K线源"),
                status="success" if target_sample_count > 0 else "failed",
                detail=f"有效目标样本 {target_sample_count} 个，跳过 {skipped_count} 个",
            ),
            *source_status,
        ],
    )


def _sample_from_bars(
    *,
    trade_date: str,
    candidate: StrongStockCandidate,
    bars: list[KlineBar],
    windows: list[int],
    analyzer: Analyzer,
) -> _CalibrationSample | None:
    normalized_date = _normalize_date(trade_date)
    signal_index = next((index for index, bar in enumerate(bars) if bar.date == normalized_date), None)
    if signal_index is None or signal_index < 59:
        return None

    max_window = max(windows) if windows else DEFAULT_BACKTEST_WINDOWS[-1]
    future_bars = bars[signal_index + 1 : signal_index + max_window + 1]
    if len(future_bars) < min(windows):
        return None

    history = bars[: signal_index + 1]
    analysis = analyzer(history)
    bucket_names = _target_bucket_names(analysis)
    current = bars[signal_index]
    return _CalibrationSample(
        trade_date=trade_date,
        symbol=candidate.symbol,
        name=candidate.name,
        analysis=analysis,
        entry_close=current.close if current.close > 0 else None,
        future_bars=future_bars,
        bucket_names=bucket_names,
    )


class _CalibrationSample:
    def __init__(
        self,
        *,
        trade_date: str,
        symbol: str,
        name: str,
        analysis: GsgfAnalysis,
        entry_close: float | None,
        future_bars: list[KlineBar],
        bucket_names: list[str],
    ) -> None:
        self.trade_date = trade_date
        self.symbol = symbol
        self.name = name
        self.analysis = analysis
        self.entry_close = entry_close
        self.future_bars = future_bars
        self.bucket_names = bucket_names


def _target_bucket_names(analysis: GsgfAnalysis) -> list[str]:
    names: list[str] = []
    if analysis.final_status in {"确认买点", "低吸观察"}:
        names.append(analysis.final_status)
    if analysis.zone == "b_zone_a_point":
        names.append("B区A点")
    if analysis.confirm_type == "放量突破确认":
        names.append("放量突破确认")
    return _dedupe(names)


def _build_buckets(samples: list[_CalibrationSample], windows: list[int]) -> list[GsgfCalibrationBucket]:
    grouped: dict[str, list[_CalibrationSample]] = defaultdict(list)
    for sample in samples:
        for bucket_name in sample.bucket_names:
            grouped[bucket_name].append(sample)

    return [
        GsgfCalibrationBucket(
            name=bucket_name,
            sample_count=len(grouped.get(bucket_name, [])),
            windows=[_window_stat(grouped.get(bucket_name, []), window) for window in windows],
            examples=[_example(sample) for sample in grouped.get(bucket_name, [])[:5]],
        )
        for bucket_name in TARGET_BUCKETS
        if grouped.get(bucket_name)
    ]


def _unique_symbol_samples(samples: list[_CalibrationSample]) -> list[_CalibrationSample]:
    by_bucket_symbol: dict[tuple[str, str], _CalibrationSample] = {}
    for sample in samples:
        for bucket_name in sample.bucket_names:
            key = (bucket_name, sample.symbol)
            existing = by_bucket_symbol.get(key)
            if existing is None or sample.trade_date < existing.trade_date:
                by_bucket_symbol[key] = sample
    output: list[_CalibrationSample] = []
    seen_ids: set[int] = set()
    for sample in sorted(by_bucket_symbol.values(), key=lambda item: (item.trade_date, item.symbol)):
        identity = id(sample)
        if identity in seen_ids:
            continue
        seen_ids.add(identity)
        output.append(sample)
    return output


def _window_stat(samples: list[_CalibrationSample], window: int) -> GsgfCalibrationWindowStat:
    returns: list[float] = []
    drawdowns: list[float] = []
    for sample in samples:
        sample_window = _sample_window(sample, window)
        if sample_window.realized_return_pct is None:
            continue
        returns.append(sample_window.realized_return_pct)
        if sample_window.max_drawdown_pct is not None:
            drawdowns.append(sample_window.max_drawdown_pct)
    hit_count = sum(1 for value in returns if value > 0)
    return GsgfCalibrationWindowStat(
        window_days=window,
        sample_count=len(returns),
        hit_count=hit_count,
        hit_rate=round(hit_count / len(returns) * 100, 2) if returns else None,
        avg_return_pct=_round_or_none(returns),
        avg_max_drawdown_pct=_round_or_none(drawdowns),
    )


def _example(sample: _CalibrationSample) -> GsgfCalibrationExample:
    return GsgfCalibrationExample(
        trade_date=sample.trade_date,
        symbol=sample.symbol,
        name=sample.name,
        status=sample.analysis.final_status,
        score=sample.analysis.total_score,
        setup_type=sample.analysis.setup_type,
        confirm_type=sample.analysis.confirm_type,
        entry_close=sample.entry_close,
    )


def _sample_payload(sample: _CalibrationSample, windows: list[int]) -> GsgfCalibrationSample:
    return GsgfCalibrationSample(
        trade_date=sample.trade_date,
        symbol=sample.symbol,
        name=sample.name,
        status=sample.analysis.final_status,
        score=sample.analysis.total_score,
        setup_type=sample.analysis.setup_type,
        confirm_type=sample.analysis.confirm_type,
        zone=sample.analysis.zone,
        bucket_names=sample.bucket_names,
        entry_close=sample.entry_close,
        windows=[_sample_window(sample, window) for window in windows],
    )


def _sample_window(sample: _CalibrationSample, window: int) -> GsgfCalibrationSampleWindow:
    if sample.entry_close is None or sample.entry_close <= 0 or len(sample.future_bars) < window:
        return GsgfCalibrationSampleWindow(window_days=window)
    scoped = sample.future_bars[:window]
    return GsgfCalibrationSampleWindow(
        window_days=window,
        realized_return_pct=round((scoped[-1].close / sample.entry_close - 1) * 100, 2),
        max_drawdown_pct=round((min(bar.low for bar in scoped) / sample.entry_close - 1) * 100, 2),
    )


def _clean_windows(windows: list[int] | None) -> list[int]:
    values = windows or DEFAULT_BACKTEST_WINDOWS
    output: list[int] = []
    seen: set[int] = set()
    for value in values:
        normalized = max(1, min(int(value), 60))
        if normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output or DEFAULT_BACKTEST_WINDOWS


def _dedupe_dates(values: list[str]) -> list[str]:
    return _dedupe([value.strip() for value in values if value.strip()])


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _normalize_date(value: str) -> str:
    return value.replace("-", "").strip()


def _round_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return round(mean(values), 2)


def _report(progress: ProgressReporter | None, message: str) -> None:
    if progress is not None:
        progress(message)
