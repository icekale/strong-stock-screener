import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getAuctionModelTop3, getStockKline } from './product-api';
import { ApiRequestError, apiRequest } from './product-request';

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
});
