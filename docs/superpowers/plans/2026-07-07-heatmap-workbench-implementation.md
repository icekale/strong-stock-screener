# Heatmap Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a native `/heatmap` A-share market heatmap workbench with FastAPI-backed data, Canvas treemap rendering, StockMaster-style controls, stock detail navigation, and explicit live/fallback source status.

**Architecture:** Keep heatmap data assembly in a focused FastAPI provider and expose only typed API responses to the Next.js app. The web route owns filters and workbench layout, the Canvas component owns drawing and pointer interaction, and pure TypeScript helpers own treemap geometry, colors, labels, hrefs, and query mapping. Upstream `wenyuanw/a-share-heatmap` is used as MIT-attributed reference/data seed, not as an iframe or copied standalone page.

**Tech Stack:** FastAPI, Pydantic, httpx, pytest, Next.js App Router, React 19, Ant Design, Tailwind, Canvas 2D, Node test runner.

---

## File Map

- `apps/api/app/models.py`: add heatmap literals and response models beside existing Pydantic models.
- `apps/api/app/providers/heatmap.py`: load baseline universe, fetch live quotes/summary, build treemap responses, maintain short provider-local caches, and return fallback data with source status.
- `apps/api/app/data/heatmap/market-heatmap-fallback.json`: MIT-attributed baseline stock universe copied from upstream.
- `apps/api/app/data/heatmap/market-heatmap-subboards.json`: MIT-attributed industry/sub-board mapping copied from upstream.
- `apps/api/app/data/heatmap/LICENSE.a-share-heatmap`: upstream MIT license text.
- `apps/api/tests/test_heatmap_provider.py`: provider model, filter, quote merge, cache, and fallback tests.
- `apps/api/tests/test_heatmap_api.py`: FastAPI endpoint tests for `/api/heatmap/*`.
- `apps/api/app/main.py`: wire provider singleton and three API routes.
- `apps/web/lib/types.ts`: mirror heatmap response types.
- `apps/web/lib/api.ts`: add heatmap fetch helpers.
- `apps/web/lib/heatmap.ts`: labels, query params, source status labels, stock detail href wrapper, and formatting helpers.
- `apps/web/lib/heatmap.test.ts`: pure frontend helper tests.
- `apps/web/lib/stockNavigation.ts`: add `from=heatmap` return context.
- `apps/web/lib/stockNavigation.test.ts`: cover heatmap stock detail round trip.
- `apps/web/app/heatmap/heatmapTreemap.ts`: pure treemap geometry, color, hit testing, and viewport transforms.
- `apps/web/app/heatmap/heatmapTreemap.test.ts`: layout/color/hit-test tests.
- `apps/web/app/heatmap/HeatmapCanvas.tsx`: Canvas rendering and interactions.
- `apps/web/app/heatmap/HeatmapWorkspace.tsx`: data loading, filters, refresh, layout, toolbar, detail rail, and empty/error states.
- `apps/web/app/heatmap/page.tsx`: dynamic client page with skeleton.
- `apps/web/components/AppShell.tsx`: add left-nav `热图` entry and selected route logic.
- `scripts/smoke-ui.mjs`: include `/heatmap` in smoke routes.
- `README.md`: add heatmap module and upstream attribution.

## Task 1: Backend Models And MIT Data Seed

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/data/heatmap/market-heatmap-fallback.json`
- Create: `apps/api/app/data/heatmap/market-heatmap-subboards.json`
- Create: `apps/api/app/data/heatmap/LICENSE.a-share-heatmap`
- Test: `apps/api/tests/test_heatmap_provider.py`

- [ ] **Step 1: Write the failing model/data tests**

Create `apps/api/tests/test_heatmap_provider.py` with the imports and first tests below:

```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.models import HeatmapBoardNode, HeatmapStockNode, HeatmapSummary, HeatmapTreemapResponse


def test_heatmap_models_expose_source_status_and_stock_metrics() -> None:
    response = HeatmapTreemapResponse(
        market="all",
        period="day",
        size_mode="market_cap",
        trend="all",
        board=None,
        summary=HeatmapSummary(
            trade_date="2026-07-07",
            updated_at="2026-07-07T10:30:00+08:00",
            stock_count=1,
            board_count=1,
            advance_count=1,
            decline_count=0,
            unchanged_count=0,
            turnover_cny=120_000_000,
            previous_turnover_cny=100_000_000,
            turnover_change_pct=20,
        ),
        nodes=[
            HeatmapBoardNode(
                key="半导体",
                name="半导体",
                value=12_000_000_000,
                stock_count=1,
                advance_count=1,
                decline_count=0,
                unchanged_count=0,
                avg_change_pct=3.2,
                turnover_cny=120_000_000,
                children=[
                    HeatmapStockNode(
                        symbol="603690.SH",
                        code="603690",
                        name="至纯科技",
                        industry="半导体",
                        sub_industry="半导体设备",
                        exchange="SH",
                        market="sse",
                        price=28.4,
                        change_pct=3.2,
                        week_change_pct=8.1,
                        month_change_pct=12.4,
                        year_change_pct=30.5,
                        turnover_cny=120_000_000,
                        circulating_market_cap_cny=12_000_000_000,
                        total_market_cap_cny=15_000_000_000,
                        value=12_000_000_000,
                        quote_time="2026-07-07T10:30:00+08:00",
                    )
                ],
            )
        ],
        source_status=[{"source": "东方财富热图行情", "status": "success", "detail": "测试"}],
        generated_at="2026-07-07T10:30:01+08:00",
    )

    dumped = response.model_dump(mode="json")
    assert dumped["source_status"][0]["status"] == "success"
    assert dumped["nodes"][0]["children"][0]["symbol"] == "603690.SH"
    assert dumped["nodes"][0]["children"][0]["market"] == "sse"


def test_upstream_heatmap_license_seed_is_present() -> None:
    data_dir = Path("app/data/heatmap")
    assert (data_dir / "market-heatmap-fallback.json").exists()
    assert (data_dir / "market-heatmap-subboards.json").exists()
    license_text = (data_dir / "LICENSE.a-share-heatmap").read_text(encoding="utf-8")
    assert "MIT License" in license_text
    assert "A-Share Heatmap contributors" in license_text
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/python -m pytest tests/test_heatmap_provider.py -q
```

Expected: FAIL because the heatmap models and data files do not exist.

- [ ] **Step 3: Add heatmap literals and Pydantic models**

Add these definitions to `apps/api/app/models.py` near the other Literal aliases and response classes:

```python
HeatmapPeriodKey = Literal["day", "week", "month", "year"]
HeatmapMarketKey = Literal["all", "sse", "szse", "hs300", "zza500", "cyb", "kcb"]
HeatmapSizeMode = Literal["market_cap", "turnover"]
HeatmapTrendFilter = Literal["all", "rise", "fall"]
HeatmapExchange = Literal["SH", "SZ", "BJ"]
```

Add the response classes:

```python
class HeatmapStockNode(BaseModel):
    symbol: str
    code: str
    name: str
    industry: str
    sub_industry: str | None = None
    exchange: HeatmapExchange
    market: HeatmapMarketKey
    price: float | None = None
    change_pct: float = 0
    week_change_pct: float | None = None
    month_change_pct: float | None = None
    year_change_pct: float | None = None
    turnover_cny: float | None = None
    circulating_market_cap_cny: float | None = None
    total_market_cap_cny: float | None = None
    value: float = 0
    quote_time: str | None = None


class HeatmapBoardNode(BaseModel):
    key: str
    name: str
    value: float = 0
    stock_count: int = 0
    advance_count: int = 0
    decline_count: int = 0
    unchanged_count: int = 0
    avg_change_pct: float | None = None
    turnover_cny: float | None = None
    children: list[HeatmapStockNode] = Field(default_factory=list)


class HeatmapSummary(BaseModel):
    trade_date: str | None = None
    updated_at: str
    stock_count: int = 0
    board_count: int = 0
    advance_count: int = 0
    decline_count: int = 0
    unchanged_count: int = 0
    turnover_cny: float | None = None
    previous_turnover_cny: float | None = None
    turnover_change_pct: float | None = None
    index_change_pct: float | None = None


class HeatmapTreemapResponse(BaseModel):
    market: HeatmapMarketKey
    period: HeatmapPeriodKey
    size_mode: HeatmapSizeMode
    trend: HeatmapTrendFilter = "all"
    board: str | None = None
    summary: HeatmapSummary
    nodes: list[HeatmapBoardNode] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str


class HeatmapQuoteItem(BaseModel):
    symbol: str
    price: float | None = None
    change_pct: float = 0
    turnover_cny: float | None = None
    quote_time: str | None = None


class HeatmapQuotesResponse(BaseModel):
    market: HeatmapMarketKey
    period: HeatmapPeriodKey
    quotes: dict[str, HeatmapQuoteItem] = Field(default_factory=dict)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str


class HeatmapOverviewItem(BaseModel):
    market: HeatmapMarketKey
    name: str
    change_pct: float | None = None
    stock_count: int = 0
    updated_at: str


class HeatmapOverviewResponse(BaseModel):
    period: HeatmapPeriodKey
    markets: list[HeatmapOverviewItem] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str
```

- [ ] **Step 4: Copy upstream MIT data seed**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener
mkdir -p apps/api/app/data/heatmap
cp /tmp/a-share-heatmap/src/lib/data/market-heatmap-fallback.json apps/api/app/data/heatmap/market-heatmap-fallback.json
cp /tmp/a-share-heatmap/src/lib/data/market-heatmap-subboards.json apps/api/app/data/heatmap/market-heatmap-subboards.json
cp /tmp/a-share-heatmap/LICENSE apps/api/app/data/heatmap/LICENSE.a-share-heatmap
```

Expected:

```bash
ls -lh apps/api/app/data/heatmap
```

