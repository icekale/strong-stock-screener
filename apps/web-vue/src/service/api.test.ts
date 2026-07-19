import { beforeEach, describe, expect, it, vi } from 'vitest';
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
});
