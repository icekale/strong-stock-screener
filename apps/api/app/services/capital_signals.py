from __future__ import annotations

import statistics
from collections.abc import Iterable
from datetime import datetime, timedelta
from threading import RLock
from typing import Protocol
from zoneinfo import ZoneInfo

from app.models import (
    CapitalSummaryResponse,
    EtfRadarFactorDefinition,
    EtfRadarHistoryPoint,
    EtfRadarHistoryResponse,
    EtfRadarHoldersResponse,
    EtfRadarItem,
    EtfRadarMethodologyResponse,
    EtfRadarOverviewResponse,
    EtfRadarSummary,
    EtfShareChange,
    EtfSharePoint,
    EtfSynchronization,
    MarginMarketPoint,
    MarginSummary,
    StrongStockSourceStatus,
)
from app.providers.capital_signals import CapitalProviderResult
from app.services.capital_signal_store import CapitalSignalStore


MODEL_VERSION = "heuristic-v1"
POOL_VERSION = "core-a-share-v1"
CORE_ETF_POOL = {
    "510300.SH": ("沪深300ETF", "沪深300"),
    "510310.SH": ("沪深300ETF易方达", "沪深300"),
    "510500.SH": ("中证500ETF", "中证500"),
    "512100.SH": ("中证1000ETF", "中证1000"),
    "563360.SH": ("中证A500ETF", "中证A500"),
    "588000.SH": ("科创50ETF", "科创50"),
    "159915.SZ": ("创业板ETF", "创业板指"),
}


class CapitalDataProvider(Protocol):
    def get_margin_rows(self, trade_date: str) -> CapitalProviderResult[MarginMarketPoint]: ...

    def get_etf_share_rows(
        self, trade_date: str, symbols: list[str] | tuple[str, ...]
    ) -> CapitalProviderResult[EtfSharePoint]: ...


class QuoteProvider(Protocol):
    def get_quotes(self, symbols: list[str]) -> list[object]: ...


class HolderProvider(Protocol):
    def get_holder_positions(
        self, symbols: dict[str, str]
    ) -> CapitalProviderResult: ...