shows `market-heatmap-fallback.json`, `market-heatmap-subboards.json`, and `LICENSE.a-share-heatmap`.

- [ ] **Step 5: Run the model/data tests**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/python -m pytest tests/test_heatmap_provider.py::test_heatmap_models_expose_source_status_and_stock_metrics tests/test_heatmap_provider.py::test_upstream_heatmap_license_seed_is_present -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/api/app/models.py apps/api/app/data/heatmap apps/api/tests/test_heatmap_provider.py
git commit -m "feat: add heatmap backend models and data seed"
```

## Task 2: Backend Heatmap Provider

**Files:**
- Create: `apps/api/app/providers/heatmap.py`
- Modify: `apps/api/tests/test_heatmap_provider.py`

- [ ] **Step 1: Write failing provider tests**

Append these tests to `apps/api/tests/test_heatmap_provider.py`:

```python
from app.providers.heatmap import (
    HeatmapBaselineStock,
    HeatmapProvider,
    HeatmapQuoteSnapshot,
    HeatmapQuoteValue,
    HeatmapSummarySnapshot,
)


def _fixed_now() -> datetime:
    return datetime(2026, 7, 7, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))


def _baseline() -> list[HeatmapBaselineStock]:
    return [
        HeatmapBaselineStock(
            symbol="603690.SH",
            code="603690",
            name="至纯科技",
            exchange="SH",
            market="sse",
            industry="半导体",
            sub_industry="半导体设备",
            circulating_market_cap_cny=12_000_000_000,
            total_market_cap_cny=15_000_000_000,
        ),
        HeatmapBaselineStock(
            symbol="300475.SZ",
            code="300475",
            name="香农芯创",
            exchange="SZ",
            market="cyb",
            industry="半导体",
            sub_industry="存储芯片",
            circulating_market_cap_cny=8_000_000_000,
            total_market_cap_cny=10_000_000_000,
        ),
        HeatmapBaselineStock(
            symbol="600000.SH",
            code="600000",
            name="浦发银行",
            exchange="SH",
            market="sse",
            industry="银行",
            sub_industry="股份制银行",
            circulating_market_cap_cny=180_000_000_000,
            total_market_cap_cny=190_000_000_000,
        ),
    ]


def _quote_snapshot() -> HeatmapQuoteSnapshot:
    return HeatmapQuoteSnapshot(
        updated_at="2026-07-07T10:30:00+08:00",
        values={
            "603690.SH": HeatmapQuoteValue(
                price=28.4,
                changes={"day": 3.2, "week": 8.1, "month": 12.4, "year": 30.5},
                turnover_cny=120_000_000,
                quote_time="2026-07-07T10:30:00+08:00",
            ),
            "300475.SZ": HeatmapQuoteValue(
                price=54.2,
                changes={"day": -1.8, "week": 2.1, "month": 7.4, "year": 18.0},
                turnover_cny=90_000_000,
                quote_time="2026-07-07T10:30:00+08:00",
            ),
            "600000.SH": HeatmapQuoteValue(
                price=9.8,
                changes={"day": 0.0, "week": -1.0, "month": 1.2, "year": 6.0},
                turnover_cny=60_000_000,
                quote_time="2026-07-07T10:30:00+08:00",
            ),
        },
        source_status=[{"source": "fake quotes", "status": "success", "detail": "3 rows"}],
    )


def _summary_snapshot() -> HeatmapSummarySnapshot:
    return HeatmapSummarySnapshot(
        trade_date="2026-07-07",
        updated_at="2026-07-07T10:30:00+08:00",
        advance_count=1,
        decline_count=1,
        unchanged_count=1,
        turnover_cny=270_000_000,
        previous_turnover_cny=300_000_000,
        source_status=[{"source": "fake summary", "status": "success", "detail": "ok"}],
    )


def test_heatmap_provider_builds_board_nodes_from_quotes() -> None:
    provider = HeatmapProvider(
        baseline_stocks=_baseline(),
        quote_loader=lambda symbols: _quote_snapshot(),
        summary_loader=_summary_snapshot,
        now=_fixed_now,
    )

    response = provider.get_treemap(
        market="all",
        period="day",
        size_mode="market_cap",
        trend="all",
        board=None,
        limit=20,
    )

    assert response.summary.stock_count == 3
    assert response.summary.board_count == 2
    assert response.nodes[0].name == "银行"
    assert response.nodes[0].value == 180_000_000_000
    assert response.nodes[1].name == "半导体"
    assert {child.symbol for child in response.nodes[1].children} == {"603690.SH", "300475.SZ"}
    assert response.source_status[0].status == "success"


def test_heatmap_provider_applies_market_board_trend_and_size_filters() -> None:
    provider = HeatmapProvider(
        baseline_stocks=_baseline(),
        quote_loader=lambda symbols: _quote_snapshot(),
        summary_loader=_summary_snapshot,
        now=_fixed_now,
    )

    response = provider.get_treemap(
        market="sse",
        period="day",
        size_mode="turnover",
        trend="rise",
        board="半导体",
        limit=20,
    )

    assert response.summary.stock_count == 1
    assert response.nodes[0].name == "半导体"
    assert response.nodes[0].value == 120_000_000
    assert response.nodes[0].children[0].symbol == "603690.SH"


def test_heatmap_provider_returns_fallback_status_when_live_quote_loader_fails() -> None:
    def failing_quote_loader(symbols: list[str]) -> HeatmapQuoteSnapshot:
        raise RuntimeError("network down")

    provider = HeatmapProvider(
        baseline_stocks=_baseline(),
        quote_loader=failing_quote_loader,
        summary_loader=_summary_snapshot,
        now=_fixed_now,
    )

    response = provider.get_treemap(
        market="all",
        period="day",
        size_mode="market_cap",
        trend="all",
        board=None,
        limit=20,
    )

    assert response.nodes
    assert any(status.source == "东方财富热图行情" and status.status == "failed" for status in response.source_status)
    assert any(status.source == "热图内置样本" and status.status == "stale" for status in response.source_status)
```

- [ ] **Step 2: Run the provider tests and verify they fail**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/python -m pytest tests/test_heatmap_provider.py -q
```

Expected: FAIL because `app.providers.heatmap` does not exist.

- [ ] **Step 3: Implement provider data types and constructor**

Create `apps/api/app/providers/heatmap.py` with this structure:

```python
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Callable
from zoneinfo import ZoneInfo

import httpx

from app.models import (
    HeatmapBoardNode,
    HeatmapMarketKey,
    HeatmapOverviewItem,
    HeatmapOverviewResponse,
    HeatmapPeriodKey,
    HeatmapQuoteItem,
    HeatmapQuotesResponse,
    HeatmapSizeMode,
    HeatmapStockNode,
    HeatmapSummary,
    HeatmapTreemapResponse,
    HeatmapTrendFilter,
    StrongStockSourceStatus,
)


@dataclass(frozen=True)
class HeatmapBaselineStock:
    symbol: str
    code: str
    name: str
    exchange: str
    market: HeatmapMarketKey
    industry: str
    sub_industry: str | None
    circulating_market_cap_cny: float | None
    total_market_cap_cny: float | None


@dataclass(frozen=True)
class HeatmapQuoteValue:
    price: float | None
    changes: dict[HeatmapPeriodKey, float]
    turnover_cny: float | None
    quote_time: str | None = None


@dataclass(frozen=True)
class HeatmapQuoteSnapshot:
    updated_at: str
    values: dict[str, HeatmapQuoteValue]
    source_status: list[StrongStockSourceStatus | dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class HeatmapSummarySnapshot:
    trade_date: str | None
    updated_at: str
    advance_count: int | None
    decline_count: int | None
    unchanged_count: int | None
    turnover_cny: float | None
    previous_turnover_cny: float | None
    source_status: list[StrongStockSourceStatus | dict[str, str]] = field(default_factory=list)


class HeatmapProvider:
    source_name = "东方财富热图行情"

    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        baseline_stocks: list[HeatmapBaselineStock] | None = None,
        quote_loader: Callable[[list[str]], HeatmapQuoteSnapshot] | None = None,
        summary_loader: Callable[[], HeatmapSummarySnapshot] | None = None,
        timeout_seconds: float = 8,
        now: Callable[[], datetime] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.data_dir = data_dir or Path(__file__).resolve().parents[1] / "data" / "heatmap"
        self.timeout_seconds = timeout_seconds
        self.now = now or (lambda: datetime.now(ZoneInfo("Asia/Shanghai")))
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client(timeout=timeout_seconds)
        self._baseline_stocks = baseline_stocks
        self._quote_loader = quote_loader or self._fetch_eastmoney_quotes
        self._summary_loader = summary_loader or self._fetch_summary
        self._quote_cache: tuple[float, HeatmapQuoteSnapshot] | None = None
        self._summary_cache: tuple[float, HeatmapSummarySnapshot] | None = None

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()
```

- [ ] **Step 4: Implement baseline loading and response building**

Add these provider methods:

```python
    def get_treemap(
        self,
        *,
        market: HeatmapMarketKey,
        period: HeatmapPeriodKey,
        size_mode: HeatmapSizeMode,
        trend: HeatmapTrendFilter,
        board: str | None,
        limit: int,
    ) -> HeatmapTreemapResponse:
        generated_at = self.now().isoformat()
        baseline = self._load_baseline_stocks()
        symbols = [stock.symbol for stock in baseline]
        quote_snapshot, quote_status = self._safe_quote_snapshot(symbols)
        summary_snapshot, summary_status = self._safe_summary_snapshot()
        stocks = self._build_stock_nodes(
            baseline=baseline,
            quotes=quote_snapshot.values,
            market=market,
            period=period,
            size_mode=size_mode,
            trend=trend,
            board=board,
            limit=limit,
        )
        nodes = self._group_boards(stocks)
        summary = self._build_summary(
            nodes=nodes,
            snapshot=summary_snapshot,
            updated_at=quote_snapshot.updated_at,
        )
        return HeatmapTreemapResponse(
            market=market,
            period=period,
            size_mode=size_mode,
            trend=trend,
            board=board,
            summary=summary,
            nodes=nodes,
            source_status=_dedupe_statuses([*quote_status, *summary_status]),
            generated_at=generated_at,
        )

    def get_quotes(self, *, market: HeatmapMarketKey, period: HeatmapPeriodKey) -> HeatmapQuotesResponse:
        baseline = self._filter_market(self._load_baseline_stocks(), market)
        quote_snapshot, quote_status = self._safe_quote_snapshot([stock.symbol for stock in baseline])
        return HeatmapQuotesResponse(
            market=market,
            period=period,
            quotes={
                symbol: HeatmapQuoteItem(
                    symbol=symbol,
                    price=value.price,
                    change_pct=value.changes.get(period, value.changes.get("day", 0)),
                    turnover_cny=value.turnover_cny,
                    quote_time=value.quote_time,
                )
                for symbol, value in quote_snapshot.values.items()
            },
            source_status=_dedupe_statuses(quote_status),
            generated_at=self.now().isoformat(),
        )

    def get_overview(self, *, period: HeatmapPeriodKey) -> HeatmapOverviewResponse:
        baseline = self._load_baseline_stocks()
        quote_snapshot, quote_status = self._safe_quote_snapshot([stock.symbol for stock in baseline])
        markets: list[HeatmapOverviewItem] = []
        for key, name in MARKET_LABELS.items():
            stocks = self._filter_market(baseline, key)
            changes = [
                quote_snapshot.values[stock.symbol].changes.get(period, 0)
                for stock in stocks
                if stock.symbol in quote_snapshot.values
            ]
            markets.append(
                HeatmapOverviewItem(
                    market=key,
                    name=name,
                    change_pct=round(sum(changes) / len(changes), 2) if changes else None,
                    stock_count=len(stocks),
                    updated_at=quote_snapshot.updated_at,
                )
            )
        return HeatmapOverviewResponse(
            period=period,
            markets=markets,
            source_status=_dedupe_statuses(quote_status),
            generated_at=self.now().isoformat(),
        )
```

Use `circulating_market_cap_cny` for `size_mode="market_cap"` and `turnover_cny` for `size_mode="turnover"`. Sort boards and stocks by descending value so large areas are stable.

Add these private helpers in the same provider file so the public methods above have no hidden dependencies:

```python
    def _load_baseline_stocks(self) -> list[HeatmapBaselineStock]:
        if self._baseline_stocks is not None:
            return self._baseline_stocks
        fallback = json.loads((self.data_dir / "market-heatmap-fallback.json").read_text(encoding="utf-8"))
        subboards = json.loads((self.data_dir / "market-heatmap-subboards.json").read_text(encoding="utf-8"))
        mapped: list[HeatmapBaselineStock] = []
        for row in fallback.get("stocks", []):
            code = str(row.get("code", "")).zfill(6)
            exchange = str(row.get("exchange", "SH"))
            symbol = f"{code}.{exchange}"
            subboard = subboards.get("subboards", {}).get(code) or subboards.get("subboards", {}).get(symbol) or {}
            mapped.append(
                HeatmapBaselineStock(
                    symbol=symbol,
                    code=code,
                    name=str(row.get("name") or code),
                    exchange=exchange,
                    market=_market_for_stock(code=code, exchange=exchange),
                    industry=str(row.get("boardName") or subboard.get("sectorName") or "未标注"),
                    sub_industry=str(row.get("subBoardName") or subboard.get("subBoardName") or "") or None,
                    circulating_market_cap_cny=_number(row.get("floatMarketCap")),
                    total_market_cap_cny=_number(row.get("totalMarketCap")),
                )
            )
        self._baseline_stocks = mapped
        return mapped

    def _build_stock_nodes(
        self,
        *,
        baseline: list[HeatmapBaselineStock],
        quotes: dict[str, HeatmapQuoteValue],
        market: HeatmapMarketKey,
        period: HeatmapPeriodKey,
        size_mode: HeatmapSizeMode,
        trend: HeatmapTrendFilter,
        board: str | None,
        limit: int,
    ) -> list[HeatmapStockNode]:
        stocks: list[HeatmapStockNode] = []
        for base in self._filter_market(baseline, market):
            if board and base.industry != board:
                continue
            quote = quotes.get(base.symbol)
            change_pct = quote.changes.get(period, quote.changes.get("day", 0)) if quote else 0
            if trend == "rise" and change_pct <= FLAT_THRESHOLD:
                continue
            if trend == "fall" and change_pct >= -FLAT_THRESHOLD:
                continue
            value = quote.turnover_cny if size_mode == "turnover" and quote else base.circulating_market_cap_cny
            stocks.append(
                HeatmapStockNode(
                    symbol=base.symbol,
                    code=base.code,
                    name=base.name,
                    industry=base.industry,
                    sub_industry=base.sub_industry,
                    exchange=base.exchange,
                    market=base.market,
                    price=quote.price if quote else None,
                    change_pct=round(change_pct, 2),
                    week_change_pct=quote.changes.get("week") if quote else None,
                    month_change_pct=quote.changes.get("month") if quote else None,
                    year_change_pct=quote.changes.get("year") if quote else None,
                    turnover_cny=quote.turnover_cny if quote else None,
                    circulating_market_cap_cny=base.circulating_market_cap_cny,
                    total_market_cap_cny=base.total_market_cap_cny,
                    value=max(1, value or 1),
                    quote_time=quote.quote_time if quote else None,
                )
            )
        return sorted(stocks, key=lambda item: item.value, reverse=True)[:limit]

    def _group_boards(self, stocks: list[HeatmapStockNode]) -> list[HeatmapBoardNode]:
        grouped: dict[str, list[HeatmapStockNode]] = defaultdict(list)
        for stock in stocks:
            grouped[stock.industry or "未标注"].append(stock)
        nodes: list[HeatmapBoardNode] = []
        for name, children in grouped.items():
            changes = [stock.change_pct for stock in children]
            nodes.append(
                HeatmapBoardNode(
                    key=name,
                    name=name,
                    value=sum(stock.value for stock in children),
                    stock_count=len(children),
                    advance_count=sum(1 for stock in children if stock.change_pct > FLAT_THRESHOLD),
                    decline_count=sum(1 for stock in children if stock.change_pct < -FLAT_THRESHOLD),
                    unchanged_count=sum(1 for stock in children if -FLAT_THRESHOLD <= stock.change_pct <= FLAT_THRESHOLD),
                    avg_change_pct=round(sum(changes) / len(changes), 2) if changes else None,
                    turnover_cny=sum(stock.turnover_cny or 0 for stock in children),
                    children=sorted(children, key=lambda item: item.value, reverse=True),
                )
            )
        return sorted(nodes, key=lambda node: node.value, reverse=True)

    def _build_summary(
        self,
        *,
        nodes: list[HeatmapBoardNode],
        snapshot: HeatmapSummarySnapshot,
        updated_at: str,
    ) -> HeatmapSummary:
        stock_count = sum(node.stock_count for node in nodes)
        turnover = snapshot.turnover_cny
        previous = snapshot.previous_turnover_cny
        return HeatmapSummary(
            trade_date=snapshot.trade_date,
            updated_at=snapshot.updated_at or updated_at,
            stock_count=stock_count,
            board_count=len(nodes),
            advance_count=sum(node.advance_count for node in nodes),
            decline_count=sum(node.decline_count for node in nodes),
            unchanged_count=sum(node.unchanged_count for node in nodes),
            turnover_cny=turnover,
            previous_turnover_cny=previous,
            turnover_change_pct=round((turnover - previous) / previous * 100, 2) if turnover is not None and previous else None,
        )

    def _filter_market(self, baseline: list[HeatmapBaselineStock], market: HeatmapMarketKey) -> list[HeatmapBaselineStock]:
        if market == "all":
            return baseline
        return [stock for stock in baseline if _stock_in_market(stock, market)]
```

Add module-level helpers:

```python
def _dedupe_statuses(statuses: list[StrongStockSourceStatus | dict[str, str]]) -> list[StrongStockSourceStatus]:
    deduped: dict[tuple[str, str], StrongStockSourceStatus] = {}
    for status in statuses:
        item = status if isinstance(status, StrongStockSourceStatus) else StrongStockSourceStatus(**status)
        deduped[(item.source, item.status)] = item
    return list(deduped.values())


def _number(value: object) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _market_for_stock(*, code: str, exchange: str) -> HeatmapMarketKey:
    if code.startswith("300"):
        return "cyb"
    if code.startswith("688"):
        return "kcb"
    if exchange == "SH":
        return "sse"
    if exchange == "SZ":
        return "szse"
    return "all"


def _stock_in_market(stock: HeatmapBaselineStock, market: HeatmapMarketKey) -> bool:
    if market in ("sse", "szse", "cyb", "kcb"):
        return stock.market == market
    if market == "hs300":
        return (stock.total_market_cap_cny or 0) >= 80_000_000_000
    if market == "zza500":
        cap = stock.total_market_cap_cny or 0
        return 15_000_000_000 <= cap < 80_000_000_000
    return True
```

- [ ] **Step 5: Implement live loaders, short caches, and fallback**

Add these rules to `apps/api/app/providers/heatmap.py`:

```python
QUOTE_CACHE_SECONDS = 8
SUMMARY_CACHE_SECONDS = 8
FLAT_THRESHOLD = 0.1
MARKET_LABELS: dict[HeatmapMarketKey, str] = {
    "all": "全 A",
    "sse": "上证 A 股",
    "szse": "深证 A 股",
    "hs300": "沪深 300",
    "zza500": "中证 A500",
    "cyb": "创业板",
    "kcb": "科创板",
}
```

