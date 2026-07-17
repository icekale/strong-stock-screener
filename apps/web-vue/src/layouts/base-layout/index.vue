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
import { getLayoutGeometry, getSiderGeometry } from './layoutState';

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

const siderGeometry = computed(() =>
  getSiderGeometry({
    isVerticalMix: isVerticalMix.value,
    isHorizontalMix: isHorizontalMix.value,
    reverseHorizontalMix: themeStore.layout.reverseHorizontalMix,
    hasActiveFirstLevelMenuChildren: isActiveFirstLevelMenuHasChildren.value,
    width: themeStore.sider.width,
    collapsedWidth: themeStore.sider.collapsedWidth,
    mixWidth: themeStore.sider.mixWidth,
    mixCollapsedWidth: themeStore.sider.mixCollapsedWidth,
    mixChildMenuWidth: themeStore.sider.mixChildMenuWidth,
    mixSiderFixed: appStore.mixSiderFixed,
    hasChildMenus: childLevelMenus.value.length > 0
  })
);

const layoutGeometry = computed(() =>
  getLayoutGeometry({
    siderWidth: siderGeometry.value.siderWidth,
    siderCollapsedWidth: siderGeometry.value.siderCollapsedWidth,
    tabHeight: themeStore.tab.height,
    fullContent: appStore.fullContent,
    footerVisible: themeStore.footer.visible,
    fixedFooter: themeStore.footer.fixed,
    footerHeight: themeStore.footer.height
  })
);

const contentClass = computed(() =>
  ['base-layout-content', appStore.contentXScrollable ? 'overflow-x-hidden' : ''].filter(Boolean).join(' ')
);
</script>

<template>
  <AdminLayout
    v-model:sider-collapse="appStore.siderCollapse"
    :mode="layoutMode"
    :scroll-el-id="LAYOUT_SCROLL_EL_ID"
    :scroll-mode="themeStore.layout.scrollMode"
    :is-mobile="appStore.isMobile"
    :full-content="appStore.fullContent"
    :fixed-top="themeStore.fixedHeaderAndTab"
    :header-height="themeStore.header.height"
    :tab-visible="themeStore.tab.visible"
    :tab-height="layoutGeometry.tabHeight"
    :content-class="contentClass"
    :sider-visible="siderVisible"
    :sider-width="layoutGeometry.siderWidth"
    :sider-collapsed-width="layoutGeometry.siderCollapsedWidth"
    :footer-visible="themeStore.footer.visible"
    :footer-height="themeStore.footer.height"
    :fixed-footer="themeStore.footer.fixed"
    :right-footer="themeStore.footer.right"
    :style="{ '--wb-content-bottom-padding': `${layoutGeometry.contentBottomPadding}px` }"
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
