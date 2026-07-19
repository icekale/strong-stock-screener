import { describe, expect, it } from 'vitest';
import { productRoutes, resolveProductRoute } from './product-routes';

describe('product route table', () => {
  it('preserves the public workbench paths', () => {
    expect(productRoutes.filter(route => !route.meta?.hideInMenu).map(route => route.path)).toEqual([
      '/',
      '/screener',
      '/auction',
      '/market',
      '/etf-radar',
      '/watchlist',
      '/sentiment',
      '/chanlun',
      '/system'
    ]);
  });

  it('exposes the ETF capital radar as a top-level workbench route', () => {
    expect(productRoutes.find(route => route.path === '/etf-radar')).toMatchObject({
      name: 'etf-radar',
      component: 'layout.base$view.etf-radar',
      meta: {
        title: 'ETF资金雷达',
        icon: 'ant-design:radar-chart-outlined',
        order: 5,
        constant: true
      }
    });
  });

  it('resolves stock detail as a dynamic route', () => {
    expect(productRoutes.find(route => route.name === 'stock')?.path).toBe('/stock/:symbol');
  });

  it('keeps legacy paths as redirects', () => {
    expect(productRoutes.find(route => route.path === '/settings')?.redirect).toBe('/system?tab=data');
    expect(productRoutes.find(route => route.path === '/sectors')?.redirect).toBe('/market?view=sectors');
    expect(productRoutes.find(route => route.path === '/heatmap')?.redirect).toBe('/market?view=heatmap');
    expect(productRoutes.find(route => route.path === '/model-maintenance')?.redirect).toBe('/system?tab=model');
  });

  it('resolves exact route paths without duplicating navigation entries', () => {
    expect(resolveProductRoute('/auction')).toEqual({ name: 'auction', path: '/auction' });
    expect(resolveProductRoute('/unknown')).toBeNull();
  });
});
