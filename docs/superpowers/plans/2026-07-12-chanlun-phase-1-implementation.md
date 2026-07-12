# Multi-Period Chanlun Workbench Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a verified Phase 1 foundation for the multi-period Chanlun workbench: closed-bar minute storage and backfill, a `czsc` adapter, analysis APIs, K-line overlays, and `/chanlun` single-stock research.

**Architecture:** Keep all Chanlun backend behavior under `apps/api/app/services/chanlun/`. TickFlow supplies current intraday bars; an optional `mootdx` source fills a bounded recent history into SQLite. The adapter converts normalized project bars to `czsc` and maps results back to project-owned Pydantic models. The existing ECharts overlay renders typed layers without replacing K-line, GSGF, screener, or auction paths.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite, `czsc==0.10.12`, `mootdx==0.11.7`, pytest, Next.js 15, React 19, TypeScript, Ant Design, ECharts, Docker.

**Scope:** This plan covers the first phase only. It does not implement full buy/sell-point taxonomy, divergence, screening scores, alerts, paper orders, or backtest reporting. Those start only after the Phase 1 exit criteria pass.

---

## File Structure

### Create

- `apps/api/app/providers/tdx_minute_history.py`: Optional `mootdx` history adapter.
- `apps/api/app/services/chanlun/__init__.py`: Chanlun service package.
- `apps/api/app/services/chanlun/bars.py`: Shanghai session normalization and aggregation.
- `apps/api/app/services/chanlun/store.py`: Idempotent minute-bar SQLite store.
- `apps/api/app/services/chanlun/adapter.py`: `czsc` conversion and project-owned structure mapping.
- `apps/api/app/services/chanlun/service.py`: Cached per-period analysis and workspace assembly.
- `apps/api/app/services/chanlun/symbols.py`: Cached code/name lookup.
- `apps/api/tests/test_chanlun_models.py`
- `apps/api/tests/test_chanlun_bars.py`
- `apps/api/tests/test_chanlun_store.py`
- `apps/api/tests/test_tdx_minute_history.py`
- `apps/api/tests/test_chanlun_adapter.py`
- `apps/api/tests/test_chanlun_service.py`
- `apps/web/lib/chanlunOverlay.ts`
- `apps/web/lib/chanlunOverlay.test.ts`
- `apps/web/app/chanlun/page.tsx`
- `apps/web/app/chanlun/ChanlunWorkspace.tsx`
- `apps/web/app/chanlun/chanlunWorkspace.test.ts`
- `apps/web/app/stock/[symbol]/stockKlineChanlun.test.ts`

### Modify

- `apps/api/pyproject.toml`, `apps/api/uv.lock`, `Dockerfile`, `apps/api/Dockerfile`, `apps/api/tests/test_docker_runtime_deps.py`
- `apps/api/app/config.py`, `apps/api/app/models.py`, `apps/api/app/main.py`, `apps/api/tests/test_config.py`, `apps/api/tests/test_api.py`
- `apps/web/lib/types.ts`, `apps/web/lib/api.ts`, `apps/web/lib/api.test.ts`, `apps/web/lib/appNavigation.ts`, `apps/web/lib/appNavigation.test.ts`
- `apps/web/components/AppShell.tsx`, `apps/web/components/TickFlowKlineChart.tsx`, `apps/web/lib/brickIndicator.ts`, `apps/web/lib/klineOverlayOption.test.ts`
- `apps/web/app/stock/[symbol]/StockKlineWorkspace.tsx`, `apps/web/app/globals.css`, `README.md`

## Shared Contracts

```python
ChanlunPeriod = Literal["1d", "60m", "30m", "5m"]
ChanlunStatus = Literal["observing", "provisional", "confirmed", "final"]
ChanlunDirection = Literal["up", "down", "unknown"]
ChanlunAvailability = Literal["ready", "backfilling", "insufficient_bars", "stale", "unavailable"]
ChanlunLayerKey = Literal["fractals", "strokes", "segments", "zones"]
```

Phase 1 returns fractals, strokes, derived segments, confirmed zones, and an optional observing tail. It has no execution-grade signals. Every response includes source status, availability, `calculated_at`, `last_closed_bar_at`, adjustment mode, and `rule_version="cl-v1"`. The web client renders these server-owned objects and never infers confirmation locally.

## Task 1: Prove and Pin the Native Runtime

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/uv.lock`
- Modify: `Dockerfile`
- Modify: `apps/api/Dockerfile`
- Modify: `apps/api/tests/test_docker_runtime_deps.py`

- [ ] **Step 1: Write failing runtime tests**

```python
def test_chanlun_runtime_dependencies_are_pinned() -> None:
    repo_root = Path(__file__).parents[3]
    content = (repo_root / "apps/api/pyproject.toml").read_text(encoding="utf-8")

    assert '"czsc==0.10.12"' in content
    assert '"mootdx==0.11.7"' in content


def test_dockerfiles_verify_chanlun_native_imports() -> None:
    repo_root = Path(__file__).parents[3]
    for path in [repo_root / "Dockerfile", repo_root / "apps/api/Dockerfile"]:
        content = path.read_text(encoding="utf-8")
        assert "libgomp1" in content
        assert "import czsc" in content
        assert "import mootdx" in content
