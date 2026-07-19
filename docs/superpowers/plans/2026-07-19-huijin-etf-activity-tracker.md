# Huijin ETF Activity Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the generic ETF capital score with a source-transparent Huijin ETF activity tracker based on seven core ETFs, three cross-validation ETFs, disclosed holding baselines, and official daily share changes.

**Architecture:** Keep official exchange access and persistence in the FastAPI backend. Add a pure calculation module for public-rule metrics and cross-validation, version the disclosed baseline separately from daily share history, and extend the existing `/api/etf-radar/*` contracts without adding a second request stack. Refocus the Vue workspace and homepage on confirmed holdings, daily share activity, conservative pair validation, and explicit source state.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx, pytest, Vue 3, TypeScript, Vite, Vitest, Ant Design Vue, ECharts.

---

## File Map

- `apps/api/app/models.py`: add baseline, daily activity, validation-group, summary, history, and holder response fields.
- `apps/api/app/services/huijin_etf_activity.py`: own the versioned ten-ETF universe and all pure public-rule calculations.
- `apps/api/app/services/capital_signal_store.py`: persist versioned Huijin baselines alongside existing share history and snapshots.
- `apps/api/app/services/capital_signal_sampler.py`: archive all ten ETF share snapshots after exchange disclosure without requiring a page visit.
- `apps/api/app/providers/capital_signals.py`: preserve the exchange-reported SZSE date and reject mismatched historical requests.
- `apps/api/app/services/capital_signals.py`: orchestrate baselines, ten-ETF share collection, daily activity, cross-validation, history, holders, methodology, and homepage projection.
- `apps/api/app/main.py`: keep the five existing routes and cache boundary; no new route family.
- `apps/api/tests/test_huijin_etf_activity.py`: public formulas, universe, pair validation, and 2026-07-17 regression fixtures.
- `apps/api/tests/test_capital_signal_store.py`: baseline round-trip, corrupt-file fallback, and version replacement.
- `apps/api/tests/test_capital_signal_providers.py`: actual-date parsing and no fabricated SZSE history.
- `apps/api/tests/test_capital_signals.py`: service orchestration, partial coverage, stale fallback, baseline refresh, and homepage projection.
- `apps/api/tests/test_capital_signal_sampler.py`: post-close window, retry, once-per-day completion, and shutdown behavior.
- `apps/api/tests/test_api.py`: response schema and route compatibility.
- `apps/web-vue/src/service/types.ts`: mirror the upgraded FastAPI contracts.
- `apps/web-vue/src/utils/domain/capitalSignals.ts`: format activity direction, multiples, validation state, shares, and percentages.
- `apps/web-vue/src/utils/domain/capitalSignals.test.ts`: formatting and semantic-state tests.
- `apps/web-vue/src/views/EtfRadarView.vue`: render today, cumulative history, confirmed holdings, and methodology views.
- `apps/web-vue/src/views/EtfRadarView.test.ts`: lazy loading, new table contract, pair validation, stale state, and removed generic score labels.
- `apps/web-vue/src/views/HomeView.vue`: replace the generic evidence card with a compact Huijin ETF activity summary.
- `apps/web-vue/src/views/HomeView.test.ts`: homepage wording, values, navigation, and loading/error behavior.

### Task 1: Public-Rule Domain Models and Pure Calculations

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/services/huijin_etf_activity.py`
- Create: `apps/api/tests/test_huijin_etf_activity.py`

- [ ] **Step 1: Write failing universe and formula tests**

Create `apps/api/tests/test_huijin_etf_activity.py` with these fixtures and assertions:

```python
import pytest

from app.models import HuijinEtfBaseline
from app.services.huijin_etf_activity import (
    CORE_ETFS,
    VALIDATION_ETFS,
    calculate_activity,
)


def baseline(symbol: str, total_shares: float) -> HuijinEtfBaseline:
    return HuijinEtfBaseline(
        baseline_id=f"2025-12-31:{symbol}",
        pool_version="huijin-public-v1",
        symbol=symbol,
        name=symbol,
        index_name="测试指数",
        role="core",
        report_period="2025-12-31",
        baseline_total_shares=total_shares,
        confirmed_huijin_shares=total_shares * 0.8,
        confirmed_huijin_holding_pct=80,
        source_kind="derived",
        source="fixture",
    )


def test_public_universe_contains_exact_core_and_validation_symbols() -> None:
    assert set(CORE_ETFS) == {
        "510050.SH", "510300.SH", "510500.SH", "512100.SH",
        "159915.SZ", "510230.SH", "588080.SH",
    }
    assert set(VALIDATION_ETFS) == {"159919.SZ", "159922.SZ", "159845.SZ"}


def test_public_formula_reproduces_2026_07_17_chinext_example() -> None:
    result = calculate_activity(
        symbol="159915.SZ",
        name="创业板ETF易方达",
        index_name="创业板",
        role="core",
        trade_date="2026-07-17",
        total_shares=14_916_000_000,
        previous_total_shares=13_020_000_000,
        baseline=baseline("159915.SZ", 31_500_000_000),
    )

    assert result.share_delta == 1_896_000_000
    assert result.daily_change_pct == pytest.approx(14.5622, rel=1e-4)
    assert result.baseline_change_pct == pytest.approx(6.0190, rel=1e-4)
    assert result.multiple == pytest.approx(60.1904, rel=1e-4)
    assert result.direction == "increase"
    assert result.is_tenfold is True


