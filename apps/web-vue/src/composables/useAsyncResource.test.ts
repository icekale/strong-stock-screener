import { describe, expect, it, vi } from 'vitest';
import { useAsyncResource } from './useAsyncResource';

describe('useAsyncResource', () => {
  it('loads data and exposes loading state transitions', async () => {
    const loader = vi.fn().mockResolvedValue({ value: 7 });
    const resource = useAsyncResource(loader);

    expect(resource.data.value).toBeUndefined();
    expect(resource.loading.value).toBe(false);

    await resource.refresh();

    expect(resource.data.value).toEqual({ value: 7 });
    expect(resource.error.value).toBeUndefined();
    expect(resource.isStale.value).toBe(false);
    expect(loader).toHaveBeenCalledTimes(1);
  });

  it('keeps the previous value when a refresh fails', async () => {
    const loader = vi
      .fn()
      .mockResolvedValueOnce('first')
      .mockRejectedValueOnce(new Error('temporary failure'));
    const resource = useAsyncResource(loader);

    await resource.refresh();
    await expect(resource.refresh()).rejects.toThrow('temporary failure');

    expect(resource.data.value).toBe('first');
    expect(resource.isStale.value).toBe(true);
    expect(resource.error.value?.message).toBe('temporary failure');
  });
});