class CapitalSignalService:
    def __init__(
        self,
        *,
        provider: CapitalDataProvider,
        store: CapitalSignalStore,
        quote_provider: QuoteProvider | None = None,
        holder_provider: HolderProvider | None = None,
        clock=None,
        ttl_seconds: int = 60,
    ) -> None:
        self.provider = provider
        self.store = store
        self.quote_provider = quote_provider
        self.holder_provider = holder_provider
        self.clock = clock or (lambda: datetime.now(ZoneInfo("Asia/Shanghai")))
        self.ttl_seconds = ttl_seconds
        self._lock = RLock()
        self._homepage_cache: tuple[datetime, CapitalSummaryResponse] | None = None

    def overview(self, *, force: bool = False) -> EtfRadarOverviewResponse:
        with self._lock:
            now = self.clock()
            cached = self.store.load_snapshot()
            if not force and cached is not None and _is_fresh(cached.generated_at, now, self.ttl_seconds):
                return cached

            trade_date = _latest_weekday(now)
            symbols = list(CORE_ETF_POOL)
            current_result = self.provider.get_etf_share_rows(trade_date, symbols)
            if not current_result.rows:
                if cached is not None:
                    return cached.model_copy(
                        update={
                            "source_status": [
                                *cached.source_status,
                                StrongStockSourceStatus(
                                    source="ETF资金雷达缓存",
                                    status="stale",
                                    detail="远端刷新失败，返回最近持久化缓存",
                                ),
                            ]
                        }
                    )
                return self._empty_overview(now, trade_date, current_result.source_status)

            previous_date = _previous_weekday(trade_date)
            history = self.store.load_share_history()
            stored_current_rows = [
                row
                for row in history
                if row.trade_date == trade_date and row.symbol in CORE_ETF_POOL
            ]
            current_rows = _merge_share_history(stored_current_rows, current_result.rows)
            retained_count = len(current_rows) - len(current_result.rows)
            current_status = list(current_result.source_status)
            if retained_count > 0:
                current_status.append(
                    StrongStockSourceStatus(
                        source="ETF份额缓存",
                        status="stale",
                        detail=f"本次部分刷新，保留 {retained_count} 只同日缓存记录",
                    )
                )
            previous_by_symbol = _latest_share_before(history, trade_date)
            missing_sse = [
                symbol
                for symbol in symbols
                if symbol.endswith(".SH") and symbol not in previous_by_symbol
            ]
            previous_status: list[StrongStockSourceStatus] = []
            if missing_sse:
                previous_result = self.provider.get_etf_share_rows(previous_date, missing_sse)
                history = _merge_share_history(history, previous_result.rows)
                previous_by_symbol = _latest_share_before(history, trade_date)
                previous_status = previous_result.source_status

            close_by_symbol = self._quote_closes(symbols)
            enriched: list[EtfSharePoint] = []
            items: list[EtfRadarItem] = []
            for row in current_rows:
                previous = previous_by_symbol.get(row.symbol)
                close = close_by_symbol.get(row.symbol, row.close)
                change = build_share_change(
                    current_shares=row.total_shares,
                    previous_shares=previous.total_shares if previous else None,
                    close=close,
                )
                prior_amounts = [
                    item.estimated_subscription_cny
                    for item in history
                    if item.symbol == row.symbol
                    and item.trade_date < row.trade_date
                    and item.estimated_subscription_cny is not None
                ][-60:]
                robust_score = robust_z_score(change.estimated_subscription_cny, prior_amounts)
                enriched_row = row.model_copy(
                    update={
                        "close": close,
                        "share_change": change.share_change,
                        "estimated_subscription_cny": change.estimated_subscription_cny,
                        "robust_score": robust_score,
                    }
                )
                enriched.append(enriched_row)
                items.append(_radar_item(enriched_row))

            history = _merge_share_history(history, enriched)
            self.store.save_share_history(history)
            summary = _radar_summary(items)
            generated_at = now.isoformat(timespec="seconds")
            snapshot = EtfRadarOverviewResponse(
                generated_at=generated_at,
                trade_date=trade_date,
                as_of=generated_at,
                signal_stage=_signal_stage(now, trade_date),
                model_version=MODEL_VERSION,
                source_status=[*current_status, *previous_status],
                evidence_strength=summary.evidence_strength,
                evidence_level=summary.evidence_level,
                valid_etf_count=summary.valid_etf_count,
                expected_etf_count=summary.expected_etf_count,
                estimated_subscription_cny=summary.estimated_subscription_cny,
                evidence=summary.evidence,
                items=items,
            )
            self.store.save_snapshot(snapshot)
            return snapshot

    def homepage_summary(self, *, force: bool = False) -> CapitalSummaryResponse:
        with self._lock:
            now = self.clock()
            if not force and self._homepage_cache is not None:
                cached_at, cached = self._homepage_cache
                if (now - cached_at).total_seconds() <= self.ttl_seconds:
                    return cached

            radar = self.overview(force=force)
            margin, margin_status = self._margin_summary(radar.trade_date)
            result = CapitalSummaryResponse(
                generated_at=radar.generated_at,
                trade_date=radar.trade_date,
                as_of=radar.as_of,
                signal_stage=radar.signal_stage,
                model_version=radar.model_version,
                source_status=[*radar.source_status, *margin_status],
                margin=margin,
                etf_radar=EtfRadarSummary(
                    evidence_strength=radar.evidence_strength,
                    evidence_level=radar.evidence_level,
                    valid_etf_count=radar.valid_etf_count,
                    expected_etf_count=radar.expected_etf_count,
                    estimated_subscription_cny=radar.estimated_subscription_cny,
                    evidence=radar.evidence[:3],
                ),
            )
            self._homepage_cache = (now, result)
            return result

    def history(self, *, days: int = 120) -> EtfRadarHistoryResponse:
        now = self.clock()
        trade_date = _latest_weekday(now)
        rows = self.store.load_share_history()
        dates = sorted({row.trade_date for row in rows})[-days:]
        points = [
            EtfRadarHistoryPoint(
                trade_date=row.trade_date,
                symbol=row.symbol,
                name=row.name or CORE_ETF_POOL.get(row.symbol, (row.symbol, ""))[0],
                total_shares=row.total_shares,
                share_change=row.share_change,
                estimated_subscription_cny=row.estimated_subscription_cny,
                robust_score=row.robust_score,
            )
            for row in rows
            if row.trade_date in dates
        ]
        generated_at = now.isoformat(timespec="seconds")
        return EtfRadarHistoryResponse(
            generated_at=generated_at,
            trade_date=trade_date,
            as_of=generated_at,
            signal_stage="post_close",
            model_version=MODEL_VERSION,
            source_status=[
                StrongStockSourceStatus(
                    source="ETF份额历史缓存",
                    status="success" if points else "stale",
                    detail=f"返回最近 {len(dates)} 个可用交易日",
                )
            ],
            points=points,
        )

    def holders(self) -> EtfRadarHoldersResponse:
        now = self.clock()
        generated_at = now.isoformat(timespec="seconds")
        expected_period = _expected_holder_period(now)
        cached = self.store.load_holder_reports()
        cached_period = max((item.report_period for item in cached), default=None)
        if cached and cached_period is not None and cached_period >= expected_period:
            return EtfRadarHoldersResponse(
                generated_at=generated_at,
                trade_date=_latest_weekday(now),
                as_of=generated_at,
                signal_stage="disclosure",
                model_version=MODEL_VERSION,
                source_status=[
                    StrongStockSourceStatus(
                        source="基金持有人披露缓存",
                        status="success",
                        detail=f"最新报告期 {cached_period}",
                    )
                ],
                positions=cached,
            )

        if self.holder_provider is not None:
            result = self.holder_provider.get_holder_positions(
                {symbol: details[0] for symbol, details in CORE_ETF_POOL.items()}
            )
            if result.rows:
                self.store.save_holder_reports(result.rows)
                return EtfRadarHoldersResponse(
                    generated_at=generated_at,
                    trade_date=_latest_weekday(now),
                    as_of=generated_at,
                    signal_stage="disclosure",
                    model_version=MODEL_VERSION,
                    source_status=result.source_status,
                    positions=result.rows,
                )
            if cached:
                return EtfRadarHoldersResponse(
                    generated_at=generated_at,
                    trade_date=_latest_weekday(now),
                    as_of=generated_at,
                    signal_stage="disclosure",
                    model_version=MODEL_VERSION,
                    source_status=[
                        *result.source_status,
                        StrongStockSourceStatus(
                            source="基金持有人披露缓存",
                            status="stale",
                            detail=f"刷新失败，保留报告期 {cached_period}",
                        ),
                    ],
                    positions=cached,
                )

        return EtfRadarHoldersResponse(
            generated_at=generated_at,
            trade_date=_latest_weekday(now),
            as_of=generated_at,
            signal_stage="disclosure",
            model_version=MODEL_VERSION,
            source_status=[
                StrongStockSourceStatus(
                    source="基金定期报告",
                    status="stale",
                    detail=f"尚无已确认的精确实体持有人记录，应有报告期 {expected_period}",
                )
            ],
        )

    def methodology(self) -> EtfRadarMethodologyResponse:
        now = self.clock()
        generated_at = now.isoformat(timespec="seconds")
        return EtfRadarMethodologyResponse(
            generated_at=generated_at,
            trade_date=_latest_weekday(now),
            as_of=generated_at,
            signal_stage="post_close",
            model_version=MODEL_VERSION,
            source_status=[
                StrongStockSourceStatus(
                    source="资金雷达方法定义",
                    status="success",
                    detail="启发式证据模型，非统计概率",
                )
            ],
            pool_version=POOL_VERSION,
            core_pool=list(CORE_ETF_POOL),
            thresholds={"watch": 35, "suspected": 55, "strong": 70},
            factors=[
                EtfRadarFactorDefinition(
                    key="same_time_turnover",
                    name="同刻成交放大",
                    description="当前累计成交额相对过去20日相同时刻中位数",
                    availability="等待分钟基线",
                ),
                EtfRadarFactorDefinition(
                    key="relative_index_return",
                    name="相对指数表现",
                    description="ETF当日收益减对应指数收益",
                    availability="等待指数映射行情",
                ),
                EtfRadarFactorDefinition(
                    key="share_change",
                    name="份额变化",
                    description="交易所披露总份额的日变化",
                    availability="盘后可用",
                ),
                EtfRadarFactorDefinition(
                    key="estimated_subscription",
                    name="估算净申购金额",
                    description="份额变化乘当日价格，仅代表规模代理",
                    availability="盘后可用",
                ),
            ],
            limitations=[
                "证据强度是启发式分数，不是国家队介入概率。",
                "深交所历史份额从本服务上线后逐日归档，不向前填充。",
                "当前行情源没有逐笔主动买卖和超大单等级。",
                "ETF申购不能直接识别具体投资者身份。",
            ],
        )

    def _margin_summary(
        self, trade_date: str
    ) -> tuple[MarginSummary, list[StrongStockSourceStatus]]:
        history = self.store.load_margin_history()
        current_rows = [row for row in history if row.trade_date == trade_date]
        statuses: list[StrongStockSourceStatus] = []
        if not current_rows:
            current_result = self.provider.get_margin_rows(trade_date)
            current_rows = current_result.rows
            history = _merge_margin_history(history, current_rows)
            statuses.extend(current_result.source_status)

        previous_date = _previous_weekday(trade_date)
        previous_rows = [row for row in history if row.trade_date == previous_date]
        if not previous_rows:
            previous_result = self.provider.get_margin_rows(previous_date)
            previous_rows = previous_result.rows
            history = _merge_margin_history(history, previous_rows)
            statuses.extend(previous_result.source_status)
        self.store.save_margin_history(history)

        current_balance = _sum_optional(row.margin_balance_cny for row in current_rows)
        comparable_markets = {row.market for row in current_rows} & {
            row.market for row in previous_rows
        }
        comparable_current_balance = _sum_optional(
            row.margin_balance_cny for row in current_rows if row.market in comparable_markets
        )
        comparable_previous_balance = _sum_optional(
            row.margin_balance_cny for row in previous_rows if row.market in comparable_markets
        )
        change = (
            comparable_current_balance - comparable_previous_balance
            if comparable_current_balance is not None and comparable_previous_balance is not None
            else None
        )
        change_pct = (
            change / comparable_previous_balance * 100
            if change is not None and comparable_previous_balance not in {None, 0}
            else None
        )
        return (
            MarginSummary(
                balance_cny=current_balance,
                financing_balance_cny=_sum_optional(
                    row.financing_balance_cny for row in current_rows
                ),
                securities_lending_balance_cny=_sum_optional(
                    row.securities_lending_balance_cny for row in current_rows
                ),
                financing_buy_cny=_sum_optional(row.financing_buy_cny for row in current_rows),
                change_cny=change,
                change_pct=change_pct,
                available_markets=len({row.market for row in current_rows}),
            ),
            statuses,
        )

    def _quote_closes(self, symbols: list[str]) -> dict[str, float]:
        if self.quote_provider is None:
            return {}
        try:
            quotes = self.quote_provider.get_quotes(symbols)
        except Exception:
            return {}
        output: dict[str, float] = {}
        for quote in quotes:
            symbol = getattr(quote, "symbol", None)
            price = getattr(quote, "last_price", None)
            if isinstance(symbol, str) and isinstance(price, (int, float)) and price > 0:
                output[symbol] = float(price)
        return output

    @staticmethod
    def _empty_overview(
        now: datetime,
        trade_date: str,
        source_status: list[StrongStockSourceStatus],
    ) -> EtfRadarOverviewResponse:
        generated_at = now.isoformat(timespec="seconds")
        return EtfRadarOverviewResponse(
            generated_at=generated_at,
            trade_date=trade_date,
            as_of=generated_at,
            signal_stage=_signal_stage(now, trade_date),
            model_version=MODEL_VERSION,
            source_status=source_status,
        )


