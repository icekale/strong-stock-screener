# ETF Three-Factor Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a source-traceable ETF three-factor signal workbench, latest completed-day close changes, persistent in-app alerts, and global unread notifications to the existing `/etf-radar` product.

**Architecture:** Keep the existing capital-signal service as the authority for official ETF shares and confirmed Huijin baselines. Add a focused pure scoring module, a persistent store, and an orchestrating monitor that combines TickFlow quotes, daily K-lines, index direction, and official share history; the monitor writes snapshots and alert events that read APIs can serve without external calls. The Vue app consumes those APIs through a dedicated three-factor panel and a global notification-center component.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pytest, Vue 3, TypeScript, Ant Design Vue 4, ECharts 6, Vitest, Vue Test Utils, Pinia-compatible composables.

## Global Constraints

- Monitor exactly the seven symbols in `CORE_ETFS`; validation ETFs may add evidence but never increase the monitored count.
- Use “信号强度” and “疑似活动”; never label a rule score as a calibrated probability or a confirmed Huijin trade.
- Table close change uses the latest completed trading day only; intraday direction is a separate field and separate label.
- Full model: volume `50%` + direction `20%` + share `30%`; normal intraday share delay uses volume `70%` + direction `30%`.
- Do not renormalize a single remaining factor when volume or direction data fails.
- Price and volume scans run every 60 seconds only during `09:30-11:30` and `13:00-15:00` Asia/Shanghai on weekdays.
- Post-close share upgrades run at `19:05` and `19:35`; alert retention is 30 days; same-symbol same-level cooldown is 30 minutes.
- Frontend notification polling is 30 seconds while visible and stops while `document.hidden` is true.
- Reuse the existing workbench tokens and red-up/green-down convention; do not copy the reference site's visual skin.
- Do not modify or commit the pre-existing untracked `apps/web/pnpm-workspace.yaml`.

---

### Task 1: Pure Three-Factor Rules and API Models

**Files:**
- Create: `apps/api/app/services/etf_three_factor.py`
- Modify: `apps/api/app/models.py`
- Test: `apps/api/tests/test_etf_three_factor.py`

**Interfaces:**
- Produces: `volume_factor_score(volume_ratio: float | None) -> float | None`
- Produces: `direction_factor_score(etf_change_pct: float | None, index_change_pct: float | None) -> float | None`
- Produces: `share_factor_score(share_change_pct: float | None) -> float | None`
- Produces: `combine_factor_scores(volume_score, direction_score, share_score, share_pending) -> tuple[float | None, EtfThreeFactorMode]`
- Produces: `summarize_three_factor(items: Sequence[EtfThreeFactorItem]) -> EtfThreeFactorSummary`
- Produces Pydantic contracts used by every later backend and frontend task.

- [ ] **Step 1: Write boundary-first failing tests**

Add table-driven tests that define every approved threshold and the missing-data rule:

```python
@pytest.mark.parametrize(
    ("ratio", "expected"),
    [(3.0, 100), (2.5, 85), (2.0, 70), (1.5, 50), (1.4999, 0), (None, None)],
)
def test_volume_factor_score_boundaries(ratio, expected):
    assert volume_factor_score(ratio) == expected


@pytest.mark.parametrize(
    ("etf", "index", "expected"),
    [(1, -1, 100), (1, 1, 70), (-1, 1, 20), (-1, -1, 0), (None, 1, None)],
)
def test_direction_factor_score_matrix(etf, index, expected):
    assert direction_factor_score(etf, index) == expected


def test_intraday_two_factor_mode_uses_70_30_weights():
    score, mode = combine_factor_scores(100, 70, None, share_pending=True)
    assert score == 91
    assert mode == "two_factor"


def test_non_share_failure_does_not_renormalize_one_factor():
    score, mode = combine_factor_scores(100, None, None, share_pending=True)
    assert score is None
    assert mode == "incomplete"
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
cd apps/api
./.venv/bin/python -m pytest tests/test_etf_three_factor.py -q
```

Expected: collection fails because `app.services.etf_three_factor` and the new model types do not exist.

- [ ] **Step 3: Add exact Pydantic contracts**

Add these contracts to `app/models.py`, using the project's existing `StrongStockSourceStatus` and metadata conventions:

