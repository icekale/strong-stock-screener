# Auction Top3 Live Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight TickFlow-backed live confirmation layer for auction Top3 model candidates without changing model scoring or training features.

**Architecture:** The backend reads the cached Top3 model result, merges it with the latest auction snapshot by symbol, and returns a per-candidate confirmation state. The frontend fetches this confirmation after loading Top3 and renders compact `可买 / 观察 / 放弃` signals inside the existing model Top3 panel.

**Tech Stack:** FastAPI, Pydantic, existing `AuctionSnapshotStore`, existing `AuctionModelResultStore`, Next.js/React, Ant Design, Node test runner, pytest.

---

## File Structure

- Modify `apps/api/app/models.py`
  - Add confirmation literals and response models.
- Create `apps/api/app/services/auction_top3_live_confirmation.py`
  - Own the confirmation rules and persistence store.
- Modify `apps/api/app/main.py`
  - Add `GET /api/auction/model/top3/live-confirmation`.
  - Wire cached Top3 + latest auction snapshot into the service.
- Modify `apps/api/tests/test_auction_model.py`
  - Cover API behavior and cache-only constraints.
- Create `apps/api/tests/test_auction_top3_live_confirmation.py`
  - Cover rule decisions.
- Modify `apps/web/lib/types.ts`
  - Add response and item types.
- Modify `apps/web/lib/api.ts`
  - Add `getAuctionModelLiveConfirmation`.
- Modify `apps/web/lib/auctionModel.ts` and `apps/web/lib/auctionModel.test.ts`
  - Add label/color/status helpers.
- Modify `apps/web/app/auction/AuctionWorkspace.tsx`
  - Fetch and render live confirmation inside the existing Top3 cards.

---

### Task 1: Backend Confirmation Rules

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/services/auction_top3_live_confirmation.py`
- Test: `apps/api/tests/test_auction_top3_live_confirmation.py`

- [ ] **Step 1: Write failing tests**

Create `apps/api/tests/test_auction_top3_live_confirmation.py` with tests for buyable, watch, reject, and missing realtime cases:

```python
from app.models import AuctionModelPredictionItem, AuctionSnapshotItem
from app.services.auction_top3_live_confirmation import confirm_auction_top3_item


def model_item(**updates):
    data = {
        "symbol": "300001.SZ",
        "name": "模型一号",
        "prob_3pct": 0.91,
        "bucket": "selected",
        "rank": 1,
        "risk_flags": [],
    }
    data.update(updates)
    return AuctionModelPredictionItem(**data)


def snapshot_item(**updates):
    data = {
        "symbol": "300001.SZ",
        "name": "模型一号",
        "open_gap_pct": 4.5,
        "current_pct_change": 5.2,
        "turnover_cny": 160_000_000,
        "turnover_rate": 3.5,
        "quote_time": "2026-07-06T09:25:00+08:00",
    }
    data.update(updates)
    return AuctionSnapshotItem(**data)


def test_live_confirmation_marks_selected_candidate_buyable() -> None:
    result = confirm_auction_top3_item(model_item(), snapshot_item())

    assert result.confirmation == "buyable"
    assert "模型入选Top3" in result.reasons
    assert "实时量能通过" in result.reasons


def test_live_confirmation_rejects_model_liquidity_risk() -> None:
    result = confirm_auction_top3_item(
        model_item(risk_flags=["近3日日均成交额低于1亿"]),
        snapshot_item(),
    )

    assert result.confirmation == "reject"
    assert "模型流动性风险" in result.risk_flags


def test_live_confirmation_rejects_overheated_gap_without_resonance() -> None:
    result = confirm_auction_top3_item(
        model_item(),
        snapshot_item(open_gap_pct=8.1, theme_resonance=False),
    )

    assert result.confirmation == "reject"
    assert "高开过热" in result.risk_flags


