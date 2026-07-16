import { describe, expect, it } from 'vitest';
import { productRoutes, resolveProductRoute } from './product-routes';

describe('product route table', () => {
  it('preserves the public workbench paths', () => {
    expect(productRoutes.filter(route => !route.meta?.hideInMenu).map(route => route.path)).toEqual([
      '/',
      '/screener',
      '/auction',
      '/market',
      '/watchlist',
      '/sentiment',
      '/chanlun',
      '/system'
    ]);
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
