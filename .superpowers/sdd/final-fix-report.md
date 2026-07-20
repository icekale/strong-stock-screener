# Final Review Fix Report

日期：2026-07-20
分支：`codex/huijin-holdings-trend`

## 结论

`final-review.md` 的 7 个 Important 和 2 个 Minor 均已按测试先行完成修复；未发现规格冲突。每项测试均先在未修改对应生产逻辑时得到目标 RED，再做最小修复并得到 GREEN。

## RED / GREEN

### I1 `history()` 覆盖刷新后历史

- RED：新增 `test_history_reloads_rows_saved_by_overview_before_sanitizing`，刷新写入 `159915.SZ@2026-07-17` 后，旧列表再次保存导致断言 `any(...)` 为 `False`。
- RED 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -k history_reloads_rows_saved_by_overview_before_sanitizing -vv`
- RED 结果：`1 failed, 43 deselected`。
- 修复：`history()` 使用服务锁协调首载；需要 `overview()` 刷新时，刷新完成后重新读取 `etf-share-history.json`，再执行定向清理，禁止用刷新前列表覆盖。
- GREEN：同一命令结果 `1 passed, 43 deselected`。
- 文件：`apps/api/app/services/capital_signals.py`、`apps/api/tests/test_capital_signals.py`。

### I2 失败/拒绝符号的同日缓存信任边界

- RED 1：新增 `test_service_trusts_cache_only_for_symbols_with_actual_request_failures`；实际失败的 `510300.SH` 缓存应保留，而日期拒绝的 `159915.SZ` 污染值实际仍为 `9999`。
- RED 1 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -k trusts_cache_only_for_symbols_with_actual_request_failures -vv`
- RED 1 结果：`1 failed, 43 deselected`，失败值 `9999.0 is None`。
- RED 2：在 provider partial SZSE 测试中要求结构化 `failed_symbols=("159922.SZ",)`、`rejected_symbols=("159919.SZ",)`；原结果没有这些元数据。
- RED 2 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signal_providers.py -k partial_szse_coverage -vv`
- RED 2 结果：`1 failed, 26 deselected`，实际 `failed_symbols == ()`。
- RED 3：审计补充 `test_overview_candidate_date_rejects_unvalidated_cached_symbols`；候选日明确拒绝的验证 ETF 仍从旧缓存恢复为 `9999`。
- RED 3 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -k candidate_date_rejects_unvalidated_cached_symbols -vv`
- RED 3 结果：`1 failed, 47 deselected`，失败值 `9999.0 is None`。
- 修复：`CapitalProviderResult` 增加 `failed_symbols`/`rejected_symbols`；SSE 按交易所请求、SZSE 按具体符号记录失败和拒绝。服务在首轮与候选日期分支都只复用 `failed_symbols` 的同日缓存，立即删除 `rejected_symbols` 的同日持久化行。
- GREEN 1：服务目标测试 `1 passed, 43 deselected`。
- GREEN 2：provider 元数据测试 `1 passed, 26 deselected`。
- GREEN 3：候选日边界测试 `1 passed, 47 deselected`。
- 文件：`apps/api/app/providers/capital_signals.py`、`apps/api/app/services/capital_signals.py`、`apps/api/tests/test_capital_signal_providers.py`、`apps/api/tests/test_capital_signals.py`。

### I3 缺新增字段的旧快照被复用