```

- [ ] **Step 2: Verify RED**

Run: `cd apps/api && uv run pytest tests/test_docker_runtime_deps.py -q`

Expected: FAIL because dependencies and import checks are absent.

- [ ] **Step 3: Add the exact dependencies and import smoke checks**

Add these entries to the API dependency list:

```toml
"czsc==0.10.12",
"mootdx==0.11.7",
```

After dependency installation in both Dockerfiles, run this build-time command using the correct Python path for that Dockerfile:

```dockerfile
RUN /opt/strong-stock-api-venv/bin/python - <<'PY'
import czsc
import mootdx

print(f"czsc={czsc.__version__}")
print(f"mootdx={mootdx.__version__}")
PY
```

`apps/api/Dockerfile` installs into image Python, so use `python - <<'PY'` there. Do not add a compiler toolchain until the fixed wheel fails on the actual base image.

- [ ] **Step 4: Refresh and verify**

Run:

```bash
cd apps/api
uv lock
uv run pytest tests/test_docker_runtime_deps.py -q
uv run python -c 'import czsc, mootdx; print(czsc.__version__, mootdx.__version__)'
cd ../..
docker build --target api-builder -t strong-stock-screener-api-chanlun-check .
```

Expected: test and import pass, and Docker exits 0. If the package cannot import, stop the phase before application code and capture the exact architecture/package error.

- [ ] **Step 5: Commit**

```bash
git add apps/api/pyproject.toml apps/api/uv.lock Dockerfile apps/api/Dockerfile apps/api/tests/test_docker_runtime_deps.py
git commit -m "build: add verified chanlun runtime dependencies"
```

## Task 2: Establish Public Models and Settings

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/config.py`
- Modify: `apps/api/tests/test_config.py`
- Create: `apps/api/tests/test_chanlun_models.py`
- Modify: `apps/web/lib/types.ts`

- [ ] **Step 1: Write failing model/config tests**

```python
def test_chanlun_analysis_response_has_project_owned_layers() -> None:
    response = ChanlunAnalysisResponse(
        symbol="600000.SH",
        period="5m",
        availability="ready",
        source_status=[],
    )

    assert response.rule_version == "cl-v1"
    assert response.strokes == []
    assert response.zones == []
    assert not hasattr(response, "order")


def test_chanlun_settings_have_bounded_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.chanlun_history_days == 60
    assert settings.chanlun_minute_retention_days == 180
    assert settings.chanlun_cache_seconds == 30
    assert settings.chanlun_backfill_max_bars == 4800
```

In `test_config.py`, set `STRONG_STOCK_CHANLUN_TDX_ENABLED=false` and assert `Settings(_env_file=None).chanlun_tdx_enabled is False`.

- [ ] **Step 2: Verify RED**

Run: `cd apps/api && uv run pytest tests/test_chanlun_models.py tests/test_config.py -q`

Expected: FAIL with missing models/settings.

- [ ] **Step 3: Add project-owned contracts**

Add models equivalent to this code in `app/models.py`:

```python
class ChanlunFractal(BaseModel):
    id: str
    occurred_at: str
    price: float
    mark: Literal["top", "bottom"]
    status: ChanlunStatus


class ChanlunStroke(BaseModel):
    id: str
    start_at: str
    start_price: float
    end_at: str
    end_price: float
    direction: ChanlunDirection
    status: ChanlunStatus


class ChanlunZone(BaseModel):
    id: str
    start_at: str
    end_at: str
    high: float
    low: float
    virtual: bool = False
    status: ChanlunStatus


class ChanlunAnalysisResponse(BaseModel):
    symbol: str
    period: ChanlunPeriod
    availability: ChanlunAvailability
    bars: list[KlineBar] = Field(default_factory=list)
    fractals: list[ChanlunFractal] = Field(default_factory=list)
    strokes: list[ChanlunStroke] = Field(default_factory=list)
    segments: list[ChanlunStroke] = Field(default_factory=list)
    zones: list[ChanlunZone] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    calculated_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
    last_closed_bar_at: str | None = None
    adjustment_mode: str = "raw_unadjusted"
    rule_version: str = "cl-v1"
```

Add `ChanlunPeriodSummary`, `ChanlunWorkspaceResponse`, `ChanlunBackfillRequest`, and `ChanlunSymbolMatch`. Mirror these exact public fields in `apps/web/lib/types.ts` with string unions, not broad `string` types.

Add bounded settings:

```python
chanlun_history_days: int = Field(default=60, ge=5, le=240)
chanlun_minute_retention_days: int = Field(default=180, ge=30, le=730)
chanlun_cache_seconds: int = Field(default=30, ge=5, le=600)
chanlun_backfill_max_bars: int = Field(default=4800, ge=240, le=24000)
chanlun_tdx_enabled: bool = True
chanlun_tdx_timeout_seconds: float = Field(default=4, ge=1, le=15)
```

