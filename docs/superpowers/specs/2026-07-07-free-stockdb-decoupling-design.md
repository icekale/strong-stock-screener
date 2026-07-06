# free-stockdb 训练源解耦设计

## 背景

竞价 Top3 模型当前把 free-stockdb 作为历史日 K 数据源，用于五年训练、回测和每日重新生成候选。free-stockdb 的仓库形态更接近 Windows 本地数据服务，核心运行依赖 Windows 可执行文件，不适合直接放进 Docker、Unraid 或 macOS 运行。

这会带来一个实盘风险：如果 Top3 结果在早盘点击时临时依赖 Windows 机器上的 free-stockdb，全链路会受到局域网连通性、Windows 服务状态和全市场日 K 拉取速度影响。早盘竞价决策需要秒级读取已有结果，不能等待历史数据源慢查询或超时。

项目已有多个数据源可以提供历史 K 线，例如 TickFlow、百度 K 线和后续可扩展的 fallback provider。更合理的边界是：free-stockdb 只作为离线训练和回测数据集构建源；每日 Top3 推理、实盘确认和页面展示使用通用 K 线 provider、本地缓存和 TickFlow 实时数据。

## 目标

- 把 free-stockdb 从实盘运行时强依赖降级为模型训练数据源。
- `/auction` 页面优先读取本地 Top3 缓存，避免早盘阻塞。
- 每日 Top3 推理使用通用 K 线 provider，不直接依赖 free-stockdb。
- Top3 推理改为后台任务，前端显示任务状态而不是长时间等待。
- free-stockdb 不可用时，系统仍能展示已有模型缓存、竞价强度榜和 TickFlow 实时确认。
- 明确区分训练源状态、推理源状态、缓存可用性和缓存新鲜度。
- 保持现有训练模型、缓存文件格式和 Unraid 部署方式不做破坏性变更。

## 非目标

- 不把 free-stockdb 打包进 Docker 镜像。
- 不要求 macOS 或 Unraid 直接运行 stockdb 可执行文件。
- 不在第一版重写训练管线。
- 不更换 Top3 模型特征或回测目标。
- 不要求每日 Top3 推理必须扫描全市场所有股票，第一版可复用现有候选池和 K 线 provider。
- 不接券商交易，也不做自动下单。

## 推荐方案

采用“训练慢链路 + 推理快链路 + 实时确认”的结构。

第一层是 Windows free-stockdb 训练源：

- 责任：提供大批量历史日 K，用于模型训练、重训和离线回测数据集构建。
- 运行位置：用户的 Windows 电脑或 Windows 虚拟机。
- 调用方式：通过 `STRONG_STOCK_AUCTION_MODEL_FREE_STOCKDB_BASE_URL` 指向局域网地址。
- 约束：不参与早盘页面读取，也不参与每日 Top3 推理的默认路径。

第二层是通用 K 线推理源：

- 责任：为每日 Top3 推理提供近期历史 K 线特征。
- 运行位置：StockMaster API 内部 provider。
- 调用方式：复用现有 `kline_provider`，优先 TickFlow，失败时走 fallback。
- 约束：只服务当前交易日候选推理，不负责五年训练样本构建。

第三层是 StockMaster 本地缓存：

- 责任：保存 Top3 结果、模型元数据、历史生成状态和最近一次可用结果。
- 运行位置：Unraid Docker 容器的持久化目录。
- 调用方式：`/auction` 页面默认只读本地缓存。
- 约束：缓存缺失时给出明确提示，而不是同步拉取历史数据。

第四层是 TickFlow 实时确认：

- 责任：提供早盘竞价、实时涨跌幅、成交额、换手和 K 线页面数据。
- 运行位置：外部 API。
- 调用方式：现有 TickFlow provider。
- 约束：TickFlow 缺失时降级为观察，不影响 Top3 缓存展示。

## 行为设计

### 页面读取

打开 `/auction` 时：

1. 读取竞价强度榜和行业强度。
2. 读取本地 Top3 缓存。
3. 如果缓存存在，立即展示模型结果。
4. 如果缓存不存在，展示“暂无本地 Top3 缓存”，并提示需要用当前 K 线源后台生成。
5. 异步读取实时确认结果，不阻塞模型缓存展示。

页面默认不直接触发 free-stockdb 全市场查询。

### 每日 Top3 推理

点击“重新生成 Top3”时：

1. 后端创建后台任务并立即返回任务 ID。
2. 后台任务读取当前配置的候选源和 K 线 provider。
3. K 线 provider 不可用时任务快速失败，保留旧缓存。
4. K 线 provider 可用时构建近期特征、模型打分并写入新缓存。
5. 前端轮询任务状态，展示排队、运行、完成或失败。

旧缓存不能因为新任务失败而被删除或覆盖。

### 模型训练

模型训练和重训仍可使用 free-stockdb：

- 训练任务可以读取 Windows free-stockdb 的五年日 K。
- 训练任务不应在 `/auction` 页面直接触发。
- 训练结果产出模型文件、metadata 和 performance 文件。
- 每日 Top3 推理只加载训练好的模型文件。

### 数据源状态

推理状态字段：

- `inference_provider`：当前 K 线 provider。
- `inference_reachable`：最近一次推理源检查是否成功。
- `last_checked_at`：最近检查时间。
- `latency_ms`：检查耗时。
- `last_prediction_success_at`：最近一次成功推理时间。
- `last_error`：最近错误摘要。
- `cache_trade_date`：当前可用 Top3 缓存日期。
- `cache_status`：`fresh | stale | missing`。