- RED：新增 `test_fresh_snapshot_missing_baseline_quantity_fields_is_not_reused`，从原始 snapshot JSON 删除两个字段后，provider 调用列表实际为 `[]`。
- RED 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -k fresh_snapshot_missing_baseline_quantity_fields_is_not_reused -vv`
- RED 结果：`1 failed, 43 deselected`。
- 修复：`_is_compatible_snapshot()` 检查每个 core/validation item 的 `model_fields_set`，要求原始快照确实包含 `baseline_total_shares` 和 `confirmed_huijin_shares`；字段值仍允许合法 `null`。
- GREEN：同一命令结果 `1 passed, 43 deselected`，provider 重新抓取且七只核心 ETF 两字段完整。
- 文件：`apps/api/app/services/capital_signals.py`、`apps/api/tests/test_capital_signals.py`。

### I4 跨基线且乱序的轨迹

- RED：新增 `keeps only the selected report baseline period in strict date order`；原结果为 `dates=['2026-06-30','2026-07-01','2026-06-27']`、`values=[0,2,-4]`。
- RED 命令：`cd apps/web-vue && corepack pnpm@9.15.0 test:unit --run src/utils/domain/huijinTrajectory.test.ts -t 'keeps only the selected report baseline period in strict date order'`
- RED 结果：`1 failed, 5 skipped`。
- 修复：只保留严格晚于当前 `report_period` 的真实日期，与报告期去重后升序排列；旧报告基线点不再混入。
- GREEN 命令：`cd apps/web-vue && corepack pnpm@9.15.0 test:unit --run src/utils/domain/huijinTrajectory.test.ts`
- GREEN 结果：`1 test file passed, 6 tests passed`。
- 文件：`apps/web-vue/src/utils/domain/huijinTrajectory.ts`、`apps/web-vue/src/utils/domain/huijinTrajectory.test.ts`。

### I5 SvgIcon 默认前缀不一致

- RED：新增真实组件挂载测试；无 `VITE_ICON_PREFIX`/`VITE_ICON_LOCAL_PREFIX` 时，`use[href]` 实际为 `#undefined-expectation`。
- RED 命令：`cd apps/web-vue && env -u VITE_ICON_PREFIX -u VITE_ICON_LOCAL_PREFIX corepack pnpm@9.15.0 test:unit --run src/components/custom/svg-icon.test.ts`
- RED 结果：`1 failed`，expected `#local-icon-expectation`，received `#undefined-expectation`。
- 修复：增加共享 `DEFAULT_ICON_PREFIX`/`DEFAULT_LOCAL_ICON_PREFIX`，UnoCSS、unplugin 和运行时 `SvgIcon` 使用同一默认常量。
- GREEN：同一命令结果 `1 test file passed, 1 test passed`。
- 文件：`apps/web-vue/src/constants/icon.ts`、`apps/web-vue/build/plugins/unocss.ts`、`apps/web-vue/build/plugins/unplugin.ts`、`apps/web-vue/src/components/custom/svg-icon.vue`、`apps/web-vue/src/components/custom/svg-icon.test.ts`。

### I6 默认明细缺三列且移动端不可读

- RED 1：新增六列表头/行内容测试，原表头实际为 `ETF / 确认持仓比例 / 累计偏离 / 数据状态`。
- RED 1 命令：`cd apps/web-vue && corepack pnpm@9.15.0 test:unit --run src/components/etf-radar/HuijinTrajectoryPanel.test.ts -t 'renders daily change, validation status, and data date in the detail table'`
- RED 1 结果：`1 failed, 8 skipped`。
- RED 2：移动端内部滚动契约测试要求表容器 `overflow-x:auto`、稳定 `760px` 表格宽度且不隐藏表头；旧 CSS 不满足。
- RED 2 命令：`cd apps/web-vue && corepack pnpm@9.15.0 test:unit --run src/components/etf-radar/HuijinTrajectoryPanel.test.ts -t 'keeps the responsive overflow contract'`
- RED 2 结果：`1 failed, 8 skipped`。
- 修复：表格改为 ETF、确认持仓比例、累计偏离、最近日变化、验证状态、数据日期六列；配对组使用既有 `validationStateLabel`，无配对显示“不适用”；缺份额不伪造数据日期。表格在移动端保留表头并在自身内部横向滚动，文档容器继续禁止横向溢出。
- GREEN 命令：`cd apps/web-vue && corepack pnpm@9.15.0 test:unit --run src/components/etf-radar/HuijinTrajectoryPanel.test.ts`
- GREEN 结果：`1 test file passed, 9 tests passed`。
- 文件：`apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.vue`、`apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.test.ts`。

### I7 只尝试一个真实候选日期

- RED：新增 `test_overview_tries_reported_candidate_dates_newest_to_oldest_until_complete`；provider 给出 07-17/07-16，07-17 不完整、07-16 完整时，结果仍停在 `2026-07-20`。
- RED 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -k tries_reported_candidate_dates_newest_to_oldest_until_complete -vv`
- RED 结果：`1 failed, 46 deselected`。
- 修复：对 provider 的真实候选日期去重并降序尝试；不完整且无请求失败时继续更早候选；遇请求失败立即停止。增加停止测试确保不会访问更早日期。
- GREEN 1：同一目标命令结果 `1 passed, 46 deselected`。
- GREEN 2 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -k stops_reported_date_fallback_after_request_failure -vv`
- GREEN 2 结果：`1 passed, 46 deselected`。
- 文件：`apps/api/app/services/capital_signals.py`、`apps/api/tests/test_capital_signals.py`。

