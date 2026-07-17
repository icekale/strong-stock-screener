<script setup lang="ts">
defineOptions({ name: 'SectionHeader' });

interface Props {
  title: string;
  source?: string;
  updatedAt?: string;
}

defineProps<Props>();
</script>

<template>
  <header class="wb-section-header">
    <div class="wb-section-header__copy">
      <h2 class="wb-section-header__title">{{ title }}</h2>
      <div v-if="source || updatedAt" class="wb-section-header__meta">
        <span v-if="source">来源 {{ source }}</span>
        <span v-if="updatedAt">更新 {{ updatedAt }}</span>
      </div>
    </div>
    <div v-if="$slots.default" class="wb-section-header__action">
      <slot />
    </div>
  </header>
</template>
