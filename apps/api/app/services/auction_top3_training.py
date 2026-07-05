from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.models import (
    AuctionModelTop3Response,
    AuctionTop3EntryPolicy,
    AuctionTop3ExitPolicy,
    AuctionTop3ManualTradeSample,
    AuctionTop3PerformanceResponse,
    AuctionTop3SignalSample,
    AuctionTop3SimulatedPerformancePoint,
    AuctionTop3SimulatedTradeSample,
    AuctionTop3TrainingSummary,
    KlineBar,
)

T = TypeVar("T", bound=BaseModel)


class AuctionTop3TrainingStore:
    def __init__(self, data_dir: Path) -> None:
        self.root_dir = data_dir / "auction_top3_training"
        self.signal_dir = self.root_dir / "signals"
        self.simulated_dir = self.root_dir / "simulated_trades"
        self.manual_dir = self.root_dir / "manual_trades"
        self.performance_path = self.root_dir / "performance.json"

    def upsert_signal_samples(self, samples: list[AuctionTop3SignalSample]) -> list[AuctionTop3SignalSample]:
        existing = {_signal_key(sample): sample for sample in self.load_signal_samples()}
        for sample in samples:
            existing[_signal_key(sample)] = sample
        self._write_jsonl_grouped(self.signal_dir, existing.values(), lambda item: item.trade_date)
        return samples

    def load_signal_samples(self, trade_date: str | None = None) -> list[AuctionTop3SignalSample]:
        return _read_jsonl_models(self.signal_dir, AuctionTop3SignalSample, trade_date)

    def upsert_simulated_trades(
        self,
        trades: list[AuctionTop3SimulatedTradeSample],
    ) -> list[AuctionTop3SimulatedTradeSample]:
        existing = {_simulated_key(sample): sample for sample in self.load_simulated_trades()}
        for trade in trades:
            existing[_simulated_key(trade)] = trade
        self._write_jsonl_grouped(self.simulated_dir, existing.values(), lambda item: item.trade_date)
        return trades

    def load_simulated_trades(self, trade_date: str | None = None) -> list[AuctionTop3SimulatedTradeSample]:
        return _read_jsonl_models(self.simulated_dir, AuctionTop3SimulatedTradeSample, trade_date)

    def upsert_manual_trade(self, sample: AuctionTop3ManualTradeSample) -> AuctionTop3ManualTradeSample:
        existing = {item.sample_id: item for item in self.load_manual_trades()}
        existing[sample.sample_id] = sample
        self._write_jsonl_grouped(self.manual_dir, existing.values(), lambda item: item.trade_date)
        return sample

    def load_manual_trades(self, trade_date: str | None = None) -> list[AuctionTop3ManualTradeSample]:
        return _read_jsonl_models(self.manual_dir, AuctionTop3ManualTradeSample, trade_date)

    def save_performance_points(self, points: list[AuctionTop3SimulatedPerformancePoint]) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        payload = AuctionTop3PerformanceResponse(points=points).model_dump_json(indent=2)
        self.performance_path.write_text(payload, encoding="utf-8")

    def load_performance(self) -> AuctionTop3PerformanceResponse:
        if not self.performance_path.exists():
            return AuctionTop3PerformanceResponse()
        return AuctionTop3PerformanceResponse.model_validate_json(self.performance_path.read_text(encoding="utf-8"))

    def training_summary(
        self,
        *,
        training_window_days: int,
        include_manual_training: bool,
        enabled: bool = True,
        initial_capital: float = 100000,
        portfolio_id: str = "default",
    ) -> AuctionTop3TrainingSummary:
        signals = self.load_signal_samples()
        simulated = self.load_simulated_trades()
        manual = [
            item
            for item in self.load_manual_trades()
            if include_manual_training and item.enabled_for_training
        ]
        performance = summarize_simulated_performance(
            simulated,
            initial_capital=initial_capital,
            portfolio_id=portfolio_id,
        )
        dates = sorted({sample.trade_date for sample in signals})
        return AuctionTop3TrainingSummary(
            enabled=enabled,
            signal_sample_count=len(signals),
            simulated_trade_sample_count=len(simulated),
            manual_trade_sample_count=len(manual),
            date_range=[dates[0], dates[-1]] if dates else [],
            training_window_days=training_window_days,
            latest_generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            simulated_profit_summary=performance.summary,
            quality_notes=[] if signals else ["暂无竞价 Top3 信号样本"],
        )

    def _write_jsonl_grouped(
        self,
        directory: Path,
        items: object,
        date_getter: object,
    ) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        grouped: dict[str, list[BaseModel]] = defaultdict(list)
        for item in items:
            grouped[date_getter(item)].append(item)
        for trade_date, rows in grouped.items():
            path = directory / f"{trade_date}.jsonl"
            ordered = sorted(rows, key=_model_sort_key)
            path.write_text(
                "".join(row.model_dump_json() + "\n" for row in ordered),
                encoding="utf-8",
            )


