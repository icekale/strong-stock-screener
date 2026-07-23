# ETF 超量资金趋势与十倍量标记 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 ETF 雷达日度活动中，统一计算过去20日份额变化倍数，标注十倍量申购/赎回，并展示全部监控 ETF 合计的超量资金趋势，同时修复活动表格错位。

**Architecture:** 后端新增纯本地计算服务，从 `CapitalSignalStore` 的 ETF 份额历史计算每只 ETF 的20日基线、十倍量字段和市场聚合趋势；现有三因子与旧报告基线字段保持不变。Vue 前端新增趋势图面板和纯展示领域格式化工具，日度活动页先展示聚合趋势再展示异常明细，缺失点保持断线并暴露覆盖率。

**Tech Stack:** FastAPI、Pydantic、pytest、Vue 3、TypeScript、ECharts、Vitest/Node test、pnpm。

---

## 文件地图

- Create: `apps/api/app/services/etf_excess_flow.py`，计算20日份额基线、十倍量字段和聚合资金趋势。
- Modify: `apps/api/app/models.py`，扩展 ETF 活动项并增加趋势响应模型。
- Modify: `apps/api/app/main.py`，注册 `/api/etf-radar/excess-flow`。
- Test: `apps/api/tests/test_etf_excess_flow.py`，覆盖计算边界和缺失数据。
- Test: `apps/api/tests/test_api.py`，覆盖新接口的响应契约与旧缓存兼容。
- Modify: `apps/web-vue/src/service/types.ts`，同步后端新增字段。
- Modify: `apps/web-vue/src/service/product-api.ts`，增加趋势读取函数。
- Create: `apps/web-vue/src/utils/domain/etfExcessFlow.ts`，集中处理图表序列和显示标签。
- Test: `apps/web-vue/src/utils/domain/etfExcessFlow.test.ts`，覆盖图表序列和事件点。
- Create: `apps/web-vue/src/components/etf-radar/EtfExcessFlowPanel.vue`，展示市场合计趋势图、覆盖率和事件摘要。
- Test: `apps/web-vue/src/components/etf-radar/EtfExcessFlowPanel.test.ts`，覆盖加载、空数据和十倍量展示契约。
- Modify: `apps/web-vue/src/components/etf-radar/EtfActivityTable.vue`，增加十倍量标签、倍数显示和稳定列布局。
- Modify: `apps/web-vue/src/views/EtfRadarView.vue`，读取趋势接口并把趋势面板放在日度活动表格之前。
- Modify: `apps/web-vue/src/components/etf-radar/EtfActivityTable.test.ts`，增加方向标签和排序回归。

### Task 1: 先写后端计算契约测试

**Files:**
- Create: `apps/api/tests/test_etf_excess_flow.py`

- [ ] **Step 1: 写 20 日基线与十倍边界测试**

使用 `EtfSharePoint` 构造 21 个按交易日排序的历史点，最后一天设置正向变化为前20日绝对变化均值的10倍，断言：

```python
def test_share_change_multiple_excludes_current_day_and_marks_tenfold() -> None:
    history = _history_with_deltas("510050.SH", [100] * 20 + [1000])
    result = build_activity_metrics(history, symbols=("510050.SH",))

    current = result.items[-1]
    assert current.share_change_20d_avg_abs == 100
    assert current.share_change_20d_multiple == 10
    assert current.is_tenfold_share_change is True
    assert current.share_change_direction == "increase"
```

测试负向 `-1000` 返回 `decrease` 并触发赎回；`999` 不触发；少于20个前置有效值不触发。

- [ ] **Step 2: 写零基线和缺失价格测试**

覆盖以下明确行为：

```python
def test_zero_baseline_does_not_create_infinite_multiple() -> None:
    history = _history_with_deltas("510050.SH", [0] * 20 + [1000])
    current = build_activity_metrics(history, symbols=("510050.SH",)).items[-1]
    assert current.share_change_20d_avg_abs == 0
    assert current.share_change_20d_multiple is None
    assert current.is_tenfold_share_change is False

def test_missing_close_is_excluded_from_money_coverage_not_treated_as_zero() -> None:
    history = _history_with_deltas("510050.SH", [100] * 20 + [1000], close=None)
    point = build_flow_trend(history, symbols=("510050.SH",)).points[-1]
    assert point.coverage_count == 0
    assert point.net_excess_flow_cny is None
```

- [ ] **Step 3: 写市场合计与事件列表测试**

构造两只 ETF 的同日正负变化，断言 `net = inflow - outflow`、事件计数和 `trigger_symbols` 排序稳定；构造第二只 ETF 缺失价格，断言 `expected_count` 仍为2而 `coverage_count` 为1。

