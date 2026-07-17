# 个股 K 线旧版功能恢复设计

## 目标

在 Soybean Vue 页面外壳中恢复旧版个股工作台的 K 线功能和交互语义，同时保留当前版本的字体、颜色、导航、统计摘要和卡片视觉。此次调整解决两个已确认的问题：分钟周期当前仍请求日 K，以及当前 Vue 图表只支持一个副图。

## 当前证据

- `apps/web-vue/src/views/StockView.vue` 对所有周期调用 `getStockKline(symbol, 220)`，没有把周期传给 K 线接口。
- 当前 `StockKlineChart` 只有主图和可选成交量网格；个股页仅绑定 `subIndicators[0]`。
- 旧版 `TickFlowKlineChart` 已有 MA 开关、1/2/3 副图布局、指标选择、指标布局本地持久化、周线聚合、GSGF 证据和缠论叠加的实现与测试。
- 现有后端已经有 TickFlow 分钟数据获取及 5/30/60 分钟闭合 K 线聚合逻辑，应复用这套逻辑，避免另造周期算法。

## 范围

### 保留当前 UI

- Soybean AppShell、侧边栏、顶部标签、字体、主题色和页面背景不变。
- 当前个股页的行情摘要卡片、最新价/涨跌幅/成交额/换手率和“打开缠论工作台”入口保留。
- 控件继续使用 Ant Design Vue 和当前紧凑卡片风格，不恢复旧版 React 的页面布局。

### 恢复旧版功能

1. K 线周期：日线、周线、60 分钟、30 分钟、5 分钟。
   - 日线由日 K 数据源提供。
   - 周线由日线在前端按交易周聚合，行为与旧版一致。
   - 60/30/5 分钟由后端返回对应的已闭合周期数据。
2. 主图指标：MA5、MA10、MA20、MA60 可分别开关；默认显示 MA5、MA10、MA20，MA60 默认关闭。
3. 副图布局：1 图、2 图、3 图；每个副图独立选择成交量、MACD、KDJ、RSI、WR、BIAS、CCI、ATR、OBV、ROC、DMI、砖形图。
4. 图表交互：十字光标、Tooltip、滚轮缩放、拖动、底部缩放条、重置视图和自适应尺寸。
5. 标注：GSGF 证据和缠论结构可分别开关；标注必须随周期和缩放窗口映射到当前 X 轴，不得使用日线日期硬套分钟线。
6. 内容视图：保留并迁移旧版的信息、战法、概念三类内容，以当前 Vue 卡片和排版呈现。
7. 指标布局保存：沿用旧版存储键 `strong-stock-screener:kline-indicator-layout`，非法或过期值回退到 1 图 + 成交量。

## 设计

### 数据流

```text
StockView 周期选择
  -> getStockKline(symbol, count, period)
  -> GET /api/stocks/{symbol}/kline?count=...&period=...
  -> 日 K provider 或 TickFlow intraday provider
  -> 已闭合 5/30/60 分钟 K 线
  -> KlineBar[] + source_status + period
  -> Vue ECharts 多网格图表
```

后端的周期聚合复用 `apps/api/app/services/chanlun/bars.py` 及现有 TickFlow provider。未闭合的当前分钟柱不进入结构分析和图表历史序列；没有足够数据时返回成功响应和明确的 `source_status`，由前端显示“数据不足/待确认”，而不是把日 K 当作分钟 K。

### API 契约

- `GET /api/stocks/{symbol}/kline` 新增 `period=1d|60m|30m|5m`，默认 `1d`，`count` 继续限制在现有安全范围。
- `StockKlineResponse` 增加 `period` 字段，响应中的 `source_status.detail` 必须说明实际周期和返回数量。
- 缓存键必须包含 provider、symbol、period、count，避免切换周期复用错误数据。
- 前端周线不新增后端周期；以日 K 聚合后生成周线，并沿用日 K 的来源状态。

### Vue 图表

- 扩展 `StockKlineChart` 和 `buildKlineOverlayOption`，让主网格和 1-3 个副网格由同一份指标状态生成。
- 主图使用 candlestick、均线、GSGF/缠论 overlay；副图使用与旧版一致的高度比例和指标顺序。
- `brick` 使用现有砖形指标计算逻辑迁移到 Vue chart option，不注册为原生指标。
- `EChart` 暴露 resize、restore-data、dataZoom 需要的实例能力，窗口变化时只 resize，不重新请求数据。
- 图表 key 至少包含 symbol、period、bar 数量和最后一根 K 线的时间/价格，切换周期或股票时清理旧 overlay。

### 页面交互

- 在当前“K 线与结构”卡片内恢复旧版控制栏：周期、均线、证据/缠论开关、副图数量和每个副图的指标选择。
- 当切换周期时并发加载行情、报价和缠论分析；旧请求返回后不得覆盖新周期状态。
- 研究数据只在信息/战法/概念视图首次进入时加载，避免打开页面时阻塞 K 线首屏。
- 分钟周期不可用时保留行情摘要，并在图表区域显示具体数据源失败原因。

## 测试与验收

### 后端

- API 测试验证 `period` 参数被传递到正确 provider。
- 测试缓存键区分 `1d`、`5m`、`30m`、`60m`。
- 测试分钟 K 线只包含闭合柱，返回的 `period` 和来源详情正确。
- 现有个股日 K、缠论和 provider 测试全部通过。

### 前端

- 指标状态测试覆盖 1/2/3 图、非法本地状态、每个副图独立指标和 MA 默认值。
- 图表 option 测试覆盖主图、副图网格、各指标 series、缩放轴同步和 overlay 周期映射。
- Vue 类型检查、单元测试和生产构建通过。
- 使用真实 `600000.SH` 验收：日/周/60m/30m/5m 切换得到不同时间粒度；切换到 3 图后同时显示三个副图；缩放和返回页面后状态不丢失；无控制台错误。

## 非目标

- 不迁移旧 React AppShell、候选股左侧列表或旧版页面布局。
- 不把 React runtime、`kline-charts-react` 或旧 Next 路由引入 Vue 应用。
- 不在本次工作中修改缠论算法、背驰判定、选股模型或交易下单逻辑；只消费其已有分析结果并修复展示与周期数据边界。

