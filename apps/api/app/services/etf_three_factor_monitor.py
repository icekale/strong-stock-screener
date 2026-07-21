from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from threading import RLock
from typing import Protocol
from zoneinfo import ZoneInfo

from app.models import (
    EtfActivityAlert,
    EtfFactorEvidence,
    EtfRadarOverviewResponse,
    EtfThreeFactorHistoryPoint,
    EtfThreeFactorHistoryResponse,
    EtfThreeFactorItem,
    EtfThreeFactorResponse,
    KlineBar,
    StrongStockSourceStatus,
)
from app.services.capital_signal_store import CapitalSignalStore
from app.services.capital_signals import enrich_etf_overview_close_changes
from app.services.etf_three_factor import (
    INDEX_SYMBOL_BY_ETF,
    combine_factor_scores,
    direction_factor_score,
    share_factor_score,
    signal_level,
    summarize_three_factor,
    volume_factor_score,
)
from app.services.etf_three_factor_store import EtfThreeFactorStore
from app.services.huijin_etf_activity import CORE_ETFS


SHANGHAI = ZoneInfo("Asia/Shanghai")
MONITOR_MODEL_VERSION = "three-factor-v1"


class QuoteProvider(Protocol):
    def get_quotes(self, symbols: list[str]) -> list[object]: ...


class DailyKlineProvider(Protocol):
    def get_klines(self, symbol: str, count: int = 40) -> list[KlineBar]: ...


class ShareSnapshotProvider(Protocol):
    def overview(self, *, force: bool = False) -> EtfRadarOverviewResponse: ...


@dataclass(frozen=True)
class _ShareValue:
    change_pct: float | None
    total_shares: float | None
    evidence: EtfFactorEvidence


@dataclass(frozen=True)
class _DailyBars:
    bars: list[KlineBar]
    error: str | None = None


