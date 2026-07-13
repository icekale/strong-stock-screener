# CZSC Upstream Shadow Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated `czsc==1.0.0rc8` research engine, display its selected signals in `/chanlun`, compute non-authoritative `czsc_score_v2` shadow rankings, and validate the strategy on a reproducible five-year dataset without changing current formal decisions.

**Architecture:** Keep `czsc==0.10.12` in the main API environment and run rc8 in a second Python environment behind a versioned JSONL worker protocol. The main API owns validation, evidence normalization, scoring, persistence, background scheduling, and all public contracts. Runtime research is optional and isolated; offline validation uses frozen Parquet data and the same worker/scoring code.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLite, `czsc==0.10.12`, isolated `czsc==1.0.0rc8`, pytest, httpx, optional PyArrow, Next.js 15, React 19, TypeScript, Ant Design, ECharts, Playwright, Docker.

**Design:** `docs/superpowers/specs/2026-07-13-czsc-upstream-integration-design.md`

---

## Execution Prerequisite

Before Task 1, use `superpowers:using-git-worktrees` to create an isolated worktree from commit `d532894` or a descendant containing this plan. Use branch `codex/czsc-upstream-integration`. Do not implement directly in another feature worktree.

Run every command block from the repository root unless the block starts with an explicit `cd`. A `cd` applies only to that command block; later blocks must establish their own working directory.

Record the baseline before edits:

```bash
cd apps/api && uv run pytest -q
cd ../web && pnpm test && pnpm build
```

Expected baseline: backend and frontend pass; the production build exits 0. If baseline behavior differs, record the exact failure before changing code.

## Milestone Boundaries

1. **Runtime foundation:** Tasks 1-7 produce a working research endpoint with no screener or UI authority.
2. **Workbench and shadow screening:** Tasks 8-12 expose research evidence and asynchronous shadow scores while preserving formal ordering.
3. **Five-year validation:** Tasks 13-15 build frozen data, perform walk-forward evaluation, and produce a reproducible report.

Do not begin a later milestone while required tests for the previous milestone are failing.

## File Structure

### Create

- `apps/api/rc8-worker/pyproject.toml`: isolated rc8 dependency project.
- `apps/api/rc8-worker/uv.lock`: independent lock for the worker runtime.
- `apps/api/app/services/chanlun/research_catalog.json`: shared fixed signal whitelist.
- `apps/api/app/services/chanlun/research_catalog.py`: typed catalog loader and evidence mapping.
- `apps/api/app/services/chanlun/research_scoring.py`: pure `czsc_score_v2` calculation.
- `apps/api/app/services/chanlun/research_protocol.py`: request/response schemas and snapshot hashing.
- `apps/api/app/services/chanlun/rc8_worker.py`: stdlib plus rc8 JSONL process entry point.
- `apps/api/app/services/chanlun/rc8_client.py`: priority queue, process lifecycle, timeout, and circuit breaker.
- `apps/api/app/services/chanlun/research_store.py`: runtime SQLite snapshots, evidence, batches, and scores.
- `apps/api/app/services/chanlun/research_service.py`: single-stock coordination, cache reuse, and async completion.
- `apps/api/app/services/chanlun/shadow_service.py`: bounded screener batch scheduling.
- `apps/api/app/providers/free_stockdb.py`: shared HTTP-only free-stockdb transport.
- `apps/api/app/services/chanlun/research_history.py`: free-stockdb offline history adapter and data normalization.
- `apps/api/app/services/chanlun/research_dataset.py`: candidate reconstruction, quality checks, Parquet partitions, and manifest.
- `apps/api/app/services/chanlun/research_validation.py`: folds, samples, ranking comparison, portfolio, and gates.
- `apps/api/app/services/chanlun/research_report.py`: deterministic JSON/CSV/HTML report writer.
- `apps/api/tests/test_chanlun_research_models.py`
- `apps/api/tests/test_chanlun_research_catalog.py`
- `apps/api/tests/test_chanlun_research_scoring.py`
- `apps/api/tests/test_chanlun_research_protocol.py`
- `apps/api/tests/test_chanlun_rc8_client.py`
- `apps/api/tests/test_chanlun_research_store.py`
- `apps/api/tests/test_chanlun_research_service.py`
- `apps/api/tests/test_chanlun_shadow_service.py`
- `apps/api/tests/test_chanlun_research_history.py`
- `apps/api/tests/test_chanlun_research_dataset.py`
- `apps/api/tests/test_chanlun_research_validation.py`
- `apps/api/tests/test_chanlun_research_report.py`
- `apps/api/tests/fixtures/fake_rc8_worker.py`
- `apps/api/rc8-worker/test_worker.py`
- `apps/web/lib/czscResearchOverlay.ts`
- `apps/web/lib/czscResearchOverlay.test.ts`
- `apps/web/lib/czscShadow.ts`
- `apps/web/lib/czscShadow.test.ts`
- `apps/web/app/chanlun/ChanlunResearchEvidence.tsx`
- `scripts/benchmark-czsc-rc8.py`
- `scripts/czsc-research.py`
- `scripts/visual-qa-chanlun.mjs`

### Modify

- `Dockerfile`, `apps/api/Dockerfile`
- `apps/api/pyproject.toml`, `apps/api/uv.lock`
- `apps/api/app/config.py`, `apps/api/app/models.py`, `apps/api/app/main.py`
- `apps/api/app/services/auction_model.py`
- `apps/api/app/services/chanlun/service.py`
- `apps/api/app/services/screener.py`
- `apps/api/tests/test_api.py`, `apps/api/tests/test_config.py`
- `apps/api/tests/test_docker_runtime_deps.py`, `apps/api/tests/test_screener_gsgf_ranking.py`
- `apps/api/tests/test_retention_policy.py`, `apps/api/tests/test_auction_model.py`
- `apps/web/package.json`, `apps/web/pnpm-lock.yaml`
- `apps/web/lib/types.ts`, `apps/web/lib/api.ts`, `apps/web/lib/api.test.ts`
- `apps/web/lib/chanlunOverlay.ts`, `apps/web/lib/chanlunOverlay.test.ts`
- `apps/web/components/TickFlowKlineChart.tsx`
- `apps/web/app/chanlun/ChanlunWorkspace.tsx`, `apps/web/app/chanlun/chanlunWorkspaceHelpers.ts`
- `apps/web/app/chanlun/chanlunWorkspace.test.ts`
- `apps/web/app/HomeWorkbench.tsx`
- `apps/web/components/screener/CandidateResults.tsx`
- `apps/web/lib/screenerDeSlop.test.ts`
- `apps/web/app/globals.css`, `scripts/smoke-ui.mjs`, `README.md`

## Shared Contracts

Use these names consistently in all tasks:

```python
CzscResearchStatus = Literal[
    "ready", "pending", "stale", "unavailable", "insufficient_bars", "adjustment_mismatch"
]
CzscEvidenceRole = Literal["primary", "confirmation", "risk", "observation"]
CzscEvidenceDirection = Literal["bullish", "bearish", "neutral"]
CzscV2BatchStatus = Literal["pending", "ready", "partial", "unavailable"]
CZSC_RC8_PROTOCOL_VERSION = "czsc-rc8-jsonl-v1"
CZSC_CATALOG_VERSION = "czsc-v2-catalog-1"
CZSC_SCORE_RULE_VERSION = "czsc-score-v2-rule-1"
```

The worker returns versioned signal states/events with both audit-only raw key/value strings and structured `v1`/`v2`/`v3`/`score` fields. Only the main API creates `CzscSignalEvidence`, applies Chinese explanations, computes scores, or persists data; business rules never parse the audit strings.

## Task 1: Prove and Package the Isolated rc8 Runtime

**Files:**
- Create: `apps/api/rc8-worker/pyproject.toml`
- Create: `apps/api/rc8-worker/uv.lock`
- Modify: `Dockerfile`
- Modify: `apps/api/Dockerfile`
- Modify: `apps/api/tests/test_docker_runtime_deps.py`

- [ ] **Step 1: Write failing packaging tests**

Add these assertions to `test_docker_runtime_deps.py`:

```python
def test_rc8_worker_has_an_independent_locked_project() -> None:
    repo_root = Path(__file__).parents[3]
    with (repo_root / "apps/api/rc8-worker/pyproject.toml").open("rb") as file:
        project = tomllib.load(file)

    assert project["project"]["dependencies"] == ["czsc==1.0.0rc8"]
    assert (repo_root / "apps/api/rc8-worker/uv.lock").exists()


def test_dockerfiles_build_and_copy_an_isolated_rc8_venv() -> None:
    repo_root = Path(__file__).parents[3]
    for path in [repo_root / "Dockerfile", repo_root / "apps/api/Dockerfile"]:
        content = path.read_text(encoding="utf-8")
        assert "/opt/czsc-rc8-venv" in content
        assert "importlib.metadata.version('czsc')" in content
        assert "1.0.0rc8" in content
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
cd apps/api
uv run pytest tests/test_docker_runtime_deps.py -q
```

Expected: FAIL because the second project and venv do not exist.

- [ ] **Step 3: Create and lock the worker project**

