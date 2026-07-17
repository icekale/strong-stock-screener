// @vitest-environment jsdom

import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';
import { router } from '@/router';
import { useAppStore } from '@/store/modules/app';
import { themeSettings } from '@/theme/settings';
import { getContentBottomPadding, getLayoutGeometry, getSiderGeometry } from './layoutState';

describe('base layout state', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('reserves fixed footer space only when the footer is visible', () => {
    expect(getContentBottomPadding({ footerVisible: true, fixedFooter: true, footerHeight: 48 })).toBe(72);
    expect(getContentBottomPadding({ footerVisible: true, fixedFooter: false, footerHeight: 48 })).toBe(24);
    expect(getContentBottomPadding({ footerVisible: false, fixedFooter: true, footerHeight: 48 })).toBe(24);
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
});
