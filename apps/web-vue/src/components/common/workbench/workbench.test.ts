import { describe, expect, it } from 'vitest';
import { formatWorkbenchNumber, normalizeWorkbenchStatus } from './workbench';

describe('normalizeWorkbenchStatus', () => {
  it.each([
    ['success', { label: '成功', tone: 'success' }],
    ['failed', { label: '失败', tone: 'error' }],
    ['partial', { label: '部分', tone: 'warning' }],
    ['unknown', { label: '待确认', tone: 'neutral' }]
  ] as const)('maps %s to a visible label and tone', (status, expected) => {
    expect(normalizeWorkbenchStatus(status)).toEqual(expected);
  });
});

describe('formatWorkbenchNumber', () => {
  it('rounds prices to two decimal places', () => {
    expect(formatWorkbenchNumber(8.870000000000001, 'price')).toBe('8.87');
  });

  it('formats large money values in Chinese units', () => {
    expect(formatWorkbenchNumber(258000000000, 'money')).toBe('2.58万亿');
  });

  it('renders missing values as a placeholder', () => {
    expect(formatWorkbenchNumber(null, 'price')).toBe('--');
  });
});
