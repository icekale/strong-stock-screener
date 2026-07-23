from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from statistics import mean
from zoneinfo import ZoneInfo

from app.models import (
    CapitalSignalMetadata,
    EtfExcessFlowPoint,
    EtfExcessFlowResponse,
    EtfSharePoint,
    HuijinEtfActivityItem,
    StrongStockSourceStatus,
)
from app.services.capital_signal_store import CapitalSignalStore
from app.services.huijin_etf_activity import ALL_ETFS


BASELINE_DAYS = 20
MODEL_VERSION = "etf-excess-flow-v1"
FORMULA = (
    "sign(share_delta) * max(abs(share_delta) - "
    "share_change_20d_avg_abs, 0) * close"
)


@dataclass(frozen=True)
class EtfExcessFlowActivityResult:
    items: list[HuijinEtfActivityItem]


class EtfExcessFlowService:
    def __init__(self, store: CapitalSignalStore, clock=None) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(ZoneInfo("Asia/Shanghai")))

    def trend(self, *, days: int = 60) -> EtfExcessFlowResponse:
        history = self.store.load_share_history()
        symbols = tuple(ALL_ETFS)
        now = self.clock()
        selected_history = [row for row in history if row.symbol in symbols]
        latest_date = max(
            (row.trade_date for row in selected_history),
            default=_latest_weekday(now),
        )
        latest_expected_date = _latest_weekday(now)
        has_current_history = latest_date == latest_expected_date
        source_status = [
            StrongStockSourceStatus(
                source="ETF份额历史缓存",
                status="success" if selected_history and has_current_history else "stale",
                detail=(
                    f"监控池 {len(symbols)} 只，最新归档 {latest_date}"
                    if selected_history
                    else "无可用监控池 ETF 份额历史缓存"
                ),
            )
        ]
        return build_flow_trend(
            history,
            symbols=symbols,
            days=days,
            now=now,
            source_status=source_status,
        )


def build_activity_metrics(
    history: list[EtfSharePoint],
    symbols: Iterable[str],
) -> EtfExcessFlowActivityResult:
    selected_symbols = tuple(dict.fromkeys(symbols))
    observed_dates = sorted({row.trade_date for row in history})
    date_positions = {trade_date: index for index, trade_date in enumerate(observed_dates)}
    rows_by_symbol: dict[str, list[EtfSharePoint]] = {
        symbol: sorted(
            (row for row in history if row.symbol == symbol),
            key=lambda row: row.trade_date,
        )
        for symbol in selected_symbols
    }
    items: list[HuijinEtfActivityItem] = []
    for symbol in selected_symbols:
        definition = ALL_ETFS.get(symbol)
        if definition is None:
            continue
        previous_total: float | None = None
        previous_trade_date: str | None = None
        prior_deltas: list[float] = []
        for row in rows_by_symbol[symbol]:
            delta = None
            if (
                previous_total is not None
                and isfinite(previous_total)
                and isfinite(row.total_shares)
                and _is_adjacent_observed_date(
                    previous_trade_date,
                    row.trade_date,
                    date_positions,
                )
            ):
                delta = row.total_shares - previous_total
            baseline = (
                mean(abs(value) for value in prior_deltas[-BASELINE_DAYS:])
                if len(prior_deltas) >= BASELINE_DAYS
                else None
            )
            multiple = (
                abs(delta) / baseline
                if delta is not None and baseline is not None and baseline > 0
                else None
            )
            direction = _direction(delta)
            items.append(
                HuijinEtfActivityItem(
                    symbol=symbol,
                    name=definition.name,
                    index_name=definition.index_name,
                    role=definition.role,
                    paired_symbol=definition.paired_symbol,
                    trade_date=row.trade_date,
                    total_shares=row.total_shares,
                    previous_total_shares=previous_total,
                    share_delta=delta,
                    direction=direction,
                    share_change_20d_avg_abs=baseline,
                    share_change_20d_multiple=multiple,
                    is_tenfold_share_change=multiple is not None and multiple >= 10,
                )
            )
            if delta is not None and isfinite(delta):
                prior_deltas.append(delta)
            previous_total = row.total_shares
            previous_trade_date = row.trade_date
    return EtfExcessFlowActivityResult(
        items=sorted(items, key=lambda item: (item.trade_date, item.symbol))
    )


