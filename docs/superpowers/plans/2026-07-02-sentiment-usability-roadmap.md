# Sentiment Usability Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the sentiment page from a data dashboard into a trading decision module that answers whether to trade, which sectors matter, which watchlist stocks require attention, and how the rules improve over time.

**Architecture:** Build this as four incremental releases. Stage 1 adds a backend decision layer and a conclusion-first UI without changing existing raw sentiment APIs. Stage 2 links sentiment to the watchlist pool. Stage 3 upgrades timeline sampling and notification triggers. Stage 4 archives decisions and next-session outcomes for rule calibration.

**Tech Stack:** FastAPI + Pydantic models + JSONL stores for backend; Next.js/React/Ant Design for frontend; existing TickFlow/iFinD providers, watchlist pool, sentiment monitor, and notification channels.

---

## Release Sequence

1. **Stage 1: 情绪结论与交易许可**
   - Output: the sentiment page clearly says `市场状态 / 交易许可 / 风险等级 / 主线方向 / 原因`.
   - Success check: opening `/sentiment` shows a conclusion card before raw tables.

2. **Stage 2: 自选股联动**
   - Output: the sentiment page tells the user which watchlist stocks match strengthening sectors or risk conditions.
   - Success check: watchlist stocks are grouped into `重点盯 / 等确认 / 风险回避`.

3. **Stage 3: 情绪时间轴与通知**
   - Output: the system evaluates 09:25, 09:35, 10:00, 11:30, 14:30 states and sends actionable alerts.
   - Success check: monitor alerts explain what changed and what action is implied.

4. **Stage 4: 每日归档与规则校准**
   - Output: each day stores the decision, next-session outcome, and rule hit/miss summary.
   - Success check: a review endpoint can say which sentiment rules worked and which produced false positives.

---

### Task 1: Stage 1 Backend Decision Layer

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/services/sentiment_decision.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_sentiment_decision.py`
- Modify: `apps/api/tests/test_api.py`

- [ ] **Step 1: Add failing tests for market-state classification**

Create `apps/api/tests/test_sentiment_decision.py` with these tests:

```python
from app.models import (
    MarketEmotionMetrics,
    MarketEmotionSnapshotResponse,
    SentimentSummaryMetrics,
    SentimentSummaryResponse,
    ShortTermSentimentIndustryItem,
)
from app.services.sentiment_decision import build_sentiment_decision


def _summary(
    *,
    score: float,
    limit_up: int,
    break_board: int,
    limit_down: int,
    seal_rate: float,
    advance: int = 3000,
    decline: int = 2000,
    turnover_change_pct: float = 3,
) -> SentimentSummaryResponse:
    return SentimentSummaryResponse(
        trade_date="2026-07-02",
        metrics=SentimentSummaryMetrics(
            emotion_score=score,
            emotion_level="良好",
            limit_up_count=limit_up,
            break_board_count=break_board,
            limit_down_count=limit_down,
            advance_count=advance,
            decline_count=decline,
            seal_rate_pct=seal_rate,
            turnover_change_pct=turnover_change_pct,
        ),
        hot_industries=[
            ShortTermSentimentIndustryItem(
                name="存储芯片",
                limit_up_count=8,
                break_board_count=1,
                max_consecutive_boards=3,
                leader="德明利",
                symbols=["001309.SZ"],
                strength_score=90,
            )
        ],
    )


def _emotion(score: float, samples: list[float]) -> MarketEmotionSnapshotResponse:
    return MarketEmotionSnapshotResponse(
        trade_date="2026-07-02",
        metrics=MarketEmotionMetrics(emotion_score=score, emotion_level="良好"),
        samples=[
            {
                "trade_date": "2026-07-02",
                "sampled_at": f"2026-07-02T09:{30 + index:02d}:00+08:00",
                "emotion_score": item,
                "emotion_level": "一般",
                "limit_up_count": 10,
                "break_board_count": 2,
                "max_consecutive_boards": 2,
            }
            for index, item in enumerate(samples)
        ],
    )


def test_decision_marks_repair_as_light_trial() -> None:
    decision = build_sentiment_decision(
        summary=_summary(score=58, limit_up=55, break_board=8, limit_down=2, seal_rate=78),
        market_emotion=_emotion(58, [40, 47, 58]),
    )

    assert decision.market_state == "修复"
    assert decision.trade_permission == "轻仓试错"
    assert decision.risk_level == "中"
    assert decision.main_sectors[0].name == "存储芯片"
    assert "情绪分数回升" in decision.reasons


def test_decision_marks_retreat_as_cash_wait() -> None:
    decision = build_sentiment_decision(
        summary=_summary(
            score=22,
            limit_up=18,
            break_board=28,
            limit_down=35,
            seal_rate=39,
            advance=900,
            decline=4200,
            turnover_change_pct=-6,
        ),
        market_emotion=_emotion(22, [52, 39, 22]),
    )

    assert decision.market_state == "退潮"
    assert decision.trade_permission == "空仓等待"
    assert decision.risk_level == "高"
    assert "跌停与炸板压力高" in decision.risks


