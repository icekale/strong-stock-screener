# Professional Workbench Hardening Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first product-hardening layer: observable caches, system status APIs, and a settings-page status console so slow data sources and stale snapshots become visible instead of feeling like random failures.

**Architecture:** Keep the current single-container FastAPI + Next.js architecture. Harden the existing in-memory `TtlCache`, add a lightweight cache registry and system status router surface inside `main.py`, then expose that status through typed frontend APIs and a compact settings-page panel. This phase intentionally does not rewrite screeners, trading rules, or the homepage.

**Tech Stack:** FastAPI, Pydantic v2, Python threading primitives, pytest, Next.js 15, React 19, TypeScript, Ant Design 6.

---

## Scope Check

This plan implements only phase one from `docs/superpowers/specs/2026-07-05-professional-workbench-hardening-design.md`:

- cache observability
- `TtlCache` hardening
- `/api/system/status`, `/api/system/cache`, `/api/system/cache/clear`
- frontend types and API clients
- settings page system status panel

It deliberately does not implement the later homepage redesign, full system console redesign, router split, or all smoke tests. Those need separate plans after this phase lands.

## File Structure

- Modify `apps/api/app/services/short_term_cache.py`
  - Owns `TtlCache`, cache stats, stale-return behavior, and safe background refresh.
- Create `apps/api/app/services/cache_registry.py`
  - Owns registration, cache summaries, and cache clearing.
- Modify `apps/api/app/models.py`
  - Adds Pydantic response models for cache and system status.
- Modify `apps/api/app/main.py`
  - Names/registers current caches and exposes system status APIs.
- Modify `apps/api/tests/test_short_term_cache.py`
  - Covers non-blocking factory execution, stale returns, refresh errors, and stats.
- Create `apps/api/tests/test_system_status.py`
  - Covers new system status/cache APIs and cache clearing.
- Modify `apps/web/lib/types.ts`
  - Adds system status response types.
- Modify `apps/web/lib/api.ts`
  - Adds system status API client functions.
- Create `apps/web/lib/systemStatus.test.ts`
  - Covers frontend cache freshness helpers.
- Create `apps/web/lib/systemStatus.ts`
  - Small pure helper for labels and stale-cache judgment.
- Create `apps/web/components/system/SystemStatusPanel.tsx`
  - Reusable status panel for the settings page.
- Modify `apps/web/app/settings/SettingsWorkspace.tsx`
  - Loads and displays system status.

---

### Task 1: Harden `TtlCache`

**Files:**
- Modify: `apps/api/app/services/short_term_cache.py`
- Modify: `apps/api/tests/test_short_term_cache.py`

- [ ] **Step 1: Add failing cache stats and lock behavior tests**

Append these tests to `apps/api/tests/test_short_term_cache.py`:

```python
def test_get_or_set_does_not_hold_lock_while_factory_runs() -> None:
    cache = TtlCache[str](ttl_seconds=60, name="test-cache")
    factory_started = Event()
    release_factory = Event()
    second_call_finished = Event()

    def slow_factory() -> str:
        factory_started.set()
        release_factory.wait(timeout=1)
        return "slow"

    def run_slow_call() -> None:
        assert cache.get_or_set("slow", slow_factory) == "slow"

    from threading import Thread

    thread = Thread(target=run_slow_call)
    thread.start()
    assert factory_started.wait(timeout=1)

    def fast_factory() -> str:
        return "fast"

    assert cache.get_or_set("fast", fast_factory) == "fast"
    second_call_finished.set()
    release_factory.set()
    thread.join(timeout=1)

    assert second_call_finished.is_set()


def test_cache_snapshot_records_hits_misses_and_refresh_error() -> None:
    cache = TtlCache[str](ttl_seconds=0.01, name="quotes")

    assert cache.get_or_set("key", lambda: "v1") == "v1"
    assert cache.get_or_set("key", lambda: "unused") == "v1"
    sleep(0.02)

    def failing_factory() -> str:
        raise RuntimeError("provider down")

    assert cache.get_or_refresh("key", failing_factory) == "v1"
    for _ in range(100):
        snapshot = cache.snapshot()
        if snapshot["refresh_error_count"] == 1:
            break
        sleep(0.01)

    snapshot = cache.snapshot()
    assert snapshot["name"] == "quotes"
    assert snapshot["hits"] >= 1
    assert snapshot["misses"] >= 1
    assert snapshot["stale_hits"] >= 1
    assert snapshot["refresh_error_count"] == 1
    assert snapshot["last_error"] == "provider down"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
uv run pytest tests/test_short_term_cache.py -q
```

