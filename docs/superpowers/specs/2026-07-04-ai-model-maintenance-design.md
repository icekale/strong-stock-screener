# AI 模型维护分析设计

## 背景

当前系统已经具备股是股非模型的自动化维护底座：

- 每次筛选可保存 GSGF 信号快照。
- 每日收盘后可自动复查历史信号表现。
- 每周可运行真实样本校准。
- 设置页已有自动快照、每日复盘、每周校准和通知开关。

但这些结果目前主要是统计表和诊断面板。用户需要自己理解命中率、回撤、分桶、退化信号，再判断模型是否该调整。实际使用中，这会让模型维护显得复杂，也会让主页上的“模型诊断”不适合日常选股。

本设计目标是新增一层 AI 分析器：后端先生成结构化模型复盘包，再调用 Codex/OpenAI、DeepSeek 或 OpenAI-compatible 服务进行二级分析，最终产出模型维护报告和待确认建议队列。

## 目标

1. 模型维护更自动化：系统自动生成可供 AI 分析的结构化复盘包。
2. AI 负责解释统计结果、归因规则表现、发现潜在退化和生成自然语言建议。
3. 策略调整保持半自动：AI 只生成建议，不直接修改模型权重或过滤规则。
4. 主页保持简单：只显示模型健康状态和待确认建议数量。
5. 独立模型维护页面承载报告、建议队列、任务状态和历史分析。
6. 支持 Codex/OpenAI、DeepSeek 和自定义 OpenAI-compatible 接口。

## 非目标

- 不让 AI 参与实时筛选排序主路径。
- 不让 AI 自动下单或直接给买卖指令。
- 不让 AI 自动修改模型参数。
- 不把每日市场复盘项目重新合并进选股工作台。
- 不在页面加载时自动调用大模型，避免慢、贵、不可控。

## 推荐方案

采用半自动模型维护闭环：

1. 后台自动复盘和校准生成结构化结果。
2. 后端把结果整理成标准 `ModelMaintenancePacket`。
3. AI 分析器读取 packet，生成 `ModelMaintenanceReport`。
4. 报告中包含自然语言摘要、证据、规则诊断和建议队列。
5. 用户在模型维护页确认、忽略或延后建议。
6. 被确认的建议先只写入“待应用配置变更”，不立即静默改策略。

## 数据结构

### ModelMaintenancePacket

用于给 AI 的结构化输入。第一版保存 JSON 文件，避免每次重新聚合。

字段：

- `packet_id`
- `generated_at`
- `trade_date`
- `model_name`: `gsgf`
- `model_version`
- `screen_strategy`
- `screen_params`
- `source_status`
- `latest_screen_run`
  - `result_hash`
  - `candidate_pool_hash`
  - `candidate_count`
  - `selected_count`
- `review_summary`
  - `windows`
  - `sample_count`
  - `hit_rate_by_signal`
  - `avg_return_by_signal`
  - `max_drawdown_by_signal`
- `calibration_summary`
  - `buckets`
  - `diagnostic_groups`
  - `unique_symbol_buckets`
- `false_negative_cases`
  - 被过滤但后续上涨的样本。
- `false_positive_cases`
  - 入选但后续表现差或回撤大的样本。
- `data_quality_notes`
  - TickFlow、iFinD、fallback、缺失样本、请求失败。

约束：

- 不保存完整 K 线序列。
- 不保存 API Key。
- 控制体积，默认只保留 Top evidence 样本。
- 对 AI 输入做脱敏和裁剪。

### ModelMaintenanceReport

AI 输出结果经过后端校验后保存。

字段：

- `report_id`
- `packet_id`
- `provider`: `openai | deepseek | openai_compatible`
- `model`
- `generated_at`
- `health_status`: `normal | watch | degraded | insufficient_sample | data_unreliable`
- `summary`
- `key_findings`
- `rule_diagnostics`
  - `rule_name`
  - `status`: `effective | neutral | over_strict | under_strict | degraded | insufficient_sample`
  - `evidence`
  - `confidence`
- `suggestions`
  - `suggestion_id`
  - `type`: `observe | adjust_weight | loosen_filter | tighten_filter | disable_rule_temporarily | data_check`
  - `title`
  - `reason`
  - `evidence_refs`
  - `risk`
  - `confidence`
  - `suggested_action`
  - `status`: `pending | accepted | ignored | snoozed`
- `disclaimer`

AI 输出必须是 JSON。后端验证失败时保存错误，不覆盖上一份成功报告。

## AI 调用设计

### Provider 配置

设置页新增“AI 分析服务”配置：

- `ai_analysis_enabled`
- `ai_provider`: `openai | deepseek | openai_compatible`
- `ai_base_url`
- `ai_api_key`
- `ai_model`
- `ai_timeout_seconds`
- `ai_temperature`: 默认 0.2
- `ai_max_tokens`
- `ai_run_after_daily_review`
- `ai_run_after_weekly_calibration`
- `ai_notify_on_report`

DeepSeek 通过 OpenAI-compatible adapter 接入，但 UI 上保留 DeepSeek 作为明确选项。

### 调用时机

第一版支持三种触发方式：

1. 每日复盘完成后自动触发 AI 分析。
2. 每周校准完成后自动触发 AI 分析。
3. 模型维护页手动点击“重新分析”。

