# Sector Radar Replica Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `/sectors` with a Duanxianxia-style sector radar panel that matches the reference UI and serves qxlive-compatible, self-owned curve data.

**Architecture:** Add a focused backend replica service that adapts existing sector workbench responses into qxlive-compatible board, chart, and stock-table payloads. Add FastAPI endpoints under `/api/sectors/replica/*`, TypeScript client/types, a pure chart-option builder, and a compact custom React UI that replaces the old sector page content.

**Tech Stack:** FastAPI, Pydantic, pytest, Next.js React, TypeScript, ECharts, node test runner.

---

## File Structure

- Create `apps/api/app/services/sector_radar_replica.py`
  - Owns fixed time axis, score calibration helpers, qxlive-compatible response building, and active-board stock table adaptation.
- Modify `apps/api/app/models.py`
  - Adds replica response models with named fields and compatibility arrays.
- Modify `apps/api/app/main.py`
  - Adds `/api/sectors/replica/radar`, `/api/sectors/replica/boards/{board_code}/stocks`, and `/api/sectors/replica/status`.
- Create `apps/api/tests/test_sector_radar_replica.py`
  - Tests response shape, fixed axis, board ranking, selected filtering, main-flow status, and stock row compatibility.
- Modify `apps/web/lib/types.ts`
  - Adds replica response and row types.
- Modify `apps/web/lib/api.ts`
  - Adds replica API client functions.
- Create `apps/web/lib/sectorReplicaChartOption.ts`
  - Pure ECharts option builder for the reference chart.
- Create `apps/web/lib/sectorReplicaChartOption.test.ts`
  - Tests chart legend/grid/axis/series behavior.
- Create `apps/web/app/sectors/SectorReplicaWorkspace.tsx`
  - Owns data loading, timers, active board, selected boards, mode, and stock-table refresh.
- Create `apps/web/app/sectors/SectorReplicaPanel.tsx`
  - Renders the reference-like compact panel, left board list, chart, sub-theme tags, and dense stock table.
- Modify `apps/web/app/sectors/SectorPageWorkspace.tsx`
  - Replaces the old primary workbench with `SectorReplicaWorkspace`.
- Modify `apps/web/app/globals.css`
  - Adds local `.sector-replica-*` CSS classes for the panel without globally changing Ant Design/workbench styles.

