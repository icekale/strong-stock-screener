import type { RouteComponent } from 'vue-router';
import type { RouteLayout } from '@elegant-router/types';

import BaseLayout from '@/layouts/base-layout/index.vue';
import BlankLayout from '@/layouts/blank-layout/index.vue';

export const layouts: Record<RouteLayout, RouteComponent | (() => Promise<RouteComponent>)> = {
  base: BaseLayout,
  blank: BlankLayout
};

export const views: Record<string, RouteComponent | (() => Promise<RouteComponent>)> = {
  403: () => import('@/views/_builtin/403/index.vue'),
  404: () => import('@/views/_builtin/404/index.vue'),
  500: () => import('@/views/_builtin/500/index.vue'),
  home: () => import('@/views/WorkspacePlaceholder.vue'),
  screener: () => import('@/views/WorkspacePlaceholder.vue'),
  auction: () => import('@/views/WorkspacePlaceholder.vue'),
  market: () => import('@/views/WorkspacePlaceholder.vue'),
  stock: () => import('@/views/WorkspacePlaceholder.vue'),
  watchlist: () => import('@/views/WorkspacePlaceholder.vue'),
  sentiment: () => import('@/views/WorkspacePlaceholder.vue'),
  chanlun: () => import('@/views/WorkspacePlaceholder.vue'),
  system: () => import('@/views/WorkspacePlaceholder.vue')
};
