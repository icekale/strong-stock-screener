# 个股 K 线旧版功能恢复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Soybean Vue 个股页保留当前 UI 的同时，恢复旧版 K 线周期、指标、多副图、缩放交互、标注和信息视图，并确保分钟周期使用真实分钟数据。

**Architecture:** 后端扩展现有个股 K 线接口，让日 K 走日线 provider、分钟周期复用 TickFlow 分钟数据和现有闭合聚合逻辑；前端继续使用 ECharts，在 Vue 内实现旧版的指标状态、多网格布局和 overlay 语义。StockView 负责周期和请求状态，StockKlineChart 负责图表 option，独立工具模块负责周期聚合和指标计算。

**Tech Stack:** FastAPI、Pydantic、TickFlow provider、Vue 3、TypeScript、Ant Design Vue、ECharts、Vitest、Pytest。

---

## 文件边界

- 后端 API 与缓存：`apps/api/app/main.py`、`apps/api/app/models.py`
- 后端验证：`apps/api/tests/test_api.py`、`apps/api/tests/test_chanlun_bars.py`
- Vue API 类型和请求：`apps/web-vue/src/service/types.ts`、`apps/web-vue/src/service/product-api.ts`、`apps/web-vue/src/service/api.test.ts`
- 周期与指标计算：新增 `apps/web-vue/src/utils/charts/klinePeriod.ts`、`apps/web-vue/src/utils/charts/klineIndicators.ts`
- 指标状态和 option：`apps/web-vue/src/utils/charts/klineIndicatorLayout.ts`、`apps/web-vue/src/utils/charts/klineOverlayOption.ts`、`apps/web-vue/src/utils/charts/chartOptions.test.ts`
- 图表实例能力：`apps/web-vue/src/components/charts/EChart.vue`、`apps/web-vue/src/components/charts/StockKlineChart.vue`
- 页面控制与旧版内容迁移：`apps/web-vue/src/views/StockView.vue`
- 页面请求与持久化纯状态：新增 `apps/web-vue/src/utils/domain/stockViewState.ts`
- Vue 构建与类型检查：`apps/web-vue/package.json`

### Task 1: 扩展个股 K 线后端周期契约

**Files:**
- Modify: `apps/api/app/models.py` (`StockKlineResponse`)
- Modify: `apps/api/app/main.py` (`get_stock_kline`, `_cached_stock_kline`)
- Test: `apps/api/tests/test_api.py`
- Test: `apps/api/tests/test_chanlun_bars.py`

- [ ] **Step 1: 写失败测试，锁定周期参数、响应周期和缓存隔离**

  在 `test_api.py` 增加三个测试：

  - 请求 `GET /api/stocks/603890.SH/kline?count=5&period=1d` 返回 `period == "1d"`，provider 收到日 K 请求。
  - 请求 `period=30m` 使用分钟 provider，返回的每根柱的 `date` 为时间戳格式，且不把日 K 返回给前端。
  - 连续请求同一股票的 `1d` 与 `30m` 后，provider 调用次数和缓存结果相互独立；重复请求相同 `period/count` 命中缓存。

  在 `test_chanlun_bars.py` 增加缺少完整分钟柱时不返回未闭合柱的断言，覆盖 5m、30m、60m 中至少一个跨午间交易时段的样本。

- [ ] **Step 2: 运行失败测试并确认失败原因**

  Run:

  ```bash
  cd /Users/kale/Documents/strong-stock-screener/apps/api
  pytest -q tests/test_api.py -k stock_kline tests/test_chanlun_bars.py
  ```

  Expected: 新增断言失败，原因是响应没有 `period`，接口没有读取 `period` 查询参数，或缓存仍只按 symbol/count 区分。

- [ ] **Step 3: 实现最小后端改动**

  - 在 `models.py` 增加 `StockKlinePeriod = Literal["1d", "60m", "30m", "5m"]`，给 `StockKlineResponse` 增加 `period` 字段。
  - 将 endpoint 签名改为 `get_stock_kline(symbol, count=220, period="1d")`，对非法周期返回 422，并继续限制 count。
  - 将 `_cached_stock_kline` 签名改为 `(symbol, count, period)`，缓存键按 provider、symbol、period、count 组成。
  - `1d` 调用 `_kline_provider().get_klines`；分钟周期调用现有 quote provider 的 `get_intraday_bars([symbol], period=period, count=...)`，使用 `aggregate_closed_intraday_bars(..., now=datetime.now(SHANGHAI))`，只保留最后 count 根。
  - source status 明确写出 `TickFlow 30分钟K`、`返回 N 条已闭合分钟K` 等实际口径；空结果保留 success/insufficient detail，不回退到日 K。
  - GSGF 日 K 标注只在 `period == "1d"` 生成，分钟 K 返回空标注。

