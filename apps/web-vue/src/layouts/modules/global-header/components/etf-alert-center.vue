<script setup lang="ts">
import { ref } from 'vue';
import { Icon } from '@iconify/vue';
import { Empty } from 'ant-design-vue';
import { useRouter } from 'vue-router';
import { useEtfAlertNotifications } from '@/composables/useEtfAlertNotifications';
import type { EtfActivityAlert } from '@/service/types';

defineOptions({
  name: 'EtfAlertCenter'
});

const router = useRouter();
const open = ref(false);
const { alerts, unreadCount, markRead, markAllRead } = useEtfAlertNotifications();

const alertTypeLabels: Record<EtfActivityAlert['alert_type'], string> = {
  single_high: '个券高强度',
  single_upgrade: '个券升级',
  market_watch: '市场观察',
  market_high: '市场高强度'
};

function formatTime(value: string) {
  return value.replace('T', ' ').replace(/([+-]\d{2}:\d{2}|Z)$/, '');
}

function evidenceText(alert: EtfActivityAlert) {
  return Object.entries(alert.evidence)
    .filter(([, value]) => value !== null)
    .slice(0, 2)
    .map(([key, value]) => `${key}: ${value}`)
    .join(' | ');
}

async function selectAlert(alert: EtfActivityAlert) {
  if (!alert.read) {
    try {
      await markRead(alert.alert_id);
    } catch {
      // Navigation is still useful when the best-effort read request fails.
    }
  }
  if (!alert.symbol) return;

  open.value = false;
  try {
    await router.push({ path: '/etf-radar', query: { tab: 'activity', symbol: alert.symbol } });
  } catch {
    // Router failures should not surface from an event handler.
  }
}

async function markAlertRead(alert: EtfActivityAlert) {
  if (!alert.read) await markRead(alert.alert_id);
}

function handleAlertKeydown(event: KeyboardEvent, alert: EtfActivityAlert) {
  if (event.key !== 'Enter' && event.key !== ' ') return;

  event.preventDefault();
  void selectAlert(alert);
}
</script>

<template>
  <ATooltip title="ETF 活动通知">
    <ABadge :count="unreadCount" :show-zero="false" :offset="[-2, 4]">
      <AButton type="text" aria-label="ETF 活动通知" @click="open = true">
        <Icon icon="mdi:bell-outline" class="text-18px" />
      </AButton>
    </ABadge>
  </ATooltip>

  <ADrawer v-model:open="open" title="ETF 活动通知" placement="right" :width="360">
    <div class="mb-12px flex items-center justify-between">
      <span class="text-13px text-secondary">未读 {{ unreadCount }}</span>
      <AButton data-testid="mark-all-read" type="link" size="small" :disabled="unreadCount === 0" @click="markAllRead">
        全部已读
      </AButton>
    </div>

    <div v-if="alerts.length" class="flex flex-col gap-8px">
      <article
        v-for="alert in alerts"
        :key="alert.alert_id"
        class="etf-alert-row flex items-stretch gap-8px rd-4px p-12px"
        :class="{ 'etf-alert-row--unread': !alert.read }"
      >
        <div
          :aria-label="`查看${alert.title}`"
          class="min-w-0 flex-1 cursor-pointer"
          data-testid="etf-alert-row"
          role="button"
          tabindex="0"
          @click="selectAlert(alert)"
          @keydown="handleAlertKeydown($event, alert)"
        >
          <div class="flex items-center justify-between gap-8px">
            <ATag :color="alert.level === 'high' ? 'red' : 'gold'">{{ alertTypeLabels[alert.alert_type] }}</ATag>
            <span class="shrink-0 text-12px text-secondary">{{ formatTime(alert.triggered_at) }}</span>
          </div>
          <div class="mt-6px min-w-0">
            <strong class="block truncate">{{ alert.title }}</strong>
            <p class="mb-0 mt-4px text-13px text-secondary">{{ alert.message }}</p>
            <p v-if="evidenceText(alert)" class="mb-0 mt-4px text-12px text-secondary">{{ evidenceText(alert) }}</p>
          </div>
        </div>
        <AButton
          v-if="!alert.read"
          class="shrink-0 self-end"
          type="link"
          size="small"
          :aria-label="`标记${alert.title}已读`"
          @click="markAlertRead(alert)"
        >
          已读
        </AButton>
      </article>
    </div>
    <AEmpty v-else description="暂无通知" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
  </ADrawer>
</template>

<style scoped>
.etf-alert-row {
  border: 1px solid var(--wb-border);
}

.etf-alert-row--unread {
  border-color: var(--ant-color-primary-border);
  background: var(--ant-color-primary-bg);
}
</style>
