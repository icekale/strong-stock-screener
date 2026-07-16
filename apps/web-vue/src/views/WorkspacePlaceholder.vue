<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';

defineOptions({ name: 'WorkspacePlaceholder' });

const route = useRoute();
const title = computed(() => String(route.meta.title || '工作区'));
</script>

<template>
  <div class="min-h-full p-16px" data-testid="workspace-placeholder">
    <a-card :title="title">
      <a-empty description="工作区迁移中" />
    </a-card>
  </div>
</template>
