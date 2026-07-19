import { type Ref, type ShallowRef, computed, ref, shallowRef } from 'vue';
import { getCapitalSummary, getMarketOverview, getSectorRadar } from '@/service/product-api';
import type { CapitalSummaryResponse, MarketOverviewResponse, SectorRadarResponse } from '@/service/types';
import { createMemoryRequestCache } from '@/utils/requestCache';

type CacheGetOptions = {
  force?: boolean;
};

type RequestCache = {
  get<T>(key: string, loader: () => Promise<T>, options?: CacheGetOptions): Promise<T>;
};

type RequestDescriptor<T> = {
  key: string;
  load: () => Promise<T>;
};

export type HomeDashboardDependencies = {
  getMarketOverview: typeof getMarketOverview;
  getSectorRadar: typeof getSectorRadar;
  getCapitalSummary: typeof getCapitalSummary;
};

export type HomeResource<T> = {
  data: ShallowRef<T | undefined>;
  error: ShallowRef<Error | undefined>;
  loading: Ref<boolean>;
  refreshing: Ref<boolean>;
  isStale: Ref<boolean>;
  refresh: (options?: CacheGetOptions) => Promise<T>;
};

const sharedCache = createMemoryRequestCache({ ttlMs: 15_000 });

const productionDependencies: HomeDashboardDependencies = {
  getMarketOverview,
  getSectorRadar,
  getCapitalSummary
};

function createResource<T>(cache: RequestCache, requestDescriptor: () => RequestDescriptor<T>): HomeResource<T> {
  const data = shallowRef<T>();
  const error = shallowRef<Error>();
  const loading = ref(false);
  const refreshing = ref(false);
  const isStale = ref(false);
  let requestGeneration = 0;

  async function refresh(options: CacheGetOptions = {}): Promise<T> {
    requestGeneration += 1;
    const generation = requestGeneration;
    const hasPreviousData = data.value !== undefined;
    const request = requestDescriptor();
    loading.value = !hasPreviousData;
    refreshing.value = hasPreviousData;
    error.value = undefined;

    try {
      const next = await cache.get(request.key, request.load, options);
      if (generation === requestGeneration) {
        data.value = next;
        isStale.value = false;
      }
      return next;
    } catch (cause) {
      const nextError = cause instanceof Error ? cause : new Error(String(cause));
      if (generation === requestGeneration) {
        error.value = nextError;
        isStale.value = hasPreviousData;
      }
      throw nextError;
    } finally {
      if (generation === requestGeneration) {
        loading.value = false;
        refreshing.value = false;
      }
    }
  }

  return { data, error, loading, refreshing, isStale, refresh };
}

export function useHomeDashboard(options: { dependencies?: HomeDashboardDependencies; cache?: RequestCache } = {}) {
  const dependencies = options.dependencies ?? productionDependencies;
  const cache = options.cache ?? (options.dependencies ? createMemoryRequestCache({ ttlMs: 15_000 }) : sharedCache);

  const overview = createResource<MarketOverviewResponse>(cache, () => ({
    key: 'home:overview',
    load: () => dependencies.getMarketOverview()
  }));
  const sectorFlow = createResource<SectorRadarResponse>(cache, () => ({
    key: 'home:sector-flow:12',
    load: () => dependencies.getSectorRadar(12)
  }));
  const capital = createResource<CapitalSummaryResponse>(cache, () => ({
    key: 'home:capital-summary',
    load: () => dependencies.getCapitalSummary()
  }));

  const busy = computed(
    () =>
      overview.loading.value ||
      overview.refreshing.value ||
      sectorFlow.loading.value ||
      sectorFlow.refreshing.value ||
      capital.loading.value ||
      capital.refreshing.value
  );

  async function loadInitial(): Promise<void> {
    await Promise.allSettled([overview.refresh(), sectorFlow.refresh(), capital.refresh()]);
  }

  async function refreshAll(): Promise<void> {
    await Promise.allSettled([
      overview.refresh({ force: true }),
      sectorFlow.refresh({ force: true }),
      capital.refresh({ force: true })
    ]);
  }

  return {
    overview,
    sectorFlow,
    capital,
    busy,
    loadInitial,
    refreshAll
  };
}