Do not add buy/sell point, divergence, alert, or order fields here.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
cd apps/api && uv run pytest tests/test_chanlun_models.py tests/test_config.py -q
cd ../web && pnpm lint
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/models.py apps/api/app/config.py apps/api/tests/test_config.py apps/api/tests/test_chanlun_models.py apps/web/lib/types.ts
git commit -m "feat: add chanlun analysis contracts"
```

## Task 3: Normalize and Aggregate Closed A-Share Minute Bars

**Files:**
- Create: `apps/api/app/services/chanlun/__init__.py`
- Create: `apps/api/app/services/chanlun/bars.py`
- Create: `apps/api/tests/test_chanlun_bars.py`

- [ ] **Step 1: Write failing time/session tests**

```python
def test_aggregate_5m_never_crosses_lunch_break() -> None:
    bars = minute_bars("2026-07-10 11:28", "2026-07-10 11:29", "2026-07-10 13:00", "2026-07-10 13:01")

    result = aggregate_closed_intraday_bars(bars, period="5m", now=shanghai("2026-07-10 13:03"))

    assert result == []


def test_unclosed_bucket_is_excluded_from_confirmed_bars() -> None:
    bars = minute_bars("2026-07-10 09:30", "2026-07-10 09:31", "2026-07-10 09:32")

    assert aggregate_closed_intraday_bars(bars, period="5m", now=shanghai("2026-07-10 09:33")) == []


def test_aggregate_uses_only_bars_available_at_cutoff() -> None:
    bars = minute_bars("2026-07-10 09:30", "2026-07-10 09:31", "2026-07-10 09:32", "2026-07-10 09:33", "2026-07-10 09:34")

    result = aggregate_closed_intraday_bars(bars, period="5m", now=shanghai("2026-07-10 09:35"))

    assert result[0].date == "2026-07-10T09:35:00+08:00"
    assert result[0].close == bars[-1].close
```

Add table-driven expected endpoints for `30m` and `60m` at `10:00`, `10:30`, `11:30`, `13:30`, and `15:00`.

- [ ] **Step 2: Verify RED**

Run: `cd apps/api && uv run pytest tests/test_chanlun_bars.py -q`

Expected: FAIL with missing module.

- [ ] **Step 3: Implement a deterministic bar module**

Implement these exact public function names and signatures: `normalize_intraday_bars(bars: Iterable[TickFlowIntradayBar]) -> list[TickFlowIntradayBar]`, `is_a_share_trading_minute(timestamp: datetime) -> bool`, and `aggregate_closed_intraday_bars(bars: Iterable[TickFlowIntradayBar], *, period: Literal["5m", "30m", "60m"], now: datetime) -> list[KlineBar]`.

Rules: convert to Asia/Shanghai, sort, keep the final duplicate timestamp, accept only `09:30-11:30` and `13:00-15:00`, and group the morning and afternoon sessions separately. A label is the bucket close time. Emit only complete buckets whose close is no later than `now`; use first open, last close, high/low extrema, and summed volume/amount. Do not calculate structures in this module.

- [ ] **Step 4: Verify GREEN**

Run: `cd apps/api && uv run pytest tests/test_chanlun_bars.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/chanlun/__init__.py apps/api/app/services/chanlun/bars.py apps/api/tests/test_chanlun_bars.py
git commit -m "feat: aggregate closed chanlun minute bars"
```

## Task 4: Persist Canonical Minute Bars Without Rewriting Closed History

**Files:**
- Create: `apps/api/app/services/chanlun/store.py`
- Create: `apps/api/tests/test_chanlun_store.py`

- [ ] **Step 1: Write failing SQLite tests**

```python
def test_store_upserts_open_bar_but_preserves_closed_snapshot(tmp_path: Path) -> None:
    store = ChanlunMinuteBarStore(tmp_path / "chanlun" / "minute.sqlite3")
    store.upsert("600000.SH", [minute_bar("2026-07-10 09:30", close=10.0)], source="TickFlow", closed=False)
    store.upsert("600000.SH", [minute_bar("2026-07-10 09:30", close=10.2)], source="TickFlow", closed=True)
    store.upsert("600000.SH", [minute_bar("2026-07-10 09:30", close=10.8)], source="TickFlow", closed=False)

    bars = store.read("600000.SH", start_at="2026-07-10T09:30:00+08:00")
    assert bars[0].close == 10.2
    assert bars[0].closed is True
```

Also cover sorted reads, source/capture metadata, idempotent inserts, and `prune(keep_days=30)`.

- [ ] **Step 2: Verify RED**

Run: `cd apps/api && uv run pytest tests/test_chanlun_store.py -q`

Expected: FAIL with missing store.

- [ ] **Step 3: Implement the SQLite store**

Use this schema:

```sql
CREATE TABLE IF NOT EXISTS minute_bars (
  symbol TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  trade_date TEXT NOT NULL,
  open REAL NOT NULL,
  high REAL NOT NULL,
  low REAL NOT NULL,
  close REAL NOT NULL,
  volume REAL NOT NULL,
  amount REAL NOT NULL,
  prev_close REAL,
  source TEXT NOT NULL,
  adjustment_mode TEXT NOT NULL,
  captured_at TEXT NOT NULL,
  closed INTEGER NOT NULL,
  PRIMARY KEY (symbol, timestamp, adjustment_mode)
);
CREATE INDEX IF NOT EXISTS minute_bars_symbol_date_idx
  ON minute_bars(symbol, trade_date, timestamp);
