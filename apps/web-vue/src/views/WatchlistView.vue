<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { addWatchlistPoolItem, getWatchlistGsgfStatus, getWatchlistPool, saveWatchlistPool } from '@/service/product-api';
import type { GsgfAction, WatchlistGsgfStatusResponse, WatchlistPoolItem, WatchlistPoolResponse } from '@/service/types';

defineOptions({ name: 'WatchlistView' });

const router = useRouter();
const pool = ref<WatchlistPoolResponse | null>(null);
const gsgf = ref<WatchlistGsgfStatusResponse | null>(null);
const content = ref('');
const symbolInput = ref('');
const loading = ref(false);
const saving = ref(false);
const error = ref<string | null>(null);

const poolItems = computed(() => pool.value?.items ?? []);
const gsgfItems = computed(() => gsgf.value?.items ?? []);

async function load() {
  loading.value = true;
  try {
    const [nextPool, nextGsgf] = await Promise.all([getWatchlistPool(), getWatchlistGsgfStatus()]);
    pool.value = nextPool;
    content.value = nextPool.content;
    gsgf.value = nextGsgf;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '读取自选股失败';
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    pool.value = await saveWatchlistPool(content.value);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '保存自选股失败';
  } finally {
    saving.value = false;
  }
}

async function addSymbol() {
  const symbol = symbolInput.value.trim().toUpperCase();
  if (!symbol) return;
  try {
    pool.value = await addWatchlistPoolItem({ symbol, group: '人工关注', tags: [] });
    symbolInput.value = '';
    await load();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '加入自选失败';
  }
}

function openStock(symbol: string, name: string | null, industry: string | null) {
  void router.push({ path: `/stock/${encodeURIComponent(symbol)}`, query: { from: 'home', name: name || undefined, industry: industry || undefined } });
}

function openPoolItem(item: WatchlistPoolItem) {
  openStock(item.symbol, item.name, item.industry);
}

function openGsgfItem(item: WatchlistGsgfStatusResponse['items'][number]) {
  openStock(item.symbol, item.name, item.industry);
}

function asGsgfItem(value: unknown) {
  return value as WatchlistGsgfStatusResponse['items'][number];
}

function asPoolItem(value: unknown) {
  return value as WatchlistPoolItem;
}

function gsgfTone(action: GsgfAction) {
  if (action === 'avoid') return 'success';
  if (action === 'strong_candidate') return 'error';
  if (action === 'wait_trigger') return 'warning';
  return 'info';
}

onMounted(() => void load());
</script>

<template>
  <div class="space-y-16px">
    <PageHeader title="自选与风险" description="统一管理观察池和结构触发">
      <template #meta>{{ poolItems.length }} 只自选</template>
      <a-button :loading="loading" @click="load">刷新数据</a-button>
    </PageHeader>

    <a-alert v-if="error" :title="error" show-icon type="warning" />

    <section class="watchlist-panel">
      <SectionHeader title="观察池编辑" source="本地自选池">
        <StatusTag :status="pool ? 'success' : loading ? 'running' : 'unknown'" />
      </SectionHeader>
      <div class="watchlist-toolbar">
        <a-space-compact class="watchlist-toolbar__input">
          <a-input v-model:value="symbolInput" placeholder="输入代码，如 600000.SH" @press-enter="addSymbol" />
          <a-button type="primary" @click="addSymbol">加入自选</a-button>
        </a-space-compact>
        <a-button :loading="saving" type="primary" @click="save">保存股票池</a-button>
      </div>
      <a-textarea v-model:value="content" :auto-size="{ minRows: 6, maxRows: 14 }" placeholder="每行输入一个代码" />
      <div class="mt-8px text-12px text-text-secondary">支持直接维护代码列表，也可以通过上方输入框追加人工关注标的。</div>
    </section>

    <section class="watchlist-panel">
      <SectionHeader title="结构触发" source="GSGF 结构分析" />
      <DataList :items="gsgfItems" :loading="loading && !gsgf" empty-description="暂无结构触发">
        <template #list-item="{ item }">
          <div
            class="watchlist-row watchlist-row--action"
            role="button"
            tabindex="0"
            @click="openGsgfItem(asGsgfItem(item))"
            @keydown.enter="openGsgfItem(asGsgfItem(item))"
            @keydown.space.prevent="openGsgfItem(asGsgfItem(item))"
          >
            <div class="min-w-0">
              <div class="font-600 truncate">{{ asGsgfItem(item).name }} <span class="text-12px text-text-secondary">{{ asGsgfItem(item).symbol }}</span></div>
              <div class="text-12px text-text-secondary truncate">{{ asGsgfItem(item).industry || '行业待补' }} · {{ asGsgfItem(item).gsgf.explanation.slice(0, 2).join('；') || '暂无结构说明' }}</div>
            </div>
            <div class="watchlist-row__status">
              <StatusTag :status="gsgfTone(asGsgfItem(item).gsgf.action)" />
              <span class="text-12px text-text-secondary">{{ asGsgfItem(item).gsgf.final_status }}</span>
            </div>
          </div>
        </template>
      </DataList>
    </section>

    <section class="watchlist-panel">
      <SectionHeader title="观察池明细" source="当前自选标的" />
      <DataList :items="poolItems" :loading="loading" empty-description="观察池为空">
        <template #list-item="{ item }">
          <div
            class="watchlist-row watchlist-row--action"
            role="button"
            tabindex="0"
            @click="openPoolItem(asPoolItem(item))"
            @keydown.enter="openPoolItem(asPoolItem(item))"
            @keydown.space.prevent="openPoolItem(asPoolItem(item))"
          >
            <div class="min-w-0">
              <div class="font-600 truncate">{{ asPoolItem(item).name || '--' }} <span class="text-12px text-text-secondary">{{ asPoolItem(item).symbol }}</span></div>
              <div class="text-12px text-text-secondary truncate">{{ asPoolItem(item).industry || '行业待补' }} · {{ asPoolItem(item).tags.join(' / ') || '未分类' }}</div>
            </div>
            <span class="text-12px text-text-secondary">{{ asPoolItem(item).group || '默认分组' }}</span>
          </div>
        </template>
      </DataList>
    </section>
  </div>
</template>

<style scoped>
.watchlist-panel {
  padding: 12px;
  background: var(--wb-surface);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
}

.watchlist-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 12px 0;
}

.watchlist-toolbar__input {
  flex: 1;
  min-width: 0;
}

.watchlist-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.watchlist-row--action {
  padding: 2px 0;
  cursor: pointer;
}

.watchlist-row--action:hover {
  color: var(--wb-primary);
}

.watchlist-row__status {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

@media (max-width: 639px) {
  .watchlist-panel {
    padding: 10px;
  }

  .watchlist-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .watchlist-toolbar__input {
    width: 100%;
  }

  .watchlist-toolbar > .ant-btn {
    width: 100%;
  }

  .watchlist-row--action {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }
}
</style>
