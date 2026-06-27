# 股是股非模型体系 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the complete 股是股非 model system: screening result enhancement, independent strategy modes, and watchlist structure-trigger monitoring.

**Architecture:** Keep the new model isolated in focused backend files (`models.py`, `gsgf_rules.py`, screener integration) and expose it through existing API and UI surfaces. The existing strong-stock statuses remain unchanged; 股是股非 produces separate analysis/action labels and watchlist trigger states.

**Tech Stack:** FastAPI, Pydantic, Python rule functions, Next.js 15, React 19, TypeScript, existing `corepack pnpm test` and `uv run pytest -q`.

---

## File Map

- Modify `apps/api/app/models.py`: add 股是股非 enums and Pydantic models, attach optional `gsgf` to screening and risk items.
- Create `apps/api/app/gsgf_rules.py`: pure rule functions for score, zone, volume structure, pressure, patterns, stars, and action.
- Modify `apps/api/app/rules.py`: compute `gsgf` for existing screening/watchlist items.
- Modify `apps/api/app/services/screener.py`: add strategy request support and sort by strong/gsgf/combined.
- Modify `apps/api/app/main.py`: add request fields and `/api/watchlist/gsgf-status`.
- Modify `apps/api/app/services/runs.py`: keep compatibility through Pydantic models; no separate storage engine change expected.
- Modify `apps/web/lib/types.ts`: add strategy and 股是股非 response types.
- Modify `apps/web/lib/api.ts`: pass strategy fields and add watchlist gsgf status API.
- Modify `apps/web/components/ScreenerWorkbench.tsx`: add strategy selector and result/detail display.
- Modify `apps/web/app/watchlist/page.tsx`: add structure trigger status column and filters.
- Test `apps/api/tests/test_gsgf_rules.py`: focused rule tests.
- Modify `apps/api/tests/test_rules.py`: integration into screening/watchlist items.
- Modify `apps/api/tests/test_api.py`: strategy request and watchlist endpoint tests.
- Modify `apps/web/lib/strongStockWorkbench.test.ts`: static coverage for UI/API wiring.

---

## Task 1: Backend Models

**Files:**
- Modify: `apps/api/app/models.py`
- Test: `apps/api/tests/test_gsgf_rules.py`

- [ ] **Step 1: Write failing model serialization test**

Create `apps/api/tests/test_gsgf_rules.py` with:

```python
from app.models import GsgfAnalysis, GsgfScoreBreakdown


def test_gsgf_analysis_serializes_business_fields() -> None:
    analysis = GsgfAnalysis(
        model_version="gsgf-v1",
        total_score=78,
        action="watch_candidate",
        zone="b_zone_a_point",
        volume_structure="three_yang_controls_three_yin",
        scores=GsgfScoreBreakdown(
            safety_pressure=15,
            volume_thickness=22,
            ma_alignment=18,
            pattern_space=10,
            star_trigger=5,
            sector_theme=8,
        ),
        pattern_tags=["颈位回踩"],
        trigger_tags=["星线蓄势"],
        pressure_flags=["前高压力"],
        risk_flags=[],
        explanation=["B区A点，等待确认"],
    )

    payload = analysis.model_dump(mode="json")

    assert payload["model_version"] == "gsgf-v1"
    assert payload["total_score"] == 78
    assert payload["action"] == "watch_candidate"
    assert payload["zone"] == "b_zone_a_point"
    assert payload["scores"]["volume_thickness"] == 22
```

- [ ] **Step 2: Verify red**

Run: `cd apps/api && uv run pytest tests/test_gsgf_rules.py::test_gsgf_analysis_serializes_business_fields -q`

Expected: fail with import error for `GsgfAnalysis`.

- [ ] **Step 3: Add models**

In `apps/api/app/models.py`, add literal aliases:

```python
GsgfAction = Literal["strong_candidate", "watch_candidate", "wait_trigger", "avoid"]
GsgfZone = Literal["a_zone", "b_zone_a_point", "c_zone", "unformed", "unknown"]
GsgfVolumeStructure = Literal[
    "three_yang_controls_three_yin",
    "neutral",
    "three_yin_controls_three_yang",
    "unknown",
]
ScreenStrategy = Literal["strong_stock", "gsgf", "combined"]
```

