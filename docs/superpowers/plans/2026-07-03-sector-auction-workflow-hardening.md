# Sector Auction Workflow Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the sector, auction, home, and source-status workflows more traceable and usable without replacing the current screener architecture.

**Architecture:** Keep TickFlow as the main market-data source and keep short-term theme references as calibration/reference data. Add thin API and UI layers for theme linkage, sampler/cache status, and source credibility instead of introducing a new data pipeline.

**Tech Stack:** FastAPI, Pydantic, pytest, Next.js, TypeScript, Ant Design, node:test.

---

### Task 1: Theme Reference And Auction Linkage

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/services/auction.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_auction.py`
- Modify: `apps/api/tests/test_api.py`
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/app/auction/AuctionWorkspace.tsx`
- Modify: `apps/web/lib/auctionSort.test.ts`

- [ ] **Step 1: Add failing backend tests**

Verify auction rows can carry theme metadata and mark resonance when a candidate belongs to a Top theme and is also in the leading auction group.

- [ ] **Step 2: Implement backend theme metadata**

Add `themes`, `hot_theme_rank`, `hot_theme_score`, `theme_auction_rank`, and `theme_resonance` to auction snapshot items.

- [ ] **Step 3: Wire theme reference into auction snapshot API**

Fetch Top theme references through the existing plate reference provider and pass them into auction snapshot building.

- [ ] **Step 4: Add frontend types and table column**

Show a compact "热门题材" column in the auction table with a visible resonance tag.

- [ ] **Step 5: Verify**

Run:
```bash
cd apps/api && uv run pytest tests/test_auction.py tests/test_api.py -q
cd apps/web && npm test -- --test-name-pattern='standalone strong stock workbench|auction'
```

### Task 2: Sector Curve Persistence Visibility

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_sector_workbench_sampler.py`
- Modify: `apps/api/tests/test_api.py`
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/sectors/SectorThemeWorkbench.tsx`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Add failing API test**

Verify a sector workbench status endpoint returns sampler state, cached point count, latest sample time, and source-status summary.

- [ ] **Step 2: Implement lightweight status endpoint**

Expose cached sampling metadata without triggering heavy TickFlow minute-line calls from page load.

- [ ] **Step 3: Render sampler status in sectors page**

Show "实时采样/缓存/最近更新时间/可信度" in the sectors page header area.

- [ ] **Step 4: Verify**

Run:
```bash
cd apps/api && uv run pytest tests/test_sector_workbench_sampler.py tests/test_api.py -q
cd apps/web && npm test -- --test-name-pattern='standalone strong stock workbench'
```

### Task 3: Home Workflow Consolidation

**Files:**
- Modify: `apps/web/components/ScreenerWorkbench.tsx`
- Modify: `apps/web/components/screener/screenerUtils.ts`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Add static assertions**

Verify the home screen exposes the core workflow entrances: 今日选股、竞价雷达、题材强度、自选观察池、可信度.

- [ ] **Step 2: Add compact workflow navigation**

Add a small Ant/Tailwind-compatible workflow strip above market overview. It should not replace existing screening controls.

- [ ] **Step 3: Verify**

Run:
```bash
cd apps/web && npm test -- --test-name-pattern='standalone strong stock workbench'
```

### Task 4: Source Credibility Display

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/models.py`
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/app/sectors/SectorThemeWorkbench.tsx`
- Modify: `apps/web/app/auction/AuctionWorkspace.tsx`

- [ ] **Step 1: Add source-status fields only where missing**

Reuse existing `source_status` records and avoid inventing a new status model unless required.

- [ ] **Step 2: Show compact trust labels**

Each affected page should show current data mode: real-time, cache, fallback, stale, error, or estimated.

- [ ] **Step 3: Verify**

Run:
```bash
cd apps/api && uv run pytest tests/test_api.py -q
cd apps/web && npm test -- --test-name-pattern='standalone strong stock workbench'
```

### Task 5: Full Regression

**Files:**
- No new files unless test failures identify a direct gap.

- [ ] **Step 1: Run backend verification**

```bash
cd apps/api && uv run ruff check app tests
cd apps/api && uv run pytest tests/test_auction.py tests/test_api.py tests/test_plate_rotation_reference.py tests/test_sector_workbench.py tests/test_sector_workbench_sampler.py -q
```

- [ ] **Step 2: Run frontend verification**

```bash
cd apps/web && npm test -- --test-name-pattern='standalone strong stock workbench|auction'
cd apps/web && npm run typecheck
```

- [ ] **Step 3: Browser smoke test**

Open `/`, `/auction`, and `/sectors` locally and verify there are no Next.js error toasts and the new status labels are visible.
