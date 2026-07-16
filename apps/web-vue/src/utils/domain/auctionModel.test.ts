import { describe, expect, it } from 'vitest';
import type { AuctionModelPredictionItem } from '@/service/types';
import {
  auctionModelBucketLabel,
  selectAuctionModelPreviewItems
} from './auctionModel';

function item(symbol: string, overrides: Partial<AuctionModelPredictionItem> = {}): AuctionModelPredictionItem {
  return {
    symbol,
    name: symbol,
    prob_3pct: 0.5,
    bucket: 'watch',
    rank: null,
    prev_close_price: null,
    market_cap_float: null,
    avg_amount_3d: null,
    feature_end_date: null,
    guard_rule: null,
    strategy_note: null,
    trend_reasons: [],
    risk_flags: [],
    data_quality: [],
    ...overrides
  };
}

describe('auctionModel', () => {
  it('orders selected candidates before lower-priority buckets', () => {
    const result = selectAuctionModelPreviewItems([
      item('watch', { bucket: 'watch', rank: 1 }),
      item('selected-2', { bucket: 'selected', rank: 2 }),
      item('selected-1', { bucket: 'selected', rank: 1 })
    ]);

    expect(result.map(entry => entry.symbol)).toEqual(['selected-1', 'selected-2', 'watch']);
  });

  it('keeps product labels stable', () => {
    expect(auctionModelBucketLabel('selected')).toBe('Top3试运行');
  });
});
