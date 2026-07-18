import { describe, expect, it } from 'vitest';
import { createMemoryRequestCache } from './requestCache';

describe('createMemoryRequestCache', () => {
  it('returns a successful value from cache inside the TTL', async () => {
    let now = 0;
    let calls = 0;
    const cache = createMemoryRequestCache({ now: () => now, ttlMs: 15_000 });
    const request = async () => {
      calls += 1;
      return 'cached';
    };

    await expect(cache.get('key', request)).resolves.toBe('cached');
    now = 14_999;
    await expect(cache.get('key', request)).resolves.toBe('cached');

    expect(calls).toBe(1);
  });

  it('reloads an expired value', async () => {
    let now = 0;
    let calls = 0;
    const cache = createMemoryRequestCache({ now: () => now, ttlMs: 15_000 });
    const request = async () => {
      calls += 1;
      return calls;
    };

    await expect(cache.get('key', request)).resolves.toBe(1);
    now = 15_000;
    await expect(cache.get('key', request)).resolves.toBe(2);

    expect(calls).toBe(2);
  });

  it('shares the same in-flight Promise and loads once for concurrent calls', async () => {
    let resolveRequest!: (value: string) => void;
    let calls = 0;
    const cache = createMemoryRequestCache({ now: () => 0, ttlMs: 15_000 });
    const request = () => {
      calls += 1;
      return new Promise<string>(resolve => {
        resolveRequest = resolve;
      });
    };

    const first = cache.get('key', request);
    const second = cache.get('key', request);

    expect(second).toBe(first);
    await Promise.resolve();
    expect(calls).toBe(1);
    resolveRequest('loaded');
    await expect(first).resolves.toBe('loaded');
  });

  it('bypasses a completed value when forced and restores it after refresh failure', async () => {
    let calls = 0;
    const cache = createMemoryRequestCache({ now: () => 0, ttlMs: 15_000 });
    const initialRequest = async () => 'previous';
    const failingRequest = async () => {
      calls += 1;
      throw new Error('refresh failed');
    };

    await expect(cache.get('key', initialRequest)).resolves.toBe('previous');
    await expect(cache.get('key', failingRequest, { force: true })).rejects.toThrow('refresh failed');
    await expect(cache.get('key', failingRequest)).resolves.toBe('previous');

    expect(calls).toBe(1);
  });

  it('shares an in-flight request even when the second call is forced', async () => {
    let resolveRequest!: (value: string) => void;
    let calls = 0;
    const cache = createMemoryRequestCache({ now: () => 0, ttlMs: 15_000 });
    const request = () => {
      calls += 1;
      return new Promise<string>(resolve => {
        resolveRequest = resolve;
      });
    };

    const first = cache.get('key', request);
    const second = cache.get('key', request, { force: true });

    expect(second).toBe(first);
    await Promise.resolve();
    expect(calls).toBe(1);
    resolveRequest('loaded');
    await expect(second).resolves.toBe('loaded');
  });

  it('does not cache a failure when there is no previous value', async () => {
    let calls = 0;
    const cache = createMemoryRequestCache({ now: () => 0, ttlMs: 15_000 });
    const request = async () => {
      calls += 1;
      if (calls === 1) throw new Error('first failed');
      return 'retry succeeded';
    };

    await expect(cache.get('key', request)).rejects.toThrow('first failed');
    await expect(cache.get('key', request)).resolves.toBe('retry succeeded');

    expect(calls).toBe(2);
  });

  it('measures the TTL from request completion time', async () => {
    let now = 0;
    let calls = 0;
    let resolveRequest!: (value: string) => void;
    const cache = createMemoryRequestCache({ now: () => now, ttlMs: 15_000 });
    const request = () => {
      calls += 1;
      if (calls === 1) {
        return new Promise<string>(resolve => {
          resolveRequest = resolve;
        });
      }
      return Promise.resolve('reloaded');
    };

    const pending = cache.get('key', request);
    now = 1_000;
    await Promise.resolve();
    resolveRequest('loaded');
    await expect(pending).resolves.toBe('loaded');

    now = 15_999;
    await expect(cache.get('key', request)).resolves.toBe('loaded');
    now = 16_000;
    await expect(cache.get('key', request)).resolves.toBe('reloaded');

    expect(calls).toBe(2);
  });

  it('caches a successful undefined value', async () => {
    let calls = 0;
    const cache = createMemoryRequestCache({ now: () => 0, ttlMs: 15_000 });
    const request = async () => {
      calls += 1;
      return undefined;
    };

    await expect(cache.get('key', request)).resolves.toBeUndefined();
    await expect(cache.get('key', request)).resolves.toBeUndefined();

    expect(calls).toBe(1);
  });

  it('reloads a value after clear', async () => {
    let calls = 0;
    const cache = createMemoryRequestCache({ now: () => 0, ttlMs: 15_000 });
    const request = async () => {
      calls += 1;
      return calls;
    };

    await expect(cache.get('key', request)).resolves.toBe(1);
    cache.clear();
    await expect(cache.get('key', request)).resolves.toBe(2);

    expect(calls).toBe(2);
  });

  it('does not let a stale success overwrite a newer same-key request', async () => {
    let resolveOld!: (value: string) => void;
    let resolveNew!: (value: string) => void;
    const cache = createMemoryRequestCache({ now: () => 0, ttlMs: 15_000 });
    const old = cache.get(
      'key',
      () =>
        new Promise<string>(resolve => {
          resolveOld = resolve;
        })
    );

    cache.clear();
    const current = cache.get(
      'key',
      () =>
        new Promise<string>(resolve => {
          resolveNew = resolve;
        })
    );
    await Promise.resolve();
    resolveNew('new');
    await expect(current).resolves.toBe('new');
    resolveOld('old');
    await expect(old).resolves.toBe('old');

    await expect(cache.get('key', async () => 'unexpected')).resolves.toBe('new');
  });

  it('does not let a stale failure remove a newer same-key value', async () => {
    let rejectOld!: (error: Error) => void;
    const cache = createMemoryRequestCache({ now: () => 0, ttlMs: 15_000 });
    const old = cache.get(
      'key',
      () =>
        new Promise<string>((_, reject) => {
          rejectOld = reject;
        })
    );

    cache.clear();
    await expect(cache.get('key', async () => 'new')).resolves.toBe('new');
    await Promise.resolve();
    rejectOld(new Error('old failed'));
    await expect(old).rejects.toThrow('old failed');

    await expect(cache.get('key', async () => 'unexpected')).resolves.toBe('new');
  });

  it('preserves the previous value while a forced refresh is pending and after it fails', async () => {
    let rejectRefresh!: (error: Error) => void;
    const cache = createMemoryRequestCache({ now: () => 0, ttlMs: 15_000 });

    await expect(cache.get('key', async () => 'previous')).resolves.toBe('previous');
    const pending = cache.get(
      'key',
      () =>
        new Promise<string>((_, reject) => {
          rejectRefresh = reject;
        }),
      { force: true }
    );
    const duringRefresh = cache.get('key', async () => 'unexpected');

    expect(duringRefresh).toBe(pending);
    await Promise.resolve();
    rejectRefresh(new Error('refresh failed'));
    await expect(pending).rejects.toThrow('refresh failed');
    await expect(cache.get('key', async () => 'unexpected')).resolves.toBe('previous');
  });

  it('shares the outer Promise when a loader synchronously re-enters the same key', async () => {
    let outerCalls = 0;
    let innerPromise!: Promise<string>;
    const cache = createMemoryRequestCache({ now: () => 0, ttlMs: 15_000 });
    const request = () => {
      outerCalls += 1;
      innerPromise = cache.get('key', request);
      return Promise.resolve('loaded');
    };

    const outerPromise = cache.get('key', request);

    await Promise.resolve();
    expect(innerPromise).toBe(outerPromise);
    await expect(outerPromise).resolves.toBe('loaded');
    expect(outerCalls).toBe(1);
  });
});