```python
EtfThreeFactorMode = Literal["three_factor", "two_factor", "incomplete"]
EtfThreeFactorLevel = Literal["high", "medium", "low", "incomplete"]
EtfFactorStatus = Literal["available", "pending", "missing", "stale"]
EtfAlertType = Literal["single_high", "single_upgrade", "market_watch", "market_high"]


class EtfFactorEvidence(BaseModel):
    score: float | None = None
    value: float | None = None
    status: EtfFactorStatus
    source: str
    data_date: str | None = None
    updated_at: str | None = None
    detail: str | None = None


class EtfThreeFactorItem(BaseModel):
    symbol: str
    name: str
    index_name: str
    index_symbol: str
    close_change_pct: float | None = None
    close_change_trade_date: str | None = None
    intraday_change_pct: float | None = None
    index_change_pct: float | None = None
    current_volume: float | None = None
    average_volume_20d: float | None = None
    volume_ratio: float | None = None
    share_change_pct: float | None = None
    volume_factor: EtfFactorEvidence
    direction_factor: EtfFactorEvidence
    share_factor: EtfFactorEvidence
    signal_score: float | None = None
    mode: EtfThreeFactorMode
    level: EtfThreeFactorLevel
    updated_at: str


class EtfThreeFactorSummary(BaseModel):
    signal_score: float | None = None
    level: EtfThreeFactorLevel = "incomplete"
    valid_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    market_state: Literal["high", "watch", "normal", "incomplete"] = "incomplete"


class EtfThreeFactorResponse(CapitalSignalMetadata):
    summary: EtfThreeFactorSummary = Field(default_factory=EtfThreeFactorSummary)
    items: list[EtfThreeFactorItem] = Field(default_factory=list)
    monitor_running: bool = False
    last_scan_at: str | None = None


class EtfThreeFactorHistoryPoint(BaseModel):
    trade_date: str
    symbol: str
    close_change_pct: float | None = None
    volume: float | None = None
    average_volume_20d: float | None = None
    volume_ratio: float | None = None
    total_shares: float | None = None
    share_change_pct: float | None = None
    signal_score: float | None = None
    level: EtfThreeFactorLevel = "incomplete"


class EtfThreeFactorHistoryResponse(CapitalSignalMetadata):
    symbol: str
    points: list[EtfThreeFactorHistoryPoint] = Field(default_factory=list)


class EtfActivityAlert(BaseModel):
    alert_id: str
    trade_date: str
    alert_type: EtfAlertType
    level: Literal["watch", "high"]
    symbol: str | None = None
    title: str
    message: str
    signal_score: float
    triggered_at: str
    last_triggered_at: str
    evidence: dict[str, float | str | None] = Field(default_factory=dict)
    read: bool = False


class EtfActivityAlertResponse(BaseModel):
    unread_count: int = 0
    alerts: list[EtfActivityAlert] = Field(default_factory=list)
```

Also add `close_change_pct` and `close_change_trade_date` as nullable fields on `HuijinEtfActivityItem`.

- [ ] **Step 4: Implement pure rule functions**

Implement only deterministic calculations in `etf_three_factor.py`. Define the index mapping in the same file:

```python
INDEX_SYMBOL_BY_ETF = MappingProxyType({
    "510050.SH": "000016.SH",
    "510300.SH": "000300.SH",
    "510500.SH": "000905.SH",
    "512100.SH": "000852.SH",
    "159915.SZ": "399006.SZ",
    "510230.SH": "000018.SH",
    "588080.SH": "000688.SH",
})


def signal_level(score: float | None) -> EtfThreeFactorLevel:
    if score is None:
        return "incomplete"
    if score >= 70:
        return "high"
    if score >= 50:
        return "medium"
    return "low"
```

`summarize_three_factor` must return `market_state="incomplete"` for fewer than five valid items, `"high"` for average `>=70` plus at least five high items, `"watch"` for average `>=50` plus at least three high items, and `"normal"` otherwise.

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```bash
cd apps/api
./.venv/bin/python -m pytest tests/test_etf_three_factor.py -q
./.venv/bin/python -m ruff check app/services/etf_three_factor.py app/models.py tests/test_etf_three_factor.py
```

Expected: all new scoring tests pass and Ruff reports no errors.

- [ ] **Step 6: Commit Task 1**

```bash
git add apps/api/app/models.py apps/api/app/services/etf_three_factor.py apps/api/tests/test_etf_three_factor.py
git commit -m "feat: define ETF three-factor rules"
```

---

