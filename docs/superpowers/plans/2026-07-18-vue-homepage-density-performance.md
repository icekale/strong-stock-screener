# Vue 首页信息密度与性能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构生产 Vue 首页，移除竞价 Top3，以独立加载、15 秒内存缓存和异步图表缩短首屏等待，并用板块实时曲线替换盘中情绪图。

**Architecture:** 新增一个无框架依赖的请求缓存和一个 Vue 首页数据编排 composable；四项首页资源独立维护状态并共享短时缓存。`HomeView.vue` 只负责派生展示数据、图表选项和紧凑响应式布局，实时曲线直接复用板块页面现有接口与图表构建器。

**Tech Stack:** Vue 3.5, TypeScript 5.9, Vite 7, Vitest 3, Ant Design Vue 4, ECharts 6, UnoCSS.

---

## 文件结构

| Path | Responsibility |
| --- | --- |
| `apps/web-vue/src/utils/requestCache.ts` | TTL 成功值缓存、同键 Promise 去重和手动刷新绕过。 |
| `apps/web-vue/src/utils/requestCache.test.ts` | 缓存命中、过期、并发、强制刷新与失败回退测试。 |
| `apps/web-vue/src/composables/useHomeDashboard.ts` | 首页四项资源的独立状态、缓存键、并行加载和板块模式切换。 |
| `apps/web-vue/src/composables/useHomeDashboard.test.ts` | 独立提交、失败隔离、缓存返回和模式切换测试。 |
| `apps/web-vue/src/service/api.test.ts` | 板块曲线最小载荷参数的 URL 契约测试。 |
| `apps/web-vue/src/views/HomeView.vue` | 首页视觉结构、派生指标、动态图表和面板错误状态。 |
| `apps/web-vue/src/views/HomeView.test.ts` | Top3 移除、关键模块渲染和图表延迟挂载测试。 |

### Task 1: 建立短时请求缓存

**Files:**
- Create: `apps/web-vue/src/utils/requestCache.ts`
- Create: `apps/web-vue/src/utils/requestCache.test.ts`

- [ ] **Step 1: 写缓存行为的失败测试**

创建 `apps/web-vue/src/utils/requestCache.test.ts`：

```ts
import { describe, expect, it, vi } from 'vitest';
import { createMemoryRequestCache } from './requestCache';

describe('createMemoryRequestCache', () => {
  it('returns a fresh cached value without repeating the request', async () => {
    const request = vi.fn().mockResolvedValue('market');
    const cache = createMemoryRequestCache({ now: () => 1000, ttlMs: 15_000 });

    await expect(cache.get('overview', request)).resolves.toBe('market');
    await expect(cache.get('overview', request)).resolves.toBe('market');
    expect(request).toHaveBeenCalledTimes(1);
  });

  it('reloads an expired value', async () => {
    let now = 1000;
    const request = vi.fn().mockResolvedValueOnce('old').mockResolvedValueOnce('new');
    const cache = createMemoryRequestCache({ now: () => now, ttlMs: 15_000 });

    await expect(cache.get('overview', request)).resolves.toBe('old');
    now = 16_001;
    await expect(cache.get('overview', request)).resolves.toBe('new');
  });

  it('deduplicates concurrent requests for the same key', async () => {
    let resolveRequest!: (value: string) => void;
    const pending = new Promise<string>(resolve => { resolveRequest = resolve; });
    const request = vi.fn(() => pending);
    const cache = createMemoryRequestCache({ now: () => 1000, ttlMs: 15_000 });

    const first = cache.get('sector', request);
    const second = cache.get('sector', request);
    expect(first).toBe(second);
    expect(request).toHaveBeenCalledTimes(1);

    resolveRequest('ready');
    await expect(first).resolves.toBe('ready');
  });

  it('bypasses a completed value on force refresh but preserves it after failure', async () => {
    const request = vi.fn().mockResolvedValueOnce('stable').mockRejectedValueOnce(new Error('down'));
    const cache = createMemoryRequestCache({ now: () => 1000, ttlMs: 15_000 });

    await expect(cache.get('ranking', request)).resolves.toBe('stable');
    await expect(cache.get('ranking', request, { force: true })).rejects.toThrow('down');
    await expect(cache.get('ranking', request)).resolves.toBe('stable');
    expect(request).toHaveBeenCalledTimes(2);
  });

  it('reuses an in-flight request even when force is requested', async () => {
    let resolveRequest!: (value: string) => void;
    const pending = new Promise<string>(resolve => { resolveRequest = resolve; });
    const request = vi.fn(() => pending);
    const cache = createMemoryRequestCache({ now: () => 1000, ttlMs: 15_000 });

    const first = cache.get('trend', request);
    const forced = cache.get('trend', request, { force: true });
    expect(forced).toBe(first);

    resolveRequest('trend');
    await expect(forced).resolves.toBe('trend');
    expect(request).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: 运行测试确认 RED**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
pnpm vitest run src/utils/requestCache.test.ts
```

