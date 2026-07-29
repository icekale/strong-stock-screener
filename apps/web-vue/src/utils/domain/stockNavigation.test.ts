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

  it('returns legacy heatmap links to the sector radar', () => {
    const context = resolveStockDetailContext(new URLSearchParams('from=heatmap'));

    expect(context.returnHref).toBe('/market');
    expect(context.returnLabel).toBe('返回板块雷达');
  });
});
