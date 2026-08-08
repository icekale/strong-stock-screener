<template>
  <div class="app-logo">
    <!--
      StockMaster 品牌 logo：深蓝圆角方块 + 上升箭头 + K 线蜡烛（红涨绿跌）。
      语义：强势股筛选（K 线）与向上突破（箭头），贴合 A 股强势股工作台定位。
      使用固定品牌色，不依赖主题变量，在任何上下文（登录页/侧栏/加载页）均正确渲染。
    -->
    <svg width="100%" height="100%" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="sm-logo-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#3a6ea5" />
          <stop offset="1" stop-color="#245b8a" />
        </linearGradient>
      </defs>
      <!-- 背景圆角方块 -->
      <rect x="10" y="10" width="180" height="180" rx="42" fill="url(#sm-logo-bg)" />
      <!-- 上升箭头（强势/突破） -->
      <path
        d="M 52 150 L 78 120 L 94 128 L 126 76 L 118 68 L 140 52 L 150 76 L 140 74 L 124 92"
        fill="none"
        stroke="#ffffff"
        stroke-width="9"
        stroke-linecap="round"
        stroke-linejoin="round"
        opacity="0.92"
      />
      <!-- K 线影线 -->
      <line x1="80" y1="150" x2="80" y2="112" stroke="#ffffff" stroke-width="5" stroke-linecap="round" opacity="0.85" />
      <line x1="112" y1="122" x2="112" y2="82" stroke="#ffffff" stroke-width="5" stroke-linecap="round" opacity="0.85" />
      <!-- K 线实体：左跌（绿）→ 右涨（红） -->
      <rect x="68" y="120" width="24" height="30" rx="5" fill="#43cf7c" />
      <rect x="100" y="88" width="24" height="34" rx="5" fill="#ff4d4f" />
    </svg>
  </div>
</template>

<style scoped></style>