不在选股按钮点击后同步调用 AI。

### Prompt 约束

系统提示强调：

- 这是 A 股短线模型维护，不是交易建议。
- 只能基于 packet 内证据输出。
- 不能编造数据。
- 样本不足时必须标记 `insufficient_sample`。
- 数据源异常时必须标记 `data_unreliable`。
- 不允许输出“必涨”“买入卖出”等确定性交易指令。
- 建议必须保守，默认观察优先。

## 后端模块

新增或扩展：

- `services/model_maintenance_packet.py`
  - 聚合 review、calibration、screen run、source status。
  - 生成 packet JSON。
- `services/ai_model_analysis.py`
  - Provider adapter。
  - Prompt 构造。
  - JSON 解析和 Pydantic 校验。
  - 错误和超时处理。
- `services/model_maintenance_store.py`
  - 保存 reports 和 suggestions。
  - 更新建议状态。
- `main.py`
  - 新增 API。
- `runtime_settings.py`
  - 新增 AI 分析配置。

新增 API：

- `POST /api/model-maintenance/packets/generate`
- `GET /api/model-maintenance/packets/latest`
- `POST /api/model-maintenance/analyze`
- `GET /api/model-maintenance/reports/latest`
- `GET /api/model-maintenance/reports`
- `POST /api/model-maintenance/suggestions/{suggestion_id}/accept`
- `POST /api/model-maintenance/suggestions/{suggestion_id}/ignore`
- `POST /api/model-maintenance/suggestions/{suggestion_id}/snooze`

## 前端设计

### 主页

主页移除复杂“模型诊断”面板，只保留一行轻状态：

- `模型状态：正常 / 观察 / 退化 / 样本不足 / 数据不可靠`
- `上次分析时间`
- `待确认建议数量`
- `查看模型维护`

如果 AI 未配置：显示 `AI 分析未配置`，链接到设置页。

### 模型维护页 `/model-maintenance`

页面结构：

1. 顶部健康卡
   - 当前模型状态。
   - 最新复盘时间。
   - 最新 AI 分析时间。
   - 数据可信度。

2. AI 分析报告
   - 摘要。
   - 关键发现。
   - 风险提示。
   - 重新分析按钮。

3. 建议队列
   - 待确认建议。
   - 每条建议显示原因、证据、风险、置信度。
   - 操作：接受、忽略、延后。

4. 规则表现
   - 有效规则。
   - 过严规则。
   - 退化规则。
   - 样本不足规则。

5. 任务与配置入口
   - 每日复盘状态。
   - 每周校准状态。
   - AI provider 状态。
   - 跳转设置页。

## 建议执行语义

第一版“接受建议”不直接改模型规则，只保存用户决策：

- `accepted` 表示用户认可建议。
- 后续版本再做“配置变更草案”。
- 如果建议类型是 `data_check`，接受后只标记需要检查数据源。

这样避免 AI 自动改策略导致不可追溯。

## 通知

当 AI 生成报告后，可通过 Telegram/企业微信/飞书/邮件发送摘要：

- 模型健康状态。
- 1-3 条关键发现。
- 待确认建议数量。
- 模型维护页链接。

通知必须包含：

`仅供模型复盘与参数维护参考，不构成投资建议。`

## 错误处理

- AI Key 未配置：不触发自动分析，页面显示配置提示。
- AI 超时：保存 failed report status，不覆盖最新成功报告。
- AI 输出非 JSON：保存原始错误摘要，提示重新分析。
- packet 样本不足：仍生成报告，但状态为 `insufficient_sample`。
- 数据源异常：状态为 `data_unreliable`，建议优先检查数据源。
- 通知失败：不影响报告保存。

## 性能与成本控制

- AI 分析只读结构化 packet，不读全量历史记录。
- 每日最多自动分析一次。
- 每周校准后最多自动分析一次。
- 手动重新分析需要按钮触发。
- Packet 裁剪 evidence，避免 token 爆炸。
- 默认 temperature 低，提升稳定性。

## 测试计划

### 后端

- Packet 生成：包含筛选参数、版本、source status、review、calibration、证据样本。
- Packet 裁剪：不包含完整 K 线，不包含 API Key。
- AI adapter：OpenAI-compatible 请求格式正确。
- AI 输出校验：合法 JSON 保存成功，非法 JSON 返回错误。
- 建议队列：accept、ignore、snooze 状态可更新。
- 自动触发：每日复盘后可创建 packet 并启动 AI 分析；配置关闭时不触发。
- 通知：报告生成后可发送摘要；通知失败不影响报告。

### 前端

- 主页只显示轻量模型状态，不显示复杂诊断表。
- `/model-maintenance` 显示最新报告、建议队列、任务状态。
- AI 未配置时显示明确引导。
- 点击重新分析显示 loading、成功、失败状态。
- 建议接受/忽略/延后后状态更新。
- 设置页可配置 OpenAI/Codex、DeepSeek、自定义兼容接口。

## 成功标准

1. 用户不用手动阅读复杂诊断表，也能知道模型是否正常。
2. 每日/每周维护结果能自动生成 AI 分析报告。
3. AI 建议有证据、有风险说明、有置信度。
4. 任何策略变化都需要用户确认，不会被 AI 静默修改。
5. 主页回归日常选股工作台，模型维护独立成页。