def test_live_confirmation_watches_when_realtime_missing() -> None:
    result = confirm_auction_top3_item(model_item(), None)

    assert result.confirmation == "watch"
    assert "realtime_missing" in result.data_quality
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd apps/api && uv run pytest tests/test_auction_top3_live_confirmation.py -q
```

Expected: import failure because `auction_top3_live_confirmation.py` does not exist.

- [ ] **Step 3: Add Pydantic models**

In `apps/api/app/models.py`, after `AuctionModelTop3Response`, add:

```python
AuctionTop3LiveConfirmation = Literal["buyable", "watch", "reject"]


class AuctionTop3RealtimeSnapshot(BaseModel):
    last_price: float | None = None
    current_pct_change: float | None = None
    open_gap_pct: float | None = None
    turnover_cny: float | None = None
    turnover_rate: float | None = None
    quote_time: str | None = None


class AuctionTop3LiveConfirmationItem(BaseModel):
    symbol: str
    name: str = ""
    model_rank: int | None = None
    model_bucket: AuctionModelBucket = "watch"
    prob_3pct: float
    confirmation: AuctionTop3LiveConfirmation
    realtime: AuctionTop3RealtimeSnapshot | None = None
    reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    data_quality: list[str] = Field(default_factory=list)


class AuctionTop3LiveConfirmationResponse(BaseModel):
    trade_date: str
    model_run_id: str | None = None
    cache_status: AuctionModelCacheStatus = "cached"
    items: list[AuctionTop3LiveConfirmationItem] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
```

- [ ] **Step 4: Add confirmation service**

Create `apps/api/app/services/auction_top3_live_confirmation.py`:

```python
from __future__ import annotations

from pathlib import Path

from app.models import (
    AuctionModelPredictionItem,
    AuctionModelTop3Response,
    AuctionSnapshotItem,
    AuctionSnapshotResponse,
    AuctionTop3LiveConfirmationItem,
    AuctionTop3LiveConfirmationResponse,
    AuctionTop3RealtimeSnapshot,
    StrongStockSourceStatus,
)

OVERHEAT_GAP_PCT = 7.0
WEAKENING_GAP_PCT = 3.0
MIN_TURNOVER_CNY = 100_000_000
MIN_TURNOVER_RATE = 3.0
MODEL_LIQUIDITY_RISK_KEYWORDS = ("流通市值低于20亿", "近3日日均成交额低于1亿")


def confirm_auction_top3_item(
    model_item: AuctionModelPredictionItem,
    realtime_item: AuctionSnapshotItem | None,
) -> AuctionTop3LiveConfirmationItem:
    reasons: list[str] = []
    risk_flags: list[str] = []
    data_quality: list[str] = []
    confirmation = "watch"
    realtime = _realtime_snapshot(realtime_item) if realtime_item is not None else None

    if model_item.bucket == "selected":
        reasons.append("模型入选Top3")
    else:
        reasons.append("模型未入选Top3执行桶")

    if any(keyword in flag for flag in model_item.risk_flags for keyword in MODEL_LIQUIDITY_RISK_KEYWORDS):
        risk_flags.append("模型流动性风险")
        confirmation = "reject"

    if realtime_item is None:
        data_quality.append("realtime_missing")
        reasons.append("实时竞价数据缺失")
    else:
        open_gap = realtime_item.open_gap_pct
        current_pct = realtime_item.current_pct_change
        turnover_cny = realtime_item.turnover_cny or 0
        turnover_rate = realtime_item.turnover_rate or 0
        has_volume = turnover_cny >= MIN_TURNOVER_CNY or turnover_rate >= MIN_TURNOVER_RATE

        if has_volume:
            reasons.append("实时量能通过")
        else:
            reasons.append("实时量能不足")

        if open_gap is not None and open_gap >= OVERHEAT_GAP_PCT and not realtime_item.theme_resonance:
            risk_flags.append("高开过热")
            confirmation = "reject"
        if current_pct is not None and current_pct < 0:
            risk_flags.append("实时涨幅转负")
            confirmation = "reject"
        if open_gap is not None and current_pct is not None and current_pct <= open_gap - WEAKENING_GAP_PCT:
            risk_flags.append("开盘后明显走弱")
            confirmation = "reject"
        if realtime_item.theme_resonance:
            reasons.append("题材共振")

        if confirmation != "reject" and model_item.bucket == "selected" and has_volume and current_pct is not None and current_pct >= 0:
            confirmation = "buyable"

    return AuctionTop3LiveConfirmationItem(
        symbol=model_item.symbol,
        name=model_item.name,
        model_rank=model_item.rank,
        model_bucket=model_item.bucket,
        prob_3pct=model_item.prob_3pct,
        confirmation=confirmation,
        realtime=realtime,
        reasons=reasons,
        risk_flags=[*model_item.risk_flags, *risk_flags],
        data_quality=[*model_item.data_quality, *data_quality],
    )