- [ ] **Step 4: 运行后端测试并确认通过**

  Run:

  ```bash
  cd /Users/kale/Documents/strong-stock-screener/apps/api
  pytest -q tests/test_api.py -k stock_kline tests/test_chanlun_bars.py
  ```

  Expected: 新增测试及原有相关测试全部通过。

- [ ] **Step 5: 提交后端周期契约**

  ```bash
  cd /Users/kale/Documents/strong-stock-screener
  git add apps/api/app/main.py apps/api/app/models.py apps/api/tests/test_api.py apps/api/tests/test_chanlun_bars.py
  git commit -m "feat: expose period-aware stock kline data"
  ```

### Task 2: 迁移 Vue 数据类型、周期聚合和指标计算

**Files:**
- Modify: `apps/web-vue/src/service/types.ts`
- Modify: `apps/web-vue/src/service/product-api.ts`
- Modify: `apps/web-vue/src/service/api.test.ts`
- Create: `apps/web-vue/src/utils/charts/klinePeriod.ts`
- Create: `apps/web-vue/src/utils/charts/klineIndicators.ts`
- Test: `apps/web-vue/src/utils/charts/klinePeriod.test.ts`
- Test: `apps/web-vue/src/utils/charts/klineIndicators.test.ts`

- [ ] **Step 1: 写失败测试，定义前端请求和计算边界**

  - 在 `api.test.ts` 断言 `getStockKline("600000.SH", { count: 120, period: "30m" })` 请求 `/api/stocks/600000.SH/kline?count=120&period=30m`。
  - 在 `klinePeriod.test.ts` 断言日 K 聚合成周 K 时，周一到周五合并为一根，open 取第一根、close 取最后一根、high/low 取极值、volume/amount 求和；输入按时间排序且不足一根时返回空数组。
  - 在 `klineIndicators.test.ts` 断言 MACD、KDJ、RSI、WR、BIAS、CCI、ATR、OBV、ROC、DMI 和砖形图对固定 40 根样本返回与 bars 等长的序列，并在前置数据不足位置返回 null 而不是 NaN/Infinity。

- [ ] **Step 2: 运行失败测试**

  ```bash
  cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
  pnpm exec vitest run src/service/api.test.ts src/utils/charts/klinePeriod.test.ts src/utils/charts/klineIndicators.test.ts
  ```

  Expected: 新测试因请求签名、文件或计算函数不存在而失败。

- [ ] **Step 3: 实现周期聚合和指标计算**

  - `getStockKline` 接受 `{ count?: number; period?: StockKlinePeriod }`，保留旧的数值第二参数兼容调用，并序列化 query 参数。
  - `klinePeriod.ts` 提供 `aggregateWeeklyBars(bars)`，按上海交易日的周一日期分组，保留每组最后一根的 MA 字段为 null，避免把未重新计算的均线展示成错误值。
  - `klineIndicators.ts` 提供纯函数：`calculateMacd`、`calculateKdj`、`calculateRsi`、`calculateWr`、`calculateBias`、`calculateCci`、`calculateAtr`、`calculateObv`、`calculateRoc`、`calculateDmi`、`calculateBrick`。所有输出只读取当前及历史 bars，不读取未来数据；初始窗口返回 null。
  - 为每个指标统一返回 `{ name, values, lines? }` 的内部结构，供 option builder 映射为 ECharts series，避免把计算逻辑塞进 Vue 组件。

- [ ] **Step 4: 运行前端计算测试并确认通过**

  ```bash
  cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
  pnpm exec vitest run src/service/api.test.ts src/utils/charts/klinePeriod.test.ts src/utils/charts/klineIndicators.test.ts
  ```

  Expected: 请求参数、周线聚合和全部指标序列测试通过，输出无 NaN/Infinity 断言失败。

- [ ] **Step 5: 提交数据和指标基础能力**

  ```bash
  cd /Users/kale/Documents/strong-stock-screener
  git add apps/web-vue/src/service apps/web-vue/src/utils/charts/klinePeriod.ts apps/web-vue/src/utils/charts/klinePeriod.test.ts apps/web-vue/src/utils/charts/klineIndicators.ts apps/web-vue/src/utils/charts/klineIndicators.test.ts
  git commit -m "feat: add vue kline periods and indicators"
  ```

### Task 3: 恢复 Vue ECharts 多副图和交互

