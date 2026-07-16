import { describe, expect, it } from 'vitest';
import type { MarketEmotionSnapshotResponse } from '@/service/types';
import { buildMarketEmotionTrend } from './marketOverviewTrend';

function snapshot(): MarketEmotionSnapshotResponse {
  return {
    trade_date: '2026-07-16',
    metrics: {
      emotion_score: 52,
      emotion_level: '良好',
      limit_up_count: 80,
      limit_down_count: 4,
      advance_count: 3000,
      decline_count: 2000,
      break_board_count: 0,
      losing_effect_score: null,
      max_consecutive_boards: 3,
      seal_rate_pct: null,
      turnover_cny: null,
      turnover_change_cny: null,
      turnover_change_pct: null,
      main_flow_cny: null,
      yesterday_limit_up_performance_pct: null,
      yesterday_ladder_performance_pct: null
    },
    buckets: [],
    samples: [
      {
        trade_date: '2026-07-16',
        sampled_at: '2026-07-16T10:00:00+08:00',
        emotion_score: 52,
        emotion_level: '良好',
        limit_up_count: 80,
        break_board_count: 0,
        limit_down_count: 4,
        losing_effect_score: null,
        max_consecutive_boards: 3,
        advance_count: 3000,
        decline_count: 2000,
        seal_rate_pct: null,
        turnover_cny: null,
        turnover_change_pct: null
      }
    ],
    source_status: [],
    notes: [],
    generated_at: '2026-07-16T10:00:00+08:00'
  };
}

describe('marketOverviewTrend', () => {
  it('builds a readable intraday point and breadth percentage', () => {
    const trend = buildMarketEmotionTrend(snapshot());

    expect(trend.times).toEqual(['10:00']);
    expect(trend.emotion).toEqual([52]);
    expect(trend.breadth).toEqual([60]);
  });
});