### Task 2: Persistent Snapshot, History, and Alert Store

**Files:**
- Create: `apps/api/app/services/etf_three_factor_store.py`
- Test: `apps/api/tests/test_etf_three_factor_store.py`

**Interfaces:**
- Consumes: models from Task 1.
- Produces: `EtfThreeFactorStore.load_snapshot()`, `save_snapshot(response)`.
- Produces: `load_history(symbol, days)`, `upsert_history(points)`.
- Produces: `load_alerts(unread_only=False)`, `upsert_alert(alert, cooldown_minutes=30)`, `mark_read(alert_id)`, `mark_all_read()`.

- [ ] **Step 1: Write failing persistence and deduplication tests**

Cover atomic round trips, 30-day retention, same-level cooldown, upgrades, and read state:

```python
def test_store_deduplicates_same_level_but_keeps_upgrade(tmp_path):
    store = EtfThreeFactorStore(tmp_path)
    first = alert("a1", "single_high", score=72, triggered_at="2026-07-22T10:00:00+08:00")
    duplicate = alert("a2", "single_high", score=75, triggered_at="2026-07-22T10:10:00+08:00")
    upgrade = alert("a3", "single_upgrade", score=84, triggered_at="2026-07-22T10:11:00+08:00")

    assert store.upsert_alert(first) is True
    assert store.upsert_alert(duplicate) is False
    assert store.upsert_alert(upgrade) is True
    assert [row.alert_id for row in store.load_alerts()] == ["a3", "a1"]
```

- [ ] **Step 2: Run focused tests and verify RED**

```bash
cd apps/api
./.venv/bin/python -m pytest tests/test_etf_three_factor_store.py -q
```

Expected: import failure for `EtfThreeFactorStore`.

- [ ] **Step 3: Implement one focused atomic store**

Use three files below `data_dir / "capital-signals"`:

```python
self.snapshot_path = root / "etf-three-factor-snapshot.json"
self.history_path = root / "etf-three-factor-history.json"
self.alerts_path = root / "etf-activity-alerts.json"
```

Use `TypeAdapter`, the existing `RLock` pattern, and temporary-file replacement. History keeps 60 trade dates so the API can safely return 40; alerts retain only rows whose `trade_date >= today - 30 days`. Persist read state in the alert object.

- [ ] **Step 4: Run store tests and verify GREEN**

```bash
cd apps/api
./.venv/bin/python -m pytest tests/test_etf_three_factor_store.py -q
./.venv/bin/python -m ruff check app/services/etf_three_factor_store.py tests/test_etf_three_factor_store.py
```

- [ ] **Step 5: Commit Task 2**

```bash
git add apps/api/app/services/etf_three_factor_store.py apps/api/tests/test_etf_three_factor_store.py
git commit -m "feat: persist ETF activity alerts"
```

---

### Task 3: Market Data Assembly and Three-Factor Monitor

**Files:**
- Create: `apps/api/app/services/etf_three_factor_monitor.py`
- Test: `apps/api/tests/test_etf_three_factor_monitor.py`
- Modify: `apps/api/app/services/capital_signals.py`
- Test: `apps/api/tests/test_capital_signals.py`

**Interfaces:**
- Consumes: `TickFlowQuoteProvider.get_quotes(symbols)` and `TickFlowDailyKlineProvider.get_klines(symbol, count)`.
- Consumes: `CapitalSignalService.overview()` and `CapitalSignalStore.load_share_history()` for official shares.
- Produces: `EtfThreeFactorMonitor.scan(now=None, force=False) -> EtfThreeFactorResponse`.
- Produces: `EtfThreeFactorMonitor.latest() -> EtfThreeFactorResponse` with no external call.
- Produces: `EtfThreeFactorMonitor.history(symbol, days=40) -> EtfThreeFactorHistoryResponse`.
- Produces: `EtfThreeFactorMonitor.enrich_overview(overview) -> EtfRadarOverviewResponse`.

- [ ] **Step 1: Write failing service tests with fake providers**

Create fakes that expose seven ETF quotes, seven index quotes, 21 completed daily bars per ETF, and official share rows. Test these behaviors separately:

