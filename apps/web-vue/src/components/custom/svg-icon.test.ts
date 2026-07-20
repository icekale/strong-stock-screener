// @vitest-environment jsdom

import { mount } from '@vue/test-utils';
import { expect, it } from 'vitest';
import SvgIcon from './svg-icon.vue';

it('uses the build-time local icon prefix when the environment omits it', () => {
  const wrapper = mount(SvgIcon, { props: { localIcon: 'expectation' } });

  expect(wrapper.find('use').attributes('href')).toBe('#local-icon-expectation');
});
