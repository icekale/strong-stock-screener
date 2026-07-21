import { onMounted, onUnmounted, ref } from 'vue';
import {
  getEtfActivityAlerts,
  markAllEtfAlertsRead,
  markEtfAlertRead
} from '@/service/product-api';
import type { EtfActivityAlert, EtfAlertReadResponse, EtfActivityAlertResponse, EtfAlertType } from '@/service/types';

type EtfAlertNotificationDependencies = {
  getEtfActivityAlerts: (unreadOnly?: boolean) => Promise<EtfActivityAlertResponse>;
  markEtfAlertRead: (alertId: string) => Promise<EtfAlertReadResponse>;
  markAllEtfAlertsRead: () => Promise<EtfAlertReadResponse>;
  notify: (alert: EtfActivityAlert) => void;
};

const POLLING_INTERVAL_MS = 30_000;
const POPUP_ALERT_TYPES = new Set<EtfAlertType>(['single_high', 'single_upgrade', 'market_high']);

const alerts = ref<EtfActivityAlert[]>([]);
const unreadCount = ref(0);
const loading = ref(false);
const shownAlertIds = new Set<string>();
let consumerCount = 0;
let pollingTimer: ReturnType<typeof setInterval> | undefined;
let dependencies: EtfAlertNotificationDependencies;

function notify(alert: EtfActivityAlert) {
  window.$notification?.warning({
    key: `etf-alert-${alert.alert_id}`,
    message: alert.title,
    description: alert.message
  });
}

const defaultDependencies: EtfAlertNotificationDependencies = {
  getEtfActivityAlerts,
  markEtfAlertRead,
  markAllEtfAlertsRead,
  notify
};

dependencies = defaultDependencies;

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = undefined;
  }
}

function startPolling() {
  stopPolling();
  if (document.hidden) return;

  pollingTimer = setInterval(() => {
    void refresh();
  }, POLLING_INTERVAL_MS);
}

function showNewAlertPopups(nextAlerts: EtfActivityAlert[]) {
  nextAlerts.forEach(alert => {
    if (alert.read || !POPUP_ALERT_TYPES.has(alert.alert_type) || shownAlertIds.has(alert.alert_id)) return;

    shownAlertIds.add(alert.alert_id);
    dependencies.notify(alert);
  });
}

async function refresh() {
  loading.value = true;

  try {
    const response = await dependencies.getEtfActivityAlerts();
    alerts.value = response.alerts;
    unreadCount.value = response.unread_count;
    showNewAlertPopups(response.alerts);
  } finally {
    loading.value = false;
  }
}

async function markRead(alertId: string) {
  await dependencies.markEtfAlertRead(alertId);
  const alert = alerts.value.find(item => item.alert_id === alertId);

  if (alert && !alert.read) {
    alert.read = true;
    unreadCount.value = Math.max(0, unreadCount.value - 1);
  }
}

async function markAllRead() {
  await dependencies.markAllEtfAlertsRead();
  alerts.value.forEach(alert => {
    alert.read = true;
  });
  unreadCount.value = 0;
}

function handleVisibilityChange() {
  if (document.hidden) {
    stopPolling();
    return;
  }

  void refresh();
  startPolling();
}

function start() {
  document.addEventListener('visibilitychange', handleVisibilityChange);
  void refresh();
  startPolling();
}

function stop() {
  stopPolling();
  document.removeEventListener('visibilitychange', handleVisibilityChange);
}

export function useEtfAlertNotifications(overrides?: Partial<EtfAlertNotificationDependencies>) {
  onMounted(() => {
    if (consumerCount === 0) {
      dependencies = { ...defaultDependencies, ...overrides };
      start();
    }
    consumerCount += 1;
  });

  onUnmounted(() => {
    consumerCount = Math.max(0, consumerCount - 1);
    if (consumerCount === 0) stop();
  });

  return { alerts, unreadCount, loading, refresh, markRead, markAllRead };
}
