<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue';
import { AdminLayout, LAYOUT_SCROLL_EL_ID } from '@sa/materials';
import type { LayoutMode } from '@sa/materials';
import { useAppStore } from '@/store/modules/app';
import { useThemeStore } from '@/store/modules/theme';
import GlobalHeader from '../modules/global-header/index.vue';
import GlobalSider from '../modules/global-sider/index.vue';
import GlobalTab from '../modules/global-tab/index.vue';
import GlobalContent from '../modules/global-content/index.vue';
import GlobalFooter from '../modules/global-footer/index.vue';
import ThemeDrawer from '../modules/theme-drawer/index.vue';
import { setupMixMenuContext } from '../context';
import {
  getContentBottomPadding,
  WORKBENCH_SIDER_COLLAPSED_WIDTH,
  WORKBENCH_SIDER_WIDTH
} from './layoutState';

defineOptions({
  name: 'BaseLayout'
});

const appStore = useAppStore();
const themeStore = useThemeStore();
const { childLevelMenus, isActiveFirstLevelMenuHasChildren } = setupMixMenuContext();

const GlobalMenu = defineAsyncComponent(() => import('../modules/global-menu/index.vue'));

const layoutMode = computed(() => {
  const vertical: LayoutMode = 'vertical';
  const horizontal: LayoutMode = 'horizontal';
  return themeStore.layout.mode.includes(vertical) ? vertical : horizontal;
});

const headerProps = computed(() => {
  const { mode, reverseHorizontalMix } = themeStore.layout;

  const headerPropsConfig: Record<UnionKey.ThemeLayoutMode, App.Global.HeaderProps> = {
    vertical: {
      showLogo: false,
      showMenu: false,
      showMenuToggler: true
    },
    'vertical-mix': {
      showLogo: false,
      showMenu: false,
      showMenuToggler: false
    },
    horizontal: {
      showLogo: true,
      showMenu: true,
      showMenuToggler: false
    },
    'horizontal-mix': {
      showLogo: true,
      showMenu: true,
      showMenuToggler: reverseHorizontalMix && isActiveFirstLevelMenuHasChildren.value
    }
  };

  return headerPropsConfig[mode];
});

const siderVisible = computed(() => themeStore.layout.mode !== 'horizontal');

const isVerticalMix = computed(() => themeStore.layout.mode === 'vertical-mix');

const isHorizontalMix = computed(() => themeStore.layout.mode === 'horizontal-mix');

const siderWidth = computed(() => getSiderWidth());

const siderCollapsedWidth = computed(() => getSiderCollapsedWidth());

const tabHeight = computed(() => Math.min(Math.max(themeStore.tab.height, 36), 40));

const contentBottomPadding = computed(() =>
  getContentBottomPadding({
    fixedFooter: themeStore.footer.fixed,
    footerHeight: themeStore.footer.height
  })
);

const contentClass = computed(() =>
  ['base-layout-content', appStore.contentXScrollable ? 'overflow-x-hidden' : ''].filter(Boolean).join(' ')
);

function getSiderWidth() {
  const { reverseHorizontalMix } = themeStore.layout;
  const { mixWidth, mixChildMenuWidth } = themeStore.sider;

  if (isHorizontalMix.value && reverseHorizontalMix) {
    return isActiveFirstLevelMenuHasChildren.value ? WORKBENCH_SIDER_WIDTH : 0;
  }

  let w = isVerticalMix.value || isHorizontalMix.value ? mixWidth : WORKBENCH_SIDER_WIDTH;

  if (isVerticalMix.value && appStore.mixSiderFixed && childLevelMenus.value.length) {
    w += mixChildMenuWidth;
  }

  return w;
}

function getSiderCollapsedWidth() {
  const { reverseHorizontalMix } = themeStore.layout;
  const { mixCollapsedWidth, mixChildMenuWidth } = themeStore.sider;

  if (isHorizontalMix.value && reverseHorizontalMix) {
    return isActiveFirstLevelMenuHasChildren.value ? WORKBENCH_SIDER_COLLAPSED_WIDTH : 0;
  }

  let w = isVerticalMix.value || isHorizontalMix.value ? mixCollapsedWidth : WORKBENCH_SIDER_COLLAPSED_WIDTH;

  if (isVerticalMix.value && appStore.mixSiderFixed && childLevelMenus.value.length) {
    w += mixChildMenuWidth;
  }

  return w;
}
</script>

<template>
  <AdminLayout
    class="base-layout-shell"
    v-model:sider-collapse="appStore.siderCollapse"
    :mode="layoutMode"
    :scroll-el-id="LAYOUT_SCROLL_EL_ID"
    :scroll-mode="themeStore.layout.scrollMode"
    :is-mobile="appStore.isMobile"
    :full-content="appStore.fullContent"
    :fixed-top="themeStore.fixedHeaderAndTab"
    :header-height="themeStore.header.height"
    header-class="base-layout-header-placement"
    :tab-visible="themeStore.tab.visible"
    :tab-height="tabHeight"
    tab-class="base-layout-tab-placement"
    :content-class="contentClass"
    :sider-visible="siderVisible"
    :sider-width="siderWidth"
    :sider-collapsed-width="siderCollapsedWidth"
    sider-class="base-layout-sider-placement"
    :footer-visible="themeStore.footer.visible"
    :footer-height="themeStore.footer.height"
    :fixed-footer="themeStore.footer.fixed"
    :right-footer="themeStore.footer.right"
    footer-class="base-layout-footer"
    :style="{ '--wb-content-bottom-padding': `${contentBottomPadding}px` }"
  >
    <template #header>
      <GlobalHeader v-bind="headerProps" />
    </template>
    <template #tab>
      <GlobalTab />
    </template>
    <template #sider>
      <GlobalSider />
    </template>
    <GlobalMenu />
    <GlobalContent />
    <ThemeDrawer />
    <template #footer>
      <GlobalFooter />
    </template>
  </AdminLayout>
</template>

<style lang="scss">
#__SCROLL_EL_ID__ {
  @include scrollbar();
}

.base-layout-content {
  padding-bottom: var(--wb-content-bottom-padding, 24px);
}
</style>