Implement `_safe_quote_snapshot()` so it:

1. Returns a fresh cached quote snapshot when cache age is under `QUOTE_CACHE_SECONDS`.
2. Calls `_quote_loader(symbols)` when cache is stale.
3. On loader failure, builds quote values from the bundled baseline snapshot fields and returns two statuses:

```python
StrongStockSourceStatus(
    source="东方财富热图行情",
    status="failed",
    detail=f"实时行情获取失败: {exc.__class__.__name__}; 使用内置样本",
)
StrongStockSourceStatus(
    source="热图内置样本",
    status="stale",
    detail="来自 wenyuanw/a-share-heatmap MIT 样本数据，仅用于降级展示",
)
```

Implement `_fetch_eastmoney_quotes()` with Eastmoney `push2.eastmoney.com/api/qt/ulist.np/get`, batched at 180 symbols, fields `f2,f3,f6,f12,f13,f14,f24,f25,f109,f110,f124,f127,f160`, and symbol secid mapping `SH -> 1.code`, `SZ/BJ -> 0.code`.

Implement `_fetch_summary()` using the existing heatmap spec source order:

1. Try Tonghuashun advance/flat/decline and turnover summary endpoints.
2. If either call fails, return a snapshot with null turnover fields and a `failed` status for the failed source.
3. Keep the response renderable when summary data fails.

- [ ] **Step 6: Run provider tests**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/python -m pytest tests/test_heatmap_provider.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/api/app/providers/heatmap.py apps/api/tests/test_heatmap_provider.py
git commit -m "feat: build heatmap provider"
```

## Task 3: FastAPI Heatmap Endpoints

**Files:**
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_heatmap_api.py`

- [ ] **Step 1: Write failing API tests**

Create `apps/api/tests/test_heatmap_api.py`:

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    HeatmapBoardNode,
    HeatmapOverviewItem,
    HeatmapOverviewResponse,
    HeatmapQuoteItem,
    HeatmapQuotesResponse,
    HeatmapStockNode,
    HeatmapSummary,
    HeatmapTreemapResponse,
    StrongStockSourceStatus,
)


class FakeHeatmapProvider:
    def get_treemap(self, *, market, period, size_mode, trend, board, limit):
        return HeatmapTreemapResponse(
            market=market,
            period=period,
            size_mode=size_mode,
            trend=trend,
            board=board,
            summary=HeatmapSummary(
                trade_date="2026-07-07",
                updated_at="2026-07-07T10:30:00+08:00",
                stock_count=1,
                board_count=1,
                advance_count=1,
                decline_count=0,
                unchanged_count=0,
                turnover_cny=120_000_000,
            ),
            nodes=[
                HeatmapBoardNode(
                    key="半导体",
                    name="半导体",
                    value=120_000_000,
                    stock_count=1,
                    advance_count=1,
                    children=[
                        HeatmapStockNode(
                            symbol="603690.SH",
                            code="603690",
                            name="至纯科技",
                            industry="半导体",
                            sub_industry="半导体设备",
                            exchange="SH",
                            market="sse",
                            price=28.4,
                            change_pct=3.2,
                            turnover_cny=120_000_000,
                            value=120_000_000,
                        )
                    ],
                )
            ],
            source_status=[StrongStockSourceStatus(source="fake", status="success", detail="ok")],
            generated_at="2026-07-07T10:30:01+08:00",
        )

    def get_quotes(self, *, market, period):
        return HeatmapQuotesResponse(
            market=market,
            period=period,
            quotes={
                "603690.SH": HeatmapQuoteItem(
                    symbol="603690.SH",
                    price=28.4,
                    change_pct=3.2,
                    turnover_cny=120_000_000,
                )
            },
            source_status=[StrongStockSourceStatus(source="fake", status="success", detail="ok")],
            generated_at="2026-07-07T10:30:01+08:00",
        )

    def get_overview(self, *, period):
        return HeatmapOverviewResponse(
            period=period,
            markets=[
                HeatmapOverviewItem(
                    market="all",
                    name="全 A",
                    change_pct=1.2,
                    stock_count=1,
                    updated_at="2026-07-07T10:30:00+08:00",
                )
            ],
            source_status=[StrongStockSourceStatus(source="fake", status="success", detail="ok")],
            generated_at="2026-07-07T10:30:01+08:00",
        )