```

`INSERT ... ON CONFLICT` may update OHLCV only while `minute_bars.closed = 0`. A `closed=True` write closes the stored row. Implement `upsert`, `read`, and `prune` with one SQLite connection per method and `sqlite3.Row` parsing.

- [ ] **Step 4: Verify GREEN**

Run: `cd apps/api && uv run pytest tests/test_chanlun_store.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/chanlun/store.py apps/api/tests/test_chanlun_store.py
git commit -m "feat: persist canonical chanlun minute bars"
```

## Task 5: Add Optional `mootdx` History Backfill

**Files:**
- Create: `apps/api/app/providers/tdx_minute_history.py`
- Create: `apps/api/tests/test_tdx_minute_history.py`
- Modify: `apps/api/app/main.py`

- [ ] **Step 1: Write failing provider tests with a fake client**

```python
def test_provider_requests_one_minute_category_in_pages() -> None:
    client = FakeMootdxClient(pages=[frame_for("2026-07-10 09:30"), frame_for("2026-07-09 09:30")])
    provider = TdxMinuteHistoryProvider(client_factory=lambda: client, enabled=True, timeout_seconds=3)

    bars = provider.get_minute_bars("600000.SH", max_bars=1600)

    assert client.calls == [("600000", 7, 0, 800), ("600000", 7, 800, 800)]
    assert len(bars) == 2
    assert bars[0].timestamp < bars[1].timestamp


def test_disabled_provider_never_constructs_a_client() -> None:
    provider = TdxMinuteHistoryProvider(client_factory=lambda: (_ for _ in ()).throw(AssertionError()), enabled=False, timeout_seconds=3)

    with pytest.raises(StrongStockDataUnavailable, match="未启用"):
        provider.get_minute_bars("600000.SH", max_bars=800)
```

- [ ] **Step 2: Verify RED**

Run: `cd apps/api && uv run pytest tests/test_tdx_minute_history.py -q`

Expected: FAIL with missing provider.

- [ ] **Step 3: Implement provider and injection factory**

`TdxMinuteHistoryProvider` imports `mootdx` in its default factory, not at module import time. Request category `7` in 800-bar pages, normalize dataframe-like `datetime/open/high/low/close/vol/amount` fields to `TickFlowIntradayBar`, sort, deduplicate, and reject invalid prices. The code shape is:

```python
def get_minute_bars(self, symbol: str, *, max_bars: int) -> list[TickFlowIntradayBar]:
    if not self.enabled:
        raise StrongStockDataUnavailable("通达信分钟历史未启用")
    client = self.client_factory()
    try:
        frames = [
            client.bars(symbol=normalize_code(symbol), frequency=7, start=start, offset=800)
            for start in range(0, max_bars, 800)
        ]
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    return normalize_tdx_frames(frames, symbol=symbol)
```

Add `_chanlun_history_provider()` in `main.py` using the new settings and `app.state.chanlun_history_provider` injection. The provider returns recent rolling history only; callers must report insufficient data rather than fabricate an older time range.

- [ ] **Step 4: Verify GREEN**

Run: `cd apps/api && uv run pytest tests/test_tdx_minute_history.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/providers/tdx_minute_history.py apps/api/tests/test_tdx_minute_history.py apps/api/app/main.py
git commit -m "feat: add chanlun minute history provider"
```

## Task 6: Build the `czsc` Adapter and Phase 1 Structure Layers

**Files:**
- Create: `apps/api/app/services/chanlun/adapter.py`
- Create: `apps/api/tests/test_chanlun_adapter.py`

- [ ] **Step 1: Write fixture-backed adapter tests**

```python
def test_adapter_maps_czsc_fractals_strokes_and_confirmed_zone() -> None:
    analysis = ChanlunAdapter().analyze("600000.SH", period="1d", bars=fixture_bars())

    assert analysis.availability == "ready"
    assert [item.mark for item in analysis.fractals] == ["bottom", "top", "bottom"]
    assert [item.direction for item in analysis.strokes] == ["up", "down"]
    assert analysis.zones[0].virtual is False
    assert analysis.zones[0].status in {"confirmed", "final"}


def test_adapter_does_not_confirm_the_observing_tail() -> None:
    analysis = ChanlunAdapter().analyze("600000.SH", period="5m", bars=fixture_bars(), include_observing=True)

    assert all(item.status != "confirmed" for item in analysis.strokes if item.end_at == analysis.bars[-1].date)


def test_adapter_returns_unavailable_when_native_runtime_cannot_import(monkeypatch) -> None:
    monkeypatch.setattr("app.services.chanlun.adapter._load_czsc", lambda: (_ for _ in ()).throw(ImportError("missing")))

    assert ChanlunAdapter().analyze("600000.SH", period="1d", bars=fixture_bars()).availability == "unavailable"