def test_missing_previous_day_keeps_daily_metrics_missing() -> None:
    result = calculate_activity(
        symbol="159915.SZ",
        name="创业板ETF易方达",
        index_name="创业板",
        role="core",
        trade_date="2026-07-17",
        total_shares=14_916_000_000,
        previous_total_shares=None,
        baseline=baseline("159915.SZ", 31_500_000_000),
    )

    assert result.share_delta is None
    assert result.daily_change_pct is None
    assert result.baseline_change_pct is None
    assert result.multiple is None
    assert result.direction == "unknown"
```

- [ ] **Step 2: Run formula tests and verify RED**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_huijin_etf_activity.py -q
```

Expected: collection fails because the Huijin models and calculation module do not exist.

- [ ] **Step 3: Add Pydantic contracts**

Add these contracts beside the existing ETF radar models in `apps/api/app/models.py`:

```python
HuijinEtfRole = Literal["core", "validator"]
EtfActivityDirection = Literal["increase", "decrease", "flat", "unknown"]
EtfValidationState = Literal[
    "confirmed_increase", "confirmed_decrease", "divergent", "incomplete"
]
HuijinBaselineSourceKind = Literal["reported", "derived"]


class HuijinEtfBaseline(BaseModel):
    baseline_id: str
    pool_version: str
    symbol: str
    name: str
    index_name: str
    role: HuijinEtfRole
    paired_symbol: str | None = None
    report_period: str
    baseline_total_shares: float = Field(gt=0)
    confirmed_huijin_shares: float = Field(ge=0)
    confirmed_huijin_holding_pct: float = Field(ge=0, le=100)
    source_kind: HuijinBaselineSourceKind
    source: str


class HuijinEtfActivityItem(BaseModel):
    symbol: str
    name: str
    index_name: str
    role: HuijinEtfRole
    paired_symbol: str | None = None
    trade_date: str
    total_shares: float | None = None
    previous_total_shares: float | None = None
    share_delta: float | None = None
    daily_change_pct: float | None = None
    baseline_change_pct: float | None = None
    cumulative_baseline_change_pct: float | None = None
    multiple: float | None = None
    direction: EtfActivityDirection = "unknown"
    is_tenfold: bool = False
    report_period: str | None = None
    confirmed_huijin_holding_pct: float | None = None
    baseline_source_kind: HuijinBaselineSourceKind | None = None


class HuijinEtfValidationGroup(BaseModel):
    index_name: str
    core_symbol: str
    validator_symbol: str
    state: EtfValidationState
    conservative_daily_change_pct: float | None = None
    conservative_baseline_change_pct: float | None = None
    conservative_multiple: float | None = None


class HuijinEtfActivitySummary(BaseModel):
    core_count: int = 7
    available_core_count: int = 0
    tenfold_increase_count: int = 0
    tenfold_decrease_count: int = 0
    confirmed_increase_group_count: int = 0
    confirmed_decrease_group_count: int = 0
    divergent_group_count: int = 0
    incomplete_group_count: int = 0
    strongest_symbol: str | None = None
    strongest_baseline_change_pct: float | None = None
```

- [ ] **Step 4: Implement the exact universe and calculations**

Create `apps/api/app/services/huijin_etf_activity.py` with immutable definitions and pure functions:

```python
from __future__ import annotations

from dataclasses import dataclass

from app.models import (
    HuijinEtfActivityItem,
    HuijinEtfBaseline,
    HuijinEtfValidationGroup,
)

POOL_VERSION = "huijin-public-v1"
MODEL_VERSION = "huijin-public-rule-v1"
TENFOLD_BASELINE_PCT = 0.1


@dataclass(frozen=True)
class EtfDefinition:
    name: str
    index_name: str
    role: str
    paired_symbol: str | None = None


CORE_ETFS = {
    "510050.SH": EtfDefinition("上证50ETF华夏", "上证50", "core"),
    "510300.SH": EtfDefinition("沪深300ETF华泰柏瑞", "沪深300", "core", "159919.SZ"),
    "510500.SH": EtfDefinition("中证500ETF南方", "中证500", "core", "159922.SZ"),
    "512100.SH": EtfDefinition("中证1000ETF南方", "中证1000", "core", "159845.SZ"),
    "159915.SZ": EtfDefinition("创业板ETF易方达", "创业板", "core"),
    "510230.SH": EtfDefinition("金融ETF国泰", "金融", "core"),
    "588080.SH": EtfDefinition("科创50ETF易方达", "科创50", "core"),
}
VALIDATION_ETFS = {
    "159919.SZ": EtfDefinition("沪深300ETF嘉实", "沪深300", "validator", "510300.SH"),
    "159922.SZ": EtfDefinition("中证500ETF嘉实", "中证500", "validator", "510500.SH"),
    "159845.SZ": EtfDefinition("中证1000ETF华夏", "中证1000", "validator", "512100.SH"),
}
ALL_ETFS = {**CORE_ETFS, **VALIDATION_ETFS}


def calculate_activity(
    *, symbol: str, name: str, index_name: str, role: str, trade_date: str,
    total_shares: float | None, previous_total_shares: float | None,
    baseline: HuijinEtfBaseline | None,
) -> HuijinEtfActivityItem:
    if total_shares is None or previous_total_shares is None or previous_total_shares <= 0:
        delta = daily_pct = baseline_pct = multiple = None
        direction = "unknown"
    else:
        delta = total_shares - previous_total_shares
        daily_pct = delta / previous_total_shares * 100
        baseline_pct = (
            delta / baseline.baseline_total_shares * 100 if baseline is not None else None
        )
        multiple = abs(baseline_pct) / TENFOLD_BASELINE_PCT if baseline_pct is not None else None
        direction = "increase" if delta > 0 else "decrease" if delta < 0 else "flat"
    cumulative = (
        (total_shares - baseline.baseline_total_shares) / baseline.baseline_total_shares * 100
        if total_shares is not None and baseline is not None
        else None
    )
    definition = ALL_ETFS.get(symbol)
    return HuijinEtfActivityItem(
        symbol=symbol,
        name=name,
        index_name=index_name,
        role=role,
        paired_symbol=definition.paired_symbol if definition else None,
        trade_date=trade_date,
        total_shares=total_shares,
        previous_total_shares=previous_total_shares,
        share_delta=delta,
        daily_change_pct=daily_pct,
        baseline_change_pct=baseline_pct,
        cumulative_baseline_change_pct=cumulative,
        multiple=multiple,
        direction=direction,
        is_tenfold=multiple is not None and multiple >= 10,
        report_period=baseline.report_period if baseline else None,
        confirmed_huijin_holding_pct=(baseline.confirmed_huijin_holding_pct if baseline else None),
        baseline_source_kind=baseline.source_kind if baseline else None,
    )
```