def test_heatmap_treemap_endpoint_returns_schema_and_filters() -> None:
    app.state.heatmap_provider = FakeHeatmapProvider()
    client = TestClient(app)
    response = client.get(
        "/api/heatmap/treemap?market=sse&period=day&size_mode=turnover&trend=rise&board=%E5%8D%8A%E5%AF%BC%E4%BD%93&limit=50"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "sse"
    assert payload["size_mode"] == "turnover"
    assert payload["trend"] == "rise"
    assert payload["board"] == "半导体"
    assert payload["nodes"][0]["children"][0]["symbol"] == "603690.SH"
    assert payload["source_status"][0]["status"] == "success"


def test_heatmap_rejects_invalid_period() -> None:
    app.state.heatmap_provider = FakeHeatmapProvider()
    client = TestClient(app)
    response = client.get("/api/heatmap/treemap?period=quarter")

    assert response.status_code == 422


def test_heatmap_quotes_and_overview_endpoints_return_source_status() -> None:
    app.state.heatmap_provider = FakeHeatmapProvider()
    client = TestClient(app)

    quotes = client.get("/api/heatmap/quotes?market=all&period=day")
    overview = client.get("/api/heatmap/overview?period=week")

    assert quotes.status_code == 200
    assert quotes.json()["quotes"]["603690.SH"]["change_pct"] == 3.2
    assert quotes.json()["source_status"][0]["status"] == "success"
    assert overview.status_code == 200
    assert overview.json()["markets"][0]["market"] == "all"
    assert overview.json()["source_status"][0]["status"] == "success"
```

- [ ] **Step 2: Run API tests and verify they fail**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/python -m pytest tests/test_heatmap_api.py -q
```

Expected: FAIL because `/api/heatmap/*` routes are missing.

- [ ] **Step 3: Import models and provider in `main.py`**

Add heatmap types to the `from app.models import (...)` block:

```python
    HeatmapMarketKey,
    HeatmapPeriodKey,
    HeatmapSizeMode,
    HeatmapTrendFilter,
```

Add provider import:

```python
from app.providers.heatmap import HeatmapProvider
```

- [ ] **Step 4: Add provider singleton**

Add near the other provider helper functions in `apps/api/app/main.py`:

```python
def _heatmap_provider() -> HeatmapProvider:
    provider = getattr(app.state, "heatmap_provider", None)
    if provider is None:
        provider = HeatmapProvider()
        app.state.heatmap_provider = provider
    return provider
```

- [ ] **Step 5: Add API routes**

Add routes near the existing market/sector endpoints:

```python
@app.get("/api/heatmap/treemap")
def get_heatmap_treemap(
    market: HeatmapMarketKey = "all",
    period: HeatmapPeriodKey = "day",
    size_mode: HeatmapSizeMode = "market_cap",
    trend: HeatmapTrendFilter = "all",
    board: str = "",
    limit: int = 5000,
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 6000))
    result = _heatmap_provider().get_treemap(
        market=market,
        period=period,
        size_mode=size_mode,
        trend=trend,
        board=board.strip() or None,
        limit=bounded_limit,
    )
    return result.model_dump(mode="json")


@app.get("/api/heatmap/quotes")
def get_heatmap_quotes(
    market: HeatmapMarketKey = "all",
    period: HeatmapPeriodKey = "day",
) -> dict[str, object]:
    result = _heatmap_provider().get_quotes(market=market, period=period)
    return result.model_dump(mode="json")


@app.get("/api/heatmap/overview")
def get_heatmap_overview(period: HeatmapPeriodKey = "day") -> dict[str, object]:
    result = _heatmap_provider().get_overview(period=period)
    return result.model_dump(mode="json")
```

- [ ] **Step 6: Run API tests**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/python -m pytest tests/test_heatmap_api.py tests/test_heatmap_provider.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/api/app/main.py apps/api/tests/test_heatmap_api.py
git commit -m "feat: expose heatmap api endpoints"
```

## Task 4: Frontend Types, API Helpers, And Stock Navigation

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Create: `apps/web/lib/heatmap.ts`
- Create: `apps/web/lib/heatmap.test.ts`
- Modify: `apps/web/lib/stockNavigation.ts`
- Modify: `apps/web/lib/stockNavigation.test.ts`

- [ ] **Step 1: Write failing frontend helper tests**

Create `apps/web/lib/heatmap.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

const {
  buildHeatmapQuery,
  formatHeatmapMoney,
  heatmapSourceStatusLabel,
  heatmapStockHref,
} = (await import(new URL("./heatmap.ts", import.meta.url).href)) as typeof import("./heatmap");

test("heatmap query maps filters to backend params", () => {
  assert.equal(
    buildHeatmapQuery({
      market: "sse",
      period: "week",
      sizeMode: "turnover",
      trend: "rise",
      board: "半导体",
      limit: 800,
    }).toString(),
    "market=sse&period=week&size_mode=turnover&trend=rise&board=%E5%8D%8A%E5%AF%BC%E4%BD%93&limit=800",
  );
});

test("heatmap money formatter keeps trading-scale units compact", () => {
  assert.equal(formatHeatmapMoney(123_000_000), "1.23亿");
  assert.equal(formatHeatmapMoney(12_300), "1.23万");
  assert.equal(formatHeatmapMoney(null), "-");
});

test("heatmap source status labels make fallback explicit", () => {
  assert.equal(heatmapSourceStatusLabel({ source: "热图内置样本", status: "stale", detail: "sample" }), "样本/过期");
  assert.equal(heatmapSourceStatusLabel({ source: "东方财富热图行情", status: "success", detail: "ok" }), "实时");
});

test("heatmap stock href returns to heatmap workbench", () => {
  assert.equal(
    heatmapStockHref({ symbol: "603690.SH", name: "至纯科技", industry: "半导体" }),
    "/stock/603690.SH?from=heatmap&name=%E8%87%B3%E7%BA%AF%E7%A7%91%E6%8A%80&industry=%E5%8D%8A%E5%AF%BC%E4%BD%93",
  );
});
```

Append to `apps/web/lib/stockNavigation.test.ts`:

```ts
test("stock detail context can return to the heatmap workbench", () => {
  assert.equal(
    buildStockDetailHref("603690.SH", {
      from: "heatmap",
      industry: "半导体",
      name: "至纯科技",
    }),
    "/stock/603690.SH?from=heatmap&name=%E8%87%B3%E7%BA%AF%E7%A7%91%E6%8A%80&industry=%E5%8D%8A%E5%AF%BC%E4%BD%93",
  );

  assert.deepEqual(resolveStockDetailContext(new URLSearchParams("from=heatmap")), {
    from: "heatmap",
    industry: null,
    name: null,
    returnHref: "/heatmap",
    returnLabel: "返回市场热图",
  });
});
```

- [ ] **Step 2: Run frontend tests and verify they fail**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
./node_modules/.bin/tsc --noEmit && node --experimental-strip-types --test lib/*.test.ts
```

Expected: FAIL because heatmap helpers and `from=heatmap` do not exist.

- [ ] **Step 3: Add frontend heatmap types**

Append to `apps/web/lib/types.ts`:

```ts
export type HeatmapPeriodKey = "day" | "week" | "month" | "year";
export type HeatmapMarketKey = "all" | "sse" | "szse" | "hs300" | "zza500" | "cyb" | "kcb";
export type HeatmapSizeMode = "market_cap" | "turnover";
export type HeatmapTrendFilter = "all" | "rise" | "fall";

export type HeatmapStockNode = {
  symbol: string;
  code: string;
  name: string;
  industry: string;
  sub_industry: string | null;
  exchange: "SH" | "SZ" | "BJ";
  market: HeatmapMarketKey;
  price: number | null;
  change_pct: number;
  week_change_pct: number | null;
  month_change_pct: number | null;
  year_change_pct: number | null;
  turnover_cny: number | null;
  circulating_market_cap_cny: number | null;
  total_market_cap_cny: number | null;
  value: number;
  quote_time: string | null;
};

export type HeatmapBoardNode = {
  key: string;
  name: string;
  value: number;
  stock_count: number;
  advance_count: number;
  decline_count: number;
  unchanged_count: number;
  avg_change_pct: number | null;
  turnover_cny: number | null;
  children: HeatmapStockNode[];
};

export type HeatmapSummary = {
  trade_date: string | null;
  updated_at: string;
  stock_count: number;
  board_count: number;
  advance_count: number;
  decline_count: number;
  unchanged_count: number;
  turnover_cny: number | null;
  previous_turnover_cny: number | null;
  turnover_change_pct: number | null;
  index_change_pct: number | null;
};

export type HeatmapTreemapResponse = {
  market: HeatmapMarketKey;
  period: HeatmapPeriodKey;
  size_mode: HeatmapSizeMode;
  trend: HeatmapTrendFilter;
  board: string | null;
  summary: HeatmapSummary;
  nodes: HeatmapBoardNode[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type HeatmapQuoteItem = {
  symbol: string;
  price: number | null;
  change_pct: number;
  turnover_cny: number | null;
  quote_time: string | null;
};

export type HeatmapQuotesResponse = {
  market: HeatmapMarketKey;
  period: HeatmapPeriodKey;
  quotes: Record<string, HeatmapQuoteItem>;
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type HeatmapOverviewItem = {
  market: HeatmapMarketKey;
  name: string;
  change_pct: number | null;
  stock_count: number;
  updated_at: string;
};

export type HeatmapOverviewResponse = {
  period: HeatmapPeriodKey;
  markets: HeatmapOverviewItem[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};
```

- [ ] **Step 4: Add `apps/web/lib/heatmap.ts`**

Create:

```ts
import { buildStockDetailHref } from "./stockNavigation";
import type {
  HeatmapMarketKey,
  HeatmapPeriodKey,
  HeatmapSizeMode,
  HeatmapTrendFilter,
  StrongStockSourceStatus,
} from "./types";

export type HeatmapQueryState = {
  market: HeatmapMarketKey;
  period: HeatmapPeriodKey;
  sizeMode: HeatmapSizeMode;
  trend: HeatmapTrendFilter;
  board: string;
  limit: number;
};

export const HEATMAP_MARKET_OPTIONS: Array<{ label: string; value: HeatmapMarketKey }> = [
  { label: "全 A", value: "all" },
  { label: "上证 A 股", value: "sse" },
  { label: "深证 A 股", value: "szse" },
  { label: "沪深 300", value: "hs300" },
  { label: "中证 A500", value: "zza500" },
  { label: "创业板", value: "cyb" },
  { label: "科创板", value: "kcb" },
];

export const HEATMAP_PERIOD_OPTIONS: Array<{ label: string; value: HeatmapPeriodKey }> = [
  { label: "日", value: "day" },
  { label: "周", value: "week" },
  { label: "月", value: "month" },
  { label: "年", value: "year" },
];

export const HEATMAP_TREND_OPTIONS: Array<{ label: string; value: HeatmapTrendFilter }> = [
  { label: "全部", value: "all" },
  { label: "上涨", value: "rise" },
  { label: "下跌", value: "fall" },
];

export function buildHeatmapQuery(state: HeatmapQueryState): URLSearchParams {
  const params = new URLSearchParams({
    market: state.market,
    period: state.period,
    size_mode: state.sizeMode,
    trend: state.trend,
    limit: String(state.limit),
  });
  const board = state.board.trim();
  if (board && board !== "全部") {
    params.set("board", board);
  }
  return params;
}

export function formatHeatmapMoney(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "-";
  }
  if (Math.abs(value) >= 100_000_000) {
    return `${(value / 100_000_000).toFixed(2)}亿`;
  }
  if (Math.abs(value) >= 10_000) {
    return `${(value / 10_000).toFixed(2)}万`;
  }
  return value.toFixed(0);
}

export function heatmapSourceStatusLabel(status: StrongStockSourceStatus): string {
  if (status.status === "success") {
    return "实时";
  }
  if (status.status === "stale") {
    return "样本/过期";
  }
  if (status.status === "failed") {
    return "失败";
  }
  if (status.status === "disabled") {
    return "未启用";
  }
  return "缺配置";
}

export function heatmapStockHref(stock: { symbol: string; name?: string | null; industry?: string | null }): string {
  return buildStockDetailHref(stock.symbol, {
    from: "heatmap",
    name: stock.name,
    industry: stock.industry,
  });
}
```

- [ ] **Step 5: Add API helpers**

Import heatmap response types in `apps/web/lib/api.ts` and add:

```ts
export async function getHeatmapTreemap(query: URLSearchParams): Promise<HeatmapTreemapResponse> {
  const response = await fetch(`${API_BASE_URL}/api/heatmap/treemap?${query.toString()}`);
  if (!response.ok) {
    throw new Error(`读取市场热图失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<HeatmapTreemapResponse>;
}