def test_decision_marks_climax_as_sell_not_chase() -> None:
    decision = build_sentiment_decision(
        summary=_summary(score=84, limit_up=130, break_board=22, limit_down=1, seal_rate=86, turnover_change_pct=12),
        market_emotion=_emotion(84, [65, 76, 84]),
    )

    assert decision.market_state == "高潮"
    assert decision.trade_permission == "只卖不追"
    assert decision.risk_level == "中"
    assert "情绪过热，避免追高" in decision.risks
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_sentiment_decision.py -q
```

Expected: fail because `app.services.sentiment_decision` and decision models do not exist.

- [ ] **Step 3: Add decision models**

In `apps/api/app/models.py`, add these literals and Pydantic models near the existing sentiment models:

```python
SentimentMarketState = Literal["冰点", "修复", "主升", "高潮", "分歧", "退潮"]
SentimentTradePermission = Literal["空仓等待", "轻仓试错", "强势进攻", "只低吸", "只卖不追"]
SentimentRiskLevel = Literal["低", "中", "高"]


class SentimentMainSectorSignal(BaseModel):
    name: str
    strength_score: float = 0
    limit_up_count: int = 0
    break_board_count: int = 0
    max_consecutive_boards: int = 0
    leader: str | None = None
    symbols: list[str] = Field(default_factory=list)


class SentimentDecisionResponse(BaseModel):
    trade_date: str
    market_state: SentimentMarketState = "冰点"
    trade_permission: SentimentTradePermission = "空仓等待"
    risk_level: SentimentRiskLevel = "中"
    confidence: float = Field(default=0, ge=0, le=100)
    score_change: float | None = None
    main_sectors: list[SentimentMainSectorSignal] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
```

- [ ] **Step 4: Implement the decision service**

Create `apps/api/app/services/sentiment_decision.py`:

```python
from __future__ import annotations

from app.models import (
    MarketEmotionSnapshotResponse,
    SentimentDecisionResponse,
    SentimentMainSectorSignal,
    SentimentSummaryResponse,
)


def build_sentiment_decision(
    summary: SentimentSummaryResponse,
    market_emotion: MarketEmotionSnapshotResponse | None = None,
) -> SentimentDecisionResponse:
    metrics = summary.metrics
    score = metrics.emotion_score
    score_change = _score_change(market_emotion)
    risk_count = _risk_count(summary)
    market_state = _market_state(summary, score_change)
    trade_permission = _trade_permission(market_state, risk_count)
    risk_level = "高" if risk_count >= 3 else "中" if risk_count >= 1 else "低"
    return SentimentDecisionResponse(
        trade_date=summary.trade_date,
        market_state=market_state,
        trade_permission=trade_permission,
        risk_level=risk_level,
        confidence=_confidence(summary, market_emotion),
        score_change=score_change,
        main_sectors=[
            SentimentMainSectorSignal(
                name=item.name,
                strength_score=item.strength_score,
                limit_up_count=item.limit_up_count,
                break_board_count=item.break_board_count,
                max_consecutive_boards=item.max_consecutive_boards,
                leader=item.leader,
                symbols=item.symbols,
            )
            for item in summary.hot_industries[:5]
        ],
        reasons=_reasons(summary, score_change),
        risks=_risks(summary, market_state),
    )


def _score_change(market_emotion: MarketEmotionSnapshotResponse | None) -> float | None:
    samples = market_emotion.samples if market_emotion else []
    if len(samples) < 2:
        return None
    return round(samples[-1].emotion_score - samples[0].emotion_score, 2)


def _risk_count(summary: SentimentSummaryResponse) -> int:
    metrics = summary.metrics
    risk_count = 0
    if (metrics.break_board_count or 0) >= 20:
        risk_count += 1
    if (metrics.limit_down_count or 0) >= 20:
        risk_count += 1
    if metrics.seal_rate_pct is not None and metrics.seal_rate_pct < 50:
        risk_count += 1
    if metrics.advance_count is not None and metrics.decline_count is not None and metrics.decline_count > metrics.advance_count * 2:
        risk_count += 1
    return risk_count


def _market_state(summary: SentimentSummaryResponse, score_change: float | None) -> str:
    metrics = summary.metrics
    score = metrics.emotion_score
    if score < 25:
        return "退潮" if _risk_count(summary) >= 2 else "冰点"
    if score >= 78:
        return "高潮"
    if _risk_count(summary) >= 3:
        return "退潮"
    if (metrics.break_board_count or 0) >= 18 and (metrics.seal_rate_pct or 100) < 60:
        return "分歧"
    if score_change is not None and score_change >= 10:
        return "修复"
    if score >= 62 and (metrics.limit_up_count or 0) >= 70:
        return "主升"
    if score >= 45:
        return "修复"
    return "冰点"