def build_share_change(
    *,
    current_shares: float,
    previous_shares: float | None,
    close: float | None,
) -> EtfShareChange:
    if previous_shares is None:
        return EtfShareChange()
    share_change = current_shares - previous_shares
    return EtfShareChange(
        share_change=share_change,
        estimated_subscription_cny=(share_change * close if close is not None else None),
    )


def robust_z_score(value: float | None, history: list[float]) -> float | None:
    if value is None or len(history) < 3:
        return None
    median = statistics.median(history)
    mad = statistics.median(abs(item - median) for item in history)
    if mad == 0:
        return None
    return (value - median) / (1.4826 * mad)


def synchronization_ratio(values: Iterable[bool | None]) -> EtfSynchronization:
    valid_values = [value for value in values if value is not None]
    positive_count = sum(value is True for value in valid_values)
    return EtfSynchronization(
        positive_count=positive_count,
        valid_count=len(valid_values),
        ratio=(positive_count / len(valid_values) if valid_values else None),
    )


def _latest_weekday(now: datetime) -> str:
    value = now.date()
    while value.weekday() >= 5:
        value -= timedelta(days=1)
    return value.isoformat()


def _expected_holder_period(now: datetime) -> str:
    year = now.year
    if now.month >= 9:
        return f"{year}-06-30"
    if now.month >= 4:
        return f"{year - 1}-12-31"
    return f"{year - 1}-06-30"