Expected: fails because `TtlCache.__init__()` does not accept `name` and `snapshot()` does not exist.

- [ ] **Step 3: Replace `TtlCache` implementation**

Replace `apps/api/app/services/short_term_cache.py` with:

```python
from __future__ import annotations

from threading import RLock, Thread
from time import monotonic
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class TtlCache(Generic[T]):
    def __init__(self, ttl_seconds: float = 90, *, name: str = "cache") -> None:
        self.name = name
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, tuple[float, T]] = {}
        self._refreshing: set[str] = set()
        self._lock = RLock()
        self._hits = 0
        self._misses = 0
        self._stale_hits = 0
        self._refresh_count = 0
        self._refresh_error_count = 0
        self._last_refresh_started_at: float | None = None
        self._last_refresh_finished_at: float | None = None
        self._last_error: str | None = None

    def get_or_set(self, key: str, factory: Callable[[], T]) -> T:
        with self._lock:
            now = monotonic()
            cached = self._items.get(key)
            if cached is not None:
                expires_at, value = cached
                if expires_at > now:
                    self._hits += 1
                    return value
            self._misses += 1

        value = factory()
        with self._lock:
            self._items[key] = (monotonic() + self.ttl_seconds, value)
            self._refresh_count += 1
            self._last_refresh_finished_at = monotonic()
            self._last_error = None
        return value

    def get_or_refresh(self, key: str, factory: Callable[[], T]) -> T:
        should_refresh = False
        with self._lock:
            now = monotonic()
            cached = self._items.get(key)
            if cached is not None:
                expires_at, value = cached
                if expires_at > now:
                    self._hits += 1
                    return value
                self._stale_hits += 1
                if key not in self._refreshing:
                    self._refreshing.add(key)
                    self._last_refresh_started_at = monotonic()
                    should_refresh = True
                stale_value = value
            else:
                self._misses += 1
                stale_value = None

        if should_refresh:
            Thread(target=self._refresh, args=(key, factory), name=f"cache-refresh-{self.name}", daemon=True).start()
            return stale_value  # type: ignore[return-value]

        if stale_value is not None:
            return stale_value

        value = factory()
        with self._lock:
            self._items[key] = (monotonic() + self.ttl_seconds, value)
            self._refresh_count += 1
            self._last_refresh_finished_at = monotonic()
            self._last_error = None
        return value

    def get_if_fresh(self, key: str) -> T | None:
        with self._lock:
            now = monotonic()
            cached = self._items.get(key)
            if cached is None:
                return None
            expires_at, value = cached
            if expires_at <= now:
                return None
            self._hits += 1
            return value

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._refreshing.clear()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            now = monotonic()
            fresh_count = sum(1 for expires_at, _ in self._items.values() if expires_at > now)
            oldest_expires_in = min(
                (expires_at - now for expires_at, _ in self._items.values()),
                default=None,
            )
            return {
                "name": self.name,
                "ttl_seconds": self.ttl_seconds,
                "size": len(self._items),
                "fresh_count": fresh_count,
                "refreshing_count": len(self._refreshing),
                "hits": self._hits,
                "misses": self._misses,
                "stale_hits": self._stale_hits,
                "refresh_count": self._refresh_count,
                "refresh_error_count": self._refresh_error_count,
                "last_refresh_started_at": self._last_refresh_started_at,
                "last_refresh_finished_at": self._last_refresh_finished_at,
                "last_error": self._last_error,
                "oldest_expires_in_seconds": oldest_expires_in,
            }

    def _refresh(self, key: str, factory: Callable[[], T]) -> None:
        try:
            value = factory()
            with self._lock:
                self._items[key] = (monotonic() + self.ttl_seconds, value)
                self._refresh_count += 1
                self._last_refresh_finished_at = monotonic()
                self._last_error = None
        except Exception as exc:
            with self._lock:
                self._refresh_error_count += 1
                self._last_refresh_finished_at = monotonic()
                self._last_error = str(exc)
        finally:
            with self._lock:
                self._refreshing.discard(key)
```

