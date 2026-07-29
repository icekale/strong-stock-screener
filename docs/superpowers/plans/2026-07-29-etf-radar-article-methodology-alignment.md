# ETF Radar Article Methodology Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the ETF daily activity table comparable with the 2025 year-end baseline methodology while keeping the 20-day anomaly metric separate, and keep retrying late exchange share disclosures until the three-factor snapshot is complete.

**Architecture:** Preserve the existing exchange ingestion and backend activity formulas. Extend the frontend unified row with explicit signed baseline and 20-day share multiples, render them as separate sortable columns, and change only the sampler schedule so `EtfThreeFactorMonitor` reuses its existing forced share refresh until all seven core ETF share factors are available.

**Tech Stack:** Vue 3, TypeScript, Vitest, FastAPI service layer, Python 3.12, pytest.

## Global Constraints

- Do not modify exchange scraping, share unit conversion, or the formulas for `daily_change_pct`, `baseline_change_pct`, and `multiple`.
- Do not restore the removed aggregate excess-flow panel or add the article's “net 38x” summary.
- Keep `cumulative_baseline_change_pct` in the long-term trajectory only.
- Keep all user-facing language explicit that ETF share changes are subscription/redemption proxies, not confirmed Huijin trades.
- Late share refreshes run in 15-minute buckets from 19:35 through 23:30 and stop at 23:31.
- Do not stage `.superpowers/sdd/task-1-report.md`, `.superpowers/sdd/task-5-report.md`, or the untracked `apps/web/` tree.

---

## File Map

- `apps/web-vue/src/utils/domain/etfThreeFactor.ts`: maps backend activity and three-factor data into table-ready signed metrics.
- `apps/web-vue/src/utils/domain/etfThreeFactor.test.ts`: proves the table model uses daily baseline change instead of cumulative deviation.
- `apps/web-vue/src/components/etf-radar/EtfActivityTable.vue`: renders and sorts the two separate share-multiple definitions.
- `apps/web-vue/src/views/EtfRadarView.test.ts`: verifies user-visible labels, values, and simultaneous 10x markers.
- `apps/api/app/services/etf_three_factor_sampler.py`: schedules late share retries and stops after a complete snapshot.
- `apps/api/tests/test_etf_three_factor_sampler.py`: verifies 15-minute retry buckets, completion, and the 23:31 cutoff.

### Task 1: Correct the Unified ETF Activity Row

**Files:**
- Modify: `apps/web-vue/src/utils/domain/etfThreeFactor.ts`
- Test: `apps/web-vue/src/utils/domain/etfThreeFactor.test.ts`

**Interfaces:**
- Consumes: `HuijinEtfActivityItem.baseline_change_pct`, `.multiple`, `.share_change_20d_multiple`, and `.direction`.
- Produces: `UnifiedEtfActivityRow.baselineChangePct`, `.baselineMultiple`, and `.shareChange20dMultiple`, all `number | null`; the two multiple values are signed for sorting and color treatment.

- [ ] **Step 1: Write the failing domain test**

Add a test that deliberately gives cumulative and daily baseline values different numbers:

```ts
it('keeps daily baseline change separate from cumulative deviation and signs both share multiples', () => {
  const [increase] = buildUnifiedEtfActivityRows([
    activityItem({
      baseline_change_pct: 6.35,
      cumulative_baseline_change_pct: -39.77,
      multiple: 63.5,
      share_change_20d_multiple: 4.5,
      direction: 'increase'
    })
  ], []);
  const [decrease] = buildUnifiedEtfActivityRows([
    activityItem({
      symbol: '510500.SH',
      baseline_change_pct: -2.53,
      cumulative_baseline_change_pct: -70.34,
      multiple: 25.3,
      share_change_20d_multiple: 2.8,
      direction: 'decrease'
    })
  ], []);

  expect(increase).toMatchObject({
    baselineChangePct: 6.35,
    baselineMultiple: 63.5,
    shareChange20dMultiple: 4.5
  });
  expect(decrease).toMatchObject({
    baselineChangePct: -2.53,
    baselineMultiple: -25.3,
    shareChange20dMultiple: -2.8
  });
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
pnpm test:unit -- src/utils/domain/etfThreeFactor.test.ts
```

