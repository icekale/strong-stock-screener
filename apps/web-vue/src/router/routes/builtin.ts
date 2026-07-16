import type { ElegantConstRoute } from '@elegant-router/types';
import { layouts, views } from '../elegant/imports';
import { transformElegantRoutesToVueRoutes } from '../elegant/transform';
import { productRoutes } from '../product-routes';

export const ROOT_ROUTE = productRoutes[0] as ElegantConstRoute;

const NOT_FOUND_ROUTE: ElegantConstRoute = {
  name: 'not-found',
  path: '/:pathMatch(.*)*',
  component: 'layout.blank$view.404',
  meta: { title: '页面不存在', constant: true }
};

export function createBuiltinVueRoutes() {
  return transformElegantRoutesToVueRoutes([NOT_FOUND_ROUTE], layouts, views);
}
