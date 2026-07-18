type CacheGetOptions = {
  force?: boolean;
};

type MemoryRequestCacheOptions = {
  now?: () => number;
  ttlMs: number;
};

type CacheEntry = {
  expiresAt: number;
  hasValue: boolean;
  promise?: Promise<unknown>;
  value?: unknown;
};

export function createMemoryRequestCache(options: MemoryRequestCacheOptions) {
  const entries = new Map<string, CacheEntry>();
  const now = options.now ?? Date.now;

  return {
    clear() {
      entries.clear();
    },

    get<T>(key: string, request: () => Promise<T>, getOptions: CacheGetOptions = {}) {
      const existing = entries.get(key);

      if (existing?.promise) {
        return existing.promise as Promise<T>;
      }

      if (existing?.hasValue && !getOptions.force && existing.expiresAt > now()) {
        return Promise.resolve(existing.value as T);
      }

      const entry: CacheEntry = existing?.hasValue ? existing : { expiresAt: 0, hasValue: false };
      entries.set(key, entry);

      const pending = Promise.resolve()
        .then(request)
        .then(
          value => {
            if (entries.get(key)?.promise === pending) {
              entry.value = value;
              entry.hasValue = true;
              entry.expiresAt = now() + options.ttlMs;
              entry.promise = undefined;
            }
            return value;
          },
          error => {
            if (entries.get(key)?.promise === pending) {
              entry.promise = undefined;
              if (!entry.hasValue) {
                entries.delete(key);
              }
            }
            throw error;
          }
        );

      entry.promise = pending;
      return pending;
    }
  };
}