- [ ] **Step 5: Add pair-validation tests and implementation**

Add tests for both-positive, both-negative, divergent, and incomplete states. Implement `validate_pair` so same-direction results select the value with the smaller absolute magnitude and divergent pairs return no conservative metrics:

```python
def validate_pair(
    core: HuijinEtfActivityItem,
    validator: HuijinEtfActivityItem,
) -> HuijinEtfValidationGroup:
    directions = {core.direction, validator.direction}
    if "unknown" in directions:
        state = "incomplete"
    elif directions == {"increase"}:
        state = "confirmed_increase"
    elif directions == {"decrease"}:
        state = "confirmed_decrease"
    else:
        state = "divergent"
    if state not in {"confirmed_increase", "confirmed_decrease"}:
        return HuijinEtfValidationGroup(
            index_name=core.index_name,
            core_symbol=core.symbol,
            validator_symbol=validator.symbol,
            state=state,
        )
    choose = lambda left, right: min((left, right), key=abs) if left is not None and right is not None else None
    return HuijinEtfValidationGroup(
        index_name=core.index_name,
        core_symbol=core.symbol,
        validator_symbol=validator.symbol,
        state=state,
        conservative_daily_change_pct=choose(core.daily_change_pct, validator.daily_change_pct),
        conservative_baseline_change_pct=choose(core.baseline_change_pct, validator.baseline_change_pct),
        conservative_multiple=(
            min(core.multiple, validator.multiple)
            if core.multiple is not None and validator.multiple is not None
            else None
        ),
    )
```

- [ ] **Step 6: Run tests, Ruff, and commit**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_huijin_etf_activity.py -q
.venv/bin/ruff check app/models.py app/services/huijin_etf_activity.py tests/test_huijin_etf_activity.py
git add app/models.py app/services/huijin_etf_activity.py tests/test_huijin_etf_activity.py
git commit -m "feat: add Huijin ETF public-rule domain"
```

Expected: all new tests pass and Ruff reports no errors.

### Task 2: Versioned Disclosed-Holding Baselines

**Files:**
- Modify: `apps/api/app/services/huijin_etf_activity.py`
- Modify: `apps/api/app/services/capital_signal_store.py`
- Modify: `apps/api/tests/test_huijin_etf_activity.py`
- Modify: `apps/api/tests/test_capital_signal_store.py`

- [ ] **Step 1: Write failing baseline derivation tests**

Add a fixture with both Huijin entities and assert that shares and percentages are summed before deriving total ETF shares:

```python
from app.models import EtfHolderPosition
from app.services.huijin_etf_activity import build_baselines


def test_baseline_derivation_sums_exact_huijin_entities() -> None:
    positions = [
        EtfHolderPosition(
            symbol="510300.SH", name="沪深300ETF华泰柏瑞", report_period="2025-12-31",
            entity_name="中央汇金资产管理有限责任公司", shares=37_858_500_000,
            holding_pct=42.62, source="fixture",
        ),
        EtfHolderPosition(
            symbol="510300.SH", name="沪深300ETF华泰柏瑞", report_period="2025-12-31",
            entity_name="中央汇金投资有限责任公司", shares=35_654_600_000,
            holding_pct=40.14, source="fixture",
        ),
    ]

    baseline = build_baselines(positions)[0]

    assert baseline.confirmed_huijin_shares == 73_513_100_000
    assert baseline.confirmed_huijin_holding_pct == pytest.approx(82.76)
    assert baseline.baseline_total_shares == pytest.approx(88_826_848_719, rel=1e-6)
    assert baseline.source_kind == "derived"
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `cd apps/api && .venv/bin/pytest tests/test_huijin_etf_activity.py -k baseline -q`