def build_auction_top3_live_confirmation(
    model_run: AuctionModelTop3Response,
    snapshot: AuctionSnapshotResponse | None,
) -> AuctionTop3LiveConfirmationResponse:
    realtime_by_symbol = {item.symbol: item for item in snapshot.items} if snapshot is not None else {}
    items = [
        confirm_auction_top3_item(item, realtime_by_symbol.get(item.symbol))
        for item in model_run.items
    ]
    source_status = [
        StrongStockSourceStatus(
            source="竞价Top3实盘确认",
            status="success",
            detail=f"读取Top3缓存 {len(model_run.items)} 只，匹配实时竞价 {sum(1 for item in items if item.realtime is not None)} 只",
        )
    ]
    if snapshot is not None:
        source_status.extend(snapshot.source_status)
    return AuctionTop3LiveConfirmationResponse(
        trade_date=model_run.trade_date,
        model_run_id=model_run.run_id,
        cache_status=model_run.cache_status,
        items=items,
        source_status=source_status,
    )


def _realtime_snapshot(item: AuctionSnapshotItem) -> AuctionTop3RealtimeSnapshot:
    return AuctionTop3RealtimeSnapshot(
        last_price=item.last_price,
        current_pct_change=item.current_pct_change,
        open_gap_pct=item.open_gap_pct,
        turnover_cny=item.turnover_cny,
        turnover_rate=item.turnover_rate,
        quote_time=item.quote_time,
    )


class AuctionTop3LiveConfirmationStore:
    def __init__(self, data_dir: Path) -> None:
        self.root_dir = data_dir / "auction_top3_live_confirmations"

    def save(self, result: AuctionTop3LiveConfirmationResponse) -> AuctionTop3LiveConfirmationResponse:
        path = self.root_dir / "confirmations" / f"{result.trade_date}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
cd apps/api && uv run pytest tests/test_auction_top3_live_confirmation.py -q
```

Expected: all tests pass.

---

### Task 2: Backend API Wiring

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_auction_model.py`

- [ ] **Step 1: Write failing API tests**

Append to `apps/api/tests/test_auction_model.py`:

```python
def test_auction_model_live_confirmation_uses_cached_top3_without_generating(tmp_path: Path) -> None:
    service = CountingFakeAuctionModelService()
    store = AuctionModelResultStore(tmp_path)
    store.save_top3(FakeAuctionModelService().predict_top3("2026-07-06"))
    app.state.auction_model_service = service
    app.state.auction_model_result_store = store
    app.state.runs_dir = tmp_path
    client = TestClient(app)
    try:
        response = client.get("/api/auction/model/top3/live-confirmation?trade_date=2026-07-06")
    finally:
        delattr(app.state, "auction_model_service")
        delattr(app.state, "auction_model_result_store")
        delattr(app.state, "runs_dir")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-07-06"
    assert payload["items"][0]["symbol"] == "300001.SZ"
    assert payload["items"][0]["confirmation"] == "watch"
    assert service.call_count == 0


def test_auction_model_live_confirmation_returns_404_without_top3_cache(tmp_path: Path) -> None:
    app.state.auction_model_result_store = AuctionModelResultStore(tmp_path)
    client = TestClient(app)
    try:
        response = client.get("/api/auction/model/top3/live-confirmation?trade_date=2026-07-06")
    finally:
        delattr(app.state, "auction_model_result_store")

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd apps/api && uv run pytest tests/test_auction_model.py::test_auction_model_live_confirmation_uses_cached_top3_without_generating tests/test_auction_model.py::test_auction_model_live_confirmation_returns_404_without_top3_cache -q
```

