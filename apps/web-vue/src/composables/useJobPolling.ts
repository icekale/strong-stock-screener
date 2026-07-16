import { computed, ref } from 'vue';
import type { BackgroundJobState } from '@/service/types';

type PollingOptions = {
  intervalMs?: number;
};

const TERMINAL_STATUSES = new Set<BackgroundJobState['status']>(['success', 'failed', 'canceled']);

export function useJobPolling<T>(
  start: () => Promise<BackgroundJobState>,
  read: (jobId: string) => Promise<BackgroundJobState>,
  options: PollingOptions = {}
) {
  const job = ref<BackgroundJobState | null>(null);
  const result = ref<T>();
  const polling = ref(false);
  const error = ref<Error>();
  const cancelled = ref(false);
  const intervalMs = options.intervalMs ?? 1000;

  const progress = computed(() => {
    const current = job.value?.progress_current ?? 0;
    const total = job.value?.progress_total ?? 0;
    if (job.value?.status === 'success') return 100;
    if (total <= 0) return 0;
    return Math.max(0, Math.min(100, Math.round((current / total) * 100)));
  });

  function wait() {
    return new Promise<void>(resolve => setTimeout(resolve, intervalMs));
  }

  async function run(): Promise<T | undefined> {
    cancelled.value = false;
    error.value = undefined;
    result.value = undefined;
    polling.value = true;

    try {
      job.value = await start();
      while (job.value && !TERMINAL_STATUSES.has(job.value.status)) {
        if (cancelled.value) return undefined;
        await wait();
        if (cancelled.value) return undefined;
        job.value = await read(job.value.job_id);
      }

      if (job.value?.status === 'failed') {
        throw new Error(job.value.error || job.value.message || '后台任务失败');
      }
      if (job.value?.status === 'canceled') {
        throw new Error(job.value.message || '后台任务已取消');
      }

      result.value = job.value?.result as T | undefined;
      return result.value;
    } catch (cause) {
      error.value = cause instanceof Error ? cause : new Error(String(cause));
      throw error.value;
    } finally {
      polling.value = false;
    }
  }

  function cancel() {
    cancelled.value = true;
    polling.value = false;
  }

  return { job, result, progress, polling, error, run, cancel };
}