Add classes:

```python
class GsgfScoreBreakdown(BaseModel):
    safety_pressure: int = 0
    volume_thickness: int = 0
    ma_alignment: int = 0
    pattern_space: int = 0
    star_trigger: int = 0
    sector_theme: int = 0


class GsgfAnalysis(BaseModel):
    model_version: str = "gsgf-v1"
    total_score: int = 0
    action: GsgfAction = "wait_trigger"
    zone: GsgfZone = "unknown"
    volume_structure: GsgfVolumeStructure = "unknown"
    scores: GsgfScoreBreakdown = Field(default_factory=GsgfScoreBreakdown)
    pattern_tags: list[str] = Field(default_factory=list)
    trigger_tags: list[str] = Field(default_factory=list)
    pressure_flags: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    explanation: list[str] = Field(default_factory=list)
```

Add optional field to `StrongStockScreeningItem` and `StrongStockRiskItem`:

```python
    gsgf: GsgfAnalysis | None = None
```

Add result metadata fields to `StrongStockScreeningResult`:

```python
    strategy: ScreenStrategy = "strong_stock"
    strong_model_version: str = "strong-v1"
    gsgf_model_version: str | None = None
    sort_version: str = "strong-sort-v1"
```

- [ ] **Step 4: Verify green**

Run: `cd apps/api && uv run pytest tests/test_gsgf_rules.py::test_gsgf_analysis_serializes_business_fields -q`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/models.py apps/api/tests/test_gsgf_rules.py
git commit -m "feat: add gsgf response models"
```

---

## Task 2: Pure 股是股非 Rule Engine

**Files:**
- Create: `apps/api/app/gsgf_rules.py`
- Test: `apps/api/tests/test_gsgf_rules.py`

- [ ] **Step 1: Add failing rule tests**

Append to `apps/api/tests/test_gsgf_rules.py`:

```python
from app.gsgf_rules import analyze_gsgf
from app.models import KlineBar


def _bars(closes: list[float], volumes: list[float] | None = None) -> list[KlineBar]:
    bars: list[KlineBar] = []
    for index, close in enumerate(closes):
        previous = closes[index - 1] if index else close
        is_up = close >= previous
        open_price = previous * (0.99 if is_up else 1.02)
        volume = volumes[index] if volumes else 1_000_000
        bars.append(
            KlineBar(
                date=f"2026-01-{(index % 28) + 1:02d}",
                open=round(open_price, 2),
                close=round(close, 2),
                high=round(max(open_price, close) * 1.03, 2),
                low=round(min(open_price, close) * 0.98, 2),
                volume=volume,
            )
        )
    return bars


def test_gsgf_detects_three_yang_controls_three_yin() -> None:
    closes = [10 + index * 0.03 for index in range(220)]
    volumes = [2_000_000 if index % 4 != 0 else 700_000 for index in range(220)]

    analysis = analyze_gsgf(_bars(closes, volumes), industry_strength="strong")

    assert analysis.volume_structure == "three_yang_controls_three_yin"
    assert analysis.scores.volume_thickness >= 18
    assert analysis.total_score >= 65


def test_gsgf_marks_c_zone_and_avoid_for_downtrend() -> None:
    closes = [20 - index * 0.04 for index in range(220)]

    analysis = analyze_gsgf(_bars(closes), industry_strength="weak")

    assert analysis.zone == "c_zone"
    assert analysis.action == "avoid"
    assert "C区风险" in analysis.risk_flags


def test_gsgf_detects_high_volume_upper_shadow_pressure() -> None:
    closes = [10 + index * 0.05 for index in range(219)] + [20.1]
    bars = _bars(closes, [1_000_000 for _ in range(219)] + [5_000_000])
    bars[-1] = bars[-1].model_copy(update={"high": 24.0, "open": 20.0, "close": 20.1, "low": 19.8})

    analysis = analyze_gsgf(bars)

    assert "高位巨量长上影" in analysis.risk_flags
    assert analysis.action == "avoid"