class EtfThreeFactorMonitor:
    def __init__(
        self,
        *,
        quote_provider: QuoteProvider,
        daily_kline_provider: DailyKlineProvider,
        share_snapshot_provider: ShareSnapshotProvider,
        capital_store: CapitalSignalStore,
        store: EtfThreeFactorStore,
    ) -> None:
        self.quote_provider = quote_provider
        self.daily_kline_provider = daily_kline_provider
        self.share_snapshot_provider = share_snapshot_provider
        self.capital_store = capital_store
        self.store = store
        self._lock = RLock()
        self._daily_cache: dict[tuple[str, str], _DailyBars] = {}
        self._daily_cache_lookup: dict[tuple[str, str, str], tuple[str, str]] = {}

    def scan(self, now: datetime | None = None, force: bool = False) -> EtfThreeFactorResponse:
        with self._lock:
            scan_at = _shanghai_now(now)
            trade_date = scan_at.date().isoformat()
            previous = self.store.load_snapshot()
            if not _is_quote_session(scan_at):
                if not _is_successful_snapshot(previous):
                    return self._unavailable_response(scan_at, "非交易时段且尚无成功监控快照")
                if previous.trade_date != trade_date or not _is_post_close(scan_at):
                    return previous
                return self._post_close_scan(previous, scan_at, trade_date, force)

            quote_by_symbol, quote_error = self._load_current_quotes(trade_date)
            if quote_error is not None:
                return previous if _is_successful_snapshot(previous) else self._unavailable_response(scan_at, quote_error)

            share_values = self._share_values(scan_at, trade_date, force)
            items = [
                self._build_item(
                    symbol=symbol,
                    quote_by_symbol=quote_by_symbol,
                    share_value=share_values[symbol],
                    scan_at=scan_at,
                    trade_date=trade_date,
                )
                for symbol in CORE_ETFS
            ]
            response = self._response(scan_at, trade_date, items, "ETF与指数实时行情均为当前交易日")
            self._save_scan(previous, response, share_values)
            return response

    def latest(self) -> EtfThreeFactorResponse:
        with self._lock:
            snapshot = self.store.load_snapshot()
            if snapshot is not None:
                return snapshot
            return self._unavailable_response(_shanghai_now(None), "尚无监控快照")

    def history(self, symbol: str, days: int = 40) -> EtfThreeFactorHistoryResponse:
        with self._lock:
            now = _shanghai_now(None)
            snapshot = self.store.load_snapshot()
            generated_at = now.isoformat(timespec="seconds")
            return EtfThreeFactorHistoryResponse(
                generated_at=generated_at,
                trade_date=snapshot.trade_date if snapshot is not None else now.date().isoformat(),
                as_of=generated_at,
                signal_stage=snapshot.signal_stage if snapshot is not None else "post_close",
                model_version=MONITOR_MODEL_VERSION,
                source_status=[
                    StrongStockSourceStatus(
                        source="ETF三因子历史缓存",
                        status="success" if snapshot is not None else "stale",
                        detail="读取本地监控历史",
                    )
                ],
                symbol=symbol,
                points=self.store.load_history(symbol, days),
            )

    def enrich_overview(self, overview: EtfRadarOverviewResponse) -> EtfRadarOverviewResponse:
        with self._lock:
            snapshot = self.store.load_snapshot()
            if snapshot is None:
                return overview
            return enrich_etf_overview_close_changes(
                overview,
                {
                    item.symbol: (item.close_change_pct, item.close_change_trade_date)
                    for item in snapshot.items
                },
            )

    def _load_current_quotes(self, trade_date: str) -> tuple[dict[str, object], str | None]:
        symbols = [*CORE_ETFS, *INDEX_SYMBOL_BY_ETF.values()]
        try:
            quotes = self.quote_provider.get_quotes(symbols)
        except Exception as exc:
            return {}, f"TickFlow行情请求失败: {exc.__class__.__name__}"
        quote_by_symbol = {
            str(getattr(quote, "symbol")): quote
            for quote in quotes
            if isinstance(getattr(quote, "symbol", None), str)
        }
        for symbol in symbols:
            quote = quote_by_symbol.get(symbol)
            if quote is None:
                return {}, f"TickFlow行情缺失 {symbol}"
            if _quote_trade_date(getattr(quote, "quote_time", None)) != trade_date:
                return {}, f"TickFlow行情过期 {symbol}"
        return quote_by_symbol, None

    def _post_close_scan(
        self,
        previous: EtfThreeFactorResponse,
        scan_at: datetime,
        trade_date: str,
        force: bool,
    ) -> EtfThreeFactorResponse:
        refresh_shares = _is_share_refresh(scan_at) or (
            _is_after_share_disclosure(scan_at) and _has_pending_share_factors(previous)
        )
        share_values = self._share_values(scan_at, trade_date, force) if refresh_shares else None
        previous_items = {item.symbol: item for item in previous.items}
        refreshed_items = [
            self._refresh_post_close_item(
                previous_items[symbol],
                share_values[symbol] if share_values is not None else None,
                scan_at,
                trade_date,
            )
            for symbol in CORE_ETFS
            if symbol in previous_items
        ]
        items = [item for item, _ in refreshed_items]
        if len(items) != len(CORE_ETFS):
            return previous
        response = self._response(
            scan_at,
            trade_date,
            items,
            "复用当日最后一次成功盘中行情",
            post_close_kline_error=next(
                (error for _, error in refreshed_items if error is not None),
                None,
            ),
        )
        if share_values is None:
            self.store.save_snapshot(response)
        else:
            self._save_scan(previous, response, share_values)
        return response

    def _response(
        self,
        scan_at: datetime,
        trade_date: str,
        items: list[EtfThreeFactorItem],
        quote_detail: str,
        *,
        post_close_kline_error: str | None = None,
    ) -> EtfThreeFactorResponse:
        generated_at = scan_at.isoformat(timespec="seconds")
        kline_status = (
            StrongStockSourceStatus(
                source="ETF日K线",
                status="stale",
                detail=post_close_kline_error,
            )
            if post_close_kline_error is not None
            else _factor_source_status(
                source="ETF日K线",
                factors=[item.volume_factor for item in items],
                success_statuses={"available"},
                failure_prefix="日K线请求失败:",
                success_detail=f"核心ETF {len(items)} 只日K线完整",
                degraded_detail="日K线部分不可用",
            )
        )
        share_status = _factor_source_status(
            source="交易所ETF份额",
            factors=[item.share_factor for item in items],
            success_statuses={"available", "pending"},
            failure_prefix="官方份额请求失败:",
            success_detail=f"核心ETF {len(items)} 只官方份额可用或待披露",
            degraded_detail="官方份额部分不可用",
        )
        monitor_status = (
            "failed"
            if "failed" in {kline_status.status, share_status.status}
            else ("stale" if "stale" in {kline_status.status, share_status.status} else "success")
        )
        return EtfThreeFactorResponse(
            generated_at=generated_at,
            trade_date=trade_date,
            as_of=generated_at,
            signal_stage="post_close" if _is_post_close(scan_at) else "intraday",
            model_version=MONITOR_MODEL_VERSION,
            source_status=[
                StrongStockSourceStatus(
                    source="TickFlow行情",
                    status="success",
                    detail=quote_detail,
                ),
                kline_status,
                share_status,
                StrongStockSourceStatus(
                    source="ETF三因子监控",
                    status=monitor_status,
                    detail=(
                        f"核心ETF {len(items)} 只"
                        if monitor_status == "success"
                        else f"核心ETF {len(items)} 只，存在降级因子数据"
                    ),
                ),
            ],
            summary=summarize_three_factor(items),
            items=items,
            monitor_running=True,
            last_scan_at=generated_at,
        )

    def _save_scan(
        self,
        previous: EtfThreeFactorResponse | None,
        response: EtfThreeFactorResponse,
        share_values: dict[str, _ShareValue],
    ) -> None:
        self.store.upsert_history(
            [
                EtfThreeFactorHistoryPoint(
                    trade_date=response.trade_date,
                    symbol=item.symbol,
                    close_change_pct=item.close_change_pct,
                    volume=item.current_volume,
                    average_volume_20d=item.average_volume_20d,
                    volume_ratio=item.volume_ratio,
                    total_shares=share_values[item.symbol].total_shares,
                    share_change_pct=item.share_change_pct,
                    signal_score=item.signal_score,
                    level=item.level,
                )
                for item in response.items
            ]
        )
        self._upsert_alerts(previous, response)
        self.store.save_snapshot(response)

    def _daily_bars(
        self,
        trade_date: str,
        symbol: str,
        *,
        stage: str,
    ) -> _DailyBars:
        failure_key = (trade_date, symbol)
        cached_failure = self._daily_cache.get(failure_key)
        if cached_failure is not None and cached_failure.error is not None:
            return cached_failure

        lookup_key = (stage, trade_date, symbol)
        cache_key = self._daily_cache_lookup.get(lookup_key)
        if cache_key is not None:
            return self._daily_cache[cache_key]

        include_current_day = stage == "post_close"
        try:
            daily_bars = _DailyBars(self.daily_kline_provider.get_klines(symbol, count=40))
        except Exception as exc:
            daily_bars = _DailyBars([], f"日K线请求失败: {exc.__class__.__name__}")
            self._daily_cache[failure_key] = daily_bars
            self._daily_cache_lookup[lookup_key] = failure_key
            return daily_bars
        completed_date = _latest_completed_bar_date(
            daily_bars.bars,
            trade_date,
            include_current_day=include_current_day,
        )
        cache_key = (completed_date or trade_date, symbol)
        self._daily_cache[cache_key] = daily_bars
        self._daily_cache_lookup[lookup_key] = cache_key
        return daily_bars

    def _build_item(
        self,
        *,
        symbol: str,
        quote_by_symbol: dict[str, object],
        share_value: _ShareValue,
        scan_at: datetime,
        trade_date: str,
    ) -> EtfThreeFactorItem:
        definition = CORE_ETFS[symbol]
        index_symbol = INDEX_SYMBOL_BY_ETF[symbol]
        quote = quote_by_symbol[symbol]
        index_quote = quote_by_symbol[index_symbol]
        daily_bars = self._daily_bars(trade_date, symbol, stage="intraday")
        completed = [
            bar
            for bar in daily_bars.bars
            if _bar_trade_date(bar.date) is not None and _bar_trade_date(bar.date) < trade_date
        ]
        completed.sort(key=lambda bar: _bar_trade_date(bar.date) or "")
        baseline = completed[-20:]
        average_volume = (
            sum(bar.volume for bar in baseline) / 20
            if len(baseline) == 20 and all(_valid_number(bar.volume) for bar in baseline)
            else None
        )
        current_volume = _number(getattr(quote, "volume", None))
        volume_ratio = (
            current_volume / average_volume
            if current_volume is not None and average_volume not in {None, 0}
            else None
        )
        close_change = _close_change(completed)
        quote_time = _text(getattr(quote, "quote_time", None))
        index_quote_time = _text(getattr(index_quote, "quote_time", None))
        volume_evidence = EtfFactorEvidence(
            score=volume_factor_score(volume_ratio),
            value=volume_ratio,
            status="available" if volume_ratio is not None else "missing",
            source="TickFlow成交量",
            data_date=trade_date if average_volume is not None else None,
            updated_at=quote_time,
            detail=(
                "当前累计成交量与最近20个已完成交易日均量"
                if volume_ratio is not None
                else daily_bars.error
                if daily_bars.error is not None
                else "当前成交量或20个已完成交易日成交量不足"
            ),
        )
        etf_change = _number(getattr(quote, "pct_change", None))
        index_change = _number(getattr(index_quote, "pct_change", None))
        direction_score = direction_factor_score(etf_change, index_change)
        direction_evidence = EtfFactorEvidence(
            score=direction_score,
            value=etf_change,
            status="available" if direction_score is not None else "missing",
            source="TickFlow行情",
            data_date=trade_date,
            updated_at=quote_time,
            detail=(
                f"指数 {index_symbol} {index_change}%；指数行情时间 {index_quote_time}"
                if direction_score is not None
                else f"ETF或指数涨跌幅缺失；指数行情时间 {index_quote_time}"
            ),
        )
        score, mode = combine_factor_scores(
            volume_evidence.score,
            direction_evidence.score,
            share_value.evidence.score,
            share_value.evidence.status == "pending",
        )
        return EtfThreeFactorItem(
            symbol=symbol,
            name=definition.name,
            index_name=definition.index_name,
            index_symbol=index_symbol,
            close_change_pct=close_change[0],
            close_change_trade_date=close_change[1],
            intraday_change_pct=etf_change,
            index_change_pct=index_change,
            current_volume=current_volume,
            average_volume_20d=average_volume,
            volume_ratio=volume_ratio,
            share_change_pct=share_value.change_pct,
            volume_factor=volume_evidence,
            direction_factor=direction_evidence,
            share_factor=share_value.evidence,
            signal_score=score,
            mode=mode,
            level=signal_level(score),
            updated_at=scan_at.isoformat(timespec="seconds"),
        )

    def _refresh_post_close_item(
        self,
        previous: EtfThreeFactorItem,
        share_value: _ShareValue | None,
        scan_at: datetime,
        trade_date: str,
    ) -> tuple[EtfThreeFactorItem, str | None]:
        daily_bars = self._daily_bars(trade_date, previous.symbol, stage="post_close")
        completed = [
            bar
            for bar in daily_bars.bars
            if _bar_trade_date(bar.date) is not None and _bar_trade_date(bar.date) <= trade_date
        ]
        completed.sort(key=lambda bar: _bar_trade_date(bar.date) or "")
        close_change = _close_change(completed)
        next_share = share_value or _ShareValue(
            change_pct=previous.share_change_pct,
            total_shares=None,
            evidence=previous.share_factor,
        )
        score, mode = combine_factor_scores(
            previous.volume_factor.score,
            previous.direction_factor.score,
            next_share.evidence.score,
            next_share.evidence.status == "pending",
        )
        return (
            previous.model_copy(
                update={
                    "close_change_pct": close_change[0],
                    "close_change_trade_date": close_change[1],
                    "share_change_pct": next_share.change_pct,
                    "share_factor": next_share.evidence,
                    "signal_score": score,
                    "mode": mode,
                    "level": signal_level(score),
                    "updated_at": scan_at.isoformat(timespec="seconds"),
                }
            ),
            daily_bars.error,
        )

    def _share_values(
        self,
        scan_at: datetime,
        trade_date: str,
        force: bool,
    ) -> dict[str, _ShareValue]:
        if (scan_at.hour, scan_at.minute) < (19, 0):
            return {
                symbol: _ShareValue(
                    change_pct=None,
                    total_shares=None,
                    evidence=EtfFactorEvidence(
                        status="pending",
                        source="交易所ETF份额",
                        data_date=trade_date,
                        updated_at=scan_at.isoformat(timespec="seconds"),
                        detail="交易所当日ETF份额预计19:00后披露",
                    ),
                )
                for symbol in CORE_ETFS
            }
        try:
            overview = self.share_snapshot_provider.overview(force=force)
        except Exception as exc:
            return self._missing_share_values(trade_date, f"官方份额请求失败: {exc.__class__.__name__}")
        if overview.trade_date != trade_date:
            return self._stale_share_values(
                trade_date,
                f"官方份额日期 {overview.trade_date} 与扫描日期不一致",
            )

        activity_by_symbol = {item.symbol: item for item in overview.core_items}
        history = self.capital_store.load_share_history()
        output: dict[str, _ShareValue] = {}
        for symbol in CORE_ETFS:
            activity = activity_by_symbol.get(symbol)
            current = next(
                (row for row in history if row.symbol == symbol and row.trade_date == trade_date),
                None,
            )
            previous = max(
                (row for row in history if row.symbol == symbol and row.trade_date < trade_date),
                key=lambda row: row.trade_date,
                default=None,
            )
            if (
                activity is None
                or current is None
                or previous is None
                or not _valid_number(activity.daily_change_pct)
                or not _valid_number(activity.total_shares)
                or not _valid_number(activity.previous_total_shares)
                or current.total_shares != activity.total_shares
                or previous.total_shares != activity.previous_total_shares
            ):
                output[symbol] = _ShareValue(
                    change_pct=None,
                    total_shares=None,
                    evidence=EtfFactorEvidence(
                        status="missing",
                        source="交易所ETF份额",
                        data_date=trade_date,
                        updated_at=overview.generated_at,
                        detail="官方当日及前一交易日份额未同时形成真实记录",
                    ),
                )
                continue
            change_pct = float(activity.daily_change_pct)
            output[symbol] = _ShareValue(
                change_pct=change_pct,
                total_shares=float(activity.total_shares),
                evidence=EtfFactorEvidence(
                    score=share_factor_score(change_pct),
                    value=change_pct,
                    status="available",
                    source="交易所ETF份额",
                    data_date=trade_date,
                    updated_at=overview.generated_at,
                    detail="官方当日及前一交易日份额",
                ),
            )
        return output

    @staticmethod
    def _missing_share_values(trade_date: str, detail: str) -> dict[str, _ShareValue]:
        return {
            symbol: _ShareValue(
                change_pct=None,
                total_shares=None,
                evidence=EtfFactorEvidence(
                    status="missing",
                    source="交易所ETF份额",
                    data_date=trade_date,
                    detail=detail,
                ),
            )
            for symbol in CORE_ETFS
        }

    @staticmethod
    def _stale_share_values(trade_date: str, detail: str) -> dict[str, _ShareValue]:
        return {
            symbol: _ShareValue(
                change_pct=None,
                total_shares=None,
                evidence=EtfFactorEvidence(
                    status="stale",
                    source="交易所ETF份额",
                    data_date=trade_date,
                    detail=detail,
                ),
            )
            for symbol in CORE_ETFS
        }

    def _upsert_alerts(
        self,
        previous: EtfThreeFactorResponse | None,
        current: EtfThreeFactorResponse,
    ) -> None:
        previous_items = {item.symbol: item for item in previous.items} if previous else {}
        for item in current.items:
            old = previous_items.get(item.symbol)
            if item.level != "high" or (old is not None and old.level == "high"):
                continue
            alert_type = "single_upgrade" if item.mode == "three_factor" else "single_high"
            self.store.upsert_alert(self._single_alert(current, item, alert_type))
        previous_state = previous.summary.market_state if previous is not None else None
        if current.summary.market_state in {"watch", "high"} and previous_state != current.summary.market_state:
            self.store.upsert_alert(self._market_alert(current))

    @staticmethod
    def _single_alert(
        response: EtfThreeFactorResponse,
        item: EtfThreeFactorItem,
        alert_type: str,
    ) -> EtfActivityAlert:
        return EtfActivityAlert(
            alert_id=_alert_id(response.generated_at, alert_type, item.symbol),
            trade_date=response.trade_date,
            alert_type=alert_type,
            level="high",
            symbol=item.symbol,
            title=f"{item.name} 疑似活动",
            message=(
                f"量比 {item.volume_ratio}; ETF涨跌 {item.intraday_change_pct}%; "
                f"指数涨跌 {item.index_change_pct}%; 份额变动 {item.share_change_pct}%; "
                f"行情时间 {item.direction_factor.updated_at}; 份额时间 {item.share_factor.updated_at}"
            ),
            signal_score=item.signal_score or 0,
            triggered_at=response.generated_at,
            last_triggered_at=response.generated_at,
            evidence={
                "volume_ratio": item.volume_ratio,
                "etf_change_pct": item.intraday_change_pct,
                "index_change_pct": item.index_change_pct,
                "share_change_pct": item.share_change_pct,
                "quote_time": item.direction_factor.updated_at,
                "share_time": item.share_factor.updated_at,
            },
        )

    @staticmethod
    def _market_alert(response: EtfThreeFactorResponse) -> EtfActivityAlert:
        alert_type = "market_high" if response.summary.market_state == "high" else "market_watch"
        representative = next((item for item in response.items if item.signal_score is not None), None)
        return EtfActivityAlert(
            alert_id=_alert_id(response.generated_at, alert_type, None),
            trade_date=response.trade_date,
            alert_type=alert_type,
            level=response.summary.market_state,
            title="ETF市场疑似活动",
            message=(
                f"有效 {response.summary.valid_count} 只; 高分 {response.summary.high_count} 只; "
                f"平均分 {response.summary.signal_score}; 量比 "
                f"{representative.volume_ratio if representative is not None else None}; ETF涨跌 "
                f"{representative.intraday_change_pct if representative is not None else None}%; "
                f"指数涨跌 {representative.index_change_pct if representative is not None else None}%; "
                f"份额变动 {representative.share_change_pct if representative is not None else None}%; "
                f"量能时间 {representative.volume_factor.updated_at if representative is not None else None}; "
                f"行情时间 {representative.direction_factor.updated_at if representative is not None else None}; "
                f"份额时间 {representative.share_factor.updated_at if representative is not None else None}"
            ),
            signal_score=response.summary.signal_score or 0,
            triggered_at=response.generated_at,
            last_triggered_at=response.generated_at,
        )

    @staticmethod
    def _unavailable_response(now: datetime, detail: str) -> EtfThreeFactorResponse:
        generated_at = now.isoformat(timespec="seconds")
        return EtfThreeFactorResponse(
            generated_at=generated_at,
            trade_date=now.date().isoformat(),
            as_of=generated_at,
            signal_stage="post_close" if _is_post_close(now) else "intraday",
            model_version=MONITOR_MODEL_VERSION,
            source_status=[
                StrongStockSourceStatus(source="ETF三因子监控", status="failed", detail=detail)
            ],
            monitor_running=False,
        )


