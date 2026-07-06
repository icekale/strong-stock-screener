# 竞价 Top3 实盘确认层设计

## 背景

竞价 Top3 模型当前使用 free-stockdb 的历史日 K 数据训练和生成候选，适合做五年训练、胜率赔率评估和 T+1 回测。但实盘早盘决策发生在 09:20-09:25，必须结合 TickFlow 实时行情确认开盘幅度、即时涨跌、成交额、换手、题材共振和走弱风险。

如果直接把 TickFlow 实时字段塞进现有模型，会造成训练特征和实盘特征不一致。第一版应避免重训模型，只在模型输出之后增加实时确认层，把 Top3 候选标记为可买、观察或放弃。

## 目标

- 保持 Top3 模型评分和排序逻辑不变。
- 用 TickFlow/竞价快照对模型候选做实盘确认。
- 给每个 Top3 候选输出 `可买`、`观察`、`放弃` 三档判断。
- 展示确认理由，例如高开过热、成交额不足、快速走弱、题材共振、流动性风险。
- 保存确认快照，作为后续训练真正竞价模型的样本来源。
- 不自动下单，不把确认结果等同于交易建议。

## 非目标

- 第一版不重训 Top3 模型。
- 第一版不把 TickFlow 实时字段加入训练特征。
- 第一版不自动改变 Top3 模型排序。
- 第一版不接入券商交易或自动下单。
- 第一版不承诺 TickFlow 缺失时仍能给出实盘确认，只能降级为观察或数据不足。

## 推荐方案

采用“模型候选 + 实时确认”的两层结构。

第一层是现有 Top3 模型：

- 输入：free-stockdb 历史日 K 特征。
- 输出：候选股票、概率分、bucket、流动性风险、历史回测摘要。
- 责任：决定哪些股票值得进入早盘观察池。

第二层是新增实盘确认层：

- 输入：Top3 模型候选、TickFlow 实时行情、竞价快照、行业/题材联动信息。
- 输出：每个候选的确认状态、实时指标、理由和数据质量。
- 责任：判断模型候选在今天竞价时点是否仍然适合行动。

确认层只做覆盖在模型输出上的解释和风控，不修改模型分数，不把候选从结果里删除。

## 确认状态

新增状态：

- `buyable`
  - 页面文案：`可买`
  - 含义：模型入选且实时信号通过，允许进入实盘计划。

- `watch`
  - 页面文案：`观察`
  - 含义：模型仍值得关注，但实时信号不完整或存在轻度风险。

- `reject`
  - 页面文案：`放弃`
  - 含义：实时风险明显，不适合按 Top3 策略行动。

默认策略是保守降级：数据缺失、TickFlow 异常、实时字段不足时标记为 `观察`，而不是 `可买`。

## 第一版规则

### 可买

候选满足以下条件时标记为 `可买`：

- Top3 bucket 为 `selected`。
- 没有模型硬风险，例如低流通市值或近 3 日日均成交额不足。
- TickFlow 有实时行情。
- 开盘幅度不过热，默认 `open_gap_pct < 7%`。
- 实时涨幅不弱于 0。
- 成交额或换手至少有一个通过确认：
  - `turnover_cny >= 100,000,000`
  - 或 `turnover_rate >= 3`
- 如果有题材/行业共振，增加确认理由，但不作为强制条件。

### 观察

以下情况标记为 `观察`：

- Top3 入选，但成交额或换手不足。
- 高开略偏热，但未达到强拒绝条件。
- TickFlow 数据缺失或延迟。
- 行业/题材信息缺失。
- 模型 bucket 不是 `selected`，但风险不明显。

### 放弃

以下情况标记为 `放弃`：

- 模型风险标记包含低流通市值或近 3 日日均成交额不足。
- `open_gap_pct >= 7%` 且没有强题材共振。
- 实时涨幅小于 0。
- 当前涨幅明显低于开盘幅度，默认 `current_pct_change <= open_gap_pct - 3`。
- TickFlow 返回异常或股票停牌/无法交易。

规则阈值先写成后端常量，后续根据样本再配置化。

## 后端设计

新增服务：`AuctionTop3LiveConfirmationService`。

输入：

- `AuctionModelTop3Response`
- `AuctionSnapshotResponse`
- 当前时间

输出：

- `AuctionTop3LiveConfirmationResponse`
  - `trade_date`
  - `generated_at`
  - `source_status`
  - `items`

每个 item 包含：

- `symbol`
- `name`
- `model_rank`
- `model_bucket`
- `prob_3pct`
- `confirmation`: `buyable | watch | reject`
- `confirmation_label`
- `realtime`
  - `last_price`
  - `current_pct_change`
  - `open_gap_pct`
  - `turnover_cny`
  - `turnover_rate`
  - `quote_time`
- `reasons`
- `risk_flags`
- `data_quality`

新增 API：

- `GET /api/auction/model/top3/live-confirmation?trade_date=YYYY-MM-DD`

行为：

- 默认读取 Top3 缓存，不重新生成 Top3。
- 读取最新竞价快照或实时快照。
- 按 symbol 合并模型候选和实时行情。
- 返回确认结果。
- 如果没有 Top3 缓存，返回 404。
- 如果 TickFlow 不可用，返回 200，但每个 item 标记为 `观察`，source_status 说明实时数据缺失。

## 前端设计

在 `/auction` 的“模型 Top3 试运行”板块增加实盘确认信息。

每个 Top3 item 显示：

- 当前确认状态标签：`可买`、`观察`、`放弃`
- 实时涨幅、开盘幅度、成交额、换手
- 2-3 条确认理由
- 数据质量提示

交互：

- 打开页面时先读取 Top3 缓存，再尝试读取实盘确认。
- `重新生成` Top3 后，自动刷新实盘确认。
- TickFlow 失败时，不让整块报错，只显示“实时确认不可用，按模型候选观察”。

## 数据记录

新增 `AuctionTop3LiveConfirmationStore`，存储目录：

`STRONG_STOCK_DATA_DIR/auction_top3_live_confirmations`

文件：

- `confirmations/YYYY-MM-DD.json`

保存内容：

- Top3 模型 run_id
- 每个候选的确认状态
- 实时指标快照
- 确认理由
- 数据源状态

这些样本只用于后续复盘和训练候选特征沉淀，不在第一版自动混入训练。

## 测试

后端测试：

- Top3 selected + 实时信号通过时返回 `buyable`。
- 高开过热时返回 `reject`。
- 成交额不足时返回 `watch`。
- TickFlow/竞价快照缺失时返回 `watch` 并带数据质量说明。
- API 默认读取 Top3 缓存，不触发 Top3 重新生成。

前端测试：

- Top3 卡片显示确认状态。
- 实时确认失败时不覆盖模型结果。
- `重新生成` 后会刷新确认结果。

## 风险与约束

- TickFlow 在 09:25 附近可能延迟或缺字段，确认层必须显示数据质量。
- 现有模型仍是日 K 特征模型，确认层不能被误解为已训练过集合竞价特征。
- 规则阈值来自经验，必须通过后续样本复盘调整。
- 实盘确认只是决策辅助，不做自动交易。

## 成功标准

- Top3 板块能在早盘直接看到 `可买 / 观察 / 放弃`。
- 当 TickFlow 可用时，每个模型候选都有实时指标和确认理由。
- 当 TickFlow 不可用时，页面仍能展示模型候选，并明确提示实时确认缺失。
- 后端测试覆盖确认规则和 API 缓存行为。
- 不改变现有 Top3 模型结果和回测统计。