## Task 1: Backend Replica Models And Pure Service

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/services/sector_radar_replica.py`
- Test: `apps/api/tests/test_sector_radar_replica.py`

- [ ] **Step 1: Write failing backend service tests**

Add tests for:

```python
def test_replica_response_uses_qxlive_shape_and_selected_board_series() -> None:
    response = build_sector_radar_replica_response(
        workbench=_workbench_response(),
        mode="strength",
        selected_codes=["theme:cpo"],
        sampled_at=datetime(2026, 7, 9, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    assert response.result == "success"
    assert response.checkplate == ["theme:cpo"]
    assert response.legend == ["CPO"]
    assert [item.name for item in response.plates][:2] == ["CPO", "机器人"]
    assert response.series[0].name == "CPO"
    assert response.series[0].type == "line"
    assert response.qxlive.series["QX"]
```

```python
def test_replica_time_axis_contains_reference_session_labels() -> None:
    axis = build_reference_time_axis()
    assert axis[:3] == ["09:15", "09:16", "09:17"]
    assert "11:30" in axis
    assert "13:00" in axis
    assert axis[-1] == "15:00"
```

```python
def test_replica_stock_rows_keep_reference_column_order() -> None:
    rows = build_sector_replica_stock_rows(_workbench_response(), board_code="theme:cpo")
    first = rows[0]
    assert first.compat_row[0] == "603690"
    assert first.compat_row[1] == "至纯科技"
    assert first.compat_row[2] == 10.0
    assert first.compat_row[8] == 320_000_000
    assert first.compat_row[12] == "2连板"
    assert first.compat_row[17] == 120_000_000
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
cd apps/api
uv run pytest tests/test_sector_radar_replica.py -q
```

Expected: FAIL because `app.services.sector_radar_replica` and replica models do not exist.

- [ ] **Step 3: Implement minimal Pydantic models**

Add models:

```python
class SectorReplicaMode(str, Enum):
    strength = "strength"
    main_flow = "main_flow"

class SectorReplicaPlate(BaseModel):
    code: str
    name: str
    val: float
    ztcount: int = 0
    display_value: str | None = None

class SectorReplicaChartSeries(BaseModel):
    name: str
    type: str = "line"
    data: list[float | None] = Field(default_factory=list)
    smooth: bool = True
    showSymbol: bool = False

class SectorReplicaQxLive(BaseModel):
    Aaxis: list[str] = Field(default_factory=list)
    zflist: list[float] = Field(default_factory=list)
    series: dict[str, list[float | None]] = Field(default_factory=dict)

class SectorReplicaStockRow(BaseModel):
    symbol: str
    code: str
    name: str | None = None
    pct_change: float | None = None
    turnover_cny: float | None = None
    circulating_value_cny: float | None = None
    board_label: str = "--"
    auction_pct_change: float | None = None
    auction_amount_cny: float | None = None
    auction_volume_ratio: float | None = None
    buy_ratio_pct: float | None = None
    seal_amount_cny: float | None = None
    leader_tag: str | None = None
    themes: list[str] = Field(default_factory=list)
    industry: str | None = None
    compat_row: list[Any] = Field(default_factory=list)

class SectorReplicaRadarResponse(BaseModel):
    result: str = "success"
    mode: SectorReplicaMode
    trade_date: str | None = None
    axis: list[str] = Field(default_factory=list)
    qxlive: SectorReplicaQxLive = Field(default_factory=SectorReplicaQxLive)
    plates: list[SectorReplicaPlate] = Field(default_factory=list)
    checkplate: list[str] = Field(default_factory=list)
    legend: list[str] = Field(default_factory=list)
    series: list[SectorReplicaChartSeries] = Field(default_factory=list)
    stocks: list[SectorReplicaStockRow] = Field(default_factory=list)
    related_tags: list[str] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
```

- [ ] **Step 4: Implement minimal service**

Implement:

```python
def build_reference_time_axis() -> list[str]:
    return _minute_labels((9, 15), (11, 30)) + _minute_labels((13, 0), (15, 0))
```

```python
def build_sector_radar_replica_response(
    *,
    workbench: SectorWorkbenchResponse,
    mode: SectorReplicaMode | str,
    selected_codes: list[str],
    sampled_at: datetime,
) -> SectorReplicaRadarResponse:
    axis = build_reference_time_axis()
    plates = [_plate_from_theme(theme, mode=str(mode)) for theme in workbench.themes]
    code_by_name = {_board_code(theme.name): theme.name for theme in workbench.themes}
    selected = _selected_codes(selected_codes, plates)
    legend_names = [code_by_name.get(code, code) for code in selected]
    series = [_series_for_theme_name(name, workbench.series, axis) for name in legend_names]
    return SectorReplicaRadarResponse(
        mode=mode,
        trade_date=workbench.trade_date,
        axis=axis,
        qxlive=_qxlive_payload(workbench, axis),
        plates=plates,
        checkplate=selected,
        legend=legend_names,
        series=series,
        stocks=build_sector_replica_stock_rows(workbench, board_code=selected[0] if selected else None),
        related_tags=workbench.related_tags,
        source_status=[*workbench.source_status, _replica_status(mode)],
        generated_at=sampled_at.isoformat(timespec="seconds"),
    )
```

- [ ] **Step 5: Run backend service tests and verify GREEN**

Run:

```bash
cd apps/api
uv run pytest tests/test_sector_radar_replica.py -q
```

Expected: PASS.

## Task 2: Backend API Endpoints

**Files:**
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_api.py` or `apps/api/tests/test_sector_radar_replica.py`

- [ ] **Step 1: Write failing endpoint tests**

Add tests using `TestClient` that call:

```python
response = client.get("/api/sectors/replica/radar?mode=strength&limit=5")
assert response.status_code == 200
payload = response.json()
assert payload["result"] == "success"
assert "plates" in payload
assert "qxlive" in payload
```

```python
response = client.get("/api/sectors/replica/boards/theme:cpo/stocks")
assert response.status_code == 200
assert "rows" in response.json()
```

- [ ] **Step 2: Run endpoint tests and verify RED**

Run:

```bash
cd apps/api
uv run pytest tests/test_sector_radar_replica.py -q
```

Expected: FAIL with 404 or missing imports.

- [ ] **Step 3: Add endpoints**

Use existing `_cached_market_rankings`, `_sector_theme_rows`, and `build_sector_workbench_response` flow in `main.py`. Add:

```python
@app.get("/api/sectors/replica/radar", response_model=SectorReplicaRadarResponse)
def get_sector_replica_radar(...):
    workbench = _build_sector_replica_workbench(...)
    return build_sector_radar_replica_response(...)
```

```python
@app.get("/api/sectors/replica/boards/{board_code:path}/stocks")
def get_sector_replica_board_stocks(board_code: str, ...):
    workbench = _build_sector_replica_workbench(...)
    rows = build_sector_replica_stock_rows(workbench, board_code=board_code, sub_theme=sub_theme)
    return {"rows": [row.model_dump(mode="json") for row in rows], ...}
```

- [ ] **Step 4: Run endpoint tests and targeted existing sector tests**

Run:

```bash
cd apps/api
uv run pytest tests/test_sector_radar_replica.py tests/test_sector_workbench.py -q
```

Expected: PASS.

## Task 3: Frontend Types, API Client, And Chart Option

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Create: `apps/web/lib/sectorReplicaChartOption.ts`
- Create: `apps/web/lib/sectorReplicaChartOption.test.ts`

- [ ] **Step 1: Write failing chart option test**

Add:

```ts
test("sector replica chart option keeps reference-like legend and fixed axis", () => {
  const option = buildSectorReplicaChartOption({
    axis: ["09:15", "09:16", "15:00"],
    series: [{ name: "芯片", type: "line", data: [1, 2, 3], smooth: true, showSymbol: false }],
  });
  assert.deepEqual(option.legend?.data, ["芯片"]);
  assert.equal(option.grid?.left, "2.5%");
  assert.deepEqual(option.xAxis?.data, ["09:15", "09:16", "15:00"]);
  assert.equal(option.series?.[0]?.showSymbol, false);
});
```

- [ ] **Step 2: Run frontend test and verify RED**

Run:

```bash
cd apps/web
node --experimental-strip-types --test lib/sectorReplicaChartOption.test.ts
```

Expected: FAIL because the chart option module does not exist.

- [ ] **Step 3: Add types and API client**

Add TypeScript types mirroring backend models:

```ts
export type SectorReplicaMode = "strength" | "main_flow";
export type SectorReplicaPlate = { code: string; name: string; val: number; ztcount: number; display_value: string | null };
export type SectorReplicaChartSeries = { name: string; type: "line"; data: Array<number | null>; smooth: boolean; showSymbol: boolean };
export type SectorReplicaRadarResponse = { result: "success"; mode: SectorReplicaMode; axis: string[]; qxlive: { Aaxis: string[]; zflist: number[]; series: Record<string, Array<number | null>> }; plates: SectorReplicaPlate[]; checkplate: string[]; legend: string[]; series: SectorReplicaChartSeries[]; stocks: SectorReplicaStockRow[]; related_tags: string[]; source_status: StrongStockSourceStatus[]; generated_at: string };
```

Add API helpers:

```ts
export async function getSectorReplicaRadar(options: { mode?: SectorReplicaMode; selected?: string[]; limit?: number; stockLimit?: number } = {}): Promise<SectorReplicaRadarResponse> { ... }
export async function getSectorReplicaBoardStocks(boardCode: string, options: { mode?: SectorReplicaMode; subTheme?: string | null; limit?: number } = {}): Promise<SectorReplicaStocksResponse> { ... }
```

- [ ] **Step 4: Add chart option builder**

Build a pure ECharts option with:

- centered top legend;
- grid `{ left: "2.5%", right: "1%", bottom: "5%", top: "10%", containLabel: true }`;
- category x-axis with provided fixed axis;
- value y-axis with light split lines;
- thin smooth line series with `showSymbol: false`.

- [ ] **Step 5: Run frontend chart test**

Run:

```bash
cd apps/web
node --experimental-strip-types --test lib/sectorReplicaChartOption.test.ts
```

Expected: PASS.

## Task 4: Replace `/sectors` With Replica UI

**Files:**
- Create: `apps/web/app/sectors/SectorReplicaWorkspace.tsx`
- Create: `apps/web/app/sectors/SectorReplicaPanel.tsx`
- Modify: `apps/web/app/sectors/SectorPageWorkspace.tsx`
- Modify: `apps/web/app/globals.css`

- [ ] **Step 1: Write or update frontend behavior tests**

Add lightweight tests for pure helpers if UI component testing is unavailable:

```ts
test("sector replica keeps at least one checked board", () => {
  assert.deepEqual(nextSectorReplicaSelection(["a"], "a", false), ["a"]);
  assert.deepEqual(nextSectorReplicaSelection(["a"], "b", true), ["a", "b"]);
});
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
cd apps/web
node --experimental-strip-types --test lib/sectorReplica*.test.ts
```

Expected: FAIL until helper is created.

- [ ] **Step 3: Implement replica workspace and panel**

Implement:

- 15s radar refresh interval;
- 8s active-board stock refresh interval;
- board list with compact checkbox rows and red `N涨停` badges;
- ECharts chart using `buildSectorReplicaChartOption`;
- compact sub-theme buttons;
- custom dense table with reference columns;
- stock row link through `buildStockDetailHref`.

- [ ] **Step 4: Replace sector page content**

Change `SectorPageWorkspace` to render `SectorReplicaWorkspace` as the primary content. Keep old components import-free from the rendered path.

- [ ] **Step 5: Run frontend tests and typecheck**

Run:

```bash
cd apps/web
pnpm test
```

Expected: PASS.

## Task 5: Verification And Commit

**Files:**
- All touched files.

- [ ] **Step 1: Run backend targeted tests**

Run:

```bash
cd apps/api
uv run pytest tests/test_sector_radar_replica.py tests/test_sector_workbench.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend tests**

Run:

```bash
cd apps/web
pnpm test
```

Expected: PASS.

- [ ] **Step 3: Check git diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: only sector replica implementation, tests, and plan files are changed.

- [ ] **Step 4: Commit**

Run:

```bash
git add apps/api/app apps/api/tests apps/web/app apps/web/lib docs/superpowers/plans/2026-07-09-sector-radar-replica.md
git commit -m "feat: add sector radar replica"
```

Expected: commit succeeds on `codex/sector-radar-replica`.