### M1 合法与非法日期混合仍被接受

- RED：新增 `test_szse_share_parser_rejects_mixed_valid_and_invalid_scale_dates`；`2026-07-17 + 2026-02-31` 实际仍返回一行。
- RED 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signal_providers.py -k mixed_valid_and_invalid_scale_dates -vv`
- RED 结果：`1 failed, 27 deselected`。
- 修复：先收集所有 ISO token，再逐个做日历校验；任一 token 非法即整体拒绝，合法日期仍必须唯一。
- GREEN：同一命令结果 `1 passed, 27 deselected`。
- 文件：`apps/api/app/providers/capital_signals.py`、`apps/api/tests/test_capital_signal_providers.py`。

### M2 无日期元数据触发五轮全池探测

- RED：新增 `test_overview_does_not_probe_full_universe_without_reported_dates`；原调用为目标日加五个回溯日，共六次十只 ETF 全池请求。
- RED 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -k does_not_probe_full_universe_without_reported_dates -vv`
- RED 结果：`1 failed, 46 deselected`，实际 full-universe calls 为 6 次。
- 修复：与 I7 统一为 provider 候选日期驱动；无 `available_trade_dates` 时不做任何全池日期猜测，并返回明确 stale 状态。
- GREEN：同一命令结果 `1 passed, 46 deselected`。
- 文件：`apps/api/app/services/capital_signals.py`、`apps/api/tests/test_capital_signals.py`。

## 完整验证

运行前检查：`env | rg '^VITE_' || true` 无输出，Vue 命令没有环境覆盖。

### Backend suite

```bash
cd apps/api
.venv/bin/pytest tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py tests/test_capital_signal_providers.py tests/test_capital_signals.py tests/test_capital_signal_sampler.py tests/test_api.py -q
```

结果：exit 0，`261 passed in 18.06s`。

### Ruff

```bash
cd apps/api
.venv/bin/ruff check app/models.py app/providers/capital_signals.py app/services/huijin_etf_activity.py app/services/capital_signal_store.py app/services/capital_signals.py app/services/capital_signal_sampler.py app/main.py tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py tests/test_capital_signal_providers.py tests/test_capital_signals.py tests/test_capital_signal_sampler.py tests/test_api.py
```

结果：exit 0，`All checks passed!`。

### Vue unit

```bash
cd apps/web-vue
corepack pnpm@9.15.0 test:unit --run
```

结果：exit 0，`26 passed test files`，`143 passed tests`。

### Vue typecheck

```bash
cd apps/web-vue
corepack pnpm@9.15.0 typecheck
```

结果：exit 0，`vue-tsc --noEmit --skipLibCheck` 无错误。

### Vue build

```bash
cd apps/web-vue
corepack pnpm@9.15.0 build
```

结果：exit 0，`Build successful. Please see dist directory`。

### Git 检查

- `apps/web-vue/src/typings/components.d.ts`：已还原为 HEAD 内容，不进入提交。
- `git diff --check`：exit 0，无输出。

## 改动文件汇总

- `.superpowers/sdd/final-fix-report.md`
- `apps/api/app/providers/capital_signals.py`
- `apps/api/app/services/capital_signals.py`
- `apps/api/tests/test_capital_signal_providers.py`
- `apps/api/tests/test_capital_signals.py`
- `apps/web-vue/build/plugins/unocss.ts`
- `apps/web-vue/build/plugins/unplugin.ts`
- `apps/web-vue/src/constants/icon.ts`
- `apps/web-vue/src/components/custom/svg-icon.vue`
- `apps/web-vue/src/components/custom/svg-icon.test.ts`
- `apps/web-vue/src/utils/domain/huijinTrajectory.ts`
- `apps/web-vue/src/utils/domain/huijinTrajectory.test.ts`
- `apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.vue`
- `apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.test.ts`

## 2026-07-21 Final Re-review Fixes

本轮仅处理复审新增的 2 个 Important；未修改已关闭的前端修复，未发现规格冲突。

### I1 SZSE 日期 provenance 与四态缓存边界

