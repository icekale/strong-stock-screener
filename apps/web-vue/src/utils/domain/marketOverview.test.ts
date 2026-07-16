import { describe, expect, it } from 'vitest';
import type { SectorRadarItem } from '@/service/types';
import { buildSectorFlowRows, getAuctionCacheTradeDate, marketBreadthPercent } from './marketOverview';

const sector = (name: string, netFlow: number | null): SectorRadarItem => ({
  name,
  source: 'test',
  change_pct: null,
  turnover_cny: null,
  advance_count: null,
  decline_count: null,
  leader: null,
  net_flow_cny: netFlow,
  strength_score: 0
});

describe('marketOverview', () => {
  it('normalizes sector flow widths and drops missing values', () => {
    expect(buildSectorFlowRows([sector('A', 100), sector('B', null), sector('C', -50)])).toEqual([
      { item: sector('A', 100), widthPercent: 100 },
      { item: sector('C', -50), widthPercent: 50 }
    ]);
  });

  it('calculates breadth from advancing and declining stocks', () => {
    expect(marketBreadthPercent(3, 1)).toBe(75);
    expect(marketBreadthPercent(null, 1)).toBe(0);
  });

  it('uses the previous Friday for a weekend auction cache date', () => {
    expect(getAuctionCacheTradeDate(new Date('2026-07-11T04:00:00.000Z'))).toBe('2026-07-10');
  });
});
