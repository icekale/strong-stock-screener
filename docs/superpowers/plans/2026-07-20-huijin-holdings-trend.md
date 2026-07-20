# Huijin Holdings Trend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair Shenzhen ETF share dates and rebuild `/etf-radar` around confirmed Huijin holdings baselines and cumulative ETF-share trajectories.

**Architecture:** Keep official exchange collection, calculations, and persistence in FastAPI. Correct the SZSE date at the provider boundary, sanitize only impossible future-dated SZSE rows in the service, extend the typed activity contract with baseline quantities, and add a focused Vue trajectory component while preserving the existing daily activity, holders, and methodology views.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx, pytest, Vue 3, TypeScript, Vitest, Ant Design Vue, ECharts.

---

## File Map

- `apps/api/app/providers/capital_signals.py`: parse the actual SZSE share date from the `dqgm` column title and report actual coverage dates.
- `apps/api/tests/test_capital_signal_providers.py`: cover real metadata/date mismatches, missing dates, and ambiguous dates.
- `apps/api/app/services/capital_signals.py`: remove impossible future SZSE history rows before activity calculation.
- `apps/api/tests/test_capital_signals.py`: prove targeted history cleanup and preservation of valid rows.
- `apps/api/app/models.py`: expose baseline ETF shares and confirmed Huijin shares on each activity item.
- `apps/api/app/services/huijin_etf_activity.py`: populate the new baseline fields.
- `apps/api/tests/test_huijin_etf_activity.py`: verify the new activity contract.
- `apps/web-vue/src/service/types.ts`: mirror the two new required nullable fields.
- `apps/web-vue/src/service/api.test.ts`: enforce frontend/backend contract requiredness.
- `apps/web-vue/src/utils/domain/huijinTrajectory.ts`: own ranking, selection, trajectory dates, and data-state labels.
- `apps/web-vue/src/utils/domain/huijinTrajectory.test.ts`: test pure trajectory transformations.
- `apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.vue`: render the approved ranking, selected chart, detail strip, and compact table.
- `apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.test.ts`: verify rendering and selection behavior.
- `apps/web-vue/src/views/EtfRadarView.vue`: make holdings trajectory the default view and retain the daily/holders/methodology views.
- `apps/web-vue/src/views/EtfRadarView.test.ts`: verify request behavior, tabs, fallback states, and retained functionality.
- `apps/web-vue/src/router/product-routes.ts`: rename the product menu entry.
- `apps/web-vue/src/router/product-routes.test.ts`: verify the new title.
- `apps/web-vue/src/locales/langs/zh-cn.ts`: rename the Chinese route label.
- `apps/web-vue/src/locales/langs/en-us.ts`: rename the English route label.

### Task 1: Parse the Actual SZSE ETF Share Date

**Files:**
- Modify: `apps/api/app/providers/capital_signals.py:157-205,362-394`
- Test: `apps/api/tests/test_capital_signal_providers.py`

- [ ] **Step 1: Replace the SZSE fixture metadata with the real response shape**

Add a fixture whose page date differs from the share date:

```python
SZSE_SHARE_FIXTURE = [
    {
        "metadata": {
            "subname": "2026-07-20",
            "cols": {
                "dqgm": "当前规模<br>（万份）<span>说明</span><br>（2026-07-17）"
            },
        },
        "data": [
            {
                "sys_key": "<u>159915</u>",
                "kzjcurl": "<u>创业板ETF易方达</u>",
                "dqgm": "1,492,045.49",
            }
        ],
    }
]
```

- [ ] **Step 2: Write failing parser tests**