export async function getHeatmapQuotes(market: HeatmapMarketKey, period: HeatmapPeriodKey): Promise<HeatmapQuotesResponse> {
  const params = new URLSearchParams({ market, period });
  const response = await fetch(`${API_BASE_URL}/api/heatmap/quotes?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`读取热图行情失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<HeatmapQuotesResponse>;
}

export async function getHeatmapOverview(period: HeatmapPeriodKey): Promise<HeatmapOverviewResponse> {
  const params = new URLSearchParams({ period });
  const response = await fetch(`${API_BASE_URL}/api/heatmap/overview?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`读取热图概览失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<HeatmapOverviewResponse>;
}
```

- [ ] **Step 6: Add heatmap stock navigation context**

Change `apps/web/lib/stockNavigation.ts`:

```ts
export type StockDetailFrom = "auction" | "auction-model" | "heatmap" | "home" | "sectors";
```

Update `buildStockDetailHref()` trusted source condition:

```ts
if (
  context.from === "auction" ||
  context.from === "auction-model" ||
  context.from === "heatmap" ||
  context.from === "sectors"
) {
  query.set("from", context.from);
}
```

Update `resolveStockDetailContext()`:

```ts
const from: StockDetailFrom =
  source === "auction" || source === "auction-model" || source === "heatmap" || source === "sectors"
    ? source
    : "home";
```

Update return mapping:

```ts
returnHref:
  from === "auction" || from === "auction-model"
    ? "/auction"
    : from === "heatmap"
      ? "/heatmap"
      : from === "sectors"
        ? "/sectors"
        : "/",
returnLabel:
  from === "auction"
    ? "返回竞价雷达"
    : from === "auction-model"
      ? "返回竞价模型"
      : from === "heatmap"
        ? "返回市场热图"
        : from === "sectors"
          ? "返回题材工作台"
          : "返回选股工作台",
```

- [ ] **Step 7: Run frontend helper tests**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
./node_modules/.bin/tsc --noEmit && node --experimental-strip-types --test lib/*.test.ts
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/web/lib/types.ts apps/web/lib/api.ts apps/web/lib/heatmap.ts apps/web/lib/heatmap.test.ts apps/web/lib/stockNavigation.ts apps/web/lib/stockNavigation.test.ts
git commit -m "feat: add heatmap frontend data helpers"
```

## Task 5: Pure Treemap Layout And Color Math

**Files:**
- Create: `apps/web/app/heatmap/heatmapTreemap.ts`
- Create: `apps/web/app/heatmap/heatmapTreemap.test.ts`

- [ ] **Step 1: Write failing treemap tests**

Create `apps/web/app/heatmap/heatmapTreemap.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

const {
  heatmapChangeColor,
  hitTestHeatmap,
  layoutHeatmapTreemap,
  transformHeatmapPoint,
} = (await import(new URL("./heatmapTreemap.ts", import.meta.url).href)) as typeof import("./heatmapTreemap");

const nodes = [
  {
    key: "半导体",
    name: "半导体",
    value: 120,
    stock_count: 2,
    advance_count: 1,
    decline_count: 1,
    unchanged_count: 0,
    avg_change_pct: 0.8,
    turnover_cny: 100,
    children: [
      {
        symbol: "603690.SH",
        code: "603690",
        name: "至纯科技",
        industry: "半导体",
        sub_industry: "半导体设备",
        exchange: "SH",
        market: "sse",
        price: 28,
        change_pct: 3.2,
        week_change_pct: null,
        month_change_pct: null,
        year_change_pct: null,
        turnover_cny: 80,
        circulating_market_cap_cny: 100,
        total_market_cap_cny: 120,
        value: 80,
        quote_time: null,
      },
      {
        symbol: "300475.SZ",
        code: "300475",
        name: "香农芯创",
        industry: "半导体",
        sub_industry: "存储芯片",
        exchange: "SZ",
        market: "cyb",
        price: 54,
        change_pct: -1.8,
        week_change_pct: null,
        month_change_pct: null,
        year_change_pct: null,
        turnover_cny: 40,
        circulating_market_cap_cny: 60,
        total_market_cap_cny: 80,
        value: 40,
        quote_time: null,
      },
    ],
  },
];

test("layoutHeatmapTreemap produces bounded board and stock rectangles", () => {
  const layout = layoutHeatmapTreemap(nodes, { width: 1000, height: 600 });

  assert.equal(layout.boards.length, 1);
  assert.equal(layout.stocks.length, 2);
  for (const item of [...layout.boards, ...layout.stocks]) {
    assert.ok(item.x >= 0);
    assert.ok(item.y >= 0);
    assert.ok(item.x + item.width <= 1000);
    assert.ok(item.y + item.height <= 600);
    assert.ok(item.width > 0);
    assert.ok(item.height > 0);
  }
});

test("layoutHeatmapTreemap keeps tiny stocks renderable without NaN", () => {
  const tinyLayout = layoutHeatmapTreemap(
    [
      {
        ...nodes[0],
        value: 1,
        children: nodes[0].children.map((stock, index) => ({
          ...stock,
          value: index === 0 ? 0 : 0.0001,
        })),
      },
    ],
    { width: 320, height: 220 },
  );

  assert.equal(tinyLayout.stocks.length, 2);
  assert.ok(tinyLayout.stocks.every((item) => Number.isFinite(item.width) && Number.isFinite(item.height)));
});

test("heatmapChangeColor follows A-share red-rise and green-fall convention", () => {
  assert.equal(heatmapChangeColor(4).tone, "rise");
  assert.equal(heatmapChangeColor(-2).tone, "fall");
  assert.equal(heatmapChangeColor(0.02).tone, "flat");
});

test("hitTestHeatmap returns topmost stock under transformed pointer", () => {
  const layout = layoutHeatmapTreemap(nodes, { width: 1000, height: 600 });
  const first = layout.stocks[0];
  const point = transformHeatmapPoint(
    { x: first.x + first.width / 2, y: first.y + first.height / 2 },
    { scale: 1, offsetX: 0, offsetY: 0 },
  );

  assert.equal(hitTestHeatmap(layout.stocks, point)?.stock.symbol, first.stock.symbol);
});
```

- [ ] **Step 2: Run treemap tests and verify they fail**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
node --experimental-strip-types --test app/heatmap/heatmapTreemap.test.ts
```

Expected: FAIL because `heatmapTreemap.ts` does not exist.

- [ ] **Step 3: Implement layout and color helpers**

Create `apps/web/app/heatmap/heatmapTreemap.ts` with these exports:

```ts
import type { HeatmapBoardNode, HeatmapStockNode } from "../../lib/types";

export type HeatmapViewport = {
  scale: number;
  offsetX: number;
  offsetY: number;
};

export type HeatmapRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type HeatmapBoardRect = HeatmapRect & {
  board: HeatmapBoardNode;
};

export type HeatmapStockRect = HeatmapRect & {
  board: HeatmapBoardNode;
  stock: HeatmapStockNode;
};

export type HeatmapLayout = {
  boards: HeatmapBoardRect[];
  stocks: HeatmapStockRect[];
};

export function layoutHeatmapTreemap(
  nodes: HeatmapBoardNode[],
  size: { width: number; height: number },
): HeatmapLayout {
  const width = Math.max(1, size.width);
  const height = Math.max(1, size.height);
  const boards = sliceDice(
    nodes.map((board) => ({ item: board, value: Math.max(0, board.value) })),
    { x: 0, y: 0, width, height },
    "horizontal",
  ).map((rect) => ({ ...rect, board: rect.item }));

  const stocks: HeatmapStockRect[] = [];
  for (const boardRect of boards) {
    const inner = insetRect(boardRect, 4);
    const stockRects = sliceDice(
      boardRect.board.children.map((stock) => ({ item: stock, value: Math.max(0, stock.value) })),
      inner,
      inner.width >= inner.height ? "vertical" : "horizontal",
    );
    for (const stockRect of stockRects) {
      stocks.push({
        x: stockRect.x,
        y: stockRect.y,
        width: stockRect.width,
        height: stockRect.height,
        board: boardRect.board,
        stock: stockRect.item,
      });
    }
  }

  return { boards, stocks };
}

export function heatmapChangeColor(changePct: number): { tone: "rise" | "fall" | "flat"; fill: string; text: string } {
  if (changePct > 0.1) {
    return { tone: "rise", fill: riseColor(changePct), text: "#fff7f5" };
  }
  if (changePct < -0.1) {
    return { tone: "fall", fill: fallColor(changePct), text: "#f5fff7" };
  }
  return { tone: "flat", fill: "#6f6a62", text: "#fffaf2" };
}

export function hitTestHeatmap(stocks: HeatmapStockRect[], point: { x: number; y: number }): HeatmapStockRect | null {
  for (let index = stocks.length - 1; index >= 0; index -= 1) {
    const item = stocks[index];
    if (point.x >= item.x && point.x <= item.x + item.width && point.y >= item.y && point.y <= item.y + item.height) {
      return item;
    }
  }
  return null;
}

export function transformHeatmapPoint(point: { x: number; y: number }, viewport: HeatmapViewport): { x: number; y: number } {
  return {
    x: (point.x - viewport.offsetX) / viewport.scale,
    y: (point.y - viewport.offsetY) / viewport.scale,
  };
}
```

Also implement local helpers `sliceDice`, `insetRect`, `riseColor`, and `fallColor` in the same file. `sliceDice` must distribute zero-value rows using a value floor of `1` so every stock gets a finite rectangle.

Use this helper shape:

```ts
function sliceDice<T>(
  entries: Array<{ item: T; value: number }>,
  rect: HeatmapRect,
  direction: "horizontal" | "vertical",
): Array<HeatmapRect & { item: T }> {
  const visible = entries.length ? entries : [];
  const values = visible.map((entry) => Math.max(1, entry.value || 0));
  const total = values.reduce((sum, value) => sum + value, 0) || visible.length || 1;
  let cursor = direction === "horizontal" ? rect.x : rect.y;
  return visible.map((entry, index) => {
    const isLast = index === visible.length - 1;
    if (direction === "horizontal") {
      const width = isLast ? rect.x + rect.width - cursor : (rect.width * values[index]) / total;
      const result = {
        item: entry.item,
        x: cursor,
        y: rect.y,
        width: Math.max(1, width),
        height: Math.max(1, rect.height),
      };
      cursor += width;
      return result;
    }
    const height = isLast ? rect.y + rect.height - cursor : (rect.height * values[index]) / total;
    const result = {
      item: entry.item,
      x: rect.x,
      y: cursor,
      width: Math.max(1, rect.width),
      height: Math.max(1, height),
    };
    cursor += height;
    return result;
  });
}

function insetRect(rect: HeatmapRect, padding: number): HeatmapRect {
  return {
    x: rect.x + padding,
    y: rect.y + padding + 18,
    width: Math.max(1, rect.width - padding * 2),
    height: Math.max(1, rect.height - padding * 2 - 18),
  };
}

function riseColor(changePct: number): string {
  const strength = Math.min(1, Math.abs(changePct) / 10);
  const lightness = Math.round(42 + strength * 18);
  return `hsl(5 72% ${lightness}%)`;
}

function fallColor(changePct: number): string {
  const strength = Math.min(1, Math.abs(changePct) / 10);
  const lightness = Math.round(34 + strength * 14);
  return `hsl(144 44% ${lightness}%)`;
}
```

- [ ] **Step 4: Run treemap tests and all frontend pure tests**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
node --experimental-strip-types --test app/heatmap/heatmapTreemap.test.ts
./node_modules/.bin/tsc --noEmit && node --experimental-strip-types --test lib/*.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/web/app/heatmap/heatmapTreemap.ts apps/web/app/heatmap/heatmapTreemap.test.ts
git commit -m "feat: add heatmap treemap layout helpers"
```

## Task 6: Canvas Renderer And Interactions

**Files:**
- Create: `apps/web/app/heatmap/HeatmapCanvas.tsx`
- Modify: `apps/web/app/heatmap/heatmapTreemap.ts`

- [ ] **Step 1: Add Canvas component contract**

Create `apps/web/app/heatmap/HeatmapCanvas.tsx` with these props:

```tsx
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { HeatmapBoardNode, HeatmapStockNode } from "../../lib/types";
import {
  heatmapChangeColor,
  hitTestHeatmap,
  layoutHeatmapTreemap,
  transformHeatmapPoint,
  type HeatmapStockRect,
  type HeatmapViewport,
} from "./heatmapTreemap";

export type HeatmapCanvasProps = {
  nodes: HeatmapBoardNode[];
  selectedStock: HeatmapStockNode | null;
  onHoverStock: (stock: HeatmapStockNode | null) => void;
  onSelectStock: (stock: HeatmapStockNode | null) => void;
  resetKey: number;
};
```

- [ ] **Step 2: Implement drawing loop**

Implement these behaviors inside `HeatmapCanvas`:

```tsx
const canvasRef = useRef<HTMLCanvasElement | null>(null);
const wrapperRef = useRef<HTMLDivElement | null>(null);
const [viewport, setViewport] = useState<HeatmapViewport>({ scale: 1, offsetX: 0, offsetY: 0 });
const [canvasSize, setCanvasSize] = useState({ width: 1, height: 1 });

const layout = useMemo(() => layoutHeatmapTreemap(nodes, canvasSize), [canvasSize, nodes]);

useEffect(() => {
  const wrapper = wrapperRef.current;
  if (!wrapper) {
    return;
  }
  const observer = new ResizeObserver(([entry]) => {
    const rect = entry.contentRect;
    setCanvasSize({ width: Math.max(1, rect.width), height: Math.max(1, rect.height) });
  });
  observer.observe(wrapper);
  return () => observer.disconnect();
}, []);
```

The render effect must:

1. Scale for `window.devicePixelRatio`.
2. Fill canvas background with `#171512`.
3. Apply `viewport.offsetX`, `viewport.offsetY`, and `viewport.scale`.
4. Draw board labels only when board rectangles are large enough.
5. Draw stock name/code/change only when the stock rectangle has enough room.
6. Highlight selected stock with a `#fffaf2` stroke.

- [ ] **Step 3: Implement pointer, zoom, pan, and reset interactions**

Add these handlers:

```tsx
function pointerToWorld(event: React.PointerEvent<HTMLCanvasElement>) {
  const rect = event.currentTarget.getBoundingClientRect();
  return transformHeatmapPoint(
    { x: event.clientX - rect.left, y: event.clientY - rect.top },
    viewport,
  );
}

function handlePointerMove(event: React.PointerEvent<HTMLCanvasElement>) {
  if (dragStateRef.current) {
    const nextViewport = {
      ...viewport,
      offsetX: event.clientX - dragStateRef.current.startX + dragStateRef.current.offsetX,
      offsetY: event.clientY - dragStateRef.current.startY + dragStateRef.current.offsetY,
    };
    setViewport(nextViewport);
    return;
  }
  const hit = hitTestHeatmap(layout.stocks, pointerToWorld(event));
  onHoverStock(hit?.stock ?? null);
}

function handleWheel(event: React.WheelEvent<HTMLCanvasElement>) {
  event.preventDefault();
  const nextScale = Math.min(4, Math.max(0.7, viewport.scale * (event.deltaY > 0 ? 0.9 : 1.1)));
  setViewport((current) => ({ ...current, scale: nextScale }));
}
```

Use `resetKey` in an effect:

```tsx
useEffect(() => {
  setViewport({ scale: 1, offsetX: 0, offsetY: 0 });
}, [resetKey]);
```

- [ ] **Step 4: Run type check**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
./node_modules/.bin/tsc --noEmit
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/web/app/heatmap/HeatmapCanvas.tsx apps/web/app/heatmap/heatmapTreemap.ts
git commit -m "feat: render interactive heatmap canvas"
```

## Task 7: Heatmap Workspace Page And Navigation

**Files:**
- Create: `apps/web/app/heatmap/page.tsx`
- Create: `apps/web/app/heatmap/HeatmapWorkspace.tsx`
- Modify: `apps/web/components/AppShell.tsx`
- Modify: `scripts/smoke-ui.mjs`

- [ ] **Step 1: Add `/heatmap` page shell**

Create `apps/web/app/heatmap/page.tsx`:

```tsx
"use client";

import { Card, Skeleton, Typography } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";

const HeatmapWorkspace = dynamic(
  () => import("./HeatmapWorkspace").then((module) => module.HeatmapWorkspace),
  { ssr: false, loading: () => <HeatmapPlaceholder /> },
) as ComponentType;

export default function HeatmapPage() {
  return <HeatmapWorkspace />;
}

function HeatmapPlaceholder() {
  return (
    <main className="workbench-page min-h-screen p-5">
      <div className="mb-4">
        <Typography.Title className="m-0 text-[#11100e]" level={3}>
          市场热力图
        </Typography.Title>
        <Typography.Text className="workbench-muted">正在加载全市场涨跌、成交额和行业分布。</Typography.Text>
      </div>
      <section className="grid gap-3 xl:grid-cols-[240px_minmax(0,1fr)_300px]">
        <Card className="workbench-panel" size="small">
          <Skeleton active paragraph={{ rows: 8 }} title={false} />
        </Card>
        <Card className="workbench-panel min-h-[560px] min-w-0">
          <Skeleton active paragraph={{ rows: 12 }} />
        </Card>
        <Card className="workbench-panel" size="small">
          <Skeleton active paragraph={{ rows: 9 }} title={false} />
        </Card>
      </section>
    </main>
  );
}
```

- [ ] **Step 2: Implement `HeatmapWorkspace` state and data loading**

Create `apps/web/app/heatmap/HeatmapWorkspace.tsx` with:

```tsx
"use client";

import {
  DownloadOutlined,
  FullscreenOutlined,
  ReloadOutlined,
  RetweetOutlined,
} from "@ant-design/icons";
import { Alert, App, Button, Card, Empty, Segmented, Select, Skeleton, Space, Tag, Typography } from "antd";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getHeatmapTreemap } from "../../lib/api";
import {
  buildHeatmapQuery,
  formatHeatmapMoney,
  heatmapSourceStatusLabel,
  heatmapStockHref,
  HEATMAP_MARKET_OPTIONS,
  HEATMAP_PERIOD_OPTIONS,
  HEATMAP_TREND_OPTIONS,
} from "../../lib/heatmap";
import type {
  HeatmapMarketKey,
  HeatmapPeriodKey,
  HeatmapSizeMode,
  HeatmapStockNode,
  HeatmapTrendFilter,
  HeatmapTreemapResponse,
} from "../../lib/types";
import { HeatmapCanvas } from "./HeatmapCanvas";

export function HeatmapWorkspace() {
  const { message } = App.useApp();
  const canvasWrapRef = useRef<HTMLDivElement | null>(null);
  const [market, setMarket] = useState<HeatmapMarketKey>("all");
  const [period, setPeriod] = useState<HeatmapPeriodKey>("day");
  const [sizeMode, setSizeMode] = useState<HeatmapSizeMode>("market_cap");
  const [trend, setTrend] = useState<HeatmapTrendFilter>("all");
  const [board, setBoard] = useState("全部");
  const [data, setData] = useState<HeatmapTreemapResponse | null>(null);
  const [hoveredStock, setHoveredStock] = useState<HeatmapStockNode | null>(null);
  const [selectedStock, setSelectedStock] = useState<HeatmapStockNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);

  const query = useMemo(
    () => buildHeatmapQuery({ market, period, sizeMode, trend, board, limit: 5000 }),
    [board, market, period, sizeMode, trend],
  );

  const load = useCallback(async (showLoading = false) => {
    if (showLoading) {
      setLoading(true);
    }
    setRefreshing(true);
    try {
      const response = await getHeatmapTreemap(query);
      setData(response);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取市场热图失败");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [query]);

  useEffect(() => {
    void load(true);
  }, [load]);

  useEffect(() => {
    const timer = window.setInterval(() => void load(false), 15_000);
    return () => window.clearInterval(timer);
  }, [load]);
```

Continue in the same component with memoized board options:

```tsx
  const boardOptions = useMemo(
    () => ["全部", ...(data?.nodes ?? []).map((node) => node.name)].map((name) => ({ label: name, value: name })),
    [data?.nodes],
  );
  const activeStock = selectedStock ?? hoveredStock;
```

- [ ] **Step 3: Implement workbench layout**

Use this three-zone structure:

```tsx
return (
  <main className="workbench-page min-h-screen p-5">
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <Typography.Title className="m-0 text-[#11100e]" level={3}>市场热力图</Typography.Title>
        <Typography.Text className="workbench-muted">
          全 A 涨跌、成交额和行业面积分布；红涨绿跌，数据源状态在右侧显示。
        </Typography.Text>
      </div>
      <Space wrap>
        <Button icon={<ReloadOutlined />} loading={refreshing} onClick={() => void load(false)}>刷新</Button>
        <Button icon={<RetweetOutlined />} onClick={() => { setSelectedStock(null); setHoveredStock(null); setResetKey((value) => value + 1); }}>重置视图</Button>
        <Button icon={<DownloadOutlined />} onClick={handleDownload}>截图</Button>
        <Button icon={<FullscreenOutlined />} onClick={handleFullscreen}>全屏</Button>
      </Space>
    </div>

    {error ? <Alert className="mb-3" message={error} showIcon type="warning" /> : null}

    <section className="grid gap-3 xl:grid-cols-[240px_minmax(0,1fr)_300px]">
      <Card className="workbench-panel" size="small" title="筛选">
        {/* Ant Design controls from Step 4 */}
      </Card>
      <Card className="workbench-panel min-w-0" bodyStyle={{ padding: 10 }}>
        <div ref={canvasWrapRef} className="h-[calc(100vh-170px)] min-h-[520px] overflow-hidden rounded-lg border border-[#2b2925] bg-[#171512]">
          {loading && !data ? (
            <div className="p-4"><Skeleton active paragraph={{ rows: 12 }} /></div>
          ) : data?.nodes.length ? (
            <HeatmapCanvas
              nodes={data.nodes}
              selectedStock={selectedStock}
              onHoverStock={setHoveredStock}
              onSelectStock={setSelectedStock}
              resetKey={resetKey}
            />
          ) : (
            <Empty className="pt-20" description="暂无可展示热图数据" />
          )}
        </div>
      </Card>
      <Card className="workbench-panel" size="small" title="详情">
        {/* summary, active stock, legend, source status from Step 5 */}
      </Card>
    </section>
  </main>
);
```

- [ ] **Step 4: Add filter controls**

Inside the left `筛选` card, use:

```tsx
<div className="space-y-4">
  <div>
    <Typography.Text className="mb-1 block text-xs font-semibold text-[#7b756d]">市场范围</Typography.Text>
    <Select className="w-full" options={HEATMAP_MARKET_OPTIONS} value={market} onChange={setMarket} />
  </div>
  <div>
    <Typography.Text className="mb-1 block text-xs font-semibold text-[#7b756d]">行业板块</Typography.Text>
    <Select className="w-full" showSearch options={boardOptions} value={board} onChange={setBoard} />
  </div>
  <div>
    <Typography.Text className="mb-1 block text-xs font-semibold text-[#7b756d]">涨跌方向</Typography.Text>
    <Segmented block options={HEATMAP_TREND_OPTIONS} value={trend} onChange={(value) => setTrend(value as HeatmapTrendFilter)} />
  </div>
  <div>
    <Typography.Text className="mb-1 block text-xs font-semibold text-[#7b756d]">面积指标</Typography.Text>
    <Segmented
      block
      options={[
        { label: "流通市值", value: "market_cap" },
        { label: "成交额", value: "turnover" },
      ]}
      value={sizeMode}
      onChange={(value) => setSizeMode(value as HeatmapSizeMode)}
    />
  </div>
  <div>
    <Typography.Text className="mb-1 block text-xs font-semibold text-[#7b756d]">涨跌区间</Typography.Text>
    <Segmented block options={HEATMAP_PERIOD_OPTIONS} value={period} onChange={(value) => setPeriod(value as HeatmapPeriodKey)} />
  </div>
</div>
```

- [ ] **Step 5: Add summary, detail, legend, source status, screenshot, and fullscreen**

In the detail rail:

```tsx
<div className="space-y-4">
  <div className="grid grid-cols-3 gap-2 text-center">
    <Metric label="上涨" value={data?.summary.advance_count ?? 0} tone="rise" />
    <Metric label="平盘" value={data?.summary.unchanged_count ?? 0} tone="flat" />
    <Metric label="下跌" value={data?.summary.decline_count ?? 0} tone="fall" />
  </div>
  <div className="rounded-lg border border-[#ddd8d0] p-3">
    {activeStock ? (
      <>
        <div className="flex items-start justify-between gap-2">
          <div>
            <Typography.Text className="block font-semibold text-[#11100e]">{activeStock.name}</Typography.Text>
            <Typography.Text className="workbench-muted text-xs">{activeStock.symbol} · {activeStock.industry}</Typography.Text>
          </div>
          <Tag color={activeStock.change_pct >= 0 ? "red" : "green"}>{activeStock.change_pct.toFixed(2)}%</Tag>
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <Detail label="价格" value={activeStock.price == null ? "-" : activeStock.price.toFixed(2)} />
          <Detail label="成交额" value={formatHeatmapMoney(activeStock.turnover_cny)} />
          <Detail label="流通市值" value={formatHeatmapMoney(activeStock.circulating_market_cap_cny)} />
          <Detail label="细分" value={activeStock.sub_industry ?? "-"} />
        </dl>
        <Link className="mt-3 block text-sm font-semibold text-[#11100e]" href={heatmapStockHref(activeStock)}>查看K线</Link>
      </>
    ) : (
      <Typography.Text className="workbench-muted text-sm">悬停或点击股票查看细节。</Typography.Text>
    )}
  </div>
  <div className="rounded-lg border border-[#ddd8d0] p-3 text-xs text-[#7b756d]">
    <div className="mb-2 font-semibold text-[#11100e]">数据源</div>
    <Space wrap>
      {(data?.source_status ?? []).map((status) => (
        <Tag key={`${status.source}-${status.status}`} color={status.status === "success" ? "green" : status.status === "stale" ? "orange" : "red"}>
          {status.source} · {heatmapSourceStatusLabel(status)}
        </Tag>
      ))}
    </Space>
  </div>
</div>
```

Implement `handleDownload()` using `canvas.toDataURL("image/png")` and a temporary `<a download="stockmaster-heatmap.png">`. Implement `handleFullscreen()` with `canvasWrapRef.current?.requestFullscreen()`. Show `message.warning()` when the browser rejects either action.

- [ ] **Step 6: Add nav entry and smoke route**

Modify `apps/web/components/AppShell.tsx`:

```tsx
import { HeatMapOutlined } from "@ant-design/icons";
```

Add this `NAV_ITEMS` entry between `板块` and `竞价`:

```tsx
{
  href: "/heatmap",
  key: "/heatmap",
  icon: <HeatMapOutlined />,
  label: "热图",
  title: "市场热力图",
},
```

Update `selectedNavKey()`:

```ts
if (pathname.startsWith("/heatmap")) {
  return "/heatmap";
}
```

Modify `scripts/smoke-ui.mjs` route list:

```js
const routes = ["/", "/auction", "/heatmap", "/sectors", "/watchlist", "/stock/002080.SZ", "/settings", "/sentiment"];
```

- [ ] **Step 7: Run frontend type and unit checks**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
./node_modules/.bin/tsc --noEmit
node --experimental-strip-types --test lib/*.test.ts app/heatmap/heatmapTreemap.test.ts
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/web/app/heatmap apps/web/components/AppShell.tsx scripts/smoke-ui.mjs
git commit -m "feat: add heatmap workbench page"
```

## Task 8: Attribution, Verification, And Browser QA

**Files:**
- Modify: `README.md`
- Modify: `docs/DEPLOYMENT.md` if deployment notes mention exposed modules

- [ ] **Step 1: Add README module description and upstream attribution**

Add a `市场热力图` item to the feature list:

```markdown
- **市场热力图**：独立 `/heatmap` 工作台，按全 A / 指数范围 / 行业 / 涨跌方向 / 面积指标展示 Canvas 热图，支持悬停详情、K 线跳转、截图、全屏和数据源状态识别。
```

Add an attribution section:

```markdown
### Third-party attribution

The market heatmap baseline universe and interaction reference are adapted from [`wenyuanw/a-share-heatmap`](https://github.com/wenyuanw/a-share-heatmap), licensed under MIT. A copy of the upstream MIT license is preserved at `apps/api/app/data/heatmap/LICENSE.a-share-heatmap`. Fallback heatmap data is displayed as sample/stale data and is not presented as proprietary realtime data.
```

- [ ] **Step 2: Run backend heatmap tests and existing focused API checks**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/python -m pytest tests/test_heatmap_provider.py tests/test_heatmap_api.py -q
```

Expected: PASS.

Run the full API suite when the focused tests pass:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/python -m pytest -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend checks**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
./node_modules/.bin/tsc --noEmit
node --experimental-strip-types --test lib/*.test.ts app/heatmap/heatmapTreemap.test.ts
```

Expected: PASS.

Run build if `sharp` optional dependency is available:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
pnpm build
```

Expected: PASS. If build fails because local `pnpm` ignored optional build scripts for `sharp`, record the exact `sharp` error and keep the `tsc + node --test` verification as the frontend gate for this task.

- [ ] **Step 4: Run local app and smoke UI**

Start or reuse the API and web services:

```bash
cd /Users/kale/Documents/strong-stock-screener
docker compose up --build
```

If Docker is already serving the workbench on `http://127.0.0.1:3110`, run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
SMOKE_UI_BASE_URL=http://127.0.0.1:3110 node ../../scripts/smoke-ui.mjs
```

Expected: PASS or `smoke:ui skipped` when Playwright is not installed.

- [ ] **Step 5: Manual browser verification**

Open `http://127.0.0.1:3110/heatmap` and verify:

- The left nav shows `热图` and highlights on `/heatmap`.
- The Canvas is nonblank on desktop `1440x900`.
- The Canvas remains nonblank on mobile `390x844` and controls/details do not overlap.
- Market, board, trend, size mode, and period controls trigger new `/api/heatmap/treemap` requests.
- Hover updates the right detail rail.
- Click pins the stock detail.
- `查看K线` opens `/stock/<symbol>?from=heatmap...`.
- Returning from stock detail shows `返回市场热图`.
- Reset view clears selected stock and restores zoom/pan.
- Fullscreen enters browser fullscreen for the heatmap panel.
- Screenshot downloads a PNG.
- If live quote fetch fails, source status visibly says sample/stale or failed rather than realtime.

- [ ] **Step 6: Commit attribution and verification support**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener
git add README.md docs/DEPLOYMENT.md
git commit -m "docs: document heatmap module attribution"
```

Skip `docs/DEPLOYMENT.md` in the `git add` command if no deployment note changes were needed.

## Final Verification Gate

Before reporting completion, run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/python -m pytest tests/test_heatmap_provider.py tests/test_heatmap_api.py -q
```

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
./node_modules/.bin/tsc --noEmit
node --experimental-strip-types --test lib/*.test.ts app/heatmap/heatmapTreemap.test.ts
```

Then run the broad suites when focused checks pass:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/python -m pytest -q
```

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
pnpm build
```

Record any `pnpm build` local optional-dependency failure exactly. Do not call the feature complete until the focused backend tests, frontend type check, frontend node tests, and browser verification have all passed.
