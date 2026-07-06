from pathlib import Path
from datetime import datetime, timedelta
from threading import Event
from time import sleep
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.main import (
    AUCTION_SNAPSHOT_CACHE,
    MARKET_RANKINGS_CACHE,
    SECTOR_INTRADAY_CACHE,
    SECTOR_RADAR_CACHE,
    app,
    _refresh_sector_theme_rows,
    shutdown_auction_sampler,
    shutdown_sector_workbench_sampler,
    startup_auction_sampler,
    startup_sector_workbench_sampler,
)
from app.models import (
    KlineBar,
    MarketAdvanceDeclineSummary,
    MarketIndexSnapshot,
    MarketOverviewResponse,
    MarketRankingItem,
    MarketRankingsResponse,
    MarketSectorStrengthItem,
    MarketTurnoverSummary,
    SectorRadarItem,
    SectorRadarResponse,
    StrongStockCandidate,
    StrongStockDataUnavailable,
    StrongStockSourceStatus,
)
from app.providers.watchlist import WatchlistSnapshot, WatchlistItem
from app.providers.tickflow import TickFlowIntradayBar, TickFlowQuote
from app.services.plate_rotation_reference import PlateRotationReferenceResponse, PlateRotationThemeItem
from app.services.sector_workbench_store import SectorThemeRowsStore
from app.providers.news_risk import NegativeNewsRisk


def _bars(closes: list[float]) -> list[KlineBar]:
    bars: list[KlineBar] = []
    for index, close in enumerate(closes):
        previous = closes[index - 1] if index else close
        open_price = previous * 0.99 if close >= previous else previous * 1.02
        bars.append(
            KlineBar(
                date=f"2026-01-{(index % 28) + 1:02d}",
                open=round(open_price, 2),
                close=round(close, 2),
                high=round(max(open_price, close) * 1.03, 2),
                low=round(min(open_price, close) * 0.98, 2),
                volume=1_000_000 + index * 10_000,
            )
        )
    return bars


class FakeCandidateProvider:
    source_name = "fake候选池"

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        return [
            StrongStockCandidate(
                symbol="603890.SH",
                name="春秋电子",
                industry="消费电子",
                limit_up_evidence=["20日内涨停"],
                abnormal_status="triggered",
                abnormal_flags=["近期是否触发严重异动: 是"],
            ),
            StrongStockCandidate(
                symbol="002000.SZ",
                name="示例股份",
                limit_up_evidence=["20日内涨停"],
            ),
        ]


class IndustryClusterCandidateProvider:
    source_name = "fake板块候选池"

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        return [
            StrongStockCandidate(
                symbol="603890.SH",
                name="强势电子",
                industry="消费电子",
                limit_up_evidence=["20日内涨停"],
            ),
            StrongStockCandidate(
                symbol="603891.SH",
                name="弱势电子",
                industry="消费电子",
                limit_up_evidence=["20日内涨停"],
            ),
            StrongStockCandidate(
                symbol="603892.SH",
                name="跟随电子",
                industry="消费电子",
                limit_up_evidence=["20日内涨停"],
            ),
            StrongStockCandidate(
                symbol="002000.SZ",
                name="独立个股",
                industry="房地产",
                limit_up_evidence=["20日内涨停"],
            ),
        ]


class LargeCandidateProvider:
    source_name = "fake大候选池"

    def __init__(self, count: int) -> None:
        self.count = count

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        return [
            StrongStockCandidate(
                symbol=f"{600000 + index:06d}.SH",
                name=f"示例{index}",
                industry="测试行业",
                limit_up_evidence=["20日内涨停"],
            )
            for index in range(self.count)
        ]


class UnstableOrderCandidateProvider:
    source_name = "fake顺序漂移候选池"

    def __init__(self) -> None:
        self.calls = 0

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        self.calls += 1
        candidates = [
            StrongStockCandidate(
                symbol="600003.SH",
                name="示例三",
                industry="测试行业",
                limit_up_evidence=["20日内涨停"],
            ),
            StrongStockCandidate(
                symbol="600001.SH",
                name="示例一",
                industry="测试行业",
                limit_up_evidence=["20日内涨停"],
            ),
            StrongStockCandidate(
                symbol="600002.SH",
                name="示例二",
                industry="测试行业",
                limit_up_evidence=["20日内涨停"],
            ),
        ]
        if self.calls % 2 == 0:
            return list(reversed(candidates))
        return candidates


class RankedCandidateProvider:
    source_name = "fake有序候选池"
    preserve_candidate_order = True

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        return [
            StrongStockCandidate(
                symbol="600003.SH",
                name="优先三",
                industry="测试行业",
                limit_up_evidence=["20日内涨停", "最近涨停: 20260611", "20日涨停次数: 3"],
            ),
            StrongStockCandidate(
                symbol="600001.SH",
                name="优先一",
                industry="测试行业",
                limit_up_evidence=["20日内涨停", "最近涨停: 20260611", "20日涨停次数: 2"],
            ),
            StrongStockCandidate(
                symbol="600002.SH",
                name="优先二",
                industry="测试行业",
                limit_up_evidence=["20日内涨停", "最近涨停: 20260610", "20日涨停次数: 1"],
            ),
        ]


class AdvancedFilterCandidateProvider:
    source_name = "fake高级筛选候选池"

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        return [
            StrongStockCandidate(
                symbol="603890.SH",
                name="主板电子",
                industry="消费电子",
                limit_up_evidence=["20日内涨停"],
                total_market_cap_cny=12_000_000_000,
            ),
            StrongStockCandidate(
                symbol="300001.SZ",
                name="创业电子",
                industry="消费电子",
                limit_up_evidence=["20日内涨停"],
                total_market_cap_cny=12_000_000_000,
            ),
            StrongStockCandidate(
                symbol="688001.SH",
                name="科创半导体",
                industry="半导体",
                limit_up_evidence=["20日内涨停"],
                total_market_cap_cny=12_000_000_000,
            ),
            StrongStockCandidate(
                symbol="000001.SZ",
                name="超大银行",
                industry="银行",
                limit_up_evidence=["20日内涨停"],
                total_market_cap_cny=200_000_000_000,
            ),
        ]


class FailingCandidateProvider:
    source_name = "fake候选池"

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        raise StrongStockDataUnavailable("候选池数据源失败")


class UnavailableStatusCandidateProvider(FakeCandidateProvider):
    def status(self) -> StrongStockSourceStatus:
        return StrongStockSourceStatus(
            source=self.source_name,
            status="failed",
            detail="候选池不可用",
        )


class FakeKlineProvider:
    source_name = "fake K线"

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        if symbol == "002000.SZ":
            return _bars([20 - index * 0.05 for index in range(220)])
        return _bars([10 + index * 0.05 for index in range(220)])


class FakeCalibrationKlineProvider:
    source_name = "fake校准K线"

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        entry_close = 20 if symbol == "002000.SZ" else 10
        future_closes = [19, 19.4, 19.2, 18.8] if symbol == "002000.SZ" else [11, 10.5, 11.2, 11.6]
        return _calibration_bars(entry_close=entry_close, future_closes=future_closes)


def _calibration_bars(entry_close: float, future_closes: list[float]) -> list[KlineBar]:
    start = datetime(2025, 11, 24)
    closes = [entry_close for _ in range(66)] + future_closes
    bars: list[KlineBar] = []
    for index, close in enumerate(closes):
        bars.append(
            KlineBar(
                date=(start + timedelta(days=index)).strftime("%Y%m%d"),
                open=close,
                close=close,
                high=round(close * 1.02, 2),
                low=round(close * 0.98, 2),
                volume=1_000_000 + index,
            )
        )
    assert bars[65].date == "20260128"
    return bars


class IndustryClusterKlineProvider(FakeKlineProvider):
    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        if symbol == "603891.SH":
            return _bars([20 - index * 0.05 for index in range(220)])
        return _bars([10 + index * 0.05 for index in range(220)])


class CountingKlineProvider(FakeKlineProvider):
    source_name = "counting fake K线"

    def __init__(self) -> None:
        self.symbols: list[str] = []

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        self.symbols.append(symbol)
        return super().get_klines(symbol, count=count)


class BlockingKlineProvider(FakeKlineProvider):
    source_name = "blocking fake K线"

    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        self.started.set()
        assert self.release.wait(timeout=2) is True
        return super().get_klines(symbol, count=count)


class AuctionReviewKlineProvider(FakeKlineProvider):
    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        return [
            KlineBar(date="2026-06-30", open=9.8, close=10.0, high=10.2, low=9.7, volume=100),
            KlineBar(date="2026-07-01", open=10.4, close=10.8, high=11.3, low=10.2, volume=300),
            KlineBar(date="2026-07-02", open=11.0, close=11.2, high=11.5, low=10.7, volume=280),
        ]


class FakeQuoteProvider:
    source_name = "TickFlow"

    def status(self):
        from app.models import StrongStockSourceStatus

        return StrongStockSourceStatus(source="TickFlow", status="missing_key", detail="TICKFLOW_API_KEY 未配置")


class FakeNewsRiskProvider:
    source_name = "fake新闻风险"

    def __init__(self) -> None:
        self.symbols: list[str] = []

    def get_negative_news_risk(self, symbol: str) -> NegativeNewsRisk:
        self.symbols.append(symbol)
        if symbol == "603890.SH":
            return NegativeNewsRisk(
                status="triggered",
                flags=["负面新闻待核验: 2026-06-12 春秋电子收到监管函（东方财富）"],
            )
        return NegativeNewsRisk(status="clear", flags=[])


class FakeLiveQuoteProvider:
    source_name = "TickFlow"

    def status(self) -> StrongStockSourceStatus:
        return StrongStockSourceStatus(source="TickFlow", status="success", detail="fake quotes")

    def get_quotes(self, symbols: list[str]) -> list[TickFlowQuote]:
        return [
            TickFlowQuote(
                symbol=symbol,
                name="春秋电子" if symbol == "603890.SH" else "示例股份",
                last_price=16.55 if symbol == "603890.SH" else 18.5,
                prev_close=15.26 if symbol == "603890.SH" else 20.0,
                open_price=16.3 if symbol == "603890.SH" else 19.1,
                high_price=16.8 if symbol == "603890.SH" else 19.4,
                low_price=16.0 if symbol == "603890.SH" else 18.2,
                pct_change=8.45 if symbol == "603890.SH" else -7.5,
                turnover_rate=12.34 if symbol == "603890.SH" else 4.56,
                turnover_cny=360_000_000,
                volume=220_000,
                quote_time="2026-06-11T10:05:00+08:00",
            )
            for symbol in symbols
        ]

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        return {
            symbol: [
                TickFlowIntradayBar(
                    timestamp=1781141400000,
                    open=16.3,
                    high=16.4,
                    low=16.0,
                    close=16.2,
                    volume=12000,
                    amount=19_440_000,
                    prev_close=15.26,
                ),
                TickFlowIntradayBar(
                    timestamp=1781141460000,
                    open=16.2,
                    high=16.65,
                    low=16.2,
                    close=16.55,
                    volume=15000,
                    amount=24_825_000,
                    prev_close=15.26,
                ),
            ]
            for symbol in symbols
        }


class CountingIntradayQuoteProvider(FakeLiveQuoteProvider):
    def __init__(self) -> None:
        self.intraday_calls = 0

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        self.intraday_calls += 1
        return super().get_intraday_bars(symbols, period=period, count=count)