```

- [ ] **Step 2: Verify RED**

Run: `cd apps/api && uv run pytest tests/test_chanlun_adapter.py -q`

Expected: FAIL because the adapter is absent.

- [ ] **Step 3: Implement lazy native conversion and mapping**

Use the pinned public API only through `_load_czsc()`:

```python
def _to_raw_bars(symbol: str, period: ChanlunPeriod, bars: list[KlineBar]) -> list[object]:
    RawBar, Freq, _CZSC = _load_czsc()
    return [
        RawBar(
            id=index,
            symbol=symbol,
            dt=datetime.fromisoformat(bar.date),
            freq=_freq_for_period(Freq, period),
            open=bar.open,
            close=bar.close,
            high=bar.high,
            low=bar.low,
            vol=bar.volume,
            amount=bar.amount or 0,
        )
        for index, bar in enumerate(bars)
    ]
```

Map `CZSC(raw_bars).fx_list`, `bi_list`, and `zs_list` to the project models with stable IDs. Derive a segment from at least three alternating completed strokes; never use the final incomplete stroke. Derive one provisional virtual zone only from the latest three completed strokes when their price ranges overlap. Catch `ImportError`, `OSError`, and invalid-bar failures inside the adapter and return `unavailable`/`insufficient_bars` source state instead of raising.

Do not implement MACD, divergence, or buy/sell labels in this task.

- [ ] **Step 4: Verify GREEN**

Run: `cd apps/api && uv run pytest tests/test_chanlun_adapter.py -q`

Expected: PASS. If pinned-library output differs, print the raw `fx_list`, `bi_list`, and `zs_list` from the fixture before changing expected data; do not change mapping rules blindly.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/chanlun/adapter.py apps/api/tests/test_chanlun_adapter.py
git commit -m "feat: add czsc chanlun structure adapter"
```

## Task 7: Compose Stored Bars, Sources, Cache, and Backfill Jobs

**Files:**
- Create: `apps/api/app/services/chanlun/service.py`
- Create: `apps/api/app/services/chanlun/symbols.py`
- Create: `apps/api/tests/test_chanlun_service.py`
- Modify: `apps/api/app/main.py`

- [ ] **Step 1: Write failing service tests**

```python
def test_service_uses_closed_store_bars_before_observing_tail(tmp_path: Path) -> None:
    service = ChanlunAnalysisService(
        store=seeded_store(tmp_path),
        intraday_provider=FakeQuoteProvider(),
        history_provider=FakeHistoryProvider(),
        adapter=FakeAdapter(),
    )

    result = service.analysis("600000.SH", period="5m", lookback=120, include_observing=True, now=shanghai("2026-07-10 10:02"))

    assert result.last_closed_bar_at == "2026-07-10T10:00:00+08:00"
    assert result.bars[-1].date == "2026-07-10T10:00:00+08:00"


def test_service_returns_insufficient_bars_without_calling_adapter(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    result = ChanlunAnalysisService(store=seeded_store(tmp_path), intraday_provider=FakeQuoteProvider(), history_provider=FakeHistoryProvider(), adapter=adapter).analysis(
        "600000.SH", period="60m", lookback=120, include_observing=False
    )

    assert result.availability == "insufficient_bars"
    assert adapter.calls == []


def test_backfill_writes_history_once_and_reports_progress(tmp_path: Path) -> None:
    progress: list[tuple[int, int, str]] = []
    service = ChanlunAnalysisService(
        store=seeded_store_with_no_rows(tmp_path),
        intraday_provider=FakeQuoteProvider(),
        history_provider=FakeHistoryProvider(two_history_rows()),
        adapter=FakeAdapter(),
        cache=build_test_cache(),
    )

    result = service.backfill("600000.SH", progress=lambda current, total, message: progress.append((current, total, message)), should_cancel=lambda: False)

    assert result["written_bars"] == 2
    assert progress[-1][0] == progress[-1][1]
```

Also cover cache-key invalidation when the last closed bar changes and `stale` fallback only when stored history exists.

- [ ] **Step 2: Verify RED**

Run: `cd apps/api && uv run pytest tests/test_chanlun_service.py -q`

Expected: FAIL with missing service.

- [ ] **Step 3: Implement the analysis service**

Implement these exact `ChanlunAnalysisService` methods: `analysis(self, symbol: str, *, period: ChanlunPeriod, lookback: int, include_observing: bool, now: datetime | None = None) -> ChanlunAnalysisResponse`; `workspace(self, symbol: str, *, lookback: int) -> ChanlunWorkspaceResponse`; and `backfill(self, symbol: str, *, progress: ProgressCallback, should_cancel: CancelCheck) -> dict[str, object]`.

Rules:

- Daily uses the existing K-line provider and only completed daily bars.
- Intraday first reads current TickFlow `1m`, upserts it, then derives all 5m/30m/60m output from the SQLite canonical rows through Task 3. Do not treat TickFlow pre-aggregated bars as a second canonical input.
- Require 20 completed bars before adapter invocation. Otherwise return `insufficient_bars` and an explicit source detail.
- `backfill` pages the optional source, writes `closed=True` raw rows, prunes retention, and never calls the adapter.
- Cache finished response copies by symbol, period, lookback, last closed bar timestamp, adjustment mode, and `cl-v1`, using `Settings.chanlun_cache_seconds`.
- A live-source failure returns `stale` only if persisted rows can still produce an analysis; otherwise return an explicit unavailable source state.