def _shanghai_now(now: datetime | None) -> datetime:
    value = now or datetime.now(SHANGHAI)
    return value.replace(tzinfo=SHANGHAI) if value.tzinfo is None else value.astimezone(SHANGHAI)


def _is_quote_session(now: datetime) -> bool:
    if now.weekday() >= 5:
        return False
    clock = (now.hour, now.minute)
    return (9, 30) <= clock <= (11, 30) or (13, 0) <= clock <= (15, 0)


def _is_post_close(now: datetime) -> bool:
    return (now.hour, now.minute) >= (15, 5)


def _is_share_refresh(now: datetime) -> bool:
    return now.weekday() < 5 and (now.hour, now.minute) in {(19, 5), (19, 35)}


def _is_after_share_disclosure(now: datetime) -> bool:
    return now.weekday() < 5 and (now.hour, now.minute) >= (19, 0)


def _has_pending_share_factors(snapshot: EtfThreeFactorResponse) -> bool:
    return any(item.share_factor.status == "pending" for item in snapshot.items)


def _is_successful_snapshot(snapshot: EtfThreeFactorResponse | None) -> bool:
    return snapshot is not None and snapshot.monitor_running and bool(snapshot.items)


def _quote_trade_date(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if len(value) >= 10 and value[:10].count("-") == 2:
        return value[:10]
    if value.isdigit():
        timestamp = int(value)
        if timestamp > 10_000_000_000:
            timestamp //= 1000
        return datetime.fromtimestamp(timestamp, SHANGHAI).date().isoformat()
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return (parsed.replace(tzinfo=SHANGHAI) if parsed.tzinfo is None else parsed.astimezone(SHANGHAI)).date().isoformat()


def _bar_trade_date(value: str) -> str | None:
    compact = value.replace("-", "")
    if len(compact) != 8 or not compact.isdigit():
        return None
    return f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"


def _latest_completed_bar_date(
    bars: list[KlineBar],
    trade_date: str,
    *,
    include_current_day: bool,
) -> str | None:
    completed_dates = [
        bar_date
        for bar in bars
        if (bar_date := _bar_trade_date(bar.date)) is not None
        and (bar_date <= trade_date if include_current_day else bar_date < trade_date)
    ]
    return max(completed_dates, default=None)


def _factor_source_status(
    *,
    source: str,
    factors: list[EtfFactorEvidence],
    success_statuses: set[str],
    failure_prefix: str,
    success_detail: str,
    degraded_detail: str,
) -> StrongStockSourceStatus:
    failures = [
        factor
        for factor in factors
        if factor.detail is not None and factor.detail.startswith(failure_prefix)
    ]
    if failures:
        return StrongStockSourceStatus(
            source=source,
            status="failed",
            detail=failures[0].detail or failure_prefix,
        )
    unavailable_symbols = [
        symbol
        for symbol, factor in zip(CORE_ETFS, factors, strict=True)
        if factor.status not in success_statuses
    ]
    if unavailable_symbols:
        return StrongStockSourceStatus(
            source=source,
            status="stale",
            detail=f"{degraded_detail}: {', '.join(unavailable_symbols)}",
        )
    return StrongStockSourceStatus(source=source, status="success", detail=success_detail)


def _close_change(completed: list[KlineBar]) -> tuple[float | None, str | None]:
    if len(completed) < 2 or not _valid_number(completed[-2].close) or not _valid_number(completed[-1].close):
        return None, None
    if completed[-2].close == 0:
        return None, None
    return (
        (completed[-1].close / completed[-2].close - 1) * 100,
        _bar_trade_date(completed[-1].date),
    )


def _number(value: object) -> float | None:
    if not _valid_number(value):
        return None
    return float(value)


def _valid_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _alert_id(triggered_at: str, alert_type: str, symbol: str | None) -> str:
    payload = f"{triggered_at}:{alert_type}:{symbol or ''}".encode()
    return hashlib.sha256(payload).hexdigest()[:24]