Expected: failure because `build_baselines` is absent.

- [ ] **Step 3: Implement deterministic baseline building**

Group positions by `(report_period, symbol)`, reject entities outside the existing exact provider whitelist by consuming only provider-filtered rows, require positive summed shares and percentage, and return baselines in universe order:

```python
def build_baselines(positions: list[EtfHolderPosition]) -> list[HuijinEtfBaseline]:
    grouped: dict[tuple[str, str], list[EtfHolderPosition]] = {}
    for position in positions:
        if position.symbol in ALL_ETFS:
            grouped.setdefault((position.report_period, position.symbol), []).append(position)
    output: list[HuijinEtfBaseline] = []
    for (period, symbol), rows in grouped.items():
        shares = sum(row.shares for row in rows if row.shares is not None)
        pct = sum(row.holding_pct for row in rows if row.holding_pct is not None)
        if shares <= 0 or pct <= 0:
            continue
        definition = ALL_ETFS[symbol]
        output.append(HuijinEtfBaseline(
            baseline_id=f"{period}:{POOL_VERSION}:{symbol}",
            pool_version=POOL_VERSION,
            symbol=symbol,
            name=definition.name,
            index_name=definition.index_name,
            role=definition.role,
            paired_symbol=definition.paired_symbol,
            report_period=period,
            baseline_total_shares=shares / (pct / 100),
            confirmed_huijin_shares=shares,
            confirmed_huijin_holding_pct=pct,
            source_kind="derived",
            source="基金持有人披露持仓与比例推导",
        ))
    return sorted(output, key=lambda item: list(ALL_ETFS).index(item.symbol))
```

- [ ] **Step 4: Write failing store tests**

Extend `apps/api/tests/test_capital_signal_store.py` to assert:

```python
def test_huijin_baseline_round_trip_and_corrupt_fallback(tmp_path: Path) -> None:
    store = CapitalSignalStore(tmp_path)
    rows = [baseline_fixture("510300.SH")]
    store.save_huijin_baselines(rows)
    assert store.load_huijin_baselines() == rows

    store.huijin_baselines_path.write_text("not-json", encoding="utf-8")
    assert store.load_huijin_baselines() == []
```

- [ ] **Step 5: Add atomic baseline persistence**

Add a `TypeAdapter(list[HuijinEtfBaseline])`, the path `huijin-etf-baselines.json`, and typed load/save methods using the existing `_write_bytes` atomic replacement helper. `save_huijin_baselines` replaces the full versioned snapshot; it does not append duplicate baseline IDs.

- [ ] **Step 6: Run tests and commit**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py -q
.venv/bin/ruff check app/services/huijin_etf_activity.py app/services/capital_signal_store.py tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py
git add app/services/huijin_etf_activity.py app/services/capital_signal_store.py tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py
git commit -m "feat: persist Huijin ETF baselines"
```

Expected: all selected tests pass.

### Task 3: Honest Exchange Dates and Ten-ETF Collection

**Files:**
- Modify: `apps/api/app/providers/capital_signals.py`
- Modify: `apps/api/tests/test_capital_signal_providers.py`

- [ ] **Step 1: Write failing SZSE date tests**

Add tests proving the payload date wins and mismatched historical requests return no rows:

```python
def test_szse_share_parser_rejects_payload_from_another_trade_date() -> None:
    rows = parse_szse_etf_share_payload(
        SZSE_SHARE_FIXTURE,
        trade_date="2026-07-16",
        symbols=["159915.SZ"],
    )
    assert rows == []


def test_szse_share_parser_uses_metadata_trade_date() -> None:
    rows = parse_szse_etf_share_payload(
        SZSE_SHARE_FIXTURE,
        trade_date="2026-07-17",
        symbols=["159915.SZ"],
    )
    assert rows[0].trade_date == "2026-07-17"
```

- [ ] **Step 2: Run provider tests and verify RED**

Run: `cd apps/api && .venv/bin/pytest tests/test_capital_signal_providers.py -k szse_share -q`

Expected: the mismatched-date test fails because the parser currently stamps the requested date onto current data.

- [ ] **Step 3: Parse the actual exchange date**

Read `metadata.subname` from the first SZSE section, normalize it with `_date_text`, and return no rows when it differs from the requested trade date:

```python
section = _first_section(payload)
metadata = section.get("metadata") if isinstance(section, dict) else None
payload_date = _date_text(metadata.get("subname")) if isinstance(metadata, dict) else None
if payload_date is None or payload_date != trade_date:
    return []
```

Use `payload_date` in every returned `EtfSharePoint`; never fall back to the requested date.

- [ ] **Step 4: Add a provider request regression for the ten-symbol split**

Assert that one service request containing the ten-symbol universe sends six Shanghai codes through the SSE request and four Shenzhen codes through individual SZSE requests. The test must inspect requested `SEC_CODE`/query keys and source statuses; it must not make live network calls.

- [ ] **Step 5: Run tests, Ruff, and commit**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_capital_signal_providers.py -q
.venv/bin/ruff check app/providers/capital_signals.py tests/test_capital_signal_providers.py
git add app/providers/capital_signals.py tests/test_capital_signal_providers.py
git commit -m "fix: preserve official ETF share dates"
```

