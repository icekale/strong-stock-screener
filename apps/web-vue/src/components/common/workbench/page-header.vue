<script setup lang="ts">
defineOptions({ name: 'PageHeader' });

interface Props {
  title: string;
  description?: string;
}

defineProps<Props>();
</script>

<template>
  <header class="wb-page-header">
    <div class="wb-page-header__copy">
      <h1 class="wb-page-header__title">{{ title }}</h1>
      <p v-if="description" class="wb-page-header__description">{{ description }}</p>
    </div>

    <div v-if="$slots.meta || $slots.default" class="wb-page-header__actions">
      <div v-if="$slots.meta" class="wb-page-header__meta">
        <slot name="meta" />
      </div>
      <div v-if="$slots.default" class="wb-page-header__actions-content">
        <slot />
      </div>
    </div>
  </header>
</template>