Working directory: `apps/web-vue`

Expected: FAIL because `baselineChangePct` is `cumulative_baseline_change_pct` and the two explicit multiple fields do not exist.

- [ ] **Step 3: Implement the minimal row mapping**

Extend `UnifiedEtfActivityRow`:

```ts
baselineMultiple: number | null;
shareChange20dMultiple: number | null;
```

Initialize both fields to `null`. Add a private helper:

```ts
function signedMultiple(value: number | null | undefined, direction: HuijinEtfActivityItem['direction']) {
  if (value === null || value === undefined) return null;
  if (direction === 'decrease') return -Math.abs(value);
  if (direction === 'increase') return Math.abs(value);
  if (direction === 'flat') return 0;
  return null;
}
```

Map the activity fields:

```ts
row.baselineChangePct = activity.baseline_change_pct;
row.baselineMultiple = signedMultiple(activity.multiple, activity.direction);
row.shareChange20dMultiple = signedMultiple(activity.share_change_20d_multiple, activity.direction);
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run:

```bash
pnpm test:unit -- src/utils/domain/etfThreeFactor.test.ts
```

Expected: all tests in the file pass.

- [ ] **Step 5: Commit the domain correction**

```bash
git add apps/web-vue/src/utils/domain/etfThreeFactor.ts apps/web-vue/src/utils/domain/etfThreeFactor.test.ts
git commit -m "fix(etf-radar): use daily baseline activity metrics"
```

### Task 2: Separate the Two Share-Multiple Definitions in the Table

**Files:**
- Modify: `apps/web-vue/src/components/etf-radar/EtfActivityTable.vue`
- Modify: `apps/web-vue/src/views/EtfRadarView.test.ts`

**Interfaces:**
- Consumes: `UnifiedEtfActivityRow.baselineMultiple`, `.shareChange20dMultiple`, and `row.activity.is_tenfold` / `.is_tenfold_share_change`.
- Produces: sortable columns named `年末基准日变`, `年末基准倍量`, `20日份额异常`, and `成交量/20日均量`, plus independent `基准10x` and `20日10x` labels.

- [ ] **Step 1: Strengthen the activity fixture and write the failing view test**

Add these defaults to the `activityItem` fixture in `EtfRadarView.test.ts`:

```ts
share_change_20d_avg_abs: 20_000_000,
share_change_20d_multiple: 10.5,
is_tenfold_share_change: true,
```

Replace the old cumulative assertion and add explicit table assertions:

```ts
const tableText = wrapper.get('[data-testid="etf-activity-table"]').text();
expect(tableText).toContain('年末基准日变');
expect(tableText).toContain('年末基准倍量');
expect(tableText).toContain('20日份额异常');
expect(tableText).toContain('成交量/20日均量');
expect(tableText).toContain('+12.00%');
expect(tableText).not.toContain('+14.50%');
expect(tableText).toContain('+12.0x');
expect(tableText).toContain('+10.5x');
expect(tableText).toContain('基准10x');
expect(tableText).toContain('20日10x');
```

- [ ] **Step 2: Run the view test and verify RED**

Run:

```bash
pnpm test:unit -- src/views/EtfRadarView.test.ts
```

Working directory: `apps/web-vue`

Expected: FAIL because the table still labels cumulative deviation as the report baseline field and does not render separate multiple columns or labels.

- [ ] **Step 3: Implement the table columns and labels**

Update `SortKey`:

```ts
type SortKey =
  | 'closeChangePct'
  | 'dailyChangePct'
  | 'baselineChangePct'
  | 'baselineMultiple'
  | 'shareChange20dMultiple'
  | 'volumeRatio'
  | 'signalScore';
