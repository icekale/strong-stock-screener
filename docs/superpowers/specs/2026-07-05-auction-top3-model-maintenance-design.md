# 竞价 Top3 纳入模型维护设计

## 背景

当前 `/model-maintenance` 已能生成股是股非/GSGF 选股模型维护包，并调用配置的 AI 分析服务生成模型维护报告。但竞价 Top3 模型还没有进入维护包，导致早盘竞价模块虽然已经用于实战，却不能被同一套模型维护系统复盘和诊断。

页面交互也存在一个明显问题：按钮文案是“生成复盘包并分析”，实际会先生成维护包再调用 AI。如果 AI 配置缺失或调用失败，后端会降级为离线规则摘要，页面只显示报告，用户难以判断这次是否真的提交给 Codex、DeepSeek 或 OpenAI-compatible 服务分析。

## 目标

1. 模型维护包同时覆盖 GSGF 选股模型和竞价 Top3 模型。
2. 竞价 Top3 内容默认读取已有缓存，不在维护页重新运行竞价模型。
3. 页面从黑盒一键按钮改为清晰的两步流程：先生成维护包，再提交 AI 分析。
4. 页面明确显示本次分析是在线 AI 生成，还是离线规则摘要。
5. 生成维护包后提供可复制的维护包链接，方便用户直接把链接粘贴给 Codex 分析。
6. 支持可开关的竞价 Top3 训练样本闭环：记录每日 Top3 信号、模拟买卖结果、可选真实操作样本，用于后续模型诊断和训练。

## 非目标

- 不在模型维护页实时重算竞价 Top3。
- 不让 AI 自动修改竞价模型参数。
- 不把竞价回测、竞价复盘历史全部塞进第一版维护包。
- 不让 Web 应用直接控制 Codex Desktop 线程；第一版只提供可复制的维护包链接和可选提示词。
- 不改变现有 GSGF 模型维护报告和建议队列的核心行为。
- 不接入真实交易执行，不自动下单。
- 不把模拟交易结果等同于真实收益。
- 不把用户真实操作样本默认混入模型训练，必须由用户显式打开。

## 推荐方案

采用“统一维护包 + 分模型摘要 + 两步式提交”的方案。

后端继续使用 `ModelMaintenancePacket` 作为维护包入口，在其中新增竞价 Top3 摘要字段。旧字段继续服务 GSGF，新增字段只包含竞价模型必要信息和样本摘要。

竞价 Top3 训练闭环采用三层样本，默认只打开信号样本：

1. `信号样本`
   - 每天保存 Top3 模型选出的股票、分数、行业、信号、风险标签、特征版本和数据源状态。
   - 这是模型输入侧的固定快照，不能使用未来数据回填。

2. `模拟交易样本`
   - 可开关。
   - 按固定规则回放买入/卖出结果，例如 09:25 入选、09:30/09:35/10:00/收盘不同买点表现、止盈止损、次日溢价。
   - 提供可追踪的模拟收益状况，包括单笔收益、日度收益、累计收益曲线、最大回撤和分策略表现。
   - 用于评估模型选股质量，不代表真实交易收益。

3. `真实操作样本`
   - 可开关。
   - 用户手动记录是否买入、买入价、卖出价、仓位、买入理由、卖出原因。
   - 与模拟样本分开存储，避免把用户执行能力和模型选股能力混在一起。

前端把原来的“生成复盘包并分析”拆为两个主要动作：

1. `生成维护包`
   - 生成并保存最新维护包。
   - 页面展示维护包包含哪些模型、交易日、数据源状态、竞价 Top3 是否命中缓存。

2. `提交给 AI 分析`
   - 调用现有 `/api/model-maintenance/analyze`。
   - 页面展示实际 provider、model、是否离线降级。
   - 如果无法在线分析，明确提示“当前为离线规则摘要”。

同时新增 `复制 Codex 分析链接`。链接指向完整维护包阅读页或 JSON 端点，用户可以直接把链接粘贴给 Codex，让 Codex 基于同一份数据包分析。维护包不对业务数据做脱敏，但运行时密钥、API Key、通知 Token 等凭证永不写入维护包。

## 数据设计

### ModelMaintenancePacket 扩展

新增字段：

