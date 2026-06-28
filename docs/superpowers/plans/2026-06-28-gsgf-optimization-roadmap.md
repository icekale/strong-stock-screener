# GSGF Optimization Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the connected 《股是股非》 module into a measurable, intraday-aware, filterable, reviewable stock-picking subsystem inside the strong-stock screener.

**Architecture:** Keep the existing screener as the owner of screening flow. Add small backend services for calibration, intraday confirmation, trade-plan narration, and daily review records, then expose only the fields needed by the current frontend workbench. TickFlow remains scoped to this screener and no `empty` screening status is introduced.

**Tech Stack:** FastAPI, Pydantic models, pytest, Ruff, Next.js, TypeScript, Node test runner, TickFlow daily/realtime/intraday data providers.

---

### Task 1: 回测校准核心

**Files:**
- Create: `apps/api/app/services/gsgf_backtest.py`
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_gsgf_backtest.py`
- Test: `apps/api/tests/test_api.py`

- [ ] **Step 1: Write failing service tests**

```python
from app.models import KlineBar
from app.services.gsgf_backtest import summarize_gsgf_backtest


def test_summarize_gsgf_backtest_groups_future_returns_by_status() -> None:
    bars = [
        KlineBar(date=f"2026-01-{index + 1:02d}", open=10 + index, close=10 + index, high=10 + index, low=10 + index, volume=1_000_000)
        for index in range(80)
    ]

    result = summarize_gsgf_backtest({"603890.SH": bars}, windows=[1, 3], min_history=60)

    assert result.sample_count > 0
    assert any(bucket.status in {"确认买点", "候选", "低吸观察", "观察", "减仓", "回避"} for bucket in result.buckets)
    assert result.buckets[0].windows[0].window_days == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_gsgf_backtest.py -q
```

Expected: fail because `app.services.gsgf_backtest` does not exist.

- [ ] **Step 3: Implement minimal models and summarizer**

Add Pydantic models:

```python
class GsgfBacktestWindowStat(BaseModel):
    window_days: int
    sample_count: int = 0
    win_rate: float | None = None
    avg_return_pct: float | None = None
    median_return_pct: float | None = None
    avg_max_drawdown_pct: float | None = None


class GsgfBacktestBucket(BaseModel):
    status: GsgfFinalStatus
    sample_count: int = 0
    avg_score: float | None = None
    windows: list[GsgfBacktestWindowStat] = Field(default_factory=list)


class GsgfBacktestSummary(BaseModel):
    windows: list[int] = Field(default_factory=list)
    sample_count: int = 0
    buckets: list[GsgfBacktestBucket] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
```

Create `summarize_gsgf_backtest(symbol_bars, windows, min_history)` that runs `analyze_gsgf` on rolling daily K-line prefixes and records future returns.

- [ ] **Step 4: Run service tests to verify pass**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_gsgf_backtest.py -q
```

Expected: pass.

- [ ] **Step 5: Add API endpoint test and implementation**

Add `POST /api/gsgf/backtest` accepting `symbols`, `windows`, `min_history`, `count`, using `_kline_provider()` and returning `GsgfBacktestSummary`.

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_api.py::test_gsgf_backtest_returns_bucketed_forward_stats -q
```

Expected after implementation: pass.

### Task 2: 盘中确认闭环

**Files:**
- Modify: `apps/api/app/services/intraday.py`
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_intraday.py` or `apps/api/tests/test_api.py`

- [x] Add optional GSGF context to intraday snapshot request.
- [x] Classify `确认买点` as valid only when price holds above intraday MA and volume is not stalling.
- [x] Classify `低吸观察` as stronger only after an early drop recovers intraday MA.
- [x] Classify `减仓` when high-open strength fades or price fails to hold intraday MA.
- [x] Verify with TickFlow quote/minute fake providers.

### Task 3: 工作台股是股非筛选器

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/components/ScreenerWorkbench.tsx`
- Modify: `apps/web/lib/stockListFilter.ts` if extracted filtering is needed
- Test: `apps/web/lib/strongStockWorkbench.test.ts`

- [x] Add filters for `确认买点`, `低吸观察`, `放量突破确认`, `B区A点`, and “排除全局阴量压制”.
- [x] Keep existing candidate status filter unchanged; do not add `empty`.
- [x] Verify TypeScript and source wiring tests.

### Task 4: 交易计划解释层

**Files:**
- Create: `apps/api/app/services/gsgf_trade_plan.py`
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/web/components/ScreenerWorkbench.tsx`
- Test: backend service/API tests and frontend source test

- [x] Convert GSGF status, setup, confirm, and risk flags into holder/buyer/risk invalidation text.
- [x] Separate holder guidance from empty-position guidance.
- [x] Use operational wording such as “持有优于追涨”, “等分歧低吸”, “冲高不封减仓”.
- [x] Keep output research-only and avoid guaranteed-profit language.

### Task 5: 每日信号复盘表

**Files:**
- Create: `apps/api/app/services/gsgf_review.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/lib/types.ts`
- Add/Modify frontend review surface only after backend is stable
- Test: backend persistence tests and frontend source test

- [x] Persist daily GSGF signal snapshots from screen runs.
- [x] Re-check snapshots after 1/3/5/10 sessions using current K-line provider.
- [x] Store realized return, max drawdown, and whether the original signal was confirmed.
- [x] Provide summary by signal type and status.
- [x] Keep records in the screener data directory, not the daily-report app.

### Verification Gate

Run before claiming this roadmap implementation is complete:

```bash
cd apps/api
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check app tests

cd ../web
corepack pnpm test
```

Expected: all tests pass; existing FastAPI/TestClient deprecation warning is acceptable.