Expected: provider tests pass and no fabricated prior-day SZSE row is produced.

### Task 4: Service Orchestration and API Compatibility

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/services/capital_signals.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_capital_signals.py`
- Modify: `apps/api/tests/test_api.py`

- [ ] **Step 1: Extend response contracts with additive fields**

Add these fields while retaining the existing optional fields for one compatibility release:

```python
class EtfRadarSummary(BaseModel):
    # existing compatibility fields remain
    activity: HuijinEtfActivitySummary = Field(default_factory=HuijinEtfActivitySummary)


class EtfRadarOverviewResponse(CapitalSignalMetadata):
    # existing compatibility fields remain
    pool_version: str = "huijin-public-v1"
    baseline_version: str | None = None
    activity: HuijinEtfActivitySummary = Field(default_factory=HuijinEtfActivitySummary)
    core_items: list[HuijinEtfActivityItem] = Field(default_factory=list)
    validation_items: list[HuijinEtfActivityItem] = Field(default_factory=list)
    validation_groups: list[HuijinEtfValidationGroup] = Field(default_factory=list)


class EtfRadarHistoryPoint(BaseModel):
    # existing fields remain
    daily_change_pct: float | None = None
    baseline_change_pct: float | None = None
    cumulative_baseline_change_pct: float | None = None
    multiple: float | None = None


class EtfRadarHoldersResponse(CapitalSignalMetadata):
    positions: list[EtfHolderPosition] = Field(default_factory=list)
    baselines: list[HuijinEtfBaseline] = Field(default_factory=list)
```

- [ ] **Step 2: Write failing service tests**

Update fake share and holder providers to cover all ten symbols. Add assertions that:

```python
snapshot = service.overview(force=True)
assert snapshot.pool_version == "huijin-public-v1"
assert len(snapshot.core_items) == 7
assert len(snapshot.validation_items) == 3
assert {group.index_name for group in snapshot.validation_groups} == {
    "沪深300", "中证500", "中证1000"
}
assert snapshot.activity.core_count == 7
assert snapshot.baseline_version == "2025-12-31:huijin-public-v1"
```

Add separate tests for missing validator history, stale baseline cache, and a current report-period cache that covers only the old ETF pool. The old partial baseline must trigger a refresh rather than being accepted as complete.

- [ ] **Step 3: Run service tests and verify RED**

Run: `cd apps/api && .venv/bin/pytest tests/test_capital_signals.py -q`

Expected: failures for absent Huijin fields, wrong universe, and incomplete baseline coverage.

- [ ] **Step 4: Replace the generic overview calculation**

In `CapitalSignalService.overview`:

1. Load or refresh baselines for all ten symbols using `holder_provider` and `build_baselines`.
2. Request current shares for `list(ALL_ETFS)`.
3. Merge same-day partial exchange results with same-day persisted rows.
4. Load each symbol's latest real prior-day row from history.
5. Call `calculate_activity` for every available definition.
6. Keep seven rows in `core_items`, three rows in `validation_items`, and call `validate_pair` for the three configured pairs.
7. Build `HuijinEtfActivitySummary` from core and group states.
8. Persist raw share history and the additive response snapshot.

The summary builder must count only non-null core rows. It must select `strongest_symbol` by the largest absolute `baseline_change_pct`; it must not add share deltas across ETFs.

Populate the legacy `items` field from the seven core rows for one compatibility release: map `share_delta` to `share_change`, retain `total_shares`, and leave the removed score fields `null`. Populate legacy coverage counts from the same seven rows; do not run the old generic score calculation in parallel.

- [ ] **Step 5: Upgrade history, holders, methodology, and homepage projection**

- `history`: calculate the new percentages from persisted raw share rows and the matching report baseline; return only real dates.
- `holders`: return exact positions plus the versioned baseline rows.
- `methodology`: publish the four formulas, `TENFOLD_BASELINE_PCT`, exact ten-symbol pool, cross-validation rules, the limitation that activity does not identify a buyer, and the explicit statement that the paid “7 月 6 日新规” is not implemented.
- `homepage_summary`: project only counts, strongest core ETF, trade date, and source coverage into `etf_radar.activity`; do not fetch history or methodology.

Keep `MODEL_VERSION = "huijin-public-rule-v1"` in all upgraded responses.

- [ ] **Step 6: Write API schema tests**

Extend the injected fake service in `apps/api/tests/test_api.py` and assert `/api/etf-radar/overview` includes:

```python
payload = client.get("/api/etf-radar/overview").json()
assert payload["pool_version"] == "huijin-public-v1"
assert "core_items" in payload
assert "validation_groups" in payload
assert payload["model_version"] == "huijin-public-rule-v1"
```

Assert the five route paths and `days=1..365` validation remain unchanged.

- [ ] **Step 7: Run backend gates and commit**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py tests/test_capital_signal_providers.py tests/test_capital_signals.py -q
.venv/bin/pytest tests/test_api.py -k 'capital or etf_radar' -q
.venv/bin/ruff check app/models.py app/services/huijin_etf_activity.py app/services/capital_signal_store.py app/services/capital_signals.py app/providers/capital_signals.py app/main.py tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py tests/test_capital_signal_providers.py tests/test_capital_signals.py tests/test_api.py
git add app/models.py app/services/capital_signals.py app/main.py tests/test_capital_signals.py tests/test_api.py
git commit -m "feat: expose Huijin ETF activity API"
```

