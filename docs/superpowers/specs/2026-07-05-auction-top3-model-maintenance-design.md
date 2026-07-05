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

## 非目标

- 不在模型维护页实时重算竞价 Top3。
- 不让 AI 自动修改竞价模型参数。
- 不把竞价回测、竞价复盘历史全部塞进第一版维护包。
- 不让 Web 应用直接控制 Codex Desktop 线程；第一版只提供可复制的维护包链接和可选提示词。
- 不改变现有 GSGF 模型维护报告和建议队列的核心行为。

## 推荐方案

采用“统一维护包 + 分模型摘要 + 两步式提交”的方案。

后端继续使用 `ModelMaintenancePacket` 作为维护包入口，在其中新增竞价 Top3 摘要字段。旧字段继续服务 GSGF，新增字段只包含竞价模型必要信息和样本摘要。

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

约束：

- `auction_top3.items` 只保留前 10 条摘要，不保存完整原始行情。
- 每条竞价样本只保留代码、名称、行业、分数、排序、主要信号、风险标签、关键特征摘要。
- 如果找不到竞价 Top3 缓存，`available=false`，并在 `notes` 和 `data_quality_notes` 中说明原因。
- 维护包不保存 API Key、运行时密钥、通知 Token。
- 维护包可保存完整业务分析上下文，但仍不保存完整 K 线和完整竞价全市场数据，避免文件体积失控。

### AI 报告扩展

第一版不新增 `ModelMaintenanceReport` 顶层字段，避免扩大前后端改动面。AI 报告通过现有字段表达竞价模型诊断：

- `key_findings` 可包含竞价 Top3 的模型表现判断。
- `rule_diagnostics` 可加入 `auction_top3_*` 规则名。
- `suggestions` 可加入竞价模型相关建议。
- `summary` 明确说明本次覆盖了哪些模型。

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
- 如果 AI 不可用，报告的 `model` 保持可识别，例如 `offline-rule-summary`。

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

3. `Codex 分析链接`
   - 维护包生成后显示只读链接。
   - 提供 `复制链接` 按钮。
   - 提供次要按钮 `复制带提示词的链接`，文案示例：`请打开这个维护包链接，分析 GSGF 和竞价 Top3 模型是否退化，并给出只观察不自动改规则的建议：{packet_url}`。

### 操作按钮

- `生成维护包`
- `提交给 AI 分析`
- `复制 Codex 分析链接`
- `复制带提示词的链接`

保留一个次要入口 `生成并分析` 也可以，但默认视觉上强调两步流程，避免用户不知道下一步。

### 状态反馈

- 生成维护包成功：提示维护包已生成，显示“下一步：提交给 AI 分析”和可复制给 Codex 的维护包链接。
- 在线 AI 成功：显示 provider/model。
- 离线降级：显示“AI 未配置或调用失败，当前使用离线规则摘要”。
- 竞价缓存缺失：显示“竞价 Top3 无缓存，本次只维护 GSGF；请先在竞价页生成 Top3 模型结果”。

## 错误处理

- 竞价 Top3 缓存缺失不阻断维护包生成。
- AI 调用失败不覆盖上一份成功报告，但允许生成离线摘要。
- 页面必须区分“没有报告”“离线报告”“在线 AI 报告”。
- 维护包链接必须只读、可追溯。
- 维护包业务数据不脱敏；凭证类字段必须从源头排除，不能进入 packet。
- 复制 Codex 分析链接失败时显示明确错误。

## 测试计划

### 后端

- 生成维护包时，存在竞价 Top3 缓存则包含 `model_sections.auction_top3.available=true`。
- 缓存缺失时，维护包仍成功，且写入数据质量提示。
- AI prompt 包含竞价 Top3 摘要。
- 离线分析能识别竞价 Top3 缓存状态。
- 现有 GSGF 模型维护 API 测试继续通过。

### 前端

- `/model-maintenance` 显示维护包状态卡。
- 点击“生成维护包”后显示下一步提示。
- 生成维护包后显示可复制的维护包链接。
- 点击“提交给 AI 分析”后显示 provider/model。
- `offline-rule-summary` 时显示离线降级提示。
- 竞价 Top3 缓存缺失时显示可理解的说明。
- 复制 Codex 分析链接按钮存在并可用。

## 实施顺序

1. 后端扩展维护包数据结构和 packet builder。
2. 后端接入竞价 Top3 缓存读取，不触发重算。
3. 后端扩展 AI prompt 和离线摘要。
4. 前端新增维护包读取接口和状态卡。
5. 前端拆分“生成维护包”和“提交 AI 分析”。
6. 前端新增维护包阅读页、Codex 分析链接复制。
7. 补充后端和前端测试。
