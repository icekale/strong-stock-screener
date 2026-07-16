import type { ElegantConstRoute, ElegantRoute } from '@elegant-router/types';
import { layouts, views } from '../elegant/imports';
import { transformElegantRoutesToVueRoutes } from '../elegant/transform';
import { productRoutes } from '../product-routes';

export function createStaticRoutes() {
  return {
    constantRoutes: productRoutes as ElegantRoute[],
    authRoutes: [] as ElegantRoute[]
  };
}

export function getAuthVueRoutes(routes: ElegantConstRoute[]) {
  return transformElegantRoutesToVueRoutes(routes, layouts, views);
}