- [ ] **Step 4: Run cache tests**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
uv run pytest tests/test_short_term_cache.py -q
```

Expected: all tests in `test_short_term_cache.py` pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/api/app/services/short_term_cache.py apps/api/tests/test_short_term_cache.py
git commit -m "Harden short term cache observability"
```

---

### Task 2: Add Cache Registry

**Files:**
- Create: `apps/api/app/services/cache_registry.py`
- Create: `apps/api/tests/test_cache_registry.py`

- [ ] **Step 1: Write failing registry tests**

Create `apps/api/tests/test_cache_registry.py`:

```python
from __future__ import annotations

from app.services.cache_registry import CacheRegistry
from app.services.short_term_cache import TtlCache


def test_cache_registry_summarizes_registered_caches() -> None:
    registry = CacheRegistry()
    cache = TtlCache[str](ttl_seconds=30, name="market")
    cache.get_or_set("a", lambda: "value")

    registry.register("market", cache, group="home")
    summary = registry.summary()

    assert summary["total"] == 1
    assert summary["items"][0]["name"] == "market"
    assert summary["items"][0]["group"] == "home"
    assert summary["items"][0]["size"] == 1


def test_cache_registry_clears_one_group() -> None:
    registry = CacheRegistry()
    home_cache = TtlCache[str](ttl_seconds=30, name="home")
    stock_cache = TtlCache[str](ttl_seconds=30, name="stock")
    home_cache.get_or_set("a", lambda: "home")
    stock_cache.get_or_set("a", lambda: "stock")

    registry.register("home", home_cache, group="home")
    registry.register("stock", stock_cache, group="stock")
    cleared = registry.clear(group="home")

    assert cleared == ["home"]
    assert home_cache.snapshot()["size"] == 0
    assert stock_cache.snapshot()["size"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
uv run pytest tests/test_cache_registry.py -q
```

Expected: fails because `app.services.cache_registry` does not exist.

- [ ] **Step 3: Implement registry**

Create `apps/api/app/services/cache_registry.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Protocol


class CacheLike(Protocol):
    name: str

    def clear(self) -> None: ...

    def snapshot(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class RegisteredCache:
    name: str
    group: str
    cache: CacheLike


class CacheRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._items: dict[str, RegisteredCache] = {}

    def register(self, name: str, cache: CacheLike, *, group: str) -> None:
        with self._lock:
            self._items[name] = RegisteredCache(name=name, group=group, cache=cache)

    def summary(self) -> dict[str, object]:
        with self._lock:
            items = []
            for item in sorted(self._items.values(), key=lambda value: value.name):
                snapshot = item.cache.snapshot()
                snapshot["name"] = item.name
                snapshot["group"] = item.group
                items.append(snapshot)
            return {"total": len(items), "items": items}

    def clear(self, *, group: str | None = None) -> list[str]:
        cleared: list[str] = []
        with self._lock:
            for item in self._items.values():
                if group is not None and item.group != group:
                    continue
                item.cache.clear()
                cleared.append(item.name)
        return sorted(cleared)
```

- [ ] **Step 4: Run registry tests**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
uv run pytest tests/test_cache_registry.py -q
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/api/app/services/cache_registry.py apps/api/tests/test_cache_registry.py
git commit -m "Add cache registry"
```

---

### Task 3: Add System Status API

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_system_status.py`

- [ ] **Step 1: Write failing API tests**

Create `apps/api/tests/test_system_status.py`:

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import MARKET_OVERVIEW_CACHE, app


