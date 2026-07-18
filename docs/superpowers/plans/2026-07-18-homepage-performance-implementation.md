# 首页首屏性能优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让首页市场状态先于慢面板可用，并通过 15 秒内存缓存与同键请求去重减少重复 HTTP 请求。

**Architecture:** 新增一个无框架依赖的首页请求缓存协调器，按 key 保存短时成功值和进行中的 Promise；失败不写入成功缓存，Promise 身份检查防止旧请求覆盖强制刷新的新请求。`MarketOverviewWorkbench` 将市场概览作为关键请求独立结束 loading，板块/情绪以及视口触发的趋势请求继续使用现有 `PanelState` 与请求代次保护，并通过缓存协调器复用请求。

**Tech Stack:** Next.js 15, React 19, TypeScript 5.7, Node `node:test`, Playwright smoke checks.

---

## 文件结构

| Path | Responsibility |
| --- | --- |
| `apps/web/lib/marketOverviewCache.ts` | 首页短时内存缓存、TTL、并发 Promise 去重和清理。 |
| `apps/web/lib/marketOverviewCache.test.ts` | 缓存命中、过期、并发、强制刷新和失败行为测试。 |
| `apps/web/app/MarketOverviewWorkbench.tsx` | 接入各首页面板缓存，拆分关键请求与后台请求的 loading 生命周期。 |
| `apps/web/lib/marketOverview.test.ts` | 首页加载调用边界、趋势延迟激活和刷新行为契约测试。 |

### Task 1: 建立缓存协调器

**Files:**
- Create: `apps/web/lib/marketOverviewCache.ts`
- Create: `apps/web/lib/marketOverviewCache.test.ts`

- [ ] **Step 1: 写缓存行为的失败测试**

创建测试覆盖以下单一行为：成功结果在 TTL 内命中且不再次调用 request；TTL 到期后重新调用；相同 key 的并发调用共享一个 Promise；`force: true` 绕过成功缓存；请求失败不会留下可命中的失败值；旧请求在强制刷新请求之后完成时不会覆盖新值。

测试使用可控 `now`，不依赖真实等待：

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { createMemoryRequestCache } from "./marketOverviewCache";

test("cache returns a fresh value without repeating the request", async () => {
  let calls = 0;
  const cache = createMemoryRequestCache({ now: () => 1000, ttlMs: 15_000 });
  const request = async () => {
    calls += 1;
    return "market";
  };

  assert.equal(await cache.get("market:2026-07-18", request), "market");
  assert.equal(await cache.get("market:2026-07-18", request), "market");
  assert.equal(calls, 1);
});

test("cache expires values after the configured TTL", async () => {
  let now = 1000;
  let calls = 0;
  const cache = createMemoryRequestCache({ now: () => now, ttlMs: 15_000 });
  const request = async () => ++calls;

  assert.equal(await cache.get("market", request), 1);
  now = 16_001;
  assert.equal(await cache.get("market", request), 2);
});

test("cache shares an in-flight request for the same key", async () => {
  let resolveRequest!: (value: string) => void;
  let calls = 0;
  const pending = new Promise<string>((resolve) => { resolveRequest = resolve; });
  const cache = createMemoryRequestCache({ now: () => 1000, ttlMs: 15_000 });
  const request = () => {
    calls += 1;
    return pending;
  };

  const first = cache.get("sector", request);
  const second = cache.get("sector", request);
  assert.equal(first, second);
  resolveRequest("sector");
  assert.equal(await first, "sector");
  assert.equal(calls, 1);
});

test("force refresh bypasses the cached value and failures do not poison it", async () => {
  let calls = 0;
  const cache = createMemoryRequestCache({ now: () => 1000, ttlMs: 15_000 });
  const request = async () => {
    calls += 1;
    if (calls === 2) throw new Error("temporary failure");
    return calls;
  };

  assert.equal(await cache.get("emotion", request), 1);
  await assert.rejects(cache.get("emotion", request, { force: true }), /temporary failure/);
  assert.equal(await cache.get("emotion", request), 1);
  assert.equal(calls, 2);
});