- [ ] **Step 4: 运行测试确认先失败**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest -q tests/test_etf_excess_flow.py
```

Expected: FAIL，因为新增服务和模型尚未存在。

### Task 2: 实现后端模型和纯计算服务

**Files:**
- Modify: `apps/api/app/models.py` near `HuijinEtfActivityItem`, `EtfRadarHistoryResponse`。
- Create: `apps/api/app/services/etf_excess_flow.py`。

- [ ] **Step 1: 增加 Pydantic 字段和响应模型**

在 `HuijinEtfActivityItem` 增加：

```python
share_change_20d_avg_abs: float | None = None
share_change_20d_multiple: float | None = None
is_tenfold_share_change: bool = False
```

新增 `EtfExcessFlowPoint` 与 `EtfExcessFlowResponse`，金额字段使用 `float | None`，事件字段使用 `list[str]` 默认空列表，响应继承 `CapitalSignalMetadata` 并额外包含 `formula: str`、`expected_count: int` 和 `points`。

- [ ] **Step 2: 实现历史扫描函数**

在新服务中实现以下稳定接口：

```python
def build_activity_metrics(
    history: list[EtfSharePoint],
    symbols: Iterable[str],
) -> EtfExcessFlowActivityResult: ...

def build_flow_trend(
    history: list[EtfSharePoint],
    symbols: Iterable[str],
    days: int = 60,
) -> EtfExcessFlowResponse: ...
```

每个 symbol 先按日期排序，使用相邻总份额差作为日变化；计算当前日期时只从当前日期之前的最多20个非空变化中取 `mean(abs(delta))`。当有效前置样本不足20或均值不大于0时，倍数为 `None`。

- [ ] **Step 3: 实现资金与事件聚合**

对有效价格点计算：

```python
excess_shares = sign(delta) * max(abs(delta) - baseline, 0)
excess_flow_cny = excess_shares * close
```

正值累加 `excess_inflow_cny`，负值累加其绝对值到 `excess_outflow_cny`，净值为两者之差。金额字段在当日没有可用价格时返回 `None`，不补零。十倍事件只在倍数 `>= 10` 时计数，并按 symbol 排序写入 `trigger_symbols`。

- [ ] **Step 4: 运行后端单测确认通过**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest -q tests/test_etf_excess_flow.py
```

Expected: PASS。

### Task 3: 接入 API 并覆盖响应兼容

**Files:**
- Modify: `apps/api/app/main.py` near existing `/api/etf-radar/*` routes。
- Modify: `apps/api/tests/test_api.py` near existing ETF radar endpoint tests。

- [ ] **Step 1: 添加服务工厂和读取路由**

新增：

```python
@app.get("/api/etf-radar/excess-flow", response_model=EtfExcessFlowResponse)
def get_etf_excess_flow(days: int = Query(default=60, ge=20, le=120)) -> EtfExcessFlowResponse:
    return _etf_excess_flow_service().trend(days=days)
```

服务使用当前 `CapitalSignalStore(get_settings().data_dir)` 读取缓存，并返回标准 `source_status`。路由不触发外部刷新，避免趋势图拖慢日度活动首屏。

- [ ] **Step 2: 写 API 契约测试**

使用临时数据目录写入旧格式 `etf-share-history.json`，调用新接口并断言新增字段有默认值/正确计算；再调用既有 `/api/etf-radar/overview` 和 `/api/etf-radar/history`，确保旧响应仍可解析。

- [ ] **Step 3: 运行后端接口回归**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest -q tests/test_etf_excess_flow.py tests/test_api.py -k 'etf_radar or excess_flow'
```

Expected: PASS。

### Task 4: 增加前端类型、API 客户端和纯展示转换

**Files:**
- Modify: `apps/web-vue/src/service/types.ts` near ETF radar types。
- Modify: `apps/web-vue/src/service/product-api.ts` near existing ETF radar functions。
- Create: `apps/web-vue/src/utils/domain/etfExcessFlow.ts`。
- Test: `apps/web-vue/src/utils/domain/etfExcessFlow.test.ts`。

- [ ] **Step 1: 增加 TypeScript 契约**

同步 `HuijinEtfActivityItem` 的三个新增字段，并新增 `EtfExcessFlowPoint`、`EtfExcessFlowResponse`，保持后端 `null` 可见。

- [ ] **Step 2: 增加 API 函数**

实现：

```ts
export async function getEtfExcessFlow(days = 60): Promise<EtfExcessFlowResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/etf-radar/excess-flow?days=${days}`);
  if (!response.ok) throw new Error(`读取ETF超量资金趋势失败：${response.status} ${await response.text()}`);
  return response.json() as Promise<EtfExcessFlowResponse>;
}
```

- [ ] **Step 3: 添加纯函数转换**