def build_signal_samples_from_top3(result: AuctionModelTop3Response) -> list[AuctionTop3SignalSample]:
    samples: list[AuctionTop3SignalSample] = []
    for item in result.items:
        if item.bucket != "selected":
            continue
        rank = item.rank or len(samples) + 1
        sample_id = f"sig-{result.trade_date.replace('-', '')}-{item.symbol.replace('.', '')}-{rank}"
        samples.append(
            AuctionTop3SignalSample(
                sample_id=sample_id,
                trade_date=result.trade_date,
                symbol=item.symbol,
                name=item.name,
                rank=rank,
                score=item.prob_3pct,
                model_version=result.model_version,
                feature_version=result.feature_version,
                guard_rule=item.guard_rule or result.guard_rule,
                signals=item.trend_reasons,
                risk_flags=item.risk_flags,
                feature_snapshot={
                    "prob_3pct": item.prob_3pct,
                    "prev_close_price": item.prev_close_price,
                    "market_cap_float": item.market_cap_float,
                    "avg_amount_3d": item.avg_amount_3d,
                    "feature_end_date": item.feature_end_date,
                    "data_quality": item.data_quality,
                },
                source_status=result.source_status,
            )
        )
    return samples


def generate_simulated_trade_samples(
    signals: list[AuctionTop3SignalSample],
    bars_by_symbol: dict[str, list[KlineBar]],
    *,
    initial_capital: float,
    position_pct: float,
    entry_policy: AuctionTop3EntryPolicy = "open_0930",
    exit_policy: AuctionTop3ExitPolicy = "next_open_exit",
    portfolio_id: str = "default",
) -> list[AuctionTop3SimulatedTradeSample]:
    trades: list[AuctionTop3SimulatedTradeSample] = []
    for signal in signals:
        bars = bars_by_symbol.get(signal.symbol, [])
        trade_bar = _bar_for_date(bars, signal.trade_date)
        next_bar = _next_bar_after_date(bars, signal.trade_date)
        sample_id = f"sim-{signal.sample_id}-{entry_policy}-{exit_policy}"
        entry_price = trade_bar.open if trade_bar and entry_policy == "open_0930" else None
        exit_price = _exit_price(exit_policy, trade_bar, next_bar)
        return_pct = None
        profit_amount = None
        max_drawdown_pct = None
        max_favorable_pct = None
        if entry_price and exit_price:
            return_pct = round((exit_price - entry_price) / entry_price * 100, 2)
            profit_amount = round(initial_capital * position_pct * return_pct / 100, 2)
            if trade_bar:
                max_drawdown_pct = round((trade_bar.low - entry_price) / entry_price * 100, 2)
                max_favorable_pct = round((trade_bar.high - entry_price) / entry_price * 100, 2)
        trades.append(
            AuctionTop3SimulatedTradeSample(
                sample_id=sample_id,
                signal_sample_id=signal.sample_id,
                portfolio_id=portfolio_id,
                trade_date=signal.trade_date,
                symbol=signal.symbol,
                entry_policy=entry_policy,
                entry_price=entry_price,
                entry_time=f"{signal.trade_date} 09:30" if entry_price else None,
                exit_policy=exit_policy,
                exit_price=exit_price,
                exit_time=_exit_time(exit_policy, signal.trade_date, next_bar),
                position_pct=position_pct,
                return_pct=return_pct,
                profit_amount=profit_amount,
                max_drawdown_pct=max_drawdown_pct,
                max_favorable_pct=max_favorable_pct,
            )
        )
    return trades