test("an older forced request cannot overwrite a newer forced request", async () => {
  let resolveOld!: (value: string) => void;
  let resolveNew!: (value: string) => void;
  const oldRequest = new Promise<string>((resolve) => { resolveOld = resolve; });
  const newRequest = new Promise<string>((resolve) => { resolveNew = resolve; });
  const cache = createMemoryRequestCache({ now: () => 1000, ttlMs: 15_000 });

  const old = cache.get("market", () => oldRequest, { force: true });
  const fresh = cache.get("market", () => newRequest, { force: true });
  resolveNew("new");
  assert.equal(await fresh, "new");
  resolveOld("old");
  assert.equal(await old, "old");
  assert.equal(await cache.get("market", async () => "unexpected"), "new");
});
```

- [ ] **Step 2: 运行测试确认 RED**

运行：

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
node --experimental-strip-types --test lib/marketOverviewCache.test.ts
```

预期：失败，原因是 `marketOverviewCache.ts` 尚未存在。

- [ ] **Step 3: 实现最小缓存协调器**

导出 `createMemoryRequestCache<T>({ now, ttlMs })`，返回 `get(key, request, options?)` 和 `clear()`。内部 entry 保存 `value`、`expiresAt` 和 `promise`；成功时仅当当前 entry 的 Promise 仍是本次 Promise 才写入值，失败时仅清除本次 Promise，不删除更新后的 entry。`force` 只跳过已完成值和已有 Promise 的复用，不改变返回类型。

- [ ] **Step 4: 运行缓存测试确认 GREEN**

运行：

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
node --experimental-strip-types --test lib/marketOverviewCache.test.ts
```

预期：5 个缓存测试全部通过。

- [ ] **Step 5: 提交缓存单元**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/web/lib/marketOverviewCache.ts apps/web/lib/marketOverviewCache.test.ts
git commit -m "feat: add homepage request cache"
```

### Task 2: 接入核心首页请求并拆分 loading 生命周期

**Files:**
- Modify: `apps/web/app/MarketOverviewWorkbench.tsx`
- Modify: `apps/web/lib/marketOverview.test.ts`

- [ ] **Step 1: 写首页加载契约的失败测试**

在现有源码契约测试中增加断言：`MarketOverviewWorkbench` 创建专用缓存、核心请求使用 `getMarketOverview`、板块和情绪请求不包在控制全局 loading 的等待链中、趋势继续由 `IntersectionObserver` 激活，并且手动刷新传入 `force: true`。

测试只断言稳定的调用边界，不断言实现变量名称：

```ts
test("homepage treats market overview as the critical refresh request", () => {
  const source = readFileSync(new URL("../app/MarketOverviewWorkbench.tsx", import.meta.url), "utf8");

  assert.match(source, /createMemoryRequestCache/);
  assert.match(source, /getMarketOverview/);
  assert.match(source, /getHomepagePanel/);
  assert.match(source, /force: true/);
  assert.match(source, /IntersectionObserver/);
});
```

- [ ] **Step 2: 运行定向测试确认 RED**

运行：

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
node --experimental-strip-types --test --test-name-pattern="critical refresh request" lib/marketOverview.test.ts
```

预期：失败，因为首页尚未接入缓存协调器。

- [ ] **Step 3: 在首页组件中接入缓存**

在 `MarketOverviewWorkbench.tsx` 模块级创建 15 秒缓存实例，并用一个小型 `getHomepagePanel` 包装现有请求：

```ts
const homepageCache = createMemoryRequestCache({ ttlMs: 15_000 });

function getHomepagePanel<T>(name: string, tradeDate: string, request: () => Promise<T>, force = false) {
  return homepageCache.get(`homepage:${name}:${tradeDate}`, request, { force });
}
```

`refresh(force = false)` 中：

- 市场概览调用 `getHomepagePanel("market", tradeDate, getMarketOverview, force)`，其 Promise 结束后立即结束 `refreshing`。
- 板块资金流和情绪摘要分别调用 `getHomepagePanel`，仍通过 `executeLatestOnly` 独立提交 `PanelState`，但不再决定 `refreshing` 的结束时间。
- 初次 `useEffect` 调用 `refresh(false)`；刷新按钮和面板重试回调调用 `refresh(true)`。
- 保留 `settleRequest`，确保后台请求失败仍转换为面板 error/stale 状态，不产生未处理 Promise rejection。

- [ ] **Step 4: 运行首页契约和类型检查**

运行：

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
node --experimental-strip-types --test lib/marketOverview.test.ts
npx tsc --noEmit
```