实现 `buildExcessFlowSeries(response)`，返回 ECharts 的日期、净流入、申购、赎回和事件点序列；`null` 保留为 `null`，不使用 `connectNulls`。实现 `shareChangeMultipleLabel(item)` 和 `shareChangeEventLabel(item)`，只把 `is_tenfold_share_change` 为真的项目生成标签。

- [ ] **Step 4: 先运行前端领域测试**

Run:

```bash
cd apps/web-vue
pnpm exec vitest run src/utils/domain/etfExcessFlow.test.ts
```

Expected: PASS。

### Task 5: 实现趋势面板并修复活动表格布局

**Files:**
- Create: `apps/web-vue/src/components/etf-radar/EtfExcessFlowPanel.vue`。
- Test: `apps/web-vue/src/components/etf-radar/EtfExcessFlowPanel.test.ts`。
- Modify: `apps/web-vue/src/components/etf-radar/EtfActivityTable.vue`。
- Test: `apps/web-vue/src/components/etf-radar/EtfActivityTable.test.ts`。

- [ ] **Step 1: 写面板状态测试**

覆盖成功数据、部分覆盖、无数据和请求失败四种状态；成功数据断言三条序列和十倍事件文案存在，空数据断言“暂无可用趋势数据”而不是渲染空坐标轴。

- [ ] **Step 2: 实现 ECharts 面板**

使用现有 `EChart` 异步组件和工作台 CSS token；图例固定显示净超量、申购、赎回，tooltip 显示日期、金额、覆盖数和触发 ETF。净值用绿色/红色按正负显示，不能用渐变背景或装饰性图形。

- [ ] **Step 3: 增加表格十倍量展示**

在 `EtfActivityTable.vue` 的份额日变化和状态列使用统一的 `10×申购` / `10×赎回` 标签；倍数为 null 时仍显示原有 `--`。标签使用固定内联高度，状态文本允许换行。

- [ ] **Step 4: 修复表格列布局**

为身份列、数值列和状态列设置明确的 `minmax`/固定最小宽度，数值列右对齐，身份列两行截断，状态列使用 `white-space: normal`；滚动容器保留键盘焦点和窄屏横向滚动。桌面宽屏不让空白列无限拉伸。

- [ ] **Step 5: 运行前端组件测试**

Run:

```bash
cd apps/web-vue
pnpm exec vitest run src/components/etf-radar/EtfExcessFlowPanel.test.ts src/components/etf-radar/EtfActivityTable.test.ts
```

Expected: PASS。

### Task 6: 接入日度活动页并做全量验证

**Files:**
- Modify: `apps/web-vue/src/views/EtfRadarView.vue`。

- [ ] **Step 1: 添加趋势状态和加载请求**

在页面已有 `loadOverview`/`loadHistory` 流程中并行请求 `getEtfExcessFlow(60)`，趋势失败只显示面板错误，不阻塞表格、三因子和交叉验证。

- [ ] **Step 2: 插入面板**

在 `activeTab === 'activity'` 的活动摘要之后、`EtfActivityTable` 之前插入 `EtfExcessFlowPanel`，传递响应、加载状态和错误；刷新按钮同时刷新趋势数据。

- [ ] **Step 3: 运行前端类型检查、单测和构建**

Run:

```bash
cd apps/web-vue
pnpm exec vue-tsc --noEmit
pnpm exec vitest run
pnpm build
```

Expected: 类型检查通过、全部测试通过、生产构建生成 `dist/index.html`。

- [ ] **Step 4: 运行后端全量相关测试和静态检查**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest -q tests/test_etf_excess_flow.py tests/test_api.py tests/test_etf_three_factor_monitor.py tests/test_huijin_etf_activity.py
.venv/bin/python -m ruff check app tests
```

Expected: 测试通过，Ruff 无错误。

- [ ] **Step 5: 记录变更并提交实现**

```bash
git add apps/api/app/models.py apps/api/app/main.py apps/api/app/services/etf_excess_flow.py apps/api/tests/test_etf_excess_flow.py apps/api/tests/test_api.py apps/web-vue/src/service/types.ts apps/web-vue/src/service/product-api.ts apps/web-vue/src/utils/domain/etfExcessFlow.ts apps/web-vue/src/utils/domain/etfExcessFlow.test.ts apps/web-vue/src/components/etf-radar/EtfExcessFlowPanel.vue apps/web-vue/src/components/etf-radar/EtfExcessFlowPanel.test.ts apps/web-vue/src/components/etf-radar/EtfActivityTable.vue apps/web-vue/src/components/etf-radar/EtfActivityTable.test.ts apps/web-vue/src/views/EtfRadarView.vue
git commit -m "feat: add ETF excess flow trend"
```