def _trade_permission(market_state: str, risk_count: int) -> str:
    if market_state in {"退潮", "冰点"}:
        return "空仓等待"
    if market_state == "高潮":
        return "只卖不追"
    if market_state == "分歧":
        return "只低吸"
    if market_state == "主升" and risk_count == 0:
        return "强势进攻"
    return "轻仓试错"


def _confidence(summary: SentimentSummaryResponse, market_emotion: MarketEmotionSnapshotResponse | None) -> float:
    confidence = 50
    metrics = summary.metrics
    if metrics.advance_count is not None and metrics.decline_count is not None:
        confidence += 15
    if metrics.turnover_change_pct is not None:
        confidence += 10
    if summary.hot_industries:
        confidence += 10
    if market_emotion and len(market_emotion.samples) >= 2:
        confidence += 15
    return float(min(confidence, 100))


def _reasons(summary: SentimentSummaryResponse, score_change: float | None) -> list[str]:
    metrics = summary.metrics
    reasons: list[str] = []
    if score_change is not None and score_change > 0:
        reasons.append("情绪分数回升")
    if (metrics.limit_up_count or 0) >= 50:
        reasons.append("涨停家数达到活跃区间")
    if metrics.seal_rate_pct is not None and metrics.seal_rate_pct >= 70:
        reasons.append("封板率较强")
    if summary.hot_industries:
        reasons.append(f"主线板块集中在{summary.hot_industries[0].name}")
    return reasons or ["数据不足，保持观察"]


def _risks(summary: SentimentSummaryResponse, market_state: str) -> list[str]:
    metrics = summary.metrics
    risks: list[str] = []
    if (metrics.limit_down_count or 0) >= 20 or (metrics.break_board_count or 0) >= 20:
        risks.append("跌停与炸板压力高")
    if metrics.seal_rate_pct is not None and metrics.seal_rate_pct < 50:
        risks.append("封板率偏低")
    if market_state == "高潮":
        risks.append("情绪过热，避免追高")
    if metrics.decline_count is not None and metrics.advance_count is not None and metrics.decline_count > metrics.advance_count:
        risks.append("下跌家数多于上涨家数")
    return risks
```

- [ ] **Step 5: Add the decision API**

In `apps/api/app/main.py`, add import:

```python
from app.services.sentiment_decision import build_sentiment_decision
```

Add endpoint near the existing sentiment endpoints:

```python
@app.get("/api/short-term/sentiment/decision")
def get_short_term_sentiment_decision(
    trade_date: str,
    limit: int = 80,
    refresh: bool = False,
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 200))
    if refresh:
        sentiment, market_emotion = _build_and_persist_sentiment_snapshots(trade_date, bounded_limit)
        summary = build_sentiment_summary(sentiment, market_emotion, snapshot_status="fresh")
    else:
        cached_summary = _sentiment_snapshot_store().load_summary(trade_date)
        cached_emotion = _sentiment_snapshot_store().load_market_emotion(trade_date)
        if cached_summary is None:
            sentiment, market_emotion = _build_and_persist_sentiment_snapshots(trade_date, bounded_limit)
            summary = build_sentiment_summary(sentiment, market_emotion, snapshot_status="fresh")
        else:
            summary = cached_summary
            market_emotion = cached_emotion
    return build_sentiment_decision(summary, market_emotion).model_dump(mode="json")
