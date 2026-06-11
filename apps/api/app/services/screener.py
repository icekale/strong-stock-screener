from __future__ import annotations

from typing import Protocol

from app.models import (
    KlineBar,
    StrongStockCandidate,
    StrongStockDataUnavailable,
    StrongStockRiskItem,
    StrongStockScreeningItem,
    StrongStockScreeningResult,
    StrongStockSourceStatus,
)
from app.providers.watchlist import WatchlistSnapshot
from app.rules import analyze_screening_item, analyze_watchlist_risk


class CandidateProvider(Protocol):
    source_name: str

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        ...


class KlineProvider(Protocol):
    source_name: str

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        ...


class StrongStockScreener:
    def __init__(
        self,
        candidate_provider: CandidateProvider,
        kline_provider: KlineProvider,
    ) -> None:
        self.candidate_provider = candidate_provider
        self.kline_provider = kline_provider

    def screen(
        self,
        trade_date: str,
        limit: int,
        watchlist_snapshot: WatchlistSnapshot | None = None,
    ) -> StrongStockScreeningResult:
        candidates = self.candidate_provider.get_candidates(trade_date)
        if not candidates:
            raise StrongStockDataUnavailable("20日内涨停候选池为空")

        source_status = [
            StrongStockSourceStatus(
                source=self.candidate_provider.source_name,
                status="success",
                detail=f"返回 {len(candidates)} 只 20 日涨停候选",
            )
        ]
        items: list[StrongStockScreeningItem] = []
        failures = 0
        for candidate in candidates:
            try:
                bars = self.kline_provider.get_klines(candidate.symbol, count=220)
            except Exception:
                failures += 1
                continue
            item = analyze_screening_item(candidate, bars, trade_date=trade_date)
            if item.status != "data_incomplete":
                items.append(item)

        if failures:
            source_status.append(
                StrongStockSourceStatus(
                    source=self.kline_provider.source_name,
                    status="failed",
                    detail=f"{failures} 只股票K线获取失败",
                )
            )
        else:
            source_status.append(
                StrongStockSourceStatus(
                    source=self.kline_provider.source_name,
                    status="success",
                    detail="候选股K线获取完成",
                )
            )

        ranked = sorted(items, key=lambda item: (item.status == "focus", item.score), reverse=True)[:limit]
        return StrongStockScreeningResult(
            trade_date=trade_date,
            source_status=source_status,
            items=ranked,
            watchlist_risk_items=self._watchlist_risks(watchlist_snapshot, trade_date),
        )

    def _watchlist_risks(
        self,
        watchlist_snapshot: WatchlistSnapshot | None,
        trade_date: str,
    ) -> list[StrongStockRiskItem]:
        if watchlist_snapshot is None:
            return []
        risks: list[StrongStockRiskItem] = []
        for item in watchlist_snapshot.items:
            try:
                bars = self.kline_provider.get_klines(item.symbol, count=220)
            except Exception:
                continue
            risks.append(
                analyze_watchlist_risk(
                    StrongStockCandidate(symbol=item.symbol, name=item.name or item.symbol),
                    bars,
                    trade_date=trade_date,
                )
            )
        return risks

