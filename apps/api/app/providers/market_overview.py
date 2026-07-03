from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.models import (
    MarketAdvanceDeclineSummary,
    MarketEmotionBucket,
    MarketIndexSnapshot,
    MarketOverviewResponse,
    MarketRankingItem,
    MarketRankingsResponse,
    MarketSectorStrengthItem,
    MarketTurnoverSummary,
    SectorRadarItem,
    SectorRadarResponse,
    StrongStockSourceStatus,
)


INDEX_SECIDS = ("1.000001", "0.399001", "0.899050")
DISPLAY_INDEX_SECIDS = ("1.000001", "0.399001", "0.399006", "1.000688")
DISPLAY_INDEX_SYMBOLS = ["000001.SH", "399001.SZ", "399006.SZ", "000688.SH"]
TICKFLOW_INDEX_SYMBOLS = ["000001.SH", "399001.SZ", "899050.BJ"]
IFIND_AGGREGATE_INDEX_SYMBOLS = {"000001.SH", "399001.SZ", "899050.BJ"}
IFIND_INDEX_SYMBOLS = "000001.SH,399001.SZ,899050.BJ,399006.SZ,000688.SH"
IFIND_INDEX_INDICATORS = "最新价,涨跌幅,成交额,上涨家数,下跌家数"
TICKFLOW_A_SHARE_UNIVERSE = "CN_Equity_A"
DISPLAY_INDEX_NAMES = {
    "000001.SH": "上证",
    "399001.SZ": "深证",
    "399006.SZ": "创业板",
    "000688.SH": "科创50",
}
A_SHARE_STOCK_LIST_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
THS_INDUSTRIES_URL = "https://files.688798.xyz/ths/industries.json"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class EastmoneyMarketOverviewProvider:
    source_name = "东方财富全市场"

    def __init__(
        self,
        timeout_seconds: float = 12,
        http_client: object | None = None,
        realtime_quote_provider: object | None = None,
        ifind_index_provider: object | None = None,
        ifind_stock_provider: object | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.realtime_quote_provider = realtime_quote_provider
        self.ifind_index_provider = ifind_index_provider
        self.ifind_stock_provider = ifind_stock_provider
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client()
        self._a_share_realtime_rows_cache: list[dict[str, Any]] | None = None
        self._ths_industry_map_cache: dict[str, str] | None = None

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    def get_overview(self) -> MarketOverviewResponse:
        source_status: list[StrongStockSourceStatus] = []
        trade_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        eastmoney_trade_date = trade_date.replace("-", "")
        turnover = MarketTurnoverSummary()
        advance_decline = MarketAdvanceDeclineSummary()
        indices: list[MarketIndexSnapshot] = []
        sectors: list[MarketSectorStrengthItem] = []

        if self.ifind_index_provider is None:
            source_status.append(
                StrongStockSourceStatus(
                    source="iFinD 实时指数",
                    status="disabled",
                    detail="未配置 iFinD 指数源，实时市场概览使用备用源",
                )
            )
        else:
            try:
                ifind = self._fetch_ifind_realtime_overview()
                turnover.total_cny = round(ifind["total_cny"], 2)
                indices = ifind.get("indices", [])
                advance_decline = MarketAdvanceDeclineSummary(
                    advance_count=ifind.get("advance_count"),
                    decline_count=ifind.get("decline_count"),
                )
                if ifind.get("trade_date"):
                    trade_date = str(ifind["trade_date"])
                source_status.append(
                    StrongStockSourceStatus(
                        source="iFinD 实时指数",
                        status="success",
                        detail=f"index_highfreq_quotes 返回 {ifind['quote_count']} 个指数",
                    )
                )
            except Exception as exc:
                source_status.append(
                    StrongStockSourceStatus(
                        source="iFinD 实时指数",
                        status="failed",
                        detail=f"实时指数获取失败: {exc.__class__.__name__}; fallback 到 TickFlow",
                    )
                )

        if turnover.total_cny is not None:
            pass
        elif self.realtime_quote_provider is None:
            source_status.append(
                StrongStockSourceStatus(
                    source="TickFlow 实时指数",
                    status="disabled",
                    detail="未配置实时行情源，今日成交额使用 fallback",
                )
            )
        else:
            try:
                tickflow = self._fetch_tickflow_realtime_turnover()
                turnover.total_cny = round(tickflow["total_cny"], 2)
                if tickflow.get("trade_date"):
                    trade_date = str(tickflow["trade_date"])
                source_status.append(
                    StrongStockSourceStatus(
                        source="TickFlow 实时指数",
                        status="success",
                        detail=f"沪深北指数实时成交额，返回 {tickflow['quote_count']} 个指数",
                    )
                )
            except Exception as exc:
                source_status.append(
                    StrongStockSourceStatus(
                        source="TickFlow 实时指数",
                        status="failed",
                        detail=f"实时成交额获取失败: {exc.__class__.__name__}; fallback 到东方财富",
                    )
                )

        try:
            index_rows = self._fetch_index_snapshot()
            if turnover.total_cny is None:
                turnover.total_cny = round(sum(_number(row.get("f6")) or 0 for row in index_rows), 2)
                index_detail = "沪深北指数成交额与上涨/下跌/平盘家数，fallback 今日成交额"
            elif advance_decline.advance_count is not None and advance_decline.decline_count is not None:
                index_detail = "iFinD 已提供实时涨跌家数，东方财富仅作兜底校验"
            else:
                index_detail = "沪深北指数上涨/下跌/平盘家数，今日成交额由实时源提供"
            if advance_decline.advance_count is None or advance_decline.decline_count is None:
                advance_decline = MarketAdvanceDeclineSummary(
                    advance_count=sum(_integer(row.get("f104")) or 0 for row in index_rows),
                    decline_count=sum(_integer(row.get("f105")) or 0 for row in index_rows),
                    unchanged_count=sum(_integer(row.get("f106")) or 0 for row in index_rows),
                )
            elif advance_decline.unchanged_count is None:
                advance_decline.unchanged_count = sum(_integer(row.get("f106")) or 0 for row in index_rows)
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富全A指数",
                    status="success",
                    detail=index_detail,
                )
            )
        except Exception as exc:
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富全A指数",
                    status="failed",
                    detail=f"指数快照获取失败: {exc.__class__.__name__}",
                )
            )

        try:
            if not indices:
                try:
                    indices = self._fetch_tickflow_display_indices()
                    source_status.append(
                        StrongStockSourceStatus(
                            source="TickFlow 指数展示",
                            status="success",
                            detail=f"返回 {len(indices)} 个顶部指数展示项",
                        )
                    )
                except Exception as tickflow_exc:
                    source_status.append(
                        StrongStockSourceStatus(
                            source="TickFlow 指数展示",
                            status="failed" if self.realtime_quote_provider is not None else "disabled",
                            detail=f"顶部指数展示获取失败: {tickflow_exc.__class__.__name__}; fallback 到东方财富",
                        )
                    )
                    indices = self._fetch_display_index_snapshot()
                    source_status.append(
                        StrongStockSourceStatus(
                            source="东方财富指数展示",
                            status="success",
                            detail=f"返回 {len(indices)} 个顶部指数展示项",
                        )
                    )
        except Exception as exc:
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富指数展示",
                    status="failed",
                    detail=f"顶部指数展示获取失败: {exc.__class__.__name__}",
                )
            )

        try:
            history = self._fetch_index_amount_history()
            if history["trade_date"]:
                trade_date = str(history["trade_date"])
                eastmoney_trade_date = trade_date.replace("-", "")
            previous_total = _number(history.get("previous_total_cny"))
            if previous_total is not None:
                turnover.previous_total_cny = round(previous_total, 2)
            if turnover.total_cny is not None and turnover.previous_total_cny:
                turnover.change_cny = round(turnover.total_cny - turnover.previous_total_cny, 2)
                turnover.change_pct = round(
                    turnover.change_cny / turnover.previous_total_cny * 100,
                    2,
                )
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富指数日K",
                    status="success",
                    detail="沪深北指数日K成交额用于昨日对比",
                )
            )
        except Exception as exc:
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富指数日K",
                    status="failed",
                    detail=f"昨日成交额获取失败: {exc.__class__.__name__}",
                )
            )

        try:
            sectors = self._fetch_sector_strength(limit=20)
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富行业板块",
                    status="success",
                    detail=f"返回 {len(sectors)} 个全市场板块",
                )
            )
        except Exception as exc:
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富行业板块",
                    status="failed",
                    detail=f"板块强度获取失败: {exc.__class__.__name__}",
                )
            )

        try:
            limit_down_count = self._fetch_direct_limit_down_count(eastmoney_trade_date)
            advance_decline.limit_down_count = limit_down_count
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富跌停池",
                    status="success",
                    detail=f"直接跌停池返回，跌停 {limit_down_count} 只",
                )
            )
        except Exception as exc:
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富跌停池",
                    status="failed",
                    detail=f"直接跌停池获取失败: {exc.__class__.__name__}; fallback 到全A实时涨跌幅估算",
                )
            )
            try:
                limit_down_count = self._fetch_limit_down_count_from_realtime_rows()
                advance_decline.limit_down_count = limit_down_count
                source_status.append(
                    StrongStockSourceStatus(
                        source="东方财富全A跌停估算",
                        status="success",
                        detail=f"基于全A实时涨跌幅按交易所规则估算，跌停 {limit_down_count} 只",
                    )
                )
            except Exception as fallback_exc:
                source_status.append(
                    StrongStockSourceStatus(
                        source="东方财富全A跌停估算",
                        status="failed",
                        detail=f"跌停家数估算失败: {fallback_exc.__class__.__name__}",
                    )
                )

        return MarketOverviewResponse(
            trade_date=trade_date,
            turnover=turnover,
            advance_decline=advance_decline,
            indices=indices,
            sectors=sectors,
            source_status=source_status,
        )

    def get_sector_radar(self, limit: int = 20) -> SectorRadarResponse:
        bounded_limit = max(1, min(limit, 50))
        source_status: list[StrongStockSourceStatus] = []
        trade_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        try:
            inflow = self._fetch_sector_capital_flow(limit=bounded_limit, direction="inflow")
            outflow = self._fetch_sector_capital_flow(limit=bounded_limit, direction="outflow")
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富行业板块资金流",
                    status="success",
                    detail=f"返回净流入 {len(inflow)} 个 / 净流出 {len(outflow)} 个板块",
                )
            )
            return SectorRadarResponse(
                trade_date=trade_date,
                capital_flow_status="direct",
                flow_source="东方财富行业板块资金净额",
                inflow=inflow,
                outflow=outflow,
                source_status=source_status,
            )
        except Exception as exc:
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富行业板块资金流",
                    status="failed",
                    detail=f"资金净额获取失败: {exc.__class__.__name__}; fallback 到涨跌额估算",
                )
            )
            overview = self.get_overview()
            items = [_sector_radar_item(sector) for sector in overview.sectors if sector.turnover_cny is not None]
            inflow = sorted(
                [item for item in items if item.net_flow_cny is not None and item.net_flow_cny > 0],
                key=lambda item: item.net_flow_cny or 0,
                reverse=True,
            )[:bounded_limit]
            outflow = sorted(
                [item for item in items if item.net_flow_cny is not None and item.net_flow_cny < 0],
                key=lambda item: item.net_flow_cny or 0,
            )[:bounded_limit]
            return SectorRadarResponse(
                trade_date=overview.trade_date,
                capital_flow_status="estimated",
                flow_source="东方财富行业板块涨跌额估算",
                inflow=inflow,
                outflow=outflow,
                source_status=[*source_status, *overview.source_status],
            )

    def get_pct_change_distribution(self) -> tuple[list[MarketEmotionBucket], StrongStockSourceStatus]:
        tickflow_error: str | None = None
        if self.realtime_quote_provider is not None:
            try:
                rankings = self.get_market_rankings(limit=1)
                return rankings.buckets, StrongStockSourceStatus(
                    source="TickFlow 全A实时涨跌幅",
                    status="success",
                    detail=f"全A实时行情返回 {sum(bucket.count or 0 for bucket in rankings.buckets)} 只股票",
                )
            except Exception as exc:
                tickflow_error = exc.__class__.__name__
        try:
            rows = self._fetch_a_share_realtime_rows()
            buckets = _pct_change_buckets([_number(row.get("f3")) for row in rows])
            fallback_prefix = f"TickFlow失败: {tickflow_error}; fallback 到" if tickflow_error else ""
            return buckets, StrongStockSourceStatus(
                source="东方财富全A实时涨跌幅",
                status="success",
                detail=f"{fallback_prefix}全A实时列表返回 {sum(bucket.count or 0 for bucket in buckets)} 只股票",
            )
        except Exception as exc:
            return _pct_change_buckets([]), StrongStockSourceStatus(
                source="东方财富全A实时涨跌幅",
                status="failed",
                detail=f"全A涨跌幅分布获取失败: {exc.__class__.__name__}",
            )

    def get_market_rankings(self, limit: int = 50, batch_size: int = 200) -> MarketRankingsResponse:
        if self.realtime_quote_provider is None:
            return MarketRankingsResponse(
                source_status=[
                    StrongStockSourceStatus(
                        source="TickFlow 全A实时行情",
                        status="disabled",
                        detail="未配置 TickFlow 实时行情源，无法生成全A排行榜",
                    )
                ]
            )

        bounded_limit = max(1, min(limit, 100))
        bounded_batch_size = max(1, min(batch_size, 500))
        source_status: list[StrongStockSourceStatus] = []
        quotes: list[object] = []
        tickflow_batch_count: int | None = None
        tickflow_universe_error: Exception | None = None
        if hasattr(self.realtime_quote_provider, "get_quotes_by_universe"):
            try:
                quotes = self.realtime_quote_provider.get_quotes_by_universe(TICKFLOW_A_SHARE_UNIVERSE)
                source_status.append(
                    StrongStockSourceStatus(
                        source="TickFlow 全A标的池",
                        status="success",
                        detail=f"{TICKFLOW_A_SHARE_UNIVERSE} 标的池直接返回 {len(quotes)} 条实时行情",
                    )
                )
            except Exception as exc:
                tickflow_universe_error = exc
                source_status.append(
                    StrongStockSourceStatus(
                        source="TickFlow 全A标的池",
                        status="failed",
                        detail=f"标的池请求失败: {exc}; fallback 到东方财富股票池分批查询",
                    )
                )

        if not quotes:
            rows = self._fetch_a_share_realtime_rows()
            symbols = _dedupe_symbols(_eastmoney_stock_symbol(row.get("f12")) for row in rows)
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富全A股票池",
                    status="success",
                    detail=f"股票池返回 {len(symbols)} 个标的，用于 TickFlow 批量实时行情查询",
                )
            )
            if not symbols:
                raise ValueError("empty a-share stock symbols")

            tickflow_batch_count = len(range(0, len(symbols), bounded_batch_size))
            for start in range(0, len(symbols), bounded_batch_size):
                batch = symbols[start : start + bounded_batch_size]
                quotes.extend(self.realtime_quote_provider.get_quotes(batch))

        industry_by_symbol = self._a_share_industry_by_symbol()
        items = [
            _ranking_item_from_quote(quote).model_copy(
                update={"industry": industry_by_symbol.get(str(getattr(quote, "symbol", "") or "").strip().upper())}
            )
            for quote in quotes
        ]
        items = [item for item in items if item.symbol]
        if not items:
            if tickflow_universe_error is not None:
                raise ValueError(f"empty tickflow full-a quotes after universe fallback: {tickflow_universe_error}")
            raise ValueError("empty tickflow full-a quotes")
        pct_values = [item.pct_change for item in items]
        buckets = _pct_change_buckets(pct_values, source="TickFlow 全A实时行情")
        trade_dates = [
            date
            for date in (_date_from_quote_time(item.quote_time) for item in items)
            if date
        ]
        source_status.append(
            StrongStockSourceStatus(
                source="TickFlow 全A实时行情",
                status="success",
                detail=_tickflow_rankings_status_detail(
                    item_count=len(items),
                    used_universe=any(status.source == "TickFlow 全A标的池" and status.status == "success" for status in source_status),
                    batch_count=tickflow_batch_count,
                ),
            )
        )
        pct_change_rank = sorted(
            [item for item in items if item.pct_change is not None],
            key=lambda item: (item.pct_change or -999, item.turnover_cny or 0, item.symbol),
            reverse=True,
        )[:bounded_limit]
        turnover_rank = sorted(
            [item for item in items if item.turnover_cny is not None],
            key=lambda item: (item.turnover_cny or 0, item.pct_change or -999, item.symbol),
            reverse=True,
        )[:bounded_limit]
        supplemental_status = self._supplement_rank_industries(pct_change_rank, turnover_rank)
        if supplemental_status is not None:
            source_status.append(supplemental_status)
        return MarketRankingsResponse(
            trade_date=max(trade_dates) if trade_dates else None,
            pct_change_rank=pct_change_rank,
            turnover_rank=turnover_rank,
            buckets=buckets,
            source_status=source_status,
        )

    def _supplement_rank_industries(
        self,
        pct_change_rank: list[MarketRankingItem],
        turnover_rank: list[MarketRankingItem],
    ) -> StrongStockSourceStatus | None:
        missing_symbols = _dedupe_symbols(
            item.symbol
            for item in [*pct_change_rank, *turnover_rank]
            if item.symbol and not item.industry
        )
        if not missing_symbols:
            return None
        try:
            industry_by_symbol = self._fetch_stock_industries_by_symbols(missing_symbols)
        except Exception:
            industry_by_symbol = {}
        patched = _patch_rank_industries(pct_change_rank, turnover_rank, industry_by_symbol)
        if patched:
            return StrongStockSourceStatus(
                source="东方财富行业补充",
                status="success",
                detail=f"补齐 {patched}/{len(missing_symbols)} 只排行股票行业",
            )

        try:
            industry_by_symbol = self._fetch_ths_industries_by_symbols(missing_symbols)
        except Exception:
            industry_by_symbol = {}
        patched = _patch_rank_industries(pct_change_rank, turnover_rank, industry_by_symbol)
        if patched:
            return StrongStockSourceStatus(
                source="同花顺行业分类参考",
                status="success",
                detail=f"补齐 {patched}/{len(missing_symbols)} 只排行股票行业",
            )

        missing_symbols = _dedupe_symbols(
            item.symbol
            for item in [*pct_change_rank, *turnover_rank]
            if item.symbol and not item.industry
        )
        if self.ifind_stock_provider is None or not hasattr(self.ifind_stock_provider, "get_stock_industries"):
            return StrongStockSourceStatus(
                source="iFinD 行业补充",
                status="disabled",
                detail=f"{len(missing_symbols)} 只排行股票缺少行业，未配置 iFinD 行业补充源",
            )
        try:
            industry_by_symbol = self.ifind_stock_provider.get_stock_industries(missing_symbols)
        except Exception as exc:
            return StrongStockSourceStatus(
                source="iFinD 行业补充",
                status="failed",
                detail=f"{len(missing_symbols)} 只排行股票缺少行业，补充失败: {exc.__class__.__name__}",
            )
        unique_patched = _patch_rank_industries(pct_change_rank, turnover_rank, industry_by_symbol)
        return StrongStockSourceStatus(
            source="iFinD 行业补充",
            status="success" if unique_patched else "stale",
            detail=f"补齐 {unique_patched}/{len(missing_symbols)} 只排行股票行业",
        )

    def get_stock_industries(self, symbols: list[str]) -> dict[str, str]:
        missing_symbols = _dedupe_symbols(symbols)
        output: dict[str, str] = {}
        if not missing_symbols:
            return output

        try:
            output.update(self._fetch_stock_industries_by_symbols(missing_symbols))
        except Exception:
            pass
        missing_symbols = [symbol for symbol in missing_symbols if symbol not in output]
        if not missing_symbols:
            return output

        try:
            output.update(self._fetch_ths_industries_by_symbols(missing_symbols))
        except Exception:
            pass
        missing_symbols = [symbol for symbol in missing_symbols if symbol not in output]
        if (
            missing_symbols
            and self.ifind_stock_provider is not None
            and hasattr(self.ifind_stock_provider, "get_stock_industries")
        ):
            try:
                output.update(self.ifind_stock_provider.get_stock_industries(missing_symbols))
            except Exception:
                pass
        return output

    def _fetch_stock_industries_by_symbols(self, symbols: list[str], batch_size: int = 100) -> dict[str, str]:
        output: dict[str, str] = {}
        bounded_batch_size = max(1, min(batch_size, 100))
        for start in range(0, len(symbols), bounded_batch_size):
            batch = symbols[start : start + bounded_batch_size]
            secids = [_eastmoney_stock_secid(symbol) for symbol in batch]
            secids = [secid for secid in secids if secid]
            if not secids:
                continue
            response = self.http_client.get(
                "https://push2.eastmoney.com/api/qt/ulist.np/get",
                params={
                    "secids": ",".join(secids),
                    "fields": "f12,f14,f100",
                },
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            for row in _extract_diff(response.json()):
                symbol = _eastmoney_stock_symbol(row.get("f12"))
                industry = _text(row.get("f100"))
                if symbol and industry:
                    output[symbol] = industry
        return output

    def _fetch_ths_industries_by_symbols(self, symbols: list[str]) -> dict[str, str]:
        if self._ths_industry_map_cache is None:
            response = self.http_client.get(
                THS_INDUSTRIES_URL,
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("invalid ths industries payload")
            mapping: dict[str, str] = {}
            for row in payload:
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("symbol") or "").strip().upper()
                industries = row.get("industries")
                if not symbol or not isinstance(industries, list):
                    continue
                names = [_text(item) for item in industries]
                names = [name for name in names if name]
                if names:
                    mapping[symbol] = names[1] if len(names) > 1 else names[0]
            self._ths_industry_map_cache = mapping
        return {
            symbol: self._ths_industry_map_cache[symbol]
            for symbol in _dedupe_symbols(symbols)
            if symbol in self._ths_industry_map_cache
        }

    def _fetch_direct_limit_down_count(self, date: str) -> int:
        response = self.http_client.get(
            "https://push2ex.eastmoney.com/getTopicDTPool",
            params={
                "ut": "7eea3edcaed734bea9cbfc24409ed989",
                "dpt": "wz.ztzt",
                "Pageindex": "0",
                "pagesize": "10000",
                "sort": "fund:asc",
                "date": date,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        rows = _extract_pool_rows(response.json())
        return len(rows)

    def _fetch_limit_down_count_from_realtime_rows(self) -> int:
        rows = self._fetch_a_share_realtime_rows()
        return sum(1 for row in rows if _is_limit_down_row(row))

    def _fetch_ifind_realtime_overview(self) -> dict[str, Any]:
        payload = self.ifind_index_provider.call_tool(
            "hexin-ifind-ds-index-mcp",
            "index_highfreq_quotes",
            {
                "symbols": IFIND_INDEX_SYMBOLS,
                "indicators": IFIND_INDEX_INDICATORS,
                "data_mode": "real_time",
            },
        )
        rows = _ifind_table_rows(payload)
        if not rows:
            raise ValueError("empty ifind index rows")

        total = 0.0
        advance_count = 0
        decline_count = 0
        has_advance = False
        has_decline = False
        trade_dates: list[str] = []
        indices_by_symbol: dict[str, MarketIndexSnapshot] = {}
        for row in rows:
            symbol = _text(row.get("证券代码"))
            if symbol in DISPLAY_INDEX_NAMES:
                indices_by_symbol[symbol] = MarketIndexSnapshot(
                    symbol=symbol,
                    name=DISPLAY_INDEX_NAMES[symbol],
                    last_price=_number(row.get("最新价")),
                    change_pct=_number(row.get("涨跌幅")),
                    turnover_cny=_number(row.get("成交额")),
                    source="iFinD 实时指数",
                )
            amount = _number(row.get("成交额"))
            if amount is not None and symbol in IFIND_AGGREGATE_INDEX_SYMBOLS:
                total += amount
            up_count = _integer(row.get("上涨家数"))
            if up_count is not None and symbol in IFIND_AGGREGATE_INDEX_SYMBOLS:
                advance_count += up_count
                has_advance = True
            down_count = _integer(row.get("下跌家数"))
            if down_count is not None and symbol in IFIND_AGGREGATE_INDEX_SYMBOLS:
                decline_count += down_count
                has_decline = True
            trade_date = _date_from_quote_time(row.get("time"))
            if trade_date:
                trade_dates.append(trade_date)
        if total <= 0:
            raise ValueError("empty ifind amount")
        return {
            "total_cny": total,
            "advance_count": advance_count if has_advance else None,
            "decline_count": decline_count if has_decline else None,
            "trade_date": max(trade_dates) if trade_dates else None,
            "quote_count": len(rows),
            "indices": [
                indices_by_symbol[symbol]
                for symbol in DISPLAY_INDEX_NAMES
                if symbol in indices_by_symbol
            ],
        }

    def _fetch_tickflow_realtime_turnover(self) -> dict[str, Any]:
        quotes = self.realtime_quote_provider.get_quotes(TICKFLOW_INDEX_SYMBOLS)
        aggregate_symbols = set(TICKFLOW_INDEX_SYMBOLS)
        amounts = [
            _number(getattr(quote, "turnover_cny", None))
            for quote in quotes
            if str(getattr(quote, "symbol", "") or "") in aggregate_symbols
        ]
        valid_amounts = [amount for amount in amounts if amount is not None]
        if not valid_amounts:
            raise ValueError("empty tickflow turnover")
        trade_dates = [
            trade_date
            for trade_date in (
                _date_from_quote_time(getattr(quote, "quote_time", None)) for quote in quotes
            )
            if trade_date
        ]
        return {
            "total_cny": sum(valid_amounts),
            "trade_date": max(trade_dates) if trade_dates else None,
            "quote_count": len(valid_amounts),
        }

    def _fetch_tickflow_display_indices(self) -> list[MarketIndexSnapshot]:
        if self.realtime_quote_provider is None:
            raise ValueError("tickflow display index source disabled")
        quotes = self.realtime_quote_provider.get_quotes(DISPLAY_INDEX_SYMBOLS)
        items_by_symbol: dict[str, MarketIndexSnapshot] = {}
        for quote in quotes:
            symbol = str(getattr(quote, "symbol", "") or "")
            if symbol not in DISPLAY_INDEX_NAMES:
                continue
            items_by_symbol[symbol] = MarketIndexSnapshot(
                symbol=symbol,
                name=DISPLAY_INDEX_NAMES[symbol],
                last_price=_number(getattr(quote, "last_price", None)),
                change_pct=_number(getattr(quote, "pct_change", None)),
                turnover_cny=_number(getattr(quote, "turnover_cny", None)),
                source="TickFlow 实时指数",
            )
        if not items_by_symbol:
            raise ValueError("empty tickflow display indices")
        return [
            items_by_symbol[symbol]
            for symbol in DISPLAY_INDEX_SYMBOLS
            if symbol in items_by_symbol
        ]

    def _fetch_index_snapshot(self) -> list[dict[str, Any]]:
        response = self.http_client.get(
            "https://push2.eastmoney.com/api/qt/ulist.np/get",
            params={
                "secids": ",".join(INDEX_SECIDS),
                "fields": "f2,f3,f6,f12,f14,f104,f105,f106",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        rows = _extract_diff(response.json())
        if not rows:
            raise ValueError("empty index snapshot")
        return rows

    def _fetch_display_index_snapshot(self) -> list[MarketIndexSnapshot]:
        response = self.http_client.get(
            "https://push2.eastmoney.com/api/qt/ulist.np/get",
            params={
                "secids": ",".join(DISPLAY_INDEX_SECIDS),
                "fields": "f2,f3,f6,f12,f14",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        rows = _extract_diff(response.json())
        if not rows:
            raise ValueError("empty display index snapshot")
        items_by_symbol: dict[str, MarketIndexSnapshot] = {}
        for row in rows:
            symbol = _eastmoney_index_symbol(row.get("f12"))
            if symbol not in DISPLAY_INDEX_NAMES:
                continue
            items_by_symbol[symbol] = MarketIndexSnapshot(
                symbol=symbol,
                name=DISPLAY_INDEX_NAMES[symbol],
                last_price=_number(row.get("f2")),
                change_pct=_number(row.get("f3")),
                turnover_cny=_number(row.get("f6")),
                source="东方财富指数行情",
            )
        return [
            items_by_symbol[symbol]
            for symbol in DISPLAY_INDEX_NAMES
            if symbol in items_by_symbol
        ]

    def _fetch_index_amount_history(self) -> dict[str, object]:
        latest_total = 0.0
        previous_total = 0.0
        trade_dates: list[str] = []
        for secid in INDEX_SECIDS:
            response = self.http_client.get(
                "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                params={
                    "secid": secid,
                    "klt": "101",
                    "fqt": "1",
                    "lmt": "2",
                    "end": "20500101",
                    "iscca": "1",
                    "fields1": "f1,f2,f3,f4,f5,f6",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                },
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            klines = response.json().get("data", {}).get("klines", [])
            if not isinstance(klines, list) or len(klines) < 2:
                raise ValueError(f"index kline missing: {secid}")
            previous = _parse_kline_amount(str(klines[-2]))
            latest = _parse_kline_amount(str(klines[-1]))
            previous_total += previous["amount"]
            latest_total += latest["amount"]
            trade_dates.append(latest["date"])
        return {
            "trade_date": max(trade_dates) if trade_dates else None,
            "latest_total_cny": latest_total,
            "previous_total_cny": previous_total,
        }

    def _fetch_sector_strength(self, limit: int) -> list[MarketSectorStrengthItem]:
        response = self.http_client.get(
            "https://push2.eastmoney.com/api/qt/clist/get",
            params={
                "pn": "1",
                "pz": str(max(1, min(limit, 50))),
                "po": "1",
                "fid": "f3",
                "np": "1",
                "fltt": "2",
                "invt": "2",
                "fs": "m:90+t:2",
                "fields": "f3,f6,f12,f14,f104,f105,f136,f140",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        rows = _extract_diff(response.json())
        sectors = [
            MarketSectorStrengthItem(
                name=str(row.get("f14") or ""),
                change_pct=_number(row.get("f3")),
                turnover_cny=_number(row.get("f6")),
                advance_count=_integer(row.get("f104")),
                decline_count=_integer(row.get("f105")),
                leader=_text(row.get("f140")),
                source="东方财富行业板块",
            )
            for row in rows
            if row.get("f14")
        ]
        return sorted(
            sectors,
            key=lambda item: (
                item.change_pct if item.change_pct is not None else -999,
                item.turnover_cny if item.turnover_cny is not None else 0,
            ),
            reverse=True,
        )

    def _fetch_a_share_realtime_rows(self) -> list[dict[str, Any]]:
        if self._a_share_realtime_rows_cache is not None:
            return self._a_share_realtime_rows_cache
        rows: list[dict[str, Any]] = []
        total: int | None = None
        page_size = 100
        for page in range(1, 61):
            response = self.http_client.get(
                "https://push2.eastmoney.com/api/qt/clist/get",
                params={
                    "pn": str(page),
                    "pz": str(page_size),
                    "po": "1",
                    "fid": "f3",
                    "np": "1",
                    "fltt": "2",
                    "invt": "2",
                    "fs": A_SHARE_STOCK_LIST_FS,
                    "fields": "f3,f12,f14,f100",
                },
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            if total is None:
                total = _extract_total(payload)
            page_rows = _extract_diff(payload)
            if not page_rows:
                break
            rows.extend(page_rows)
            if total is not None and len(rows) >= total:
                break
        if not rows:
            raise ValueError("empty a-share realtime rows")
        self._a_share_realtime_rows_cache = rows
        return rows

    def _a_share_industry_by_symbol(self) -> dict[str, str]:
        try:
            rows = self._fetch_a_share_realtime_rows()
        except Exception:
            return {}
        output: dict[str, str] = {}
        for row in rows:
            symbol = _eastmoney_stock_symbol(row.get("f12"))
            industry = _text(row.get("f100"))
            if symbol and industry:
                output[symbol] = industry
        return output

    def _fetch_sector_capital_flow(self, limit: int, direction: str) -> list[SectorRadarItem]:
        response = self.http_client.get(
            "https://push2.eastmoney.com/api/qt/clist/get",
            params={
                "pn": "1",
                "pz": str(max(1, min(limit, 50))),
                "po": "1" if direction == "inflow" else "0",
                "fid": "f62",
                "np": "1",
                "fltt": "2",
                "invt": "2",
                "fs": "m:90+t:2",
                "fields": "f3,f6,f12,f14,f62,f184,f104,f105,f140",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        rows = _extract_diff(response.json())
        items = [
            _sector_radar_item(
                MarketSectorStrengthItem(
                    name=str(row.get("f14") or ""),
                    change_pct=_number(row.get("f3")),
                    turnover_cny=_number(row.get("f6")),
                    advance_count=_integer(row.get("f104")),
                    decline_count=_integer(row.get("f105")),
                    leader=_text(row.get("f140")),
                    source="东方财富行业板块资金流",
                ),
                net_flow_cny=_number(row.get("f62")),
            )
            for row in rows
            if row.get("f14")
        ]
        if not items:
            raise ValueError("empty sector capital flow")
        return items


def _extract_diff(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("invalid payload")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("missing data")
    diff = data.get("diff")
    if not isinstance(diff, list):
        raise ValueError("missing diff")
    return [row for row in diff if isinstance(row, dict)]


def _extract_total(payload: object) -> int | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    total = _integer(data.get("total"))
    return total if total and total > 0 else None


def _extract_pool_rows(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("invalid payload")
    data = payload.get("data")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if not isinstance(data, dict):
        raise ValueError("missing data")
    for key in ("pool", "diff", "list"):
        rows = data.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    raise ValueError("missing pool")


def _sector_radar_item(
    sector: MarketSectorStrengthItem,
    net_flow_cny: float | None = None,
) -> SectorRadarItem:
    resolved_net_flow_cny = net_flow_cny
    if resolved_net_flow_cny is None and sector.turnover_cny is not None and sector.change_pct is not None:
        resolved_net_flow_cny = round(sector.turnover_cny * sector.change_pct / 100, 2)

    breadth_score = 0.0
    if sector.advance_count is not None and sector.decline_count is not None:
        total = sector.advance_count + sector.decline_count
        if total > 0:
            breadth_score = (sector.advance_count - sector.decline_count) / total * 10

    turnover_score = min((sector.turnover_cny or 0) / 10_000_000_000, 20)
    change_score = (sector.change_pct or 0) * 10
    return SectorRadarItem(
        name=sector.name,
        source=sector.source,
        change_pct=sector.change_pct,
        turnover_cny=sector.turnover_cny,
        advance_count=sector.advance_count,
        decline_count=sector.decline_count,
        leader=sector.leader,
        net_flow_cny=resolved_net_flow_cny,
        strength_score=round(change_score + breadth_score + turnover_score, 2),
    )


def _pct_change_buckets(
    values: list[float | None],
    source: str = "东方财富全A实时涨跌幅",
) -> list[MarketEmotionBucket]:
    bucket_defs = [
        (">10%", 10.0, None),
        ("7-10%", 7.0, 10.0),
        ("5-7%", 5.0, 7.0),
        ("3-5%", 3.0, 5.0),
        ("0-3%", 0.0, 3.0),
        ("-3-0%", -3.0, 0.0),
        ("-5--3%", -5.0, -3.0),
        ("-7--5%", -7.0, -5.0),
        ("-10--7%", -10.0, -7.0),
        ("<-10%", None, -10.0),
    ]
    buckets = [
        MarketEmotionBucket(
            label=label,
            min_pct=min_pct,
            max_pct=max_pct,
            count=0,
            source=source,
        )
        for label, min_pct, max_pct in bucket_defs
    ]
    for value in values:
        if value is None:
            continue
        for bucket in buckets:
            if _pct_in_bucket(value, bucket.min_pct, bucket.max_pct):
                bucket.count = (bucket.count or 0) + 1
                break
    return buckets


def _pct_in_bucket(value: float, min_pct: float | None, max_pct: float | None) -> bool:
    if min_pct is None:
        return value < (max_pct or 0)
    if max_pct is None:
        return value > min_pct
    return min_pct <= value < max_pct


def _tickflow_rankings_status_detail(
    item_count: int,
    used_universe: bool,
    batch_count: int | None,
) -> str:
    if used_universe:
        return f"标的池 quotes 返回 {item_count} 只股票"
    if batch_count is not None:
        return f"批量 quotes 返回 {item_count} 只股票，批次 {batch_count} 个"
    return f"quotes 返回 {item_count} 只股票"


def _is_limit_down_row(row: dict[str, Any]) -> bool:
    pct_change = _number(row.get("f3"))
    if pct_change is None:
        return False
    code = str(row.get("f12") or "").strip()
    name = str(row.get("f14") or "").strip().upper()
    threshold = _limit_down_threshold_pct(code, name)
    return pct_change <= threshold + 0.05


def _limit_down_threshold_pct(code: str, name: str) -> float:
    if "ST" in name:
        return -5.0
    if code.startswith(("300", "301", "688")):
        return -20.0
    if code.startswith(("8", "4", "920")):
        return -30.0
    return -10.0


def _parse_kline_amount(value: str) -> dict[str, Any]:
    parts = value.split(",")
    if len(parts) < 7:
        raise ValueError("invalid kline row")
    return {"date": parts[0], "amount": float(parts[6])}


def _ifind_table_rows(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        raise ValueError("invalid ifind payload")
    data = payload.get("data")
    if isinstance(data, str):
        data = json.loads(data)
    if isinstance(data, dict) and isinstance(data.get("tables"), list):
        table = data["tables"]
    elif isinstance(data, dict) and isinstance(data.get("text"), str):
        table = _markdown_table(data["text"])
    else:
        raise ValueError("missing ifind tables")
    if not table:
        return []
    header = table[0]
    if not isinstance(header, list):
        raise ValueError("invalid ifind header")
    rows: list[dict[str, object]] = []
    for item in table[1:]:
        if not isinstance(item, list):
            continue
        rows.append({str(header[index]): item[index] for index in range(min(len(header), len(item)))})
    return rows


def _markdown_table(value: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in value.splitlines():
        text = line.strip()
        if not text.startswith("|") or "---" in text:
            continue
        rows.append([cell.strip() for cell in text.strip("|").split("|")])
    return rows


def _date_from_quote_time(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        timestamp = float(text)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, ZoneInfo("Asia/Shanghai")).date().isoformat()
    except ValueError:
        pass
    try:
        normalized = text.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    except ValueError:
        return None


def _number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: object) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _eastmoney_index_symbol(value: object) -> str:
    code = str(value or "").strip()
    if code.startswith("399"):
        return f"{code}.SZ"
    if code:
        return f"{code}.SH"
    return ""


def _eastmoney_stock_symbol(value: object) -> str:
    code = str(value or "").strip()
    if len(code) != 6 or not code.isdigit():
        return ""
    if code.startswith("92"):
        return f"{code}.BJ"
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return ""


def _eastmoney_stock_secid(symbol: object) -> str:
    text = str(symbol or "").strip().upper()
    if "." not in text:
        text = _eastmoney_stock_symbol(text)
    if not text or "." not in text:
        return ""
    code, exchange = text.split(".", 1)
    if len(code) != 6 or not code.isdigit():
        return ""
    if exchange in {"SZ", "BJ"}:
        return f"0.{code}"
    if exchange == "SH":
        return f"1.{code}"
    return ""


def _patch_rank_industries(
    pct_change_rank: list[MarketRankingItem],
    turnover_rank: list[MarketRankingItem],
    industry_by_symbol: dict[str, str],
) -> int:
    patched_symbols: set[str] = set()
    for item in [*pct_change_rank, *turnover_rank]:
        if item.industry:
            continue
        industry = industry_by_symbol.get(item.symbol)
        if industry:
            item.industry = industry
            patched_symbols.add(item.symbol)
    return len(patched_symbols)


def _dedupe_symbols(symbols: object) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        text = str(symbol or "").strip().upper()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _ranking_item_from_quote(quote: object) -> MarketRankingItem:
    pct_change = _number(getattr(quote, "pct_change", None))
    return MarketRankingItem(
        symbol=str(getattr(quote, "symbol", "") or "").strip().upper(),
        name=_text(getattr(quote, "name", None)),
        industry=None,
        last_price=_number(getattr(quote, "last_price", None)),
        pct_change=pct_change,
        current_pct_change=pct_change,
        open_price=_number(getattr(quote, "open_price", None)),
        prev_close=_number(getattr(quote, "prev_close", None)),
        turnover_rate=_number(getattr(quote, "turnover_rate", None)),
        turnover_cny=_number(getattr(quote, "turnover_cny", None)),
        volume=_number(getattr(quote, "volume", None)),
        quote_time=_text(getattr(quote, "quote_time", None)),
    )