Implement `ChanlunSymbolSearchService` as a 24-hour cached wrapper around `akshare.stock_info_a_code_name()`. Its loader is injectable for tests. Normalize code to `.SH`, `.SZ`, or `.BJ`, merge watchlist/latest-screen results first, and return local matches plus failed source status rather than raise when Akshare is unavailable.

Add `_chanlun_minute_store()`, `_chanlun_adapter()`, `_chanlun_analysis_service()`, and `_chanlun_symbol_search_service()` factories in `main.py`, using the existing `app.state` injection pattern.

- [ ] **Step 4: Verify GREEN**

Run: `cd apps/api && uv run pytest tests/test_chanlun_service.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/chanlun/service.py apps/api/app/services/chanlun/symbols.py apps/api/tests/test_chanlun_service.py apps/api/app/main.py
git commit -m "feat: compose chanlun multi-period analysis"
```

## Task 8: Expose Analysis, Workspace, Search, and Backfill APIs

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_api.py`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.test.ts`

- [ ] **Step 1: Write failing API contract tests**

Extend `_client()` so API tests can inject Chanlun services. Add these tests:

```python
def test_chanlun_analysis_endpoint_returns_project_owned_layers(tmp_path: Path) -> None:
    client = _client(tmp_path, chanlun_analysis_service=FakeChanlunService())

    response = client.get("/api/chanlun/stocks/600000.SH/analysis?period=5m&lookback=120")

    assert response.status_code == 200
    assert response.json()["period"] == "5m"
    assert response.json()["rule_version"] == "cl-v1"


def test_chanlun_backfill_reuses_active_symbol_job(tmp_path: Path) -> None:
    client = _client(tmp_path, chanlun_analysis_service=BlockingChanlunService())

    first = client.post("/api/chanlun/stocks/600000.SH/backfill", json={"history_days": 60})
    second = client.post("/api/chanlun/stocks/600000.SH/backfill", json={"history_days": 60})

    assert first.json()["job_id"] == second.json()["job_id"]
```

Add client tests that assert `URLSearchParams` encodes `period`, `lookback`, and `include_observing`, and non-OK responses include status/body text.

- [ ] **Step 2: Verify RED**

Run:

```bash
cd apps/api && uv run pytest tests/test_api.py -k chanlun -q
cd ../web && pnpm exec node --experimental-strip-types --test lib/api.test.ts
```

Expected: FAIL because routes/fetchers are absent.

- [ ] **Step 3: Implement routes and typed client functions**

Add these exact FastAPI paths next to the existing stock routes: `GET /api/chanlun/stocks/{symbol}/analysis`, `GET /api/chanlun/stocks/{symbol}/workspace`, `GET /api/chanlun/symbols/search`, `POST /api/chanlun/stocks/{symbol}/backfill`, and `GET /api/chanlun/stocks/{symbol}/backfill/{job_id}`. Their handler signatures must be the typed signatures exercised by the API tests above.

Validate `lookback` to `20..260` daily and `20..2400` intraday. Use background-job type `chanlun_backfill:{normalized_symbol}` so the active job is deduplicated per symbol. Translate source exceptions to 503 only when there is no stored fallback.

Add `getChanlunAnalysis`, `getChanlunWorkspace`, `searchChanlunSymbols`, `createChanlunBackfillJob`, and `getChanlunBackfillJob` in `apps/web/lib/api.ts`, following existing error handling conventions exactly.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
cd apps/api && uv run pytest tests/test_api.py -k chanlun -q
cd ../web && pnpm exec node --experimental-strip-types --test lib/api.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/main.py apps/api/tests/test_api.py apps/web/lib/api.ts apps/web/lib/types.ts apps/web/lib/api.test.ts
git commit -m "feat: expose chanlun analysis APIs"
```

## Task 9: Draw Typed Chanlun Layers on the Existing K-Line Engine

**Files:**
- Create: `apps/web/lib/chanlunOverlay.ts`
- Create: `apps/web/lib/chanlunOverlay.test.ts`
- Modify: `apps/web/lib/brickIndicator.ts`
- Modify: `apps/web/lib/klineOverlayOption.test.ts`
- Modify: `apps/web/components/TickFlowKlineChart.tsx`

- [ ] **Step 1: Write failing overlay tests**

```ts
test("chanlun overlay renders strokes, segments, and zones with stable ids", () => {
  const series = buildChanlunOverlaySeries(fixtureAnalysis, { fractals: false, strokes: true, segments: true, zones: true });

  assert.deepEqual(series.map((item) => item.id), ["chanlun-zones", "chanlun-strokes", "chanlun-segments"]);
});

test("chanlun overlay omits dense fractals when zoomed out", () => {
  const series = buildChanlunOverlaySeries(fixtureAnalysis, allLayers, { visibleBarCount: 180 });

  assert.equal(series.some((item) => item.id === "chanlun-fractals"), false);
});