Expected: FAIL，提示无法解析 `./requestCache`。

- [ ] **Step 3: 实现最小缓存协调器**

创建 `apps/web-vue/src/utils/requestCache.ts`：

```ts
type CacheEntry<T> = {
  expiresAt: number;
  hasValue: boolean;
  promise?: Promise<T>;
  value?: T;
};

type CacheGetOptions = {
  force?: boolean;
};

type MemoryRequestCacheOptions = {
  now?: () => number;
  ttlMs: number;
};

export function createMemoryRequestCache(options: MemoryRequestCacheOptions) {
  const now = options.now ?? Date.now;
  const entries = new Map<string, CacheEntry<unknown>>();

  function get<T>(key: string, request: () => Promise<T>, getOptions: CacheGetOptions = {}): Promise<T> {
    const current = entries.get(key) as CacheEntry<T> | undefined;
    if (current?.promise) return current.promise;
    if (!getOptions.force && current?.hasValue && current.expiresAt > now()) {
      return Promise.resolve(current.value as T);
    }

    const previous = current?.hasValue
      ? { expiresAt: current.expiresAt, hasValue: true, value: current.value }
      : { expiresAt: 0, hasValue: false };
    const promise = request();
    const pending: CacheEntry<T> = { ...previous, promise };
    entries.set(key, pending as CacheEntry<unknown>);

    void promise.then(
      value => {
        if ((entries.get(key) as CacheEntry<T> | undefined)?.promise !== promise) return;
        entries.set(key, { expiresAt: now() + options.ttlMs, hasValue: true, value });
      },
      () => {
        if ((entries.get(key) as CacheEntry<T> | undefined)?.promise !== promise) return;
        if (previous.hasValue) entries.set(key, previous as CacheEntry<unknown>);
        else entries.delete(key);
      }
    );

    return promise;
  }

  return {
    clear: () => entries.clear(),
    get
  };
}
```

- [ ] **Step 4: 运行缓存测试确认 GREEN**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
pnpm vitest run src/utils/requestCache.test.ts
```

Expected: 5 tests passed。

- [ ] **Step 5: 提交缓存单元**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/web-vue/src/utils/requestCache.ts apps/web-vue/src/utils/requestCache.test.ts
git commit -m "feat: add vue homepage request cache"
```

### Task 2: 编排四项独立首页资源

**Files:**
- Create: `apps/web-vue/src/composables/useHomeDashboard.ts`
- Create: `apps/web-vue/src/composables/useHomeDashboard.test.ts`
- Modify: `apps/web-vue/src/service/api.test.ts`

- [ ] **Step 1: 写首页数据编排的失败测试**

创建 `apps/web-vue/src/composables/useHomeDashboard.test.ts`，用最小结构值避免依赖完整行情 fixture：