class FailingIntradayQuoteProvider(FakeLiveQuoteProvider):
    def __init__(self) -> None:
        self.intraday_calls = 0

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        self.intraday_calls += 1
        raise StrongStockDataUnavailable("TickFlow minute bars rate limited")


class FakeGsgfConfirmQuoteProvider(FakeLiveQuoteProvider):
    def get_quotes(self, symbols: list[str]) -> list[TickFlowQuote]:
        return [
            TickFlowQuote(
                symbol=symbol,
                name="春秋电子",
                last_price=16.55,
                prev_close=15.26,
                open_price=16.2,
                high_price=16.56,
                low_price=16.0,
                pct_change=5.7,
                turnover_cny=360_000_000,
                volume=220_000,
                quote_time="2026-06-11T10:05:00+08:00",
            )
            for symbol in symbols
        ]


class FakeGsgfLowBuyQuoteProvider(FakeLiveQuoteProvider):
    def get_quotes(self, symbols: list[str]) -> list[TickFlowQuote]:
        return [
            TickFlowQuote(
                symbol=symbol,
                name="春秋电子",
                last_price=15.15,
                prev_close=15.26,
                open_price=14.5,
                high_price=15.2,
                low_price=14.4,
                pct_change=-0.72,
                turnover_cny=220_000_000,
                volume=180_000,
                quote_time="2026-06-11T10:05:00+08:00",
            )
            for symbol in symbols
        ]

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        return {
            symbol: [
                TickFlowIntradayBar(
                    timestamp=1781141400000,
                    open=14.8,
                    high=14.9,
                    low=14.4,
                    close=14.6,
                    volume=12000,
                    amount=17_520_000,
                    prev_close=15.26,
                ),
                TickFlowIntradayBar(
                    timestamp=1781141460000,
                    open=14.6,
                    high=15.2,
                    low=14.6,
                    close=15.15,
                    volume=15000,
                    amount=22_725_000,
                    prev_close=15.26,
                ),
            ]
            for symbol in symbols
        }


class FakeIfindHealthClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> object:
        self.calls.append({"url": url, **kwargs})

        class _Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> object:
                return {
                    "result": {
                        "tools": [
                            {
                                "name": "stock.profile",
                                "description": "A股基础资料",
                                "inputSchema": {"type": "object", "properties": {}},
                            }
                        ]
                    }
                }

        return _Response()


class FakeIfindResearchProvider:
    def get_stock_research(self, symbol: str):
        from app.models import StockResearchResponse

        return StockResearchResponse(
            symbol=symbol,
            source_status=[
                StrongStockSourceStatus(source="iFinD A股数据", status="success", detail="fake profile"),
                StrongStockSourceStatus(source="iFinD 新闻公告", status="success", detail="fake news"),
                StrongStockSourceStatus(source="iFinD 指数板块", status="success", detail="fake sector"),
            ],
            profile={"公司简称": "春秋电子", "所属行业": "消费电子"},
            valuation={"市盈率TTM": "28.5", "市净率": "3.2"},
            financials={"ROE": "12.4%", "营业收入同比": "18.1%"},
            events=[{"title": "近期严重异动核查", "level": "warning"}],
            news=[{"title": "春秋电子获机构关注", "sentiment": "neutral"}],
            notices=[{"title": "春秋电子风险提示公告"}],
            sector={"板块": "消费电子", "强度": "strong"},
        )


class CountingIfindResearchProvider(FakeIfindResearchProvider):
    source_name = "counting iFinD MCP"

    def __init__(self) -> None:
        self.symbols: list[str] = []

    def get_stock_research(self, symbol: str):
        self.symbols.append(symbol)
        return super().get_stock_research(symbol)


class FakeMarketOverviewProvider:
    source_name = "fake市场概览"

    def get_overview(self) -> MarketOverviewResponse:
        return MarketOverviewResponse(
            trade_date="2026-06-26",
            turnover=MarketTurnoverSummary(
                total_cny=3_575_720_000_000,
                previous_total_cny=3_618_100_000_000,
                change_cny=-42_380_000_000,
                change_pct=-1.17,
            ),
            advance_decline=MarketAdvanceDeclineSummary(
                advance_count=802,
                decline_count=4738,
                unchanged_count=51,
                limit_up_count=None,
                limit_down_count=None,
            ),
            indices=[
                MarketIndexSnapshot(
                    symbol="000001.SH",
                    name="上证",
                    last_price=4027.26,
                    change_pct=-2.25,
                    turnover_cny=1_600_000_000_000,
                    source="iFinD 实时指数",
                ),
                MarketIndexSnapshot(
                    symbol="399001.SZ",
                    name="深证",
                    last_price=15782.22,
                    change_pct=-3.43,
                    turnover_cny=1_900_000_000_000,
                    source="iFinD 实时指数",
                ),
                MarketIndexSnapshot(
                    symbol="399006.SZ",
                    name="创业板",
                    last_price=3188.66,
                    change_pct=1.25,
                    turnover_cny=800_000_000_000,
                    source="iFinD 实时指数",
                ),
                MarketIndexSnapshot(
                    symbol="000688.SH",
                    name="科创50",
                    last_price=1020.48,
                    change_pct=0.86,
                    turnover_cny=300_000_000_000,
                    source="iFinD 实时指数",
                ),
            ],
            sectors=[
                MarketSectorStrengthItem(
                    name="存储芯片",
                    change_pct=3.26,
                    turnover_cny=86_500_000_000,
                    advance_count=38,
                    decline_count=6,
                    leader="香农芯创",
                    source="东方财富行业板块",
                ),
                MarketSectorStrengthItem(
                    name="电力",
                    change_pct=1.42,
                    turnover_cny=54_200_000_000,
                    advance_count=42,
                    decline_count=18,
                    leader="豫能控股",
                    source="东方财富行业板块",
                ),
                MarketSectorStrengthItem(
                    name="消费电子",
                    change_pct=-2.18,
                    turnover_cny=61_400_000_000,
                    advance_count=9,
                    decline_count=58,
                    leader="春秋电子",
                    source="东方财富行业板块",
                ),
            ],
            source_status=[
                StrongStockSourceStatus(
                    source="东方财富全A指数",
                    status="success",
                    detail="沪深北指数成交额和涨跌家数",
                ),
                StrongStockSourceStatus(
                    source="东方财富行业板块",
                    status="success",
                    detail="返回 2 个板块",
                ),
            ],
        )

    def get_market_rankings(self, limit: int = 50) -> MarketRankingsResponse:
        return MarketRankingsResponse(
            trade_date="2026-06-26",
            pct_change_rank=[
                MarketRankingItem(
                    symbol="300001.SZ",
                    name="涨幅一号",
                    industry="机器人",
                    last_price=11.2,
                    open_price=10.8,
                    prev_close=10.0,
                    pct_change=12.0,
                    current_pct_change=12.0,
                    turnover_cny=300_000_000,
                    turnover_rate=6.0,
                    quote_time="2026-06-26T10:00:00+08:00",
                ),
                MarketRankingItem(
                    symbol="300002.SZ",
                    name="涨幅二号",
                    industry="电池",
                    last_price=12.1,
                    open_price=11.0,
                    prev_close=10.5,
                    pct_change=8.5,
                    current_pct_change=8.5,
                    turnover_cny=900_000_000,
                    turnover_rate=2.0,
                    quote_time="2026-06-26T10:00:00+08:00",
                ),
            ][:limit],
            turnover_rank=[
                MarketRankingItem(
                    symbol="600003.SH",
                    name="成交一号",
                    last_price=13.2,
                    pct_change=3.2,
                    turnover_cny=1_500_000_000,
                    quote_time="2026-06-26T10:00:00+08:00",
                )
            ][:limit],
            source_status=[
                StrongStockSourceStatus(
                    source="TickFlow 全A实时行情",
                    status="success",
                    detail="fake rankings",
                )
            ],
        )


class CountingMarketOverviewProvider(FakeMarketOverviewProvider):
    source_name = "counting fake市场概览"

    def __init__(self) -> None:
        self.overview_calls = 0

    def get_overview(self) -> MarketOverviewResponse:
        self.overview_calls += 1
        return super().get_overview()


class FakeStockIndustryProvider(FakeMarketOverviewProvider):
    def get_stock_industries(self, symbols: list[str]) -> dict[str, str]:
        return {symbol: "贵金属" for symbol in symbols if symbol == "000506.SZ"}


class CountingSectorRadarProvider(FakeMarketOverviewProvider):
    source_name = "counting fake板块雷达"

    def __init__(self) -> None:
        self.radar_calls: list[int] = []

    def get_sector_radar(self, limit: int = 20) -> SectorRadarResponse:
        self.radar_calls.append(limit)
        return SectorRadarResponse(
            trade_date="2026-06-26",
            capital_flow_status="direct",
            flow_source="fake板块资金流",
            inflow=[
                SectorRadarItem(
                    name="存储芯片",
                    change_pct=3.26,
                    turnover_cny=86_500_000_000,
                    net_flow_cny=4_200_000_000,
                    advance_count=38,
                    decline_count=6,
                    leader="香农芯创",
                    source="fake板块资金流",
                )
            ],
            outflow=[
                SectorRadarItem(
                    name="消费电子",
                    change_pct=-2.18,
                    turnover_cny=61_400_000_000,
                    net_flow_cny=-3_300_000_000,
                    advance_count=9,
                    decline_count=58,
                    leader="春秋电子",
                    source="fake板块资金流",
                )
            ],
            source_status=[
                StrongStockSourceStatus(
                    source="fake板块资金流",
                    status="success",
                    detail="返回 2 个板块",
                )
            ],
        )


class CountingMarketRankingsProvider(FakeMarketOverviewProvider):
    source_name = "counting fake全A排行"

    def __init__(self) -> None:
        self.ranking_calls: list[int] = []

    def get_market_rankings(self, limit: int = 50) -> MarketRankingsResponse:
        self.ranking_calls.append(limit)
        return super().get_market_rankings(limit=limit)


class SequenceMarketRankingsProvider(FakeMarketOverviewProvider):
    source_name = "sequence fake全A排行"

    def __init__(self) -> None:
        self.ranking_calls: list[int] = []

    def get_market_rankings(self, limit: int = 50) -> MarketRankingsResponse:
        self.ranking_calls.append(limit)
        symbol = "300025.SZ" if len(self.ranking_calls) == 1 else "300930.SZ"
        name = "九点二五" if len(self.ranking_calls) == 1 else "九点三零"
        return MarketRankingsResponse(
            trade_date="2026-06-26",
            pct_change_rank=[
                MarketRankingItem(
                    symbol=symbol,
                    name=name,
                    industry="机器人",
                    last_price=11.2,
                    open_price=10.8,
                    prev_close=10.0,
                    pct_change=12.0,
                    current_pct_change=12.0,
                    turnover_cny=300_000_000,
                    turnover_rate=6.0,
                    quote_time="2026-06-26T10:00:00+08:00",
                )
            ][:limit],
            source_status=[
                StrongStockSourceStatus(
                    source="TickFlow 全A实时行情",
                    status="success",
                    detail="fake sequence rankings",
                )
            ],
        )


class SequenceMarketRankingsProviderWithIndustryBackfill(SequenceMarketRankingsProvider):
    def get_market_rankings(self, limit: int = 50) -> MarketRankingsResponse:
        response = super().get_market_rankings(limit=limit)
        if len(self.ranking_calls) == 1:
            response.pct_change_rank[0].industry = None
        return response

    def get_stock_industries(self, symbols: list[str]) -> dict[str, str]:
        return {symbol: "通信设备" for symbol in symbols if symbol == "300025.SZ"}