def test_system_cache_api_lists_registered_caches() -> None:
    client = TestClient(app)

    response = client.get("/api/system/cache")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    names = {item["name"] for item in payload["items"]}
    assert "market_overview" in names


def test_system_cache_clear_clears_registered_cache() -> None:
    client = TestClient(app)
    MARKET_OVERVIEW_CACHE.get_or_set("unit-test", lambda: object())

    response = client.post("/api/system/cache/clear")

    assert response.status_code == 200
    assert "market_overview" in response.json()["cleared"]


def test_system_status_exposes_jobs_and_cache_summary() -> None:
    client = TestClient(app)

    response = client.get("/api/system/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert "generated_at" in payload
    assert payload["cache"]["total"] >= 1
    job_names = {job["name"] for job in payload["jobs"]}
    assert "auction_sampler" in job_names
    assert "sector_workbench_sampler" in job_names
    assert "sentiment_monitor" in job_names
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
uv run pytest tests/test_system_status.py -q
```

Expected: fails because `/api/system/cache` and `/api/system/status` do not exist.

- [ ] **Step 3: Add response models**

Append these models near the other system-like models in `apps/api/app/models.py`:

```python
SystemConfidence = Literal["fresh", "stale", "partial", "degraded", "unavailable"]


class SystemCacheItem(BaseModel):
    name: str
    group: str
    ttl_seconds: float
    size: int
    fresh_count: int
    refreshing_count: int
    hits: int
    misses: int
    stale_hits: int
    refresh_count: int
    refresh_error_count: int
    last_refresh_started_at: float | None = None
    last_refresh_finished_at: float | None = None
    last_error: str | None = None
    oldest_expires_in_seconds: float | None = None


class SystemCacheSummary(BaseModel):
    total: int
    items: list[SystemCacheItem] = Field(default_factory=list)


class SystemJobStatus(BaseModel):
    name: str
    running: bool
    enabled: bool
    detail: str


class SystemStatusResponse(BaseModel):
    status: Literal["ok", "degraded"]
    generated_at: str
    cache: SystemCacheSummary
    jobs: list[SystemJobStatus] = Field(default_factory=list)
    confidence: SystemConfidence = "fresh"


class SystemCacheClearResponse(BaseModel):
    cleared: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Register caches and add system endpoints**

In `apps/api/app/main.py`, add imports:

```python
from app.services.cache_registry import CacheRegistry
```

Update cache declarations so every cache has a stable name:

```python
SHORT_TERM_SENTIMENT_CACHE: TtlCache[ShortTermSentimentResponse] = TtlCache(ttl_seconds=90, name="short_term_sentiment")
MARKET_EMOTION_CACHE: TtlCache[MarketEmotionSnapshotResponse] = TtlCache(ttl_seconds=45, name="market_emotion")
MARKET_OVERVIEW_CACHE: TtlCache[MarketOverviewResponse] = TtlCache(ttl_seconds=45, name="market_overview")
MARKET_RANKINGS_CACHE: TtlCache[MarketRankingsResponse] = TtlCache(ttl_seconds=45, name="market_rankings")
AUCTION_SNAPSHOT_CACHE: TtlCache[AuctionSnapshotResponse] = TtlCache(ttl_seconds=15, name="auction_snapshot")
SECTOR_RADAR_CACHE: TtlCache[SectorRadarResponse] = TtlCache(ttl_seconds=45, name="sector_radar")
PLATE_ROTATION_REFERENCE_CACHE: TtlCache[PlateRotationReferenceResponse] = TtlCache(ttl_seconds=120, name="plate_rotation_reference")
SECTOR_INTRADAY_CACHE: TtlCache[tuple[list[SectorWorkbenchSeries], StrongStockSourceStatus]] = TtlCache(
    ttl_seconds=90,
    name="sector_intraday",
)
SECTOR_THEME_ROWS_CACHE: TtlCache[tuple[list[dict[str, object]], StrongStockSourceStatus | None]] = TtlCache(
    ttl_seconds=300,
    name="sector_theme_rows",
)
STOCK_KLINE_CACHE: TtlCache[StockKlineResponse] = TtlCache(ttl_seconds=300, name="stock_kline")
STOCK_RESEARCH_CACHE: TtlCache[StockResearchResponse] = TtlCache(ttl_seconds=900, name="stock_research")
CACHE_REGISTRY = CacheRegistry()
for cache_name, cache_group, cache in [
    ("short_term_sentiment", "sentiment", SHORT_TERM_SENTIMENT_CACHE),
    ("market_emotion", "sentiment", MARKET_EMOTION_CACHE),
    ("market_overview", "home", MARKET_OVERVIEW_CACHE),
    ("market_rankings", "home", MARKET_RANKINGS_CACHE),
    ("auction_snapshot", "auction", AUCTION_SNAPSHOT_CACHE),
    ("sector_radar", "sectors", SECTOR_RADAR_CACHE),
    ("plate_rotation_reference", "sectors", PLATE_ROTATION_REFERENCE_CACHE),
    ("sector_intraday", "sectors", SECTOR_INTRADAY_CACHE),
    ("sector_theme_rows", "sectors", SECTOR_THEME_ROWS_CACHE),
    ("stock_kline", "stocks", STOCK_KLINE_CACHE),
    ("stock_research", "stocks", STOCK_RESEARCH_CACHE),
]:
    CACHE_REGISTRY.register(cache_name, cache, group=cache_group)
```

Import the new models from `app.models`:

```python
    SystemCacheClearResponse,
    SystemCacheSummary,
    SystemStatusResponse,
```

Add endpoints after `/health`:

```python
@app.get("/api/system/cache", response_model=SystemCacheSummary)
def get_system_cache() -> SystemCacheSummary:
    return SystemCacheSummary.model_validate(CACHE_REGISTRY.summary())


@app.post("/api/system/cache/clear", response_model=SystemCacheClearResponse)
def clear_system_cache(group: str | None = None) -> SystemCacheClearResponse:
    return SystemCacheClearResponse(cleared=CACHE_REGISTRY.clear(group=group))


@app.get("/api/system/status", response_model=SystemStatusResponse)
def get_system_status() -> SystemStatusResponse:
    cache = get_system_cache()
    jobs = _system_jobs()
    has_cache_errors = any(item.refresh_error_count > 0 for item in cache.items)
    status = "degraded" if has_cache_errors else "ok"
    confidence = "degraded" if has_cache_errors else "fresh"
    return SystemStatusResponse(
        status=status,
        generated_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        cache=cache,
        jobs=jobs,
        confidence=confidence,
    )
```

Add helper near the other private helpers:

```python
def _system_jobs() -> list[dict[str, object]]:
    auction_sampler = getattr(app.state, "auction_sampler", None)
    sector_sampler = getattr(app.state, "sector_workbench_sampler", None)
    sentiment_monitor = getattr(app.state, "sentiment_monitor", None)
    gsgf_service = getattr(app.state, "gsgf_auto_review_service", None)
    return [
        {
            "name": "auction_sampler",
            "running": bool(auction_sampler and getattr(auction_sampler, "_thread", None) and auction_sampler._thread.is_alive()),
            "enabled": not getattr(app.state, "auction_sampler_disabled", False),
            "detail": "竞价时段采样器",
        },
        {
            "name": "sector_workbench_sampler",
            "running": bool(sector_sampler and getattr(sector_sampler, "running", False)),
            "enabled": not getattr(app.state, "sector_workbench_sampler_disabled", False),
            "detail": "板块工作台交易时段采样器",
        },
        {
            "name": "sentiment_monitor",
            "running": bool(sentiment_monitor and sentiment_monitor.status().running),
            "enabled": load_runtime_settings(_runtime_config_path()).sentiment_monitor.enabled,
            "detail": "短线情绪监控",
        },
        {
            "name": "gsgf_auto_review",
            "running": bool(gsgf_service and gsgf_service.status().running),
            "enabled": load_runtime_settings(_runtime_config_path()).gsgf_auto_review.daily_review_enabled,
            "detail": "GSGF 自动复盘",
        },
    ]
```

- [ ] **Step 5: Run API tests**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
uv run pytest tests/test_short_term_cache.py tests/test_cache_registry.py tests/test_system_status.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/api/app/models.py apps/api/app/main.py apps/api/tests/test_system_status.py
git commit -m "Expose system cache status APIs"
```

---

### Task 4: Add Frontend System Status API and Helpers

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Create: `apps/web/lib/systemStatus.ts`
- Create: `apps/web/lib/systemStatus.test.ts`

- [ ] **Step 1: Add helper tests**

Create `apps/web/lib/systemStatus.test.ts`:

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import { cacheFreshnessLabel, systemStatusTone } from "./systemStatus";
import type { SystemCacheItem, SystemStatusResponse } from "./types";

function cache(overrides: Partial<SystemCacheItem> = {}): SystemCacheItem {
  return {
    name: "market_overview",
    group: "home",
    ttl_seconds: 45,
    size: 1,
    fresh_count: 1,
    refreshing_count: 0,
    hits: 3,
    misses: 1,
    stale_hits: 0,
    refresh_count: 1,
    refresh_error_count: 0,
    last_refresh_started_at: null,
    last_refresh_finished_at: null,
    last_error: null,
    oldest_expires_in_seconds: 12.3,
    ...overrides,
  };
}

test("cacheFreshnessLabel formats fresh cache", () => {
  assert.equal(cacheFreshnessLabel(cache()), "12秒后过期");
});

test("cacheFreshnessLabel formats stale cache", () => {
  assert.equal(cacheFreshnessLabel(cache({ fresh_count: 0, oldest_expires_in_seconds: -20 })), "已过期20秒");
});

test("systemStatusTone maps degraded systems to warning", () => {
  const status: SystemStatusResponse = {
    status: "degraded",
    generated_at: "2026-07-05T10:00:00+08:00",
    confidence: "degraded",
    cache: { total: 1, items: [cache({ refresh_error_count: 1, last_error: "timeout" })] },
    jobs: [],
  };
  assert.equal(systemStatusTone(status), "warning");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
npm test -- lib/systemStatus.test.ts
```

Expected: fails because `systemStatus.ts` and system types do not exist.

- [ ] **Step 3: Add frontend types**

Append to `apps/web/lib/types.ts`:

```typescript
export type SystemConfidence = "fresh" | "stale" | "partial" | "degraded" | "unavailable";

export type SystemCacheItem = {
  name: string;
  group: string;
  ttl_seconds: number;
  size: number;
  fresh_count: number;
  refreshing_count: number;
  hits: number;
  misses: number;
  stale_hits: number;
  refresh_count: number;
  refresh_error_count: number;
  last_refresh_started_at: number | null;
  last_refresh_finished_at: number | null;
  last_error: string | null;
  oldest_expires_in_seconds: number | null;
};

export type SystemCacheSummary = {
  total: number;
  items: SystemCacheItem[];
};

export type SystemJobStatus = {
  name: string;
  running: boolean;
  enabled: boolean;
  detail: string;
};

export type SystemStatusResponse = {
  status: "ok" | "degraded";
  generated_at: string;
  cache: SystemCacheSummary;
  jobs: SystemJobStatus[];
  confidence: SystemConfidence;
};

export type SystemCacheClearResponse = {
  cleared: string[];
};
```

- [ ] **Step 4: Add frontend API functions**

In `apps/web/lib/api.ts`, add imports:

```typescript
  SystemCacheClearResponse,
  SystemCacheSummary,
  SystemStatusResponse,
```

Add functions near other system/config APIs:

```typescript
export async function getSystemStatus(): Promise<SystemStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/system/status`);
  if (!response.ok) {
    throw new Error(`读取系统状态失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<SystemStatusResponse>;
}

export async function getSystemCache(): Promise<SystemCacheSummary> {
  const response = await fetch(`${API_BASE_URL}/api/system/cache`);
  if (!response.ok) {
    throw new Error(`读取缓存状态失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<SystemCacheSummary>;
}

export async function clearSystemCache(group?: string): Promise<SystemCacheClearResponse> {
  const params = new URLSearchParams();
  if (group) {
    params.set("group", group);
  }
  const suffix = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/system/cache/clear${suffix ? `?${suffix}` : ""}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`清理缓存失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<SystemCacheClearResponse>;
}
```

- [ ] **Step 5: Add pure helper**

Create `apps/web/lib/systemStatus.ts`:

```typescript
import type { SystemCacheItem, SystemStatusResponse } from "./types";

export function cacheFreshnessLabel(item: SystemCacheItem): string {
  const seconds = item.oldest_expires_in_seconds;
  if (seconds === null) {
    return item.size > 0 ? "缓存状态未知" : "暂无缓存";
  }
  if (seconds >= 0) {
    return `${Math.round(seconds)}秒后过期`;
  }
  return `已过期${Math.abs(Math.round(seconds))}秒`;
}

export function systemStatusTone(status: SystemStatusResponse): "success" | "warning" {
  if (status.status === "degraded" || status.confidence === "degraded") {
    return "warning";
  }
  return "success";
}
```

- [ ] **Step 6: Run frontend helper tests**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
npm test -- lib/systemStatus.test.ts
```

Expected: `systemStatus.test.ts` passes.

- [ ] **Step 7: Commit**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/web/lib/types.ts apps/web/lib/api.ts apps/web/lib/systemStatus.ts apps/web/lib/systemStatus.test.ts
git commit -m "Add frontend system status clients"
```

---

### Task 5: Show System Status in Settings

**Files:**
- Create: `apps/web/components/system/SystemStatusPanel.tsx`
- Modify: `apps/web/app/settings/SettingsWorkspace.tsx`

- [ ] **Step 1: Create system status panel**

Create `apps/web/components/system/SystemStatusPanel.tsx`:

```tsx
"use client";

import { Alert, Button, Card, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { cacheFreshnessLabel, systemStatusTone } from "../../lib/systemStatus";
import type { SystemCacheItem, SystemStatusResponse } from "../../lib/types";

type Props = {
  loading: boolean;
  status: SystemStatusResponse | null;
  error: string | null;
  onRefresh: () => void;
};

const columns: ColumnsType<SystemCacheItem> = [
  { title: "缓存", dataIndex: "name", key: "name" },
  { title: "分组", dataIndex: "group", key: "group" },
  {
    title: "状态",
    key: "freshness",
    render: (_, item) => (
      <Tag color={item.refresh_error_count > 0 ? "red" : item.fresh_count > 0 ? "green" : "orange"}>
        {cacheFreshnessLabel(item)}
      </Tag>
    ),
  },
  { title: "命中", dataIndex: "hits", key: "hits", align: "right" },
  { title: "Miss", dataIndex: "misses", key: "misses", align: "right" },
  { title: "错误", dataIndex: "last_error", key: "last_error", render: (value) => value || "--" },
];

export function SystemStatusPanel({ loading, status, error, onRefresh }: Props) {
  const tone = status ? systemStatusTone(status) : "warning";
  return (
    <Card
      className="workbench-panel"
      title="系统运行状态"
      extra={
        <Button loading={loading} onClick={onRefresh} size="small">
          刷新状态
        </Button>
      }
    >
      {error && <Alert className="mb-3" showIcon type="error" message={error} />}
      {status ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Tag color={tone === "success" ? "green" : "orange"}>
              {status.status === "ok" ? "运行正常" : "存在降级"}
            </Tag>
            <Typography.Text className="workbench-muted text-xs">
              生成时间：{status.generated_at}
            </Typography.Text>
          </div>
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            {status.jobs.map((job) => (
              <div className="rounded-md border border-[#ddd8d0] bg-white px-3 py-2" key={job.name}>
                <div className="text-sm font-bold text-[#11100e]">{job.name}</div>
                <div className="mt-1 text-xs text-[#7b756d]">{job.detail}</div>
                <Tag className="mt-2" color={job.running ? "green" : job.enabled ? "orange" : "default"}>
                  {job.running ? "运行中" : job.enabled ? "等待窗口" : "未启用"}
                </Tag>
              </div>
            ))}
          </div>
          <Table
            columns={columns}
            dataSource={status.cache.items}
            loading={loading}
            pagination={false}
            rowKey="name"
            size="small"
          />
        </div>
      ) : (
        <Typography.Text className="workbench-muted">暂无系统状态，请点击刷新。</Typography.Text>
      )}
    </Card>
  );
}
```

- [ ] **Step 2: Wire panel into settings page**

In `apps/web/app/settings/SettingsWorkspace.tsx`, update imports:

```typescript
import { checkRuntimeSettingsHealth, getRuntimeSettings, getSystemStatus, saveRuntimeSettings } from "../../lib/api";
import { SystemStatusPanel } from "../../components/system/SystemStatusPanel";
import type {
  GsgfAutoReviewConfig,
  RuntimeSettingsConfig,
  RuntimeSettingsHealthProbe,
  SystemStatusResponse,
} from "../../lib/types";
```

Add state:

```typescript
  const [systemStatus, setSystemStatus] = useState<SystemStatusResponse | null>(null);
  const [systemStatusLoading, setSystemStatusLoading] = useState(false);
  const [systemStatusError, setSystemStatusError] = useState<string | null>(null);
```

Update the first effect:

```typescript
  useEffect(() => {
    void loadSettings();
    void loadSystemStatus();
  }, []);
```

Add function:

```typescript
  async function loadSystemStatus() {
    setSystemStatusLoading(true);
    setSystemStatusError(null);
    try {
      setSystemStatus(await getSystemStatus());
    } catch (err) {
      setSystemStatusError(err instanceof Error ? err.message : "读取系统状态失败");
    } finally {
      setSystemStatusLoading(false);
    }
  }
```

Render the panel immediately after the settings header card:

```tsx
<SystemStatusPanel
  error={systemStatusError}
  loading={systemStatusLoading}
  onRefresh={loadSystemStatus}
  status={systemStatus}
/>
```

- [ ] **Step 3: Run frontend checks**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
npm test
```

Expected: TypeScript and all frontend tests pass.

- [ ] **Step 4: Commit**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/web/components/system/SystemStatusPanel.tsx apps/web/app/settings/SettingsWorkspace.tsx
git commit -m "Show system status in settings"
```

---

### Task 6: Full Verification

**Files:**
- No planned code changes.

- [ ] **Step 1: Run backend tests**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
uv run pytest -q
```

Expected: all backend tests pass.

- [ ] **Step 2: Run backend lint**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
uv run ruff check app tests
```

Expected: no ruff violations.

- [ ] **Step 3: Run frontend tests**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
npm test
```

Expected: TypeScript and node tests pass.

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
npm run build
```

Expected: Next.js build succeeds.

- [ ] **Step 5: Smoke test system APIs**

Run with the local backend running:

```bash
curl -s http://127.0.0.1:8010/api/system/status | python -m json.tool | head -80
curl -s http://127.0.0.1:8010/api/system/cache | python -m json.tool | head -80
```

Expected: both commands return JSON with cache items, job status, and no 500.

- [ ] **Step 6: Confirm no verification-only changes remain**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener
git status --short
```

Expected: no output. If this command shows files, return to the task that introduced the failing behavior, update that task's implementation, rerun its tests, and amend the relevant task commit with `git commit --amend --no-edit`.

---

## Self-Review

- Spec coverage: this plan covers phase one only: cache registry, `TtlCache` hardening, system status API, frontend API/types, and settings visibility.
- Intentional gaps: homepage redesign, full settings-console redesign, router split, market snapshot service, and Unraid smoke automation are later phases.
- Placeholder scan: no unfinished marker words or vague implementation instructions are used.
- Type consistency: backend models use `SystemCacheSummary`, `SystemStatusResponse`, and `SystemCacheClearResponse`; frontend mirrors them as `SystemCacheSummary`, `SystemStatusResponse`, and `SystemCacheClearResponse`.
