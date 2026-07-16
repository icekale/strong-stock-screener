import { describe, expect, it } from 'vitest';
import type { BackgroundJobState } from '@/service/types';
import { useJobPolling } from './useJobPolling';

function job(status: BackgroundJobState['status'], result: unknown = null): BackgroundJobState {
  return {
    job_id: 'job-1',
    type: 'test',
    status,
    progress_current: status === 'success' ? 3 : 1,
    progress_total: 3,
    message: status,
    started_at: null,
    finished_at: null,
    error: null,
    result_path: null,
    result
  };
}

describe('useJobPolling', () => {
  it('polls until a job reaches a terminal state and returns its result', async () => {
    let reads = 0;
    const polling = useJobPolling(
      async () => job('pending'),
      async () => {
        reads += 1;
        return reads === 1 ? job('running') : job('success', { done: true });
      },
      { intervalMs: 0 }
    );

    await expect(polling.run()).resolves.toEqual({ done: true });
    expect(polling.job.value?.status).toBe('success');
    expect(polling.progress.value).toBe(100);
    expect(polling.polling.value).toBe(false);
  });
});