```ts
import { describe, expect, it, vi } from 'vitest';
import { createMemoryRequestCache } from '@/utils/requestCache';
import type {
  MarketOverviewResponse,
  MarketRankingsResponse,
  SectorRadarResponse,
  SectorReplicaRadarResponse
} from '@/service/types';
import { useHomeDashboard } from './useHomeDashboard';

function createDependencies() {
  return {
    getMarketOverview: vi.fn().mockResolvedValue({ trade_date: '2026-07-18', source_status: [] } as unknown as MarketOverviewResponse),
    getMarketRankings: vi.fn().mockResolvedValue({ pct_change_rank: [] } as unknown as MarketRankingsResponse),
    getSectorRadar: vi.fn().mockResolvedValue({ inflow: [], source_status: [] } as unknown as SectorRadarResponse),
    getSectorReplicaRadar: vi.fn().mockResolvedValue({ axis: [], series: [], source_status: [] } as unknown as SectorReplicaRadarResponse)
  };
}

describe('useHomeDashboard', () => {
  it('starts all four resources and commits each result independently', async () => {
    const dependencies = createDependencies();
    const dashboard = useHomeDashboard({
      cache: createMemoryRequestCache({ ttlMs: 15_000 }),
      dependencies
    });

    await dashboard.loadInitial();

    expect(dependencies.getMarketOverview).toHaveBeenCalledTimes(1);
    expect(dependencies.getMarketRankings).toHaveBeenCalledWith(12);
    expect(dependencies.getSectorRadar).toHaveBeenCalledWith(12);
    expect(dependencies.getSectorReplicaRadar).toHaveBeenCalledWith({ mode: 'strength', limit: 5, stockLimit: 1 });
    expect(dashboard.overview.data.value?.trade_date).toBe('2026-07-18');
  });

  it('isolates a secondary failure from successful overview data', async () => {
    const dependencies = createDependencies();
    dependencies.getSectorRadar.mockRejectedValue(new Error('sector down'));
    const dashboard = useHomeDashboard({
      cache: createMemoryRequestCache({ ttlMs: 15_000 }),
      dependencies
    });

    await dashboard.loadInitial();

    expect(dashboard.overview.data.value?.trade_date).toBe('2026-07-18');
    expect(dashboard.sectorFlow.error.value?.message).toBe('sector down');
    expect(dashboard.rankings.error.value).toBeUndefined();
  });

  it('refreshes only the trend resource when its mode changes', async () => {
    const dependencies = createDependencies();
    const dashboard = useHomeDashboard({
      cache: createMemoryRequestCache({ ttlMs: 15_000 }),
      dependencies
    });
    await dashboard.loadInitial();

    await dashboard.setSectorMode('main_flow');

    expect(dependencies.getSectorReplicaRadar).toHaveBeenLastCalledWith({ mode: 'main_flow', limit: 5, stockLimit: 1 });
    expect(dependencies.getMarketOverview).toHaveBeenCalledTimes(1);
    expect(dependencies.getSectorRadar).toHaveBeenCalledTimes(1);
  });

  it('uses cached values on remount and force refreshes all resources', async () => {
    const dependencies = createDependencies();
    const cache = createMemoryRequestCache({ ttlMs: 15_000 });
    await useHomeDashboard({ cache, dependencies }).loadInitial();
    await useHomeDashboard({ cache, dependencies }).loadInitial();
    expect(dependencies.getMarketOverview).toHaveBeenCalledTimes(1);

    const dashboard = useHomeDashboard({ cache, dependencies });
    await dashboard.refreshAll();
    expect(dependencies.getMarketOverview).toHaveBeenCalledTimes(2);
    expect(dependencies.getSectorReplicaRadar).toHaveBeenCalledTimes(2);
  });
});
```

- [ ] **Step 2: 增加最小板块载荷 URL 的失败测试**

在 `apps/web-vue/src/service/api.test.ts` 的 import 中加入 `getSectorReplicaRadar`，并增加：

```ts
it('requests a compact sector trend payload for the homepage', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ axis: [], series: [] }), { status: 200 })
  );

  await getSectorReplicaRadar({ mode: 'strength', limit: 5, stockLimit: 1 });

  expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
    '/api/sectors/replica/radar?mode=strength&limit=5&stock_limit=1'
  );
});
```

- [ ] **Step 3: 运行测试确认 RED**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
pnpm vitest run src/composables/useHomeDashboard.test.ts src/service/api.test.ts
```

Expected: composable 测试因文件不存在失败；API URL 测试通过或暴露查询参数回归。

- [ ] **Step 4: 实现资源 composable**

创建 `apps/web-vue/src/composables/useHomeDashboard.ts`。每个资源使用 `shallowRef`，避免对图表响应做无意义深层代理：

```ts
import { computed, ref, shallowRef } from 'vue';
import type { Ref, ShallowRef } from 'vue';
import {
  getMarketOverview,
  getMarketRankings,
  getSectorRadar,
  getSectorReplicaRadar
} from '@/service/product-api';
import type {
  MarketOverviewResponse,
  MarketRankingsResponse,
  SectorRadarResponse,
  SectorReplicaMode,
  SectorReplicaRadarResponse
} from '@/service/types';
import { createMemoryRequestCache } from '@/utils/requestCache';

type Cache = ReturnType<typeof createMemoryRequestCache>;
type RefreshOptions = { force?: boolean };