```

Add a signed formatter:

```ts
function formatMultiple(value: number | null) {
  return value === null ? '--' : `${value > 0 ? '+' : ''}${value.toFixed(1)}x`;
}
```

Add independent status labels:

```ts
function activityFlags(row: UnifiedEtfActivityRow) {
  if (!row.activity) return [];
  return [
    row.activity.is_tenfold ? '基准10x' : null,
    row.activity.is_tenfold_share_change ? '20日10x' : null
  ].filter((value): value is string => value !== null);
}
```

Render the columns in this order:

```text
ETF / 指数
收盘涨跌
份额日变化
年末基准日变
年末基准倍量
20日份额异常
成交量/20日均量
三因子评分
状态
```

Use `valueClass` for both signed multiple cells. Render each label returned by `activityFlags(row)` as a small tag in the appropriate multiple cell and append both labels to the status text. Increase the table `min-width` and add two numeric `<col>` elements so headers and rows remain aligned.

Remove the `shareChangeEventLabel` import from this component; the old utility remains untouched because the removed aggregate panel tests still cover it.

- [ ] **Step 4: Run the focused frontend tests and verify GREEN**

Run:

```bash
pnpm test:unit -- src/utils/domain/etfThreeFactor.test.ts src/views/EtfRadarView.test.ts
```

Expected: both files pass with the new article-comparable values and labels.

- [ ] **Step 5: Commit the table presentation**

```bash
git add apps/web-vue/src/components/etf-radar/EtfActivityTable.vue apps/web-vue/src/views/EtfRadarView.test.ts
git commit -m "feat(etf-radar): separate share activity multiples"
```

### Task 3: Retry Late Exchange Share Disclosures Until Complete

**Files:**
- Modify: `apps/api/app/services/etf_three_factor_sampler.py`
- Modify: `apps/api/tests/test_etf_three_factor_sampler.py`

**Interfaces:**
- Consumes: the existing `scan(now=current, force=True)` return value, expected to expose `.trade_date`, `.items`, each item `.share_change_pct`, and `.share_factor.status`.
- Produces: `_has_complete_share_snapshot(snapshot: object, trade_date: str) -> bool`; one forced scan per 15-minute late-share bucket until complete or 23:31.

- [ ] **Step 1: Add a real snapshot fixture and failing retry tests**

Add:

```python
from types import SimpleNamespace


def share_snapshot(trade_date: str, *, complete: bool) -> SimpleNamespace:
    return SimpleNamespace(
        trade_date=trade_date,
        items=[
            SimpleNamespace(
                share_change_pct=1.0 if complete else None,
                share_factor=SimpleNamespace(status="available" if complete else "stale"),
            )
            for _ in range(7)
        ],
    )
```

Add the retry test:

```python
def test_sampler_retries_late_shares_once_per_15_minute_bucket_until_complete() -> None:
    current = Clock("2026-07-22T19:35:00")
    calls: list[str] = []
    results = iter([
        share_snapshot("2026-07-22", complete=False),
        share_snapshot("2026-07-22", complete=True),
    ])

    def scan(**kwargs: object) -> object:
        calls.append(kwargs["now"].strftime("%H:%M"))
        return next(results)

    sampler = EtfThreeFactorSampler(scan=scan, clock=current)

    assert sampler.sample_once() is True
    current.current = datetime.fromisoformat("2026-07-22T19:49:00")
    assert sampler.sample_once() is False
    current.current = datetime.fromisoformat("2026-07-22T19:50:00")
    assert sampler.sample_once() is True
    current.current = datetime.fromisoformat("2026-07-22T20:05:00")
    assert sampler.sample_once() is False
    assert calls == ["19:35", "19:50"]
```

Add the cutoff test:

```python
def test_sampler_stops_late_share_retries_at_2331() -> None:
    current = Clock("2026-07-22T23:30:00")
    sampler = EtfThreeFactorSampler(
        scan=lambda **_kwargs: share_snapshot("2026-07-22", complete=False),
        clock=current,
    )

    assert sampler.sample_once() is True
    current.current = datetime.fromisoformat("2026-07-22T23:31:00")
    assert sampler.sample_once() is False