class FailingMarketRankingsProvider(FakeMarketOverviewProvider):
    source_name = "failing fake全A排行"

    def get_market_rankings(self, limit: int = 50) -> MarketRankingsResponse:
        raise StrongStockDataUnavailable("rankings unavailable")


class BlockingMarketRankingsProvider(FakeMarketOverviewProvider):
    source_name = "blocking fake全A排行"

    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.ranking_calls: list[int] = []

    def get_market_rankings(self, limit: int = 50) -> MarketRankingsResponse:
        self.ranking_calls.append(limit)
        self.started.set()
        self.release.wait(timeout=3)
        return super().get_market_rankings(limit=limit)


class EmptySectorRadarProvider(FakeMarketOverviewProvider):
    source_name = "empty fake板块雷达"

    def get_sector_radar(self, limit: int = 20) -> SectorRadarResponse:
        return SectorRadarResponse(
            trade_date="2026-06-26",
            capital_flow_status="unavailable",
            flow_source="empty fake板块资金流",
            inflow=[],
            outflow=[],
            source_status=[
                StrongStockSourceStatus(
                    source="empty fake板块资金流",
                    status="failed",
                    detail="主源无板块资金流",
                )
            ],
        )


class FakeTdxSectorRadarProvider:
    source_name = "通达信MCP"

    def __init__(self) -> None:
        self.calls: list[int] = []

    def status(self) -> StrongStockSourceStatus:
        return StrongStockSourceStatus(source="通达信MCP", status="success", detail="fake tdx configured")

    def get_sector_radar(self, limit: int = 20) -> SectorRadarResponse:
        self.calls.append(limit)
        return SectorRadarResponse(
            trade_date="2026-06-26",
            capital_flow_status="estimated",
            flow_source="通达信MCP涨停概念集中度估算",
            inflow=[
                SectorRadarItem(
                    name="半导体",
                    source="通达信MCP涨停概念",
                    advance_count=3,
                    decline_count=0,
                    leader="新洁能",
                    net_flow_cny=680_000_000,
                    strength_score=71,
                )
            ],
            outflow=[],
            source_status=[
                StrongStockSourceStatus(
                    source="通达信MCP涨停概念",
                    status="success",
                    detail="fallback ok",
                )
            ],
        )


class FailingTdxSectorRadarProvider:
    source_name = "通达信MCP"

    def get_sector_radar(self, limit: int = 20) -> SectorRadarResponse:
        raise StrongStockDataUnavailable("tdx unavailable")


class FakeTdxThemeRowsProvider(FakeTdxSectorRadarProvider):
    def query_rows(self, question: str, size: int = 50, page: int = 1, market_range: str = "AG") -> list[dict[str, object]]:
        return [
            {
                "代码": "300001.SZ",
                "名称": "涨幅一号",
                "所属概念": "机器人;减速器",
                "连续涨停天数": 2,
                "封单金额": 12000,
            },
            {
                "代码": "300002.SZ",
                "名称": "涨幅二号",
                "所属概念": "电池;储能",
                "连续涨停天数": 1,
                "封单金额": 3000,
            },
        ]


class FakeConceptTagProvider:
    source_name = "fake概念归属"

    def get_concept_tags(self, symbol: str) -> list[str]:
        return {
            "603890.SH": ["消费电子", "AI眼镜", "机器人概念", "浙江板块"],
            "002000.SZ": ["房地产", "存储芯片", "先进封装", "广东板块"],
        }.get(symbol, [])


class FailingIfCalledCandidateProvider(FakeCandidateProvider):
    source_name = "不应同步调用候选池"

    def __init__(self) -> None:
        self.calls = 0

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        self.calls += 1
        raise AssertionError("candidate provider should not be called synchronously")


class FakePlateRotationReferenceProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str, int]] = []

    def get_today_themes(
        self,
        *,
        limit: int = 20,
        source: str = "kaipan",
        days: int = 20,
    ) -> PlateRotationReferenceResponse:
        self.calls.append((limit, source, days))
        return PlateRotationReferenceResponse(
            source=source,
            themes=[
                PlateRotationThemeItem(rank=1, code="801159", name="机器人", score=35630, value_type="score", color="red"),
                PlateRotationThemeItem(rank=2, code="801314", name="ST板块", score=12964, value_type="score", color="red"),
            ][:limit],
            source_status=[
                StrongStockSourceStatus(
                    source="短线侠/开盘啦题材榜单",
                    status="success",
                    detail="fake",
                )
            ],
        )


def _client(
    tmp_path: Path,
    candidate_provider: object | None = None,
    kline_provider: object | None = None,
    quote_provider: object | None = None,
    news_risk_provider: object | None = None,
    market_overview_provider: object | None = None,
    concept_provider: object | None = None,
) -> TestClient:
    app.state.candidate_provider = candidate_provider or FakeCandidateProvider()
    app.state.kline_provider = kline_provider or FakeKlineProvider()
    app.state.quote_provider = quote_provider or FakeQuoteProvider()
    app.state.news_risk_provider = news_risk_provider or FakeNewsRiskProvider()
    app.state.market_overview_provider = market_overview_provider or FakeMarketOverviewProvider()
    if concept_provider is not None:
        app.state.concept_provider = concept_provider
    elif hasattr(app.state, "concept_provider"):
        delattr(app.state, "concept_provider")
    if hasattr(app.state, "default_concept_provider"):
        delattr(app.state, "default_concept_provider")
    app.state.auction_sampler_disabled = True
    app.state.sector_workbench_sampler_disabled = True
    AUCTION_SNAPSHOT_CACHE.clear()
    MARKET_RANKINGS_CACHE.clear()
    SECTOR_INTRADAY_CACHE.clear()
    SECTOR_RADAR_CACHE.clear()
    if hasattr(app.state, "auction_snapshot_store"):
        delattr(app.state, "auction_snapshot_store")
    if hasattr(app.state, "auction_review_store"):
        delattr(app.state, "auction_review_store")
    if hasattr(app.state, "sector_workbench_store"):
        delattr(app.state, "sector_workbench_store")
    if hasattr(app.state, "sector_theme_rows_store"):
        delattr(app.state, "sector_theme_rows_store")
    if hasattr(app.state, "sector_theme_rows_refreshing"):
        delattr(app.state, "sector_theme_rows_refreshing")
    if hasattr(app.state, "sector_theme_rows_async_refresh_disabled"):
        delattr(app.state, "sector_theme_rows_async_refresh_disabled")
    if hasattr(app.state, "sector_intraday_refreshing"):
        delattr(app.state, "sector_intraday_refreshing")
    if hasattr(app.state, "sector_intraday_async_refresh_disabled"):
        delattr(app.state, "sector_intraday_async_refresh_disabled")
    if hasattr(app.state, "sector_now"):
        delattr(app.state, "sector_now")
    if hasattr(app.state, "plate_rotation_reference_provider"):
        delattr(app.state, "plate_rotation_reference_provider")
    app.state.watchlist_snapshot = WatchlistSnapshot(
        items=[WatchlistItem(symbol="002000.SZ", name="示例股份")]
    )
    app.state.runs_dir = tmp_path
    app.state.watchlist_path = tmp_path / "watchlist.txt"
    app.state.runtime_config_path = tmp_path / "runtime_config.json"
    app.state.sector_workbench_dir = tmp_path / "sectors"
    return TestClient(app)


def _seed_sector_theme_rows(
    tmp_path: Path,
    *,
    rows: list[dict[str, object]] | None = None,
    source: str = "通达信MCP涨停概念映射",
) -> None:
    store = SectorThemeRowsStore(tmp_path / "sectors" / "theme-rows")
    app.state.sector_theme_rows_store = store
    store.save(
        trade_date=datetime.now().astimezone().date().isoformat(),
        rows=rows
        or [
            {
                "代码": "300001.SZ",
                "名称": "涨幅一号",
                "所属概念": "机器人;减速器",
                "连续涨停天数": 2,
                "封单金额": 12000,
            },
            {
                "代码": "300002.SZ",
                "名称": "涨幅二号",
                "所属概念": "电池;储能",
                "连续涨停天数": 1,
                "封单金额": 3000,
            },
        ],
        status_source=source,
        status_detail="测试题材快照",
    )


