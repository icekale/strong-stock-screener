<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { addWatchlistPoolItem, getWatchlistGsgfStatus, getWatchlistPool, saveWatchlistPool } from '@/service/product-api';
import type { WatchlistGsgfStatusResponse, WatchlistPoolResponse } from '@/service/types';

defineOptions({ name: 'WatchlistView' });

const router = useRouter();
const pool = ref<WatchlistPoolResponse | null>(null);
const gsgf = ref<WatchlistGsgfStatusResponse | null>(null);
const content = ref('');
const symbolInput = ref('');
const loading = ref(false);
const saving = ref(false);
const error = ref<string | null>(null);

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
  try { pool.value = await saveWatchlistPool(content.value); } catch (cause) { error.value = cause instanceof Error ? cause.message : '保存自选股失败'; } finally { saving.value = false; }
}

async function addSymbol() {
  const symbol = symbolInput.value.trim().toUpperCase();
  if (!symbol) return;
  try { pool.value = await addWatchlistPoolItem({ symbol, group: '人工关注', tags: [] }); symbolInput.value = ''; await load(); } catch (cause) { error.value = cause instanceof Error ? cause.message : '加入自选失败'; }
}

function openStock(symbol: string, name: string | null, industry: string | null) {
  void router.push({ path: `/stock/${encodeURIComponent(symbol)}`, query: { from: 'home', name: name || undefined, industry: industry || undefined } });
}

onMounted(() => void load());
</script>

<template>
  <div class="space-y-16px"><div class="flex flex-wrap items-center justify-between gap-12px"><div><div class="text-22px font-700 text-text-primary">自选与风险</div><div class="mt-4px text-13px text-text-secondary">统一管理观察池和结构触发</div></div><a-button :loading="loading" @click="load">刷新</a-button></div><a-alert v-if="error" :message="error" show-icon type="warning" /><a-row :gutter="12"><a-col :xs="24" :lg="10"><a-card size="small" title="股票池"><a-space-compact class="mb-12px w-full"><a-input v-model:value="symbolInput" placeholder="输入代码，如 600000.SH" @press-enter="addSymbol" /><a-button type="primary" @click="addSymbol">加入</a-button></a-space-compact><a-textarea v-model:value="content" :auto-size="{ minRows: 10, maxRows: 18 }" placeholder="每行输入一个代码" /><a-button class="mt-12px" :loading="saving" type="primary" @click="save">保存股票池</a-button></a-card></a-col><a-col :xs="24" :lg="14"><a-card size="small" title="结构触发"><a-list :data-source="gsgf?.items ?? []" size="small"><template #renderItem="{ item }"><a-list-item class="cursor-pointer" @click="openStock(item.symbol, item.name, item.industry)"><a-list-item-meta :title="`${item.name} · ${item.symbol}`" :description="item.gsgf.explanation.slice(0, 2).join('；')" /><template #extra><a-tag :color="item.gsgf.action === 'avoid' ? 'green' : item.gsgf.action === 'strong_candidate' ? 'red' : 'orange'">{{ item.gsgf.final_status }}</a-tag></template></a-list-item></template></a-list><a-empty v-if="!gsgf?.items.length" description="暂无结构触发" /></a-card></a-col></a-row><a-card size="small" title="观察池明细"><a-list :loading="loading" :data-source="pool?.items ?? []" size="small"><template #renderItem="{ item }"><a-list-item class="cursor-pointer" @click="openStock(item.symbol, item.name, item.industry)"><a-list-item-meta :title="`${item.name || '--'} · ${item.symbol}`" :description="`${item.industry || '行业待补'} · ${(item.tags || []).join(' / ') || '未分类'}`" /></a-list-item></template></a-list><a-empty v-if="!pool?.items.length" description="观察池为空" /></a-card></div>
</template>
