import { describe, expect, it, vi } from 'vitest';
import type {
  MarketOverviewResponse,
  MarketRankingsResponse,
  SectorRadarResponse,
  SectorReplicaMode,
  SectorReplicaRadarResponse
} from '@/service/types';
import { createMemoryRequestCache } from '@/utils/requestCache';
import { type HomeDashboardDependencies, useHomeDashboard } from './useHomeDashboard';

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
};

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });

  return { promise, resolve, reject };
}

async function flushMicrotasks(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

function overview(value: string): MarketOverviewResponse {
  return { generated_at: value } as MarketOverviewResponse;
}

function rankings(value: string): MarketRankingsResponse {
  return { generated_at: value } as MarketRankingsResponse;
}

function sectorFlow(value: string): SectorRadarResponse {
  return { generated_at: value } as SectorRadarResponse;
}

function sectorTrend(value: string, mode: SectorReplicaMode = 'strength'): SectorReplicaRadarResponse {
  return { generated_at: value, mode } as SectorReplicaRadarResponse;
}

function dependencies(overrides: Partial<HomeDashboardDependencies> = {}): HomeDashboardDependencies {
  return {
    getMarketOverview: vi.fn(() => Promise.resolve(overview('overview'))),
    getMarketRankings: vi.fn(() => Promise.resolve(rankings('rankings'))),
    getSectorRadar: vi.fn(() => Promise.resolve(sectorFlow('sector-flow'))),
    getSectorReplicaRadar: vi.fn(() => Promise.resolve(sectorTrend('sector-trend'))),
    ...overrides
  };
}

function cache() {
  return createMemoryRequestCache({ now: () => 0, ttlMs: 15_000 });
}

describe('useHomeDashboard', () => {
  it('starts every initial request together and commits each result independently', async () => {
    const overviewRequest = deferred<MarketOverviewResponse>();
    const rankingsRequest = deferred<MarketRankingsResponse>();
    const sectorFlowRequest = deferred<SectorRadarResponse>();
    const sectorTrendRequest = deferred<SectorReplicaRadarResponse>();
    const api = dependencies({
      getMarketOverview: vi.fn(() => overviewRequest.promise),
      getMarketRankings: vi.fn(() => rankingsRequest.promise),
      getSectorRadar: vi.fn(() => sectorFlowRequest.promise),
      getSectorReplicaRadar: vi.fn(() => sectorTrendRequest.promise)
    });
    const dashboard = useHomeDashboard({ dependencies: api, cache: cache() });

    let settled = false;
    const loading = dashboard.loadInitial().then(() => {
      settled = true;
    });
    await flushMicrotasks();

    expect(api.getMarketOverview).toHaveBeenCalledTimes(1);
    expect(api.getMarketRankings).toHaveBeenCalledWith(12);
    expect(api.getSectorRadar).toHaveBeenCalledWith(12);
    expect(api.getSectorReplicaRadar).toHaveBeenCalledWith({ mode: 'strength', limit: 5, stockLimit: 1 });

    const overviewResult = overview('first');
    overviewRequest.resolve(overviewResult);
    await flushMicrotasks();

    expect(dashboard.overview.data.value).toBe(overviewResult);
    expect(dashboard.rankings.data.value).toBeUndefined();
    expect(dashboard.sectorFlow.data.value).toBeUndefined();
    expect(dashboard.sectorTrend.data.value).toBeUndefined();
    expect(settled).toBe(false);

    rankingsRequest.resolve(rankings('first'));
    sectorFlowRequest.resolve(sectorFlow('first'));
    sectorTrendRequest.resolve(sectorTrend('first'));
    await loading;
  });

  it('isolates secondary failures from successful initial resources', async () => {
    const failure = new Error('sector flow failed');
    const api = dependencies({
      getSectorRadar: vi.fn(() => Promise.reject(failure))
    });
    const dashboard = useHomeDashboard({ dependencies: api, cache: cache() });

    await dashboard.loadInitial();

    expect(dashboard.overview.data.value).toEqual(overview('overview'));
    expect(dashboard.rankings.data.value).toEqual(rankings('rankings'));
    expect(dashboard.sectorTrend.data.value).toEqual(sectorTrend('sector-trend'));
    expect(dashboard.sectorFlow.data.value).toBeUndefined();
    expect(dashboard.sectorFlow.error.value).toBe(failure);
  });

  it('preserves successful data and marks it stale after a forced refresh failure', async () => {
    const first = overview('first');
    const api = dependencies({
      getMarketOverview: vi.fn().mockResolvedValueOnce(first).mockRejectedValueOnce('forced failure')
    });
    const dashboard = useHomeDashboard({ dependencies: api, cache: cache() });

    await dashboard.overview.refresh();
    await expect(dashboard.overview.refresh({ force: true })).rejects.toThrow('forced failure');

    expect(dashboard.overview.data.value).toBe(first);
    expect(dashboard.overview.isStale.value).toBe(true);
    expect(dashboard.overview.error.value?.message).toBe('forced failure');
  });

  it('refreshes only the trend when the sector mode changes', async () => {
    const api = dependencies();
    const dashboard = useHomeDashboard({ dependencies: api, cache: cache() });

    await dashboard.loadInitial();
    await dashboard.setSectorMode('main_flow');

    expect(api.getMarketOverview).toHaveBeenCalledTimes(1);
    expect(api.getMarketRankings).toHaveBeenCalledTimes(1);
    expect(api.getSectorRadar).toHaveBeenCalledTimes(1);
    expect(api.getSectorReplicaRadar).toHaveBeenCalledTimes(2);
    expect(api.getSectorReplicaRadar).toHaveBeenLastCalledWith({ mode: 'main_flow', limit: 5, stockLimit: 1 });
  });

  it('does not refetch the sector trend when its mode is unchanged', async () => {
    const api = dependencies();
    const dashboard = useHomeDashboard({ dependencies: api, cache: cache() });

    await dashboard.loadInitial();
    await dashboard.setSectorMode('strength');

    expect(api.getSectorReplicaRadar).toHaveBeenCalledTimes(1);
  });

  it('captures the sector mode before the cache defers each trend loader', async () => {
    const strength = deferred<SectorReplicaRadarResponse>();
    const mainFlow = deferred<SectorReplicaRadarResponse>();
    const getSectorReplicaRadar = vi.fn((options: { mode?: SectorReplicaMode } = {}) =>
      options.mode === 'strength' ? strength.promise : mainFlow.promise
    );
    const api = dependencies({
      getSectorReplicaRadar
    });
    const dashboard = useHomeDashboard({ dependencies: api, cache: cache() });

    const initial = dashboard.loadInitial();
    const changed = dashboard.setSectorMode('main_flow');
    await flushMicrotasks();

    expect(getSectorReplicaRadar).toHaveBeenCalledTimes(2);
    expect(getSectorReplicaRadar.mock.calls.map(([options]) => options?.mode)).toEqual(['strength', 'main_flow']);

    strength.resolve(sectorTrend('strength', 'strength'));
    mainFlow.resolve(sectorTrend('main-flow', 'main_flow'));
    await Promise.all([initial, changed]);
  });

  it('keeps trend busy and unpublished while the latest mode request is pending', async () => {
    const strength = deferred<SectorReplicaRadarResponse>();
    const mainFlow = deferred<SectorReplicaRadarResponse>();
    const api = dependencies({
      getSectorReplicaRadar: vi.fn(({ mode }) => (mode === 'strength' ? strength.promise : mainFlow.promise))
    });
    const dashboard = useHomeDashboard({ dependencies: api, cache: cache() });

    const oldRequest = dashboard.sectorTrend.refresh();
    await flushMicrotasks();
    const currentRequest = dashboard.setSectorMode('main_flow');
    await flushMicrotasks();

    strength.resolve(sectorTrend('strength', 'strength'));
    await oldRequest;
    await flushMicrotasks();

    expect(dashboard.sectorTrend.data.value).toBeUndefined();
    expect(dashboard.busy.value).toBe(true);

    const current = sectorTrend('main-flow', 'main_flow');
    mainFlow.resolve(current);
    await currentRequest;

    expect(dashboard.sectorTrend.data.value).toBe(current);
    expect(dashboard.busy.value).toBe(false);
  });

  it('does not let a late strength success replace the latest trend result', async () => {
    const strength = deferred<SectorReplicaRadarResponse>();
    const mainFlow = deferred<SectorReplicaRadarResponse>();
    const api = dependencies({
      getSectorReplicaRadar: vi.fn(({ mode }) => (mode === 'strength' ? strength.promise : mainFlow.promise))
    });
    const dashboard = useHomeDashboard({ dependencies: api, cache: cache() });

    const oldRequest = dashboard.sectorTrend.refresh();
    await flushMicrotasks();
    const currentRequest = dashboard.setSectorMode('main_flow');
    await flushMicrotasks();
    const current = sectorTrend('main-flow', 'main_flow');
    mainFlow.resolve(current);
    await currentRequest;

    strength.resolve(sectorTrend('strength', 'strength'));
    await oldRequest;

    expect(dashboard.sectorTrend.data.value).toBe(current);
  });

  it('does not let a late strength failure overwrite the latest trend state', async () => {
    const strength = deferred<SectorReplicaRadarResponse>();
    const mainFlow = deferred<SectorReplicaRadarResponse>();
    const api = dependencies({
      getSectorReplicaRadar: vi.fn(({ mode }) => (mode === 'strength' ? strength.promise : mainFlow.promise))
    });
    const dashboard = useHomeDashboard({ dependencies: api, cache: cache() });

    const oldRequest = dashboard.sectorTrend.refresh();
    await flushMicrotasks();
    const currentRequest = dashboard.setSectorMode('main_flow');
    await flushMicrotasks();
    const current = sectorTrend('main-flow', 'main_flow');
    mainFlow.resolve(current);
    await currentRequest;

    strength.reject(new Error('strength failed'));
    await expect(oldRequest).rejects.toThrow('strength failed');

    expect(dashboard.sectorTrend.data.value).toBe(current);
    expect(dashboard.sectorTrend.error.value).toBeUndefined();
    expect(dashboard.sectorTrend.isStale.value).toBe(false);
    expect(dashboard.busy.value).toBe(false);
  });

  it('shares completed cached results and forces every loader through refreshAll', async () => {
    const api = dependencies();
    const sharedCache = cache();
    const firstDashboard = useHomeDashboard({ dependencies: api, cache: sharedCache });
    const secondDashboard = useHomeDashboard({ dependencies: api, cache: sharedCache });

    await firstDashboard.loadInitial();
    await secondDashboard.loadInitial();

    expect(api.getMarketOverview).toHaveBeenCalledTimes(1);
    expect(api.getMarketRankings).toHaveBeenCalledTimes(1);
    expect(api.getSectorRadar).toHaveBeenCalledTimes(1);
    expect(api.getSectorReplicaRadar).toHaveBeenCalledTimes(1);

    await secondDashboard.refreshAll();

    expect(api.getMarketOverview).toHaveBeenCalledTimes(2);
    expect(api.getMarketRankings).toHaveBeenCalledTimes(2);
    expect(api.getSectorRadar).toHaveBeenCalledTimes(2);
    expect(api.getSectorReplicaRadar).toHaveBeenCalledTimes(2);
  });

  it('isolates caches for composables with custom dependencies', async () => {
    const api = dependencies();
    const firstDashboard = useHomeDashboard({ dependencies: api });
    const secondDashboard = useHomeDashboard({ dependencies: api });

    await firstDashboard.loadInitial();
    await secondDashboard.loadInitial();

    expect(api.getMarketOverview).toHaveBeenCalledTimes(2);
    expect(api.getMarketRankings).toHaveBeenCalledTimes(2);
    expect(api.getSectorRadar).toHaveBeenCalledTimes(2);
    expect(api.getSectorReplicaRadar).toHaveBeenCalledTimes(2);
  });

  it('tracks busy through initial loading and refreshing existing data', async () => {
    const initial = deferred<MarketOverviewResponse>();
    const refreshed = deferred<MarketOverviewResponse>();
    const api = dependencies({
      getMarketOverview: vi.fn().mockReturnValueOnce(initial.promise).mockReturnValueOnce(refreshed.promise)
    });
    const dashboard = useHomeDashboard({ dependencies: api, cache: cache() });

    const initialLoad = dashboard.overview.refresh();
    expect(dashboard.busy.value).toBe(true);
    expect(dashboard.overview.loading.value).toBe(true);
    initial.resolve(overview('initial'));
    await initialLoad;

    expect(dashboard.busy.value).toBe(false);
    const refresh = dashboard.overview.refresh({ force: true });
    expect(dashboard.busy.value).toBe(true);
    expect(dashboard.overview.refreshing.value).toBe(true);
    refreshed.resolve(overview('refreshed'));
    await refresh;

    expect(dashboard.busy.value).toBe(false);
  });
});
