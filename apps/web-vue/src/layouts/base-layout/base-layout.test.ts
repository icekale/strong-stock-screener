// @vitest-environment jsdom

import { defineComponent, h } from 'vue';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';
import { router } from '@/router';
import { useAppStore } from '@/store/modules/app';
import { useThemeStore } from '@/store/modules/theme';
import { themeSettings } from '@/theme/settings';
import BaseLayout from './index.vue';
import { getContentBottomPadding, getLayoutGeometry, getSiderGeometry } from './layoutState';

const AdminLayoutStub = defineComponent({
  name: 'AdminLayout',
  props: {
    contentClass: String,
    fixedFooter: Boolean,
    footerVisible: Boolean,
    siderCollapsedWidth: Number,
    siderWidth: Number,
    tabHeight: Number
  },
  setup(props, { slots }) {
    return () => h('div', { class: props.contentClass }, slots.default?.());
  }
});

describe('base layout state', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('reserves fixed footer space only when the footer is visible', () => {
    expect(getContentBottomPadding({ fullContent: false, footerVisible: true, fixedFooter: true, footerHeight: 48 })).toBe(
      72
    );
    expect(
      getContentBottomPadding({ fullContent: false, footerVisible: true, fixedFooter: false, footerHeight: 48 })
    ).toBe(24);
    expect(getContentBottomPadding({ fullContent: false, footerVisible: false, fixedFooter: true, footerHeight: 48 })).toBe(
      24
    );
    expect(getContentBottomPadding({ fullContent: true, footerVisible: true, fixedFooter: true, footerHeight: 48 })).toBe(
      24
    );
  });

  it('keeps configured regular sider dimensions in the consumed geometry', () => {
    const geometry = getSiderGeometry({
      isVerticalMix: false,
      isHorizontalMix: false,
      reverseHorizontalMix: false,
      hasActiveFirstLevelMenuChildren: false,
      width: 232,
      collapsedWidth: 72,
      mixWidth: 90,
      mixCollapsedWidth: 64,
      mixChildMenuWidth: 200,
      mixSiderFixed: false,
      hasChildMenus: false
    });

    expect(geometry).toEqual({ siderWidth: 232, siderCollapsedWidth: 72 });
  });

  it('passes configured tab and sider values through while honoring footer visibility', () => {
    expect(
      getLayoutGeometry({
        siderWidth: 232,
        siderCollapsedWidth: 72,
        tabHeight: 52,
        fullContent: false,
        footerVisible: false,
        fixedFooter: true,
        footerHeight: 48
      })
    ).toEqual({
      siderWidth: 232,
      siderCollapsedWidth: 72,
      tabHeight: 52,
      contentBottomPadding: 24
    });
  });

  it('keeps configured tab heights above the safe minimum and clamps smaller values', () => {
    expect(
      getLayoutGeometry({
        siderWidth: 232,
        siderCollapsedWidth: 72,
        tabHeight: 52,
        fullContent: false,
        footerVisible: true,
        fixedFooter: false,
        footerHeight: 48
      }).tabHeight
    ).toBe(52);
    expect(
      getLayoutGeometry({
        siderWidth: 232,
        siderCollapsedWidth: 72,
        tabHeight: 32,
        fullContent: false,
        footerVisible: true,
        fixedFooter: false,
        footerHeight: 48
      }).tabHeight
    ).toBe(40);
  });

  it('uses the financial workbench shell defaults', () => {
    expect(themeSettings.sider.width).toBe(208);
    expect(themeSettings.sider.collapsedWidth).toBe(64);
    expect(themeSettings.tab.height).toBe(40);
  });

  it('toggles a collapsed sidebar back to expanded through the app store action', () => {
    const ShellStoreHarness = defineComponent({
      setup() {
        return { appStore: useAppStore() };
      },
      template: '<div />'
    });
    const wrapper = mount(ShellStoreHarness, { global: { plugins: [router] } });
    const { appStore } = wrapper.vm as unknown as { appStore: ReturnType<typeof useAppStore> };

    appStore.setSiderCollapse(true);

    appStore.toggleSiderCollapse();

    expect(appStore.siderCollapse).toBe(false);
    wrapper.unmount();
  });

  it('passes store-derived shell geometry and content classes to AdminLayout', async () => {
    await router.push('/layout-test');

    const ShellStoreHarness = defineComponent({
      setup() {
        return { appStore: useAppStore(), themeStore: useThemeStore() };
      },
      template: '<div />'
    });
    const storeWrapper = mount(ShellStoreHarness, { global: { plugins: [router] } });
    const { appStore, themeStore } = storeWrapper.vm as unknown as {
      appStore: ReturnType<typeof useAppStore>;
      themeStore: ReturnType<typeof useThemeStore>;
    };
    const original = {
      contentXScrollable: appStore.contentXScrollable,
      footerFixed: themeStore.footer.fixed,
      footerVisible: themeStore.footer.visible,
      mode: themeStore.layout.mode,
      siderCollapsedWidth: themeStore.sider.collapsedWidth,
      siderWidth: themeStore.sider.width,
      tabHeight: themeStore.tab.height
    };

    themeStore.layout.mode = 'vertical';
    themeStore.sider.width = 216;
    themeStore.sider.collapsedWidth = 68;
    themeStore.tab.height = 32;
    themeStore.footer.visible = false;
    themeStore.footer.fixed = true;
    appStore.setContentXScrollable(true);

    let wrapper;
    try {
      wrapper = mount(BaseLayout, {
        global: {
          plugins: [router],
          stubs: {
            AdminLayout: AdminLayoutStub,
            GlobalContent: true,
            GlobalFooter: true,
            GlobalHeader: true,
            GlobalMenu: true,
            GlobalSider: true,
            GlobalTab: true,
            ThemeDrawer: true
          }
        }
      });
      const adminLayout = wrapper.findComponent(AdminLayoutStub);

      expect(adminLayout.props()).toMatchObject({
        contentClass: 'base-layout-content overflow-x-hidden',
        fixedFooter: true,
        footerVisible: false,
        siderCollapsedWidth: 68,
        siderWidth: 216,
        tabHeight: 40
      });
    } finally {
      wrapper?.unmount();
      storeWrapper.unmount();
      themeStore.layout.mode = original.mode;
      themeStore.sider.width = original.siderWidth;
      themeStore.sider.collapsedWidth = original.siderCollapsedWidth;
      themeStore.tab.height = original.tabHeight;
      themeStore.footer.visible = original.footerVisible;
      themeStore.footer.fixed = original.footerFixed;
      appStore.setContentXScrollable(original.contentXScrollable);
    }
  });
});