```python
def test_scan_builds_two_factor_intraday_item(tmp_path):
    monitor = monitor_with(
        volume=300,
        historical_volumes=[100] * 20,
        etf_change=1.2,
        index_change=-0.5,
        share_pending=True,
        tmp_path=tmp_path,
    )
    result = monitor.scan(now=shanghai("2026-07-22T10:30:00"))
    item = by_symbol(result, "510050.SH")
    assert item.volume_ratio == 3
    assert item.volume_factor.score == 100
    assert item.direction_factor.score == 100
    assert item.share_factor.status == "pending"
    assert item.signal_score == 100
    assert item.mode == "two_factor"


def test_post_close_share_refresh_upgrades_to_three_factor(tmp_path):
    result = monitor_with_share_change(tmp_path, share_change_pct=5.0).scan(
        now=shanghai("2026-07-22T19:05:00")
    )
    item = by_symbol(result, "510050.SH")
    assert item.share_factor.score == 100
    assert item.mode == "three_factor"
```

Also test: current partial day is excluded from 20-day baseline; fewer than 20 completed bars makes volume unavailable; quote or index failure keeps the old snapshot and creates no event; latest completed close change uses two completed bars; history writes one point per symbol and trade date.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
cd apps/api
./.venv/bin/python -m pytest tests/test_etf_three_factor_monitor.py tests/test_capital_signals.py -q
```

Expected: monitor import fails and close-change fields are not populated.

- [ ] **Step 3: Implement provider protocols and daily cache**

Define narrow protocols inside `etf_three_factor_monitor.py`:

```python
class QuoteProvider(Protocol):
    def get_quotes(self, symbols: list[str]) -> list[object]: ...


class DailyKlineProvider(Protocol):
    def get_klines(self, symbol: str, count: int = 40) -> list[KlineBar]: ...


class ShareSnapshotProvider(Protocol):
    def overview(self, *, force: bool = False) -> EtfRadarOverviewResponse: ...
```

Cache daily bars by `(trade_date, symbol)` and fetch each ETF at most once per completed trading date. Use quote `volume` as current cumulative volume. Do not substitute turnover amount for volume.

Current and historical volume must come from the same TickFlow unit convention. A quote whose `quote_time` does not match the current Shanghai trade date is stale and cannot create a new intraday signal; this also prevents weekday public holidays from producing alerts.

- [ ] **Step 4: Implement scan assembly and evidence status**

For each `CORE_ETFS` item:

1. map its index through `INDEX_SYMBOL_BY_ETF`;
2. calculate the 20 completed-day mean volume;
3. calculate latest completed close change;
4. read real-time ETF/index direction only during the scan window;
5. read `daily_change_pct` from the official overview only when its `trade_date` equals the scan trade date and both share dates are real;
6. call Task 1 scoring functions;
7. persist snapshot and one daily history point.

Use `EtfFactorEvidence.status="pending"` only for the expected pre-19:00 share delay. Network or schema failures use `"missing"` or `"stale"` and a concrete detail.

- [ ] **Step 5: Generate alert candidates without sending them**

Compare the prior stored snapshot with the new snapshot:

```python
if previous.level != "high" and current.level == "high":
    alert_type = "single_upgrade" if current.mode == "three_factor" else "single_high"
```

Generate `market_watch` on entry into `summary.market_state == "watch"` and `market_high` on entry into `"high"`. Pass candidates to `store.upsert_alert`; only persisted new events appear in the API. Titles must contain “疑似活动” and messages must include factor values and source times.

- [ ] **Step 6: Enrich the existing overview with completed close changes**

`enrich_overview` must copy only `core_items` and `validation_items`, adding matching `close_change_pct` and `close_change_trade_date` without mutating the persisted capital snapshot. If the three-factor snapshot is unavailable, return the original overview unchanged.

- [ ] **Step 7: Run focused and capital regression tests**

```bash
cd apps/api
./.venv/bin/python -m pytest tests/test_etf_three_factor_monitor.py tests/test_capital_signals.py -q
./.venv/bin/python -m ruff check app/services/etf_three_factor_monitor.py app/services/capital_signals.py tests/test_etf_three_factor_monitor.py
```

- [ ] **Step 8: Commit Task 3**

```bash
git add apps/api/app/services/etf_three_factor_monitor.py apps/api/app/services/capital_signals.py apps/api/tests/test_etf_three_factor_monitor.py apps/api/tests/test_capital_signals.py
git commit -m "feat: monitor ETF three-factor signals"
```

---

### Task 4: Scheduler and FastAPI Endpoints

**Files:**
- Create: `apps/api/app/services/etf_three_factor_sampler.py`
- Test: `apps/api/tests/test_etf_three_factor_sampler.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_api.py`

**Interfaces:**
- Consumes: `EtfThreeFactorMonitor.scan`, `latest`, `history`, and store alert methods.
- Produces: `EtfThreeFactorSampler.start()`, `stop_and_wait()`, `sample_once()`.
- Produces the five routes defined in the approved design.

- [ ] **Step 1: Write failing scheduler window tests**

Use an injected clock and scan callback. Cover `09:29` false, `09:30` true, `11:30` true, lunch false, `13:00` true, `15:00` true, `15:05` one close refresh, `19:05` and `19:35` share refresh, weekend false, and a stopped thread that joins cleanly.

```python
def test_sampler_runs_intraday_once_per_minute():
    calls = []
    sampler = EtfThreeFactorSampler(scan=lambda **kwargs: calls.append(kwargs), clock=clock("2026-07-22T10:00:10"))
    assert sampler.sample_once() is True
    assert sampler.sample_once() is False
    assert len(calls) == 1
