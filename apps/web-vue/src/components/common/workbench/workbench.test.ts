// @vitest-environment jsdom

import { h, defineComponent } from 'vue';
import type { PropType } from 'vue';
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import DataList from './data-list.vue';
import { formatWorkbenchNumber, normalizeWorkbenchStatus } from './workbench';
import StatusTag from './status-tag.vue';

describe('normalizeWorkbenchStatus', () => {
  it.each([
    ['success', { label: '成功', tone: 'success' }],
    ['failed', { label: '失败', tone: 'error' }],
    ['partial', { label: '部分', tone: 'warning' }],
    ['unknown', { label: '待确认', tone: 'neutral' }]
  ] as const)('maps %s to a visible label and tone', (status, expected) => {
    expect(normalizeWorkbenchStatus(status)).toEqual(expected);
  });
});

describe('formatWorkbenchNumber', () => {
  it('rounds prices to two decimal places', () => {
    expect(formatWorkbenchNumber(8.870000000000001, 'price')).toBe('8.87');
  });

  it('formats large money values in Chinese units', () => {
    expect(formatWorkbenchNumber(2_580_000_000_000, 'money')).toBe('2.58万亿');
    expect(formatWorkbenchNumber(258_000_000_000, 'money')).toBe('2580.00亿');
  });

  it('renders missing values as a placeholder', () => {
    expect(formatWorkbenchNumber(null, 'price')).toBe('--');
  });
});

describe('DataList', () => {
  it('prioritizes errors over loading and empty states', () => {
    const wrapper = mount(DataList, {
      props: {
        error: '读取失败',
        emptyDescription: '暂无记录',
        loading: true
      }
    });

    expect(wrapper.find('[role="alert"]').text()).toBe('读取失败');
    expect(wrapper.text()).not.toContain('加载中');
    expect(wrapper.text()).not.toContain('暂无记录');
  });

  it('uses itemKey to preserve item state when rows reorder', async () => {
    type Item = { id: string };
    const items: Item[] = [{ id: 'a' }, { id: 'b' }];
    let nextInstanceId = 0;
    const TrackedItem = defineComponent({
      props: {
        item: { type: Object as PropType<Item>, required: true }
      },
      setup(props) {
        const instanceId = ++nextInstanceId;
        return () => h('span', `${props.item.id}:${instanceId}`);
      }
    });

    const wrapper = mount(DataList, {
      props: {
        items,
        itemKey: (item: unknown) => (item as Item).id
      },
      slots: {
        'list-item': ({ item }: { item: unknown }) => h(TrackedItem, { item: item as Item })
      }
    });

    expect(wrapper.findAll('li').map(item => item.text())).toEqual(['a:1', 'b:2']);

    await wrapper.setProps({ items: [items[1], items[0]] });

    expect(wrapper.findAll('li').map(item => item.text())).toEqual(['b:2', 'a:1']);
  });
});

describe('StatusTag', () => {
  it('renders a static visible label without live-region semantics', () => {
    const wrapper = mount(StatusTag, { props: { status: 'success' } });

    expect(wrapper.text()).toBe('成功');
    expect(wrapper.attributes('role')).toBeUndefined();
    expect(wrapper.attributes('aria-live')).toBeUndefined();
  });
});
