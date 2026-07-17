export type WorkbenchStatusTone = 'success' | 'error' | 'warning' | 'info' | 'neutral';

export type WorkbenchStatus = {
  label: string;
  tone: WorkbenchStatusTone;
};

export type WorkbenchNumberKind = 'price' | 'money' | 'percent';

export type WorkbenchMetricTone = WorkbenchStatusTone | 'positive' | 'negative';

export type WorkbenchItemKey = string | number | symbol;

export type WorkbenchItemKeyResolver = (item: unknown, index: number) => WorkbenchItemKey;

export type WorkbenchMetric = {
  key: string;
  label: string;
  value: string | number | null | undefined;
  helper?: string;
  tone?: WorkbenchMetricTone;
};

export function createWorkbenchItemKeyResolver() {
  const objectIdentityBases = new WeakMap<object, symbol>();
  const objectDuplicateSuffixes = new WeakMap<object, Map<WorkbenchItemKey, number>>();
  const nextSuffixByBase = new Map<WorkbenchItemKey, number>();

  function getBaseKey(item: unknown, index: number, itemKey?: WorkbenchItemKeyResolver): WorkbenchItemKey {
    const resolvedKey = itemKey?.(item, index);
    if (resolvedKey !== undefined) return resolvedKey;

    if (item !== null && typeof item === 'object') {
      const record = item as Record<string, unknown>;

      for (const field of ['key', 'id', 'code', 'symbol']) {
        const value = record[field];
        if (typeof value === 'string' || typeof value === 'number' || typeof value === 'symbol') return value;
      }

      const identityBase = objectIdentityBases.get(item);
      if (identityBase) return identityBase;

      const generatedBase = Symbol('workbench-item');
      objectIdentityBases.set(item, generatedBase);
      return generatedBase;
    }

    if (typeof item === 'string' || typeof item === 'number' || typeof item === 'symbol') return item;

    return `${typeof item}:${String(item)}`;
  }

  function getObjectDuplicateSuffix(
    item: object,
    baseKey: WorkbenchItemKey,
    isAvailable: (key: WorkbenchItemKey) => boolean
  ) {
    let suffixes = objectDuplicateSuffixes.get(item);
    if (!suffixes) {
      suffixes = new Map();
      objectDuplicateSuffixes.set(item, suffixes);
    }

    let suffix = suffixes.get(baseKey) ?? (nextSuffixByBase.get(baseKey) ?? 0) + 1;

    while (!isAvailable(formatDuplicateKey('object', baseKey, suffix))) suffix += 1;

    nextSuffixByBase.set(baseKey, Math.max(nextSuffixByBase.get(baseKey) ?? 0, suffix));
    suffixes.set(baseKey, suffix);
    return suffix;
  }

  function formatDuplicateKey(kind: 'object' | 'value', baseKey: WorkbenchItemKey, suffix: number) {
    return `${kind}:${typeof baseKey}:${String(baseKey)}:${suffix}`;
  }

  return (items: unknown[], itemKey?: WorkbenchItemKeyResolver): WorkbenchItemKey[] => {
    const baseKeys = items.map((item, index) => getBaseKey(item, index, itemKey));
    const baseCounts = new Map<WorkbenchItemKey, number>();

    baseKeys.forEach(baseKey => {
      baseCounts.set(baseKey, (baseCounts.get(baseKey) ?? 0) + 1);
    });

    const rawKeys = new Set(baseKeys);
    const finalKeys = new Set<WorkbenchItemKey>();
    const isAvailable = (key: WorkbenchItemKey) => !rawKeys.has(key) && !finalKeys.has(key);
    const valueOccurrences = new Map<WorkbenchItemKey, number>();
    const objectOccurrences = new Map<object, number>();

    return baseKeys.map((baseKey, index) => {
      if (baseCounts.get(baseKey) === 1) {
        finalKeys.add(baseKey);
        return baseKey;
      }

      const item = items[index];
      if (item !== null && typeof item === 'object') {
        const objectOccurrence = objectOccurrences.get(item) ?? 0;
        objectOccurrences.set(item, objectOccurrence + 1);

        if (objectOccurrence === 0) {
          const suffix = getObjectDuplicateSuffix(item, baseKey, isAvailable);
          const finalKey = formatDuplicateKey('object', baseKey, suffix);
          finalKeys.add(finalKey);
          return finalKey;
        }
      }

      let valueOccurrence = (valueOccurrences.get(baseKey) ?? 0) + 1;
      let finalKey = formatDuplicateKey('value', baseKey, valueOccurrence);

      while (!isAvailable(finalKey)) {
        valueOccurrence += 1;
        finalKey = formatDuplicateKey('value', baseKey, valueOccurrence);
      }

      valueOccurrences.set(baseKey, valueOccurrence);
      finalKeys.add(finalKey);
      return finalKey;
    });
  };
}

export function normalizeWorkbenchStatus(value: unknown): WorkbenchStatus {
  if (value === 'success') return { label: '成功', tone: 'success' };
  if (value === 'failed') return { label: '失败', tone: 'error' };
  if (value === 'partial') return { label: '部分', tone: 'warning' };
  if (value === 'running') return { label: '运行中', tone: 'info' };

  return { label: '待确认', tone: 'neutral' };
}

export function formatWorkbenchNumber(value: number | null | undefined, kind: WorkbenchNumberKind): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';

  if (kind === 'price') return value.toFixed(2);
  if (kind === 'percent') return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;

  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';

  if (abs >= 1_000_000_000_000) return `${sign}${(abs / 1_000_000_000_000).toFixed(2)}万亿`;
  if (abs >= 100_000_000) return `${sign}${(abs / 100_000_000).toFixed(2)}亿`;
  if (abs >= 10_000) return `${sign}${(abs / 10_000).toFixed(2)}万`;

  return value.toFixed(0);
}