```python
def test_szse_share_parser_uses_scale_column_date_not_page_date() -> None:
    rows = parse_szse_etf_share_payload(
        SZSE_SHARE_FIXTURE,
        trade_date="2026-07-17",
        symbols=["159915.SZ"],
    )

    assert len(rows) == 1
    assert rows[0].trade_date == "2026-07-17"
    assert rows[0].total_shares == pytest.approx(14_920_454_900)


@pytest.mark.parametrize(
    "dqgm_title",
    [
        "当前规模（万份）",
        "当前规模（2026-07-16）（2026-07-17）",
        "当前规模（2026-02-31）",
    ],
)
def test_szse_share_parser_rejects_missing_ambiguous_or_invalid_scale_date(
    dqgm_title: str,
) -> None:
    payload = deepcopy(SZSE_SHARE_FIXTURE)
    payload[0]["metadata"]["cols"]["dqgm"] = dqgm_title

    assert parse_szse_etf_share_payload(
        payload,
        trade_date="2026-07-17",
        symbols=["159915.SZ"],
    ) == []
```

- [ ] **Step 3: Run the parser tests and verify RED**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_capital_signal_providers.py -k 'szse_share_parser' -vv
```

Expected: the mismatch fixture fails because the parser reads `metadata.subname`.

- [ ] **Step 4: Implement strict column-title date extraction**

Add `import re` and this helper:

```python
_ISO_DATE_PATTERN = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")