- RED 1：`test_service_does_not_revive_unverified_szse_cache_after_network_failure` 预置旧 JSON 语义的 `159915.SZ@2026-07-17=9999`，本轮该符号网络失败。旧实现把它作为 failed cache 复活，实际 `total_shares=9999`。
- RED 1 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -k does_not_revive_unverified_szse_cache_after_network_failure -vv`
- RED 1 结果：`1 failed, 49 deselected`，失败值 `9999.0 is None`。
- RED 2：`test_service_reuses_verified_same_day_cache_after_temporary_empty_response` 预置十只合法同日缓存，其中 SZ 行带 strict provenance；provider 返回同日元数据但暂时空数据。旧实现 `available_core_count=0`。
- RED 2 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -k reuses_verified_same_day_cache_after_temporary_empty_response -vv`
- RED 2 结果：`1 failed, 49 deselected`，实际覆盖 `0`，预期 `7`。
- RED 3：strict parser 行、旧持久化 JSON 默认值和 provider 空数据分类分别由以下命令确认缺失：
  - `cd apps/api && .venv/bin/pytest tests/test_capital_signal_store.py -k legacy_szse_share_dates_as_unverified -vv` -> `1 failed, 9 deselected`，字段实际为 `None`。
  - `cd apps/api && .venv/bin/pytest tests/test_capital_signal_providers.py -k szse_current_share_parser_does_not_invent_history -vv` -> `1 failed, 28 deselected`，字段实际为 `None`。
  - `cd apps/api && .venv/bin/pytest tests/test_capital_signal_providers.py -k distinguishes_same_date_empty_szse_from_date_rejection -vv` -> `1 failed, 28 deselected`，`empty_symbols` 实际为空。
- 修复：`EtfSharePoint.date_validation` 默认 `unverified`，strict `metadata.cols.dqgm` 解析行标记 `szse_dqgm_v1`。provider 将结果分为有效 strict 行、`rejected_symbols`（日期缺失/非法/明确错配）、`empty_symbols`（同日元数据但无有效行）和 `failed_symbols`（网络/请求失败）。服务对明确 rejected 同日行直接删除；failed/empty 时保留 SH 同日缓存，但 SZ 仅复用 `szse_dqgm_v1`，未验证旧 SZ 行从历史移除。首轮与候选日期路径使用同一规则。
- GREEN：
  - 两条服务复现：`2 passed, 48 deselected`。
  - provenance/store 边界：`2 passed, 8 deselected`（含原损坏文件守卫）。
  - strict parser 与四态 provider 测试分别 `1 passed, 28 deselected`。
- 文件：`apps/api/app/models.py`、`apps/api/app/providers/capital_signals.py`、`apps/api/app/services/capital_signals.py`、`apps/api/tests/test_capital_signal_store.py`、`apps/api/tests/test_capital_signal_providers.py`、`apps/api/tests/test_capital_signals.py`。

### I2 `history()` 按 snapshot 状态协调首载

- RED：`test_history_refreshes_when_only_sse_history_exists_without_snapshot` 仅预置 `510300.SH@2026-07-16` 且无 snapshot。旧实现 full-universe provider 调用为 `[]`，未刷新最新/SZ 历史。
- RED 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -k refreshes_when_only_sse_history_exists_without_snapshot -vv`
- RED 结果：`1 failed, 51 deselected`。
- 守卫：`test_history_uses_fresh_compatible_snapshot_without_refresh` 在修复前已通过，证明新鲜 snapshot 路径本来不重复请求；修复后继续保持 provider 调用为零。
- 修复：进入 `RLock` 后先加载 snapshot；仅当 snapshot 存在、兼容且 TTL 新鲜时直接使用其披露日，否则调用一次 `overview()` 并无条件重新读取 history。SZ 未来日期清理在刷新/重读之后执行。
- GREEN 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -k 'refreshes_when_only_sse_history_exists_without_snapshot or uses_fresh_compatible_snapshot_without_refresh' -q`
- GREEN 结果：`2 passed, 50 deselected`。
- 文件：`apps/api/app/services/capital_signals.py`、`apps/api/tests/test_capital_signals.py`。

### 本轮验证

