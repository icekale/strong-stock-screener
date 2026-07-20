import { beforeEach, describe, expect, expectTypeOf, it, vi } from 'vitest';
import {
  getAuctionModelTop3,
  getCapitalSummary,
  getEtfRadarHistory,
  getEtfRadarHolders,
  getEtfRadarMethodology,
  getEtfRadarOverview,
  getSectorReplicaRadar,
  getStockKline
} from './product-api';
import type { ApiRequestError } from './product-request';
import { apiRequest } from './product-request';
import type {
  CapitalSummaryResponse,
  EtfActivityDirection,
  EtfRadarHistoryPoint,
  EtfRadarHistoryResponse,
  EtfRadarHoldersResponse,
  EtfRadarOverviewResponse,
  EtfRadarSummary,
  EtfValidationState,
  HuijinBaselineSourceKind,
  HuijinEtfActivityItem,
  HuijinEtfActivitySummary,
  HuijinEtfBaseline,
  HuijinEtfRole,
  HuijinEtfValidationGroup
} from './types';

describe('apiRequest', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('requests a relative API path and parses JSON', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );

    await expect(apiRequest('/api/health')).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8010/api/health', undefined);
  });

  it('includes status and response body in failed requests', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{"detail":"down"}', { status: 503 }));

    await expect(apiRequest('/api/health')).rejects.toEqual(
      expect.objectContaining({ status: 503, body: '{"detail":"down"}' } satisfies Partial<ApiRequestError>)
    );
  });

  it('builds the cache-only Top3 request with the trade date', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ predictions: [] }), { status: 200 })
    );

    await getAuctionModelTop3('2026-07-16', { cacheOnly: true });

    expect(fetchMock.mock.calls[0]?.[0]).toContain(
      '/api/auction/model/top3?trade_date=2026-07-16&cache_only=true'
    );
  });

  it('encodes stock symbols and query parameters', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 })
    );

    await getStockKline('600000.SH', 120);

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/stocks/600000.SH/kline?count=120');
  });

  it('requests the selected stock kline period after count', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 })
    );

    await getStockKline('600000.SH', { count: 120, period: '30m' });

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      '/api/stocks/600000.SH/kline?count=120&period=30m'
    );
  });

  it('builds the sector replica radar request with dashboard defaults', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await getSectorReplicaRadar({ mode: 'strength', limit: 5, stockLimit: 1 });

    const requestUrl = new URL(String(fetchMock.mock.calls[0]?.[0]));
    expect(requestUrl.pathname).toBe('/api/sectors/replica/radar');
    expect(Array.from(requestUrl.searchParams.entries())).toEqual([
      ['mode', 'strength'],
      ['limit', '5'],
      ['stock_limit', '1']
    ]);
  });

  it('requests all capital radar endpoints and preserves the history days query', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(() => Promise.resolve(new Response(JSON.stringify({}), { status: 200 })));

    await getCapitalSummary();
    await getEtfRadarOverview();
    await getEtfRadarHistory();
    await getEtfRadarHistory(45);
    await getEtfRadarHolders();
    await getEtfRadarMethodology();

    expect(fetchMock.mock.calls.map(call => new URL(String(call[0])))).toEqual([
      expect.objectContaining({ pathname: '/api/market/capital-summary', port: '8010' }),
      expect.objectContaining({ pathname: '/api/etf-radar/overview', port: '8010' }),
      expect.objectContaining({ pathname: '/api/etf-radar/history', port: '8010', search: '?days=120' }),
      expect.objectContaining({ pathname: '/api/etf-radar/history', port: '8010', search: '?days=45' }),
      expect.objectContaining({ pathname: '/api/etf-radar/holders', port: '8010' }),
      expect.objectContaining({ pathname: '/api/etf-radar/methodology', port: '8010' })
    ]);
  });

  it('keeps Huijin ETF response contracts aligned with backend payloads', () => {
    expectTypeOf<HuijinEtfRole>().toEqualTypeOf<'core' | 'validator'>();
    expectTypeOf<EtfActivityDirection>().toEqualTypeOf<'increase' | 'decrease' | 'flat' | 'unknown'>();
    expectTypeOf<EtfValidationState>().toEqualTypeOf<
      'confirmed_increase' | 'confirmed_decrease' | 'divergent' | 'incomplete'
    >();
    expectTypeOf<HuijinBaselineSourceKind>().toEqualTypeOf<'reported' | 'derived'>();
    expectTypeOf<Pick<EtfRadarSummary, 'activity'>>().toEqualTypeOf<{
      activity: HuijinEtfActivitySummary;
    }>();
    expectTypeOf<
      Pick<
        EtfRadarOverviewResponse,
        | 'pool_version'
        | 'baseline_version'
        | 'baseline_fingerprint'
        | 'activity'
        | 'core_items'
        | 'validation_items'
        | 'validation_groups'
      >
    >().toEqualTypeOf<{
      pool_version: string;
      baseline_version: string | null;
      baseline_fingerprint: string | null;
      activity: HuijinEtfActivitySummary;
      core_items: HuijinEtfActivityItem[];
      validation_items: HuijinEtfActivityItem[];
      validation_groups: HuijinEtfValidationGroup[];
    }>();
    expectTypeOf<
      Pick<
        EtfRadarHistoryPoint,
        'daily_change_pct' | 'baseline_change_pct' | 'cumulative_baseline_change_pct' | 'multiple'
      >
    >().toEqualTypeOf<{
      daily_change_pct: number | null;
      baseline_change_pct: number | null;
      cumulative_baseline_change_pct: number | null;
      multiple: number | null;
    }>();
    expectTypeOf<Pick<EtfRadarHoldersResponse, 'baselines'>>().toEqualTypeOf<{
      baselines: HuijinEtfBaseline[];
    }>();
    expectTypeOf<Pick<HuijinEtfActivityItem, 'baseline_total_shares' | 'confirmed_huijin_shares'>>()
      .toEqualTypeOf<{
        baseline_total_shares: number | null;
        confirmed_huijin_shares: number | null;
      }>();

    const activity = {
      core_count: 7,
      available_core_count: 1,
      tenfold_increase_count: 1,
      tenfold_decrease_count: 0,
      confirmed_increase_group_count: 1,
      confirmed_decrease_group_count: 0,
      divergent_group_count: 0,
      incomplete_group_count: 6,
      strongest_symbol: '510300.SH',
      strongest_baseline_change_pct: 1.25
    } satisfies HuijinEtfActivitySummary;
    const activityItem = {
      symbol: '510300.SH',
      name: '沪深300ETF',
      index_name: '沪深300',
      role: 'core',
      paired_symbol: '510310.SH',
      trade_date: '2026-07-18',
      total_shares: 120,
      previous_total_shares: 110,
      share_delta: 10,
      daily_change_pct: 9.09,
      baseline_change_pct: 20,
      cumulative_baseline_change_pct: 20,
      multiple: 2,
      direction: 'increase',
      is_tenfold: false,
      report_period: '2026Q2',
      baseline_total_shares: 100,
      confirmed_huijin_shares: 75,
      confirmed_huijin_holding_pct: 75,
      baseline_source_kind: 'reported'
    } satisfies HuijinEtfActivityItem;
    const validationGroup = {
      index_name: '沪深300',
      core_symbol: '510300.SH',
      validator_symbol: '510310.SH',
      state: 'confirmed_increase',
      conservative_daily_change_pct: 1.5,
      conservative_baseline_change_pct: 2.5,
      conservative_multiple: 1.2
    } satisfies HuijinEtfValidationGroup;
    const baseline = {
      baseline_id: 'huijin-public-v1:2026Q2:510300.SH',
      pool_version: 'huijin-public-v1',
      symbol: '510300.SH',
      name: '沪深300ETF',
      index_name: '沪深300',
      role: 'core',
      paired_symbol: '510310.SH',
      report_period: '2026Q2',
      baseline_total_shares: 100,
      confirmed_huijin_shares: 75,
      confirmed_huijin_holding_pct: 75,
      source_kind: 'reported',
      source: 'fund-report'
    } satisfies HuijinEtfBaseline;
    const metadata = {
      generated_at: '2026-07-18T15:01:00+08:00',
      trade_date: '2026-07-18',
      as_of: '2026-07-18T15:00:00+08:00',
      signal_stage: 'post_close' as const,
      model_version: 'capital-signals-v1',
      source_status: []
    };
    const overview = {
      ...metadata,
      evidence_strength: 72.5,
      evidence_level: '观察',
      valid_etf_count: 1,
      expected_etf_count: 7,
      estimated_subscription_cny: 100_000_000,
      evidence: ['份额增加'],
      items: [
        {
          symbol: '510300.SH',
          name: '沪深300ETF',
          index_name: '沪深300',
          total_shares: 120,
          share_change: 10,
          estimated_subscription_cny: 100_000_000,
          robust_score: 72.5,
          same_time_turnover_ratio: 1.1,
          relative_index_return_pct: 0.5,
          late_session_acceleration: 0.2,
          evidence_strength: 72.5,
          evidence: ['份额增加']
        }
      ],
      pool_version: 'huijin-public-v1',
      baseline_version: '2026Q2',
      baseline_fingerprint: 'abc123',
      activity,
      core_items: [activityItem],
      validation_items: [{ ...activityItem, symbol: '510310.SH', role: 'validator' }],
      validation_groups: [validationGroup]
    } satisfies EtfRadarOverviewResponse;
    const history = {
      ...metadata,
      points: [
        {
          trade_date: '2026-07-18',
          symbol: '510300.SH',
          name: '沪深300ETF',
          total_shares: 120,
          share_change: 10,
          estimated_subscription_cny: 100_000_000,
          robust_score: 72.5,
          daily_change_pct: 9.09,
          baseline_change_pct: 20,
          cumulative_baseline_change_pct: 20,
          multiple: 2
        }
      ]
    } satisfies EtfRadarHistoryResponse;
    const holders = {
      ...metadata,
      positions: [
        {
          symbol: '510300.SH',
          name: '沪深300ETF',
          report_period: '2026Q2',
          entity_name: '中央汇金',
          shares: 75,
          holding_pct: 75,
          change_shares: 5,
          source: 'fund-report'
        }
      ],
      baselines: [baseline]
    } satisfies EtfRadarHoldersResponse;
    const capital = {
      ...metadata,
      margin: {
        balance_cny: 1,
        financing_balance_cny: 1,
        securities_lending_balance_cny: 0,
        financing_buy_cny: 1,
        change_cny: 0,
        change_pct: 0,
        available_markets: 2,
        expected_markets: 2
      },
      etf_radar: {
        evidence_strength: 72.5,
        evidence_level: '观察',
        valid_etf_count: 1,
        expected_etf_count: 7,
        estimated_subscription_cny: 100_000_000,
        evidence: ['份额增加'],
        activity
      }
    } satisfies CapitalSummaryResponse;

    expect(overview.core_items[0]?.baseline_source_kind).toBe('reported');
    expect(history.points[0]?.cumulative_baseline_change_pct).toBe(20);
    expect(holders.baselines[0]?.baseline_id).toContain('510300.SH');
    expect(capital.etf_radar.activity.strongest_symbol).toBe('510300.SH');
  });
});
