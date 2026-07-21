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
  if (!alert.read) await markRead(alert.alert_id);
  if (!alert.symbol) return;

  open.value = false;
  await router.push({ path: '/etf-radar', query: { tab: 'activity', symbol: alert.symbol } });
}

async function markAlertRead(alert: EtfActivityAlert) {
  if (!alert.read) await markRead(alert.alert_id);
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
        data-testid="etf-alert-row"
        class="etf-alert-row cursor-pointer rd-4px p-12px"
        :class="{ 'etf-alert-row--unread': !alert.read }"
        @click="selectAlert(alert)"
      >
        <div class="flex items-center justify-between gap-8px">
          <ATag :color="alert.level === 'high' ? 'red' : 'gold'">{{ alertTypeLabels[alert.alert_type] }}</ATag>
          <span class="shrink-0 text-12px text-secondary">{{ formatTime(alert.triggered_at) }}</span>
        </div>
        <div class="mt-6px flex items-start gap-8px">
          <div class="min-w-0 flex-1">
            <strong class="block truncate">{{ alert.title }}</strong>
            <p class="mb-0 mt-4px text-13px text-secondary">{{ alert.message }}</p>
            <p v-if="evidenceText(alert)" class="mb-0 mt-4px text-12px text-secondary">{{ evidenceText(alert) }}</p>
          </div>
          <AButton
            v-if="!alert.read"
            type="link"
            size="small"
            :aria-label="`标记${alert.title}已读`"
            @click.stop="markAlertRead(alert)"
          >
            已读
          </AButton>
        </div>
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