def _previous_weekday(trade_date: str) -> str:
    value = datetime.strptime(trade_date, "%Y-%m-%d").date() - timedelta(days=1)
    while value.weekday() >= 5:
        value -= timedelta(days=1)
    return value.isoformat()


def _signal_stage(now: datetime, trade_date: str) -> str:
    if trade_date == now.date().isoformat() and now.hour < 16:
        return "intraday"
    return "post_close"


def _is_fresh(generated_at: str, now: datetime, ttl_seconds: int) -> bool:
    try:
        parsed = datetime.fromisoformat(generated_at)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=now.tzinfo)
        return 0 <= (now - parsed).total_seconds() <= ttl_seconds
    except ValueError:
        return False


def _latest_share_before(
    history: list[EtfSharePoint], trade_date: str
) -> dict[str, EtfSharePoint]:
    output: dict[str, EtfSharePoint] = {}
    for row in sorted(history, key=lambda item: item.trade_date):
        if row.trade_date < trade_date:
            output[row.symbol] = row
    return output


def _merge_share_history(
    history: list[EtfSharePoint], rows: list[EtfSharePoint]
) -> list[EtfSharePoint]:
    merged = {(row.trade_date, row.symbol): row for row in history}
    merged.update({(row.trade_date, row.symbol): row for row in rows})
    return sorted(merged.values(), key=lambda row: (row.trade_date, row.symbol))