- `model_sections`
  - `gsgf`
    - `enabled`
    - `model_version`
    - `selected_count`
    - `risk_item_count`
    - `observation_item_count`
  - `auction_top3`
    - `enabled`
    - `available`
    - `trade_date`
    - `feature_end_date`
    - `model_version`
    - `feature_version`
    - `guard_rule`
    - `mode`
    - `cache_status`
    - `generated_at`
    - `top_count`
    - `watch_count`
    - `backtest_summary`
    - `items`
    - `source_status`
    - `notes`
  - `auction_top3_training`
    - `enabled`
    - `signal_sample_count`
    - `simulated_trade_sample_count`
    - `manual_trade_sample_count`
    - `simulated_profit_summary`
      - `portfolio_id`
      - `latest_equity`
      - `today_return_pct`
      - `cumulative_return_pct`
      - `max_drawdown_pct`
      - `win_rate`
      - `profit_loss_ratio`
      - `complete_sample_count`
      - `incomplete_sample_count`
      - `best_policy`
      - `worst_policy`
    - `date_range`
    - `training_window_days`
    - `latest_generated_at`
    - `quality_notes`

约束：

- `auction_top3.items` 只保留前 10 条摘要，不保存完整原始行情。
- 每条竞价样本只保留代码、名称、行业、分数、排序、主要信号、风险标签、关键特征摘要。
- 如果找不到竞价 Top3 缓存，`available=false`，并在 `notes` 和 `data_quality_notes` 中说明原因。
- 维护包不保存 API Key、运行时密钥、通知 Token。
- 维护包可保存完整业务分析上下文，但仍不保存完整 K 线和完整竞价全市场数据，避免文件体积失控。

### Top3 训练样本

新增训练样本存储，作为竞价复盘和模型维护之间的中间层。

字段：

- `AuctionTop3SignalSample`
  - `sample_id`
  - `trade_date`
  - `symbol`
  - `name`
  - `industry`
  - `rank`
  - `score`
  - `model_version`
  - `feature_version`
  - `guard_rule`
  - `signals`
  - `risk_flags`
  - `feature_snapshot`
  - `source_status`
  - `created_at`

- `AuctionTop3SimulatedTradeSample`
  - `sample_id`
  - `signal_sample_id`
  - `portfolio_id`
  - `entry_policy`: `open_0930 | after_0935_confirm | before_1000_strength | close_follow`
  - `entry_price`
  - `entry_time`
  - `exit_policy`: `intraday_stop | intraday_take_profit | close_exit | next_open_exit | next_close_exit`
  - `exit_price`
  - `exit_time`
  - `position_pct`
  - `return_pct`
  - `profit_amount`
  - `max_drawdown_pct`
  - `max_favorable_pct`
  - `label`: `win | loss | neutral | data_incomplete`
  - `created_at`

- `AuctionTop3SimulatedPerformancePoint`
  - `portfolio_id`
  - `trade_date`
  - `entry_policy`
  - `exit_policy`
  - `trade_count`
  - `win_count`
  - `loss_count`
  - `daily_return_pct`
  - `cumulative_return_pct`
  - `equity`
  - `max_drawdown_pct`
  - `created_at`

- `AuctionTop3ManualTradeSample`
  - `sample_id`
  - `signal_sample_id`
  - `enabled_for_training`
  - `bought`
  - `buy_price`
  - `sell_price`
  - `position_pct`
  - `buy_reason`
  - `sell_reason`
  - `return_pct`
  - `created_at`

约束：

- 信号样本只能保存当时可见数据，不能在盘后用未来表现改写信号特征。
- 模拟交易样本必须标记策略口径，避免不同买卖规则混在一起训练。
- 模拟收益追踪必须按 `entry_policy + exit_policy + portfolio_id` 分开统计，避免不同规则混算。
- 默认模拟账户本金使用配置值 `top3_simulated_initial_capital`，只用于收益曲线计算，不代表真实资金。
- 真实操作样本默认不进入训练集，只有 `enabled_for_training=true` 才能被统计。
- 训练数据用于模型维护和规则建议，不直接触发自动调参上线。

### AI 报告扩展

第一版不新增 `ModelMaintenanceReport` 顶层字段，避免扩大前后端改动面。AI 报告通过现有字段表达竞价模型诊断：

- `key_findings` 可包含竞价 Top3 的模型表现判断。
- `rule_diagnostics` 可加入 `auction_top3_*` 规则名。
- `suggestions` 可加入竞价模型相关建议。
- `summary` 明确说明本次覆盖了哪些模型。
- AI 报告可基于 `auction_top3_training` 总结 Top3 模型训练样本质量、样本量、胜率、亏损分布和需要补样的交易场景。