export type HomeDashboardDependencies = {
  getMarketOverview: typeof getMarketOverview;
  getMarketRankings: typeof getMarketRankings;
  getSectorRadar: typeof getSectorRadar;
  getSectorReplicaRadar: typeof getSectorReplicaRadar;
};

export type HomeResource<T> = {
  data: ShallowRef<T | undefined>;
  error: ShallowRef<Error | undefined>;
  isStale: Ref<boolean>;
  loading: Ref<boolean>;
  refresh: (options?: RefreshOptions) => Promise<T>;
  refreshing: Ref<boolean>;
};

const sharedCache = createMemoryRequestCache({ ttlMs: 15_000 });
const defaultDependencies: HomeDashboardDependencies = {
  getMarketOverview,
  getMarketRankings,
  getSectorRadar,
  getSectorReplicaRadar
};

function createResource<T>(cache: Cache, key: () => string, loader: () => Promise<T>): HomeResource<T> {
  const data = shallowRef<T>();
  const error = shallowRef<Error>();
  const isStale = ref(false);
  const loading = ref(false);
  const refreshing = ref(false);

  async function refresh(options: RefreshOptions = {}) {
    const hasData = data.value !== undefined;
    loading.value = !hasData;
    refreshing.value = hasData;
    error.value = undefined;
    try {
      const value = await cache.get(key(), loader, options);
      data.value = value;
      isStale.value = false;
      return value;
    } catch (cause) {
      const nextError = cause instanceof Error ? cause : new Error(String(cause));
      error.value = nextError;
      isStale.value = hasData;
      throw nextError;
    } finally {
      loading.value = false;
      refreshing.value = false;
    }
  }

  return { data, error, isStale, loading, refresh, refreshing };
}

export function useHomeDashboard(options: {
  cache?: Cache;
  dependencies?: HomeDashboardDependencies;
} = {}) {
  const cache = options.cache ?? sharedCache;
  const dependencies = options.dependencies ?? defaultDependencies;
  const sectorMode = ref<SectorReplicaMode>('strength');
  const overview = createResource<MarketOverviewResponse>(cache, () => 'home:overview', () => dependencies.getMarketOverview());
  const rankings = createResource<MarketRankingsResponse>(cache, () => 'home:rankings:12', () => dependencies.getMarketRankings(12));
  const sectorFlow = createResource<SectorRadarResponse>(cache, () => 'home:sector-flow:12', () => dependencies.getSectorRadar(12));
  const sectorTrend = createResource<SectorReplicaRadarResponse>(
    cache,
    () => `home:sector-trend:${sectorMode.value}:5:1`,
    () => dependencies.getSectorReplicaRadar({ mode: sectorMode.value, limit: 5, stockLimit: 1 })
  );
  const resources = [overview, rankings, sectorFlow, sectorTrend] as const;
  const busy = computed(() => resources.some(item => item.loading.value || item.refreshing.value));

  function settle<T>(resource: HomeResource<T>, force = false) {
    return resource.refresh({ force }).catch(() => undefined);
  }

  async function loadInitial() {
    return Promise.all([settle(overview), settle(rankings), settle(sectorFlow), settle(sectorTrend)]);
  }

  async function refreshAll() {
    return Promise.all([settle(overview, true), settle(rankings, true), settle(sectorFlow, true), settle(sectorTrend, true)]);
  }

  async function setSectorMode(mode: SectorReplicaMode) {
    if (sectorMode.value === mode) return;
    sectorMode.value = mode;
    await settle(sectorTrend);
  }

  return { busy, loadInitial, overview, rankings, refreshAll, sectorFlow, sectorMode, sectorTrend, setSectorMode };
}
```

- [ ] **Step 5: 运行定向测试确认 GREEN**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
pnpm vitest run src/utils/requestCache.test.ts src/composables/useHomeDashboard.test.ts src/service/api.test.ts
```

Expected: 所有定向测试通过。