```

- [ ] **Step 2: Run sampler tests and verify RED**

```bash
cd apps/api
./.venv/bin/python -m pytest tests/test_etf_three_factor_sampler.py -q
```

- [ ] **Step 3: Implement the sampler using existing thread lifecycle patterns**

Mirror `CapitalSignalSampler`'s `Event`, `Thread`, lifecycle lock, and `stop_and_wait`. Use a minute key (`YYYY-MM-DDTHH:MM`) to prevent duplicate intraday scans and separate completion keys for `15:05`, `19:05`, and `19:35`. Scanner exceptions are logged and never terminate the thread.

- [ ] **Step 4: Write failing API tests**

Inject `app.state.etf_three_factor_monitor` and assert:

```python
assert client.get("/api/etf-radar/three-factor").status_code == 200
assert client.get("/api/etf-radar/three-factor/510050.SH/history?days=40").status_code == 200
assert client.get("/api/etf-radar/three-factor/600000.SH/history").status_code == 404
assert client.get("/api/etf-radar/alerts?unread_only=true").json()["unread_count"] == 2
assert client.post("/api/etf-radar/alerts/a1/read").status_code == 200
assert client.post("/api/etf-radar/alerts/read-all").status_code == 200
```

Also assert `/api/etf-radar/overview` calls `enrich_overview` and returns completed-day close fields.

- [ ] **Step 5: Wire factories, lifespan, and routes**

Add `_etf_three_factor_monitor()` that shares `_quote_provider()`, `_daily_kline_provider()`, `_capital_signal_service()`, and a single `EtfThreeFactorStore(settings.data_dir)`. Add startup/shutdown functions guarded by `app.state.etf_three_factor_sampler_disabled`, then include them in lifespan next to the capital sampler.

Routes must serve `monitor.latest()` and store reads; only an explicit test/admin force path may call `scan()`. Validate `symbol in CORE_ETFS` before history access and return 404 for unknown symbols or alert IDs.

- [ ] **Step 6: Run API and scheduler tests**

```bash
cd apps/api
./.venv/bin/python -m pytest tests/test_etf_three_factor_sampler.py tests/test_api.py -q
./.venv/bin/python -m ruff check app/main.py app/services/etf_three_factor_sampler.py tests/test_etf_three_factor_sampler.py
```

- [ ] **Step 7: Commit Task 4**

```bash
git add apps/api/app/main.py apps/api/app/services/etf_three_factor_sampler.py apps/api/tests/test_api.py apps/api/tests/test_etf_three_factor_sampler.py
git commit -m "feat: expose ETF activity monitor API"
```

---

### Task 5: Vue API Types and Domain Formatting

**Files:**
- Modify: `apps/web-vue/src/service/types.ts`
- Modify: `apps/web-vue/src/service/product-api.ts`
- Modify: `apps/web-vue/src/service/api.test.ts`
- Create: `apps/web-vue/src/utils/domain/etfThreeFactor.ts`
- Create: `apps/web-vue/src/utils/domain/etfThreeFactor.test.ts`

**Interfaces:**
- Consumes: backend JSON contracts from Tasks 1 and 4.
- Produces: `getEtfThreeFactor`, `getEtfThreeFactorHistory`, `getEtfActivityAlerts`, `markEtfAlertRead`, `markAllEtfAlertsRead`.
- Produces: formatting and tone helpers used by the page and notification center.

- [ ] **Step 1: Add failing API request tests**

Mock `fetch` and verify exact method/path pairs, including encoded alert IDs and `unread_only`:

```ts
await getEtfThreeFactorHistory('510050.SH', 40);
expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/etf-radar/three-factor/510050.SH/history?days=40'));

