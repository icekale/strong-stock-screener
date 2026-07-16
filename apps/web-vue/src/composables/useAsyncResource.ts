import { computed, ref } from 'vue';

export function useAsyncResource<T>(loader: () => Promise<T>) {
  const data = ref<T>();
  const loading = ref(false);
  const refreshing = ref(false);
  const error = ref<Error>();
  const isStale = ref(false);

  const hasData = computed(() => data.value !== undefined);

  async function refresh(): Promise<T> {
    const hasPreviousData = hasData.value;
    loading.value = !hasPreviousData;
    refreshing.value = hasPreviousData;
    error.value = undefined;

    try {
      const next = await loader();
      data.value = next;
      isStale.value = false;
      return next;
    } catch (cause) {
      const nextError = cause instanceof Error ? cause : new Error(String(cause));
      error.value = nextError;
      isStale.value = hasPreviousData;
      throw nextError;
    } finally {
      loading.value = false;
      refreshing.value = false;
    }
  }

  return { data, loading, refreshing, error, isStale, refresh };
}