Expected: selected tests pass and Ruff reports no errors.

### Task 5: Post-Close Daily Share Sampler

**Files:**
- Create: `apps/api/app/services/capital_signal_sampler.py`
- Create: `apps/api/tests/test_capital_signal_sampler.py`
- Modify: `apps/api/app/main.py`

- [ ] **Step 1: Write failing sampler-window and retry tests**

Create `apps/api/tests/test_capital_signal_sampler.py`:

```python
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.services.capital_signal_sampler import (
    CapitalSignalSampler,
    is_capital_signal_refresh_window,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")


def at(hour: int, minute: int) -> datetime:
    return datetime(2026, 7, 20, hour, minute, tzinfo=SHANGHAI)


def test_refresh_window_starts_after_exchange_disclosure_time() -> None:
    assert is_capital_signal_refresh_window(at(19, 4)) is False
    assert is_capital_signal_refresh_window(at(19, 5)) is True
    assert is_capital_signal_refresh_window(at(23, 30)) is True
    assert is_capital_signal_refresh_window(at(23, 31)) is False


def test_sampler_retries_partial_snapshot_and_stops_after_complete_snapshot() -> None:
    responses = iter([
        SimpleNamespace(trade_date="2026-07-20", core_items=[1] * 6, validation_items=[1] * 4),
        SimpleNamespace(trade_date="2026-07-20", core_items=[1] * 7, validation_items=[1] * 3),
    ])
    calls = 0

    def refresh():
        nonlocal calls
        calls += 1
        return next(responses)

    sampler = CapitalSignalSampler(refresh=refresh, clock=lambda: at(19, 10))
    assert sampler.sample_once() is False
    assert sampler.sample_once() is True
    assert sampler.sample_once() is False
    assert calls == 2
```

- [ ] **Step 2: Run sampler tests and verify RED**

Run: `cd apps/api && .venv/bin/pytest tests/test_capital_signal_sampler.py -q`

Expected: collection fails because the sampler module does not exist.

- [ ] **Step 3: Implement the bounded daemon sampler**

Create a daemon-thread sampler following the existing `SectorWorkbenchSampler` lifecycle pattern:

```python
from __future__ import annotations

from datetime import datetime
from threading import Event, Thread
from typing import Callable
from zoneinfo import ZoneInfo


def is_capital_signal_refresh_window(now: datetime | None = None) -> bool:
    current = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    if current.weekday() >= 5:
        return False
    minutes = current.hour * 60 + current.minute
    return 19 * 60 + 5 <= minutes <= 23 * 60 + 30


class CapitalSignalSampler:
    def __init__(
        self,
        *, refresh: Callable[[], object], clock: Callable[[], datetime] | None = None,
        retry_seconds: float = 900, idle_seconds: float = 1800,
    ) -> None:
        self._refresh = refresh
        self._clock = clock or (lambda: datetime.now(ZoneInfo("Asia/Shanghai")))
        self._retry_seconds = retry_seconds
        self._idle_seconds = idle_seconds
        self._completed_date: str | None = None
        self._stop_event = Event()
        self._thread: Thread | None = None

    def sample_once(self) -> bool:
        now = self._clock()
        trade_date = now.date().isoformat()
        if not is_capital_signal_refresh_window(now) or self._completed_date == trade_date:
            return False
        snapshot = self._refresh()
        complete = (
            getattr(snapshot, "trade_date", None) == trade_date
            and len(getattr(snapshot, "core_items", [])) == 7
            and len(getattr(snapshot, "validation_items", [])) == 3
        )
        if complete:
            self._completed_date = trade_date
        return complete

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, name="capital-signal-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                complete = self.sample_once()
            except Exception:
                complete = False
            self._stop_event.wait(self._idle_seconds if complete else self._retry_seconds)
```

- [ ] **Step 4: Wire startup and shutdown without blocking lifespan**

Add `startup_capital_signal_sampler` and `shutdown_capital_signal_sampler` beside the existing sampler lifecycle functions in `main.py`. The refresh callback must be `lambda: _capital_signal_service().overview(force=True)`. Start it in lifespan after the existing sector sampler and stop it first during shutdown.

Tests must inject a fake sampler through `app.state.capital_signal_sampler`; startup must be idempotent and shutdown must not construct the default service when no sampler started.