后续如果需要做多模型报告页，再引入独立的 `model_section_reports`。

## 后端设计

### 维护包生成

扩展 `build_model_maintenance_packet()`：

- 保留现有 GSGF 聚合逻辑。
- 新增可选入参 `auction_top3_run`。
- 生成 `model_sections.auction_top3`。
- 若竞价 Top3 缓存缺失，写入数据质量提示，不抛出错误。

扩展 `/api/model-maintenance/packets/generate`：

- 默认尝试读取同交易日或最近交易日的竞价 Top3 缓存。
- 只读缓存，不触发 `predict_top3()`。
- 返回维护包。
- 返回维护包访问链接 `packet_url`，用于页面一键复制给 Codex。

新增维护包读取端点：

- `GET /api/model-maintenance/packets/{packet_id}`
  - 返回完整维护包 JSON。
  - 不包含 API Key、运行时密钥、通知 Token、完整原始行情序列。
  - 适合 Codex 通过链接读取和分析。

- `GET /model-maintenance/packets/{packet_id}`
  - 前端阅读页，展示维护包摘要、包含模型、数据质量提示和复制 JSON 链接。
  - 方便用户人工检查后再复制给 Codex。

新增或复用读取逻辑：

- 优先读取 `trade_date` 对应竞价 Top3 缓存。
- 若没有筛选交易日，使用当前交易日或最近可用交易日。
- 若缓存不存在，维护包仍生成成功。

### AI 分析

扩展 AI prompt：

- 明确说明 packet 可能包含多个模型。
- 要求分别评价 GSGF 和竞价 Top3。
- 样本不足或缓存缺失时必须标记为样本不足，而不是编造结论。
- 建议必须保守，不允许直接输出买卖指令。

扩展离线规则摘要：

- 如果维护包包含竞价 Top3，离线报告也要给出基础诊断。
- 如果维护包包含 Top3 训练样本摘要，离线报告要提示样本量是否足够、模拟交易口径是否单一、真实操作样本是否启用。
- 如果 AI 不可用，报告的 `model` 保持可识别，例如 `offline-rule-summary`。

### Top3 训练样本任务

新增可开关的样本生成任务：

- `record_top3_signal_samples`
  - 默认开启。
  - 每次 Top3 模型结果生成后，保存当天 Top3 信号样本。

- `generate_top3_simulated_trade_samples`
  - 默认关闭。
  - 收盘后或次日读取行情结果，按固定买卖规则生成模拟交易样本。

- `include_manual_trade_samples_in_training`
  - 默认关闭。
  - 用户手动打开后，真实操作样本才进入训练统计。

- `top3_training_window_days`
  - 默认 60。
  - 控制维护包里训练样本统计窗口。

- `top3_simulated_initial_capital`
  - 默认 100000。
  - 用于计算模拟账户权益曲线。

- `top3_simulated_position_pct`
  - 默认 0.33。
  - 用于计算每只 Top3 股票的模拟仓位。

新增 API：

- `GET /api/model-maintenance/auction-top3/training/summary`
  - 返回 Top3 训练样本摘要。

- `POST /api/model-maintenance/auction-top3/training/generate`
  - 手动生成或刷新指定日期的模拟交易样本。

- `GET /api/model-maintenance/auction-top3/training/performance`
  - 返回模拟交易收益追踪，包括日度收益、累计收益、最大回撤、胜率、盈亏比和分策略表现。

- `POST /api/model-maintenance/auction-top3/manual-trades`
  - 保存用户真实操作样本。

- `PATCH /api/model-maintenance/auction-top3/manual-trades/{sample_id}`
  - 修改真实操作样本和是否进入训练集。

## 前端设计

### 页面流程

`/model-maintenance` 顶部增加流程卡：

1. `维护包`
   - 显示维护包 ID、生成时间、交易日。
   - 显示包含模型：`GSGF`、`竞价 Top3`。
   - 显示竞价 Top3 状态：`已纳入`、`无缓存`、`数据不足`。

2. `AI 分析`
   - 显示当前 AI 配置状态。
   - 显示上次报告 provider/model。
   - 如果是 `offline-rule-summary`，用醒目的说明提示这不是在线 AI 分析。

3. `Top3 训练数据`
   - 显示信号样本数、模拟交易样本数、真实操作样本数。
   - 显示模拟收益概览：累计收益、今日收益、最大回撤、胜率、盈亏比。
   - 显示模拟收益曲线，支持按买入策略和卖出策略切换。
   - 显示训练窗口天数。
   - 显示三个开关状态：记录信号样本、生成模拟交易样本、真实操作样本进入训练。
   - 提供 `生成/刷新 Top3 训练样本` 按钮。

