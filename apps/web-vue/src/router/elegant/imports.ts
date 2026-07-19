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
  home: () => import('@/views/HomeView.vue'),
  screener: () => import('@/views/ScreenerView.vue'),
  auction: () => import('@/views/AuctionView.vue'),
  market: () => import('@/views/MarketView.vue'),
  'etf-radar': () => import('@/views/EtfRadarView.vue'),
  etf_radar: () => import('@/views/EtfRadarView.vue'),
  stock: () => import('@/views/StockView.vue'),
  watchlist: () => import('@/views/WatchlistView.vue'),
  sentiment: () => import('@/views/SentimentView.vue'),
  chanlun: () => import('@/views/ChanlunView.vue'),
  system: () => import('@/views/SystemView.vue')
};
