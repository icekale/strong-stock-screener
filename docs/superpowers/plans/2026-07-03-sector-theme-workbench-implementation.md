# Sector Theme Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `/sectors` into a concept/theme-first sector workbench with strength/main-flow modes, multi-theme intraday curves, selected-theme stock table, and clear data-source fallback.

**Architecture:** Keep the backend aggregation in focused services so `app/main.py` only wires the endpoint. TickFlow market rankings remain the realtime quote source, TDX limit-up concept rows provide theme concentration when available, and industry grouping is the explicit fallback. The frontend replaces the old sector flow page with a compact Ant Design workbench composed of selector, mode tabs, chart, related tags, and stock table.

**Tech Stack:** FastAPI, Pydantic, pytest, Next.js App Router, React 19, Ant Design, Tailwind, ECharts, Node test runner.

---

### Task 1: Backend Models And Pure Aggregation

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/services/sector_workbench.py`
- Test: `apps/api/tests/test_sector_workbench.py`

- [ ] **Step 1: Write failing backend aggregation tests**

Add tests that construct `MarketRankingsResponse` and TDX-style rows, then assert:

```python
def test_sector_workbench_prefers_theme_rows_over_industry_fallback() -> None:
    response = build_sector_workbench_response(
        rankings=_rankings(),
        limit_up_rows=[
            {"代码": "603690.SH", "名称": "至纯科技", "所属概念": "CPO;半导体设备", "连续涨停天数": 2, "封单金额": 12000},
            {"代码": "300475.SZ", "名称": "香农芯创", "所属概念": "存储芯片;半导体", "连续涨停天数": 1, "封单金额": 8000},
        ],
        mode="strength",
        scope="auto",
        selected=[],
        limit=10,
        stock_limit=10,
        sampled_at=datetime(2026, 7, 3, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert response.scope == "theme"
    assert response.themes[0].name == "CPO"
    assert response.themes[0].limit_up_count == 1
    assert response.selected_themes[:3] == ["CPO", "半导体设备", "存储芯片"]
    assert response.stocks[0].themes
    assert response.source_status[0].status == "success"
```

Also add:

```python
def test_sector_workbench_falls_back_to_industry_when_theme_rows_are_missing() -> None:
    response = build_sector_workbench_response(
        rankings=_rankings(),
        limit_up_rows=[],
        mode="main_flow",
        scope="auto",
        selected=["半导体"],
        limit=10,
        stock_limit=10,
        sampled_at=datetime(2026, 7, 3, 10, 31, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert response.scope == "industry"
    assert response.themes[0].name == "半导体"
    assert response.themes[0].flow_status == "estimated"
    assert response.series[0].metric == "main_flow"
    assert response.stocks[0].industry == "半导体"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd apps/api
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m pytest tests/test_sector_workbench.py -q
```

Expected: fail because `app.services.sector_workbench` and new models do not exist.

- [ ] **Step 3: Add Pydantic models**

Add to `apps/api/app/models.py`:

```python
SectorWorkbenchMode = Literal["strength", "main_flow"]
SectorWorkbenchScope = Literal["theme", "industry"]
SectorWorkbenchScopeRequest = Literal["theme", "industry", "auto"]
SectorFlowStatus = Literal["direct", "estimated", "unavailable"]
```

Define `SectorWorkbenchTheme`, `SectorWorkbenchPoint`, `SectorWorkbenchSeries`, `SectorWorkbenchStock`, and `SectorWorkbenchResponse` with the fields from the design spec.

- [ ] **Step 4: Implement pure service**

Create `apps/api/app/services/sector_workbench.py` with:

```python
def build_sector_workbench_response(
    *,
    rankings: MarketRankingsResponse,
    limit_up_rows: list[dict[str, Any]],
    mode: SectorWorkbenchMode,
    scope: SectorWorkbenchScopeRequest,
    selected: list[str],
    limit: int,
    stock_limit: int,
    sampled_at: datetime,
) -> SectorWorkbenchResponse:
    # Parse theme rows first, otherwise group rankings by industry.
    # Return current aggregate themes, selected names, one-point series, related tags, stocks, and source status.
    return response
```

Implementation rules:
- Use TDX concept rows when `scope` is `auto` or `theme` and at least one concept is parsed.
- Fall back to ranking `industry` grouping when theme rows are unavailable.
- Compute `strength_score` from limit-up count, average pct change, advancing count, turnover, and board count.
- Compute `main_flow_cny` as estimated turnover weighted by pct change unless a direct value is present.
- Generate one current `SectorWorkbenchPoint` per selected theme.
- Return source status that states whether concept rows or industry fallback was used.

- [ ] **Step 5: Run backend aggregation tests**

Run the same pytest command and expect all tests in `test_sector_workbench.py` to pass.

### Task 2: Sampling Store And API Endpoint

**Files:**
- Create: `apps/api/app/services/sector_workbench_store.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_sector_workbench.py`

- [ ] **Step 1: Write failing store and API tests**

Add tests for:

```python
def test_sector_workbench_store_dedupes_same_minute_and_builds_series(tmp_path: Path) -> None:
    store = SectorWorkbenchSampleStore(tmp_path)
    response = _workbench_response("strength", "theme")
    store.append(response)
    store.append(response)

    series = store.series_for(
        trade_date=response.trade_date,
        mode="strength",
        scope="theme",
        selected=response.selected_themes,
        metric="strength",
    )

    assert len(series[0].points) == 1
```

Add endpoint assertion to `test_api.py` or a focused client test:

```python
def test_sector_workbench_endpoint_returns_mode_and_source_status(monkeypatch) -> None:
    app.state.market_overview_provider = FakeRankingProvider()
    client = TestClient(app)
    response = client.get("/api/sectors/workbench?mode=strength&scope=auto&limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "strength"
    assert payload["themes"]
    assert payload["source_status"]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd apps/api
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m pytest tests/test_sector_workbench.py tests/test_api.py::test_sector_workbench_endpoint_returns_mode_and_source_status -q
```

Expected: fail because the store and endpoint do not exist.

- [ ] **Step 3: Implement sample store**

Create a JSON store under `data/sectors` by default, with a class:

```python
class SectorWorkbenchSampleStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def append(self, response: SectorWorkbenchResponse) -> None:
        """Persist one aggregate point per selected theme for the response minute."""

    def series_for(
        self,
        *,
        trade_date: str | None,
        mode: SectorWorkbenchMode,
        scope: SectorWorkbenchScope,
        selected: list[str],
        metric: str,
    ) -> list[SectorWorkbenchSeries]:
        """Read same-day aggregate points for selected themes."""

    def prune(self, keep_days: int = 60) -> None:
        """Delete sector sample files older than keep_days."""
```

Store only aggregate points keyed by trade date, mode, scope, theme name, and minute.

- [ ] **Step 4: Wire endpoint**

Add `GET /api/sectors/workbench` in `apps/api/app/main.py`.

Endpoint flow:
1. Validate `mode`, `scope`, `limit`, `stock_limit`.
2. Fetch `_cached_market_rankings(100)`.
3. Try to fetch TDX limit-up concept rows with `_tdx_provider().query_rows("今日涨停股列表 封单金额 首次涨停时间 涨停原因 连续涨停天数 板型 封成比 所属概念 所属通达信风格", size=100)`.
4. Build response with `build_sector_workbench_response`.
5. Append current sample.
6. Replace response `series` with persisted same-day series.
7. Return `model_dump(mode="json")`.

- [ ] **Step 5: Run endpoint tests**

Run the pytest command from Step 2 and expect passing.

### Task 3: Frontend Types, API Client, And Navigation Context

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/lib/stockNavigation.ts`
- Modify: `apps/web/lib/stockNavigation.test.ts`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Write failing frontend structural tests**

Add assertions:

```ts
assert.match(typesSource, /SectorWorkbenchResponse/);
assert.match(typesSource, /SectorWorkbenchTheme/);
assert.match(apiSource, /getSectorWorkbench/);
assert.match(sectorsFeatureSource, /SectorThemeWorkbench/);
assert.match(sectorsFeatureSource, /板块强度/);
assert.match(sectorsFeatureSource, /主力流入/);
assert.match(sectorsFeatureSource, /加入自选/);
```

Update stock navigation test:

```ts
assert.equal(
  buildStockDetailHref("603690.SH", { from: "sectors", name: "至纯科技", industry: "半导体" }),
  "/stock/603690.SH?from=sectors&name=%E8%87%B3%E7%BA%AF%E7%A7%91%E6%8A%80&industry=%E5%8D%8A%E5%AF%BC%E4%BD%93",
);
assert.equal(resolveStockDetailContext(new URLSearchParams("from=sectors")).returnHref, "/sectors");
```

- [ ] **Step 2: Run frontend tests and verify failure**

Run:

```bash
cd apps/web
corepack pnpm --ignore-workspace test
```

Expected: fail because types/client/component/navigation support is missing.

- [ ] **Step 3: Add TypeScript types and API client**

Add sector workbench types matching backend models. Add:

```ts
export async function getSectorWorkbench(options: {
  mode?: SectorWorkbenchMode;
  scope?: SectorWorkbenchScopeRequest;
  selected?: string[];
  limit?: number;
  stockLimit?: number;
} = {}): Promise<SectorWorkbenchResponse> {
  const params = new URLSearchParams();
  if (options.mode) params.set("mode", options.mode);
  if (options.scope) params.set("scope", options.scope);
  if (options.selected?.length) params.set("selected", options.selected.join(","));
  if (options.limit) params.set("limit", String(options.limit));
  if (options.stockLimit) params.set("stock_limit", String(options.stockLimit));
  const response = await fetch(`${API_BASE_URL}/api/sectors/workbench?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`读取题材工作台失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<SectorWorkbenchResponse>;
}
```

The function builds `URLSearchParams`, appends repeated selected theme names as a comma-separated `selected` query parameter, calls `/api/sectors/workbench`, throws `读取题材工作台失败` on non-OK responses, and returns typed JSON.

- [ ] **Step 4: Extend stock navigation context**

Change `StockDetailFrom` to include `"sectors"`, encode `from=sectors`, and resolve return label as `返回题材工作台`.

- [ ] **Step 5: Run frontend tests**

Run the frontend test command and expect passing.

### Task 4: Sector Workbench UI

**Files:**
- Modify: `apps/web/app/sectors/SectorPageWorkspace.tsx`
- Create: `apps/web/app/sectors/SectorThemeWorkbench.tsx`
- Optionally keep: `apps/web/app/sectors/SectorFlowWorkspace.tsx`

- [ ] **Step 1: Replace page shell**

Change `SectorPageWorkspace` to render `SectorThemeWorkbench` as the primary content. Keep the title and source status aligned with existing workbench styling.

- [ ] **Step 2: Implement `SectorThemeWorkbench`**

Component state:

```ts
const [mode, setMode] = useState<SectorWorkbenchMode>("strength");
const [selectedThemes, setSelectedThemes] = useState<string[]>([]);
const [data, setData] = useState<SectorWorkbenchResponse | null>(null);
```

Behavior:
- Fetch `getSectorWorkbench` on mode or selected change.
- Initialize selected themes from backend `selected_themes`.
- Keep selected themes when mode changes.
- Limit selection to 5 themes.
- Show clear AntD feedback when adding a stock to watchlist.

- [ ] **Step 3: Implement chart and table**

Use ECharts for the line chart and Ant Design `Table` for stocks. The table has columns: 名称/代码, 行业, 题材, 涨幅, 成交额, 换手, 连板, 竞价, 封单, 操作.

- [ ] **Step 4: Run frontend tests and build**

Run:

```bash
cd apps/web
corepack pnpm --ignore-workspace test
corepack pnpm --ignore-workspace build
```

Expected: both commands exit 0.

### Task 5: Full Verification And Commit

**Files:**
- All files changed by Tasks 1-4.

- [ ] **Step 1: Run backend focused tests**

```bash
cd apps/api
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m pytest tests/test_sector_workbench.py tests/test_api.py -q
```

- [ ] **Step 2: Run backend lint**

```bash
cd apps/api
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m ruff check app tests
```

- [ ] **Step 3: Run frontend tests and build**

```bash
cd apps/web
corepack pnpm --ignore-workspace test
corepack pnpm --ignore-workspace build
```

- [ ] **Step 4: Review diff**

```bash
git diff --stat
git diff -- apps/api/app/models.py apps/api/app/services/sector_workbench.py apps/api/app/main.py apps/web/app/sectors/SectorThemeWorkbench.tsx
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/app apps/api/tests apps/web/app apps/web/lib docs/superpowers/plans/2026-07-03-sector-theme-workbench-implementation.md
git commit -m "Build sector theme workbench"
```

Expected commit includes backend API, frontend workbench, tests, and this implementation plan.