- [ ] **Step 6: 提交数据编排单元**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/web-vue/src/composables/useHomeDashboard.ts apps/web-vue/src/composables/useHomeDashboard.test.ts apps/web-vue/src/service/api.test.ts
git commit -m "feat: orchestrate vue homepage data"
```

### Task 3: 重构首页布局并移除 Top3

**Files:**
- Modify: `apps/web-vue/src/views/HomeView.vue`
- Create: `apps/web-vue/src/views/HomeView.test.ts`

- [ ] **Step 1: 写首页组件的失败测试**

创建 `apps/web-vue/src/views/HomeView.test.ts`。测试直接检查源码边界，并挂载组件检查用户可见模块，避免自动导入组件让测试依赖应用启动器：

```ts
// @vitest-environment jsdom

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { flushPromises, shallowMount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import HomeView from './HomeView.vue';

const api = vi.hoisted(() => ({
  getMarketOverview: vi.fn(),
  getMarketRankings: vi.fn(),
  getSectorRadar: vi.fn(),
  getSectorReplicaRadar: vi.fn()
}));

vi.mock('@/service/product-api', () => api);

describe('HomeView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    api.getMarketOverview.mockResolvedValue({
      trade_date: '2026-07-18', generated_at: '2026-07-18T09:46:00+08:00',
      indices: [], source_status: [], turnover: {}, advance_decline: {}
    });
    api.getMarketRankings.mockResolvedValue({ pct_change_rank: [], generated_at: '2026-07-18T09:46:00+08:00' });
    api.getSectorRadar.mockResolvedValue({ inflow: [], source_status: [], generated_at: '2026-07-18T09:46:00+08:00' });
    api.getSectorReplicaRadar.mockResolvedValue({ axis: [], series: [], source_status: [], generated_at: '2026-07-18T09:46:00+08:00' });
  });

  afterEach(() => vi.unstubAllGlobals());

  it('does not import, request, or render auction Top3', () => {
    const source = readFileSync(fileURLToPath(new URL('./HomeView.vue', import.meta.url)), 'utf8');
    expect(source).not.toContain('getAuctionModelTop3');
    expect(source).not.toContain('AuctionModelTop3Response');
    expect(source).not.toContain('竞价 Top3');
  });

  it('renders the dense market sections and requests the compact sector curve', async () => {
    const wrapper = shallowMount(HomeView, {
      global: {
        stubs: {
          PageHeader: { template: '<header><slot name="meta"/><slot/></header>' },
          SectionHeader: { props: ['title'], template: '<h2>{{ title }}</h2>' },
          MetricStrip: true,
          DataList: true,
          StatusTag: true,
          ASegmented: true,
          AButton: true,
          AAlert: true,
          SectorRadarChart: true
        }
      }
    });
    await flushPromises();

    expect(wrapper.text()).toContain('主要指数');
    expect(wrapper.text()).toContain('板块资金流');
    expect(wrapper.text()).toContain('板块实时曲线');
    expect(wrapper.text()).toContain('市场关注榜');
    expect(wrapper.text()).toContain('数据状态');
    expect(api.getSectorReplicaRadar).toHaveBeenCalledWith({ mode: 'strength', limit: 5, stockLimit: 1 });
  });

  it('defers chart mounting until the next animation frame', () => {
    const source = readFileSync(fileURLToPath(new URL('./HomeView.vue', import.meta.url)), 'utf8');
    expect(source).toContain('defineAsyncComponent');
    expect(source).toContain('requestAnimationFrame');
    expect(source).toContain('v-if="chartsReady"');
  });
});
```

- [ ] **Step 2: 运行组件测试确认 RED**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
pnpm vitest run src/views/HomeView.test.ts
```

Expected: Top3 移除、板块实时曲线和图表延迟挂载断言失败。

- [ ] **Step 3: 重写首页脚本的数据边界**

在 `HomeView.vue` 中：

- 删除 `getAuctionModelTop3`、`isAuctionModelTop3CacheMiss`、`AuctionModelTop3Response`、`AuctionModelPredictionItem`、`top3`、`top3Message` 和 `asTop3Item`。
- 删除 `getMarketEmotionSnapshot`、`MarketEmotionSnapshotResponse`、`MarketTrendChart` 和情绪曲线 option。
- 删除 `useTradeDate`、日期选择器和无效的历史日期切换。
- 使用 `useHomeDashboard()` 暴露的四项资源。
- 用 `defineAsyncComponent(() => import('@/components/charts/SectorRadarChart.vue'))` 动态加载图表。
- 在 `onMounted` 中并行启动 `loadInitial()`，并用 `requestAnimationFrame` 设置 `chartsReady`；`onBeforeUnmount` 取消尚未执行的 frame。
- 右侧曲线 option 调用：

