# GSGF 自动复盘与真实样本校准设计

## 背景

当前首页已有两个股是股非模型辅助模块：

- `信号复盘`：基于已保存的选股信号快照，复查后续 1/3/5/10 日收益和回撤。
- `真实样本校准`：基于 TickFlow 历史日 K，对指定历史交易日的候选池做真实样本校准。

这两个能力已经可用，但当前使用方式偏手动。真实样本校准还会拉取较多 K 线，请求耗时可能达到几十秒，前端同步等待时容易让用户误以为页面卡住。

目标是把它们升级为自动化、可追溯、可提醒的模型健康检查系统。

## 目标

1. 每次选股后自动保存 GSGF 信号快照，减少用户忘记保存导致的样本断层。
2. 每个交易日收盘后自动复查历史信号表现，沉淀最近一次信号复盘结果。
3. 真实样本校准支持后台任务执行，页面展示进度和最近一次结果。
4. 每周自动跑一次真实样本校准，避免模型长期不校准。
5. 复用已有通知渠道，在模型信号退化或校准完成时发送摘要。
6. 保持 TickFlow 只服务于当前独立选股工作台，不影响日报项目。

## 非目标

- 不新增交易下单能力。
- 不把 GSGF 信号当作收益保证。
- 不改变现有选股状态枚举，不新增 `empty` 作为新股筛选状态。
- 不重写现有情绪监控系统，只复用其后台线程、配置和通知模式。
- 不在每次选股后自动执行真实样本校准，以免 TickFlow 请求过重。

## 功能设计

### 1. 选股后自动保存快照

`/api/screener/run` 成功生成结果后，如果结果里存在 `gsgf` 分析结果，后端自动调用现有 `GsgfReviewStore.persist_snapshot`。

保存策略：

- 自动保存不改变原有选股返回结构。
- 快照仍写入 `data/gsgf_review/snapshots.jsonl`。
- 需要避免同一交易日、同一股票、同一信号被短时间重复写入。第一版可按 `trade_date + symbol + signal_type + status` 去重。
- 前端保留“保存复盘快照”按钮，作为手动补救入口。

### 2. 每日自动信号复查

新增 `GsgfReviewJob` 服务：

- 每个交易日收盘后运行一次，默认时间 `15:40`。
- 从 `gsgf_review/snapshots.jsonl` 读取历史快照。
- 用当前 K 线源复查 `1/3/5/10` 日表现。
- 生成 `GsgfReviewSummary`。
- 保存最近一次结果到 `data/gsgf_review/latest_summary.json`。

页面行为：

- 首页 `信号复盘` 默认读取 `latest_summary.json`。
- 用户仍可点击“立即复查”触发一次手动复查。
- 页面展示最近复查时间、样本数、信号桶表现。

### 3. 真实样本校准后台任务

真实样本校准从同步接口升级为后台任务。

新增任务模型：

- `job_id`
- `type = "gsgf_calibration"`
- `status = pending | running | success | failed | canceled`
- `progress_current`
- `progress_total`
- `message`
- `started_at`
- `finished_at`
- `error`
- `result_path`

新增 API：

- `POST /api/gsgf/calibration/jobs`
  - 创建后台校准任务。
  - 参数保留现有 `trade_dates`、`windows`、`scan_limit`、`count`。
- `GET /api/gsgf/calibration/jobs/{job_id}`
  - 查询任务状态和进度。
- `GET /api/gsgf/calibration/latest`
  - 读取最近一次成功校准结果。
- `POST /api/gsgf/calibration/jobs/{job_id}/cancel`
  - 尝试取消未完成任务。第一版允许软取消，在单只股票处理之间检查取消状态。

结果保存：

- 成功结果写入 `data/gsgf_calibration/results/{job_id}.json`。
- 最近一次成功结果复制到 `data/gsgf_calibration/latest.json`。

页面行为：

- 点击“开始校准”后，按钮进入运行态。
- 页面每 2-3 秒轮询任务状态。
- 显示 `已扫描 / 目标数量 / 跳过数量 / 当前阶段 / 耗时`。
- 页面刷新后可从 `latest` 恢复最近一次结果。

### 4. 每周自动真实样本校准

新增 `GsgfAutoReviewConfig` 运行时配置，存入现有 `runtime_config.json`：

- `auto_snapshot_enabled: bool = true`
- `daily_review_enabled: bool = true`
- `daily_review_time: "15:40"`
- `weekly_calibration_enabled: bool = true`
- `weekly_calibration_weekday: 5`
- `weekly_calibration_time: "16:10"`
- `weekly_calibration_trade_days: 5`
- `weekly_calibration_scan_limit: 80`
- `windows: [1, 3, 5, 10]`
- `kline_count: 260`
- `notify_on_success: bool = true`
- `notify_on_degradation: bool = true`

每周自动校准逻辑：

