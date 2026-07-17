<script setup lang="ts">
import type { WorkbenchMetric } from './workbench';

defineOptions({ name: 'MetricStrip' });

interface Props {
  items: WorkbenchMetric[];
}

defineProps<Props>();
</script>

<template>
  <dl class="wb-metric-strip">
    <div v-for="item in items" :key="item.key" class="wb-metric" :class="item.tone ? `wb-metric--${item.tone}` : undefined">
      <dt class="wb-metric__label">{{ item.label }}</dt>
      <dd class="wb-metric__value">{{ item.value ?? '--' }}</dd>
      <dd v-if="item.helper" class="wb-metric__helper">{{ item.helper }}</dd>
    </div>
  </dl>
</template>