```ts
buildSectorReplicaChartOption({
  axis: sectorTrend.value?.axis ?? [],
  compact: true,
  mode: sectorMode.value,
  series: sectorTrend.value?.series ?? []
}) as EChartsOption
```

- 数据源状态按 `source` 去重合并 `overview`、`sectorFlow`、`sectorTrend` 的 `source_status`；同源冲突优先级为 `failed > stale > success > unknown`。

- [ ] **Step 4: 重写首页模板与局部样式**

模板使用以下完整结构；脚本中为模板建立 `overviewData`、`rankingData`、`sectorFlowData`、`sectorTrendData`、对应 loading/error、`displayTradeDate` 和 `latestUpdate` computed，避免在模板中访问嵌套 ref 的 `.value`：

```vue
<PageHeader title="市场总览" description="全 A 盘面、资金流与板块轮动">
  <template #meta>{{ displayTradeDate }} · {{ latestUpdate }}</template>
  <a-button :loading="busy" type="primary" @click="refreshAll">刷新数据</a-button>
</PageHeader>

<a-alert v-if="overviewError && !overviewData" :title="overviewError" show-icon type="warning" />

<section class="home-index-section">
  <SectionHeader title="主要指数" :updated-at="latestUpdate" />
  <div class="home-index-grid">
    <div v-for="index in indices" :key="index.symbol" class="home-index-cell">
      <span class="home-index-cell__name">{{ index.name }}</span>
      <div class="home-index-cell__quote">
        <strong>{{ index.last_price ?? '--' }}</strong>
        <span :class="changeTone(index.change_pct)">{{ formatPct(index.change_pct) }}</span>
      </div>
    </div>
  </div>
  <div v-if="!indices.length" class="home-empty home-empty--indices">主要指数待确认</div>
</section>

<MetricStrip :items="overviewMetrics" />

<div class="home-chart-grid">
  <section class="home-panel">
    <SectionHeader title="板块资金流" :updated-at="formatGeneratedAt(sectorFlowData?.generated_at)" />
    <div v-if="sectorFlowError && !sectorFlowData" class="home-empty home-empty--error" role="alert">
      {{ sectorFlowError }}
    </div>
    <SectorRadarChart
      v-else-if="chartsReady"
      :height="280"
      :loading="sectorFlowLoading && !sectorFlowData"
      :option="sectorFlowOption"
    />
    <div v-else class="home-chart-placeholder">正在准备图表</div>
  </section>
  <section class="home-panel">
    <SectionHeader
      title="板块实时曲线"
      :source="sectorMode === 'strength' ? '强度 Top 5' : '主力流 Top 5'"
      :updated-at="formatGeneratedAt(sectorTrendData?.generated_at)"
    >
      <a-segmented
        :value="sectorMode"
        size="small"
        :options="[{ label: '强度', value: 'strength' }, { label: '主力流', value: 'main_flow' }]"
        @change="value => setSectorMode(value as SectorReplicaMode)"
      />
    </SectionHeader>
    <div v-if="sectorTrendError && !sectorTrendData" class="home-empty home-empty--error" role="alert">
      {{ sectorTrendError }}
    </div>
    <SectorRadarChart
      v-else-if="chartsReady"
      :height="280"
      :loading="sectorTrendLoading && !sectorTrendData"
      :option="sectorTrendOption"
    />
    <div v-else class="home-chart-placeholder">正在准备图表</div>
  </section>
</div>

<div class="home-bottom-grid">
  <section class="home-panel">
    <SectionHeader title="市场关注榜" :updated-at="formatGeneratedAt(rankingData?.generated_at)" />
    <DataList
      :items="rankingData?.pct_change_rank.slice(0, 8) ?? []"
      :loading="rankingLoading"
      :error="rankingError"
      empty-description="暂无排行榜"
    >
      <template #list-item="{ item }">
        <div class="home-ranking-row">
          <span>{{ asRankingItem(item).name || asRankingItem(item).symbol }}</span>
          <span :class="changeTone(asRankingItem(item).pct_change)">{{ formatPct(asRankingItem(item).pct_change) }}</span>
        </div>
      </template>
    </DataList>
  </section>
  <section class="home-panel">
    <SectionHeader title="数据状态" :updated-at="latestUpdate">
      <span class="text-12px text-text-secondary">{{ sourceItems.length || '--' }} 个来源</span>
    </SectionHeader>
    <div class="home-source-list">
      <div v-for="item in sourceItems" :key="item.source" class="home-source-row">
        <span class="truncate">{{ item.source }}</span>
        <StatusTag :status="sourceStatusTone(item.status)" />
      </div>
      <div v-if="!sourceItems.length" class="home-empty">数据状态待确认</div>
    </div>
  </section>
</div>
```