def build_flow_trend(
    history: list[EtfSharePoint],
    symbols: Iterable[str],
    days: int = 60,
    *,
    now: datetime | None = None,
    source_status: Iterable[StrongStockSourceStatus] | None = None,
) -> EtfExcessFlowResponse:
    selected_symbols = tuple(dict.fromkeys(symbols))
    result = build_activity_metrics(history, selected_symbols)
    rows_by_key = {(row.trade_date, row.symbol): row for row in history}
    activity_by_key = {(item.trade_date, item.symbol): item for item in result.items}
    dates = sorted({item.trade_date for item in result.items})[-days:]
    points: list[EtfExcessFlowPoint] = []
    expected_count = len(selected_symbols)
    for trade_date in dates:
        inflow = 0.0
        outflow = 0.0
        coverage_count = 0
        increase_count = 0
        decrease_count = 0
        trigger_symbols: list[str] = []
        for symbol in selected_symbols:
            item = activity_by_key.get((trade_date, symbol))
            if item is None:
                continue
            if item.is_tenfold_share_change:
                trigger_symbols.append(symbol)
                if item.direction == "increase":
                    increase_count += 1
                elif item.direction == "decrease":
                    decrease_count += 1
            baseline = item.share_change_20d_avg_abs
            row = rows_by_key.get((trade_date, symbol))
            if (
                item.share_delta is None
                or baseline is None
                or baseline <= 0
                or row is None
                or row.close is None
                or not isfinite(row.close)
                or row.close <= 0
            ):
                continue
            coverage_count += 1
            excess_shares = _signed_excess_shares(item.share_delta, baseline)
            flow = excess_shares * row.close
            if flow > 0:
                inflow += flow
            elif flow < 0:
                outflow += abs(flow)
        points.append(
            EtfExcessFlowPoint(
                trade_date=trade_date,
                net_excess_flow_cny=(inflow - outflow) if coverage_count else None,
                excess_inflow_cny=inflow if coverage_count else None,
                excess_outflow_cny=outflow if coverage_count else None,
                coverage_count=coverage_count,
                expected_count=expected_count,
                tenfold_increase_count=increase_count,
                tenfold_decrease_count=decrease_count,
                trigger_symbols=sorted(trigger_symbols),
            )
        )
    current = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    generated_at = current.isoformat(timespec="seconds")
    trade_date = dates[-1] if dates else _latest_weekday(current)
    metadata = CapitalSignalMetadata(
        generated_at=generated_at,
        trade_date=trade_date,
        as_of=generated_at,
        signal_stage="post_close",
        model_version=MODEL_VERSION,
        source_status=list(source_status or []),
    )
    return EtfExcessFlowResponse(
        **metadata.model_dump(),
        formula=FORMULA,
        expected_count=expected_count,
        points=points,
    )


def _direction(delta: float | None) -> str:
    if delta is None:
        return "unknown"
    if delta > 0:
        return "increase"
    if delta < 0:
        return "decrease"
    return "flat"


def _signed_excess_shares(delta: float, baseline: float) -> float:
    excess = max(abs(delta) - baseline, 0)
    return excess if delta > 0 else -excess if delta < 0 else 0.0


def _latest_weekday(now: datetime) -> str:
    current = now.date()
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current.isoformat()


def _is_adjacent_observed_date(
    previous_trade_date: str | None,
    trade_date: str,
    date_positions: dict[str, int],
) -> bool:
    if previous_trade_date is None:
        return False
    previous_position = date_positions.get(previous_trade_date)
    current_position = date_positions.get(trade_date)
    if previous_position is None or current_position != previous_position + 1:
        return False
    return True