```

- [ ] **Step 2: Verify red**

Run: `cd apps/api && uv run pytest tests/test_gsgf_rules.py -q`

Expected: fail with missing `app.gsgf_rules`.

- [ ] **Step 3: Implement minimal pure rule engine**

Create `apps/api/app/gsgf_rules.py` with:

```python
from __future__ import annotations

from statistics import mean

from app.models import GsgfAnalysis, GsgfScoreBreakdown, IndustryStrength, KlineBar

GSGF_MODEL_VERSION = "gsgf-v1"


def analyze_gsgf(
    bars: list[KlineBar],
    *,
    industry_strength: IndustryStrength | None = None,
) -> GsgfAnalysis:
    if len(bars) < 60:
        return GsgfAnalysis(
            model_version=GSGF_MODEL_VERSION,
            zone="unknown",
            action="wait_trigger",
            risk_flags=["K线不足60日"],
            explanation=["股是股非模型需要至少60日K线"],
        )
    enriched = _with_ma(bars)
    pressure_flags, pressure_risks, safety_score = _pressure(enriched)
    volume_structure, volume_score, volume_notes = _volume_structure(enriched[-40:])
    zone, ma_score, ma_notes, ma_risks = _zone_and_ma(enriched)
    pattern_score, pattern_tags = _patterns(enriched)
    star_score, trigger_tags, star_risks = _stars(enriched, zone)
    sector_score = _sector_score(industry_strength)
    scores = GsgfScoreBreakdown(
        safety_pressure=safety_score,
        volume_thickness=volume_score,
        ma_alignment=ma_score,
        pattern_space=pattern_score,
        star_trigger=star_score,
        sector_theme=sector_score,
    )
    risk_flags = _dedupe(pressure_risks + ma_risks + star_risks)
    total_score = max(0, min(100, sum(scores.model_dump().values()) - _risk_penalty(risk_flags)))
    action = _action(total_score, zone, risk_flags, trigger_tags)
    return GsgfAnalysis(
        model_version=GSGF_MODEL_VERSION,
        total_score=round(total_score),
        action=action,
        zone=zone,
        volume_structure=volume_structure,
        scores=scores,
        pattern_tags=pattern_tags,
        trigger_tags=trigger_tags,
        pressure_flags=pressure_flags,
        risk_flags=risk_flags,
        explanation=_dedupe(volume_notes + ma_notes + pattern_tags + trigger_tags + pressure_flags + risk_flags),
    )


def _with_ma(bars: list[KlineBar]) -> list[KlineBar]:
    output: list[KlineBar] = []
    for index, bar in enumerate(bars):
        closes = [item.close for item in bars[: index + 1]]
        output.append(
            bar.model_copy(
                update={
                    "ma5": bar.ma5 if bar.ma5 is not None else _ma(closes, 5),
                    "ma10": bar.ma10 if bar.ma10 is not None else _ma(closes, 10),
                    "ma20": bar.ma20 if bar.ma20 is not None else _ma(closes, 20),
                    "ma60": bar.ma60 if bar.ma60 is not None else _ma(closes, 60),
                }
            )
        )
    return output


def _ma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[-window:])


def _pressure(bars: list[KlineBar]) -> tuple[list[str], list[str], int]:
    latest = bars[-1]
    recent20 = bars[-20:]
    avg_volume = mean(bar.volume for bar in bars[-35:])
    gain20 = latest.close / max(recent20[0].close, 1) - 1
    flags: list[str] = []
    risks: list[str] = []
    if gain20 > 0.35 and latest.volume > avg_volume * 2 and _long_upper_shadow(latest):
        risks.append("高位巨量长上影")
    previous_high = max(bar.high for bar in bars[-120:-1]) if len(bars) >= 121 else 0
    if previous_high and latest.close >= previous_high * 0.97 and latest.volume < avg_volume * 1.2:
        flags.append("接近前高压力但放量不足")
    return flags, risks, 8 if risks else 16 if flags else 20


