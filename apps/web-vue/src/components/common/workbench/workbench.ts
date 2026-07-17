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