- [ ] **Step 5: Run tests, Ruff, and commit**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_capital_signal_sampler.py tests/test_start_script.py -q
.venv/bin/ruff check app/services/capital_signal_sampler.py app/main.py tests/test_capital_signal_sampler.py
git add app/services/capital_signal_sampler.py app/main.py tests/test_capital_signal_sampler.py
git commit -m "feat: archive Huijin ETF shares daily"
```

Expected: sampler tests pass, startup remains non-blocking, and Ruff reports no errors.

### Task 6: Vue Contracts and Domain Formatting

**Files:**
- Modify: `apps/web-vue/src/service/types.ts`
- Modify: `apps/web-vue/src/utils/domain/capitalSignals.ts`
- Modify: `apps/web-vue/src/utils/domain/capitalSignals.test.ts`
- Modify: `apps/web-vue/src/service/api.test.ts`

- [ ] **Step 1: Write failing formatter tests**

Add tests:

```typescript
expect(formatActivityMultiple(60.19)).toBe('60.2倍');
expect(formatActivityMultiple(null)).toBe('--');
expect(activityDirectionLabel('increase')).toBe('申购');
expect(activityDirectionLabel('decrease')).toBe('赎回');
expect(validationStateLabel('confirmed_increase')).toBe('确认增加');
expect(validationStateLabel('divergent')).toBe('方向分歧');
expect(validationStateTone('confirmed_decrease')).toBe('fall');
expect(validationStateTone('incomplete')).toBe('neutral');
```

- [ ] **Step 2: Run formatter tests and verify RED**

Run: `cd apps/web-vue && corepack pnpm@9.15.0 test:unit --run src/utils/domain/capitalSignals.test.ts`

Expected: failures because the new helpers and types are absent.

- [ ] **Step 3: Mirror backend contracts**

Add TypeScript unions and interfaces matching the Pydantic field names exactly. Extend `EtfRadarOverviewResponse`, `EtfRadarHistoryPoint`, `EtfRadarHoldersResponse`, and `CapitalSummaryResponse` additively. Do not introduce camelCase adapters.

- [ ] **Step 4: Implement pure formatters**

Add:

```typescript
export function formatActivityMultiple(value: number | null): string {
  return value === null ? '--' : `${value.toFixed(1)}倍`;
}

export function activityDirectionLabel(value: EtfActivityDirection): string {
  if (value === 'increase') return '申购';
  if (value === 'decrease') return '赎回';
  if (value === 'flat') return '持平';
  return '待确认';
}