await markAllEtfAlertsRead();
expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/etf-radar/alerts/read-all'), expect.objectContaining({ method: 'POST' }));
```

- [ ] **Step 2: Add failing domain-helper tests**

```ts
expect(signalLevelLabel('high')).toBe('高确信');
expect(factorStatusLabel('pending')).toBe('待盘后');
expect(formatVolumeRatio(3)).toBe('3.00倍');
expect(signalTone('high')).toBe('danger');
expect(closeChangeTone(-1.2)).toBe('fall');
```

- [ ] **Step 3: Run frontend tests and verify RED**

```bash
cd apps/web-vue
pnpm test:unit -- src/service/api.test.ts src/utils/domain/etfThreeFactor.test.ts
```

Expected: missing exports and missing helper module.

- [ ] **Step 4: Implement exact TypeScript contracts and API functions**

Mirror every nullable backend field; do not use optional properties for fields guaranteed by Pydantic. Add `close_change_pct` and `close_change_trade_date` to `HuijinEtfActivityItem`.

Use the existing `apiFetch` error handling and `API_BASE_URL` conventions. POST endpoints send no body unless the shared helper requires an empty JSON object.

- [ ] **Step 5: Implement pure display helpers**

Keep A-share color semantics centralized:

```ts
export function closeChangeTone(value: number | null): 'rise' | 'fall' | 'flat' {
  if (value === null || value === 0) return 'flat';
  return value > 0 ? 'rise' : 'fall';
}
```

Factor status text must distinguish `pending` as “待盘后”, `missing` as “不可用”, and `stale` as “已过期”.

- [ ] **Step 6: Run unit tests, typecheck, and commit**

```bash
cd apps/web-vue
pnpm test:unit -- src/service/api.test.ts src/utils/domain/etfThreeFactor.test.ts
pnpm typecheck
cd ../..
git add apps/web-vue/src/service/types.ts apps/web-vue/src/service/product-api.ts apps/web-vue/src/service/api.test.ts apps/web-vue/src/utils/domain/etfThreeFactor.ts apps/web-vue/src/utils/domain/etfThreeFactor.test.ts
git commit -m "feat: add ETF monitor client contracts"
```

---

### Task 6: Three-Factor Workbench and Completed-Close Column

**Files:**
- Create: `apps/web-vue/src/components/etf-radar/EtfThreeFactorPanel.vue`
- Create: `apps/web-vue/src/components/etf-radar/EtfThreeFactorPanel.test.ts`
- Modify: `apps/web-vue/src/views/EtfRadarView.vue`
- Modify: `apps/web-vue/src/views/EtfRadarView.test.ts`

**Interfaces:**
- Consumes: Task 5 types, API functions, and formatters.
- Produces: the approved top summary, seven-symbol status strip, alert summary, sortable table, selected-symbol factor details, three charts, and timeline.
- Produces route-query selection contract `/etf-radar?symbol=510050.SH&tab=activity` for notifications.

- [ ] **Step 1: Write failing component tests for information hierarchy**

Mount a seven-item fixture and verify:

```ts
expect(wrapper.get('[data-testid="three-factor-summary"]').text()).toContain('综合信号强度');
expect(wrapper.findAll('[data-testid="dragon-status"]')).toHaveLength(7);
expect(wrapper.get('[data-testid="three-factor-table"]').text()).toContain('收盘涨跌');
expect(wrapper.get('[data-testid="three-factor-table"]').text()).toContain('20日均量');
expect(wrapper.get('[data-testid="factor-detail"]').text()).toContain('量能因子');
expect(wrapper.findAll('[data-testid="three-factor-chart"]')).toHaveLength(3);
expect(wrapper.get('[data-testid="signal-timeline"]').text()).toContain('HIGH');
expect(wrapper.text()).toContain('疑似活动');
expect(wrapper.text()).not.toContain('确认买入');
```

Also verify selecting a status item changes the detail without another API request and null share evidence renders “待盘后”.

- [ ] **Step 2: Add failing ETF view tests**

Extend the API mock with `getEtfThreeFactor` and `getEtfThreeFactorHistory`. Assert that opening “日度活动” loads the latest snapshot once, the existing activity table contains a “收盘涨跌” column with red/green classes, and `?symbol=159915.SZ&tab=activity` selects that item.

- [ ] **Step 3: Run focused component tests and verify RED**

```bash
cd apps/web-vue
pnpm test:unit -- src/components/etf-radar/EtfThreeFactorPanel.test.ts src/views/EtfRadarView.test.ts
```

- [ ] **Step 4: Implement the panel as full-width workbench bands**

Use one component with these bounded sections:

```text
.etf-three-factor__summary
.etf-three-factor__dragons
.etf-three-factor__monitor
.etf-three-factor__table
.etf-three-factor__detail
.etf-three-factor__timeline
```

Do not nest decorative cards. Use `grid-template-columns`, tabular numerals, fixed table widths, an internal horizontal scroll region, and existing `--wb-*` variables. Use a compact horizontal status strip; mobile keeps stable item widths and scrolls that strip.

Load ECharts asynchronously and disable entry animation. Volume chart shows daily volume plus 20-day average; share chart preserves null gaps; ETF/index comparison uses the same date domain.

- [ ] **Step 5: Integrate into the activity tab**

Load the three-factor latest snapshot when the activity tab is first opened, cache it for 15 seconds, and preserve the old response on refresh failure. Add `close_change_pct` after the ETF column in `coreColumns` and include it in `valueTone` formatting. Rename the old ambiguous share column label from “日变化” to “份额日变化”.

Read route query once on mount and watch later query changes. A query-selected symbol must be validated against the seven returned items before selection.

- [ ] **Step 6: Run focused tests and frontend quality gates**

```bash
cd apps/web-vue
pnpm test:unit -- src/components/etf-radar/EtfThreeFactorPanel.test.ts src/views/EtfRadarView.test.ts
pnpm typecheck
pnpm build
```

- [ ] **Step 7: Commit Task 6**

```bash
git add apps/web-vue/src/components/etf-radar/EtfThreeFactorPanel.vue apps/web-vue/src/components/etf-radar/EtfThreeFactorPanel.test.ts apps/web-vue/src/views/EtfRadarView.vue apps/web-vue/src/views/EtfRadarView.test.ts
git commit -m "feat: add ETF three-factor workbench"
```

---

### Task 7: Global In-App Notification Center

**Files:**
- Create: `apps/web-vue/src/composables/useEtfAlertNotifications.ts`
- Create: `apps/web-vue/src/composables/useEtfAlertNotifications.test.ts`
- Create: `apps/web-vue/src/layouts/modules/global-header/components/etf-alert-center.vue`
- Create: `apps/web-vue/src/layouts/modules/global-header/components/etf-alert-center.test.ts`
- Modify: `apps/web-vue/src/layouts/modules/global-header/index.vue`

**Interfaces:**
- Consumes: Task 5 alert APIs and alert models.
- Produces: one shared polling lifecycle, unread count, alert list, `markRead`, `markAllRead`, and one-time popup dispatch.
- Produces: a global header bell that navigates to `/etf-radar?tab=activity&symbol=<symbol>`.

- [ ] **Step 1: Write failing composable tests with fake timers**

Test immediate load, 30-second visible polling, hidden-page pause, visible-page immediate refresh, popup dedupe, and cleanup:

```ts
documentHidden(false);
const alerts = useEtfAlertNotifications(dependencies);
await flushPromises();
expect(api.getEtfActivityAlerts).toHaveBeenCalledTimes(1);

