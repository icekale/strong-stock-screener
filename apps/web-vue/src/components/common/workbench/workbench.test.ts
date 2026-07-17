// @vitest-environment jsdom

import { h, defineComponent } from 'vue';
import type { PropType } from 'vue';
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import DataList from './data-list.vue';
import MetricStrip from './metric-strip.vue';
import PageHeader from './page-header.vue';
import SectionHeader from './section-header.vue';
import { createWorkbenchItemKeyResolver, formatWorkbenchNumber, normalizeWorkbenchStatus } from './workbench';
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

  it('makes duplicate default object keys distinct and stable across reorders', async () => {
    type Item = { id: string; label: string };
    const items: Item[] = [
      { id: 'duplicate', label: 'first' },
      { id: 'duplicate', label: 'second' }
    ];
    let nextInstanceId = 0;
    const TrackedItem = defineComponent({
      props: {
        item: { type: Object as PropType<Item>, required: true }
      },
      setup(props) {
        const instanceId = ++nextInstanceId;
        return () => h('span', `${props.item.label}:${instanceId}`);
      }
    });

    const wrapper = mount(DataList, {
      props: { items },
      slots: {
        'list-item': ({ item }: { item: unknown }) => h(TrackedItem, { item: item as Item })
      }
    });

    expect(wrapper.findAll('li').map(item => item.text())).toEqual(['first:1', 'second:2']);

    await wrapper.setProps({ items: [items[1], items[0]] });

    expect(wrapper.findAll('li').map(item => item.text())).toEqual(['second:2', 'first:1']);
  });

  it('gives duplicate primitive values unique stable default keys', () => {
    const resolveItemKeys = createWorkbenchItemKeyResolver();
    const firstKeys = resolveItemKeys(['same', 'same']);
    const secondKeys = resolveItemKeys(['same', 'same']);

    expect(new Set(firstKeys).size).toBe(2);
    expect(secondKeys).toEqual(firstKeys);
  });

  it('keeps synthesized duplicate keys away from raw keys', () => {
    const resolveItemKeys = createWorkbenchItemKeyResolver();
    const keys = resolveItemKeys([{ id: 'x' }, { id: 'x' }, 'object:string:x:1']);

    expect(new Set(keys).size).toBe(3);
    expect(keys[2]).toBe('object:string:x:1');
    expect(keys[0]).not.toBe(keys[2]);
    expect(keys[1]).not.toBe(keys[2]);
  });
});

describe('shared workbench components', () => {
  it('renders PageHeader title, description, metadata, and actions', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '市场总览', description: '盘前扫描' },
      slots: {
        default: () => h('button', '刷新'),
        meta: () => '2026-07-17'
      }
    });

    expect(wrapper.find('h1').text()).toBe('市场总览');
    expect(wrapper.find('.wb-page-header__description').text()).toBe('盘前扫描');
    expect(wrapper.find('.wb-page-header__meta').text()).toBe('2026-07-17');
    expect(wrapper.find('button').text()).toBe('刷新');
  });

  it('renders MetricStrip values, helpers, and tone classes', () => {
    const wrapper = mount(MetricStrip, {
      props: {
        items: [
          { key: 'index', label: '指数', value: '3,200', helper: '实时', tone: 'positive' },
          { key: 'status', label: '状态', value: '正常' }
        ]
      }
    });

    expect(wrapper.findAll('.wb-metric')).toHaveLength(2);
    expect(wrapper.find('.wb-metric').classes()).toContain('wb-metric--positive');
    expect(wrapper.text()).toContain('指数');
    expect(wrapper.text()).toContain('3,200');
    expect(wrapper.text()).toContain('实时');
    expect(wrapper.text()).toContain('正常');
  });

  it('renders SectionHeader title, source, update time, and action', () => {
    const wrapper = mount(SectionHeader, {
      props: { title: '数据源', source: 'iFinD', updatedAt: '09:35' },
      slots: { default: () => h('button', '查看') }
    });

    expect(wrapper.find('h2').text()).toBe('数据源');
    expect(wrapper.find('.wb-section-header__meta').text()).toContain('来源 iFinD');
    expect(wrapper.find('.wb-section-header__meta').text()).toContain('更新 09:35');
    expect(wrapper.find('button').text()).toBe('查看');
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