export function validationStateLabel(value: EtfValidationState): string {
  if (value === 'confirmed_increase') return '确认增加';
  if (value === 'confirmed_decrease') return '确认减少';
  if (value === 'divergent') return '方向分歧';
  return '数据不全';
}
```

Use the existing `rise/fall/neutral` semantic colors; do not add a second palette.

- [ ] **Step 5: Verify unchanged API paths and commit**

Run:

```bash
cd apps/web-vue
corepack pnpm@9.15.0 test:unit --run src/utils/domain/capitalSignals.test.ts src/service/api.test.ts
corepack pnpm@9.15.0 typecheck
git add src/service/types.ts src/utils/domain/capitalSignals.ts src/utils/domain/capitalSignals.test.ts src/service/api.test.ts
git commit -m "feat: add Huijin ETF frontend contracts"
```

Expected: formatter/API tests and typecheck pass.

### Task 7: Refocus the ETF Radar Workspace

**Files:**
- Modify: `apps/web-vue/src/views/EtfRadarView.vue`
- Modify: `apps/web-vue/src/views/EtfRadarView.test.ts`

- [ ] **Step 1: Replace fixture data and write failing workspace assertions**

Change the four tab labels to `今日活动`, `累计轨迹`, `确认持仓`, and `方法与数据`. Build fixtures with seven core rows, three validation rows, three validation groups, baselines, and source metadata. Assert:

```typescript
expect(wrapper.text()).toContain('汇金 ETF 追踪');
expect(wrapper.text()).toContain('十倍量增加');
expect(wrapper.text()).toContain('交叉验证');
expect(wrapper.text()).toContain('方向分歧');
expect(wrapper.text()).toContain('报告期 2025-12-31');
expect(wrapper.text()).not.toContain('证据强度');
expect(wrapper.text()).not.toContain('稳健分');
expect(wrapper.text()).not.toContain('同时间成交');
expect(wrapper.text()).not.toContain('相对指数');
```

Retain the existing lazy-load assertions: initial mount requests only overview, and each remaining endpoint is requested once on first activation.

- [ ] **Step 2: Run workspace tests and verify RED**

Run: `cd apps/web-vue && corepack pnpm@9.15.0 test:unit --run src/views/EtfRadarView.test.ts`

Expected: failures because the old generic radar labels and columns remain.

- [ ] **Step 3: Implement the today view**

Render:

1. Four stable summary metrics: tenfold increases, tenfold decreases, confirmed pairs, and divergent pairs.
2. A seven-row core table with ETF, index, share delta, daily change, baseline change, multiple, direction, confirmed holding percentage/report period, and data state.
3. Three compact validation rows showing both ETF values, conservative result, and state.

Use `a-table` horizontal scrolling inside the section. Do not make the page itself horizontally scroll.

- [ ] **Step 4: Implement cumulative, holder, and methodology views**

- Cumulative chart: one selectable ETF at a time, x-axis real trade dates, y-axis `cumulative_baseline_change_pct`, no interpolation across missing dates.
- Confirmed holdings: exact legal entity rows and a baseline summary grouped by ETF/report period.
- Methodology: four formulas, tenfold threshold, pool version, baseline source kind, pair rules, and limitations.
- Errors retain the last loaded data and show a stale warning. Empty data uses an explicit empty state, not an empty chart.

- [ ] **Step 5: Run Vue gates and commit**

Run:

```bash
cd apps/web-vue
corepack pnpm@9.15.0 test:unit --run src/views/EtfRadarView.test.ts src/utils/domain/capitalSignals.test.ts
corepack pnpm@9.15.0 typecheck
git add src/views/EtfRadarView.vue src/views/EtfRadarView.test.ts
git commit -m "feat: rebuild Huijin ETF tracker workspace"
```

Expected: focused tests and typecheck pass.

### Task 8: Replace the Homepage Generic Radar Summary

**Files:**
- Modify: `apps/web-vue/src/views/HomeView.vue`
- Modify: `apps/web-vue/src/views/HomeView.test.ts`

- [ ] **Step 1: Write failing homepage assertions**

Update the capital fixture with `etf_radar.activity`. Assert the homepage contains:

```typescript
expect(wrapper.text()).toContain('汇金 ETF 活动');
expect(wrapper.text()).toContain('十倍量增加 5');
expect(wrapper.text()).toContain('确认增加 2组');
expect(wrapper.text()).toContain('方向分歧 1组');
expect(wrapper.text()).toContain('数据日 2026-07-17');
expect(wrapper.text()).not.toContain('证据强度');
expect(wrapper.text()).not.toContain('估算净申购');
```

Keep existing assertions that the homepage requests overview, sector flow, and capital summary concurrently and does not request ETF detail/history.

- [ ] **Step 2: Run homepage tests and verify RED**

Run: `cd apps/web-vue && corepack pnpm@9.15.0 test:unit --run src/views/HomeView.test.ts src/composables/useHomeDashboard.test.ts`

Expected: wording and value assertions fail against the generic evidence card.

- [ ] **Step 3: Implement the compact activity summary**

Replace the generic evidence gauge with:

- count strip for tenfold increase/decrease;
- paired-group confirmed/divergent counts;
- strongest core ETF and baseline change percentage;
- coverage `available_core_count / core_count`;
- explicit data date and stale/partial source tag;
- existing router link to `/etf-radar`.

Keep the panel height aligned with the financing panel. Do not add charts or extra homepage requests.

- [ ] **Step 4: Run tests, typecheck, and commit**

Run:

```bash
cd apps/web-vue
corepack pnpm@9.15.0 test:unit --run src/views/HomeView.test.ts src/composables/useHomeDashboard.test.ts
corepack pnpm@9.15.0 typecheck
git add src/views/HomeView.vue src/views/HomeView.test.ts
git commit -m "feat: show Huijin ETF activity on homepage"
```

Expected: homepage tests and typecheck pass.

### Task 9: Full Verification and Real-Data QA

**Files:**
- Modify only when verification exposes a defect in files already listed above.

- [ ] **Step 1: Run full backend checks**

Run:

```bash
cd apps/api
.venv/bin/pytest tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py tests/test_capital_signal_providers.py tests/test_capital_signals.py tests/test_capital_signal_sampler.py tests/test_api.py -q
.venv/bin/ruff check app/models.py app/providers/capital_signals.py app/services/huijin_etf_activity.py app/services/capital_signal_store.py app/services/capital_signals.py app/services/capital_signal_sampler.py app/main.py tests/test_huijin_etf_activity.py tests/test_capital_signal_store.py tests/test_capital_signal_providers.py tests/test_capital_signals.py tests/test_capital_signal_sampler.py tests/test_api.py
```

Expected: all selected backend tests pass and Ruff reports no errors.

- [ ] **Step 2: Run full Vue checks**

Run:

```bash
cd apps/web-vue
corepack pnpm@9.15.0 test:unit --run
corepack pnpm@9.15.0 typecheck
corepack pnpm@9.15.0 build
```

Expected: all test files pass, typecheck exits zero, and production build succeeds.

- [ ] **Step 3: Verify the public article regression fixture**

Run the dedicated regression test with verbose output:

```bash
cd apps/api
.venv/bin/pytest tests/test_huijin_etf_activity.py -k '2026_07_17 or pair' -vv
```

Expected: the 510050, 510300, 510500/159922, 512100/159845, and 159915 cases match the documented formula and validation states.

- [ ] **Step 4: Start isolated preview**

Start the worktree API:

```bash
cd apps/api
STRONG_STOCK_CORS_ALLOW_ORIGINS=http://127.0.0.1:3111 \
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8011
```

Start the worktree Vue app:

```bash
cd apps/web-vue
VITE_API_BASE_URL=http://127.0.0.1:8011 \
  corepack pnpm@9.15.0 dev --host 127.0.0.1 --port 3111
```

- [ ] **Step 5: Perform browser and API QA**

Verify:

- `/api/etf-radar/overview` returns seven core rows, three validator rows, three groups, pool version, baseline version, and non-fabricated missing values.
- `/api/etf-radar/holders` returns exact entities plus baselines.
- `/etf-radar` loads all four views lazily and has no console errors.
- 2026-07-17 data, when present in the store, matches the public-rule formulas.
- Mobile width `390px` has no document overflow; wide tables scroll internally.
- The homepage performs no ETF history or holder requests.

- [ ] **Step 6: Review diff and commit verification-only changes**

Run:

```bash
git diff --check
git status --short
```

If verification required a correction, stage only the listed product files and commit with:

```bash
git commit -m "fix: harden Huijin ETF activity states"
```

If no correction was required, do not create an empty commit.
