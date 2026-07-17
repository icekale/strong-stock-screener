// @vitest-environment jsdom

import { createPinia, setActivePinia } from 'pinia';
import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it } from 'vitest';
import { router } from '@/router';
import { useAppStore } from '@/store/modules/app';
import { getContentBottomPadding } from './layoutState';

describe('base layout state', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('reserves footer space only when the footer is fixed', () => {
    expect(getContentBottomPadding({ fixedFooter: true, footerHeight: 48 })).toBe(72);
    expect(getContentBottomPadding({ fixedFooter: false, footerHeight: 48 })).toBe(24);
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