Create `apps/api/rc8-worker/pyproject.toml`:

```toml
[project]
name = "strong-stock-czsc-rc8-worker"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["czsc==1.0.0rc8"]
```

Lock it:

```bash
uv lock --project apps/api/rc8-worker
```

Expected: `apps/api/rc8-worker/uv.lock` records `czsc==1.0.0rc8` and exits 0.

- [ ] **Step 4: Add the second Docker build stage**

In the root Dockerfile, add this `rc8-builder` stage before the runner stage:

```dockerfile
FROM python:3.12-slim AS rc8-builder
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=$PIP_INDEX_URL PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10
WORKDIR /build/rc8
COPY apps/api/rc8-worker/pyproject.toml apps/api/rc8-worker/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /opt/czsc-rc8-venv \
    && /opt/czsc-rc8-venv/bin/python -m pip install setuptools wheel uv==0.11.6 \
    && /opt/czsc-rc8-venv/bin/uv export --locked --no-dev --no-emit-project --format requirements-txt -o requirements.txt \
    && /opt/czsc-rc8-venv/bin/python -m pip uninstall -y uv \
    && /opt/czsc-rc8-venv/bin/python -m pip install --no-build-isolation -r requirements.txt \
    && /opt/czsc-rc8-venv/bin/python -c "import importlib.metadata; assert importlib.metadata.version('czsc') == '1.0.0rc8'"
```

In the root runner, add `COPY --from=rc8-builder /opt/czsc-rc8-venv /opt/czsc-rc8-venv` beside the main API venv copy and append the rc8 `importlib.metadata.version` assertion to the existing runner smoke-check `RUN` command after `libgomp1` is installed.

Convert `apps/api/Dockerfile` to named `api-builder`, `rc8-builder`, and final runner stages using the same `/opt/strong-stock-api-venv` and `/opt/czsc-rc8-venv` paths. Copy the worker project with `COPY rc8-worker/pyproject.toml rc8-worker/uv.lock ./` in its rc8 stage, copy both venvs into the final stage, and run both pinned-version assertions there. Do not add rc8 to the main API lock.

- [ ] **Step 5: Verify the real wheel and both images**

Run:

```bash
uv run --project apps/api pytest apps/api/tests/test_docker_runtime_deps.py -q
uv sync --project apps/api/rc8-worker
uv run --project apps/api/rc8-worker python -c "import importlib.metadata; assert importlib.metadata.version('czsc') == '1.0.0rc8'"
docker build --target rc8-builder -t strong-stock-czsc-rc8-check .
docker build -f apps/api/Dockerfile -t strong-stock-api-dual-czsc apps/api
```

Expected: all commands exit 0. If PyPI has no compatible wheel for the target architecture, stop before Task 2 and capture the exact package/platform error; do not silently build from an unpinned branch.

- [ ] **Step 6: Commit**

```bash
git add apps/api/rc8-worker/pyproject.toml apps/api/rc8-worker/uv.lock Dockerfile apps/api/Dockerfile apps/api/tests/test_docker_runtime_deps.py
git commit -m "build: add isolated czsc rc8 runtime"
```

## Task 2: Add Research Models, Settings, and the Fixed Catalog

**Files:**
- Modify: `apps/api/app/config.py`
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/services/chanlun/research_catalog.json`
- Create: `apps/api/app/services/chanlun/research_catalog.py`
- Create: `apps/api/tests/test_chanlun_research_models.py`
- Create: `apps/api/tests/test_chanlun_research_catalog.py`
- Modify: `apps/api/tests/test_config.py`

- [ ] **Step 1: Write failing model and config tests**

```python
def test_research_evidence_is_versioned_and_auditable() -> None:
    evidence = CzscSignalEvidence(
        id="buy3.structure.5m:2026-07-10T10:00:00+08:00:三买",
        catalog_id="buy3.structure",
        family="third_buy",
        role="primary",
        direction="bullish",
        period="5m",
        occurred_at="2026-07-10T10:00:00+08:00",
        last_closed_bar_at="2026-07-10T10:00:00+08:00",
        signal_name="cxt_third_buy_V230228",
        raw_key="5分钟_D1_三买辅助V230228",
        raw_value="三买_6笔_任意_0",
        reason="5分钟结构出现三买",
        input_snapshot_id="sha256:abc",
        engine_version="1.0.0rc8",
    )

    assert evidence.catalog_version == "czsc-v2-catalog-1"
    assert evidence.rule_version == "czsc-score-v2-rule-1"


def test_research_settings_have_safe_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.chanlun_rc8_enabled is True
    assert settings.chanlun_rc8_interactive_wait_seconds == 3
    assert settings.chanlun_rc8_hard_timeout_seconds == 10
    assert settings.chanlun_research_retention_days == 180
    assert settings.chanlun_research_evidence_retention_days == 730
```

- [ ] **Step 2: Write the failing catalog test**

```python
def test_catalog_expands_only_the_approved_signal_whitelist() -> None:
    catalog = load_research_catalog()

    assert catalog.version == "czsc-v2-catalog-1"
    assert {item.name for item in catalog.entries} == {
        "cxt_bi_status_V230101",
        "cxt_bi_base_V230228",
        "cxt_second_bs_V240524",
        "cxt_second_bs_V230320",
        "cxt_third_buy_V230228",
        "cxt_third_bs_V230319",
        "cxt_zhong_shu_gong_zhen_V221221",
        "tas_macd_bc_V240307",
    }
    assert len(catalog.expanded_configs()) == 16
    assert all(item.params is not None for item in catalog.expanded_configs())
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
cd apps/api
uv run pytest tests/test_chanlun_research_models.py tests/test_chanlun_research_catalog.py tests/test_config.py -q
```

Expected: FAIL with missing models, settings, and loader.

- [ ] **Step 4: Add bounded settings and public models**

Add these settings:

```python
chanlun_rc8_enabled: bool = True
chanlun_rc8_python: Path = Path("./rc8-worker/.venv/bin/python")
chanlun_rc8_interactive_wait_seconds: float = Field(default=3, ge=0.1, le=10)
chanlun_rc8_hard_timeout_seconds: float = Field(default=10, ge=1, le=30)
chanlun_research_retention_days: int = Field(default=180, ge=30, le=730)
chanlun_research_evidence_retention_days: int = Field(default=730, ge=180, le=1825)
```

Add Pydantic models matching the shared contracts. `CzscSignalEvidence` must include all fields from the test plus optional `higher_period`, `lower_period`, and immutable `params`. Define a compact `CzscSignalEvidenceSummary` containing evidence ID, catalog ID, family, role, direction, period(s), occurrence time, and reason. `CzscResearchSnapshot` must contain `status`, `symbol`, `current_states`, `events`, `last_closed_by_period`, `input_snapshot_id`, `score`, `eligible`, versions, and source status. Define `CzscV2CandidateScore` with symbol, status, nullable score/rank, eligible, baseline rank, `list[CzscSignalEvidenceSummary]`, and input snapshot ID. Define `CzscV2BatchResult` with batch/job IDs, status, trade date, pool size, completed count, and an item list. Add nullable v2 fields to `StrongStockScreeningItem`, and `czsc_v2_job_id`/`czsc_v2_status` to `StrongStockScreeningResult`. Do not add a new screening status.

- [ ] **Step 5: Add and validate the JSON catalog**

The JSON root must be:

```json
{
  "catalog_version": "czsc-v2-catalog-1",
  "entries": [
    {"catalog_id": "trend.bi-status", "name": "cxt_bi_status_V230101", "periods": ["1d", "60m", "30m"], "params": {}, "key_template": "{freq}_D1_表里关系V230101", "role": "primary"},
    {"catalog_id": "trend.bi-base", "name": "cxt_bi_base_V230228", "periods": ["1d", "60m", "30m"], "params": {"bi_init_length": 9}, "key_template": "{freq}_D0BL9_V230228", "role": "primary"},
    {"catalog_id": "buy2.overlap", "name": "cxt_second_bs_V240524", "periods": ["5m"], "params": {"di": 1, "w": 9, "t": 2}, "key_template": "{freq}_D1W9T2_第二买卖点V240524", "role": "primary"},
    {"catalog_id": "buy2.ma-confirm", "name": "cxt_second_bs_V230320", "periods": ["5m"], "params": {"di": 1, "ma_type": "SMA", "timeperiod": 21}, "key_template": "{freq}_D1#SMA#21_BS2辅助V230320", "role": "confirmation"},
    {"catalog_id": "buy3.structure", "name": "cxt_third_buy_V230228", "periods": ["5m"], "params": {"di": 1}, "key_template": "{freq}_D1_三买辅助V230228", "role": "primary"},
    {"catalog_id": "buy3.ma-confirm", "name": "cxt_third_bs_V230319", "periods": ["5m"], "params": {"di": 1, "ma_type": "SMA", "timeperiod": 34}, "key_template": "{freq}_D1#SMA#34_BS3辅助V230319", "role": "confirmation"},
    {"catalog_id": "zone.resonance", "name": "cxt_zhong_shu_gong_zhen_V221221", "pairs": [["1d", "60m"], ["60m", "30m"]], "params": {}, "key_template": "{freq1}_{freq2}_中枢共振V221221", "role": "primary"},
    {"catalog_id": "risk.macd-divergence", "name": "tas_macd_bc_V240307", "periods": ["1d", "60m", "30m", "5m"], "params": {"di": 1, "n": 20}, "key_template": "{freq}_D1N20柱子背驰_BS辅助V240307", "role": "risk"}
  ]
}
```

The loader must reject unknown keys, duplicate expanded IDs, arbitrary signal names, empty periods, and catalog versions other than the expected constant.

- [ ] **Step 6: Verify GREEN and commit**

```bash
cd apps/api
uv run pytest tests/test_chanlun_research_models.py tests/test_chanlun_research_catalog.py tests/test_config.py -q
git add app/config.py app/models.py app/services/chanlun/research_catalog.json app/services/chanlun/research_catalog.py tests/test_chanlun_research_models.py tests/test_chanlun_research_catalog.py tests/test_config.py
git commit -m "feat: define czsc research contracts and catalog"
```

## Task 3: Implement Pure Evidence Mapping and `czsc_score_v2`

**Files:**
- Modify: `apps/api/app/services/chanlun/research_catalog.py`
- Create: `apps/api/app/services/chanlun/research_scoring.py`
- Modify: `apps/api/tests/test_chanlun_research_catalog.py`
- Create: `apps/api/tests/test_chanlun_research_scoring.py`

- [ ] **Step 1: Write failing evidence mapping tests**

```python
def test_map_raw_state_uses_catalog_identity_not_string_business_rules() -> None:
    evidence = map_raw_state(
        catalog_id="buy3.structure",
        period="5m",
        value_fields={"v1": "三买", "v2": "6笔", "v3": "任意", "score": 0},
        raw_key="5分钟_D1_三买辅助V230228",
        raw_value="三买_6笔_任意_0",
        occurred_at="2026-07-10T10:00:00+08:00",
        last_closed_bar_at="2026-07-10T10:00:00+08:00",
        input_snapshot_id="sha256:abc",
        engine_version="1.0.0rc8",
    )

    assert evidence is not None
    assert evidence.family == "third_buy"
    assert evidence.direction == "bullish"
    assert evidence.role == "primary"
    assert evidence.reason == "5分钟结构出现三买"