def test_health_returns_ok(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_data_source_status_reports_tickflow_missing_key(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/data-sources/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["source"] == "fake候选池"
    assert payload["items"][2]["source"] == "TickFlow"
    assert payload["items"][2]["status"] == "missing_key"


def test_data_source_status_uses_candidate_provider_status(tmp_path: Path) -> None:
    client = _client(tmp_path, candidate_provider=UnavailableStatusCandidateProvider())

    response = client.get("/api/data-sources/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["source"] == "fake候选池"
    assert payload["items"][0]["status"] == "failed"
    assert payload["items"][0]["detail"] == "候选池不可用"


def test_settings_can_be_saved_and_read_without_exposing_full_key(tmp_path: Path) -> None:
    client = _client(tmp_path)

    save_response = client.put(
        "/api/settings",
        json={
            "candidate_provider": "recent_limit_up",
            "kline_provider": "tickflow",
            "quote_provider": "tickflow",
            "tickflow_api_key": "tk_saved_secret",
            "tickflow_base_url": "https://api.example.test",
            "provider_timeout_seconds": 3.5,
        },
    )

    assert save_response.status_code == 200
    payload = save_response.json()
    assert payload["config"]["tickflow_api_key_configured"] is True
    assert payload["config"]["tickflow_api_key_preview"] != "tk_saved_secret"
    assert payload["config"]["tickflow_base_url"] == "https://api.example.test"
    assert "tickflow_api_key" not in payload["saved"]

    get_response = client.get("/api/settings")
    assert get_response.status_code == 200
    assert get_response.json()["config"]["provider_timeout_seconds"] == 3.5
    assert "tk_saved_secret" not in get_response.text


def test_settings_exposes_gsgf_auto_review_config(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["gsgf_auto_review"]["daily_review_time"] == "15:40"
    assert payload["config"]["gsgf_auto_review"]["weekly_calibration_scan_limit"] == 80


def test_settings_can_save_ai_analysis_config_without_exposing_full_key(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.put(
        "/api/settings",
        json={
            "candidate_provider": "recent_limit_up",
            "kline_provider": "tickflow",
            "quote_provider": "tickflow",
            "tickflow_base_url": "https://api.example.test",
            "provider_timeout_seconds": 3.5,
            "ai_analysis": {
                "enabled": True,
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-reasoner",
                "api_key": "deepseek_saved_secret",
                "run_after_daily_review": True,
                "run_after_weekly_calibration": False,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["ai_analysis"]["enabled"] is True
    assert payload["config"]["ai_analysis"]["provider"] == "deepseek"
    assert payload["config"]["ai_analysis"]["model"] == "deepseek-reasoner"
    assert payload["config"]["ai_analysis"]["api_key_configured"] is True
    assert payload["config"]["ai_analysis"]["api_key_preview"] != "deepseek_saved_secret"
    assert "api_key" not in payload["saved"]["ai_analysis"]
    assert "deepseek_saved_secret" not in response.text


def test_settings_can_be_saved_with_ifind_configuration(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.put(
        "/api/settings",
        json={
            "candidate_provider": "recent_limit_up",
            "kline_provider": "tickflow",
            "quote_provider": "tickflow",
            "tickflow_api_key": "tk_saved_secret",
            "tickflow_base_url": "https://api.example.test",
            "provider_timeout_seconds": 3.5,
            "ifind_api_key": "ifind_saved_secret",
            "ifind_base_url": "https://api-mcp.51ifind.com:8643",
            "ifind_service_id": "hexin-ifind-ds-stock-mcp",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["ifind_api_key_configured"] is True
    assert payload["config"]["ifind_api_key_preview"] != "ifind_saved_secret"
    assert payload["config"]["ifind_base_url"] == "https://api-mcp.51ifind.com:8643"
    assert payload["config"]["ifind_service_id"] == "hexin-ifind-ds-stock-mcp"
    assert "ifind_api_key" not in payload["saved"]


def test_settings_can_be_saved_with_tdx_mcp_configuration(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.put(
        "/api/settings",
        json={
            "candidate_provider": "recent_limit_up",
            "kline_provider": "tickflow",
            "quote_provider": "tickflow",
            "tickflow_api_key": "tk_saved_secret",
            "tickflow_base_url": "https://api.example.test",
            "provider_timeout_seconds": 3.5,
            "tdx_api_key": "tdx_saved_secret",
            "tdx_base_url": "https://mcp.tdx.example.test/mcp",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["tdx_api_key_configured"] is True
    assert payload["config"]["tdx_api_key_preview"] != "tdx_saved_secret"
    assert payload["config"]["tdx_base_url"] == "https://mcp.tdx.example.test/mcp"
    assert "tdx_api_key" not in payload["saved"]
    assert "tdx_saved_secret" not in response.text


def test_settings_health_check_reports_ifind_mcp_probe(tmp_path: Path) -> None:
    client = _client(tmp_path)
    app.state.ifind_http_client = FakeIfindHealthClient()
    save_response = client.put(
        "/api/settings",
        json={
            "candidate_provider": "recent_limit_up",
            "kline_provider": "tickflow",
            "quote_provider": "tickflow",
            "tickflow_api_key": "tk_saved_secret",
            "tickflow_base_url": "https://api.example.test",
            "provider_timeout_seconds": 3.5,
            "ifind_api_key": "ifind_saved_secret",
            "ifind_base_url": "https://api-mcp.51ifind.com:8643",
            "ifind_service_id": "hexin-ifind-ds-stock-mcp",
        },
    )
    assert save_response.status_code == 200

    response = client.get("/api/settings/health?symbol=603890.SH")

    assert response.status_code == 200
    payload = response.json()
    probe_names = [item["name"] for item in payload["probes"]]
    assert "iFinD MCP" in probe_names
    assert "iFinD A股数据" in probe_names
    assert all(isinstance(item["latency_ms"], int) for item in payload["probes"])


def test_settings_health_check_reports_tdx_mcp_probe(tmp_path: Path) -> None:
    client = _client(tmp_path)
    app.state.tdx_provider = FakeTdxSectorRadarProvider()

    response = client.get("/api/settings/health?symbol=603890.SH")

    assert response.status_code == 200
    payload = response.json()
    probe_names = [item["name"] for item in payload["probes"]]
    assert "通达信MCP" in probe_names
    tdx_probe = next(item for item in payload["probes"] if item["name"] == "通达信MCP")
    assert tdx_probe["status"] == "success"
    assert tdx_probe["detail"] == "fake tdx configured"
    assert isinstance(tdx_probe["latency_ms"], int)


def test_settings_health_check_constructs_default_tdx_provider(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/settings/health?symbol=603890.SH")

    assert response.status_code == 200
    payload = response.json()
    tdx_probe = next(item for item in payload["probes"] if item["name"] == "通达信MCP")
    assert tdx_probe["status"] in {"success", "missing_key"}
    assert tdx_probe["detail"]


def test_settings_health_check_reports_provider_probes(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        kline_provider=FakeKlineProvider(),
        quote_provider=FakeLiveQuoteProvider(),
    )

    response = client.get("/api/settings/health?symbol=603890.SH")

    assert response.status_code == 200
    payload = response.json()
    probe_names = [item["name"] for item in payload["probes"]]
    assert "fake K线" in probe_names
    assert "TickFlow 实时行情" in probe_names
    assert "TickFlow 当日分钟线" in probe_names
    assert all(isinstance(item["latency_ms"], int) for item in payload["probes"])


def test_stock_kline_endpoint_returns_daily_bars(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/stocks/603890.SH/kline?count=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "603890.SH"
    assert payload["source_status"]["source"] == "fake K线"
    assert len(payload["bars"]) == 5
    assert payload["bars"][-1]["close"] > payload["bars"][0]["close"]
    assert payload["gsgf_annotations"] == []


def test_stock_kline_endpoint_returns_gsgf_chart_annotations(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/stocks/603890.SH/kline?count=220")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["type"] == "volume_structure" for item in payload["gsgf_annotations"])
    assert any(item["type"] == "zone" for item in payload["gsgf_annotations"])


def test_stock_kline_endpoint_reuses_cached_provider_result(tmp_path: Path) -> None:
    kline_provider = CountingKlineProvider()
    client = _client(tmp_path, kline_provider=kline_provider)

    first = client.get("/api/stocks/603890.SH/kline?count=5")
    second = client.get("/api/stocks/603890.SH/kline?count=5")
    third = client.get("/api/stocks/603890.SH/kline?count=6")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200
    assert kline_provider.symbols == ["603890.SH", "603890.SH"]


def test_stock_research_reports_missing_ifind_key_without_breaking(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/stocks/603890.SH/research")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "603890.SH"
    assert payload["source_status"][0]["source"] == "iFinD MCP"
    assert payload["source_status"][0]["status"] == "missing_key"
    assert payload["profile"] == {}
    assert payload["financials"] == {}
    assert payload["news"] == []
    assert payload["sector"] == {}


def test_stock_research_returns_ifind_payload_from_provider(tmp_path: Path) -> None:
    client = _client(tmp_path)
    app.state.ifind_provider = FakeIfindResearchProvider()

    response = client.get("/api/stocks/603890.SH/research")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "603890.SH"
    assert payload["profile"]["公司简称"] == "春秋电子"
    assert payload["valuation"]["市盈率TTM"] == "28.5"
    assert payload["financials"]["ROE"] == "12.4%"
    assert payload["events"][0]["level"] == "warning"
    assert payload["news"][0]["title"] == "春秋电子获机构关注"
    assert payload["notices"][0]["title"] == "春秋电子风险提示公告"
    assert payload["sector"]["强度"] == "strong"


def test_stock_research_endpoint_reuses_cached_ifind_payload(tmp_path: Path) -> None:
    client = _client(tmp_path)
    provider = CountingIfindResearchProvider()
    app.state.ifind_provider = provider

    first = client.get("/api/stocks/603890.SH/research")
    second = client.get("/api/stocks/603890.SH/research")

    assert first.status_code == 200
    assert second.status_code == 200
    assert provider.symbols == ["603890.SH"]


def test_market_overview_returns_full_a_share_metrics(tmp_path: Path) -> None:
    client = _client(tmp_path, market_overview_provider=FakeMarketOverviewProvider())

    response = client.get("/api/market/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-26"
    assert payload["turnover"]["total_cny"] == 3_575_720_000_000
    assert payload["turnover"]["previous_total_cny"] == 3_618_100_000_000
    assert payload["turnover"]["change_cny"] == -42_380_000_000
    assert payload["turnover"]["change_pct"] == -1.17
    assert payload["advance_decline"]["advance_count"] == 802
    assert payload["advance_decline"]["decline_count"] == 4738
    assert payload["advance_decline"]["unchanged_count"] == 51
    assert [item["symbol"] for item in payload["indices"]] == [
        "000001.SH",
        "399001.SZ",
        "399006.SZ",
        "000688.SH",
    ]
    assert payload["indices"][2]["name"] == "创业板"
    assert payload["indices"][3]["name"] == "科创50"
    assert payload["sectors"][0]["name"] == "存储芯片"
    assert payload["sectors"][0]["source"] == "东方财富行业板块"
    assert payload["source_status"][0]["source"] == "东方财富全A指数"


def test_short_term_sentiment_archive_persists_decision(tmp_path: Path) -> None:
    client = _client(tmp_path, market_overview_provider=FakeMarketOverviewProvider())

    response = client.post("/api/short-term/sentiment/review/archive?trade_date=2026-06-26&limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-26"
    archived = tmp_path / "sentiment_reviews" / "2026-06-26.jsonl"
    assert archived.exists()
    assert '"trade_date":"2026-06-26"' in archived.read_text(encoding="utf-8")


def test_stock_quote_returns_tickflow_turnover_rate(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeLiveQuoteProvider())

    response = client.get("/api/stocks/603890.SH/quote")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "603890.SH"
    assert payload["last_price"] == 16.55
    assert payload["turnover_rate"] == 12.34
    assert payload["source_status"]["source"] == "TickFlow"


def test_stock_quote_supplements_industry_from_market_provider(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        quote_provider=FakeLiveQuoteProvider(),
        market_overview_provider=FakeStockIndustryProvider(),
    )

    response = client.get("/api/stocks/000506.SZ/quote")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "示例股份"
    assert payload["industry"] == "贵金属"


def test_market_overview_endpoint_reuses_cached_snapshot(tmp_path: Path) -> None:
    provider = CountingMarketOverviewProvider()
    client = _client(tmp_path, market_overview_provider=provider)

    first = client.get("/api/market/overview")
    second = client.get("/api/market/overview")

    assert first.status_code == 200
    assert second.status_code == 200
    assert provider.overview_calls == 1


def test_market_rankings_returns_tickflow_pct_and_turnover_rankings(tmp_path: Path) -> None:
    client = _client(tmp_path, market_overview_provider=FakeMarketOverviewProvider())

    response = client.get("/api/market/rankings?limit=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-26"
    assert [item["symbol"] for item in payload["pct_change_rank"]] == ["300001.SZ", "300002.SZ"]
    assert payload["turnover_rank"][0]["symbol"] == "600003.SH"
    assert payload["source_status"][0]["source"] == "TickFlow 全A实时行情"


def test_market_rankings_endpoint_reuses_cached_provider_result(tmp_path: Path) -> None:
    provider = CountingMarketRankingsProvider()
    client = _client(tmp_path, market_overview_provider=provider)

    first = client.get("/api/market/rankings?limit=2")
    second = client.get("/api/market/rankings?limit=2")
    third = client.get("/api/market/rankings?limit=3")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200
    assert provider.ranking_calls == [2, 3]


def test_auction_snapshot_returns_opening_auction_candidates(tmp_path: Path) -> None:
    client = _client(tmp_path, market_overview_provider=FakeMarketOverviewProvider())
    app.state.auction_now = datetime(2026, 6, 26, 9, 26)

    try:
        response = client.get("/api/auction/snapshot?limit=2")
    finally:
        delattr(app.state, "auction_now")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"] == "pre_open"
    assert payload["metrics"]["candidate_count"] == 2
    assert payload["items"][0]["symbol"] == "300001.SZ"
    assert payload["items"][0]["auction_score"] > payload["items"][1]["auction_score"]
    assert payload["items"][0]["current_pct_change"] == 12.0
    assert payload["items"][0]["industry"] == "机器人"
    assert payload["items"][0]["open_gap_pct"] == 8.0
    assert payload["items"][0]["tier"] == "risk_overheat"
    assert payload["items"][0]["action_note"] == "高开过热，只适合观察封单与承接，不追高。"
    assert "竞价强势高开" in payload["items"][0]["signals"]
    assert "高开需防冲高回落" in payload["items"][0]["risk_flags"]
    assert payload["source_status"][0]["source"] == "TickFlow 全A实时行情"


def test_auction_snapshot_links_candidates_to_hot_plate_reference(tmp_path: Path) -> None:
    client = _client(tmp_path, market_overview_provider=FakeMarketOverviewProvider())
    app.state.plate_rotation_reference_provider = FakePlateRotationReferenceProvider()

    response = client.get("/api/auction/snapshot?limit=2&refresh=true")

    assert response.status_code == 200
    payload = response.json()
    first = payload["items"][0]
    assert first["industry"] == "机器人"
    assert first["themes"] == ["机器人"]
    assert first["hot_theme_rank"] == 1
    assert first["theme_auction_rank"] == 1
    assert first["theme_resonance"] is True
    assert "题材共振" in first["signals"]
    assert any(item["source"] == "短线题材联动" for item in payload["source_status"])


def test_auction_snapshot_endpoint_reuses_cached_provider_result(tmp_path: Path) -> None:
    provider = CountingMarketRankingsProvider()
    client = _client(tmp_path, market_overview_provider=provider)

    first = client.get("/api/auction/snapshot?limit=2")
    second = client.get("/api/auction/snapshot?limit=2")
    third = client.get("/api/auction/snapshot?limit=3")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200
    assert provider.ranking_calls == [100]


def test_auction_latest_returns_missing_without_fetching_provider(tmp_path: Path) -> None:
    provider = CountingMarketRankingsProvider()
    client = _client(tmp_path, market_overview_provider=provider)

    response = client.get("/api/auction/latest?limit=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_status"] == "missing"
    assert payload["metrics"]["candidate_count"] == 0
    assert payload["items"] == []
    assert provider.ranking_calls == []


def test_auction_snapshot_refresh_updates_latest_snapshot(tmp_path: Path) -> None:
    provider = CountingMarketRankingsProvider()
    client = _client(tmp_path, market_overview_provider=provider)

    refresh_response = client.get("/api/auction/snapshot?limit=2&refresh=true")
    latest_response = client.get("/api/auction/latest?limit=2")

    assert refresh_response.status_code == 200
    assert latest_response.status_code == 200
    latest_payload = latest_response.json()
    assert latest_payload["snapshot_status"] == "cached"
    assert latest_payload["cache_age_seconds"] is not None
    assert latest_payload["items"][0]["symbol"] == "300001.SZ"
    assert provider.ranking_calls == [100]


def test_auction_snapshot_refresh_after_open_keeps_0925_locked_snapshot(tmp_path: Path) -> None:
    provider = SequenceMarketRankingsProvider()
    client = _client(tmp_path, market_overview_provider=provider)
    app.state.auction_now = datetime(2026, 6, 26, 9, 25, 0)

    try:
        lock_response = client.get("/api/auction/snapshot?limit=2&refresh=true")
        app.state.auction_now = datetime(2026, 6, 26, 9, 30, 1)
        after_open_response = client.get("/api/auction/snapshot?limit=2&refresh=true")
        latest_response = client.get("/api/auction/latest?limit=2")
    finally:
        delattr(app.state, "auction_now")

    assert lock_response.status_code == 200
    assert after_open_response.status_code == 200
    assert latest_response.status_code == 200
    assert lock_response.json()["items"][0]["symbol"] == "300025.SZ"
    assert after_open_response.json()["items"][0]["symbol"] == "300025.SZ"
    latest_payload = latest_response.json()
    assert latest_payload["items"][0]["symbol"] == "300025.SZ"
    assert "09:25" in latest_payload["source_status"][-1]["detail"]
    assert provider.ranking_calls == [100, 100]


def test_auction_snapshot_refresh_after_open_backfills_locked_industries(tmp_path: Path) -> None:
    provider = SequenceMarketRankingsProviderWithIndustryBackfill()
    client = _client(tmp_path, market_overview_provider=provider)
    app.state.auction_now = datetime(2026, 6, 26, 9, 25, 0)

    try:
        lock_response = client.get("/api/auction/snapshot?limit=2&refresh=true")
        app.state.auction_now = datetime(2026, 6, 26, 9, 30, 1)
        after_open_response = client.get("/api/auction/snapshot?limit=2&refresh=true")
        latest_response = client.get("/api/auction/latest?limit=2")
    finally:
        delattr(app.state, "auction_now")

    assert lock_response.status_code == 200
    assert lock_response.json()["items"][0]["industry"] == "通信设备"
    assert after_open_response.status_code == 200
    assert after_open_response.json()["items"][0]["symbol"] == "300025.SZ"
    assert after_open_response.json()["items"][0]["industry"] == "通信设备"
    assert latest_response.json()["items"][0]["industry"] == "通信设备"


def test_auction_latest_restores_0925_locked_snapshot_after_store_restart(tmp_path: Path) -> None:
    provider = SequenceMarketRankingsProvider()
    client = _client(tmp_path, market_overview_provider=provider)
    app.state.auction_now = datetime(2026, 6, 26, 9, 25, 0)

    try:
        lock_response = client.get("/api/auction/snapshot?limit=2&refresh=true")
        delattr(app.state, "auction_snapshot_store")
        latest_response = client.get("/api/auction/latest?limit=2")
    finally:
        delattr(app.state, "auction_now")

    assert lock_response.status_code == 200
    assert latest_response.status_code == 200
    latest_payload = latest_response.json()
    assert latest_payload["items"][0]["symbol"] == "300025.SZ"
    assert latest_payload["snapshot_status"] == "cached"
    assert "09:25" in latest_payload["source_status"][-1]["detail"]


def test_auction_snapshot_refresh_job_runs_in_background_and_saves_latest(
    tmp_path: Path,
) -> None:
    provider = BlockingMarketRankingsProvider()
    client = _client(tmp_path, market_overview_provider=provider)

    job_response = client.post("/api/auction/snapshot/jobs?limit=2")

    assert job_response.status_code == 200
    job_payload = job_response.json()
    assert job_payload["type"] == "auction_snapshot_refresh"
    assert job_payload["status"] in {"pending", "running"}
    assert provider.started.wait(timeout=1) is True
    latest_before_release = client.get("/api/auction/latest?limit=2").json()
    assert latest_before_release["snapshot_status"] == "missing"

    provider.release.set()
    job_id = job_payload["job_id"]
    completed_payload = job_payload
    for _ in range(30):
        completed_payload = client.get(f"/api/auction/snapshot/jobs/{job_id}").json()
        if completed_payload["status"] == "success":
            break
        sleep(0.05)

    assert completed_payload["status"] == "success"
    latest_response = client.get("/api/auction/latest?limit=2")
    latest_payload = latest_response.json()
    assert latest_response.status_code == 200
    assert latest_payload["snapshot_status"] == "cached"
    assert latest_payload["items"][0]["symbol"] == "300001.SZ"
    assert provider.ranking_calls == [100]


def test_auction_snapshot_refresh_job_reuses_active_job(tmp_path: Path) -> None:
    provider = BlockingMarketRankingsProvider()
    client = _client(tmp_path, market_overview_provider=provider)

    first_response = client.post("/api/auction/snapshot/jobs?limit=2")
    assert provider.started.wait(timeout=1) is True
    second_response = client.post("/api/auction/snapshot/jobs?limit=2")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_payload = first_response.json()
    second_payload = second_response.json()
    assert second_payload["job_id"] == first_payload["job_id"]

    provider.release.set()
    for _ in range(30):
        completed_payload = client.get(
            f"/api/auction/snapshot/jobs/{first_payload['job_id']}"
        ).json()
        if completed_payload["status"] == "success":
            break
        sleep(0.05)

    assert provider.ranking_calls == [100]


def test_auction_timeline_returns_locked_observation_points(tmp_path: Path) -> None:
    provider = CountingMarketRankingsProvider()
    client = _client(tmp_path, market_overview_provider=provider)
    app.state.auction_now = datetime(2026, 7, 1, 9, 20, 2)

    try:
        refresh_response = client.get("/api/auction/snapshot?limit=2&refresh=true")
        timeline_response = client.get("/api/auction/timeline?limit=2")
    finally:
        delattr(app.state, "auction_now")

    assert refresh_response.status_code == 200
    assert timeline_response.status_code == 200
    payload = timeline_response.json()
    first_point = payload["points"][0]
    assert first_point["label"] == "09:20"
    assert first_point["snapshot_status"] == "captured"
    assert first_point["items"][0]["symbol"] == "300001.SZ"
    assert payload["points"][1]["snapshot_status"] == "waiting"
    assert provider.ranking_calls == [100]


def test_startup_auction_sampler_respects_disabled_state(tmp_path: Path) -> None:
    _client(tmp_path)
    if hasattr(app.state, "auction_sampler"):
        delattr(app.state, "auction_sampler")

    startup_auction_sampler()

    assert not hasattr(app.state, "auction_sampler")
    shutdown_auction_sampler()


def test_startup_sector_workbench_sampler_respects_disabled_state(tmp_path: Path) -> None:
    _client(tmp_path)
    if hasattr(app.state, "sector_workbench_sampler"):
        delattr(app.state, "sector_workbench_sampler")

    startup_sector_workbench_sampler()

    assert not hasattr(app.state, "sector_workbench_sampler")
    shutdown_sector_workbench_sampler()


def test_auction_review_latest_returns_404_before_summary(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/auction/review/latest")

    assert response.status_code == 404


def test_auction_review_returns_archived_records_for_trade_date(tmp_path: Path) -> None:
    client = _client(tmp_path, market_overview_provider=CountingMarketRankingsProvider())
    app.state.auction_now = datetime(2026, 7, 1, 9, 25, 0)

    try:
        snapshot_response = client.get("/api/auction/snapshot?limit=2&refresh=true")
        review_response = client.get("/api/auction/review?trade_date=2026-07-01")
    finally:
        delattr(app.state, "auction_now")

    assert snapshot_response.status_code == 200
    assert review_response.status_code == 200
    payload = review_response.json()
    assert payload["trade_date"] == "2026-07-01"
    assert payload["record_count"] == 2
    assert payload["records"][0]["symbol"] == "300001.SZ"
    assert "量能活跃" in payload["records"][0]["rule_tags"]


def test_auction_review_finalize_saves_latest_summary(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        kline_provider=AuctionReviewKlineProvider(),
        market_overview_provider=CountingMarketRankingsProvider(),
    )
    app.state.auction_now = datetime(2026, 7, 1, 9, 25, 0)

    try:
        client.get("/api/auction/snapshot?limit=2&refresh=true")
        finalize_response = client.post("/api/auction/review/finalize?trade_date=2026-07-01")
        latest_response = client.get("/api/auction/review/latest")
    finally:
        delattr(app.state, "auction_now")

    assert finalize_response.status_code == 200
    assert latest_response.status_code == 200
    payload = latest_response.json()
    assert payload["trade_date"] == "2026-07-01"
    assert payload["record_count"] == 2
    assert payload["data_incomplete_count"] == 2
    assert payload["records"][0]["day_result"]["close_pct"] == 8.0
    assert payload["buckets"]


def test_auction_review_finalize_seeds_records_from_latest_snapshot(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        kline_provider=AuctionReviewKlineProvider(),
        market_overview_provider=CountingMarketRankingsProvider(),
    )
    app.state.auction_now = datetime(2026, 7, 1, 10, 0, 0)

    try:
        client.get("/api/auction/snapshot?limit=2&refresh=true")
        finalize_response = client.post("/api/auction/review/finalize?trade_date=2026-06-26")
    finally:
        delattr(app.state, "auction_now")

    assert finalize_response.status_code == 200
    payload = finalize_response.json()
    assert payload["trade_date"] == "2026-06-26"
    assert payload["record_count"] == 2
    assert payload["records"][0]["selected_at_label"] == "manual"


def test_auction_review_finalize_expands_existing_manual_records(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        kline_provider=AuctionReviewKlineProvider(),
        market_overview_provider=CountingMarketRankingsProvider(),
    )
    app.state.auction_now = datetime(2026, 7, 1, 10, 0, 0)

    try:
        client.get("/api/auction/snapshot?limit=1&refresh=true")
        first_response = client.post("/api/auction/review/finalize?trade_date=2026-06-26")
        client.get("/api/auction/snapshot?limit=2&refresh=true")
        second_response = client.post("/api/auction/review/finalize?trade_date=2026-06-26")
    finally:
        delattr(app.state, "auction_now")

    assert first_response.status_code == 200
    assert first_response.json()["record_count"] == 1
    assert second_response.status_code == 200
    assert second_response.json()["record_count"] == 2


def test_auction_review_backfill_reports_unavailable_without_verified_source(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/auction/review/backfill?start_date=2026-06-01&end_date=2026-06-05&max_days=3")

    assert response.status_code == 200
    assert response.json()["status"] == "data_unavailable"


def test_sector_radar_returns_inflow_and_outflow_rankings(tmp_path: Path) -> None:
    client = _client(tmp_path, market_overview_provider=FakeMarketOverviewProvider())

    response = client.get("/api/sectors/radar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-26"
    assert payload["capital_flow_status"] == "estimated"
    assert payload["flow_source"] == "东方财富行业板块涨跌额估算"
    assert payload["inflow"][0]["name"] == "存储芯片"
    assert payload["inflow"][0]["net_flow_cny"] > 0
    assert payload["outflow"][0]["name"] == "消费电子"
    assert payload["outflow"][0]["net_flow_cny"] < 0
    assert payload["source_status"][0]["source"] == "东方财富全A指数"


def test_sector_radar_endpoint_reuses_cached_provider_result(tmp_path: Path) -> None:
    provider = CountingSectorRadarProvider()
    client = _client(tmp_path, market_overview_provider=provider)

    first = client.get("/api/sectors/radar?limit=2")
    second = client.get("/api/sectors/radar?limit=2")
    third = client.get("/api/sectors/radar?limit=3")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200
    assert provider.radar_calls == [2, 3]


def test_sector_radar_falls_back_to_tdx_when_primary_source_is_empty(tmp_path: Path) -> None:
    provider = FakeTdxSectorRadarProvider()
    client = _client(tmp_path, market_overview_provider=EmptySectorRadarProvider())
    app.state.tdx_provider = provider

    response = client.get("/api/sectors/radar?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["flow_source"] == "通达信MCP涨停概念集中度估算"
    assert payload["inflow"][0]["name"] == "半导体"
    assert payload["source_status"][0]["source"] == "empty fake板块资金流"
    assert payload["source_status"][1]["source"] == "通达信MCP涨停概念"
    assert provider.calls == [5]


def test_sector_radar_falls_back_to_tickflow_industry_aggregation_when_primary_sources_are_empty(tmp_path: Path) -> None:
    client = _client(tmp_path, market_overview_provider=EmptySectorRadarProvider())
    app.state.tdx_provider = FailingTdxSectorRadarProvider()

    response = client.get("/api/sectors/radar?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["flow_source"] == "TickFlow全A实时行情行业聚合"
    assert payload["inflow"][0]["name"] == "电池"
    assert payload["inflow"][0]["net_flow_cny"] > 0
    assert {item["name"] for item in payload["inflow"]} >= {"机器人", "电池"}
    assert payload["outflow"] == []
    assert payload["source_status"][0]["source"] == "empty fake板块资金流"
    assert payload["source_status"][1]["source"] == "通达信MCP板块兜底"
    assert payload["source_status"][2]["source"] == "TickFlow行业聚合"


def test_sector_workbench_endpoint_returns_theme_mode_and_source_status(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _seed_sector_theme_rows(tmp_path)
    app.state.sector_now = datetime(2026, 7, 3, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    response = client.get("/api/sectors/workbench?mode=strength&scope=auto&limit=5&stock_limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "strength"
    assert payload["scope"] == "theme"
    assert payload["themes"][0]["name"] == "机器人"
    assert payload["selected_themes"][0] == "机器人"
    assert payload["series"][0]["points"]
    assert payload["stocks"][0]["symbol"] == "300001.SZ"
    assert payload["source_status"][0]["status"] == "success"


def test_sector_workbench_endpoint_explicit_industry_scope_ignores_theme_snapshot_status(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _seed_sector_theme_rows(tmp_path)
    app.state.sector_now = datetime(2026, 7, 3, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    response = client.get("/api/sectors/workbench?mode=strength&scope=industry&limit=5&stock_limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "industry"
    assert payload["themes"][0]["scope"] == "industry"
    assert payload["source_status"][0]["source"] == "TickFlow行业聚合"
    assert all(item["source"] != "题材快照" for item in payload["source_status"])


def test_sector_workbench_endpoint_falls_back_to_concept_tags_when_tdx_theme_rows_unavailable(tmp_path: Path) -> None:
    client = _client(tmp_path, concept_provider=FakeConceptTagProvider())
    _seed_sector_theme_rows(
        tmp_path,
        source="东财 slist 概念归属",
        rows=[
            {
                "代码": "300001.SZ",
                "名称": "涨幅一号",
                "所属行业": "机器人",
                "所属概念": "AI眼镜;机器人概念",
                "连续涨停天数": 2,
                "封单金额": 12000,
            },
            {
                "代码": "300002.SZ",
                "名称": "涨幅二号",
                "所属行业": "电池",
                "所属概念": "存储芯片;先进封装",
                "连续涨停天数": 1,
                "封单金额": 3000,
            },
        ],
    )

    response = client.get("/api/sectors/workbench?mode=strength&scope=auto&limit=5&stock_limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "theme"
    assert payload["themes"][0]["limit_up_count"] > 0
    assert {item["name"] for item in payload["themes"]} >= {"AI眼镜", "机器人概念", "存储芯片"}
    assert all(not item["name"].endswith("板块") for item in payload["themes"])
    assert payload["source_status"][0]["source"] == "东财 slist 概念归属"


def test_plate_rotation_reference_endpoint_returns_theme_system(tmp_path: Path) -> None:
    client = _client(tmp_path)
    provider = FakePlateRotationReferenceProvider()
    app.state.plate_rotation_reference_provider = provider

    response = client.get("/api/sectors/plate-reference?limit=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "kaipan"
    assert [item["name"] for item in payload["themes"]] == ["机器人", "ST板块"]
    assert payload["themes"][0]["code"] == "801159"
    assert payload["themes"][0]["score"] == 35630
    assert payload["source_status"][0]["status"] == "success"
    assert provider.calls == [(2, "kaipan", 20)]


def test_sector_workbench_endpoint_does_not_block_on_theme_refresh_when_snapshot_missing(tmp_path: Path) -> None:
    candidate_provider = FailingIfCalledCandidateProvider()
    quote_provider = CountingIntradayQuoteProvider()
    client = _client(
        tmp_path,
        candidate_provider=candidate_provider,
        concept_provider=FakeConceptTagProvider(),
        quote_provider=quote_provider,
    )
    app.state.tdx_provider = FakeTdxSectorRadarProvider()
    app.state.sector_theme_rows_async_refresh_disabled = True

    response = client.get("/api/sectors/workbench?mode=strength&scope=auto&limit=5&stock_limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert candidate_provider.calls == 0
    assert quote_provider.intraday_calls == 0
    assert payload["scope"] == "industry"
    assert payload["source_status"][0]["source"] == "题材快照"
    assert payload["source_status"][0]["status"] == "stale"
    assert "后台题材快照未就绪" in payload["source_status"][0]["detail"]


def test_refresh_sector_theme_rows_persists_theme_snapshot(tmp_path: Path) -> None:
    _client(tmp_path, concept_provider=FakeConceptTagProvider())
    app.state.tdx_provider = FakeTdxSectorRadarProvider()

    rows, status = _refresh_sector_theme_rows(trade_date=datetime.now().astimezone().date().isoformat())
    stored_rows, stored_status = app.state.sector_theme_rows_store.load(datetime.now().astimezone().date().isoformat())

    assert rows
    assert status is not None
    assert status.source == "东财 slist 概念归属"
    assert stored_rows == rows
    assert stored_status is not None
    assert stored_status.source == "东财 slist 概念归属"


def test_sector_workbench_endpoint_schedules_tickflow_intraday_history_when_missing(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeLiveQuoteProvider())
    _seed_sector_theme_rows(tmp_path)

    response = client.get("/api/sectors/workbench?mode=strength&scope=auto&limit=5&stock_limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert any(
        item["source"] == "TickFlow 当日分钟线" and item["status"] == "stale"
        for item in payload["source_status"]
    )


def test_sector_workbench_endpoint_does_not_block_on_intraday_refresh_when_history_missing(tmp_path: Path) -> None:
    quote_provider = CountingIntradayQuoteProvider()
    client = _client(tmp_path, quote_provider=quote_provider)
    _seed_sector_theme_rows(tmp_path)
    app.state.sector_intraday_async_refresh_disabled = True

    response = client.get("/api/sectors/workbench?mode=strength&scope=auto&limit=5&stock_limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert quote_provider.intraday_calls == 0
    assert any(
        item["source"] == "TickFlow 当日分钟线" and item["status"] == "stale"
        for item in payload["source_status"]
    )


def test_sector_workbench_endpoint_does_not_persist_after_hours_snapshot_samples(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=CountingIntradayQuoteProvider())
    _seed_sector_theme_rows(tmp_path)
    app.state.sector_intraday_async_refresh_disabled = True
    app.state.sector_now = datetime(2026, 7, 3, 19, 31, tzinfo=ZoneInfo("Asia/Shanghai"))

    response = client.get("/api/sectors/workbench?mode=strength&scope=auto&limit=5&stock_limit=10")

    assert response.status_code == 200
    assert [
        point["time"]
        for series in response.json()["series"]
        for point in series["points"]
        if point["time"] == "19:31"
    ] == []
    assert not (tmp_path / "sectors" / "2026-07-03.json").exists()


def test_sector_workbench_endpoint_caches_tickflow_intraday_history(tmp_path: Path) -> None:
    quote_provider = CountingIntradayQuoteProvider()
    client = _client(tmp_path, quote_provider=quote_provider)
    _seed_sector_theme_rows(tmp_path)
    app.state.sector_now = datetime(2026, 7, 3, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    first = client.get("/api/sectors/workbench?mode=strength&scope=auto&limit=5&stock_limit=10")
    second = client.get("/api/sectors/workbench?mode=strength&scope=auto&limit=5&stock_limit=10")

    assert first.status_code == 200
    assert second.status_code == 200
    assert quote_provider.intraday_calls == 1


def test_sector_workbench_endpoint_caches_tickflow_intraday_failure(tmp_path: Path) -> None:
    quote_provider = FailingIntradayQuoteProvider()
    client = _client(tmp_path, quote_provider=quote_provider)
    _seed_sector_theme_rows(tmp_path)
    app.state.sector_now = datetime(2026, 7, 3, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    first = client.get("/api/sectors/workbench?mode=strength&scope=auto&limit=5&stock_limit=10")
    second = client.get("/api/sectors/workbench?mode=strength&scope=auto&limit=5&stock_limit=10")

    assert first.status_code == 200
    assert second.status_code == 200
    assert quote_provider.intraday_calls == 1
    assert any(
        item["source"] == "TickFlow 当日分钟线"
        and item["status"] == "failed"
        and "rate limited" in item["detail"]
        for item in second.json()["source_status"]
    )


def test_sector_workbench_status_endpoint_reports_local_cache_without_heavy_refresh(tmp_path: Path) -> None:
    quote_provider = CountingIntradayQuoteProvider()
    client = _client(tmp_path, quote_provider=quote_provider)
    _seed_sector_theme_rows(tmp_path)
    app.state.sector_intraday_async_refresh_disabled = True
    app.state.sector_now = datetime(2026, 7, 3, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    workbench = client.get("/api/sectors/workbench?mode=strength&scope=auto&limit=5&stock_limit=10")
    workbench_payload = workbench.json()
    response = client.get(f"/api/sectors/workbench/status?trade_date={workbench_payload['trade_date']}")

    assert workbench.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == workbench_payload["trade_date"]
    assert payload["sample_window_open"] is True
    assert payload["sampler_enabled"] is False
    assert payload["sampler_running"] is False
    assert payload["cache"]["sample_count"] > 0
    assert payload["cache"]["latest_sampled_at"] == "2026-07-03T10:30:00+08:00"
    assert payload["cache"]["sample_sources"] == ["snapshot"]
    assert payload["source_status"][0]["source"] == "板块分时持久化"
    assert quote_provider.intraday_calls == 0


def test_sector_workbench_endpoint_falls_back_to_sector_radar_when_rankings_fail(tmp_path: Path) -> None:
    client = _client(tmp_path, market_overview_provider=FailingMarketRankingsProvider())

    response = client.get("/api/sectors/workbench?mode=strength&scope=auto&limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["themes"][0]["name"] == "存储芯片"
    assert payload["stocks"] == []
    assert payload["source_status"][0]["source"] == "板块雷达兜底"


def test_screen_run_returns_items_and_persists_latest_without_empty_status(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/screen/runs", json={"trade_date": "2026-06-11", "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-11"
    assert payload["items"][0]["status"] == "focus"
    assert payload["items"][0]["industry"] == "消费电子"
    assert payload["items"][0]["severe_abnormal_warning"] == "triggered"
    assert payload["items"][0]["negative_news_status"] == "triggered"
    assert payload["items"][0]["negative_news_flags"] == [
        "负面新闻待核验: 2026-06-12 春秋电子收到监管函（东方财富）"
    ]
    assert all(item["status"] != "empty" for item in payload["items"])
    assert payload["watchlist_risk_items"][0]["risk_action"] == "empty"
    assert payload["watchlist_risk_items"][0]["severe_abnormal_warning"] == "unknown"
    assert payload["watchlist_risk_items"][0]["negative_news_status"] == "clear"

    latest_response = client.get("/api/screen/runs/latest")
    assert latest_response.status_code == 200
    assert latest_response.json()["trade_date"] == "2026-06-11"
    assert (tmp_path / "latest.json").exists()


def test_screen_run_respects_scan_limit_before_fetching_klines(tmp_path: Path) -> None:
    kline_provider = CountingKlineProvider()
    client = _client(
        tmp_path,
        candidate_provider=LargeCandidateProvider(count=50),
        kline_provider=kline_provider,
    )

    response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 12},
    )

    assert response.status_code == 200
    scanned_candidates = [symbol for symbol in kline_provider.symbols if symbol.startswith("600")]
    assert len(scanned_candidates) == 12
    assert "002000.SZ" in kline_provider.symbols
    payload = response.json()
    assert len(payload["items"]) == 10
    assert "本次分析 12/50" in payload["source_status"][0]["detail"]


def test_screen_run_uses_wider_default_scan_limit(tmp_path: Path) -> None:
    kline_provider = CountingKlineProvider()
    client = _client(
        tmp_path,
        candidate_provider=LargeCandidateProvider(count=200),
        kline_provider=kline_provider,
    )

    response = client.post("/api/screen/runs", json={"trade_date": "2026-06-11", "limit": 10})

    assert response.status_code == 200
    scanned_candidates = [symbol for symbol in kline_provider.symbols if symbol.startswith("600")]
    assert len(scanned_candidates) == 160
    payload = response.json()
    assert payload["gsgf_funnel"]["scan_limit_count"] == 160
    assert "本次分析 160/200" in payload["source_status"][0]["detail"]


def test_screen_run_job_runs_in_background_and_persists_latest(tmp_path: Path) -> None:
    kline_provider = BlockingKlineProvider()
    client = _client(tmp_path, kline_provider=kline_provider)

    response = client.post(
        "/api/screen/runs/jobs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 4},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "screen_run"
    assert payload["status"] in {"pending", "running"}
    assert payload["result"] is None
    assert kline_provider.started.wait(timeout=1) is True

    kline_provider.release.set()
    completed_payload = payload
    for _ in range(30):
        completed_payload = client.get(f"/api/screen/runs/jobs/{payload['job_id']}").json()
        if completed_payload["status"] == "success":
            break
        sleep(0.05)

    assert completed_payload["status"] == "success"
    assert completed_payload["result"]["trade_date"] == "2026-06-11"
    assert len(completed_payload["result"]["items"]) > 0
    latest_response = client.get("/api/screen/runs/latest")
    assert latest_response.status_code == 200
    assert latest_response.json()["trade_date"] == "2026-06-11"


def test_screen_run_job_reuses_active_job(tmp_path: Path) -> None:
    kline_provider = BlockingKlineProvider()
    client = _client(tmp_path, kline_provider=kline_provider)

    first_response = client.post(
        "/api/screen/runs/jobs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 4},
    )
    assert first_response.status_code == 200
    assert kline_provider.started.wait(timeout=1) is True

    second_response = client.post(
        "/api/screen/runs/jobs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 4},
    )

    assert second_response.status_code == 200
    assert second_response.json()["job_id"] == first_response.json()["job_id"]
    kline_provider.release.set()


def test_screen_run_is_stable_when_candidate_source_order_changes(tmp_path: Path) -> None:
    client = _client(tmp_path, candidate_provider=UnstableOrderCandidateProvider())

    first_response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 2, "scan_limit": 2},
    )
    second_response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 2, "scan_limit": 2},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_symbols = [item["symbol"] for item in first_response.json()["items"]]
    second_symbols = [item["symbol"] for item in second_response.json()["items"]]
    assert first_symbols == ["600001.SH", "600002.SH"]
    assert second_symbols == first_symbols


def test_screen_run_preserves_ranked_candidate_order_before_scan_limit(tmp_path: Path) -> None:
    kline_provider = CountingKlineProvider()
    client = _client(
        tmp_path,
        candidate_provider=RankedCandidateProvider(),
        kline_provider=kline_provider,
    )

    response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 2, "scan_limit": 2},
    )

    assert response.status_code == 200
    scanned_candidates = [symbol for symbol in kline_provider.symbols if symbol.startswith("600")]
    assert scanned_candidates == ["600003.SH", "600001.SH"]


def test_screen_run_filters_by_market_cap_industry_and_market_type(tmp_path: Path) -> None:
    client = _client(tmp_path, candidate_provider=AdvancedFilterCandidateProvider())

    response = client.post(
        "/api/screen/runs",
        json={
            "trade_date": "2026-06-11",
            "limit": 10,
            "scan_limit": 10,
            "filters": {
                "min_market_cap_billion": 100,
                "max_market_cap_billion": 150,
                "industries": ["消费电子"],
                "market_types": ["main"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["symbol"] for item in payload["items"]] == ["603890.SH"]
    assert "筛选后 1/4" in payload["source_status"][0]["detail"]


def test_screen_run_filters_by_kdj_j_max_after_kline_analysis(tmp_path: Path) -> None:
    client = _client(tmp_path, candidate_provider=AdvancedFilterCandidateProvider())

    response = client.post(
        "/api/screen/runs",
        json={
            "trade_date": "2026-06-11",
            "limit": 10,
            "scan_limit": 10,
            "filters": {"kdj_j_max": 0},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert "KDJ-J<0" in payload["source_status"][0]["detail"]


def test_screen_run_scores_industry_strength_without_overriding_trend_risk(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        candidate_provider=IndustryClusterCandidateProvider(),
        kline_provider=IndustryClusterKlineProvider(),
    )

    response = client.post("/api/screen/runs", json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 4})

    assert response.status_code == 200
    payload = response.json()
    clustered_item = next(item for item in payload["items"] if item["symbol"] == "603890.SH")
    weak_item = next(item for item in payload["items"] if item["symbol"] == "603891.SH")
    solo_item = next(item for item in payload["items"] if item["symbol"] == "002000.SZ")
    assert clustered_item["industry_strength"] == "strong"
    assert clustered_item["industry_score"] == 15
    assert clustered_item["industry_rank"] == 1
    assert "板块强度加分" in clustered_item["rule_hits"]
    assert weak_item["industry_strength"] == "strong"
    assert weak_item["status"] == "wait_pullback"
    assert solo_item["industry_strength"] == "neutral"
    assert solo_item["industry_score"] == 0


def test_screen_run_accepts_gsgf_strategy_and_returns_metadata(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 10, "strategy": "gsgf"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy"] == "gsgf"
    assert payload["gsgf_model_version"] == "gsgf-v2"
    assert payload["sort_version"] == "gsgf-sort-v1"
    assert payload["gsgf_funnel"]["candidate_pool_count"] >= len(payload["items"])
    assert "final_displayed_count" in payload["gsgf_funnel"]
    assert "gsgf_observation_items" in payload
    assert payload["items"][0]["gsgf"]["total_score"] >= 0
    assert payload["items"][0]["gsgf"]["final_status"] in {"确认买点", "候选", "低吸观察", "观察", "减仓", "回避"}
    assert "setup_score" in payload["items"][0]["gsgf"]
    assert "confirm_score" in payload["items"][0]["gsgf"]
    assert "evidence_refs" in payload["items"][0]["gsgf"]
    assert "diagnostics" in payload["items"][0]["gsgf"]


def test_gsgf_backtest_returns_bucketed_forward_stats(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/gsgf/backtest",
        json={"symbols": ["603890.SH"], "windows": [1, 3], "min_history": 60, "count": 90},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["windows"] == [1, 3]
    assert payload["sample_count"] > 0
    assert payload["source_status"][0]["source"] == "股是股非回测"
    assert payload["buckets"][0]["status"] in {"确认买点", "候选", "低吸观察", "观察", "减仓", "回避"}
    assert payload["buckets"][0]["windows"][0]["window_days"] == 1
    assert payload["buckets"][0]["windows"][0]["sample_count"] > 0
    assert "avg_return_pct" in payload["buckets"][0]["windows"][0]


def test_gsgf_calibration_returns_real_data_bucket_summary(tmp_path: Path) -> None:
    client = _client(tmp_path, kline_provider=FakeCalibrationKlineProvider())

    response = client.post(
        "/api/gsgf/calibration",
        json={"trade_dates": ["2026-01-28"], "windows": [1, 3], "scan_limit": 2, "count": 90},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_dates"] == ["2026-01-28"]
    assert payload["windows"] == [1, 3]
    assert payload["scanned_count"] == 2
    assert payload["target_sample_count"] > 0
    assert payload["buckets"][0]["sample_count"] > 0
    assert payload["unique_symbol_buckets"][0]["sample_count"] > 0
    assert payload["samples"][0]["symbol"] in {"603890.SH", "002000.SZ"}
    assert "realized_return_pct" in payload["samples"][0]["windows"][0]


def test_gsgf_trade_plan_endpoint_returns_operational_guidance(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/gsgf/trade-plan",
        json={
            "analysis": {
                "total_score": 76,
                "action": "strong_candidate",
                "final_status": "确认买点",
                "zone": "a_zone",
                "volume_structure": "three_yang_controls_three_yin",
                "setup_type": "B区A点",
                "setup_score": 20,
                "confirm_type": "放量突破确认",
                "confirm_score": 35,
                "risk_flags": [],
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "确认买点"
    assert any("持有优于追涨" in item for item in payload["holder_guidance"])
    assert any("等分歧低吸" in item for item in payload["empty_position_guidance"])
    assert payload["holder_guidance"] != payload["empty_position_guidance"]
    assert "不构成收益承诺" in payload["research_note"]


def test_gsgf_review_endpoints_persist_and_recheck_latest_screen_run(tmp_path: Path) -> None:
    client = _client(tmp_path)
    screen_response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 10, "strategy": "gsgf"},
    )
    assert screen_response.status_code == 200

    snapshot_response = client.post("/api/gsgf/review/snapshots/latest")
    assert snapshot_response.status_code == 200
    snapshot_payload = snapshot_response.json()
    assert snapshot_payload["saved_count"] == 0

    summary_response = client.post("/api/gsgf/review/recheck", json={"windows": [1, 3], "count": 90})
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["record_count"] > 0
    assert summary_payload["windows"] == [1, 3]
    assert summary_payload["buckets"][0]["sample_count"] > 0
    assert "realized_return_pct" in summary_payload["items"][0]["windows"][0]
    assert (tmp_path / "gsgf_review" / "snapshots.jsonl").exists()


def test_screen_run_auto_saves_gsgf_review_snapshot(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 10, "strategy": "gsgf"},
    )

    assert response.status_code == 200
    records = (tmp_path / "gsgf_review" / "snapshots.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(records) > 0


def test_screen_run_respects_disabled_gsgf_auto_snapshot(tmp_path: Path) -> None:
    client = _client(tmp_path)
    settings_response = client.put(
        "/api/settings",
        json={
            "candidate_provider": "recent_limit_up",
            "kline_provider": "tickflow",
            "quote_provider": "tickflow",
            "tickflow_base_url": "https://api.example.test",
            "provider_timeout_seconds": 3.5,
            "gsgf_auto_review": {"auto_snapshot_enabled": False},
        },
    )
    assert settings_response.status_code == 200

    response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 10, "strategy": "gsgf"},
    )

    assert response.status_code == 200
    assert not (tmp_path / "gsgf_review" / "snapshots.jsonl").exists()


def test_gsgf_review_latest_endpoint_returns_persisted_summary(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 10, "strategy": "gsgf"},
    )
    client.post("/api/gsgf/review/recheck", json={"windows": [1, 3], "count": 90})

    response = client.get("/api/gsgf/review/latest")

    assert response.status_code == 200
    assert response.json()["record_count"] > 0


def test_gsgf_calibration_job_endpoint_returns_job_status(tmp_path: Path) -> None:
    client = _client(tmp_path, kline_provider=FakeCalibrationKlineProvider())

    response = client.post(
        "/api/gsgf/calibration/jobs",
        json={"trade_dates": ["2026-01-28"], "windows": [1, 3], "scan_limit": 2, "count": 90},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "gsgf_calibration"
    assert payload["job_id"]


def test_recent_screen_trade_dates_reads_saved_runs(tmp_path: Path) -> None:
    from app.main import _recent_screen_trade_dates

    client = _client(tmp_path)
    client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-10", "limit": 10, "scan_limit": 10, "strategy": "gsgf"},
    )
    client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 10, "strategy": "gsgf"},
    )

    assert _recent_screen_trade_dates(2) == ["2026-06-10", "2026-06-11"]


def test_gsgf_health_endpoint_returns_summary(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/gsgf/health")

    assert response.status_code == 200
    assert "summary_text" in response.json()


def test_screen_run_accepts_combined_strategy(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 10, "strategy": "combined"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy"] == "combined"
    assert payload["sort_version"] == "combined-sort-v1"


def test_screen_run_rejects_candidate_source_failure(tmp_path: Path) -> None:
    client = _client(tmp_path, candidate_provider=FailingCandidateProvider())

    response = client.post("/api/screen/runs", json={"trade_date": "2026-06-11", "limit": 10})

    assert response.status_code == 503
    assert "候选池数据源失败" in response.json()["detail"]


def test_watchlist_gsgf_status_returns_structure_triggers(tmp_path: Path) -> None:
    client = _client(tmp_path)
    app.state.watchlist_path.write_text(
        "603890.SH 春秋电子 | group=观察 | industry=消费电子",
        encoding="utf-8",
    )

    response = client.get("/api/watchlist/gsgf-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["symbol"] == "603890.SH"
    assert payload["items"][0]["gsgf"]["model_version"] == "gsgf-v2"


def test_latest_returns_404_before_first_run(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/screen/runs/latest")

    assert response.status_code == 404


def test_intraday_snapshot_uses_latest_screen_run_symbols_without_empty_status(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeLiveQuoteProvider())
    screen_response = client.post("/api/screen/runs", json={"trade_date": "2026-06-11", "limit": 10})
    assert screen_response.status_code == 200

    response = client.post("/api/intraday/snapshot", json={"limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"][0]["source"] == "TickFlow 实时行情"
    assert payload["source_status"][1]["source"] == "TickFlow 当日分钟线"
    assert payload["items"][0]["symbol"] == "603890.SH"
    assert payload["items"][0]["industry"] == "消费电子"
    assert payload["items"][0]["action"] == "reduce"
    assert "早盘涨幅超过7%" in payload["items"][0]["signals"]
    assert all(item["action"] != "empty" for item in payload["items"])


def test_intraday_snapshot_confirms_gsgf_buy_point_with_intraday_ma(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeGsgfConfirmQuoteProvider())

    response = client.post(
        "/api/intraday/snapshot",
        json={
            "symbols": ["603890.SH"],
            "limit": 10,
            "gsgf_context": {
                "603890.SH": {
                    "final_status": "确认买点",
                    "confirm_type": "放量突破确认",
                    "risk_flags": [],
                }
            },
        },
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["gsgf_intraday_confirmation"] == "盘中确认"
    assert "GSGF确认买点：站稳日内均线" in item["signals"]
    assert "GSGF确认信号：放量突破确认" in item["signals"]


def test_intraday_snapshot_confirms_gsgf_low_buy_after_recovery(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeGsgfLowBuyQuoteProvider())

    response = client.post(
        "/api/intraday/snapshot",
        json={
            "symbols": ["603890.SH"],
            "limit": 10,
            "gsgf_context": {
                "603890.SH": {
                    "final_status": "低吸观察",
                    "setup_type": "双星止跌",
                    "risk_flags": [],
                }
            },
        },
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["gsgf_intraday_confirmation"] == "低吸确认"
    assert item["action"] == "low_buy_watch"
    assert "GSGF低吸观察：急跌后收回日内均线" in item["signals"]


def test_intraday_snapshot_confirms_gsgf_reduce_when_strength_fades(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeLiveQuoteProvider())

    response = client.post(
        "/api/intraday/snapshot",
        json={
            "symbols": ["603890.SH"],
            "limit": 10,
            "gsgf_context": {
                "603890.SH": {
                    "final_status": "减仓",
                    "risk_flags": ["高位巨量长上影"],
                }
            },
        },
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["gsgf_intraday_confirmation"] in {"减仓确认", "风险失效"}
    assert item["action"] in {"reduce", "avoid_chase"}
    assert any("GSGF" in signal for signal in item["signals"])


def test_intraday_snapshot_requires_symbols_or_latest_screen_run(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeLiveQuoteProvider())

    response = client.post("/api/intraday/snapshot", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "no screen run"


def test_intraday_snapshot_accepts_watchlist_text_groups_and_tags(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeLiveQuoteProvider())

    response = client.post(
        "/api/intraday/snapshot",
        json={"watchlist_text": "[高标]\n603890 春秋电子 #AI #回踩 行业=消费电子", "limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["symbol"] == "603890.SH"
    assert payload["items"][0]["name"] == "春秋电子"
    assert payload["items"][0]["industry"] == "消费电子"
    assert payload["items"][0]["group"] == "高标"
    assert payload["items"][0]["tags"] == ["AI", "回踩"]


def test_watchlist_pool_can_be_saved_and_used_for_intraday(tmp_path: Path) -> None:
    client = _client(tmp_path, quote_provider=FakeLiveQuoteProvider())

    save_response = client.put(
        "/api/watchlist/pool",
        json={"content": "[高标]\n603890 春秋电子 #AI #回踩"},
    )
    assert save_response.status_code == 200
    assert save_response.json()["items"][0]["group"] == "高标"

    get_response = client.get("/api/watchlist/pool")
    assert get_response.status_code == 200
    assert get_response.json()["content"] == "[高标]\n603890 春秋电子 #AI #回踩"

    intraday_response = client.post(
        "/api/intraday/snapshot",
        json={"use_watchlist_pool": True, "limit": 10},
    )

    assert intraday_response.status_code == 200
    payload = intraday_response.json()
    assert payload["items"][0]["symbol"] == "603890.SH"
    assert payload["items"][0]["group"] == "高标"
    assert payload["items"][0]["tags"] == ["AI", "回踩"]


def test_watchlist_pool_item_can_be_added_to_custom_group_and_updated(tmp_path: Path) -> None:
    client = _client(tmp_path)

    first_response = client.post(
        "/api/watchlist/pool/items",
        json={
            "symbol": "603890.SH",
            "name": "春秋电子",
            "industry": "消费电子",
            "group": "mlcc",
            "note": "观察10日线承接",
        },
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert "[mlcc]" in first_payload["content"]
    assert first_payload["items"][0]["symbol"] == "603890.SH"
    assert first_payload["items"][0]["group"] == "mlcc"
    assert first_payload["items"][0]["industry"] == "消费电子"
    assert first_payload["items"][0]["note"] == "观察10日线承接"

    second_response = client.post(
        "/api/watchlist/pool/items",
        json={
            "symbol": "603890",
            "name": "春秋电子",
            "industry": "元器件",
            "group": "存储芯片",
            "tags": ["强势"],
            "note": "更新为存储芯片观察",
        },
    )

    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["content"].count("603890.SH") == 1
    assert "[存储芯片]" in second_payload["content"]
    assert second_payload["items"][0]["group"] == "存储芯片"
    assert second_payload["items"][0]["industry"] == "元器件"
    assert second_payload["items"][0]["tags"] == ["强势"]
    assert second_payload["items"][0]["note"] == "更新为存储芯片观察"