训练状态字段：

- `training_source_configured`：是否配置 free-stockdb。
- `training_source_reachable`：最近一次训练源检查是否成功。
- `last_training_success_at`：最近一次训练或重训成功时间。
- `training_source_error`：最近训练源错误摘要。

页面显示简短文案：

- `K线源在线，缓存可用`
- `K线源离线，使用本地缓存`
- `训练源离线，不影响今日缓存读取`
- `缓存缺失，需要用当前K线源生成`

## 后端设计

### 服务边界

保留现有 `FreeStockDbAuctionModelSource`，但只用于训练、重训和离线回测数据集构建。

新增或调整每日推理 source：

- `ProviderAuctionModelSource`

它负责：

- 从现有候选源获取候选池。
- 使用现有 `kline_provider` 拉取近期日 K。
- 构建与训练模型兼容的特征行。
- 不访问 free-stockdb。

新增轻量任务层：

- `AuctionModelGenerationJobStore`
- `AuctionModelGenerationService`

任务 store 负责记录：

- 任务 ID
- trade_date
- status：`queued | running | success | failed`
- created_at
- started_at
- finished_at
- error
- result_cache_path

任务 service 负责：

- 快速检查当前 K 线 provider。
- 调用现有 `AuctionModelService.predict_top3`。
- 写入 `AuctionModelResultStore`。
- 保证失败时不破坏旧缓存。

### API

保留现有缓存读取 API。

新增或调整：

- `POST /api/auction/model/top3/generate`
  - 创建后台生成任务。
  - 返回任务 ID 和初始状态。

- `GET /api/auction/model/top3/jobs/{job_id}`
  - 查询任务状态。

- `GET /api/auction/model/top3/source-status`
  - 返回推理源状态、训练源状态和缓存状态。

如果现有重新生成 API 已经存在，优先兼容旧路径，内部改为后台任务，避免破坏前端调用。

## 前端设计

`/auction` 的“模型 Top3 试运行”板块调整为：

- 第一行显示缓存状态和 trade_date。
- 有缓存时立即展示 Top3 结果。
- 右侧显示 K 线推理源状态。
- “重新生成”按钮变为任务触发按钮。
- 任务运行时显示进度状态，不清空当前结果。
- 任务失败时显示错误摘要，并继续保留旧结果。
- 训练源状态可以放到设置页或模型维护页，不作为早盘页面主状态。

前端不需要显示复杂日志，只显示对早盘决策有用的信息。

## 配置与部署

Unraid 模板继续保留：

- `STRONG_STOCK_AUCTION_MODEL_FREE_STOCKDB_BASE_URL`

用途：

- 模型训练
- 模型重训
- 离线回测数据集构建

示例值：

- `http://192.168.5.221:7899`

文档需要明确：

- free-stockdb 只需要部署在 Windows。
- Docker/Unraid 容器只需要能访问该局域网地址。
- 早盘实盘读取不依赖 free-stockdb 在线。
- 每日 Top3 推理不依赖 free-stockdb 在线。
- 只有模型训练、重训和离线回测数据集构建才需要 free-stockdb 在线。

## 错误处理

- K 线 provider 不可用：每日推理任务失败，保留旧缓存。
- free-stockdb 未配置：训练功能提示配置地址，不影响每日推理。
- free-stockdb 超时：训练任务失败，不影响旧模型和旧缓存。
- 返回非 JSON：任务失败，记录错误摘要。
- 返回结构异常：任务失败，记录错误摘要。
- 写缓存失败：任务失败，不覆盖旧缓存。
- TickFlow 失败：实时确认降级，不影响 Top3 缓存。

## 测试

后端测试：

- 缓存读取不调用 free-stockdb。
- 每日推理会创建后台任务并立即返回。
- 每日推理使用 `kline_provider`，不访问 free-stockdb。
- K 线 provider 失败时任务失败且旧缓存保留。
- K 线 provider 成功时任务写入新 Top3 缓存。
- source-status 能区分推理源在线、推理源离线、训练源离线、缓存缺失和缓存可用。
- 训练源状态检查失败不影响缓存读取和每日推理。

前端测试：

- 有缓存时立即展示 Top3。
- 任务运行时不清空旧 Top3。
- 任务失败时显示错误但保留旧结果。
- 训练源离线时提示不影响今日缓存读取。
- 推理源离线时显示“使用本地缓存”。

部署验证：

- 本地 API 测试通过。
- Web 单元测试通过。
- Unraid 上不配置 free-stockdb 时页面仍可打开。
- Unraid 上不配置 free-stockdb 时仍能用 TickFlow K 线生成今日 Top3。
- Unraid 上配置 Windows free-stockdb 后，训练源状态能正确显示。

## 成功标准

- 早盘打开 `/auction` 不会因为 free-stockdb 离线而卡住或报整页错误。
- 点击重新生成后，页面不会长时间阻塞。
- Windows free-stockdb 不在线时，旧 Top3 缓存仍可用于观察。
- Windows free-stockdb 不在线时，每日 Top3 推理仍可使用其他 K 线数据源。
- 代码和文档明确说明 free-stockdb 是训练源，不是 Docker 内部依赖，也不是早盘推理依赖。
- 当前模型文件、缓存目录和 Unraid 模板保持兼容。