def test_map_raw_state_discards_inactive_other_value() -> None:
    assert map_raw_state(
        catalog_id="buy3.structure",
        period="5m",
        value_fields={"v1": "其他", "v2": "其他", "v3": "任意", "score": 0},
        raw_key="5分钟_D1_三买辅助V230228",
        raw_value="其他_其他_任意_0",
        occurred_at="2026-07-10T10:00:00+08:00",
        last_closed_bar_at="2026-07-10T10:00:00+08:00",
        input_snapshot_id="sha256:abc",
        engine_version="1.0.0rc8",
    ) is None
```

In the second test, pass the same explicit keyword arguments as the first test; change both the audit `raw_value` and structured `value_fields`. Add a third assertion that changing only `raw_value` while keeping `value_fields.v1 == "三买"` does not change the mapped family/direction/role. This proves business mapping does not parse audit strings.

- [ ] **Step 2: Write failing score tests**

```python
def test_score_reaches_100_for_complete_trend_continuation() -> None:
    result = score_czsc_v2(
        evidence=_complete_bullish_evidence(),
        freshness={period: "fresh" for period in ("1d", "60m", "30m", "5m")},
    )

    assert result.score == 100
    assert result.eligible is True
    assert result.rule_version == "czsc-score-v2-rule-1"


def test_score_applies_one_risk_penalty_per_period() -> None:
    result = score_czsc_v2(
        evidence=[*_complete_bullish_evidence(), _top_risk("1d"), _sell_risk("1d")],
        freshness={period: "fresh" for period in ("1d", "60m", "30m", "5m")},
    )

    assert result.score == 70
    assert result.eligible is False


def test_missing_or_stale_period_produces_null_score() -> None:
    result = score_czsc_v2(
        evidence=_complete_bullish_evidence(),
        freshness={"1d": "fresh", "60m": "fresh", "30m": "stale", "5m": "fresh"},
    )

    assert result.score is None
    assert result.eligible is False
```

- [ ] **Step 3: Run tests and verify RED**

```bash
cd apps/api
uv run pytest tests/test_chanlun_research_catalog.py tests/test_chanlun_research_scoring.py -q
```

Expected: FAIL because mapping and scoring functions are absent.

- [ ] **Step 4: Implement explicit mappings and score caps**

Use explicit catalog/value mappings such as:

```python
VALUE_MAP = {
    ("buy2.overlap", "二买"): ("second_buy", "bullish", "primary"),
    ("buy2.overlap", "二卖"): ("sell_risk", "bearish", "risk"),
    ("buy3.structure", "三买"): ("third_buy", "bullish", "primary"),
    ("buy3.ma-confirm", "三买"): ("third_buy", "bullish", "confirmation"),
    ("risk.macd-divergence", "顶背驰"): ("divergence", "bearish", "risk"),
    ("risk.macd-divergence", "底背驰"): ("divergence", "bullish", "observation"),
    ("zone.resonance", "看多"): ("zone_confluence", "bullish", "primary"),
    ("zone.resonance", "看空"): ("sell_risk", "bearish", "risk"),
}
```

For trend entries, map structured `v1` and `v2` separately into attributes retained in `params` or evidence details. Do not split or inspect `raw_value`, and do not use suffix checks outside this module.

Implement scoring as five capped buckets plus per-period maximum risk penalties:

```python
score = min(daily_points, 20) + min(hour_points, 20) + min(half_hour_points, 20)
score += min(trigger_points, 30) + min(alignment_points, 10)
score -= sum(max_penalty_by_period.values())
score = max(0, min(100, score))
```

Return `score=None` unless all four freshness values equal `fresh`. `eligible` requires no daily risk, no 60m/30m sell risk, and an active primary 5m second-buy or third-buy.

- [ ] **Step 5: Verify and commit**

```bash
cd apps/api
uv run pytest tests/test_chanlun_research_catalog.py tests/test_chanlun_research_scoring.py -q
git add app/services/chanlun/research_catalog.py app/services/chanlun/research_scoring.py tests/test_chanlun_research_catalog.py tests/test_chanlun_research_scoring.py
git commit -m "feat: map and score czsc research evidence"
```

## Task 4: Implement the rc8 JSONL Worker

**Files:**
- Create: `apps/api/app/services/chanlun/research_protocol.py`
- Create: `apps/api/app/services/chanlun/rc8_worker.py`
- Create: `apps/api/tests/test_chanlun_research_protocol.py`
- Create: `apps/api/rc8-worker/test_worker.py`
- Modify: `Dockerfile`
- Modify: `apps/api/Dockerfile`

- [ ] **Step 1: Write failing protocol tests in the main API**

```python
def test_request_hash_is_order_stable_and_changes_with_last_bar() -> None:
    first = build_research_request("600000.SH", _period_bars(close=10.0))
    reordered = build_research_request("600000.SH", dict(reversed(list(_period_bars(close=10.0).items()))))
    changed = build_research_request("600000.SH", _period_bars(close=10.1))

    assert first.input_snapshot_id == reordered.input_snapshot_id
    assert first.input_snapshot_id.startswith("sha256:")
    assert first.input_snapshot_id != changed.input_snapshot_id


def test_protocol_rejects_unclosed_or_unknown_period_payload() -> None:
    with pytest.raises(ValueError):
        CzscRc8Request.model_validate({**_request_payload(), "periods": {"15m": []}})
```

Add a deterministic cutoff case where a period contains a bar later than its declared `last_closed_by_period`; validation must reject it before serialization.

- [ ] **Step 2: Write worker tests in the isolated project**

`test_worker.py` must load `apps/api/app/services/chanlun/rc8_worker.py` with `importlib.util.spec_from_file_location`, so the isolated environment does not import the main API package. Invoke `handle_request` with deterministic zig-zag bars and assert:

```python
class WorkerTests(unittest.TestCase):
    def test_worker_returns_versioned_states_events_and_diagnostics(self):
        response = handle_request(make_request())

        self.assertEqual(response["schema_version"], "czsc-rc8-jsonl-v1")
        self.assertEqual(response["engine_version"], "1.0.0rc8")
        self.assertEqual(response["catalog_version"], "czsc-v2-catalog-1")
        self.assertEqual(response["status"], "ready")
        self.assertIn("current_states", response)
        self.assertIn("events", response)
        self.assertEqual(set(response["diagnostics"]), {"1d", "60m", "30m", "5m"})

    def test_worker_rejects_catalog_or_protocol_mismatch(self):
        payload = make_request()
        payload["catalog_version"] = "unknown"
        with self.assertRaises(ValueError):
            handle_request(payload)