预期：现有首页测试和 TypeScript 检查通过。

### Task 3: 接入趋势请求并覆盖刷新与卸载边界

**Files:**
- Modify: `apps/web/app/MarketOverviewWorkbench.tsx`
- Modify: `apps/web/lib/marketOverview.test.ts`

- [ ] **Step 1: 写趋势缓存契约测试**

增加源码断言：趋势请求使用 `getHomepagePanel`，趋势激活仍由 `IntersectionObserver` 控制，盘中定时采样使用强制刷新，趋势刷新不会调用首页核心 `refresh`。

```ts
test("homepage caches activated trend requests without coupling them to core refresh", () => {
  const source = readFileSync(new URL("../app/MarketOverviewWorkbench.tsx", import.meta.url), "utf8");

  assert.match(source, /getHomepagePanel\("sector-trend"/);
  assert.match(source, /getHomepagePanel\("emotion-trend"/);
  assert.match(source, /refreshEmotion/);
  assert.match(source, /setInterval\([\s\S]*?180_000/);
  assert.doesNotMatch(source, /onRefreshEmotion=\{\(\) => void refreshTrends\(\)\}/);
});
```

- [ ] **Step 2: 运行定向测试确认 RED**

运行：

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
node --experimental-strip-types --test --test-name-pattern="activated trend requests" lib/marketOverview.test.ts
```

预期：失败，因为趋势请求尚未使用首页缓存键。

- [ ] **Step 3: 为趋势和情绪采样增加缓存键**

在 `refreshTrends(force = false)` 中分别使用：

```ts
getHomepagePanel("sector-trend", tradeDate, () => getSectorReplicaRadar({ mode: "strength", limit: 6, stockLimit: 1 }), force)
getHomepagePanel("emotion-trend", tradeDate, () => getMarketEmotionSnapshot(tradeDate, 80, false), force)
```

`refreshEmotion(force = true)` 默认强制读取实时情绪，保持盘中 180 秒采样语义；趋势区首次激活使用 `refreshTrends(false)`，手动刷新使用 `refreshTrends(true)`。继续使用现有三个请求代次 ref，组件卸载时清理 observer 和 interval。

- [ ] **Step 4: 运行完整前端测试**

运行：

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
npm test
```

预期：项目现有测试全部通过，包含新增缓存和首页契约测试。

### Task 4: 生产构建与浏览器性能验证

**Files:**
- Inspect: `apps/web/app/MarketOverviewWorkbench.tsx`
- Inspect: `apps/web/lib/marketOverviewCache.ts`
- Inspect: `apps/web/lib/marketOverview.test.ts`
- Inspect: `apps/web/lib/marketOverviewCache.test.ts`

- [ ] **Step 1: 运行静态质量检查**

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
npx tsc --noEmit
cd /Users/kale/Documents/strong-stock-screener
git diff --check
```

预期：命令退出码为 0，且无 whitespace error。

- [ ] **Step 2: 构建生产包**

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
npm run build
```

预期：Next.js 生产构建完成，首页路由生成成功。

- [ ] **Step 3: 启动或复用本地服务并检查首页**

使用现有 `http://127.0.0.1:3123/`；若服务未运行，执行：

```bash
cd /Users/kale/Documents/strong-stock-screener
./scripts/start-local.sh
```

在 `1280x720` 和 `390x844` 下验证：市场状态先出现；慢板块或情绪请求不会遮挡市场状态；趋势区进入视口前不发趋势请求；连续刷新只保留最新结果；页面 `document.documentElement.scrollWidth === document.documentElement.clientWidth`。

- [ ] **Step 4: 检查最终差异并提交**

```bash
cd /Users/kale/Documents/strong-stock-screener
git status --short
git diff --check
git diff --stat
git add apps/web/app/MarketOverviewWorkbench.tsx apps/web/lib/marketOverview.test.ts
git commit -m "perf: speed up homepage market loading"
```

只提交本计划涉及的首页性能文件；其他已有未提交改动保持原样。