def summarize_simulated_performance(
    trades: list[AuctionTop3SimulatedTradeSample],
    *,
    initial_capital: float,
    portfolio_id: str,
) -> AuctionTop3PerformanceResponse:
    complete = [
        trade
        for trade in trades
        if trade.portfolio_id == portfolio_id
        and trade.label != "data_incomplete"
        and trade.profit_amount is not None
    ]
    grouped: dict[str, list[AuctionTop3SimulatedTradeSample]] = defaultdict(list)
    for trade in complete:
        grouped[trade.trade_date].append(trade)
    equity = initial_capital
    peak = initial_capital
    points: list[AuctionTop3SimulatedPerformancePoint] = []
    for trade_date in sorted(grouped):
        daily_profit = sum(float(trade.profit_amount or 0) for trade in grouped[trade_date])
        equity += daily_profit
        peak = max(peak, equity)
        daily_return = daily_profit / initial_capital * 100
        cumulative_return = (equity - initial_capital) / initial_capital * 100
        drawdown = (equity - peak) / peak * 100 if peak else 0
        wins = sum(1 for trade in grouped[trade_date] if trade.label == "win")
        losses = sum(1 for trade in grouped[trade_date] if trade.label == "loss")
        first = grouped[trade_date][0]
        points.append(
            AuctionTop3SimulatedPerformancePoint(
                portfolio_id=portfolio_id,
                trade_date=trade_date,
                entry_policy=first.entry_policy,
                exit_policy=first.exit_policy,
                trade_count=len(grouped[trade_date]),
                win_count=wins,
                loss_count=losses,
                daily_return_pct=round(daily_return, 2),
                cumulative_return_pct=round(cumulative_return, 2),
                equity=round(equity, 2),
                max_drawdown_pct=round(drawdown, 2),
            )
        )
    wins = [trade for trade in complete if trade.label == "win"]
    losses = [trade for trade in complete if trade.label == "loss"]
    avg_win = sum(float(trade.return_pct or 0) for trade in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(float(trade.return_pct or 0) for trade in losses) / len(losses)) if losses else 0
    policy_returns: dict[str, float] = defaultdict(float)
    for trade in complete:
        policy_key = f"{trade.entry_policy}->{trade.exit_policy}"
        policy_returns[policy_key] += float(trade.profit_amount or 0)
    best_policy = max(policy_returns.items(), key=lambda item: item[1])[0] if policy_returns else None
    worst_policy = min(policy_returns.items(), key=lambda item: item[1])[0] if policy_returns else None
    summary = {
        "portfolio_id": portfolio_id,
        "latest_equity": round(equity, 2),
        "today_return_pct": points[-1].daily_return_pct if points else None,
        "cumulative_return_pct": points[-1].cumulative_return_pct if points else None,
        "max_drawdown_pct": min((point.max_drawdown_pct or 0 for point in points), default=0),
        "win_rate": round(len(wins) / len(complete), 4) if complete else None,
        "profit_loss_ratio": round(avg_win / avg_loss, 4) if avg_loss else None,
        "complete_sample_count": len(complete),
        "incomplete_sample_count": len([trade for trade in trades if trade.label == "data_incomplete"]),
        "best_policy": best_policy,
        "worst_policy": worst_policy,
    }
    return AuctionTop3PerformanceResponse(summary=summary, points=points, trades=trades)


def _signal_key(sample: AuctionTop3SignalSample) -> tuple[str, str, int | None]:
    return (sample.trade_date, sample.symbol, sample.rank)


def _simulated_key(sample: AuctionTop3SimulatedTradeSample) -> tuple[str, str, str, str]:
    return (sample.trade_date, sample.signal_sample_id, sample.entry_policy, sample.exit_policy)


def _read_jsonl_models(directory: Path, model: type[T], trade_date: str | None = None) -> list[T]:
    paths = [directory / f"{trade_date}.jsonl"] if trade_date else sorted(directory.glob("*.jsonl"))
    records: list[T] = []
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(model.model_validate_json(line))
    return records


def _bar_for_date(bars: list[KlineBar], trade_date: str) -> KlineBar | None:
    return next((bar for bar in bars if bar.date[:10] == trade_date), None)


def _next_bar_after_date(bars: list[KlineBar], trade_date: str) -> KlineBar | None:
    ordered = sorted(bars, key=lambda bar: bar.date)
    for bar in ordered:
        if bar.date[:10] > trade_date:
            return bar
    return None


def _exit_price(
    exit_policy: AuctionTop3ExitPolicy,
    trade_bar: KlineBar | None,
    next_bar: KlineBar | None,
) -> float | None:
    if exit_policy == "close_exit" and trade_bar:
        return trade_bar.close
    if exit_policy == "next_open_exit" and next_bar:
        return next_bar.open
    if exit_policy == "next_close_exit" and next_bar:
        return next_bar.close
    return None


def _exit_time(exit_policy: AuctionTop3ExitPolicy, trade_date: str, next_bar: KlineBar | None) -> str | None:
    if exit_policy == "close_exit":
        return f"{trade_date} 15:00"
    if exit_policy in {"next_open_exit", "next_close_exit"} and next_bar:
        clock = "09:30" if exit_policy == "next_open_exit" else "15:00"
        return f"{next_bar.date[:10]} {clock}"
    return None


def _model_sort_key(item: BaseModel) -> tuple[str, int, str]:
    payload = item.model_dump()
    return (
        str(payload.get("trade_date") or ""),
        int(payload.get("rank") or 999999),
        str(payload.get("symbol") or payload.get("sample_id") or ""),
    )