Expected: 404 or route missing for the first test.

- [ ] **Step 3: Wire API in `main.py`**

Import the service:

```python
from app.services.auction_top3_live_confirmation import (
    AuctionTop3LiveConfirmationStore,
    build_auction_top3_live_confirmation,
)
```

Add route after `/api/auction/model/top3`:

```python
@app.get("/api/auction/model/top3/live-confirmation")
def get_auction_model_top3_live_confirmation(trade_date: str) -> dict[str, object]:
    try:
        datetime.strptime(trade_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="trade_date must use YYYY-MM-DD") from exc
    model_run = _auction_model_result_store().load_top3(trade_date)
    if model_run is None:
        raise HTTPException(status_code=404, detail="暂无缓存的竞价模型Top3结果")
    snapshot = _auction_snapshot_store().latest(max_age_seconds=24 * 3600, limit=100)
    if snapshot.snapshot_status == "missing":
        snapshot = None
    result = build_auction_top3_live_confirmation(model_run, snapshot)
    _auction_top3_live_confirmation_store().save(result)
    return result.model_dump(mode="json")
```

Add store helper near other stores:

```python
def _auction_top3_live_confirmation_store() -> AuctionTop3LiveConfirmationStore:
    injected = getattr(app.state, "auction_top3_live_confirmation_store", None)
    if injected is not None:
        return injected
    data_dir = Path(getattr(app.state, "runs_dir", get_settings().data_dir))
    return AuctionTop3LiveConfirmationStore(data_dir)
```

- [ ] **Step 4: Run API tests**

Run:

```bash
cd apps/api && uv run pytest tests/test_auction_model.py tests/test_auction_top3_live_confirmation.py -q
```

Expected: all tests pass.

---

### Task 3: Frontend API and Helpers

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/lib/auctionModel.ts`
- Modify: `apps/web/lib/auctionModel.test.ts`

- [ ] **Step 1: Write failing frontend helper tests**

Append to `apps/web/lib/auctionModel.test.ts`:

```typescript
test("auction model live confirmation labels are trading-workbench copy", () => {
  assert.equal(auctionModelLiveConfirmationLabel("buyable"), "可买");
  assert.equal(auctionModelLiveConfirmationLabel("watch"), "观察");
  assert.equal(auctionModelLiveConfirmationLabel("reject"), "放弃");
});

