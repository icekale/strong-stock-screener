import { beforeEach, describe, expect, expectTypeOf, it, vi } from 'vitest';
import {
  generateMarketSentimentAnalysis,
  getAuctionModelTop3,
  getCapitalSummary,
  getEtfActivityAlerts,
  getEtfRadarHistory,
  getEtfRadarHolders,
  getEtfRadarMethodology,
  getEtfRadarOverview,
  getEtfThreeFactor,
  getEtfThreeFactorHistory,
  getMarketSentimentAnalysis,
  getMarketSentimentPercentile,
  markAllEtfAlertsRead,
  markEtfAlertRead,
  getSectorReplicaRadar,
  getStockKline
} from './product-api';
import type { ApiRequestError } from './product-request';
import { apiRequest } from './product-request';
import type {
  CapitalSummaryResponse,
  EtfActivityAlert,
  EtfActivityAlertResponse,
  EtfActivityDirection,
  EtfAlertType,
  EtfFactorEvidence,
  EtfFactorStatus,
  EtfRadarHistoryPoint,
  EtfRadarHistoryResponse,
  EtfRadarHoldersResponse,
  EtfRadarOverviewResponse,
  EtfRadarSummary,
  EtfThreeFactorHistoryPoint,
  EtfThreeFactorHistoryResponse,
  EtfThreeFactorItem,
  EtfThreeFactorLevel,
  EtfThreeFactorMode,
  EtfThreeFactorResponse,
  EtfThreeFactorSummary,
  EtfValidationState,
  HuijinBaselineSourceKind,
  HuijinEtfActivityItem,
  HuijinEtfActivitySummary,
  HuijinEtfBaseline,
  HuijinEtfRole,
  HuijinEtfValidationGroup,
  SentimentPercentileAnalysisResponse,
  SentimentPercentilePoint,
  SentimentPercentileResponse
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

  it('requests ETF three-factor routes with encoded identifiers and exact request methods', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(() => Promise.resolve(new Response(JSON.stringify({}), { status: 200 })));

    await getEtfThreeFactor();
    await getEtfThreeFactorHistory('510050.SH', 40);
    await getEtfActivityAlerts(true);
    await markEtfAlertRead('alert/2026 07');
    await markAllEtfAlertsRead();

    expect(fetchMock.mock.calls.map(call => [String(call[0]), call[1]])).toEqual([
      [expect.stringContaining('/api/etf-radar/three-factor'), undefined],
      [expect.stringContaining('/api/etf-radar/three-factor/510050.SH/history?days=40'), undefined],
      [expect.stringContaining('/api/etf-radar/alerts?unread_only=true'), undefined],
      [
        expect.stringContaining('/api/etf-radar/alerts/alert%2F2026%2007/read'),
        expect.objectContaining({ method: 'POST' })
      ],
      [
        expect.stringContaining('/api/etf-radar/alerts/read-all'),
        expect.objectContaining({ method: 'POST' })
      ]
    ]);
  });

  it('requests sentiment percentile data and analysis with encoded query parameters', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(() => Promise.resolve(new Response(JSON.stringify({}), { status: 200 })));

    await getMarketSentimentPercentile('2026-07-22T15:10:00+08:00', true);
    await getMarketSentimentAnalysis('2026-07-22 / close');
    await generateMarketSentimentAnalysis('2026-07-22 / close', true);

    expect(fetchMock.mock.calls.map(call => [String(call[0]), call[1]])).toEqual([
      [
        expect.stringContaining(
          '/api/short-term/sentiment/percentile?refresh=true&as_of=2026-07-22T15%3A10%3A00%2B08%3A00'
        ),
        undefined
      ],
      [
        expect.stringContaining('/api/short-term/sentiment/percentile/analysis?trade_date=2026-07-22+%2F+close'),
        undefined
      ],
      [
        expect.stringContaining(
          '/api/short-term/sentiment/percentile/analysis/generate?trade_date=2026-07-22+%2F+close&force=true'
        ),
        expect.objectContaining({ method: 'POST' })
      ]
    ]);
  });

  it('keeps sentiment percentile contracts aligned with backend payloads', () => {
    const factor = {
      score: 72.5,
      raw_value: 1.25,
      raw_unit: '%'
    };
    const percentile = {
      trade_date: '2026-07-22',
      score: 68.2,
      level: '偏热',
      factors: {
        volume: factor,
        index_move_5d: factor,
        price_position: factor,
        amplitude_5d: factor,
        volume_trend: factor
      }
    } satisfies SentimentPercentilePoint;
    const response = {
      model_version: 'market-sentiment-percentile-v1',
      benchmark_symbol: '000985.SH',
      benchmark_name: '中证全指',
      window_size: 500,
      weights: {
        volume: 0.2,
        index_move_5d: 0.2,
        price_position: 0.2,
        amplitude_5d: 0.2,
        volume_trend: 0.2
      },
      latest_complete_trade_date: '2026-07-22',
      selected_trade_date: '2026-07-22',
      selected: percentile,
      history: [percentile],
      cache_status: 'fresh',
      source_status: [],
      generated_at: '2026-07-22T15:10:00+08:00',
      notes: []
    } satisfies SentimentPercentileResponse;
    const analysis = {
      trade_date: '2026-07-22',
      status: 'ready',
      model_version: 'market-sentiment-percentile-v1',
      provider: 'openai',
      llm_model: 'gpt-5',
      input_hash: 'abc123',
      attempts: 1,
      requested_at: '2026-07-22T15:10:00+08:00',
      completed_at: '2026-07-22T15:10:03+08:00',
      retry_after: null,
      error: null,
      result: {
        market_conclusion: '情绪偏热。',
        key_drivers: ['量能72.5分', '位置72.5分'],
        factor_divergence: '量能与波动同步抬升。',
        historical_context: '处于近500日偏高区间。',
        risk_posture: 'balanced',
        next_session_watch: ['留意68.2分是否回落', '观察量能72.5分延续'],
        risk_note: '高位波动可能放大。'
      }
    } satisfies SentimentPercentileAnalysisResponse;

    expect(response.selected?.factors.volume.raw_unit).toBe('%');
    expect(analysis.status).toBe('ready');
  });

  it('keeps ETF three-factor contracts aligned with backend payloads', () => {
    expectTypeOf<EtfThreeFactorMode>().toEqualTypeOf<'three_factor' | 'two_factor' | 'incomplete'>();
    expectTypeOf<EtfThreeFactorLevel>().toEqualTypeOf<'high' | 'medium' | 'low' | 'incomplete'>();
    expectTypeOf<EtfFactorStatus>().toEqualTypeOf<'available' | 'pending' | 'missing' | 'stale'>();
    expectTypeOf<EtfAlertType>().toEqualTypeOf<
      'single_high' | 'single_upgrade' | 'market_watch' | 'market_high'
    >();
    expectTypeOf<EtfFactorEvidence>().toEqualTypeOf<{
      score: number | null;
      value: number | null;
      status: EtfFactorStatus;
      source: string;
      data_date: string | null;
      updated_at: string | null;
      detail: string | null;
    }>();
    expectTypeOf<Pick<HuijinEtfActivityItem, 'close_change_pct' | 'close_change_trade_date'>>().toEqualTypeOf<{
      close_change_pct: number | null;
      close_change_trade_date: string | null;
    }>();

    const metadata = {
      generated_at: '2026-07-22T15:05:00+08:00',
      trade_date: '2026-07-22',
      as_of: '2026-07-22T15:05:00+08:00',
      signal_stage: 'post_close' as const,
      model_version: 'three-factor-v1',
      source_status: []
    };
    const factor = {
      score: null,
      value: null,
      status: 'pending',
      source: 'official-share-history',
      data_date: null,
      updated_at: null,
      detail: null
    } satisfies EtfFactorEvidence;
    const item = {
      symbol: '510050.SH',
      name: '华夏上证50ETF',
      index_name: '上证50',
      index_symbol: '000016.SH',
      close_change_pct: null,
      close_change_trade_date: null,
      intraday_change_pct: null,
      index_change_pct: null,
      current_volume: null,
      average_volume_20d: null,
      volume_ratio: null,
      share_change_pct: null,
      volume_factor: factor,
      direction_factor: factor,
      share_factor: factor,
      signal_score: null,
      mode: 'incomplete',
      level: 'incomplete',
      updated_at: '2026-07-22T15:05:00+08:00'
    } satisfies EtfThreeFactorItem;
    const summary = {
      signal_score: null,
      level: 'incomplete',
      valid_count: 0,
      high_count: 0,
      medium_count: 0,
      market_state: 'incomplete'
    } satisfies EtfThreeFactorSummary;
    const response = {
      ...metadata,
      summary,
      items: [item],
      monitor_running: false,
      last_scan_at: null
    } satisfies EtfThreeFactorResponse;
    const historyPoint = {
      trade_date: '2026-07-22',
      symbol: '510050.SH',
      close_change_pct: null,
      volume: null,
      average_volume_20d: null,
      volume_ratio: null,
      total_shares: null,
      share_change_pct: null,
      signal_score: null,
      level: 'incomplete'
    } satisfies EtfThreeFactorHistoryPoint;
    const history = {
      ...metadata,
      symbol: '510050.SH',
      points: [historyPoint]
    } satisfies EtfThreeFactorHistoryResponse;
    const alert = {
      alert_id: 'alert-1',
      trade_date: '2026-07-22',
      alert_type: 'single_high',
      level: 'high',
      symbol: null,
      title: 'ETF activity',
      message: 'Signal upgraded',
      signal_score: 82,
      triggered_at: '2026-07-22T15:05:00+08:00',
      last_triggered_at: '2026-07-22T15:05:00+08:00',
      evidence: { volume_ratio: 3, factor: 'volume', missing: null },
      read: false
    } satisfies EtfActivityAlert;
    const alerts = { unread_count: 1, alerts: [alert] } satisfies EtfActivityAlertResponse;

    expect(response.items[0]?.volume_factor.status).toBe('pending');
    expect(history.points[0]?.volume_ratio).toBeNull();
    expect(alerts.alerts[0]?.evidence.missing).toBeNull();
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
      close_change_pct: 1.25,
      close_change_trade_date: '2026-07-18',
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