```

- [ ] **Step 2: Run sampler tests and verify RED**

Run:

```bash
uv run pytest -q tests/test_etf_three_factor_sampler.py
```

Working directory: `apps/api`

Expected: FAIL because all times after 19:35 share one completion key and the scheduler continues to classify 23:31 as a refresh window.

- [ ] **Step 3: Implement bounded 15-minute retry buckets**

Add constants:

```python
LATE_SHARE_START_MINUTE = 19 * 60 + 35
LATE_SHARE_END_MINUTE = 23 * 60 + 31
LATE_SHARE_BUCKET_MINUTES = 15
EXPECTED_CORE_ETF_COUNT = 7
```

Change `_scan_kind` so 19:35 through 23:30 returns `share_retry`, while 23:31 and later returns `None`.

Add:

```python
def _late_share_bucket(now: datetime) -> int:
    minute = now.hour * 60 + now.minute
    return (minute - LATE_SHARE_START_MINUTE) // LATE_SHARE_BUCKET_MINUTES


def _has_complete_share_snapshot(snapshot: object, trade_date: str) -> bool:
    if getattr(snapshot, "trade_date", None) != trade_date:
        return False
    items = getattr(snapshot, "items", None)
    if not isinstance(items, list) or len(items) != EXPECTED_CORE_ETF_COUNT:
        return False
    return all(
        getattr(item, "share_change_pct", None) is not None
        and getattr(getattr(item, "share_factor", None), "status", None) == "available"
        for item in items
    )
```

Add `self._completed_share_dates: set[str] = set()` and update `sample_once`:

```python
trade_date = current.date().isoformat()
if kind in {"share_first", "share_retry"} and trade_date in self._completed_share_dates:
    return False

completion_key = (
    f"{trade_date}:share_retry:{_late_share_bucket(current)}"
    if kind == "share_retry"
    else key if kind == "intraday"
    else f"{trade_date}:{kind}"
)

result = self._scan(now=current, force=True) if kind in {"share_first", "share_retry"} else self._scan(now=current)
completed.add(completion_key)
if kind in {"share_first", "share_retry"} and _has_complete_share_snapshot(result, trade_date):
    self._completed_share_dates.add(trade_date)
```

Keep existing intraday and close completion behavior unchanged.

- [ ] **Step 4: Run sampler and monitor tests and verify GREEN**

Run:

```bash
uv run pytest -q tests/test_etf_three_factor_sampler.py tests/test_etf_three_factor_monitor.py
```

Expected: all sampler and monitor tests pass.

- [ ] **Step 5: Commit the late disclosure retry fix**

```bash
git add apps/api/app/services/etf_three_factor_sampler.py apps/api/tests/test_etf_three_factor_sampler.py
git commit -m "fix(etf-radar): retry late share disclosures"
```

### Task 4: Full Verification and Article Sample Check

**Files:**
- Verify only; no production file changes expected.

**Interfaces:**
- Consumes: the completed frontend row/table behavior and backend retry scheduler.
- Produces: a verified release candidate on the current branch.

- [ ] **Step 1: Run focused ETF Radar tests**

```bash
pnpm test:unit -- src/utils/domain/etfThreeFactor.test.ts src/views/EtfRadarView.test.ts
```

Working directory: `apps/web-vue`

Expected: all focused frontend tests pass.

- [ ] **Step 2: Run full frontend validation**

```bash
pnpm test:unit
pnpm typecheck
pnpm build
```

Working directory: `apps/web-vue`

Expected: full unit suite, typecheck, and production build pass.

- [ ] **Step 3: Run full backend validation**

```bash
uv run pytest -q
```

Working directory: `apps/api`

Expected: full backend suite passes.

- [ ] **Step 4: Verify the 2026-07-28 article-comparable values**

Use the local API test fixture or deployed JSON to confirm the table-ready values remain:

```text
510300.SH baseline_change_pct +0.7801%, baseline multiple +7.80x
510500.SH baseline_change_pct -2.5303%, baseline multiple -25.30x
159915.SZ baseline_change_pct +6.3519%, baseline multiple +63.52x
```

Confirm cumulative values such as `-71.48%` and `-39.77%` appear only in the trajectory view, not the daily activity table.

- [ ] **Step 5: Inspect the final diff and worktree**

```bash
git diff --check
git status --short
git log -6 --oneline --decorate
```

Expected: only the pre-existing `.superpowers/sdd` changes and `apps/web/` remain uncommitted; all ETF methodology changes are committed.