def _volume_structure(bars: list[KlineBar]) -> tuple[str, int, list[str]]:
    red = [bar for bar in bars if bar.close > bar.open]
    green = [bar for bar in bars if bar.close < bar.open]
    red_day_ratio = len(red) / max(len(bars), 1)
    red_volume_ratio = sum(bar.volume for bar in red) / max(sum(bar.volume for bar in bars), 1)
    avg_red = mean([bar.volume for bar in red]) if red else 0
    avg_green = mean([bar.volume for bar in green]) if green else 0
    if red_day_ratio >= 0.55 and red_volume_ratio >= 0.6 and avg_red >= avg_green * 1.15:
        return "three_yang_controls_three_yin", 22, ["三阳控三阴"]
    if red_day_ratio <= 0.45 and red_volume_ratio <= 0.45 and avg_green > avg_red * 1.1:
        return "three_yin_controls_three_yang", 5, ["三阴控三阳"]
    return "neutral", 12, ["量形态中性"]


def _zone_and_ma(bars: list[KlineBar]) -> tuple[str, int, list[str], list[str]]:
    latest = bars[-1]
    previous = bars[-2]
    ma5 = latest.ma5 or latest.close
    ma10 = latest.ma10 or latest.close
    ma20 = latest.ma20 or latest.close
    ma60 = latest.ma60 or latest.close
    ma_values = [ma5, ma10, ma20]
    tight = max(ma_values) / max(min(ma_values), 1) - 1
    slopes_up = sum(
        1
        for current, prev in [
            (latest.ma5, previous.ma5),
            (latest.ma10, previous.ma10),
            (latest.ma20, previous.ma20),
        ]
        if current is not None and prev is not None and current > prev
    )
    if latest.close < ma10 and slopes_up <= 1:
        return "c_zone", 2, [], ["C区风险"]
    if tight < 0.06 and latest.close > max(ma_values) and slopes_up >= 2:
        return "a_zone", 18, ["A区均线归位"], []
    trend_ok = ma20 > ma60 and latest.close > ma10 and abs(latest.low / max(ma20, 1) - 1) < 0.06
    if trend_ok:
        return "b_zone_a_point", 15, ["B区A点"], []
    return "unformed", 8, ["均线结构未完全成型"], []


def _patterns(bars: list[KlineBar]) -> tuple[int, list[str]]:
    latest = bars[-1]
    recent60 = bars[-60:]
    high60 = max(bar.high for bar in recent60[:-1])
    low60 = min(bar.low for bar in recent60)
    tags: list[str] = []
    score = 0
    if latest.close >= high60 * 0.98:
        tags.append("颈位附近")
        score += 6
    if (high60 - low60) / max(latest.close, 1) < 0.22:
        tags.append("箱体收敛")
        score += 5
    if _higher_lows(recent60):
        tags.append("低点抬高")
        score += 4
    return min(15, score), tags


def _stars(bars: list[KlineBar], zone: str) -> tuple[int, list[str], list[str]]:
    recent = bars[-4:-1]
    latest = bars[-1]
    trigger_tags: list[str] = []
    risks: list[str] = []
    star_count = sum(1 for bar in recent if _is_star(bar))
    avg_volume20 = mean(bar.volume for bar in bars[-20:])
    if star_count >= 2 and mean(bar.volume for bar in recent) < avg_volume20 * 0.9:
        if zone in {"a_zone", "b_zone_a_point"}:
            trigger_tags.append("星线蓄势")
        else:
            trigger_tags.append("星线平台待确认")
    if _long_upper_shadow(latest) and latest.volume > avg_volume20 * 1.8:
        risks.append("高位巨量长上影")
    return (8 if "星线蓄势" in trigger_tags else 4 if trigger_tags else 0), trigger_tags, risks


def _sector_score(industry_strength: IndustryStrength | None) -> int:
    if industry_strength == "strong":
        return 10
    if industry_strength == "weak":
        return 2
    return 5


def _action(total_score: int, zone: str, risk_flags: list[str], trigger_tags: list[str]) -> str:
    if "C区风险" in risk_flags or "高位巨量长上影" in risk_flags:
        return "avoid"
    if total_score >= 80 and zone in {"a_zone", "b_zone_a_point"}:
        return "strong_candidate"
    if total_score >= 65:
        return "watch_candidate"
    if trigger_tags:
        return "wait_trigger"
    return "avoid" if total_score < 45 else "wait_trigger"


def _risk_penalty(risk_flags: list[str]) -> int:
    penalty = 0
    if "C区风险" in risk_flags:
        penalty += 20
    if "高位巨量长上影" in risk_flags:
        penalty += 25
    return penalty