**Files:**
- Modify: `apps/web-vue/src/utils/charts/klineIndicatorLayout.ts`
- Modify: `apps/web-vue/src/utils/charts/klineOverlayOption.ts`
- Modify: `apps/web-vue/src/components/charts/EChart.vue`
- Modify: `apps/web-vue/src/components/charts/StockKlineChart.vue`
- Modify: `apps/web-vue/src/utils/charts/chartOptions.test.ts`

- [ ] **Step 1: 写失败 option 和实例能力测试**

  - 断言 1/2/3 图分别生成 2/3/4 个 grid、xAxis、yAxis，并且所有 grid 使用同一份 dataZoom xAxisIndex。
  - 断言 MACD/KDJ/RSI 等副图生成正确的 line/bar series，砖形图生成独立 candlestick series；主图仍包含 K 线和选中的 MA。
  - 断言 overlay 只挂在主图，`visibleBarCount` 变化时标注仍按当前日期索引映射。
  - 断言 `EChart` 通过 `ref` 暴露 `resize()` 和 `restore()`，且不改变 props option 的只读语义。

- [ ] **Step 2: 运行失败测试**

  ```bash
  cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
  pnpm exec vitest run src/utils/charts/chartOptions.test.ts
  ```

  Expected: 当前 option 只有主图/成交量，无法通过 2/3 图和副图 series 断言。

- [ ] **Step 3: 实现 option builder 和 EChart ref**

  - `buildKlineOverlayOption` 接收 `subIndicators` 全数组，按旧版 76/18、62/16、52/14 的比例生成 grid，并为每个副图生成独立 axis。
  - 成交量使用上涨/下跌颜色区分；线型指标使用各自名称、颜色、legend/tooltip 值，所有 series 的 null 值不连接。
  - brick 指标复用 `calculateBrick`，使用当前副图的 x/y axis，不影响主 K 线坐标。
  - dataZoom 的 inside/slider 同步主图和所有副图；tooltip 使用 axis/cross，显示当前 K 线和各副图值。
  - `EChart.vue` 使用 `defineExpose({ resize, restore })`，restore 调用 `dispatchAction({ type: "dataZoom", start: 0, end: 100 })`；组件卸载时断开 observer 和 dispose。
  - `StockKlineChart.vue` 以 bars、period、subIndicators、movingAverages、chanlun 为 key 输入，空 bars/加载/失败均显示稳定状态，不复用上一个周期的 option。

- [ ] **Step 4: 运行图表测试和类型检查**

  ```bash
  cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
  pnpm exec vitest run src/utils/charts/chartOptions.test.ts
  pnpm typecheck
  ```

  Expected: option 测试通过，`vue-tsc` 返回 0。

- [ ] **Step 5: 提交图表能力**

  ```bash
  cd /Users/kale/Documents/strong-stock-screener
  git add apps/web-vue/src/utils/charts/klineIndicatorLayout.ts apps/web-vue/src/utils/charts/klineOverlayOption.ts apps/web-vue/src/components/charts/EChart.vue apps/web-vue/src/components/charts/StockKlineChart.vue apps/web-vue/src/utils/charts/chartOptions.test.ts
  git commit -m "feat: restore vue kline multi-pane chart"
  ```

### Task 4: 迁移 StockView 控制栏和旧版内容视图

**Files:**
- Modify: `apps/web-vue/src/views/StockView.vue`
- Modify: `apps/web-vue/src/utils/charts/klineIndicatorLayout.ts` (only if state defaults need alignment)
- Create: `apps/web-vue/src/utils/domain/stockViewState.ts`
- Test: `apps/web-vue/src/utils/domain/stockViewState.test.ts`

- [ ] **Step 1: 写失败页面状态测试**

  新建 `stockViewState.test.ts`，针对纯函数写四个断言：`buildStockViewDefaults()` 返回 `visibleMovingAverages: ["ma5", "ma10", "ma20"]`、`paneCount: 1`、`subIndicators: ["volume"]`；`nextStockRequestId()` 递增且 `isLatestStockRequest(id, current)` 只接受最新 id；`buildStockKlineQuery({ period: "30m", count: 220 })` 同时返回行情和缠论请求需要的 `period/lookback`；`serializeIndicatorState/parseIndicatorState` 对非法 JSON 回退到 1 图成交量。

  将这些纯函数接入 `StockView.vue`，使页面测试不依赖 DOM 或源码字符串。

- [ ] **Step 2: 运行失败测试**

  ```bash
  cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
  pnpm exec vitest run src/utils/domain/stockViewState.test.ts
  ```

  Expected: 新增测试因纯状态函数不存在而失败。