def _szse_share_date(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return None
    columns = metadata.get("cols")
    title = columns.get("dqgm") if isinstance(columns, dict) else None
    dates = {
        parsed
        for value in _ISO_DATE_PATTERN.findall(str(title or ""))
        if (parsed := _date_text(value)) is not None
    }
    return next(iter(dates)) if len(dates) == 1 else None
```

Change the parser boundary to:

```python
metadata = section.get("metadata") if isinstance(section, dict) else None
exchange_date = _szse_share_date(metadata)
if not exchange_date or exchange_date != _date_text(trade_date):
    return []
```

Do not fall back to `metadata.subname`.

- [ ] **Step 5: Include the actual date in source status**

After collecting `szse_rows`, derive:

```python
actual_dates = sorted({row.trade_date for row in szse_rows})
date_detail = f"；份额日期 {', '.join(actual_dates)}" if actual_dates else ""
```

Append `date_detail` to both success and partial SZSE status details.

- [ ] **Step 6: Run tests and commit**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_capital_signal_providers.py -q
.venv/bin/ruff check app/providers/capital_signals.py tests/test_capital_signal_providers.py
git add app/providers/capital_signals.py tests/test_capital_signal_providers.py
git commit -m "fix: parse actual SZSE ETF share date"
```

Expected: provider tests and Ruff pass.

### Task 2: Remove Corrupted Future-Dated SZSE History

**Files:**
- Modify: `apps/api/app/services/capital_signals.py:115-128,744-772`
- Test: `apps/api/tests/test_capital_signals.py`

- [ ] **Step 1: Write a failing targeted-cleanup test**

```python
def test_overview_discards_only_future_szse_rows_from_broken_date_parser(
    tmp_path: Path,
) -> None:
    service, store = _service(tmp_path)
    store.save_share_history([
        EtfSharePoint(
            trade_date="2026-07-16",
            symbol="510300.SH",
            name=ALL_ETFS["510300.SH"].name,
            total_shares=900,
        ),
        EtfSharePoint(
            trade_date="2026-07-20",
            symbol="159915.SZ",
            name=ALL_ETFS["159915.SZ"].name,
            total_shares=1_000,
        ),
        EtfSharePoint(
            trade_date="2026-07-20",
            symbol="600000.SH",
            name="非ETF数据",
            total_shares=1_000,
        ),
    ])

    result = service.overview(force=True)
    history = store.load_share_history()

    assert result.trade_date == "2026-07-17"
    assert not any(row.symbol == "159915.SZ" and row.trade_date == "2026-07-20" for row in history)
    assert any(row.symbol == "600000.SH" and row.trade_date == "2026-07-20" for row in history)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_capital_signals.py -k 'future_szse' -vv
```

Expected: the corrupt `159915.SZ` row remains in storage.

- [ ] **Step 3: Implement a pure sanitizer**

```python
def _discard_future_szse_rows(
    history: list[EtfSharePoint], disclosed_trade_date: str
) -> list[EtfSharePoint]:
    return [
        row
        for row in history
        if not (
            row.symbol in ALL_ETFS
            and row.symbol.endswith(".SZ")
            and row.trade_date > disclosed_trade_date
        )
    ]
```

Call it immediately after loading history:

```python
history = self.store.load_share_history()
sanitized_history = _discard_future_szse_rows(history, trade_date)
if sanitized_history != history:
    self.store.save_share_history(sanitized_history)
history = sanitized_history
```

- [ ] **Step 4: Verify service behavior and commit**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_capital_signals.py tests/test_capital_signal_store.py -q
.venv/bin/ruff check app/services/capital_signals.py tests/test_capital_signals.py
git add app/services/capital_signals.py tests/test_capital_signals.py
git commit -m "fix: clean invalid SZSE ETF history dates"
```

Expected: service/store tests pass and unrelated future rows remain.

### Task 3: Expose Confirmed and Baseline Share Quantities

**Files:**
- Modify: `apps/api/app/models.py:2088-2107`
- Modify: `apps/api/app/services/huijin_etf_activity.py:136-188`
- Test: `apps/api/tests/test_huijin_etf_activity.py`
- Modify: `apps/web-vue/src/service/types.ts`
- Test: `apps/web-vue/src/service/api.test.ts`

- [ ] **Step 1: Write failing backend contract assertions**

Extend the 2026-07-17 activity fixture test:

```python
assert result.baseline_total_shares == 31_500_000_000
assert result.confirmed_huijin_shares == 25_200_000_000
```

Add a no-baseline assertion:

```python
assert result_without_baseline.baseline_total_shares is None
assert result_without_baseline.confirmed_huijin_shares is None
```

- [ ] **Step 2: Run backend tests and verify RED**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_huijin_etf_activity.py -k '2026_07_17 or without_baseline' -vv
```

Expected: `HuijinEtfActivityItem` has no baseline quantity attributes.

- [ ] **Step 3: Add and populate the Pydantic fields**

Add to `HuijinEtfActivityItem`:

```python
baseline_total_shares: float | None = None
confirmed_huijin_shares: float | None = None
```

Populate in `calculate_activity`:

```python
baseline_total_shares=baseline.baseline_total_shares if baseline is not None else None,
confirmed_huijin_shares=baseline.confirmed_huijin_shares if baseline is not None else None,
```

- [ ] **Step 4: Add required nullable TypeScript fields and type assertions**

Add to `HuijinEtfActivityItem` in `types.ts`:

```ts
baseline_total_shares: number | null;
confirmed_huijin_shares: number | null;
```

Extend the requiredness test:

```ts
expectTypeOf<Pick<HuijinEtfActivityItem, 'baseline_total_shares' | 'confirmed_huijin_shares'>>()
  .toEqualTypeOf<{
    baseline_total_shares: number | null;
    confirmed_huijin_shares: number | null;
  }>();
```

Update all test fixtures with explicit values.

- [ ] **Step 5: Run backend/frontend contract tests and commit**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_huijin_etf_activity.py tests/test_capital_signals.py tests/test_api.py -q
cd ../web-vue
corepack pnpm@9.15.0 test:unit --run src/service/api.test.ts
corepack pnpm@9.15.0 typecheck
git add ../api/app/models.py ../api/app/services/huijin_etf_activity.py ../api/tests/test_huijin_etf_activity.py src/service/types.ts src/service/api.test.ts
git commit -m "feat: expose Huijin baseline share quantities"
```

Expected: contracts and typecheck pass.

### Task 4: Add Pure Huijin Trajectory Transformations

**Files:**
- Create: `apps/web-vue/src/utils/domain/huijinTrajectory.ts`
- Create: `apps/web-vue/src/utils/domain/huijinTrajectory.test.ts`

- [ ] **Step 1: Write failing transformation tests**

```ts
import { describe, expect, it } from 'vitest';
import {
  buildHuijinRanking,
  buildHuijinTrajectory,
  huijinActivityDataState,
  pickDefaultHuijinSymbol
} from './huijinTrajectory';

describe('Huijin trajectory transforms', () => {
  it('sorts available core ETFs by absolute cumulative deviation', () => {
    expect(buildHuijinRanking([
      item('510300.SH', -75.55),
      item('159915.SZ', -52.63),
      item('510050.SH', -85.46),
    ]).map(row => row.symbol)).toEqual(['510050.SH', '510300.SH', '159915.SZ']);
  });

  it('starts a trajectory at the report baseline and preserves real gaps', () => {
    expect(buildHuijinTrajectory(
      item('510050.SH', -85.46, '2025-12-31'),
      [point('2026-07-16', -84), point('2026-07-18', -85.46)],
      ['2026-07-16', '2026-07-17', '2026-07-18'],
    )).toEqual({
      dates: ['2025-12-31', '2026-07-16', '2026-07-17', '2026-07-18'],
      values: [0, -84, null, -85.46],
    });
  });

  it('distinguishes disclosure, daily-history, and baseline gaps', () => {
    expect(huijinActivityDataState(itemWith({ total_shares: null }))).toBe('交易所尚未披露');
    expect(huijinActivityDataState(itemWith({ previous_total_shares: null }))).toBe('日度历史积累中');
    expect(huijinActivityDataState(itemWith({ report_period: null }))).toBe('确认基线缺失');
  });
});
```

Use these local fixture builders:

```ts
const baseItem: HuijinEtfActivityItem = {
  symbol: '510050.SH',
  name: '上证50ETF华夏',
  index_name: '上证50',
  role: 'core',
  paired_symbol: null,
  trade_date: '2026-07-18',
  total_shares: 8_237_466_800,
  previous_total_shares: 8_150_166_800,
  share_delta: 87_300_000,
  daily_change_pct: 1.07,
  baseline_change_pct: 0.15,
  cumulative_baseline_change_pct: -85.46,
  multiple: 1.5,
  direction: 'increase',
  is_tenfold: false,
  report_period: '2025-12-31',
  baseline_total_shares: 56_663_567_693,
  confirmed_huijin_shares: 48_759_000_000,
  confirmed_huijin_holding_pct: 86.05,
  baseline_source_kind: 'derived'
};

function itemWith(overrides: Partial<HuijinEtfActivityItem> = {}) {
  return { ...baseItem, ...overrides };
}

function item(symbol: string, cumulative: number | null, reportPeriod = '2025-12-31') {
  return itemWith({ symbol, cumulative_baseline_change_pct: cumulative, report_period: reportPeriod });
}

function point(tradeDate: string, cumulative: number | null): EtfRadarHistoryPoint {
  return {
    trade_date: tradeDate,
    symbol: '510050.SH',
    name: '上证50ETF华夏',
    total_shares: 8_237_466_800,
    share_change: null,
    estimated_subscription_cny: null,
    robust_score: null,
    daily_change_pct: null,
    baseline_change_pct: null,
    cumulative_baseline_change_pct: cumulative,
    multiple: null
  };
}
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
cd apps/web-vue
corepack pnpm@9.15.0 test:unit --run src/utils/domain/huijinTrajectory.test.ts
```

Expected: module resolution fails because `huijinTrajectory.ts` does not exist.

- [ ] **Step 3: Implement the pure functions**

```ts
export function buildHuijinRanking(items: HuijinEtfActivityItem[]) {
  return [...items]
    .filter(item => item.cumulative_baseline_change_pct !== null)
    .sort((left, right) =>
      Math.abs(right.cumulative_baseline_change_pct!) - Math.abs(left.cumulative_baseline_change_pct!)
    );
}

export function pickDefaultHuijinSymbol(items: HuijinEtfActivityItem[]) {
  return buildHuijinRanking(items)[0]?.symbol ?? items[0]?.symbol ?? '';
}

export function buildHuijinTrajectory(
  item: HuijinEtfActivityItem,
  points: EtfRadarHistoryPoint[],
  realDates: string[]
) {
  const values = new Map(
    points.filter(point => point.symbol === item.symbol)
      .map(point => [point.trade_date, point.cumulative_baseline_change_pct])
  );
  const dates = [item.report_period, ...realDates.filter(date => date !== item.report_period)]
    .filter((date): date is string => Boolean(date));
  return {
    dates,
    values: dates.map(date => date === item.report_period ? 0 : values.get(date) ?? null)
  };
}

export function huijinActivityDataState(item: HuijinEtfActivityItem) {
  if (item.total_shares === null) return '交易所尚未披露';
  if (item.report_period === null || item.baseline_total_shares === null) return '确认基线缺失';
  if (item.previous_total_shares === null) return '日度历史积累中';
  return '可计算';
}
```

- [ ] **Step 4: Run tests, typecheck, and commit**

Run:

```bash
cd apps/web-vue
corepack pnpm@9.15.0 test:unit --run src/utils/domain/huijinTrajectory.test.ts
corepack pnpm@9.15.0 typecheck
git add src/utils/domain/huijinTrajectory.ts src/utils/domain/huijinTrajectory.test.ts
git commit -m "feat: add Huijin trajectory transforms"
```

Expected: unit tests and typecheck pass.

### Task 5: Build the Approved Trajectory Panel

**Files:**
- Create: `apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.vue`
- Create: `apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.test.ts`

- [ ] **Step 1: Write failing component tests**

Mount with seven real-shaped core rows and history points. Assert:

```ts
expect(wrapper.findAll('[data-testid="huijin-ranking-row"]')).toHaveLength(7);
expect(wrapper.get('[data-testid="huijin-baseline-date"]').text()).toContain('2025-12-31');
expect(wrapper.get('[data-testid="huijin-selected-symbol"]').text()).toContain('510050.SH');
expect(wrapper.text()).toContain('累计份额变化不能直接证明汇金增减持');

await wrapper.findAll('[data-testid="huijin-ranking-row"]')[1]!.trigger('click');
expect(wrapper.emitted('select')?.at(-1)).toEqual(['510300.SH']);

const option = wrapper.getComponent(ChartStub).props('option') as EChartsOption;
expect(option.animation).toBe(false);
expect(option.series[0].connectNulls).toBe(false);
expect(option.series[0].data).toEqual([0, -74, null, -75.55]);
```

Also assert the visible labels `汇金确认持有份额`, `报告期 ETF 总份额`, `最新 ETF 总份额`, `累计偏离`, and `日度历史积累中`.

- [ ] **Step 2: Run the component test and verify RED**

Run:

```bash
cd apps/web-vue
corepack pnpm@9.15.0 test:unit --run src/components/etf-radar/HuijinTrajectoryPanel.test.ts
```

Expected: component resolution fails.

- [ ] **Step 3: Implement the component contract**

Use this prop/event boundary:

```ts
const props = defineProps<{
  overview: EtfRadarOverviewResponse;
  history: EtfRadarHistoryResponse | null;
  selectedSymbol: string;
  historyLoading: boolean;
  historyError: string | null;
}>();

const emit = defineEmits<{
  select: [symbol: string];
}>();
```

Use these computed boundaries and chart settings:

```ts
const ranking = computed(() => buildHuijinRanking(props.overview.core_items));
const selectedItem = computed(() =>
  props.overview.core_items.find(item => item.symbol === props.selectedSymbol)
  ?? ranking.value[0]
  ?? null
);
const realDates = computed(() =>
  [...new Set((props.history?.points ?? []).map(point => point.trade_date))].sort()
);
const trajectory = computed(() => selectedItem.value
  ? buildHuijinTrajectory(selectedItem.value, props.history?.points ?? [], realDates.value)
  : { dates: [], values: [] }
);
const chartOption = computed<EChartsOption>(() => ({
  animation: false,
  aria: { enabled: true, description: `${selectedItem.value?.name ?? 'ETF'}相对报告基线的累计份额轨迹` },
  grid: { left: 58, right: 18, top: 20, bottom: 34 },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', boundaryGap: false, data: trajectory.value.dates },
  yAxis: { type: 'value', axisLabel: { formatter: (value: number) => `${value.toFixed(0)}%` } },
  series: [{
    name: selectedItem.value?.name ?? '累计偏离',
    type: 'line',
    connectNulls: false,
    showSymbol: true,
    data: trajectory.value.values
  }]
}));
```

Use this semantic template structure so tests and accessibility remain stable:

```vue
<section data-testid="huijin-trajectory-panel" class="huijin-trajectory">
  <div class="huijin-trajectory__metrics" aria-label="汇金持仓轨迹摘要">
    <div data-testid="huijin-baseline-date">{{ baselineDate }}</div>
    <div>{{ overview.trade_date }}</div>
    <div>{{ availableCount }} / {{ overview.activity.core_count }}</div>
    <div>{{ contractionCount }} 只收缩</div>
  </div>
  <div class="huijin-trajectory__sources">
    <span v-for="source in overview.source_status" :key="`${source.source}-${source.detail}`">
      {{ source.source }} · {{ source.status }} · {{ source.detail }}
    </span>
  </div>
  <div class="huijin-trajectory__main">
    <div class="huijin-ranking" role="list" aria-label="核心 ETF 累计偏离排行">
      <button
        v-for="item in ranking"
        :key="item.symbol"
        data-testid="huijin-ranking-row"
        type="button"
        @click="emit('select', item.symbol)"
      >
        <span>{{ item.name }}</span><span>{{ formatDirectionalPercent(item.cumulative_baseline_change_pct) }}</span>
      </button>
    </div>
    <div class="huijin-selected">
      <strong data-testid="huijin-selected-symbol">{{ selectedItem?.symbol }}</strong>
      <EChart v-if="history && trajectory.values.some(value => value !== null)" :option="chartOption" :height="286" />
      <div v-else class="huijin-trajectory__empty">{{ historyError || '历史积累中' }}</div>
    </div>
  </div>
  <dl class="huijin-trajectory__details">
    <div><dt>汇金确认持有份额</dt><dd>{{ formatPlainShares(selectedItem?.confirmed_huijin_shares) }}</dd></div>
    <div><dt>报告期 ETF 总份额</dt><dd>{{ formatPlainShares(selectedItem?.baseline_total_shares) }}</dd></div>
    <div><dt>最新 ETF 总份额</dt><dd>{{ formatPlainShares(selectedItem?.total_shares) }}</dd></div>
    <div><dt>汇金确认持仓比例</dt><dd>{{ formatHoldingPct(selectedItem?.confirmed_huijin_holding_pct) }}</dd></div>
    <div><dt>累计偏离</dt><dd>{{ formatDirectionalPercent(selectedItem?.cumulative_baseline_change_pct) }}</dd></div>
    <div><dt>最近日变化</dt><dd>{{ formatDirectionalPercent(selectedItem?.daily_change_pct) }}</dd></div>
  </dl>
  <p class="huijin-trajectory__note">累计份额变化不能直接证明汇金增减持，需由下一期基金报告确认。</p>
  <div class="huijin-trajectory__table" role="table" aria-label="汇金核心 ETF 持仓轨迹明细">
    <button v-for="item in overview.core_items" :key="item.symbol" type="button" @click="emit('select', item.symbol)">
      <span>{{ item.name }}</span>
      <span>{{ formatHoldingPct(item.confirmed_huijin_holding_pct) }}</span>
      <span>{{ formatDirectionalPercent(item.cumulative_baseline_change_pct) }}</span>
      <span>{{ huijinActivityDataState(item) }}</span>
    </button>
  </div>
</section>
```

Style desktop as `grid-template-columns: minmax(0, 1.15fr) minmax(320px, .85fr)` and switch to one column below `900px`. Use existing `--wb-*` tokens only. Do not use nested cards, hard-coded hex colors, custom SVG icons, or document-level horizontal overflow.

Do not use nested cards, hard-coded hex colors, custom SVG icons, or document-level horizontal overflow.

- [ ] **Step 4: Verify component behavior and commit**

Run:

```bash
cd apps/web-vue
corepack pnpm@9.15.0 test:unit --run src/components/etf-radar/HuijinTrajectoryPanel.test.ts src/utils/domain/huijinTrajectory.test.ts
corepack pnpm@9.15.0 typecheck
git add src/components/etf-radar/HuijinTrajectoryPanel.vue src/components/etf-radar/HuijinTrajectoryPanel.test.ts
git commit -m "feat: add Huijin holdings trajectory panel"
```

Expected: component/domain tests and typecheck pass.

### Task 6: Integrate the Holdings-First Workspace

**Files:**
- Modify: `apps/web-vue/src/views/EtfRadarView.vue`
- Test: `apps/web-vue/src/views/EtfRadarView.test.ts`
- Modify: `apps/web-vue/src/router/product-routes.ts`
- Test: `apps/web-vue/src/router/product-routes.test.ts`
- Modify: `apps/web-vue/src/locales/langs/zh-cn.ts`
- Modify: `apps/web-vue/src/locales/langs/en-us.ts`
- Modify: `apps/web-vue/src/utils/domain/capitalSignals.ts`
- Test: `apps/web-vue/src/utils/domain/capitalSignals.test.ts`

- [ ] **Step 1: Rewrite failing page expectations**

Change the initial view assertions to:

```ts
expect(wrapper.findAll('.etf-tab-trigger').map(tab => tab.text())).toEqual([
  '持仓轨迹', '日度活动', '确认持仓', '方法与数据'
]);
expect(wrapper.text()).toContain('汇金持仓追踪');
expect(wrapper.find('[data-testid="huijin-trajectory-panel"]').exists()).toBe(true);
expect(api.getEtfRadarOverview).toHaveBeenCalledTimes(1);
expect(api.getEtfRadarHistory).toHaveBeenCalledTimes(1);
expect(api.getEtfRadarHolders).not.toHaveBeenCalled();
expect(api.getEtfRadarMethodology).not.toHaveBeenCalled();
```

Move the existing overview assertions behind `await openTab(wrapper, 1)` and change data-state text to `交易所尚未披露`, `日度历史积累中`, `确认基线缺失`, and `可计算`.

Add an assertion that daily validation labels use `配对一致增加` / `配对一致减少`, never `确认增加` / `确认减少`.

- [ ] **Step 2: Run page/router tests and verify RED**

Run:

```bash
cd apps/web-vue
corepack pnpm@9.15.0 test:unit --run src/views/EtfRadarView.test.ts src/router/product-routes.test.ts src/utils/domain/capitalSignals.test.ts
```

Expected: old title, old tabs, old initial request behavior, and old labels fail.

- [ ] **Step 3: Integrate the trajectory panel and shared overview/history loading**

Use:

```ts
type EtfTab = 'trajectory' | 'activity' | 'holders' | 'methodology';
const activeTab = ref<EtfTab>('trajectory');
const selectedTrajectorySymbol = ref('');
```

On mount, load overview and history concurrently:

```ts
async function loadTrajectory(force = false) {
  loading.trajectory = true;
  await Promise.allSettled([loadOverview(force), loadHistory(force)]);
  if (!selectedTrajectorySymbol.value && overview.value) {
    selectedTrajectorySymbol.value = pickDefaultHuijinSymbol(overview.value.core_items);
  }
  loading.trajectory = false;
}
```

The `activity` tab reuses the loaded overview and sends no second request. Holders and methodology remain lazy. Manual refresh on trajectory refreshes overview/history together while retaining prior successful values on partial failure.

Render `HuijinTrajectoryPanel` only in the trajectory tab and move the existing overview markup unchanged into the activity tab, except for approved terminology and data-state labels.

- [ ] **Step 4: Rename route/menu text and validation labels**

Set:

```ts
meta: { title: '汇金持仓追踪', icon: 'ant-design:radar-chart-outlined', order: 5, constant: true }
```

Locale labels:

```ts
'etf-radar': '汇金持仓追踪'
'etf-radar': 'Huijin Holdings Tracker'
```

Update `validationStateLabel`:

```ts
if (state === 'confirmed_increase') return '配对一致增加';
if (state === 'confirmed_decrease') return '配对一致减少';
```

- [ ] **Step 5: Run focused tests, typecheck, build, and commit**

Run:

```bash
cd apps/web-vue
corepack pnpm@9.15.0 test:unit --run src/views/EtfRadarView.test.ts src/components/etf-radar/HuijinTrajectoryPanel.test.ts src/utils/domain/huijinTrajectory.test.ts src/utils/domain/capitalSignals.test.ts src/router/product-routes.test.ts
corepack pnpm@9.15.0 typecheck
corepack pnpm@9.15.0 build
git add src/views/EtfRadarView.vue src/views/EtfRadarView.test.ts src/router/product-routes.ts src/router/product-routes.test.ts src/locales/langs/zh-cn.ts src/locales/langs/en-us.ts src/utils/domain/capitalSignals.ts src/utils/domain/capitalSignals.test.ts
git commit -m "feat: make Huijin trajectory the default ETF workspace"
```

Expected: focused tests, typecheck, and production build pass.

### Task 7: Full Verification and Real-Data QA

**Files:**
- Modify only files listed above when verification exposes a defect.

- [ ] **Step 1: Run the complete backend ETF suite**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py tests/test_capital_signal_providers.py tests/test_capital_signals.py tests/test_capital_signal_sampler.py tests/test_api.py -q
.venv/bin/ruff check app/models.py app/providers/capital_signals.py app/services/huijin_etf_activity.py app/services/capital_signal_store.py app/services/capital_signals.py app/services/capital_signal_sampler.py app/main.py tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py tests/test_capital_signal_providers.py tests/test_capital_signals.py tests/test_capital_signal_sampler.py tests/test_api.py
```

Expected: all selected backend tests and Ruff pass.

- [ ] **Step 2: Run complete Vue checks**

Run:

```bash
cd apps/web-vue
corepack pnpm@9.15.0 test:unit --run
corepack pnpm@9.15.0 typecheck
corepack pnpm@9.15.0 build
```

Expected: all Vue tests, typecheck, and production build pass.

- [ ] **Step 3: Start isolated API and Vue services**

Run API:

```bash
cd apps/api
STRONG_STOCK_DATA_DIR=/tmp/huijin-holdings-trend-data \
STRONG_STOCK_CORS_ALLOW_ORIGINS=http://127.0.0.1:3112 \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8012
```

Run Vue:

```bash
cd apps/web-vue
VITE_API_BASE_URL=http://127.0.0.1:8012 \
corepack pnpm@9.15.0 dev --host 127.0.0.1 --port 3112
```

- [ ] **Step 4: Verify real API data**

Check:

```bash
curl -fsS http://127.0.0.1:8012/api/etf-radar/overview | jq '{
  trade_date,
  core: [.core_items[] | {
    symbol,
    total_shares,
    baseline_total_shares,
    confirmed_huijin_shares,
    cumulative_baseline_change_pct
  }],
  sources: .source_status
}'
```

Expected:

- `159915.SZ` uses the date in `metadata.cols.dqgm`;
- seven core rows have cumulative values when current shares and baselines exist;
- no invalid future SZSE point remains;
- daily values stay null when only one true archive exists.

- [ ] **Step 5: Perform browser QA**

Verify `/etf-radar` at desktop `1440x900`, compact desktop `1024x768`, and mobile `390x844`:

- trajectory is the default tab;
- seven ranking rows render and select correctly;
- chart is nonblank and uses real dates with gaps;
- detail quantities and fixed methodology note are visible;
- activity, holders, and methodology tabs still work;
- no console errors or document horizontal overflow;
- other tabs remain lazy and no request repeats on ETF selection.

- [ ] **Step 6: Review and commit verification-only fixes**

Run:

```bash
git diff --check
git status --short
```

If QA exposes a defect, stage only files in this plan and commit:

```bash
git commit -m "fix: harden Huijin holdings trajectory states"
```

Do not create an empty commit.