```

- [ ] **Step 3: Run tests and verify RED**

```bash
cd apps/api
uv run pytest tests/test_chanlun_research_protocol.py -q
cd rc8-worker
uv run python -m unittest discover -s . -p 'test_worker.py' -v
```

Expected: FAIL because request schemas and worker do not exist.

- [ ] **Step 4: Implement deterministic request schemas**

`CzscRc8Request` must contain protocol version, request ID, symbol, catalog version, adjustment mode, decision time, `last_closed_by_period`, input snapshot ID, and `dict[ChanlunPeriod, list[KlineBar]]`. Validate strict time order and require every last bar to correspond to its declared boundary under period-aware close normalization and not exceed the decision time before serialization. In particular, a daily source date such as `2026-07-10` is available at that session's 15:00 close, not midnight. Hash canonical JSON with sorted period keys and compact separators.

`CzscRc8Response` must contain protocol/catalog/engine versions, request and snapshot IDs, status, current states, transition events, period diagnostics, and a sanitized error. Every raw state/event contains `raw_key`, `raw_value`, and structured `value_fields = {v1, v2, v3, score}`; schema validation rejects missing fields or non-integer scores.

- [ ] **Step 5: Implement the stdlib plus rc8 worker**

The entry point must follow this shape:

```python
def main() -> None:
    for line in sys.stdin:
        request_id = "unknown"
        try:
            payload = json.loads(line)
            request_id = str(payload.get("request_id", "unknown"))
            response = handle_request(payload)
        except Exception as exc:
            response = error_response(request_id, exc)
        sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()
```

For each single-period catalog entry, convert bars to rc8 `RawBar`, call `generate_czsc_signals(raw_bars, signals_config=configs, df=False, sdt=start_at, init_n=0)` with only that period's fixed configs, locate exact keys expanded from the catalog, and reduce consecutive rows into current states plus inactive-to-active transition events. Convert each returned audit value through rc8 `Signal(key=raw_key, value=raw_value)` and emit its `v1`, `v2`, `v3`, and integer `score`; the main API must not parse the string.

For `zone.resonance`, do not derive long-period history from the request's limited 5m lookback and do not let `BarGenerator` expose a provisional higher-period bar. rc8 has no public Python method that primes a trader-level signal against independently initialized frequency arrays, so implement a narrow compatibility adapter using only rc8 `CZSC`, `ZS`, and `Direction`: build each side from the explicit closed bars visible at each lower-period close and reproduce the registered `cxt_zhong_shu_gong_zhen_V221221` algorithm exactly. Require at least five strokes on both sides, construct `ZS` from the latest three strokes, test `zg > zd` directly (do not use `ZS.is_valid()`, whose semantics differ), then compare `small.dd`/`small.gg` to `big.zz` and the lower-period last-stroke direction. Closed availability comes from the request's declared period boundaries, not a daily bar's midnight timestamp. Keep this adapter in `rc8_worker.py`, identify its output as the same fixed catalog signal, and add a parity fixture comparing it with rc8's registered trader signal at synchronized market-close checkpoints. If either side lacks enough strokes or an overlapping zone, return `其他` rather than fabricate confluence.

Build diagnostics from `CZSC(raw_bars)` for each explicit period:

```python
diagnostics[period] = {
    "bar_count": len(raw_bars),
    "fractal_count": len(czsc.fx_list),
    "stroke_count": len(czsc.bi_list),
    "last_stroke_direction": str(czsc.bi_list[-1].direction) if czsc.bi_list else "unknown",
}
```

The worker must load only `research_catalog.json`; it must reject function names supplied by request data.

- [ ] **Step 6: Copy the worker into both runtime images and verify**

Ensure the root image contains `/app/api/app/services/chanlun/rc8_worker.py` and the API image contains `/app/app/services/chanlun/rc8_worker.py`. Run:

```bash
cd apps/api
uv run pytest tests/test_chanlun_research_protocol.py -q
uv run --project rc8-worker python -m unittest discover -s rc8-worker -p 'test_worker.py' -v
printf '%s\n' '{"schema_version":"bad"}' | rc8-worker/.venv/bin/python app/services/chanlun/rc8_worker.py
```

Expected: tests pass; the manual command returns one JSON error line and exits without a traceback on stdout.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/services/chanlun/research_protocol.py apps/api/app/services/chanlun/rc8_worker.py apps/api/tests/test_chanlun_research_protocol.py apps/api/rc8-worker/test_worker.py Dockerfile apps/api/Dockerfile
git commit -m "feat: add versioned czsc rc8 worker protocol"
```

## Task 5: Build the Priority Client and Circuit Breaker

**Files:**
- Create: `apps/api/app/services/chanlun/rc8_client.py`
- Create: `apps/api/tests/test_chanlun_rc8_client.py`
- Create: `apps/api/tests/fixtures/fake_rc8_worker.py`

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_interactive_request_runs_before_next_background_item(tmp_path: Path) -> None:
    client = Rc8WorkerClient(python_path=sys.executable, worker_path=_fake_worker_path())
    first = client.submit(_request("delay-background-1"), priority=10)
    _wait_for(lambda: client.health()["active_request_id"] == "delay-background-1")
    second = client.submit(_request("background-2"), priority=10)
    interactive = client.submit(_request("interactive"), priority=0)

    assert first.result(timeout=1).request_id == "delay-background-1"
    assert interactive.result(timeout=1).request_id == "interactive"
    assert second.result(timeout=1).request_id == "background-2"
    client.close()


def test_timeout_restarts_worker_and_opens_circuit_after_three_failures() -> None:
    client = Rc8WorkerClient(
        python_path=sys.executable,
        worker_path=_fake_worker_path(),
        hard_timeout_seconds=0.05,
        circuit_failures=3,
        circuit_seconds=60,
    )

    for index in range(3):
        with pytest.raises(Rc8WorkerUnavailable):
            client.submit(_request(f"slow-{index}"), priority=0).result(timeout=1)

    with pytest.raises(Rc8CircuitOpen):
        client.submit(_request("blocked"), priority=0)
    client.close()
```

The fake worker sleeps 200ms for request IDs beginning `delay-`, sleeps one second for IDs beginning `slow-`, and has explicit request-ID prefixes for malformed JSON, mismatched IDs, and process exit. Add tests for each mode, one successful restart retry, and `close()` idempotency. `health()` must expose `active_request_id`, queue depth, circuit state, consecutive failed requests, engine version, and last sanitized error.

- [ ] **Step 2: Run and verify RED**

```bash
cd apps/api
uv run pytest tests/test_chanlun_rc8_client.py -q
```

Expected: FAIL because the client does not exist.

- [ ] **Step 3: Implement a single worker thread and priority queue**

Use an ordered queue item:

```python
@dataclass(order=True)
class _QueuedRequest:
    priority: int
    sequence: int
    payload: CzscRc8Request = field(compare=False)
    future: Future[CzscRc8Response] = field(compare=False)