局部 CSS 使用以下规则，全部复用既有 `--wb-*` token：

```css
.home-index-section { min-width: 0; }
.home-index-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
.home-index-cell { min-width: 0; padding: 10px 12px; background: var(--wb-surface); border: 1px solid var(--wb-border); border-radius: var(--wb-radius); }
.home-index-cell__name { color: var(--wb-muted); font-size: 12px; }
.home-index-cell__quote { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-top: 4px; font-variant-numeric: tabular-nums; }
.home-index-cell__quote strong { color: var(--wb-ink); font-size: 16px; }
.home-chart-grid { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(320px, 1fr); gap: 12px; }
.home-bottom-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr); gap: 12px; }
.home-panel { min-width: 0; padding: 12px; background: var(--wb-surface); border: 1px solid var(--wb-border); border-radius: var(--wb-radius); }
.home-chart-placeholder { display: grid; height: 280px; place-items: center; color: var(--wb-muted); font-size: 12px; }
.home-empty { padding: 20px 8px; color: var(--wb-muted); font-size: 13px; text-align: center; }
.home-empty--indices { min-height: 64px; }
.home-empty--error { display: grid; height: 280px; place-items: center; color: var(--wb-positive); }
.home-ranking-row, .home-source-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-width: 0; }
.home-source-list { padding-top: 4px; }
.home-source-row { min-height: 38px; border-bottom: 1px solid var(--wb-border); }
.home-source-row:last-child { border-bottom: 0; }
@media (max-width: 1023px) {
  .home-chart-grid, .home-bottom-grid { grid-template-columns: 1fr; }
}
@media (max-width: 639px) {
  .home-index-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .home-panel { padding: 10px; }
  .home-index-cell__quote { align-items: flex-start; flex-direction: column; gap: 2px; }
}
```

- [ ] **Step 5: 运行组件测试和类型检查**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
pnpm vitest run src/views/HomeView.test.ts src/composables/useHomeDashboard.test.ts src/utils/requestCache.test.ts src/service/api.test.ts
pnpm typecheck
```

Expected: 定向测试全部通过；`vue-tsc` 退出码 0。

- [ ] **Step 6: 提交首页重构**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/web-vue/src/views/HomeView.vue apps/web-vue/src/views/HomeView.test.ts
git commit -m "feat: rebuild vue market overview"
```

### Task 4: 完整验证与浏览器检查

**Files:**
- Modify only if verification exposes a scoped defect: files created or modified in Tasks 1-3.

- [ ] **Step 1: 运行 Vue 全量单元测试**

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
pnpm test:unit
```

Expected: 全部 Vitest 测试通过。

- [ ] **Step 2: 运行类型检查和生产构建**

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
pnpm typecheck
pnpm build
```

Expected: 两个命令退出码 0；构建产物不再让 `HomeView` 静态依赖 `MarketTrendChart`。

- [ ] **Step 3: 启动本地生产预览**

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
pnpm dev:prod --host 0.0.0.0 --port 3124
```

Expected: 输出本地访问 URL `http://127.0.0.1:3124/`；若端口已占用，使用下一个空闲端口。

- [ ] **Step 4: 桌面与移动端视觉、网络验证**

用浏览器检查 `1440x900` 与 `390x844`：

- 首页不出现竞价 Top3。
- 主要指数和四项市场状态位于图表之前。
- 板块资金流与板块实时曲线在桌面同排、移动端单列。
- 曲线图例不覆盖绘图区，强度/主力流切换只更新右图。
- 首次文字内容先于 ECharts 可见，图表加载不改变容器高度。
- 15 秒内离开并返回首页不重复请求同键 API；点击刷新会重新请求。
- 单个次要接口失败不会阻塞指数和市场状态。

- [ ] **Step 5: 检查最终差异**

```bash
cd /Users/kale/Documents/strong-stock-screener
git diff --check
git status --short
git log -4 --oneline
```

Expected: `git diff --check` 无输出；只保留实施前已存在的无关脏文件；日志包含本计划的三个实现提交。
