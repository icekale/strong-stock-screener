// @vitest-environment jsdom

import { createApp, defineComponent, nextTick } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { EtfActivityAlert } from '@/service/types';

function alert(overrides: Partial<EtfActivityAlert> = {}): EtfActivityAlert {
  return {
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
    read: false,
    ...overrides
  };
}

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

async function mountNotifications(dependencies: Record<string, unknown>) {
  const { useEtfAlertNotifications } = await import('./useEtfAlertNotifications');
  let notifications: ReturnType<typeof useEtfAlertNotifications> | undefined;
  const element = document.createElement('div');
  const app = createApp(
    defineComponent({
      setup() {
        notifications = useEtfAlertNotifications(dependencies);
        return () => null;
      }
    })
  );

  app.mount(element);
  await nextTick();

  return {
    notifications: notifications!,
    unmount: () => app.unmount()
  };
}

describe('useEtfAlertNotifications', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.resetModules();
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('loads immediately, polls while visible, pauses while hidden, refreshes on visibility, and cleans up', async () => {
    const getEtfActivityAlerts = vi.fn().mockResolvedValue({ unread_count: 1, alerts: [alert()] });
    const dependencies = {
      getEtfActivityAlerts,
      markEtfAlertRead: vi.fn(),
      markAllEtfAlertsRead: vi.fn(),
      notify: vi.fn()
    };
    const mounted = await mountNotifications(dependencies);

    await flushPromises();
    expect(getEtfActivityAlerts).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(30_000);
    expect(getEtfActivityAlerts).toHaveBeenCalledTimes(2);

    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    document.dispatchEvent(new Event('visibilitychange'));
    await vi.advanceTimersByTimeAsync(60_000);
    expect(getEtfActivityAlerts).toHaveBeenCalledTimes(2);

    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    document.dispatchEvent(new Event('visibilitychange'));
    await flushPromises();
    expect(getEtfActivityAlerts).toHaveBeenCalledTimes(3);

    mounted.unmount();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(getEtfActivityAlerts).toHaveBeenCalledTimes(3);
  });

  it('deduplicates popups and never pops up market watch alerts', async () => {
    const notify = vi.fn();
    const getEtfActivityAlerts = vi.fn().mockResolvedValue({
      unread_count: 2,
      alerts: [alert(), alert({ alert_id: 'alert-2', alert_type: 'market_watch', title: '市场观察' })]
    });
    const mounted = await mountNotifications({
      getEtfActivityAlerts,
      markEtfAlertRead: vi.fn(),
      markAllEtfAlertsRead: vi.fn(),
      notify
    });

    await flushPromises();
    await mounted.notifications.refresh();

    expect(notify).toHaveBeenCalledTimes(1);
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ alert_id: 'alert-1' }));
    mounted.unmount();
  });

  it('keeps prior state and retries after a scheduled refresh fails', async () => {
    const initialAlert = alert();
    const refreshedAlert = alert({ alert_id: 'alert-2', read: true });
    const getEtfActivityAlerts = vi
      .fn()
      .mockResolvedValueOnce({ unread_count: 1, alerts: [initialAlert] })
      .mockRejectedValueOnce(new Error('scheduled refresh failed'))
      .mockResolvedValueOnce({ unread_count: 0, alerts: [refreshedAlert] });
    const mounted = await mountNotifications({
      getEtfActivityAlerts,
      markEtfAlertRead: vi.fn(),
      markAllEtfAlertsRead: vi.fn(),
      notify: vi.fn()
    });

    await flushPromises();
    await vi.advanceTimersByTimeAsync(30_000);
    expect(mounted.notifications.alerts.value).toEqual([initialAlert]);
    expect(mounted.notifications.unreadCount.value).toBe(1);

    await vi.advanceTimersByTimeAsync(30_000);
    expect(mounted.notifications.alerts.value).toEqual([refreshedAlert]);
    expect(mounted.notifications.unreadCount.value).toBe(0);
    mounted.unmount();
  });

  it('shares one polling lifecycle and stops it after the final consumer unmounts', async () => {
    const getEtfActivityAlerts = vi.fn().mockResolvedValue({ unread_count: 0, alerts: [] });
    const dependencies = {
      getEtfActivityAlerts,
      markEtfAlertRead: vi.fn(),
      markAllEtfAlertsRead: vi.fn(),
      notify: vi.fn()
    };
    const first = await mountNotifications(dependencies);
    await flushPromises();
    const second = await mountNotifications(dependencies);
    await flushPromises();

    expect(getEtfActivityAlerts).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(30_000);
    expect(getEtfActivityAlerts).toHaveBeenCalledTimes(2);

    first.unmount();
    await vi.advanceTimersByTimeAsync(30_000);
    expect(getEtfActivityAlerts).toHaveBeenCalledTimes(3);

    second.unmount();
    await vi.advanceTimersByTimeAsync(30_000);
    expect(getEtfActivityAlerts).toHaveBeenCalledTimes(3);
  });

  it('updates unread state after marking one alert and all alerts read', async () => {
    const alerts = [alert(), alert({ alert_id: 'alert-2', symbol: null, alert_type: 'market_high' })];
    const markEtfAlertRead = vi.fn().mockResolvedValue({ status: 'ok' });
    const markAllEtfAlertsRead = vi.fn().mockResolvedValue({ status: 'ok' });
    const mounted = await mountNotifications({
      getEtfActivityAlerts: vi.fn().mockResolvedValue({ unread_count: 2, alerts }),
      markEtfAlertRead,
      markAllEtfAlertsRead,
      notify: vi.fn()
    });

    await flushPromises();
    expect(mounted.notifications.unreadCount.value).toBe(2);

    await mounted.notifications.markRead('alert-1');
    expect(markEtfAlertRead).toHaveBeenCalledWith('alert-1');
    expect(mounted.notifications.unreadCount.value).toBe(1);
    expect(mounted.notifications.alerts.value[0]?.read).toBe(true);

    await mounted.notifications.markAllRead();
    expect(markAllEtfAlertsRead).toHaveBeenCalledTimes(1);
    expect(mounted.notifications.unreadCount.value).toBe(0);
    expect(mounted.notifications.alerts.value.every(item => item.read)).toBe(true);
    mounted.unmount();
  });
});