4. `Codex 分析链接`
   - 维护包生成后显示只读链接。
   - 提供 `复制链接` 按钮。
   - 提供次要按钮 `复制带提示词的链接`，文案示例：`请打开这个维护包链接，分析 GSGF 和竞价 Top3 模型是否退化，并给出只观察不自动改规则的建议：{packet_url}`。

### 操作按钮

- `生成维护包`
- `提交给 AI 分析`
- `生成/刷新 Top3 训练样本`
- `复制 Codex 分析链接`
- `复制带提示词的链接`

保留一个次要入口 `生成并分析` 也可以，但默认视觉上强调两步流程，避免用户不知道下一步。

### 状态反馈

- 生成维护包成功：提示维护包已生成，显示“下一步：提交给 AI 分析”和可复制给 Codex 的维护包链接。
- 在线 AI 成功：显示 provider/model。
- 离线降级：显示“AI 未配置或调用失败，当前使用离线规则摘要”。
- 竞价缓存缺失：显示“竞价 Top3 无缓存，本次只维护 GSGF；请先在竞价页生成 Top3 模型结果”。
- Top3 训练样本生成成功：显示新增/更新样本数和训练窗口。
- 模拟收益追踪更新成功：显示最新累计收益、最大回撤和样本数量。
- 模拟交易样本关闭：显示“仅记录信号样本，暂不生成买卖回放结果”。

## 错误处理

- 竞价 Top3 缓存缺失不阻断维护包生成。
- AI 调用失败不覆盖上一份成功报告，但允许生成离线摘要。
- 页面必须区分“没有报告”“离线报告”“在线 AI 报告”。
- 维护包链接必须只读、可追溯。
- 维护包业务数据不脱敏；凭证类字段必须从源头排除，不能进入 packet。
- 复制 Codex 分析链接失败时显示明确错误。
- 训练样本生成失败不影响竞价 Top3 主功能。
- 行情缺失时，模拟交易样本标记 `data_incomplete`，不伪造买卖结果。
- 模拟收益追踪只统计完整样本，`data_incomplete` 样本单独计数。
- 重新生成同一日期模拟样本时，必须按 `trade_date + signal_sample_id + entry_policy + exit_policy` 去重覆盖，避免收益曲线重复累计。
- 真实操作样本保存失败时必须保留用户输入，不清空表单。

## 测试计划

### 后端

- 生成维护包时，存在竞价 Top3 缓存则包含 `model_sections.auction_top3.available=true`。
- 缓存缺失时，维护包仍成功，且写入数据质量提示。
- AI prompt 包含竞价 Top3 摘要。
- 离线分析能识别竞价 Top3 缓存状态。
- Top3 信号样本只保存当时特征快照，不使用未来表现。
- 模拟交易样本能按不同 entry/exit policy 生成独立结果。
- 模拟收益追踪能生成日度收益、累计收益、最大回撤和胜率。
- 同一日期重复刷新模拟样本不会重复累计收益。
- 真实操作样本默认不进入训练统计，打开后才计入。
- 维护包包含 `auction_top3_training` 摘要。
- 现有 GSGF 模型维护 API 测试继续通过。

### 前端

- `/model-maintenance` 显示维护包状态卡。
- 点击“生成维护包”后显示下一步提示。
- 生成维护包后显示可复制的维护包链接。
- 点击“提交给 AI 分析”后显示 provider/model。
- `offline-rule-summary` 时显示离线降级提示。
- 竞价 Top3 缓存缺失时显示可理解的说明。
- Top3 训练数据区显示开关状态、样本数和刷新按钮。
- Top3 训练数据区显示模拟收益概览和收益曲线。
- 关闭模拟交易样本时，页面显示只记录信号样本。
- 复制 Codex 分析链接按钮存在并可用。

## 实施顺序

1. 后端扩展维护包数据结构和 packet builder。
2. 后端接入竞价 Top3 缓存读取，不触发重算。
3. 后端新增 Top3 训练样本存储、统计和手动刷新 API。
4. 后端扩展 AI prompt 和离线摘要。
5. 前端新增维护包读取接口和状态卡。
6. 前端拆分“生成维护包”和“提交 AI 分析”。
7. 前端新增 Top3 训练数据区、维护包阅读页、Codex 分析链接复制。
8. 补充后端和前端测试。
