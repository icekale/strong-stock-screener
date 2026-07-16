import type { ElegantConstRoute } from '@elegant-router/types';

export const productRoutes: ElegantConstRoute[] = [
  {
    name: 'root',
    path: '/',
    component: 'layout.base$view.home',
    meta: { title: '市场总览', icon: 'ant-design:dashboard-outlined', order: 1, constant: true, fixedIndexInTab: 0 }
  },
  {
    name: 'screener',
    path: '/screener',
    component: 'layout.base$view.screener',
    meta: { title: '强势选股', icon: 'ant-design:bar-chart-outlined', order: 2, constant: true }
  },
  {
    name: 'auction',
    path: '/auction',
    component: 'layout.base$view.auction',
    meta: { title: '竞价雷达', icon: 'ant-design:rise-outlined', order: 3, constant: true }
  },
  {
    name: 'market',
    path: '/market',
    component: 'layout.base$view.market',
    meta: { title: '板块与热图', icon: 'ant-design:line-chart-outlined', order: 4, constant: true }
  },
  {
    name: 'stock',
    path: '/stock/:symbol',
    component: 'layout.base$view.stock',
    props: true,
    meta: { title: '个股详情', icon: 'ant-design:fund-outlined', constant: true, hideInMenu: true, activeMenu: 'market' }
  },
  {
    name: 'watchlist',
    path: '/watchlist',
    component: 'layout.base$view.watchlist',
    meta: { title: '自选与风险', icon: 'ant-design:folder-open-outlined', order: 5, constant: true }
  },
  {
    name: 'sentiment',
    path: '/sentiment',
    component: 'layout.base$view.sentiment',
    meta: { title: '情绪与复盘', icon: 'ant-design:thunderbolt-outlined', order: 6, constant: true }
  },
  {
    name: 'chanlun',
    path: '/chanlun',
    component: 'layout.base$view.chanlun',
    meta: { title: '缠论工作台', icon: 'ant-design:fund-outlined', order: 7, constant: true }
  },
  {
    name: 'system',
    path: '/system',
    component: 'layout.base$view.system',
    meta: { title: '模型与数据源', icon: 'ant-design:setting-outlined', order: 8, constant: true }
  },
  {
    name: 'settings',
    path: '/settings',
    redirect: '/system?tab=data',
    meta: { title: '数据源配置', constant: true, hideInMenu: true }
  },
  {
    name: 'sectors',
    path: '/sectors',
    redirect: '/market?view=sectors',
    meta: { title: '板块雷达', constant: true, hideInMenu: true }
  },
  {
    name: 'heatmap',
    path: '/heatmap',
    redirect: '/market?view=heatmap',
    meta: { title: '市场热图', constant: true, hideInMenu: true }
  },
  {
    name: 'model-maintenance',
    path: '/model-maintenance',
    redirect: '/system?tab=model',
    meta: { title: '模型维护', constant: true, hideInMenu: true }
  }
];

export function resolveProductRoute(pathname: string): { name: string; path: string } | null {
  const route = productRoutes.find(item => item.path === pathname);

  return route ? { name: route.name, path: route.path } : null;
}
