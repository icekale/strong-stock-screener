<script setup lang="ts">
import { computed } from 'vue';
import type { WorkbenchItemKeyResolver } from './workbench';
import { createWorkbenchItemKeyResolver } from './workbench';

defineOptions({ name: 'DataList' });

interface Props {
  items?: unknown[];
  loading?: boolean;
  emptyDescription?: string;
  error?: string | null;
  itemKey?: WorkbenchItemKeyResolver;
  /** 单个列表的最大渲染条数，防止超大接口（如 limit=2000）直接拖垮渲染。 */
  maxRender?: number;
}

const props = withDefaults(defineProps<Props>(), {
  items: () => [],
  loading: false,
  emptyDescription: '暂无数据',
  error: null,
  maxRender: 300
});

const resolveItemKeys = createWorkbenchItemKeyResolver();
const visibleItems = computed(() => props.items.slice(0, props.maxRender));
const itemKeys = computed(() => resolveItemKeys(visibleItems.value, props.itemKey));
const truncatedCount = computed(() => Math.max(0, props.items.length - props.maxRender));
</script>

<template>
  <div class="wb-data-list" :aria-busy="props.loading && !props.error">
    <div v-if="props.error" class="wb-data-list__state wb-data-list__state--error" role="alert">
      {{ props.error }}
    </div>
    <div v-else-if="props.loading && !props.items.length" class="wb-data-list__state" aria-live="polite">加载中...</div>
    <div v-else-if="!props.items.length" class="wb-data-list__state">{{ props.emptyDescription }}</div>

    <template v-if="visibleItems.length">
      <div v-if="props.loading && !props.error" class="wb-data-list__loading" aria-live="polite">读取中...</div>
      <div v-if="truncatedCount" class="wb-data-list__truncated text-12px text-secondary">
        仅展示前 {{ visibleItems.length }} 条，另有 {{ truncatedCount }} 条未渲染
      </div>
      <ul class="wb-data-list__items">
        <li v-for="(item, index) in visibleItems" :key="itemKeys[index]" class="wb-data-list__item">
          <slot name="list-item" :item="item" :index="index">
            <span>{{ item }}</span>
          </slot>
        </li>
      </ul>
    </template>
  </div>
</template>