def _merge_margin_history(
    history: list[MarginMarketPoint], rows: list[MarginMarketPoint]
) -> list[MarginMarketPoint]:
    merged = {(row.trade_date, row.market): row for row in history}
    merged.update({(row.trade_date, row.market): row for row in rows})
    return sorted(merged.values(), key=lambda row: (row.trade_date, row.market))


def _radar_item(row: EtfSharePoint) -> EtfRadarItem:
    default_name, index_name = CORE_ETF_POOL.get(row.symbol, (row.symbol, "未映射指数"))
    evidence: list[str] = []
    if row.estimated_subscription_cny is not None:
        direction = "净申购" if row.estimated_subscription_cny > 0 else "净赎回"
        evidence.append(f"估算{direction} {_format_cny(abs(row.estimated_subscription_cny))}")
    if row.robust_score is not None:
        evidence.append(f"稳健标准分 {row.robust_score:+.2f}")
    return EtfRadarItem(
        symbol=row.symbol,
        name=row.name or default_name,
        index_name=index_name,
        total_shares=row.total_shares,
        share_change=row.share_change,
        estimated_subscription_cny=row.estimated_subscription_cny,
        robust_score=row.robust_score,
        evidence_strength=_item_evidence_strength(row),
        evidence=evidence,
    )


def _item_evidence_strength(row: EtfSharePoint) -> float | None:
    scores: list[float] = []
    if row.share_change is not None:
        scores.append(75 if row.share_change > 0 else 25 if row.share_change < 0 else 50)
    if row.robust_score is not None:
        scores.append(max(0, min(100, 50 + row.robust_score * 12.5)))
    return round(statistics.mean(scores), 1) if scores else None


def _radar_summary(items: list[EtfRadarItem]) -> EtfRadarSummary:
    synchronization = synchronization_ratio(
        item.share_change > 0 if item.share_change is not None else None for item in items
    )
    robust_values = [item.robust_score for item in items if item.robust_score is not None]
    scores: list[float] = []
    if synchronization.ratio is not None:
        scores.append(synchronization.ratio * 100)
    if robust_values:
        scores.append(max(0, min(100, 50 + statistics.median(robust_values) * 12.5)))
    strength = round(statistics.mean(scores), 1) if scores else None
    amounts = [
        item.estimated_subscription_cny
        for item in items
        if item.estimated_subscription_cny is not None
    ]
    total_amount = sum(amounts) if amounts else None
    evidence: list[str] = []
    if synchronization.valid_count:
        evidence.append(
            f"{synchronization.positive_count}/{synchronization.valid_count} 只有效ETF份额增加"
        )
    if total_amount is not None:
        direction = "净申购" if total_amount > 0 else "净赎回"
        evidence.append(f"合计估算{direction} {_format_cny(abs(total_amount))}")
    if robust_values:
        evidence.append(f"份额金额中位标准分 {statistics.median(robust_values):+.2f}")
    return EtfRadarSummary(
        evidence_strength=strength,
        evidence_level=_evidence_level(strength),
        valid_etf_count=synchronization.valid_count,
        expected_etf_count=len(CORE_ETF_POOL),
        estimated_subscription_cny=total_amount,
        evidence=evidence,
    )


def _evidence_level(strength: float | None) -> str | None:
    if strength is None:
        return None
    if strength >= 70:
        return "较强"
    if strength >= 55:
        return "疑似"
    if strength >= 35:
        return "观察"
    return "常规"


def _sum_optional(values: Iterable[float | None]) -> float | None:
    available = [value for value in values if value is not None]
    return sum(available) if available else None


def _format_cny(value: float) -> str:
    if value >= 100_000_000:
        return f"{value / 100_000_000:.1f}亿"
    if value >= 10_000:
        return f"{value / 10_000:.0f}万"
    return f"{value:.0f}元"