test("combined overlay preserves GSGF, Chanlun, and brick ids", () => {
  const option = buildTickFlowOverlayOption({ ...fixture, chanlun: fixtureAnalysis, chanlunLayers: allLayers });
  const ids = (option.series as Array<{ id: string }>).map((item) => item.id);

  assert.equal(new Set(ids).size, ids.length);
});
```

- [ ] **Step 2: Verify RED**

Run: `cd apps/web && pnpm exec node --experimental-strip-types --test lib/chanlunOverlay.test.ts lib/klineOverlayOption.test.ts`

Expected: FAIL because the layer builder and props do not exist.

- [ ] **Step 3: Implement composable ECharts series**

`buildChanlunOverlaySeries` returns only standard ECharts series: zones use a `markArea` carrier, strokes/segments use silent line series, fractals use scatter series. Use colors `#d9363e` sell/up-stroke, `#07845e` buy/down-stroke, `#1769e0` up-segment, and `#7c3aed` down-segment. Confirmed zones use a solid low-opacity fill; virtual/provisional zones use a dashed lighter fill. Do not add gradients or shadows.

Add optional `chanlun`, `chanlunLayers`, and `visibleBarCount` to `buildTickFlowOverlayOption`; append Chanlun series after GSGF and before brick series. When `chanlun` is null, preserve existing output. Extend `TickFlowKlineChart` props with safe defaults. Render fractals only when `visibleBarCount <= 120`.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
cd apps/web
pnpm exec node --experimental-strip-types --test lib/chanlunOverlay.test.ts lib/klineOverlayOption.test.ts
pnpm lint
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/chanlunOverlay.ts apps/web/lib/chanlunOverlay.test.ts apps/web/lib/brickIndicator.ts apps/web/lib/klineOverlayOption.test.ts apps/web/components/TickFlowKlineChart.tsx
git commit -m "feat: render chanlun structure overlays"
```

## Task 10: Build the Standalone Chanlun Workbench and Navigation

**Files:**
- Modify: `apps/web/lib/appNavigation.ts`
- Modify: `apps/web/lib/appNavigation.test.ts`
- Modify: `apps/web/components/AppShell.tsx`
- Create: `apps/web/app/chanlun/page.tsx`
- Create: `apps/web/app/chanlun/ChanlunWorkspace.tsx`
- Create: `apps/web/app/chanlun/chanlunWorkspace.test.ts`
- Modify: `apps/web/app/globals.css`

- [ ] **Step 1: Write failing navigation and pure-helper tests**

```ts
test("navigation selects the Chanlun workbench", () => {
  assert.deepEqual(getNavigationSelection("/chanlun"), { groupKey: "observe", itemKey: "chanlun" });
  assert.ok(navigationGroups.find((group) => group.key === "observe")?.items.some((item) => item.href === "/chanlun"));
});

test("workbench status marks insufficient history non-actionable", () => {
  assert.deepEqual(describeChanlunAvailability("insufficient_bars"), {
    tone: "neutral",
    text: "结构样本不足",
    actionable: false,
  });
});

test("workbench defaults to daily and exposes all four periods", () => {
  assert.equal(resolveChanlunPeriod(undefined), "1d");
  assert.deepEqual(CHANLUN_PERIODS, ["1d", "60m", "30m", "5m"]);
});
```

- [ ] **Step 2: Verify RED**

Run: `cd apps/web && pnpm exec node --experimental-strip-types --test lib/appNavigation.test.ts app/chanlun/chanlunWorkspace.test.ts`

Expected: FAIL because the route/navigation/helpers are absent.

- [ ] **Step 3: Implement the compact workbench**

Add `{ key: "chanlun", href: "/chanlun", label: "缠论工作台" }` to the existing `观察` group and an existing Ant Design chart icon to `AppShell`; do not create a fourth navigation group.

`page.tsx` follows the current dynamic-import `PageFrame` placeholder pattern. `ChanlunWorkspace.tsx` must:

1. Read `symbol` from `useSearchParams`; show an empty focused state rather than silently analysing a hard-coded stock.
2. Provide an accessible Ant Design `AutoComplete` which calls `searchChanlunSymbols`; accept a manually entered normalized code if search is unavailable.
3. Fetch `getChanlunWorkspace` after symbol selection, preserving prior successful content during refresh.
4. Render one fixed four-column state rail (`1d`, `60m`, `30m`, `5m`) with direction, latest zone state, availability, and confirmation time. Each column is a button that selects the primary chart period.
5. Render selected bars through `TickFlowKlineChart` with Chanlun analysis and layer visibility controls.
6. Render source status and one `补齐分钟历史` command only for intraday `insufficient_bars`/`backfilling` states. Start/poll the typed job API and disable the command while active.
7. Render no trade recommendation, divergence, order, alert, or paper-trading controls in Phase 1.

Use the existing `compact-panel`, `app-inset`, token variables, and responsive grid constraints. Add only local `chanlun-status-rail` CSS for the state rail/chart height. Do not use gradients, glass effects, floating page cards, oversized metrics, or nested cards.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
cd apps/web
pnpm exec node --experimental-strip-types --test lib/appNavigation.test.ts app/chanlun/chanlunWorkspace.test.ts
pnpm test
pnpm build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/appNavigation.ts apps/web/lib/appNavigation.test.ts apps/web/components/AppShell.tsx apps/web/app/chanlun/page.tsx apps/web/app/chanlun/ChanlunWorkspace.tsx apps/web/app/chanlun/chanlunWorkspace.test.ts apps/web/app/globals.css
git commit -m "feat: add chanlun analysis workbench"
```

