import { describe, expect, it } from 'vitest';
import { buildStockDetailHref, resolveStockDetailContext } from './stockNavigation';

describe('stockNavigation', () => {
  it('preserves the originating workbench when opening a stock', () => {
    expect(buildStockDetailHref('603823.SH', { from: 'auction', name: '百合花', industry: '化学制品' })).toContain(
      '/stock/603823.SH?from=auction'
    );
  });

  it('returns unknown origins to the product home page', () => {
    expect(resolveStockDetailContext(new URLSearchParams('from=https://example.com')).returnHref).toBe('/');
  });
});
