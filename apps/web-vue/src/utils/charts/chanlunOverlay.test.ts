import { describe, expect, it } from 'vitest';
import { resolveChartDate, resolveVisibleBarCount } from './chanlunOverlay';

describe('chanlunOverlay', () => {
  it('maps compact backend dates to the chart axis', () => {
    expect(resolveChartDate('20260716', ['2026-07-15', '2026-07-16'])).toBe('2026-07-16');
  });

  it('calculates visible bars from the zoom range', () => {
    expect(resolveVisibleBarCount(200, { start: 25, end: 75 })).toBe(100);
  });
});
