<script setup lang="ts">
defineOptions({ name: 'DataList' });

interface Props {
  items?: unknown[];
  loading?: boolean;
  emptyDescription?: string;
  error?: string | null;
}

const props = withDefaults(defineProps<Props>(), {
  items: () => [],
  loading: false,
  emptyDescription: '暂无数据',
  error: null
});
</script>

<template>
  <div class="wb-data-list" :aria-busy="props.loading">
    <div v-if="props.error" class="wb-data-list__state wb-data-list__state--error" role="alert">
      {{ props.error }}
    </div>
    <div v-if="props.loading && !props.items.length" class="wb-data-list__state" aria-live="polite">加载中...</div>
    <div v-else-if="!props.items.length && !props.error" class="wb-data-list__state">{{ props.emptyDescription }}</div>

    <template v-if="props.items.length">
      <div v-if="props.loading" class="wb-data-list__loading" aria-live="polite">读取中...</div>
      <ul class="wb-data-list__items">
        <li v-for="(item, index) in props.items" :key="index" class="wb-data-list__item">
          <slot name="list-item" :item="item" :index="index">
            <span>{{ item }}</span>
          </slot>
        </li>
      </ul>
    </template>
  </div>
</template>
