type CacheEntry<T> = {
  expiresAt: number;
  hasValue: boolean;
  promise?: Promise<T>;
  value?: T;
};

export type MemoryRequestCache = {
  clear: () => void;
  get: <T>(key: string, request: () => T | PromiseLike<T>, options?: { force?: boolean }) => Promise<T>;
};

export function createMemoryRequestCache({
  now = Date.now,
  ttlMs = 15_000,
}: {
  now?: () => number;
  ttlMs?: number;
} = {}): MemoryRequestCache {
  const entries = new Map<string, CacheEntry<unknown>>();

  function get<T>(
    key: string,
    request: () => T | PromiseLike<T>,
    options: { force?: boolean } = {},
  ): Promise<T> {
    const existing = entries.get(key) as CacheEntry<T> | undefined;
    const currentTime = now();
    const hasFreshValue = existing?.hasValue === true && existing.expiresAt > currentTime;

    if (!options.force && hasFreshValue) {
      return Promise.resolve(existing.value as T);
    }
    if (!options.force && existing?.promise) {
      return existing.promise;
    }

    const previous = hasFreshValue
      ? {
          expiresAt: existing.expiresAt,
          hasValue: true,
          value: existing.value,
        }
      : undefined;

    const promise = Promise.resolve()
      .then(request)
      .then(
        (value) => {
          const current = entries.get(key);
          if (current?.promise === promise) {
            entries.set(key, { expiresAt: now() + ttlMs, hasValue: true, value });
          }
          return value;
        },
        (reason: unknown) => {
          const current = entries.get(key);
          if (current?.promise === promise) {
            if (previous) {
              entries.set(key, previous);
            } else {
              entries.delete(key);
            }
          }
          throw reason;
        },
      );

    entries.set(key, {
      ...(previous ?? { expiresAt: 0, hasValue: false }),
      promise,
    });
    return promise;
  }

  return { clear: () => entries.clear(), get };
}