```

- [ ] **Step 6: Add API test**

In `apps/api/tests/test_api.py`, add:

```python
def test_short_term_sentiment_decision_api_returns_trade_permission(tmp_path: Path) -> None:
    with _configured_app(tmp_path) as client:
        response = client.get("/api/short-term/sentiment/decision?trade_date=2026-06-26&limit=20&refresh=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-26"
    assert payload["market_state"] in ["冰点", "修复", "主升", "高潮", "分歧", "退潮"]
    assert payload["trade_permission"] in ["空仓等待", "轻仓试错", "强势进攻", "只低吸", "只卖不追"]
    assert isinstance(payload["reasons"], list)
```

- [ ] **Step 7: Run backend verification**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_sentiment_decision.py tests/test_api.py -q
```

Expected: pass.

- [ ] **Step 8: Commit Stage 1 backend**

Run:

```bash
git add apps/api/app/models.py apps/api/app/services/sentiment_decision.py apps/api/app/main.py apps/api/tests/test_sentiment_decision.py apps/api/tests/test_api.py
git commit -m "Add sentiment decision layer"
```

Expected: commit succeeds.

### Task 2: Stage 1 Conclusion-First Sentiment UI

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/sentiment/SentimentWorkspace.tsx`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Add failing frontend contract assertions**

In `apps/web/lib/strongStockWorkbench.test.ts`, extend the sentiment assertions:

```ts
assert.match(apiSource, /getSentimentDecision/);
assert.match(typesSource, /SentimentDecisionResponse/);
assert.match(sentimentFeatureSource, /交易许可/);
assert.match(sentimentFeatureSource, /市场状态/);
assert.match(sentimentFeatureSource, /风险等级/);
```

- [ ] **Step 2: Run the failing frontend test**

Run:

```bash
cd apps/web
node --experimental-strip-types --test lib/strongStockWorkbench.test.ts
```

Expected: fail because the decision client and UI are not wired.

- [ ] **Step 3: Add frontend types**

In `apps/web/lib/types.ts`, add:

```ts
export type SentimentMarketState = "冰点" | "修复" | "主升" | "高潮" | "分歧" | "退潮";
export type SentimentTradePermission = "空仓等待" | "轻仓试错" | "强势进攻" | "只低吸" | "只卖不追";
export type SentimentRiskLevel = "低" | "中" | "高";

export type SentimentMainSectorSignal = {
  name: string;
  strength_score: number;
  limit_up_count: number;
  break_board_count: number;
  max_consecutive_boards: number;
  leader: string | null;
  symbols: string[];
};

export type SentimentDecisionResponse = {
  trade_date: string;
  market_state: SentimentMarketState;
  trade_permission: SentimentTradePermission;
  risk_level: SentimentRiskLevel;
  confidence: number;
  score_change: number | null;
  main_sectors: SentimentMainSectorSignal[];
  reasons: string[];
  risks: string[];
  generated_at: string;
};
```

- [ ] **Step 4: Add API client**

In `apps/web/lib/api.ts`, import `SentimentDecisionResponse` and add:

```ts
export async function getSentimentDecision(
  tradeDate: string,
  limit = 80,
  refresh = false,
): Promise<SentimentDecisionResponse> {
  const params = new URLSearchParams({
    trade_date: tradeDate,
    limit: String(limit),
    refresh: String(refresh),
  });
  const response = await fetch(`${API_BASE_URL}/api/short-term/sentiment/decision?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`读取情绪交易许可失败：${response.status} ${await response.text()}`);
  }
  return response.json();
}
```

- [ ] **Step 5: Add decision card to the sentiment workspace**

In `apps/web/app/sentiment/SentimentWorkspace.tsx`, add state:

```tsx
const [decision, setDecision] = useState<SentimentDecisionResponse | null>(null);
const [decisionLoading, setDecisionLoading] = useState(true);
```

In `refresh`, call the new client:

```tsx
const nextDecision = await getSentimentDecision(date, 80, forceRefresh);
setDecision(nextDecision);
```

Render a new card before `MarketEmotionDashboard`:

```tsx
<SentimentDecisionCard decision={decision} loading={decisionLoading} />
```

Add a local component:

```tsx
function SentimentDecisionCard({
  decision,
  loading,
}: {
  decision: SentimentDecisionResponse | null;
  loading: boolean;
}) {
  if (loading && !decision) {
    return (
      <section className="workbench-panel rounded-xl border p-4">
        <Skeleton active paragraph={{ rows: 3 }} />
      </section>
    );
  }
  return (
    <section className="workbench-panel rounded-xl border">
      <div className="workbench-panel-divider flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <div className="text-sm font-black text-[#11100e]">情绪交易许可</div>
          <div className="text-xs text-[#7b756d]">先给结论，再看明细。</div>
        </div>
        <Space wrap>
          <Tag color={decision?.market_state === "退潮" ? "green" : decision?.market_state === "高潮" ? "orange" : "red"}>
            市场状态：{decision?.market_state ?? "--"}
          </Tag>
          <Tag color={decision?.risk_level === "高" ? "red" : decision?.risk_level === "中" ? "orange" : "green"}>
            风险等级：{decision?.risk_level ?? "--"}
          </Tag>
        </Space>
      </div>
      <div className="grid gap-3 p-4 lg:grid-cols-[260px_minmax(0,1fr)_minmax(0,1fr)]">
        <div className="rounded-lg border border-[#e3ddd3] bg-white px-4 py-3">
          <div className="text-xs font-black text-[#7b756d]">交易许可</div>
          <div className="mt-2 text-2xl font-black text-[#11100e]">{decision?.trade_permission ?? "--"}</div>
          <div className="mt-1 text-xs text-[#7b756d]">置信度 {decision ? decision.confidence.toFixed(0) : "--"}/100</div>
        </div>
        <div className="rounded-lg border border-[#e3ddd3] bg-white px-4 py-3">
          <div className="text-xs font-black text-[#7b756d]">成立原因</div>
          <div className="mt-2 flex flex-wrap gap-1">
            {(decision?.reasons ?? []).map((item) => <Tag key={item}>{item}</Tag>)}
          </div>
        </div>
        <div className="rounded-lg border border-[#e3ddd3] bg-white px-4 py-3">
          <div className="text-xs font-black text-[#7b756d]">风险提示</div>
          <div className="mt-2 flex flex-wrap gap-1">
            {(decision?.risks.length ? decision.risks : ["暂无硬风险"]).map((item) => <Tag key={item}>{item}</Tag>)}
          </div>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 6: Run frontend verification**

Run:

```bash
cd apps/web
./node_modules/.bin/tsc --noEmit
node --experimental-strip-types --test lib/strongStockWorkbench.test.ts
```

Expected: pass.

- [ ] **Step 7: Commit Stage 1 UI**

Run:

```bash
git add apps/web/lib/types.ts apps/web/lib/api.ts apps/web/app/sentiment/SentimentWorkspace.tsx apps/web/lib/strongStockWorkbench.test.ts
git commit -m "Show sentiment trade permission"
```

Expected: commit succeeds.

### Task 3: Stage 2 Watchlist-Sentiment Linkage

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/services/sentiment_watchlist.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_sentiment_watchlist.py`
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/sentiment/SentimentWorkspace.tsx`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Add backend tests for watchlist grouping**

Create `apps/api/tests/test_sentiment_watchlist.py`:

```python
from app.models import SentimentDecisionResponse, SentimentMainSectorSignal
from app.providers.watchlist import WatchlistItem
from app.services.sentiment_watchlist import build_sentiment_watchlist_alerts


def test_watchlist_alerts_prioritize_main_sector_matches() -> None:
    decision = SentimentDecisionResponse(
        trade_date="2026-07-02",
        market_state="修复",
        trade_permission="轻仓试错",
        risk_level="中",
        main_sectors=[
            SentimentMainSectorSignal(name="存储芯片", strength_score=88, symbols=["001309.SZ"]),
        ],
        reasons=["主线板块集中在存储芯片"],
    )
    items = [
        WatchlistItem(symbol="001309.SZ", name="德明利", group="存储芯片", tags=["观察"]),
        WatchlistItem(symbol="600000.SH", name="浦发银行", group="银行", tags=[]),
    ]

    result = build_sentiment_watchlist_alerts(decision, items)

    assert result[0].symbol == "001309.SZ"
    assert result[0].action == "重点盯"
    assert "命中主线板块" in result[0].reasons
    assert result[1].action == "等确认"
```

- [ ] **Step 2: Run failing backend test**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_sentiment_watchlist.py -q
```

Expected: fail because watchlist linkage does not exist.

- [ ] **Step 3: Add models**

In `apps/api/app/models.py`, add:

```python
SentimentWatchlistAction = Literal["重点盯", "等确认", "风险回避"]


class SentimentWatchlistAlert(BaseModel):
    symbol: str
    name: str
    group: str | None = None
    tags: list[str] = Field(default_factory=list)
    action: SentimentWatchlistAction = "等确认"
    matched_sector: str | None = None
    reasons: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Implement watchlist linkage service**

Create `apps/api/app/services/sentiment_watchlist.py`:

```python
from __future__ import annotations

from app.models import SentimentDecisionResponse, SentimentWatchlistAlert
from app.providers.watchlist import WatchlistItem


def build_sentiment_watchlist_alerts(
    decision: SentimentDecisionResponse,
    watchlist_items: list[WatchlistItem],
) -> list[SentimentWatchlistAlert]:
    main_sector_names = {item.name for item in decision.main_sectors}
    main_symbols = {symbol for sector in decision.main_sectors for symbol in sector.symbols}
    output: list[SentimentWatchlistAlert] = []
    for item in watchlist_items:
        reasons: list[str] = []
        matched_sector = None
        if item.group in main_sector_names:
            matched_sector = item.group
            reasons.append("命中主线板块")
        if item.symbol in main_symbols:
            reasons.append("属于主线代表股票")
        if decision.trade_permission in {"空仓等待", "只卖不追"} or decision.risk_level == "高":
            action = "风险回避"
            reasons.append(f"当前交易许可为{decision.trade_permission}")
        elif reasons:
            action = "重点盯"
        else:
            action = "等确认"
        output.append(
            SentimentWatchlistAlert(
                symbol=item.symbol,
                name=item.name or item.symbol,
                group=item.group,
                tags=item.tags,
                action=action,
                matched_sector=matched_sector,
                reasons=reasons or ["未命中当前主线，等待确认"],
            )
        )
    return sorted(output, key=_sort_key)


def _sort_key(item: SentimentWatchlistAlert) -> tuple[int, str]:
    rank = {"重点盯": 0, "等确认": 1, "风险回避": 2}
    return (rank[item.action], item.symbol)
```

- [ ] **Step 5: Add endpoint**

In `apps/api/app/main.py`, add:

```python
@app.get("/api/short-term/sentiment/watchlist-alerts")
def get_sentiment_watchlist_alerts(
    trade_date: str,
    limit: int = 80,
    refresh: bool = False,
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 200))
    sentiment, market_emotion = _build_and_persist_sentiment_snapshots(trade_date, bounded_limit)
    summary = build_sentiment_summary(sentiment, market_emotion, snapshot_status="fresh")
    decision = build_sentiment_decision(summary, market_emotion)
    items = parse_watchlist_text(_read_watchlist_pool())
    alerts = build_sentiment_watchlist_alerts(decision, items)
    return {"trade_date": trade_date, "items": [item.model_dump(mode="json") for item in alerts]}
```

- [ ] **Step 6: Add frontend card**

Add types and client:

```ts
export type SentimentWatchlistAlert = {
  symbol: string;
  name: string;
  group: string | null;
  tags: string[];
  action: "重点盯" | "等确认" | "风险回避";
  matched_sector: string | null;
  reasons: string[];
};

export type SentimentWatchlistAlertsResponse = {
  trade_date: string;
  items: SentimentWatchlistAlert[];
};
```

Render below the decision card as `自选股联动`, grouped by `action`.

- [ ] **Step 7: Run verification**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_sentiment_watchlist.py tests/test_api.py -q
cd ../web
./node_modules/.bin/tsc --noEmit
node --experimental-strip-types --test lib/strongStockWorkbench.test.ts
```

Expected: pass.

- [ ] **Step 8: Commit Stage 2**

Run:

```bash
git add apps/api apps/web
git commit -m "Link sentiment decisions to watchlist"
```

Expected: commit succeeds.

### Task 4: Stage 3 Timeline Sampling and Actionable Notifications

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/services/sentiment_monitor.py`
- Modify: `apps/api/app/services/short_term_sentiment.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_sentiment_monitor.py`
- Modify: `apps/web/app/sentiment/SentimentWorkspace.tsx`
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Add tests for timeline labels**

In `apps/api/tests/test_sentiment_monitor.py`, add:

```python
from app.services.sentiment_monitor import sentiment_timeline_label


def test_sentiment_timeline_label_maps_key_trading_windows() -> None:
    assert sentiment_timeline_label("09:25") == "竞价定调"
    assert sentiment_timeline_label("09:35") == "开盘承接"
    assert sentiment_timeline_label("10:00") == "情绪确认"
    assert sentiment_timeline_label("11:30") == "上午定性"
    assert sentiment_timeline_label("14:30") == "尾盘风险"
```

- [ ] **Step 2: Add tests for actionable alert text**

In `apps/api/tests/test_sentiment_monitor.py`, add:

```python
def test_sentiment_monitor_alert_includes_trade_permission() -> None:
    previous = _sample("09:35", score=62, break_board=4, limit_down=1, seal_rate=82)
    current = _sample("10:00", score=31, break_board=16, limit_down=11, seal_rate=55)

    alerts = detect_sentiment_mutations([previous, current], SentimentMonitorConfig())

    assert alerts
    assert any("交易许可" in alert.message for alert in alerts)
```

- [ ] **Step 3: Implement timeline labels**

In `apps/api/app/services/sentiment_monitor.py`, add:

```python
def sentiment_timeline_label(hhmm: str) -> str:
    if hhmm <= "09:25":
        return "竞价定调"
    if hhmm <= "09:35":
        return "开盘承接"
    if hhmm <= "10:00":
        return "情绪确认"
    if hhmm <= "11:30":
        return "上午定性"
    if hhmm <= "14:30":
        return "尾盘风险"
    return "收盘复盘"
```

- [ ] **Step 4: Include decision text in alerts**

In `detect_sentiment_mutations`, when building alert messages, append an action sentence:

```python
def _trade_permission_hint(current: MarketEmotionSample) -> str:
    if current.emotion_score < 25 or (current.limit_down_count or 0) >= 20:
        return "交易许可：空仓等待。"
    if current.break_board_count >= 15 or (current.seal_rate_pct or 100) < 60:
        return "交易许可：只低吸，不追高。"
    if current.emotion_score >= 78:
        return "交易许可：只卖不追。"
    if current.emotion_score >= 60:
        return "交易许可：轻仓进攻。"
    return "交易许可：轻仓试错。"
```

- [ ] **Step 5: Show timeline on the sentiment page**

In `apps/web/app/sentiment/SentimentWorkspace.tsx`, update `EmotionHistoryChart` to show key labels under the chart:

```tsx
const timelineLabels = ["竞价定调", "开盘承接", "情绪确认", "上午定性", "尾盘风险"];
```

Render them as compact tags below the chart.

- [ ] **Step 6: Run verification**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_sentiment_monitor.py tests/test_short_term_sentiment.py -q
cd ../web
./node_modules/.bin/tsc --noEmit
node --experimental-strip-types --test lib/strongStockWorkbench.test.ts
```

Expected: pass.

- [ ] **Step 7: Commit Stage 3**

Run:

```bash
git add apps/api apps/web
git commit -m "Add sentiment timeline alerts"
```

Expected: commit succeeds.

### Task 5: Stage 4 Decision Archive and Rule Calibration

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/services/sentiment_review_store.py`
- Create: `apps/api/app/services/sentiment_review.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_sentiment_review.py`
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/sentiment/SentimentWorkspace.tsx`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Add backend tests for archive and scoring**

Create `apps/api/tests/test_sentiment_review.py`:

```python
from pathlib import Path

from app.models import SentimentDecisionResponse
from app.services.sentiment_review import score_sentiment_decision
from app.services.sentiment_review_store import SentimentReviewStore


def _decision(trade_date: str, permission: str) -> SentimentDecisionResponse:
    return SentimentDecisionResponse(
        trade_date=trade_date,
        market_state="修复",
        trade_permission=permission,
        risk_level="中",
        confidence=80,
        reasons=["情绪分数回升"],
    )


def test_sentiment_review_store_persists_decision(tmp_path: Path) -> None:
    store = SentimentReviewStore(tmp_path)
    store.save_decision(_decision("2026-07-02", "轻仓试错"))

    loaded = store.load_decisions("2026-07-02")

    assert len(loaded) == 1
    assert loaded[0].trade_date == "2026-07-02"
    assert loaded[0].trade_permission == "轻仓试错"


def test_score_sentiment_decision_rewards_correct_risk_off_call() -> None:
    result = score_sentiment_decision(
        decision=_decision("2026-07-02", "空仓等待"),
        next_day_index_pct=-2.1,
        next_day_limit_up_count=18,
        next_day_limit_down_count=42,
    )

    assert result.hit is True
    assert result.score > 0
    assert "空仓等待规避退潮" in result.reason
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_sentiment_review.py -q
```

Expected: fail because review store and scorer do not exist.

- [ ] **Step 3: Add review models**

In `apps/api/app/models.py`, add:

```python
class SentimentDecisionOutcome(BaseModel):
    trade_date: str
    next_day_index_pct: float | None = None
    next_day_limit_up_count: int | None = None
    next_day_limit_down_count: int | None = None
    hit: bool = False
    score: float = 0
    reason: str = ""


class SentimentReviewSummary(BaseModel):
    trade_date: str
    sample_count: int = 0
    hit_count: int = 0
    hit_rate_pct: float = 0
    avg_score: float = 0
    outcomes: list[SentimentDecisionOutcome] = Field(default_factory=list)
```

- [ ] **Step 4: Implement JSONL review store**

Create `apps/api/app/services/sentiment_review_store.py`:

```python
from __future__ import annotations

from pathlib import Path

from app.models import SentimentDecisionResponse


class SentimentReviewStore:
    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir / "sentiment_reviews"
        self.root.mkdir(parents=True, exist_ok=True)

    def save_decision(self, decision: SentimentDecisionResponse) -> None:
        path = self.root / f"{decision.trade_date}.jsonl"
        existing = [item for item in self.load_decisions(decision.trade_date) if item.generated_at != decision.generated_at]
        existing.append(decision)
        path.write_text("\n".join(item.model_dump_json() for item in existing) + "\n", encoding="utf-8")

    def load_decisions(self, trade_date: str) -> list[SentimentDecisionResponse]:
        path = self.root / f"{trade_date}.jsonl"
        if not path.exists():
            return []
        return [
            SentimentDecisionResponse.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
```

- [ ] **Step 5: Implement review scoring**

Create `apps/api/app/services/sentiment_review.py`:

```python
from __future__ import annotations

from app.models import SentimentDecisionOutcome, SentimentDecisionResponse


def score_sentiment_decision(
    decision: SentimentDecisionResponse,
    next_day_index_pct: float | None,
    next_day_limit_up_count: int | None,
    next_day_limit_down_count: int | None,
) -> SentimentDecisionOutcome:
    weak_next_day = (next_day_index_pct or 0) < -1 or (next_day_limit_down_count or 0) >= 30
    strong_next_day = (next_day_index_pct or 0) > 1 or (next_day_limit_up_count or 0) >= 70
    hit = False
    score = 0.0
    reason = "结果中性"
    if decision.trade_permission == "空仓等待" and weak_next_day:
        hit = True
        score = 1.0
        reason = "空仓等待规避退潮"
    elif decision.trade_permission in {"轻仓试错", "强势进攻"} and strong_next_day:
        hit = True
        score = 1.0
        reason = "进攻许可匹配次日强势"
    elif decision.trade_permission == "只卖不追" and not strong_next_day:
        hit = True
        score = 0.7
        reason = "高潮降温提示有效"
    else:
        score = -0.5
        reason = "情绪许可与次日表现不匹配"
    return SentimentDecisionOutcome(
        trade_date=decision.trade_date,
        next_day_index_pct=next_day_index_pct,
        next_day_limit_up_count=next_day_limit_up_count,
        next_day_limit_down_count=next_day_limit_down_count,
        hit=hit,
        score=score,
        reason=reason,
    )
```

- [ ] **Step 6: Add review endpoints**

In `apps/api/app/main.py`, add:

```python
@app.post("/api/short-term/sentiment/review/archive")
def archive_sentiment_decision(trade_date: str, limit: int = 80) -> dict[str, object]:
    sentiment, market_emotion = _build_and_persist_sentiment_snapshots(trade_date, max(1, min(limit, 200)))
    summary = build_sentiment_summary(sentiment, market_emotion, snapshot_status="fresh")
    decision = build_sentiment_decision(summary, market_emotion)
    _sentiment_review_store().save_decision(decision)
    return decision.model_dump(mode="json")
```

Add `_sentiment_review_store()` using `Path(get_settings().data_dir)` in the same style as other stores.

- [ ] **Step 7: Add frontend review panel**

Add a compact `规则校准` panel below the existing monitor panel:

```tsx
<section className="workbench-panel rounded-xl border p-4">
  <div className="text-sm font-black text-[#11100e]">规则校准</div>
  <div className="mt-1 text-xs text-[#7b756d]">
    每日归档情绪结论，后续对照次日表现统计命中率。
  </div>
</section>
```

- [ ] **Step 8: Run verification**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_sentiment_review.py tests/test_api.py -q
cd ../web
./node_modules/.bin/tsc --noEmit
node --experimental-strip-types --test lib/strongStockWorkbench.test.ts
```

Expected: pass.

- [ ] **Step 9: Commit Stage 4**

Run:

```bash
git add apps/api apps/web
git commit -m "Archive sentiment decisions for calibration"
```

Expected: commit succeeds.

### Task 6: Full Verification and Release

**Files:**
- All changed files.

- [ ] **Step 1: Run full backend tests**

Run:

```bash
cd apps/api
.venv/bin/pytest
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend verification**

Run:

```bash
cd apps/web
./node_modules/.bin/tsc --noEmit
node --experimental-strip-types --test lib/*.test.ts
```

Expected: all tests pass.

- [ ] **Step 3: Build Docker image**

Run:

```bash
docker buildx build --platform linux/amd64 -t icekale/strong-stock-screener:sentiment-usability-test --load .
```

Expected: image builds successfully.

- [ ] **Step 4: Smoke test container**

Run:

```bash
docker rm -f strong-stock-screener-sentiment-test >/dev/null 2>&1 || true
docker run --platform linux/amd64 --rm -d --name strong-stock-screener-sentiment-test -p 3114:3110 --env-file .env icekale/strong-stock-screener:sentiment-usability-test
curl -fsS http://127.0.0.1:3114/health
curl -fsS -I http://127.0.0.1:3114/sentiment
curl -fsS "http://127.0.0.1:3114/api/short-term/sentiment/decision?trade_date=$(date +%F)&limit=80&refresh=false"
docker rm -f strong-stock-screener-sentiment-test
```

Expected: health returns `{"status":"ok"}`, `/sentiment` returns HTTP 200, and the decision endpoint returns JSON.

- [ ] **Step 5: Merge and deploy**

Run:

```bash
git switch main
git pull --ff-only
git merge --no-ff <feature-branch> -m "Merge sentiment usability roadmap"
git push origin main
docker buildx build --platform linux/amd64 -t icekale/strong-stock-screener:latest -t icekale/strong-stock-screener:<short-sha> --push .
ssh root@192.168.5.28 "cd /mnt/user/appdata/strong-stock-screener && docker compose pull strong-stock-screener && docker compose up -d strong-stock-screener"
```

Expected: GitHub, Docker Hub, and Unraid update successfully.

---

## Scope Guardrails

- Do not remove the existing raw sentiment dashboard in Stage 1. Put the conclusion card above it.
- Do not change the GSGF stock-picking rules in this project phase.
- Do not make AI-generated conclusions required for the first version. Use deterministic rules first; AI summary belongs in a separate approved plan after outputs are stable.
- Do not pretend historical sentiment decisions exist before Stage 4 starts archiving them.
- Use TickFlow realtime data where already available; only add new data dependencies when a stage explicitly needs them.

## Self-Review

- Spec coverage: the four requested stages are mapped to Tasks 1-5, with Task 6 for release verification.
- Placeholder scan: no incomplete markers or unspecified test command remains.
- Type consistency: backend model names use `SentimentDecisionResponse`, `SentimentMainSectorSignal`, and `SentimentWatchlistAlert`; frontend mirrors those names.
- Scope check: each stage can ship independently, and Stage 1 does not require watchlist linkage, timeline alerts, or calibration archive.
