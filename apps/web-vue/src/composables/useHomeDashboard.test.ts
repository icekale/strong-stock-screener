import { describe, expect, it, vi } from 'vitest';
import type { CapitalSummaryResponse, MarketOverviewResponse, SectorRadarResponse } from '@/service/types';
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

function sectorFlow(value: string): SectorRadarResponse {
  return { generated_at: value } as SectorRadarResponse;
}

function capital(value: string): CapitalSummaryResponse {
  return { generated_at: value } as CapitalSummaryResponse;
}

function dependencies(overrides: Partial<HomeDashboardDependencies> = {}): HomeDashboardDependencies {
  return {
    getMarketOverview: vi.fn(() => Promise.resolve(overview('overview'))),
    getSectorRadar: vi.fn(() => Promise.resolve(sectorFlow('sector-flow'))),
    getCapitalSummary: vi.fn(() => Promise.resolve(capital('capital'))),
    ...overrides
  };
}

function cache() {
  return createMemoryRequestCache({ now: () => 0, ttlMs: 15_000 });
}

describe('useHomeDashboard', () => {
  it('starts every initial request together and commits each result independently', async () => {
    const overviewRequest = deferred<MarketOverviewResponse>();
    const sectorFlowRequest = deferred<SectorRadarResponse>();
    const capitalRequest = deferred<CapitalSummaryResponse>();
    const api = dependencies({
      getMarketOverview: vi.fn(() => overviewRequest.promise),
      getSectorRadar: vi.fn(() => sectorFlowRequest.promise),
      getCapitalSummary: vi.fn(() => capitalRequest.promise)
    });
    const dashboard = useHomeDashboard({ dependencies: api, cache: cache() });

    let settled = false;
    const loading = dashboard.loadInitial().then(() => {
      settled = true;
    });
    await flushMicrotasks();

    expect(api.getMarketOverview).toHaveBeenCalledTimes(1);
    expect(api.getSectorRadar).toHaveBeenCalledWith(12);
    expect(api.getCapitalSummary).toHaveBeenCalledTimes(1);

    const overviewResult = overview('first');
    overviewRequest.resolve(overviewResult);
    await flushMicrotasks();

    expect(dashboard.overview.data.value).toBe(overviewResult);
    expect(dashboard.sectorFlow.data.value).toBeUndefined();
    expect(dashboard.capital.data.value).toBeUndefined();
    expect(settled).toBe(false);

    const capitalResult = capital('first');
    capitalRequest.resolve(capitalResult);
    await flushMicrotasks();

    expect(dashboard.capital.data.value).toBe(capitalResult);
    expect(dashboard.sectorFlow.data.value).toBeUndefined();
    expect(settled).toBe(false);

    sectorFlowRequest.resolve(sectorFlow('first'));
    await loading;
  });

  it('uses only the three dashboard resources and their exact cache keys', async () => {
    const requestKeys: string[] = [];
    const requestCache = {
      get<T>(key: string, loader: () => Promise<T>): Promise<T> {
        requestKeys.push(key);
        return loader();
      }
    };
    const dashboard = useHomeDashboard({ dependencies: dependencies(), cache: requestCache });

    await dashboard.loadInitial();

    expect(requestKeys).toEqual(['home:overview', 'home:sector-flow:12', 'home:capital-summary']);
    expect(dashboard).not.toHaveProperty('rankings');
    expect(dashboard).not.toHaveProperty('sectorTrend');
    expect(dashboard).not.toHaveProperty('sectorMode');
    expect(dashboard).not.toHaveProperty('setSectorMode');
  });

  it('isolates a secondary failure from successful initial resources', async () => {
    const failure = new Error('capital summary failed');
    const api = dependencies({
      getCapitalSummary: vi.fn(() => Promise.reject(failure))
    });
    const dashboard = useHomeDashboard({ dependencies: api, cache: cache() });

    await dashboard.loadInitial();

    expect(dashboard.overview.data.value).toEqual(overview('overview'));
    expect(dashboard.sectorFlow.data.value).toEqual(sectorFlow('sector-flow'));
    expect(dashboard.capital.data.value).toBeUndefined();
    expect(dashboard.capital.error.value).toBe(failure);
  });

  it('preserves successful data and marks it stale after a forced refresh failure', async () => {
    const first = capital('first');
    const api = dependencies({
      getCapitalSummary: vi.fn().mockResolvedValueOnce(first).mockRejectedValueOnce('forced failure')
    });
    const dashboard = useHomeDashboard({ dependencies: api, cache: cache() });

    await dashboard.capital.refresh();
    await expect(dashboard.capital.refresh({ force: true })).rejects.toThrow('forced failure');

    expect(dashboard.capital.data.value).toBe(first);
    expect(dashboard.capital.isStale.value).toBe(true);
    expect(dashboard.capital.error.value?.message).toBe('forced failure');
  });

  it('shares completed cached results and forces every loader through refreshAll', async () => {
    const api = dependencies();
    const sharedCache = cache();
    const firstDashboard = useHomeDashboard({ dependencies: api, cache: sharedCache });
    const secondDashboard = useHomeDashboard({ dependencies: api, cache: sharedCache });

    await firstDashboard.loadInitial();
    await secondDashboard.loadInitial();

    expect(api.getMarketOverview).toHaveBeenCalledTimes(1);
    expect(api.getSectorRadar).toHaveBeenCalledTimes(1);
    expect(api.getCapitalSummary).toHaveBeenCalledTimes(1);

    await secondDashboard.refreshAll();

    expect(api.getMarketOverview).toHaveBeenCalledTimes(2);
    expect(api.getSectorRadar).toHaveBeenCalledTimes(2);
    expect(api.getCapitalSummary).toHaveBeenCalledTimes(2);
  });

  it('isolates caches for composables with custom dependencies', async () => {
    const api = dependencies();
    const firstDashboard = useHomeDashboard({ dependencies: api });
    const secondDashboard = useHomeDashboard({ dependencies: api });

    await firstDashboard.loadInitial();
    await secondDashboard.loadInitial();

    expect(api.getMarketOverview).toHaveBeenCalledTimes(2);
    expect(api.getSectorRadar).toHaveBeenCalledTimes(2);
    expect(api.getCapitalSummary).toHaveBeenCalledTimes(2);
  });

  it('tracks busy through loading and refreshing across the three resources', async () => {
    const overviewRequest = deferred<MarketOverviewResponse>();
    const sectorFlowRequest = deferred<SectorRadarResponse>();
    const initialCapitalRequest = deferred<CapitalSummaryResponse>();
    const refreshedCapitalRequest = deferred<CapitalSummaryResponse>();
    const api = dependencies({
      getMarketOverview: vi.fn(() => overviewRequest.promise),
      getSectorRadar: vi.fn(() => sectorFlowRequest.promise),
      getCapitalSummary: vi
        .fn()
        .mockReturnValueOnce(initialCapitalRequest.promise)
        .mockReturnValueOnce(refreshedCapitalRequest.promise)
    });
    const dashboard = useHomeDashboard({ dependencies: api, cache: cache() });

    const initialLoad = dashboard.loadInitial();
    expect(dashboard.busy.value).toBe(true);

    overviewRequest.resolve(overview('initial'));
    sectorFlowRequest.resolve(sectorFlow('initial'));
    await flushMicrotasks();
    expect(dashboard.busy.value).toBe(true);

    initialCapitalRequest.resolve(capital('initial'));
    await initialLoad;
    expect(dashboard.busy.value).toBe(false);

    const refresh = dashboard.capital.refresh({ force: true });
    expect(dashboard.busy.value).toBe(true);
    expect(dashboard.capital.refreshing.value).toBe(true);

    refreshedCapitalRequest.resolve(capital('refreshed'));
    await refresh;
    expect(dashboard.busy.value).toBe(false);
  });
});