- 受影响回归：`cd apps/api && .venv/bin/pytest tests/test_capital_signal_store.py tests/test_capital_signal_providers.py tests/test_capital_signals.py -q` -> exit 0，`91 passed in 0.54s`。
- 完整后端计划 suite：`cd apps/api && .venv/bin/pytest tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py tests/test_capital_signal_providers.py tests/test_capital_signals.py tests/test_capital_signal_sampler.py tests/test_api.py -q` -> exit 0，`267 passed in 15.87s`。
- 完整 Ruff：`cd apps/api && .venv/bin/ruff check app/models.py app/providers/capital_signals.py app/services/huijin_etf_activity.py app/services/capital_signal_store.py app/services/capital_signals.py app/services/capital_signal_sampler.py app/main.py tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py tests/test_capital_signal_providers.py tests/test_capital_signals.py tests/test_capital_signal_sampler.py tests/test_api.py` -> exit 0，`All checks passed!`。
- API/前端影响：`date_validation` 仅属于内部 `EtfSharePoint` 持久化模型，未进入 API response 或前端类型；本轮无前端文件改动。
- `git diff --check`：exit 0，无输出。

## 2026-07-21 Third Targeted Re-review Fix

本轮仅处理第三次复审剩余的 1 个 Important；改动范围限定为 service、对应测试和本报告。

### I1 候选日先合并 trusted cache 再判断完整性

- RED 1：`test_overview_candidate_empty_uses_verified_cache_for_core_coverage` 预置 `159915.SZ@2026-07-17=2222` 且 `date_validation="szse_dqgm_v1"`；候选日其余九只新抓取成功，`159915.SZ` 为 `empty_symbols`。旧实现结果仍为 `trade_date=2026-07-20`。
- RED 1 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -k candidate_empty_uses_verified_cache_for_core_coverage -vv`
- RED 1 结果：`1 failed, 53 deselected`，实际日期 `2026-07-20`，预期 `2026-07-17`。
- RED 2：`test_overview_candidate_failure_uses_verified_cache_for_core_coverage` 使用相同 verified cache，并将候选日该符号标为 `failed_symbols`。旧实现同样停在 `2026-07-20`。
- RED 2 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -k candidate_failure_uses_verified_cache_for_core_coverage -vv`
- RED 2 结果：`1 failed, 53 deselected`，实际日期 `2026-07-20`，预期 `2026-07-17`。
- rejected 守卫：既有候选日拒绝测试改为预置 verified cache；`test_overview_candidate_date_rejects_verified_cached_symbols` 在修复前后均通过，证明明确拒绝行不会进入 trusted merge。
- 修复：候选请求完成四态清理后，先执行 `merged_fallback_rows = _merge_share_history(trusted_fallback_rows, fallback_rows)`；`_has_complete_core_coverage()` 和选中候选后的 `current_rows` 均使用该合并结果。
- GREEN 命令：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -k 'candidate_empty_uses_verified_cache_for_core_coverage or candidate_failure_uses_verified_cache_for_core_coverage or candidate_date_rejects_verified_cached_symbols' -q`
- GREEN 结果：`3 passed, 51 deselected`。
- 文件：`apps/api/app/services/capital_signals.py`、`apps/api/tests/test_capital_signals.py`。

### 本轮验证

- Service 全文件：`cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -q` -> exit 0，`54 passed in 0.49s`。
- 完整后端计划 suite 首轮：`267 passed, 2 failed`；失败为未改动的 auction 后台时序测试 `test_auction_snapshot_refresh_job_reuses_active_job` 和 `test_auction_timeline_returns_locked_observation_points`。
- 两条 auction 测试分别在独立 pytest 进程复现：均 `1 passed, 135 deselected`。
- 完整后端计划 suite 新进程重跑：`cd apps/api && .venv/bin/pytest tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py tests/test_capital_signal_providers.py tests/test_capital_signals.py tests/test_capital_signal_sampler.py tests/test_api.py -q` -> exit 0，`269 passed in 10.75s`。
- Ruff：`cd apps/api && .venv/bin/ruff check app/models.py app/providers/capital_signals.py app/services/huijin_etf_activity.py app/services/capital_signal_store.py app/services/capital_signals.py app/services/capital_signal_sampler.py app/main.py tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py tests/test_capital_signal_providers.py tests/test_capital_signals.py tests/test_capital_signal_sampler.py tests/test_api.py` -> exit 0，`All checks passed!`。
- `git diff --check`：exit 0，无输出。
