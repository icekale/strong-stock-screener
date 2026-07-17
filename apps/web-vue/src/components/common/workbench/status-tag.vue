<script setup lang="ts">
import { computed } from 'vue';
import { normalizeWorkbenchStatus } from './workbench';

defineOptions({ name: 'StatusTag' });

interface Props {
  status: unknown;
}

const props = defineProps<Props>();

const normalizedStatus = computed(() => normalizeWorkbenchStatus(props.status));
</script>

<template>
  <span
    class="wb-status-tag"
    :class="`wb-status-tag--${normalizedStatus.tone}`"
  >
    {{ normalizedStatus.label }}
  </span>
</template>
