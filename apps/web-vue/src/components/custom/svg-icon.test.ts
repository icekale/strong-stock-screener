// @vitest-environment jsdom

import { mount } from '@vue/test-utils';
import { afterEach, expect, it, vi } from 'vitest';
import SvgIcon from './svg-icon.vue';

afterEach(() => {
  vi.unstubAllEnvs();
});

it('uses the build-time local icon prefix when the environment omits it', () => {
  vi.stubEnv('VITE_ICON_LOCAL_PREFIX', '');
  const wrapper = mount(SvgIcon, { props: { localIcon: 'expectation' } });

  expect(wrapper.find('use').attributes('href')).toBe('#local-icon-expectation');
});