- [ ] **Step 3: 实现页面迁移**

  - 将 `StockView.vue` 的周期状态拆成 `StockKlinePeriod` 与 `"weekly"` 显示态；周线使用 `aggregateWeeklyBars`，其他周期直接使用 API bars。
  - 为每次加载生成递增 request id 或取消标记；只有最新请求才能写入 bars、quote、chanlun、error。
  - 恢复指标控制：MA5/10/20/60 开关、1/2/3 图 segmented、每个副图独立 select、GSGF/缠论 switch；localStorage 在 mounted 读取，watch 状态保存。
  - 将 `StockKlineChart` 的 height 提升为当前布局可用的稳定高度，并让图表区域在桌面和窄屏都不被页面 footer 遮挡。
  - 在当前 Soybean 卡片内加入“日线/周线/分钟线”视图切换及信息、战法、概念三个 tab；研究 API 只在对应 tab 首次进入时读取，内容使用当前 `a-card/a-descriptions/a-tag` 风格。
  - 对周期失败显示数据源、周期、失败原因；行情摘要失败不清空已成功的 K 线，K 线失败不清空已成功的报价。

- [ ] **Step 4: 运行前端测试和构建**

  ```bash
  cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
  pnpm exec vitest run
  pnpm typecheck
  pnpm build
  ```

  Expected: 单元测试通过，类型检查和生产构建均返回 0。

- [ ] **Step 5: 运行页面状态和图表回归**

  ```bash
  cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
  pnpm exec vitest run src/utils/domain/stockViewState.test.ts src/utils/charts/chartOptions.test.ts
  pnpm typecheck
  ```

  Expected: 页面状态、图表 option 和类型检查全部通过。

- [ ] **Step 6: 提交个股页迁移**

  ```bash
  cd /Users/kale/Documents/strong-stock-screener
  git add apps/web-vue/src/views/StockView.vue apps/web-vue/src/utils/domain/stockViewState.ts apps/web-vue/src/utils/domain/stockViewState.test.ts apps/web-vue/src/utils/charts/klineIndicatorLayout.ts apps/web-vue/src/utils/charts/chartOptions.test.ts
  git commit -m "feat: restore stock workbench controls"
  ```

### Task 5: 真实行情验收和回归

**Files:**
- Verify: `apps/api/app/main.py`, `apps/web-vue/src/views/StockView.vue`, `apps/web-vue/src/components/charts/StockKlineChart.vue`
- Verify: all tests and build outputs

- [ ] **Step 1: 启动本地 Vue 预览并连接真实 API**

  ```bash
  cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
  VITE_API_BASE_URL=http://192.168.5.28:3110 pnpm dev --host 127.0.0.1 --port 3122
  ```

- [ ] **Step 2: 用浏览器验收 600000.SH**

  打开 `http://127.0.0.1:3122/stock/600000.SH?name=浦发银行&industry=银行`，逐项确认：

  - 日线、周线、60m、30m、5m 的最后一根柱时间格式和数量不同，分钟周期不会显示日线日期。
  - 选择 3 图后同时存在成交量/MACD/KDJ 三个副图，切换其中一个指标不会改变其他副图。
  - MA5/10/20 默认显示，MA60 可开关；刷新页面后布局保持。
  - 鼠标滚轮、拖动、底部缩放条、重置按钮、窗口改变宽度都不报错且主副图同步。
  - GSGF/缠论开关只在有对应数据时启用，切换周期不残留旧周期标注。
  - 信息、战法、概念 tab 可打开，K 线首屏不等待研究接口。

- [ ] **Step 3: 检查浏览器和 API 日志**

  确认浏览器 console 没有未处理异常、ECharts dispose/resize 警告和 Vue key 警告；确认 API 对每个周期只发起对应请求，失败时响应状态和页面提示一致。

- [ ] **Step 4: 运行完整回归命令**

  ```bash
  cd /Users/kale/Documents/strong-stock-screener/apps/api
  pytest -q
  cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
  pnpm exec vitest run
  pnpm typecheck
  pnpm build
  ```

  Expected: API pytest、Vue Vitest、Vue typecheck、Vue production build 全部成功；若仓库已有与本功能无关的失败，记录具体测试名，不修改无关代码。

- [ ] **Step 5: 生成最终变更检查**

  ```bash
  cd /Users/kale/Documents/strong-stock-screener
  git diff --check HEAD~4..HEAD
  git status --short --branch
  ```

  确认只包含本功能提交和设计/计划文档，工作区里原有的其他未提交修改保持原样；完成后再决定是否合并、推送和更新 Unraid。
