// @vitest-environment jsdom

import { defineComponent, ref } from 'vue';
import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import type { EtfActivityAlert } from '@/service/types';
import EtfAlertCenter from './etf-alert-center.vue';

const push = vi.fn();
const unreadCount = ref(1);
const alerts = ref<EtfActivityAlert[]>([
  {
    alert_id: 'alert-1',
    trade_date: '2026-07-22',
    alert_type: 'single_high',
    level: 'high',
    symbol: '510050.SH',
    title: '沪深300ETF信号增强',
    message: '量能和份额同步走强',
    signal_score: 92,
    triggered_at: '2026-07-22T10:00:00+08:00',
    last_triggered_at: '2026-07-22T10:00:00+08:00',
    evidence: { volume_ratio: 1.8 },
    read: false
  }
]);
const markRead = vi.fn().mockResolvedValue(undefined);
const markAllRead = vi.fn().mockResolvedValue(undefined);

vi.mock('@/composables/useEtfAlertNotifications', () => ({
  useEtfAlertNotifications: () => ({ alerts, unreadCount, markRead, markAllRead })
}));

vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }));

const DrawerStub = defineComponent({
  props: ['open', 'title'],
  emits: ['update:open'],
  template: '<section v-if="open" role="dialog"><h2>{{ title }}</h2><slot /></section>'
});

function mountCenter() {
  return mount(EtfAlertCenter, {
    global: {
      stubs: {
        ATooltip: { template: '<span><slot /></span>' },
        ABadge: { props: ['count'], template: '<span><slot /><sup v-if="count">{{ count }}</sup></span>' },
        AButton: { template: '<button v-bind="$attrs"><slot /></button>' },
        ADrawer: DrawerStub,
        AEmpty: { template: '<div>暂无通知</div>' },
        ATag: { template: '<span><slot /></span>' }
      }
    }
  });
}

describe('EtfAlertCenter', () => {
  it('keeps a labelled bell visible, shows unread count, and opens a compact notification drawer', async () => {
    const wrapper = mountCenter();

    expect(wrapper.find('button[aria-label="ETF 活动通知"]').exists()).toBe(true);
    expect(wrapper.get('sup').text()).toBe('1');

    await wrapper.get('button[aria-label="ETF 活动通知"]').trigger('click');
    expect(wrapper.get('[role="dialog"]').text()).toContain('ETF 活动通知');
    expect(wrapper.get('[data-testid="etf-alert-row"]').text()).toContain('沪深300ETF信号增强');
    expect(wrapper.get('[data-testid="etf-alert-row"]').text()).toContain('量能和份额同步走强');
  });

  it('marks alerts read and routes symbol alerts into ETF activity', async () => {
    const wrapper = mountCenter();
    await wrapper.get('button[aria-label="ETF 活动通知"]').trigger('click');

    await wrapper.get('button[data-testid="mark-all-read"]').trigger('click');
    expect(markAllRead).toHaveBeenCalledTimes(1);

    await wrapper.get('[data-testid="etf-alert-row"]').trigger('click');

    expect(markRead).toHaveBeenCalledWith('alert-1');
    expect(push).toHaveBeenCalledWith({ path: '/etf-radar', query: { tab: 'activity', symbol: '510050.SH' } });
  });

  it('hides the badge at zero unread without hiding the bell', () => {
    unreadCount.value = 0;
    const wrapper = mountCenter();

    expect(wrapper.find('button[aria-label="ETF 活动通知"]').exists()).toBe(true);
    expect(wrapper.find('sup').exists()).toBe(false);
  });
});