test("auction model live confirmation colors separate action states", () => {
  assert.equal(auctionModelLiveConfirmationColor("buyable"), "green");
  assert.equal(auctionModelLiveConfirmationColor("watch"), "gold");
  assert.equal(auctionModelLiveConfirmationColor("reject"), "red");
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd apps/web && node --experimental-strip-types --test lib/auctionModel.test.ts
```

Expected: failure because helper functions are not exported.

- [ ] **Step 3: Add types**

In `apps/web/lib/types.ts`, near `AuctionModelTop3Response`, add:

```typescript
export type AuctionTop3LiveConfirmation = "buyable" | "watch" | "reject";

export type AuctionTop3RealtimeSnapshot = {
  last_price: number | null;
  current_pct_change: number | null;
  open_gap_pct: number | null;
  turnover_cny: number | null;
  turnover_rate: number | null;
  quote_time: string | null;
};

export type AuctionTop3LiveConfirmationItem = {
  symbol: string;
  name: string;
  model_rank: number | null;
  model_bucket: AuctionModelPredictionItem["bucket"];
  prob_3pct: number;
  confirmation: AuctionTop3LiveConfirmation;
  realtime: AuctionTop3RealtimeSnapshot | null;
  reasons: string[];
  risk_flags: string[];
  data_quality: string[];
};

export type AuctionTop3LiveConfirmationResponse = {
  trade_date: string;
  model_run_id: string | null;
  cache_status: AuctionModelTop3Response["cache_status"];
  items: AuctionTop3LiveConfirmationItem[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};
```

- [ ] **Step 4: Add API function**

In `apps/web/lib/api.ts`, import `AuctionTop3LiveConfirmationResponse` and add:

```typescript
export async function getAuctionModelLiveConfirmation(tradeDate: string): Promise<AuctionTop3LiveConfirmationResponse> {
  const params = new URLSearchParams({ trade_date: tradeDate });
  const response = await fetch(`${API_BASE_URL}/api/auction/model/top3/live-confirmation?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`读取竞价模型实盘确认失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<AuctionTop3LiveConfirmationResponse>;
}
```

- [ ] **Step 5: Add helper functions**

In `apps/web/lib/auctionModel.ts`, add:

```typescript
import type { AuctionTop3LiveConfirmation } from "./types";

export function auctionModelLiveConfirmationLabel(value: AuctionTop3LiveConfirmation): string {
  if (value === "buyable") return "可买";
  if (value === "reject") return "放弃";
  return "观察";
}

export function auctionModelLiveConfirmationColor(value: AuctionTop3LiveConfirmation): string {
  if (value === "buyable") return "green";
  if (value === "reject") return "red";
  return "gold";
}
```

- [ ] **Step 6: Run frontend helper tests**

Run:

```bash
cd apps/web && node --experimental-strip-types --test lib/auctionModel.test.ts
```

Expected: tests pass.

---

### Task 4: Frontend Top3 Panel Integration

**Files:**
- Modify: `apps/web/app/auction/AuctionWorkspace.tsx`
- Modify: `apps/web/lib/auctionModel.test.ts`

- [ ] **Step 1: Add source checks test**

Append to `apps/web/lib/auctionModel.test.ts`:

```typescript
import { readFileSync } from "node:fs";

test("auction workspace fetches and renders live confirmation", () => {
  const source = readFileSync(new URL("../app/auction/AuctionWorkspace.tsx", import.meta.url), "utf8");
  assert.match(source, /getAuctionModelLiveConfirmation/);
  assert.match(source, /liveConfirmationBySymbol/);
  assert.match(source, /实盘确认/);
});
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd apps/web && node --experimental-strip-types --test lib/auctionModel.test.ts
```

Expected: failure because workspace does not fetch/render confirmation.

- [ ] **Step 3: Wire state and fetch**

In `AuctionWorkspace.tsx`:

- Import `getAuctionModelLiveConfirmation`.
- Import confirmation helpers.
- Add state:

```typescript
const [auctionModelLiveConfirmation, setAuctionModelLiveConfirmation] = useState<AuctionTop3LiveConfirmationResponse | null>(null);
const [auctionModelLiveError, setAuctionModelLiveError] = useState<string | null>(null);
```

- Add loader:

```typescript
const loadAuctionModelLiveConfirmation = useCallback(async (date: string) => {
  try {
    const confirmation = await getAuctionModelLiveConfirmation(date);
    setAuctionModelLiveConfirmation(confirmation);
    setAuctionModelLiveError(null);
  } catch (error) {
    setAuctionModelLiveConfirmation(null);
    setAuctionModelLiveError(error instanceof Error ? error.message : "读取实盘确认失败");
  }
}, []);
```

- After successful cached load or refresh load of Top3, call:

```typescript
void loadAuctionModelLiveConfirmation(targetDate);
```

- Build map:

```typescript
const liveConfirmationBySymbol = useMemo(() => {
  return new Map((auctionModelLiveConfirmation?.items ?? []).map((item) => [item.symbol, item]));
}, [auctionModelLiveConfirmation]);
```

- Pass `liveConfirmationBySymbol` and `auctionModelLiveError` to `AuctionModelPanel`.

- [ ] **Step 4: Render confirmation in cards**

Inside each Top3 card in `AuctionModelPanel`, find the item confirmation:

```typescript
const liveConfirmation = liveConfirmationBySymbol.get(item.symbol);
```

Render:

```tsx
{liveConfirmation ? (
  <div className="mt-2 rounded-md border border-white bg-white px-2 py-1.5 text-xs">
    <div className="flex flex-wrap items-center gap-1">
      <span className="font-black text-[#11100e]">实盘确认</span>
      <Tag className="m-0" color={auctionModelLiveConfirmationColor(liveConfirmation.confirmation)}>
        {auctionModelLiveConfirmationLabel(liveConfirmation.confirmation)}
      </Tag>
      <span className="text-[#7b756d]">涨幅 {formatSignedRatioPct(decimalPercent(liveConfirmation.realtime?.current_pct_change))}</span>
      <span className="text-[#7b756d]">开盘 {formatSignedRatioPct(decimalPercent(liveConfirmation.realtime?.open_gap_pct))}</span>
    </div>
    <div className="mt-1 truncate text-[#7b756d]">
      {(liveConfirmation.reasons.length ? liveConfirmation.reasons : liveConfirmation.data_quality).join(" · ") || "实时确认待更新"}
    </div>
  </div>
) : null}
```

Add helper near format helpers:

```typescript
function decimalPercent(value: number | null | undefined): number | null {
  return value == null ? null : value / 100;
}
```

Render warning above cards if `auctionModelLiveError` exists:

```tsx
{auctionModelLiveError ? <Alert className="mb-2" showIcon title={auctionModelLiveError} type="info" /> : null}
```

- [ ] **Step 5: Run frontend tests and typecheck**

Run:

```bash
cd apps/web && node --experimental-strip-types --test lib/auctionModel.test.ts
cd apps/web && ./node_modules/.bin/tsc --noEmit
```

Expected: tests and typecheck pass.

---

### Task 5: Final Verification

**Files:**
- No new files unless tests reveal a defect.

- [ ] **Step 1: Run API tests**

Run:

```bash
cd apps/api && uv run pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend tests**

Run:

```bash
cd apps/web && node --experimental-strip-types --test lib/*.test.ts
```

Expected: all tests pass.

- [ ] **Step 3: Run frontend typecheck**

Run:

```bash
cd apps/web && ./node_modules/.bin/tsc --noEmit
```

Expected: no output and exit code 0.

- [ ] **Step 4: Smoke API manually**

Run:

```bash
curl -sS -m 20 'http://127.0.0.1:8010/api/auction/model/top3/live-confirmation?trade_date=2026-07-06' | python3 -m json.tool | sed -n '1,120p'
```

Expected: JSON with `items` and each item has `confirmation`.

- [ ] **Step 5: Commit implementation**

Run:

```bash
git add apps/api/app/models.py apps/api/app/main.py apps/api/app/services/auction_top3_live_confirmation.py apps/api/tests/test_auction_model.py apps/api/tests/test_auction_top3_live_confirmation.py apps/web/lib/types.ts apps/web/lib/api.ts apps/web/lib/auctionModel.ts apps/web/lib/auctionModel.test.ts apps/web/app/auction/AuctionWorkspace.tsx docs/superpowers/plans/2026-07-06-auction-top3-live-confirmation.md
git commit -m "Add auction Top3 live confirmation"
```

Expected: commit succeeds.