```

`submit()` must reject while the circuit is open, enqueue an immutable request, and return a `Future`. The worker thread lazily starts `Popen([python_path, worker_path], stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True, bufsize=1)`, writes one compact line, and reads exactly one response line.

Use `selectors.DefaultSelector` to enforce the hard timeout on stdout. On timeout, EOF, malformed response, or mismatched request ID: kill the process and retry the request once with a fresh process. Increment the circuit's consecutive failure count once only when the request still fails after its retry; reset it only after a schema-valid response.

- [ ] **Step 4: Verify and commit**

```bash
cd apps/api
uv run pytest tests/test_chanlun_rc8_client.py -q
git add app/services/chanlun/rc8_client.py tests/test_chanlun_rc8_client.py tests/fixtures/fake_rc8_worker.py
git commit -m "feat: isolate czsc rc8 process lifecycle"
```

## Task 6: Persist Research Snapshots, Evidence, and Shadow Batches

**Files:**
- Create: `apps/api/app/services/chanlun/research_store.py`
- Create: `apps/api/tests/test_chanlun_research_store.py`
- Modify: `apps/api/tests/test_retention_policy.py`

- [ ] **Step 1: Write failing persistence tests**

```python
def test_store_upserts_snapshot_and_deduplicates_events(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    snapshot = _snapshot("sha256:a")

    store.save_snapshot(snapshot)
    store.save_snapshot(snapshot)

    assert store.load_snapshot("sha256:a") == snapshot
    assert store.count_events() == len(snapshot.events)


def test_store_never_returns_snapshot_for_a_different_input_hash(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.save_snapshot(_snapshot("sha256:a"))

    assert store.load_snapshot("sha256:b") is None


def test_store_prunes_runtime_rows_but_keeps_latest_version_snapshot(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.save_snapshot(_snapshot("sha256:old", calculated_at="2025-01-01T15:00:00+08:00"))
    store.save_snapshot(_snapshot("sha256:latest", calculated_at="2026-07-10T15:00:00+08:00"))

    store.prune(now=datetime(2026, 7, 13, tzinfo=SHANGHAI), snapshot_days=180, evidence_days=730)

    assert store.load_snapshot("sha256:old") is None
    assert store.load_snapshot("sha256:latest") is not None
```

- [ ] **Step 2: Run and verify RED**

```bash
cd apps/api
uv run pytest tests/test_chanlun_research_store.py tests/test_retention_policy.py -q
```

Expected: FAIL because the SQLite store is absent.

- [ ] **Step 3: Implement the schema and atomic methods**

Create tables exactly for `research_snapshots`, `signal_evidence`, `shadow_batches`, and `shadow_scores`. Use `input_snapshot_id` as snapshot primary key and evidence `id` as event primary key. Save a snapshot and its events in one transaction. Store JSON using sorted keys and `ensure_ascii=False`.

Required public methods:

```python
save_snapshot(snapshot: CzscResearchSnapshot) -> None
load_snapshot(input_snapshot_id: str) -> CzscResearchSnapshot | None
latest_snapshot(symbol: str) -> CzscResearchSnapshot | None
create_batch(batch_id: str, trade_date: str, baseline_symbols: list[str]) -> None
save_batch_score(batch_id: str, score: CzscV2CandidateScore) -> None
load_batch(batch_id: str) -> CzscV2BatchResult | None
finish_batch(batch_id: str, status: CzscV2BatchStatus) -> None
prune(now: datetime, snapshot_days: int, evidence_days: int) -> None
```

Use WAL and a busy timeout, matching the existing minute store's connection style.

- [ ] **Step 4: Verify and commit**

```bash
cd apps/api
uv run pytest tests/test_chanlun_research_store.py tests/test_retention_policy.py -q
git add app/services/chanlun/research_store.py tests/test_chanlun_research_store.py tests/test_retention_policy.py
git commit -m "feat: persist czsc research snapshots"
```

## Task 7: Add the Research Service, API, and Health State

**Files:**
- Create: `apps/api/app/services/chanlun/research_service.py`
- Modify: `apps/api/app/services/chanlun/service.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_chanlun_research_service.py`
- Modify: `apps/api/tests/test_api.py`

- [ ] **Step 1: Write failing service tests**

```python
def test_service_returns_cached_snapshot_without_submitting_worker() -> None:
    request = _request("sha256:cached")
    store = FakeResearchStore(snapshot=_snapshot("sha256:cached"))
    client = RecordingRc8Client()
    service = CzscResearchService(store=store, client=client, input_provider=StaticInputProvider(request))

    result = service.get("600000.SH", lookback=220)

    assert result.status == "ready"
    assert client.requests == []


def test_service_returns_pending_after_interactive_wait_without_duplicate_submission() -> None:
    future: Future[CzscRc8Response] = Future()
    client = RecordingRc8Client(future=future)
    service = CzscResearchService(
        store=FakeResearchStore(),
        client=client,
        input_provider=StaticInputProvider(_request("sha256:new")),
        interactive_wait_seconds=0.01,
    )

    first = service.get("600000.SH", lookback=220)
    second = service.get("600000.SH", lookback=220)

    assert first.status == second.status == "pending"
    assert len(client.requests) == 1
```

Add tests proving stale/insufficient formal inputs never submit the worker and worker failure returns `unavailable` without raising.

- [ ] **Step 2: Write failing API tests**

```python
def test_research_endpoint_is_independent_from_formal_analysis(client, monkeypatch) -> None:
    app.state.chanlun_research_service = StaticResearchService(_snapshot("sha256:x"))
    response = client.get("/api/chanlun/stocks/600000.SH/research-signals?lookback=220")

    assert response.status_code == 200
    assert response.json()["input_snapshot_id"] == "sha256:x"


def test_health_reports_rc8_unavailable_without_failing_api_health(client) -> None:
    app.state.chanlun_rc8_client = UnavailableRc8Client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["chanlun_research"]["status"] == "unavailable"
```

- [ ] **Step 3: Run and verify RED**

```bash
cd apps/api
uv run pytest tests/test_chanlun_research_service.py tests/test_api.py -q -k 'research or health'
```

Expected: FAIL because service wiring and endpoint are missing.

- [ ] **Step 4: Expose a coalesced closed-bar snapshot in the existing service**

Add `closed_workspace_inputs(symbol, lookback, now=None)` to `ChanlunAnalysisService`. It must call the existing per-period paths, return only bars already classified as closed, and cache/coalesce the four-period result using `TtlCache`. Refactor `workspace()` to consume the same method so parallel formal/research calls do not refetch TickFlow or TDX.

Do not move structure derivation into the research service. The input provider returns period bars, per-period availability/freshness, last closed times, and one adjustment mode or `adjustment_mismatch`.

- [ ] **Step 5: Implement service coalescing and completion callback**

`get(symbol, lookback, priority=0, wait_seconds=None)` must:

1. Build a canonical request and check exact snapshot cache.
2. Return `insufficient_bars`, `stale`, or `adjustment_mismatch` before worker submission when input is not scoreable.
3. Reuse an in-flight `Future` keyed by `input_snapshot_id`, submitting new work with the requested priority.
4. Wait for `wait_seconds` when supplied, otherwise at most the interactive setting.
5. On completion, validate, map raw states/events through the catalog, compute the score, save atomically, and remove the in-flight key.
6. Return `pending` after the wait expires; never cancel the shared future.

- [ ] **Step 6: Wire app dependencies and endpoint**

Add singleton factories for catalog, client, store, and service under the existing Chanlun factories. Set Docker environment `STRONG_STOCK_CHANLUN_RC8_PYTHON=/opt/czsc-rc8-venv/bin/python`. Add the GET endpoint and health subsection. Close the worker client during test reset/application shutdown where current app lifecycle cleanup is implemented.

- [ ] **Step 7: Verify the runtime foundation and commit**

```bash
cd apps/api
uv run pytest tests/test_chanlun_*.py tests/test_api.py -q
cd ../..
git add apps/api/app/services/chanlun/research_service.py apps/api/app/services/chanlun/service.py apps/api/app/main.py apps/api/tests/test_chanlun_research_service.py apps/api/tests/test_api.py Dockerfile apps/api/Dockerfile
git commit -m "feat: expose isolated czsc research analysis"
```

Milestone 1 exit: the research endpoint can return `ready/pending/unavailable`, existing Chanlun tests pass, and disabling or killing rc8 leaves formal APIs operational.

## Task 8: Prove No-Future Behavior and Measure the Worker

**Files:**
- Modify: `apps/api/rc8-worker/test_worker.py`
- Create: `scripts/benchmark-czsc-rc8.py`
- Modify: `apps/api/tests/test_chanlun_research_service.py`

- [ ] **Step 1: Add the failing prefix-equivalence test**

Generate deterministic 5m, 30m, 60m, and daily bars. Send one full request and collect every returned event. Then send prefixes ending at each event time and assert that the event first appears at the same close:

```python
def test_full_timeline_matches_prefix_first_visibility(self):
    full = handle_request(make_request(bar_count=320))
    for event in full["events"]:
        prefix = request_ending_at(event["occurred_at"])
        observed = handle_request(prefix)
        self.assertIn(event_identity(event), {event_identity(item) for item in observed["events"]})
```

Also assert that removing the final bar removes events whose `occurred_at` equals that final close.

- [ ] **Step 2: Run and verify the test is meaningful**

```bash
uv run --project apps/api/rc8-worker python -m unittest discover -s apps/api/rc8-worker -p 'test_worker.py' -v
```

Expected: PASS if Task 4 timestamped transitions correctly. The fixture must assert that at least one whitelisted event exists before comparing prefixes; an empty event set is a test failure.

- [ ] **Step 3: Correct transition timestamps in the worker**

Ensure transitions are derived from each row returned by incremental `generate_czsc_signals`, using that row's `dt` as `occurred_at`. Never assign a structure's earlier fractal/stroke timestamp to a later-confirmed signal.

- [ ] **Step 4: Add the benchmark script**

The script must accept `--symbols`, `--bars`, `--worker-python`, and `--json-output`; generate deterministic requests; measure cache-free sequential latency; and output P50/P95, elapsed time, successes, failures, and max RSS when available. Exit nonzero if any response is invalid.

Run:

```bash
uv run --project apps/api/rc8-worker python -m unittest discover -s apps/api/rc8-worker -p 'test_worker.py' -v
uv run --project apps/api python scripts/benchmark-czsc-rc8.py --symbols 1 --bars 480 --worker-python apps/api/rc8-worker/.venv/bin/python --json-output /tmp/czsc-rc8-baseline.json
```

Expected: no-future tests pass and one-symbol benchmark succeeds. Record results; the 60-symbol target is checked after background batching exists.

- [ ] **Step 5: Commit**

```bash
git add apps/api/rc8-worker/test_worker.py apps/api/tests/test_chanlun_research_service.py scripts/benchmark-czsc-rc8.py
git commit -m "test: verify czsc research timing and performance"
```

## Task 9: Add Typed Frontend Research Loading and Marker Aggregation

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/lib/api.test.ts`
- Create: `apps/web/lib/czscResearchOverlay.ts`
- Create: `apps/web/lib/czscResearchOverlay.test.ts`
- Modify: `apps/web/components/TickFlowKlineChart.tsx`
- Modify: `apps/web/lib/chanlunOverlay.ts`
- Modify: `apps/web/lib/chanlunOverlay.test.ts`

- [ ] **Step 1: Write failing API and overlay tests**

```typescript
test("research API encodes symbol and requests the frozen lookback", async () => {
  await getCzscResearchSignals("600000.SH/test", { lookback: 220 });
  assert.match(lastFetchUrl(), /600000.SH%2Ftest\/research-signals\?lookback=220/);
});


test("same-candle same-side research evidence collapses into one marker", () => {
  const series = buildCzscResearchOverlaySeries(snapshotWithEvents([
    event("buy2.overlap", "2026-07-10T10:00:00+08:00", "bullish"),
    event("buy3.ma-confirm", "2026-07-10T10:00:00+08:00", "bullish"),
  ]));
  const data = series.data as Array<{ label: { formatter: string }; evidence: unknown[] }>;

  assert.equal(data.length, 1);
  assert.equal(data[0]?.label.formatter, "2B +1");
  assert.equal(data[0]?.evidence.length, 2);
});
```

Add a test that bullish markers are below candles, bearish/risk markers above, and zoom never changes grouping.

- [ ] **Step 2: Run and verify RED**

```bash
cd apps/web
pnpm test
```

Expected: FAIL with missing API/types/overlay.

- [ ] **Step 3: Mirror backend unions and implement the API**

Add exact TypeScript unions and types for `CzscSignalEvidence`, `CzscResearchSnapshot`, and v2 candidate fields. `getCzscResearchSignals` must use existing `API_BASE_URL`, URL-encode symbol, and surface non-2xx details with the established API error style.

- [ ] **Step 4: Build one stable ECharts scatter series**

Group events by resolved chart date and side. Pick the primary marker in this order: primary third buy, primary second buy, risk, confirmation, observation. Keep all grouped evidence on the data item for tooltip formatting. Use short labels only: `3B`, `2B`, `顶`, `卖`, plus `+N`.

Add optional `czscResearch` and `showCzscResearch` props to `TickFlowKlineChart`. Merge the research series after formal Chanlun layers and add a matching clear-series ID so symbol/period changes cannot leave stale markers.

- [ ] **Step 5: Verify and commit**

```bash
cd apps/web
pnpm test
git add lib/types.ts lib/api.ts lib/api.test.ts lib/czscResearchOverlay.ts lib/czscResearchOverlay.test.ts components/TickFlowKlineChart.tsx lib/chanlunOverlay.ts lib/chanlunOverlay.test.ts
git commit -m "feat: render aggregated czsc research markers"
```

## Task 10: Integrate Research Evidence into `/chanlun`

**Files:**
- Create: `apps/web/app/chanlun/ChanlunResearchEvidence.tsx`
- Modify: `apps/web/app/chanlun/ChanlunWorkspace.tsx`
- Modify: `apps/web/app/chanlun/chanlunWorkspaceHelpers.ts`
- Modify: `apps/web/app/chanlun/chanlunWorkspace.test.ts`
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/package.json`, `apps/web/pnpm-lock.yaml`
- Create: `scripts/visual-qa-chanlun.mjs`
- Modify: `scripts/smoke-ui.mjs`

- [ ] **Step 1: Write failing workbench tests**

Add pure helper tests for evidence grouping and source state, then source assertions:

```typescript
test("workbench enables research signals and keeps moving averages disabled", () => {
  const source = readFileSync(new URL("./ChanlunWorkspace.tsx", import.meta.url), "utf8");
  assert.match(source, /\[showResearch,\s*setShowResearch\]\s*=\s*useState\(true\)/);
  assert.match(source, /\[showMovingAverages,\s*setShowMovingAverages\]\s*=\s*useState\(false\)/);
});


test("workbench separates analysis replay and simulation tasks", () => {
  const source = readFileSync(new URL("./ChanlunWorkspace.tsx", import.meta.url), "utf8");
  assert.match(source, /分析证据/);
  assert.match(source, /回放验证/);
  assert.match(source, /预警模拟/);
});
```

- [ ] **Step 2: Run and verify RED**

```bash
cd apps/web
pnpm test
```

Expected: FAIL because research state and tabs are absent.

- [ ] **Step 3: Load formal and research data independently**

Keep the existing formal load path. Start the research request separately after symbol selection, abort stale symbol requests, and poll only while status is `pending`. Stop polling on `ready`, terminal failure, symbol change, or unmount. A research error must set only research state and never overwrite the formal `error`/analysis.

Pass the snapshot to `TickFlowKlineChart` only when symbol and selected period match. Add the default-on checkbox labeled `上游研究信号`; leave `均线` default off.

- [ ] **Step 4: Add task tabs without moving business logic**

Use Ant Design `Tabs` to wrap the existing presentational sections:

- `分析证据`: formal confirmed signals, `ChanlunResearchEvidence`, formal confluence.
- `回放验证`: existing replay and backtest sections.
- `预警模拟`: existing alert and paper account/order sections.

Keep handlers/state in `ChanlunWorkspace`; the new evidence component receives typed props and renders `primary`, `confirmation`, `risk`, and `observation` groups. Do not allow research evidence to call alert or paper-order actions.

- [ ] **Step 5: Add deterministic visual QA**

Add `playwright: "1.54.1"` as a pinned dev dependency. `visual-qa-chanlun.mjs` must open `/chanlun?symbol=300308.SZ`, wait for the chart container, capture 1440x1000 and 390x844 screenshots, and fail when:

- the chart canvas is blank;
- the page has horizontal overflow;
- marker label bounding boxes overlap visible toolbar controls;
- a Next.js error overlay or console error appears.

Add `/chanlun?symbol=300308.SZ` to `smoke-ui.mjs` routes.

- [ ] **Step 6: Verify and commit**

```bash
cd apps/web
pnpm test
pnpm build
git add app/chanlun/ChanlunResearchEvidence.tsx app/chanlun/ChanlunWorkspace.tsx app/chanlun/chanlunWorkspaceHelpers.ts app/chanlun/chanlunWorkspace.test.ts app/globals.css package.json pnpm-lock.yaml ../../scripts/visual-qa-chanlun.mjs ../../scripts/smoke-ui.mjs
git commit -m "feat: add czsc research evidence to workbench"
```

## Task 11: Schedule Bounded Shadow Scoring Without Delaying Formal Screening

**Files:**
- Create: `apps/api/app/services/chanlun/shadow_service.py`
- Modify: `apps/api/app/services/screener.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_chanlun_shadow_service.py`
- Modify: `apps/api/tests/test_screener_gsgf_ranking.py`
- Modify: `apps/api/tests/test_api.py`

- [ ] **Step 1: Write failing scheduler tests**

```python
def test_scheduler_returns_job_id_before_any_rc8_result(tmp_path: Path) -> None:
    blocking = BlockingResearchRunner()
    scheduler = CzscShadowScheduler(
        jobs=BackgroundJobStore(tmp_path),
        store=ChanlunResearchStore(tmp_path / "research.sqlite3"),
        runner=blocking,
    )

    started = monotonic()
    job_id = scheduler.submit(trade_date="2026-07-10", candidates=_shadow_inputs(20))

    assert monotonic() - started < 0.1
    assert job_id
    assert blocking.started.wait(timeout=1)


def test_partial_batch_keeps_null_score_for_failed_symbol(tmp_path: Path) -> None:
    result = _run_batch(failing_symbols={"600001.SH"})
    by_symbol = {item.symbol: item for item in result.items}

    assert result.status == "partial"
    assert by_symbol["600001.SH"].score is None
    assert by_symbol["600002.SH"].score is not None
```

- [ ] **Step 2: Write the formal-order regression test**

```python
def test_shadow_scheduler_never_changes_formal_order(monkeypatch) -> None:
    scheduler = RecordingShadowScheduler(job_id="shadow-1")
    screener = _screener(chanlun_v2_scheduler=scheduler)

    result = screener.screen("2026-07-10", limit=3, scan_limit=30)

    assert [item.symbol for item in result.items] == _expected_formal_symbols()
    assert result.czsc_v2_job_id == "shadow-1"
    assert all(item.czsc_score_v2 is None for item in result.items)
    assert 20 <= len(scheduler.candidates) <= 60
```

- [ ] **Step 3: Run and verify RED**

```bash
cd apps/api
uv run pytest tests/test_chanlun_shadow_service.py tests/test_screener_gsgf_ranking.py tests/test_api.py -q -k 'shadow or formal_order'
```

Expected: FAIL because scheduler integration is missing.

- [ ] **Step 4: Implement per-symbol background work units**

`CzscShadowScheduler.submit()` creates a `shadow_batches` row and one transient background job. The runner loops the immutable 20-60 candidate inputs in baseline order, calls `CzscResearchService.get(item.symbol, lookback=220, priority=10, wait_seconds=self.hard_timeout_seconds)`, stores a nullable candidate score, and updates progress after every symbol. It computes shadow rank only after all candidates finish:

```python
ordered = sorted(
    scores,
    key=lambda item: (
        0 if item.eligible else 1,
        -(item.score if item.score is not None else -1),
        item.baseline_rank,
    ),
)
```

Status is `ready` when all scoreable candidates succeed, `partial` when at least one succeeds, and `unavailable` otherwise.

- [ ] **Step 5: Inject scheduler at the existing bounded enrichment point**

Extend `StrongStockScreener` with an optional scheduler protocol. Change `_enrich_chanlun_candidates` to return the unchanged enriched item list plus the exact bounded pool in its existing formal baseline order. Create immutable shadow inputs containing only symbol, baseline rank, and trade date, submit that pool once after formal Chanlun enrichment, and capture only the returned job ID/status. The background `CzscResearchService` call owns closed-bar acquisition and persists the actual `input_snapshot_id` with each score; do not synchronously build or copy minute snapshots on the formal response path. Do not read any v2 result in `_screening_rank_key`, filters, alerts, or paper code.

Add `GET /api/chanlun/screening/shadow/jobs/{job_id}`. It returns generic job progress plus persisted batch result when available. Wire scheduler in `_execute_screen_run`; keep formal job progress at four steps.

- [ ] **Step 6: Verify and commit**

```bash
cd apps/api
uv run pytest tests/test_chanlun_shadow_service.py tests/test_screener_gsgf_ranking.py tests/test_api.py -q
git add app/services/chanlun/shadow_service.py app/services/screener.py app/main.py tests/test_chanlun_shadow_service.py tests/test_screener_gsgf_ranking.py tests/test_api.py
git commit -m "feat: add asynchronous czsc shadow scoring"
```

## Task 12: Display Shadow Scores Without Reordering Candidate Results

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`, `apps/web/lib/api.test.ts`
- Create: `apps/web/lib/czscShadow.ts`, `apps/web/lib/czscShadow.test.ts`
- Modify: `apps/web/app/HomeWorkbench.tsx`
- Modify: `apps/web/components/screener/CandidateResults.tsx`
- Modify: `apps/web/lib/screenerDeSlop.test.ts`

- [ ] **Step 1: Write failing merge and display tests**

```typescript
test("mergeShadowScores preserves formal order", () => {
  const formal = [candidate("A"), candidate("B"), candidate("C")];
  const merged = mergeShadowScores(formal, {
    C: score(95, 1),
    A: score(40, 3),
    B: score(null, null),
  });

  assert.deepEqual(merged.map((item) => item.symbol), ["A", "B", "C"]);
  assert.deepEqual(merged.map((item) => item.czsc_v2_shadow_rank), [3, null, 1]);
});
```

Add source assertions that the candidate table labels the value `CZSC研究` and does not sort by `czsc_v2_shadow_rank`.

- [ ] **Step 2: Run and verify RED**

```bash
cd apps/web
pnpm test
```

Expected: FAIL with missing merge/API/UI.

- [ ] **Step 3: Implement independent shadow polling**

When a formal result has `czsc_v2_job_id`, start a second poller. Merge successful/partial scores by symbol. Stop on terminal state, a new formal run, trade date change, or unmount. Shadow poll failures may show a muted research status but must not set the formal screening error or running state.

- [ ] **Step 4: Add a compact research line**

Under the existing formal Chanlun summary, render:

- `CZSC研究 82 · 影子#3` for ready score;
- `CZSC研究计算中` for pending;
- `CZSC研究数据不足` for null/partial;
- no buy/sell command wording.

Use the same rendering in desktop and mobile candidate layouts. Do not add a v2 filter or sort control in this phase.

- [ ] **Step 5: Verify and commit**

```bash
cd apps/web
pnpm test
pnpm build
git add lib/types.ts lib/api.ts lib/api.test.ts lib/czscShadow.ts lib/czscShadow.test.ts app/HomeWorkbench.tsx components/screener/CandidateResults.tsx lib/screenerDeSlop.test.ts
git commit -m "feat: display czsc shadow scores in screener"
```

Milestone 2 exit: formal results render first and retain order, `/chanlun` shows optional research markers/evidence, and rc8 failure affects neither formal UI nor execution features.

## Task 13: Build the Offline free-stockdb Dataset Pipeline

**Files:**
- Modify: `apps/api/pyproject.toml`, `apps/api/uv.lock`
- Create: `apps/api/app/providers/free_stockdb.py`
- Create: `apps/api/app/services/chanlun/research_history.py`
- Create: `apps/api/app/services/chanlun/research_dataset.py`
- Modify: `apps/api/app/services/auction_model.py`
- Create: `apps/api/tests/test_chanlun_research_history.py`
- Create: `apps/api/tests/test_chanlun_research_dataset.py`
- Modify: `apps/api/tests/test_auction_model.py`

- [ ] **Step 1: Extract and test the shared HTTP client**

Move `FreeStockDbClient` to `app/providers/free_stockdb.py` and give it a generic `FreeStockDbRequestError`. Add optional `http_client` injection for tests. Update `auction_model.py` to import the client and wrap `FreeStockDbRequestError` as its existing `AuctionModelDataError`, preserving current request parameters and user-facing error wording.

Add a minute query test:

```python
def test_minute_source_uses_stockdb_range_contract() -> None:
    http = RecordingHttpClient(payload=[_minute_row("20260710100000")])
    source = FreeStockDbResearchSource(
        base_url="http://stockdb.test:7899",
        http_client=http,
    )

    rows = source.minute_bars("600000.SH", start="20260701", end="20260710")

    assert http.requests[0].params["cmd"] == "vals"
    assert http.requests[0].params["t"] == "分钟k"
    assert http.requests[0].params["k1"] == "600000"
    assert http.requests[0].params["k2"] == "20260701000000<20260710235959"
    assert rows[0].date == "2026-07-10T10:00:00+08:00"
```

- [ ] **Step 2: Write failing candidate/data quality tests**

```python
def test_candidate_reconstruction_uses_only_prior_20_sessions() -> None:
    candidates = reconstruct_candidates(_daily_market_rows(), trade_date="2026-07-10")

    assert all(item.last_limit_up_date <= "2026-07-10" for item in candidates)
    assert all("ST" not in item.name.upper() for item in candidates)
    assert candidates[0].limit_up_hits_20d >= candidates[-1].limit_up_hits_20d


def test_dataset_manifest_records_checksums_and_rejects_adjustment_break(tmp_path: Path) -> None:
    builder = ResearchDatasetBuilder(source=FakeHistorySource(with_adjustment_break=True))
    manifest = builder.build(start="2026-01-01", end="2026-06-30", output=tmp_path)

    assert manifest.quality.adjustment_mismatch_count > 0
    assert all(part.sha256.startswith("sha256:") for part in manifest.partitions)
    assert not any(sample.symbol == "BROKEN.SZ" for sample in manifest.samples)
```

- [ ] **Step 3: Run and verify RED**

```bash
cd apps/api
uv run pytest tests/test_chanlun_research_history.py tests/test_chanlun_research_dataset.py tests/test_auction_model.py -q
```

Expected: FAIL because historical source and builder are absent.

- [ ] **Step 4: Add the offline dependency group**

Add `research` to the existing `[dependency-groups]` table:

```toml
research = ["pyarrow>=20.0.0,<21.0.0"]
```

Keep it out of Docker export commands. Refresh the main lock with `uv lock --project apps/api`.

- [ ] **Step 5: Implement source normalization and candidate reconstruction**

Use raw HTTP `vals` requests against tables `日k` and `分钟k`; never import the Windows `.pyd`. Normalize date, code, OHLCV, amount, name, ST, and market-cap fields. Mark source adjustment as `source_qfq` only when daily/minute continuity checks pass.

Reconstruct the 20-session candidate pool from daily rows available by the decision date. Exclude ST, ETF/non-A prefixes, suspended rows, and listings younger than the existing rule. For the five-year range, use thresholds 19.5% for `300/301/688`, 29.5% for Beijing prefixes, and 9.5% otherwise; store every qualifying date as evidence. Apply current static filters and current baseline analysis only with data ending at the decision date.

Return a typed `ResearchCandidateRecord` containing the underlying `StrongStockCandidate`, `last_limit_up_date`, `limit_up_hits_20d`, baseline rank inputs, and decision date. The test fields above refer to this record, not new fields on `StrongStockCandidate`.

- [ ] **Step 6: Write candidate-only Parquet partitions**

Persist daily data and only the 5m history needed by the 20-60 candidate enhancement pool, partitioned by symbol/month. Derive 30m and 60m using the existing Shanghai-session aggregator at validation time. Manifest rows must record source, capture time, adjustment, row count, date bounds, SHA-256, missing/duplicate/invalid counts, and all rule versions.

Use temp files plus atomic rename. Re-running the same source partition with a matching hash must reuse it; a changed hash creates a new dataset ID rather than overwriting a frozen dataset.

- [ ] **Step 7: Verify and commit**

```bash
cd apps/api
uv lock
uv run --group research pytest tests/test_chanlun_research_history.py tests/test_chanlun_research_dataset.py tests/test_auction_model.py -q
git add pyproject.toml uv.lock app/providers/free_stockdb.py app/services/chanlun/research_history.py app/services/chanlun/research_dataset.py app/services/auction_model.py tests/test_chanlun_research_history.py tests/test_chanlun_research_dataset.py tests/test_auction_model.py
git commit -m "feat: build frozen czsc research datasets"
```

## Task 14: Implement Walk-Forward Validation and Promotion Gates

**Files:**
- Create: `apps/api/app/services/chanlun/research_validation.py`
- Create: `apps/api/tests/test_chanlun_research_validation.py`

- [ ] **Step 1: Write failing fold and leakage tests**

```python
def test_five_year_windows_use_24_6_6_and_never_overlap_forward() -> None:
    folds = build_walk_forward_folds(date(2021, 7, 1), date(2026, 6, 30))

    assert folds[0].development_months == 24
    assert folds[0].validation_months == 6
    assert folds[0].test_months == 6
    assert all(fold.development_end < fold.validation_start <= fold.validation_end < fold.test_start for fold in folds)
    assert all(left.test_start < right.test_start for left, right in pairwise(folds))


def test_sample_builder_enters_next_open_and_exits_third_close() -> None:
    sample = build_outcome(_decision("2026-07-06"), _future_daily_bars())

    assert sample.entry_at == "2026-07-07T09:30:00+08:00"
    assert sample.exit_at == "2026-07-09T15:00:00+08:00"
    assert sample.net_return_pct == pytest.approx(sample.gross_return_pct - 0.20)
```

Add a test that no worker input contains a bar later than its decision time and an untradeable one-price limit-up is recorded as unfilled.

- [ ] **Step 2: Write failing metrics and gate tests**

```python
def test_profit_loss_ratio_uses_average_win_over_absolute_average_loss() -> None:
    metrics = summarize_returns([3.0, 1.0, -1.0, -1.0])
    assert metrics.win_rate_pct == 50.0
    assert metrics.profit_loss_ratio == 2.0


def test_promotion_requires_every_approved_gate() -> None:
    decision = evaluate_promotion(_passing_metrics())
    assert decision.recommendation == "suggest_promotion"

    for field in ["sample_count", "win_rate_pct", "profit_loss_ratio", "excess_return", "max_drawdown", "recent_decay", "leakage"]:
        assert evaluate_promotion(_failing_metrics(field)).recommendation == "keep_shadow"
```

- [ ] **Step 3: Run and verify RED**

```bash
cd apps/api
uv run --group research pytest tests/test_chanlun_research_validation.py -q
```

Expected: FAIL because validation functions are absent.

- [ ] **Step 4: Implement frozen-score walk-forward evaluation**

For each decision date:

1. Load the frozen baseline candidate order and only bars ending at 15:00.
2. Request rc8 evidence with the production catalog and calculate `czsc-score-v2-rule-1`.
3. Preserve baseline order separately.
4. Build v2 order using eligible, score, then baseline rank.
5. Simulate Top3, Top5, and Top10 with identical tradability and 20 bps cost.
6. Put only test-window trades into sample-out metrics.

Portfolio logic creates one equal-weight daily tranche, holds it for three sessions, and divides capital equally among concurrently open tranches. Calculate drawdown from chronological equity, not average per-trade adverse excursion.

- [ ] **Step 5: Implement exact gates**

Return `suggest_promotion` only when sample-out count is at least 300, 3-day net win rate is greater than 50%, profit/loss ratio is at least 1.3, Top5 and Top10 net returns both exceed baseline, both maximum drawdowns are no worse than baseline, recent six-month net return is positive, recent win rate is no more than 5 percentage points below prior sample-out, and every leakage/data check passes.

- [ ] **Step 6: Verify and commit**

```bash
cd apps/api
uv run --group research pytest tests/test_chanlun_research_validation.py -q
git add app/services/chanlun/research_validation.py tests/test_chanlun_research_validation.py
git commit -m "feat: validate czsc shadow strategy walk forward"
```

## Task 15: Add Reproducible CLI, Reports, Full Verification, and Documentation

**Files:**
- Create: `apps/api/app/services/chanlun/research_report.py`
- Create: `apps/api/tests/test_chanlun_research_report.py`
- Create: `scripts/czsc-research.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing report reproducibility tests**

```python
def test_report_payload_and_sample_hashes_are_reproducible(tmp_path: Path) -> None:
    first = write_validation_report(_validation_result(), output=tmp_path / "first", generated_at="2026-07-13T10:00:00+08:00")
    second = write_validation_report(_validation_result(), output=tmp_path / "second", generated_at="2026-07-13T11:00:00+08:00")

    assert first.metrics_sha256 == second.metrics_sha256
    assert first.samples_sha256 == second.samples_sha256
    assert first.html_sha256 != second.html_sha256
    assert (tmp_path / "first/checksums.sha256").exists()
```

Add a subprocess test that `python scripts/czsc-research.py --help` lists `build-dataset` and `validate`, and that `validate` refuses a manifest with a checksum mismatch before invoking rc8.

- [ ] **Step 2: Run and verify RED**

```bash
cd apps/api
uv run --group research pytest tests/test_chanlun_research_report.py -q
```

Expected: FAIL because writer and CLI are absent.

- [ ] **Step 3: Implement deterministic outputs**

Write `manifest.json`, `metrics.json`, `folds.json`, `samples.csv.gz`, `report.html`, and `checksums.sha256`. JSON must use sorted keys and stable numeric rounding. Sort sample rows by decision date, symbol, and baseline rank. Use gzip `mtime=0`. Exclude HTML generation time from metric/sample hashes.

The HTML report must show dataset quality, fold table, Top3/5/10 baseline versus v2 metrics, win rate, profit/loss ratio, cumulative curve, drawdown, recent six-month decay, failed gates, and the explicit recommendation. It must not contain order-execution controls.

- [ ] **Step 4: Implement the two CLI commands**

Use stdlib `argparse` with subcommands:

```text
build-dataset --start --end --output [--free-stockdb-base-url]
validate --dataset --output [--round-trip-cost-bps 20] [--worker-python]
```

Defaults read existing settings/environment; the LAN address is never hardcoded in this new code. `validate` performs checksum verification and makes no network requests.

At script startup, resolve the repository root from `Path(__file__)` and prepend `repo_root / "apps/api"` to `sys.path` before importing `app`, so the documented repo-root command works without a global package install.

- [ ] **Step 5: Update README and run focused tests**

Document the dual-engine boundary, `/chanlun` research markers, nullable shadow scores, the fact that formal ranking is unchanged, rc8 local setup, offline free-stockdb role, and the two CLI examples.

Run:

```bash
cd apps/api
uv run --group research pytest tests/test_chanlun_research_*.py tests/test_chanlun_rc8_client.py tests/test_chanlun_shadow_service.py -q
uv run --group research python ../../scripts/czsc-research.py --help
cd ../web
pnpm test
pnpm build
```

Expected: all pass.

- [ ] **Step 6: Run full backend, container, performance, and visual verification**

```bash
cd apps/api && uv run pytest -q
cd ../web && pnpm test && pnpm build
cd ../..
docker build -t strong-stock-screener:czsc-shadow .
docker run --rm strong-stock-screener:czsc-shadow /opt/czsc-rc8-venv/bin/python -c "import importlib.metadata; assert importlib.metadata.version('czsc') == '1.0.0rc8'"
uv run --project apps/api python scripts/benchmark-czsc-rc8.py --symbols 60 --bars 480 --worker-python apps/api/rc8-worker/.venv/bin/python --json-output /tmp/czsc-rc8-60.json
```

Expected: all tests/builds pass; 60-symbol benchmark is under 30 seconds and worker RSS is under 1 GiB. If performance misses the gate, keep the feature disabled for shadow batches and optimize before release; do not relax the gate in code.

Start the local API/web using the repository's established commands, then run:

```bash
SMOKE_UI_BASE_URL=http://127.0.0.1:3110 pnpm --dir apps/web run smoke:ui
SMOKE_UI_BASE_URL=http://127.0.0.1:3110 node scripts/visual-qa-chanlun.mjs
```

Expected: desktop/mobile screenshots are nonblank, no overflow or toolbar/marker overlap is reported, and `/chanlun` remains usable when the rc8 worker is deliberately stopped.

- [ ] **Step 7: Commit the final milestone**

```bash
git add apps/api/app/services/chanlun/research_report.py apps/api/tests/test_chanlun_research_report.py scripts/czsc-research.py README.md
git commit -m "feat: report czsc five-year shadow validation"
```

## Final Review Checklist

- [ ] `git diff --check` passes.
- [ ] `rg -n "T[B]D|T[O]DO|F[I]XME"` finds no new placeholders in implementation or docs.
- [ ] Main API still imports `czsc==0.10.12`; only the worker environment imports rc8.
- [ ] Formal screening order is byte-for-byte unchanged in regression fixtures.
- [ ] No `czsc_score_v2` field is read by formal rank keys, filters, alerts, or paper orders.
- [ ] Every score input is closed, fresh, adjustment-compatible, and tied to an input hash.
- [ ] Worker names and params come only from `research_catalog.json`.
- [ ] Full timeline and prefix calculations agree on first-visible signal time.
- [ ] Workbench formal K-line loads when the worker is missing, slow, malformed, or killed.
- [ ] Runtime SQLite retention and offline artifacts are separate.
- [ ] Five-year validation reads only frozen files after dataset creation.
- [ ] Report recommendation remains advisory and cannot toggle runtime behavior.
- [ ] Backend, frontend, Docker, benchmark, smoke UI, and visual QA evidence is recorded before merge.
