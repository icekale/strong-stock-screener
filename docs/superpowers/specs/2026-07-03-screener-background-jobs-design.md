# 选股后台任务化设计

## 背景

首页运行选股时，`scan_limit=160` 的真实请求在 Unraid 上可能耗时 80-110 秒。当前页面通过 Next.js `/api/*` 代理等待完整响应，旧版本会被默认 30 秒代理超时截断；即使提高代理超时，用户仍需要长时间盯着按钮等待，体验不适合实盘使用。

## 目标

把首页选股从“同步等待结果”改成“后台任务 + 前端轮询”：

- 点击运行筛选后立即返回任务 ID。
- 页面显示任务状态、进度文案和进度条。
- 任务完成后自动展示筛选结果。
- 任务失败时展示明确错误。
- 保留现有同步接口 `/api/screen/runs`，用于脚本、测试和兜底调试。

## 非目标

- 不改变选股策略、排序规则、TickFlow 调用方式或候选池逻辑。
- 不做 K 线批量缓存、限速队列或任务持久化恢复。
- 不改变自选股、竞价、板块、情绪模块。

## 后端设计

复用现有 `BackgroundJobStore`，新增选股任务接口：

- `POST /api/screen/runs/jobs`
  - 请求体复用 `ScreenRunRequest`。
  - 如果已有 `screen_run` 类型任务处于 `pending/running`，返回现有任务，避免重复启动多个重筛任务。
  - 启动后台线程执行现有筛选逻辑。

- `GET /api/screen/runs/jobs/{job_id}`
  - 返回任务状态。
  - `success` 时附带筛选结果。
  - `failed/canceled` 时返回错误信息。

任务执行仍调用现有 `StrongStockScreener.screen()`。成功后继续调用现有 `_run_store().save(result)`，所以 `/api/screen/runs/latest` 与记录页逻辑保持兼容。

`BackgroundJobState` 需要支持一个轻量 `result` 字段，用于 transient job 在内存中返回完成结果。这里不把完整结果写入后台任务目录，避免引入第二套筛选结果存储；筛选结果仍以 `RunStore` 为准。

## 前端设计

首页 `HomeWorkbench` 的 `handleRun()` 改为：

1. 调用 `createScreenRunJob()` 创建后台任务。
2. 设置 `running=true` 和当前任务状态。
3. 每 2 秒调用 `getScreenRunJob(job_id)`。
4. 任务成功后：
   - 将 `job.result` 写入 `result`。
   - 清空 `intraday`。
   - 刷新数据源、市场概览、板块雷达、情绪概览。
5. 任务失败或取消后：
   - `running=false`。
   - 显示 `job.error` 或通用失败文案。

`ScreenerWorkbench` 继续使用现有 `running` 属性。新增可选 `screenJob` 属性，让筛选结果区域或筛选控制区展示“任务状态 / 进度 / 当前阶段”。不重做页面布局。

## 错误处理

- 创建任务失败：显示“启动筛选任务失败”。
- 轮询任务失败：显示“读取筛选任务失败”，并停止当前轮询。
- 后端任务失败：显示后端 `job.error`。
- 用户重复点击运行：后端返回已有运行中任务，前端继续轮询同一个任务。

## 测试计划

后端：

- 创建选股任务后返回 `pending` 或 `running` 状态。
- 同一时间重复创建选股任务时返回已有活跃任务。
- 任务成功后 `GET /api/screen/runs/jobs/{job_id}` 返回 `success` 和筛选结果。
- 任务成功后 `/api/screen/runs/latest` 能读取最新筛选结果。

前端：

- API 层包含 `createScreenRunJob()` 和 `getScreenRunJob()`。
- 首页不再直接调用同步 `createScreenRun()` 作为默认运行路径。
- 任务状态会传递到工作台组件。
- 现有构建和测试继续通过。

## 后续优化

本版只解决“长请求阻塞和 500 超时”。下一版再考虑：

- TickFlow 日 K 批量缓存。
- 候选 K 线分批限速。
- 任务进度细分到候选扫描、K 线分析、排序保存。
- 支持用户取消选股任务。