- 默认周五 `16:10` 后运行，`weekly_calibration_weekday` 使用 ISO weekday 口径，周一为 1，周日为 7。
- 样本日取最近 5 个交易日。
- 如果无法可靠取得交易日列表，第一版可使用最近已有选股记录的交易日作为样本日。
- 同一自然周只自动跑一次，避免重复消耗 TickFlow。

### 5. 模型健康度与提醒

新增 `GsgfModelHealth` 摘要：

- `best_signals`
- `weak_signals`
- `insufficient_sample_signals`
- `degraded_signals`
- `last_review_at`
- `last_calibration_at`
- `summary_text`

退化判断第一版使用保守规则：

- 样本数小于 5：标记为样本不足，不做强结论。
- 样本数大于等于 5 且平均回撤扩大、平均收益转负：标记为退化。
- `放量突破确认`、`确认买点` 属于核心信号，退化时优先提醒。

通知渠道：

- 复用现有企业微信、飞书、Telegram、邮件。
- 每日复查只在异常或退化时通知。
- 每周校准完成后发送一条摘要。
- 通知文案必须包含“仅供复盘与模型校准，不构成投资建议”。

## 架构

### 后端新增或扩展模块

- `services/gsgf_review.py`
  - 增加去重保存。
  - 增加 latest summary 持久化。
- `services/gsgf_real_calibration.py`
  - 增加进度回调和取消检查。
- `services/gsgf_auto_review.py`
  - 新增后台自动复查、每周校准调度。
- `services/background_jobs.py`
  - 轻量任务注册表，管理 GSGF 校准任务状态。
- `runtime_settings.py`
  - 增加 GSGF 自动化配置。
- `main.py`
  - 接入启动/停止后台服务。
  - 新增任务和 latest 查询 API。

### 前端调整

- 首页 GSGF 面板：
  - 默认读取最近一次信号复盘和最近一次真实校准。
  - 真实校准按钮改为创建后台任务。
  - 增加任务进度条和运行状态。
- 设置页：
  - 增加 GSGF 自动复盘配置。
  - 可编辑每日复查时间、每周校准时间、scan limit、通知开关。
- 类型与 API：
  - 增加 job、latest summary、model health 类型。

## 数据流

1. 用户运行选股。
2. 后端返回选股结果，同时自动保存 GSGF 快照。
3. 每日收盘后后台任务读取快照并复查 K 线表现。
4. 复查结果保存为 latest summary。
5. 每周后台任务创建真实样本校准 job。
6. job 扫描候选池，按进度拉取 TickFlow K 线，生成分桶统计。
7. 成功结果保存为 latest calibration。
8. 页面读取 latest 和 job 状态。
9. 如触发退化或完成提醒，通知服务发送消息。

## 错误处理

- TickFlow 请求失败：
  - 当前股票记为 skipped。
  - 任务不中断，除非候选池完全不可用。
- 候选池为空：
  - job 标记 failed，保存错误信息。
- 任务超时：
  - 第一版不做硬超时终止，但页面显示运行时长。
- 服务重启：
  - running job 标记为 failed，提示“服务重启导致任务中断”。
  - 最近一次成功结果仍可读取。
- 通知失败：
  - 不影响复查或校准结果保存。
  - 在任务状态里记录通知错误。

## 性能策略

- 自动每日复查只读取已有快照和 K 线，不扫描全市场。
- 真实样本校准只按配置的 `scan_limit` 拉取 K 线。
- 校准任务复用单次任务内的 K 线 cache。
- 页面不在加载时自动触发重型校准。
- 每周自动校准同一周只执行一次。

## 测试计划

### 后端

- 自动保存快照：
  - 选股结果包含 GSGF 时自动写入快照。
  - 重复运行不会短时间重复写入同一信号。
- 每日复查：
  - 能读取 snapshots 并生成 latest summary。
  - latest summary 可通过 API 读取。
- 后台任务：
  - 创建校准任务返回 job id。
  - job 状态从 pending 到 running 到 success。
  - 失败时记录 error。
  - 取消任务后状态为 canceled 或 failed with canceled。
- 每周自动校准：
  - 同一周不会重复运行。
  - 配置关闭时不运行。
- 通知：
  - 退化信号触发通知。
  - 通知失败不影响任务成功状态。

### 前端

- 首页默认展示最近一次复盘和最近一次校准。
- 点击开始校准后显示任务进度。
- 页面刷新后仍能看到最近一次成功校准。
- 设置页能编辑 GSGF 自动化配置。
- 原有选股、自选股、K 线、情绪、竞价页面不受影响。

## 成功标准

1. 用户不需要手动保存信号快照，系统能持续积累样本。
2. 每天收盘后能自动看到最新信号复盘结果。
3. 真实样本校准不再卡住前端页面。
4. 每周自动校准可控、可追溯、可关闭。
5. Telegram 等通知渠道能收到关键模型健康提醒。