## Task 11: Add a Non-Disruptive Stock-Detail Entry Point

**Files:**
- Modify: `apps/web/app/stock/[symbol]/StockKlineWorkspace.tsx`
- Modify: `apps/web/components/TickFlowKlineChart.tsx`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/lib/types.ts`
- Create: `apps/web/app/stock/[symbol]/stockKlineChanlun.test.ts`

- [ ] **Step 1: Write failing helper tests**

```ts
test("stock detail Chanlun entry preserves normalized symbol", () => {
  assert.equal(buildChanlunWorkspaceHref("600000.sh"), "/chanlun?symbol=600000.SH");
});

test("unavailable Chanlun analysis does not hide existing K-line", () => {
  assert.equal(shouldRenderChanlunOverlay({ availability: "unavailable" }), false);
});
```

- [ ] **Step 2: Verify RED**

Run: `cd apps/web && pnpm exec node --experimental-strip-types --test app/stock/[symbol]/stockKlineChanlun.test.ts`

Expected: FAIL with missing helpers/integration.

- [ ] **Step 3: Add the detail integration**

When the active tab is daily K, load `getChanlunAnalysis(symbol, { period: "1d", lookback: 220 })` independently from the current K-line request. Add a compact `缠论结构` switch alongside GSGF evidence and a link to `/chanlun?symbol=<normalized>`. Pass analysis to `TickFlowKlineChart` only while the switch is active and availability is `ready`.

The default visible Chanlun layers are zones and segments; strokes/fractals are opt-in. On request failure, retain the existing chart exactly and show a muted unavailable state only in the control bar. Do not change chart tabs, sizes, GSGF requests, source labels, or candidate-list behavior.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
cd apps/web
pnpm exec node --experimental-strip-types --test app/stock/[symbol]/stockKlineChanlun.test.ts
pnpm test
pnpm build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/app/stock/[symbol]/StockKlineWorkspace.tsx apps/web/components/TickFlowKlineChart.tsx apps/web/lib/api.ts apps/web/lib/types.ts apps/web/app/stock/[symbol]/stockKlineChanlun.test.ts
git commit -m "feat: add chanlun entry to stock detail"
```

## Task 12: Document, Verify, and Gate Phase 2

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-07-12-chanlun-workbench-design.md` only if verification proves a factual conflict

- [ ] **Step 1: Document operation and limits**

Add a concise README section covering `/chanlun`, supported periods, TickFlow live input, optional `mootdx` bounded rolling history, persistent path `/app/data/chanlun/minute.sqlite3`, retention settings, and the Phase 1 restriction to visual/research structures only. State explicitly that no divergence, alert, paper, or real-trading workflow is available in this phase.

- [ ] **Step 2: Run full backend verification**

Run:

```bash
cd apps/api
uv run pytest -q
uv run ruff check app tests
```

Expected: all backend tests and Ruff PASS.

- [ ] **Step 3: Run full frontend verification**

Run:

```bash
cd apps/web
pnpm test
pnpm build
```

Expected: all frontend tests and production build PASS.

- [ ] **Step 4: Build and smoke-test the production container**

Run:

```bash
cd ../..
docker build -t strong-stock-screener:chanlun-phase1 .
docker run --rm --entrypoint /opt/strong-stock-api-venv/bin/python strong-stock-screener:chanlun-phase1 -c 'import czsc, mootdx; print(czsc.__version__, mootdx.__version__)'
```

Then, with a test/local source configuration, check:

```text
GET /health -> 200
GET /api/chanlun/stocks/600000.SH/analysis?period=1d -> 200 or explicit source failure
GET /api/chanlun/stocks/600000.SH/workspace -> 200 or explicit source failure
```

Do not run a real broad backfill as part of smoke validation.

- [ ] **Step 5: Perform manual visual QA**

Run: `docker compose up --build`

At 1440px and 390px, verify:

- `/chanlun?symbol=600000.SH` shows either usable state rail/K-line or truthful data status;
- zones/segments do not obscure candle data and layer controls do not resize the grid;
- sidebar navigation selects/returns from the workbench;
- `/stock/600000.SH` remains usable with Chanlun unavailable and with its toggle off;
- no Phase 2/3 feature is visible.

- [ ] **Step 6: Check Phase 1 exit criteria**

Proceed only when all conditions hold:

```text
[ ] Pinned czsc imports in the production image.
[ ] Closed minute data persists and never crosses lunch during aggregation.
[ ] History backfill is optional/paged and never blocks stock/K-line paths.
[ ] API data is project-owned, versioned, and truthful about availability.
[ ] Standalone workbench and stock-detail overlay preserve existing K-line/GSGF behavior.
[ ] Full test, build, container smoke, and responsive manual QA pass.
```

If a condition fails, repair Phase 1 or record a blocking decision in the design doc. Do not begin advanced labels, filtering, alerts, or simulation.

- [ ] **Step 7: Commit**

```bash
git add README.md docs/superpowers/specs/2026-07-12-chanlun-workbench-design.md
git commit -m "docs: document chanlun phase one operation"
```
