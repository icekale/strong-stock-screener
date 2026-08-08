<script setup lang="ts">
import { useId } from 'vue';

defineOptions({ name: 'SystemLogo' });

// 组件级唯一渐变 id：同一布局可能渲染多个 logo 实例（侧栏/顶栏/混合菜单），
// 固定 id 会让 url(#id) 引用错乱到第一个匹配元素，必须用 useId 消除冲突。
const gradientId = `sm-logo-bg-${useId()}`;
</script>

<template>
  <div class="app-logo">
    <!--
      StockMaster 品牌 logo：深蓝渐变圆角方块 + 白色上升趋势线 + 红涨绿跌 K 线蜡烛。
      语义：强势股筛选（K 线）与向上突破（趋势线），贴合 A 股强势股工作台定位。
    -->
    <svg width="100%" height="100%" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient :id="gradientId" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#3a6ea5" />
          <stop offset="1" stop-color="#245b8a" />
        </linearGradient>
      </defs>
      <!-- 背景圆角方块 -->
      <rect x="10" y="10" width="180" height="180" rx="44" :fill="`url(#${gradientId})`" />
      <!-- 上升趋势线（强势/突破） -->
      <path
        d="M 54 152 L 86 122 L 100 130 L 130 82"
        fill="none"
        stroke="#ffffff"
        stroke-width="10"
        stroke-linecap="round"
        stroke-linejoin="round"
        opacity="0.92"
      />
      <path
        d="M 130 82 L 122 72 L 146 56 L 160 82 L 146 76"
        fill="none"
        stroke="#ffffff"
        stroke-width="10"
        stroke-linecap="round"
        stroke-linejoin="round"
        opacity="0.92"
      />
      <!-- K 线影线 -->
      <line x1="86" y1="156" x2="86" y2="118" stroke="#ffffff" stroke-width="5" stroke-linecap="round" opacity="0.85" />
      <line x1="118" y1="126" x2="118" y2="88" stroke="#ffffff" stroke-width="5" stroke-linecap="round" opacity="0.85" />
      <!-- K 线实体：左跌（绿）→ 右涨（红） -->
      <rect x="74" y="124" width="24" height="30" rx="5" fill="#43cf7c" />
      <rect x="106" y="92" width="24" height="34" rx="5" fill="#ff4d4f" />
    </svg>
  </div>
</template>

<style scoped></style>