vi.advanceTimersByTime(30_000);
await flushPromises();
expect(api.getEtfActivityAlerts).toHaveBeenCalledTimes(2);

documentHidden(true);
document.dispatchEvent(new Event('visibilitychange'));
vi.advanceTimersByTime(60_000);
expect(api.getEtfActivityAlerts).toHaveBeenCalledTimes(2);
```

- [ ] **Step 2: Write failing header component tests**

Assert a familiar bell icon button, tooltip, numeric badge, drawer/list, single read, read all, and navigation. The button must have a stable `aria-label="ETF 活动通知"`; zero unread hides the badge but keeps the button.

- [ ] **Step 3: Run focused tests and verify RED**

```bash
cd apps/web-vue
pnpm test:unit -- src/composables/useEtfAlertNotifications.test.ts src/layouts/modules/global-header/components/etf-alert-center.test.ts
```

- [ ] **Step 4: Implement one shared polling composable**

Use module-level state so multiple header mounts do not create multiple intervals. Track `shownAlertIds` in memory and call `window.$notification?.warning` only for unseen unread `single_high`, `single_upgrade`, or `market_high` events. `market_watch` appears in the list without popup.

Stop the interval on hidden visibility, refresh immediately on visible, and release listeners when the final consumer unmounts.

- [ ] **Step 5: Implement the bell and notification drawer/dropdown**

Use an Iconify bell icon already supported by the build, an Ant badge, and a compact drawer or popover. Each row includes level text, title, trigger time, key evidence, and unread state. Clicking a symbol alert marks it read, closes the panel, and uses `router.push({ path: '/etf-radar', query: { tab: 'activity', symbol } })`.

Do not expose external channel settings in this component.

- [ ] **Step 6: Integrate and verify frontend gates**

```bash
cd apps/web-vue
pnpm test:unit -- src/composables/useEtfAlertNotifications.test.ts src/layouts/modules/global-header/components/etf-alert-center.test.ts
pnpm typecheck
pnpm build
```

- [ ] **Step 7: Commit Task 7**

```bash
git add apps/web-vue/src/composables/useEtfAlertNotifications.ts apps/web-vue/src/composables/useEtfAlertNotifications.test.ts apps/web-vue/src/layouts/modules/global-header/components/etf-alert-center.vue apps/web-vue/src/layouts/modules/global-header/components/etf-alert-center.test.ts apps/web-vue/src/layouts/modules/global-header/index.vue
git commit -m "feat: add ETF activity notification center"
```

---

### Task 8: Full Regression, Performance, and Visual Acceptance

**Files:**
- Modify only files from Tasks 1-7 if verification exposes a defect.
- Do not add unrelated refactors or formatting churn.

**Interfaces:**
- Validates the complete backend-to-frontend contract and deployment build.

- [ ] **Step 1: Run the complete backend suite**

```bash
cd apps/api
./.venv/bin/python -m pytest -q
./.venv/bin/python -m ruff check app tests
uv lock --check --offline
```

Expected: zero failures and zero lint errors.

- [ ] **Step 2: Run the complete Vue suite**

```bash
cd apps/web-vue
pnpm test:unit
pnpm typecheck
pnpm build
```

Expected: all tests pass, `vue-tsc` exits 0, and `dist/index.html` exists.

- [ ] **Step 3: Verify no duplicate external requests**

Run the monitor tests with provider call counters and assert:

- one batch quote request per 60-second scan;
- zero external calls from latest/history/alerts read endpoints;
- one daily K-line fetch per ETF per completed trading date;
- notification polling never triggers a model scan;
- route selection changes do not refetch latest data within the 15-second cache.

- [ ] **Step 4: Start a local production-like preview**

```bash
docker build -t icekale/strong-stock-screener:etf-three-factor-test .
docker run --rm -d --name strong-stock-screener-etf-three-factor-test -p 3124:3110 --env-file .env icekale/strong-stock-screener:etf-three-factor-test
```

Wait for container health, then verify:

```bash
curl -fsS http://127.0.0.1:3124/api/etf-radar/three-factor
curl -fsS 'http://127.0.0.1:3124/api/etf-radar/three-factor/510050.SH/history?days=40'
curl -fsS http://127.0.0.1:3124/api/etf-radar/alerts
```

- [ ] **Step 5: Perform desktop and mobile visual QA**

Inspect `http://127.0.0.1:3124/etf-radar?tab=activity&symbol=510050.SH` at desktop and 390px mobile widths. Confirm:

- the close-change column is visible through the table scroll region and uses red-up/green-down;
- all seven status items are readable and horizontally scroll on mobile;
- no text overlap or page-level horizontal overflow;
- charts are nonblank, use real dates, and preserve null gaps;
- popup, badge, drawer, read state, and deep-link selection work;
- the page says “信号强度” and “疑似活动”, never “确认买入”.

- [ ] **Step 6: Inspect final diff and commit verification fixes**

```bash
cd /Users/kale/Documents/strong-stock-screener
git diff --check
git status --short
```

If verification required code changes, stage only files that trace to this feature and commit:

```bash
git commit -m "fix: harden ETF activity monitoring"
```

Leave `apps/web/pnpm-workspace.yaml` untracked and untouched.