def _is_star(bar: KlineBar) -> bool:
    spread = bar.high - bar.low
    if spread <= 0:
        return False
    return abs(bar.close - bar.open) / spread <= 0.3


def _long_upper_shadow(bar: KlineBar) -> bool:
    spread = bar.high - bar.low
    if spread <= 0:
        return False
    upper = bar.high - max(bar.open, bar.close)
    return upper / spread > 0.45


def _higher_lows(bars: list[KlineBar]) -> bool:
    if len(bars) < 45:
        return False
    chunks = [bars[-60:-40], bars[-40:-20], bars[-20:]]
    lows = [min(bar.low for bar in chunk) for chunk in chunks if chunk]
    return len(lows) == 3 and lows[0] < lows[1] < lows[2]


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output
```

- [ ] **Step 4: Verify green**

Run: `cd apps/api && uv run pytest tests/test_gsgf_rules.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/gsgf_rules.py apps/api/tests/test_gsgf_rules.py
git commit -m "feat: add gsgf rule engine"
```

---

## Task 3: Integrate GSGF Into Existing Analysis

**Files:**
- Modify: `apps/api/app/rules.py`
- Test: `apps/api/tests/test_rules.py`

- [ ] **Step 1: Add failing integration tests**

Append to `apps/api/tests/test_rules.py`:

```python
def test_screening_item_includes_gsgf_analysis() -> None:
    candidate = StrongStockCandidate(
        symbol="603890.SH",
        name="春秋电子",
        industry="消费电子",
        limit_up_evidence=["20日内涨停"],
    )
    item = analyze_screening_item(candidate, _bars([10 + index * 0.05 for index in range(220)]), trade_date="2026-06-11")

    assert item.gsgf is not None
    assert item.gsgf.model_version == "gsgf-v1"
    assert item.gsgf.total_score > 0
    assert item.gsgf.zone in {"a_zone", "b_zone_a_point", "unformed"}


def test_watchlist_risk_includes_gsgf_without_changing_empty_rule() -> None:
    candidate = StrongStockCandidate(symbol="002000.SZ", name="示例股份")
    risk_item = analyze_watchlist_risk(candidate, _bars([20 - index * 0.05 for index in range(220)]), trade_date="2026-06-11")

    assert risk_item.risk_action == "empty"
    assert risk_item.gsgf is not None
    assert risk_item.gsgf.zone == "c_zone"
```

- [ ] **Step 2: Verify red**

Run: `cd apps/api && uv run pytest tests/test_rules.py::test_screening_item_includes_gsgf_analysis tests/test_rules.py::test_watchlist_risk_includes_gsgf_without_changing_empty_rule -q`

Expected: fail because `gsgf` is `None`.

- [ ] **Step 3: Implement integration**

In `apps/api/app/rules.py`, import:

```python
from app.gsgf_rules import analyze_gsgf
```

In `analyze_screening_item`, pass `gsgf=analyze_gsgf(bars)` in both complete and incomplete paths where possible. For the incomplete `<220` path, use `analyze_gsgf(bars)` so short-K explanations still exist.

In `analyze_watchlist_risk`, pass `gsgf=analyze_gsgf(bars)` for both short and normal branches.

- [ ] **Step 4: Verify green**

Run: `cd apps/api && uv run pytest tests/test_rules.py -q`

Expected: all rules tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/rules.py apps/api/tests/test_rules.py
git commit -m "feat: attach gsgf analysis to rule results"
```

---

## Task 4: Strategy Sorting and API Metadata

**Files:**
- Modify: `apps/api/app/services/screener.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_api.py`

- [ ] **Step 1: Add failing strategy API tests**

Append to `apps/api/tests/test_api.py`:

```python
def test_screen_run_accepts_gsgf_strategy_and_returns_metadata(tmp_path: Path) -> None:
    app.state.candidate_provider = FakeCandidateProvider()
    app.state.kline_provider = FakeKlineProvider()
    app.state.quote_provider = FakeQuoteProvider()
    app.state.news_risk_provider = FakeNewsRiskProvider()
    app.state.runs_dir = tmp_path / "runs"
    app.state.watchlist_path = tmp_path / "watchlist.txt"
    client = TestClient(app)

    response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 10, "strategy": "gsgf"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy"] == "gsgf"
    assert payload["gsgf_model_version"] == "gsgf-v1"
    assert payload["sort_version"] == "gsgf-sort-v1"
    assert payload["items"][0]["gsgf"]["total_score"] >= 0


def test_screen_run_accepts_combined_strategy(tmp_path: Path) -> None:
    app.state.candidate_provider = FakeCandidateProvider()
    app.state.kline_provider = FakeKlineProvider()
    app.state.quote_provider = FakeQuoteProvider()
    app.state.news_risk_provider = FakeNewsRiskProvider()
    app.state.runs_dir = tmp_path / "runs"
    app.state.watchlist_path = tmp_path / "watchlist.txt"
    client = TestClient(app)

    response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 10, "strategy": "combined"},
    )

    assert response.status_code == 200
    assert response.json()["strategy"] == "combined"
    assert response.json()["sort_version"] == "combined-sort-v1"
```

- [ ] **Step 2: Verify red**

Run: `cd apps/api && uv run pytest tests/test_api.py::test_screen_run_accepts_gsgf_strategy_and_returns_metadata tests/test_api.py::test_screen_run_accepts_combined_strategy -q`

Expected: fail because request model ignores or rejects strategy / result metadata remains strong defaults.

- [ ] **Step 3: Implement strategy request and sorting**

In `apps/api/app/main.py`, import `ScreenStrategy` and add fields to `ScreenRunRequest`:

```python
    strategy: ScreenStrategy = "strong_stock"
    include_gsgf: bool = True
    exclude_gsgf_hard_risk: bool = False
```

Pass to `screener.screen(...)`.

In `apps/api/app/services/screener.py`:

- Import `ScreenStrategy`.
- Add arguments to `screen`: `strategy: ScreenStrategy = "strong_stock"`, `exclude_gsgf_hard_risk: bool = False`.
- Filter hard risk if requested:

```python
if exclude_gsgf_hard_risk:
    items = [item for item in items if not _has_gsgf_hard_risk(item)]
```

- Sort with:

```python
ranked = sorted(items, key=lambda item: _screening_rank_key(item, strategy))[:limit]
```

- Return metadata:

```python
strategy=strategy,
gsgf_model_version="gsgf-v1",
sort_version=_sort_version(strategy),
```

Add helper signatures:

```python
def _screening_rank_key(item: StrongStockScreeningItem, strategy: ScreenStrategy = "strong_stock") -> tuple:
    if strategy == "gsgf":
        return _gsgf_rank_key(item)
    if strategy == "combined":
        return _combined_rank_key(item)
    return _strong_rank_key(item)
```

Keep existing ranking logic in `_strong_rank_key`.

- [ ] **Step 4: Verify green**

Run: `cd apps/api && uv run pytest tests/test_api.py -q`

Expected: API tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/main.py apps/api/app/services/screener.py apps/api/tests/test_api.py
git commit -m "feat: add gsgf screening strategies"
```

---

## Task 5: Watchlist GSGF Status API

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_api.py`

- [ ] **Step 1: Add failing watchlist endpoint test**

Append to `apps/api/tests/test_api.py`:

```python
def test_watchlist_gsgf_status_returns_structure_triggers(tmp_path: Path) -> None:
    app.state.kline_provider = FakeKlineProvider()
    app.state.watchlist_path = tmp_path / "watchlist.txt"
    app.state.watchlist_path.write_text("603890.SH 春秋电子 | group=观察 | industry=消费电子", encoding="utf-8")
    client = TestClient(app)

    response = client.get("/api/watchlist/gsgf-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["symbol"] == "603890.SH"
    assert payload["items"][0]["gsgf"]["model_version"] == "gsgf-v1"
```

- [ ] **Step 2: Verify red**

Run: `cd apps/api && uv run pytest tests/test_api.py::test_watchlist_gsgf_status_returns_structure_triggers -q`

Expected: fail with 404.

- [ ] **Step 3: Implement endpoint**

In `apps/api/app/main.py`, import `analyze_gsgf`.

Add:

```python
@app.get("/api/watchlist/gsgf-status")
def get_watchlist_gsgf_status() -> dict[str, object]:
    items = parse_watchlist_text(_read_watchlist_pool())
    output: list[dict[str, object]] = []
    for item in items:
        try:
            bars = _kline_provider().get_klines(item.symbol, count=220)
            gsgf = analyze_gsgf(bars)
            output.append({**item.model_dump(mode="json"), "gsgf": gsgf.model_dump(mode="json")})
        except Exception as exc:
            output.append(
                {
                    **item.model_dump(mode="json"),
                    "gsgf": {
                        "model_version": "gsgf-v1",
                        "total_score": 0,
                        "action": "wait_trigger",
                        "zone": "unknown",
                        "volume_structure": "unknown",
                        "scores": {},
                        "pattern_tags": [],
                        "trigger_tags": [],
                        "pressure_flags": [],
                        "risk_flags": [f"K线获取失败: {exc.__class__.__name__}"],
                        "explanation": [],
                    },
                }
            )
    return {"items": output}
```

Prefer constructing a real `GsgfAnalysis` fallback if model imports make that cleaner.

- [ ] **Step 4: Verify green**

Run: `cd apps/api && uv run pytest tests/test_api.py::test_watchlist_gsgf_status_returns_structure_triggers -q`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/main.py apps/api/tests/test_api.py
git commit -m "feat: add watchlist gsgf status api"
```

---

## Task 6: Frontend Types and API Wiring

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Test: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Add failing static wiring tests**

Append assertions to `apps/web/lib/strongStockWorkbench.test.ts`:

```ts
  assert.match(typesSource, /GsgfAnalysis/);
  assert.match(typesSource, /ScreenStrategy = "strong_stock" \\| "gsgf" \\| "combined"/);
  assert.match(apiSource, /strategy\\?: ScreenStrategy/);
  assert.match(apiSource, /getWatchlistGsgfStatus/);
```

- [ ] **Step 2: Verify red**

Run: `cd apps/web && corepack pnpm test`

Expected: fail on missing `GsgfAnalysis`.

- [ ] **Step 3: Implement types and API**

In `apps/web/lib/types.ts`, add:

```ts
export type ScreenStrategy = "strong_stock" | "gsgf" | "combined";

export type GsgfAction = "strong_candidate" | "watch_candidate" | "wait_trigger" | "avoid";
export type GsgfZone = "a_zone" | "b_zone_a_point" | "c_zone" | "unformed" | "unknown";
export type GsgfVolumeStructure =
  | "three_yang_controls_three_yin"
  | "neutral"
  | "three_yin_controls_three_yang"
  | "unknown";

export type GsgfAnalysis = {
  model_version: string;
  total_score: number;
  action: GsgfAction;
  zone: GsgfZone;
  volume_structure: GsgfVolumeStructure;
  scores: {
    safety_pressure: number;
    volume_thickness: number;
    ma_alignment: number;
    pattern_space: number;
    star_trigger: number;
    sector_theme: number;
  };
  pattern_tags: string[];
  trigger_tags: string[];
  pressure_flags: string[];
  risk_flags: string[];
  explanation: string[];
};
```

Add `gsgf?: GsgfAnalysis | null` to screening and watchlist risk item types. Add `strategy`, `gsgf_model_version`, `strong_model_version`, `sort_version` to screening response.

In `apps/web/lib/api.ts`, update run request type:

```ts
strategy?: ScreenStrategy;
include_gsgf?: boolean;
exclude_gsgf_hard_risk?: boolean;
```

Add:

```ts
export async function getWatchlistGsgfStatus(): Promise<{ items: Array<WatchlistPoolItem & { gsgf: GsgfAnalysis }> }> {
  return request("/api/watchlist/gsgf-status");
}
```

- [ ] **Step 4: Verify green**

Run: `cd apps/web && corepack pnpm test`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/types.ts apps/web/lib/api.ts apps/web/lib/strongStockWorkbench.test.ts
git commit -m "feat: wire gsgf frontend api types"
```

---

## Task 7: Homepage Strategy UI and Result Display

**Files:**
- Modify: `apps/web/components/ScreenerWorkbench.tsx`
- Test: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Add failing UI static tests**

Append assertions:

```ts
  assert.match(componentSource, /strategy/);
  assert.match(componentSource, /股是股非模型/);
  assert.match(componentSource, /综合模型/);
  assert.match(componentSource, /股是股非结构/);
  assert.match(componentSource, /gsgfLabel/);
```

- [ ] **Step 2: Verify red**

Run: `cd apps/web && corepack pnpm test`

Expected: fail on missing UI strings/helpers.

- [ ] **Step 3: Implement UI**

In `ScreenerWorkbench.tsx`:

- Add `const [strategy, setStrategy] = useState<ScreenStrategy>("combined");`
- Include `strategy` in API call payload.
- Add compact segmented buttons in filter area for 强势股模型 / 股是股非模型 / 综合模型.
- In candidate row/card, show `item.gsgf?.total_score`, `gsgfZoneLabel(item.gsgf?.zone)`, and first 2 tags from `pattern_tags`/`trigger_tags`.
- In detail panel, add section title `股是股非结构` with score breakdown and risk flags.
- Add helpers:

```ts
function gsgfLabel(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    strong_candidate: "强势候选",
    watch_candidate: "观察候选",
    wait_trigger: "等触发",
    avoid: "回避",
    a_zone: "A区",
    b_zone_a_point: "B区A点",
    c_zone: "C区",
    unformed: "未成型",
    unknown: "未知",
    three_yang_controls_three_yin: "三阳控三阴",
    neutral: "量形态中性",
    three_yin_controls_three_yang: "三阴控三阳",
  };
  return value ? labels[value] ?? value : "--";
}
```

- [ ] **Step 4: Verify green**

Run: `cd apps/web && corepack pnpm test`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/ScreenerWorkbench.tsx apps/web/lib/strongStockWorkbench.test.ts
git commit -m "feat: show gsgf strategy in screener ui"
```

---

## Task 8: Watchlist Structure Trigger UI

**Files:**
- Modify: `apps/web/app/watchlist/page.tsx`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Add failing UI tests**

Append assertions:

```ts
  assert.match(watchlistPageSource, /getWatchlistGsgfStatus/);
  assert.match(watchlistPageSource, /结构触发/);
  assert.match(watchlistPageSource, /机会触发/);
  assert.match(watchlistPageSource, /C区\\/回避/);
```

- [ ] **Step 2: Verify red**

Run: `cd apps/web && corepack pnpm test`

Expected: fail on missing watchlist strings/API.

- [ ] **Step 3: Implement watchlist status**

In `watchlist/page.tsx`:

- Import `getWatchlistGsgfStatus` and `GsgfAnalysis`.
- Add state:

```ts
const [gsgfBySymbol, setGsgfBySymbol] = useState<Record<string, GsgfAnalysis>>({});
const [structureFilter, setStructureFilter] = useState<"all" | "opportunity" | "wait" | "risk" | "avoid">("all");
```

- After loading watchlist, call `getWatchlistGsgfStatus()` and map by symbol.
- Add filter chips 全部 / 机会触发 / 等确认 / 风险预警 / C区/回避.
- Add table/card column `结构触发`; show zone/action score and first tags/risks.
- Filter display:
  - opportunity: action strong/watch and no risk flags.
  - wait: action wait_trigger.
  - risk: risk flags exist.
  - avoid: action avoid or zone c_zone.

- [ ] **Step 4: Verify green**

Run: `cd apps/web && corepack pnpm test`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web/app/watchlist/page.tsx apps/web/lib/strongStockWorkbench.test.ts
git commit -m "feat: add watchlist gsgf triggers"
```

---

## Task 9: Full Verification and Push

**Files:**
- All touched files.

- [ ] **Step 1: Run backend tests**

Run: `cd apps/api && uv run pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run frontend tests**

Run: `cd apps/web && corepack pnpm test`

Expected: all tests pass.

- [ ] **Step 3: Run frontend build**

Run: `cd apps/web && corepack pnpm build`

Expected: build passes.

- [ ] **Step 4: Inspect git status**

Run: `git status --short --branch`

Expected: clean except intentional local ignored files.

- [ ] **Step 5: Push**

```bash
git push origin main
```

Expected: GitHub `main` includes design and implementation commits.

