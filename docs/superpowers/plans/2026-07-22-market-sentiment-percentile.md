# Market Sentiment Percentile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic five-factor market sentiment percentile, reproducible historical validation, and one cached OpenAI-compatible LLM interpretation per completed trading day to the production `/sentiment` workbench.

**Architecture:** The FastAPI backend computes the statistic from `000985.SH` TickFlow daily bars, persists a versioned 500-point snapshot, and exposes independent percentile and analysis APIs. A separate analysis service combines the fixed score with existing cached market context, validates structured LLM output, and is invoked after `15:15 Asia/Shanghai` by an application-lifecycle sampler. The production Vue/Soybean frontend loads the statistical panel independently from existing short-term sentiment requests and uses the shared ECharts component.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx, pytest, Vue 3.5, TypeScript, Vite, Vitest, Ant Design Vue, ECharts 6, Docker.

## Global Constraints

- Benchmark is CSI All Share `000985.SH`, loaded through the existing `TickFlowDailyKlineProvider` with about `1020` daily bars.
- Only completed daily bars are valid. Before `15:10 Asia/Shanghai`, exclude the current local trading date.
- Use exactly five equal-weight factors: volume percentile, 5-day index movement, 500-day price position, directional 5-day amplitude, and `MA5(amount) / MA20(amount) - 1`.
- Percentile windows contain exactly `500` observations and use midrank: `(less + 0.5 * equal) / 500 * 100`.
- Do not renormalize weights when a factor is missing. A date with any missing factor has no composite score.
- Keep at most the latest `500` complete composite points and version the formula as `market-sentiment-percentile-v1`.
- Statistical score, factor weights, level, and existing trade permission remain deterministic and cannot be changed by the LLM.
- Generate one LLM interpretation per completed trade date and provider/model/input hash. Reuse the existing `ai_analysis` OpenAI-compatible settings and never expose the unmasked API key.
- Do not emit deterministic fallback prose as AI output. `unconfigured` and `failed` are visible unmet-analysis states; the statistical chart remains usable.
- LLM output cannot recommend individual stocks, position percentages, simulated orders, or automatic trades.
- Do not add NumPy, pandas, machine-learning, GPU, or chart dependencies.
- Modify the production frontend in `apps/web-vue`; do not duplicate the feature in the retired compatibility frontend under `apps/web`.
- Preserve all existing short-term sentiment metrics, trade permission, main sectors, intraday alerts, and their request failure boundaries.

---

### Task 1: Deterministic Five-Factor Calculator

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/services/market_sentiment_percentile.py`
- Create: `apps/api/tests/market_sentiment_fixtures.py`
- Create: `apps/api/tests/test_market_sentiment_percentile.py`

**Interfaces:**
- Consumes: `app.models.KlineBar` sorted or unsorted daily bars.
- Produces: `calculate_sentiment_percentile(bars: list[KlineBar]) -> list[SentimentPercentilePoint]`, `sentiment_percentile_level(score: float) -> SentimentPercentileLevel`, and Pydantic response types used by every later task.

- [ ] **Step 1: Add failing formula, warmup, tie, and no-lookahead tests**

```python
from datetime import date, timedelta

from app.models import KlineBar


def make_test_bar(index: int, *, close: float | None = None, amount: float | None = None) -> KlineBar:
    price = close if close is not None else 100 + index * 0.05 + (index % 7 - 3) * 0.2
    return KlineBar(
        date=(date(2022, 1, 1) + timedelta(days=index)).isoformat(),
        open=price - 0.2,
        high=price + 1.0,
        low=price - 1.0,
        close=price,
        volume=1_000_000 + index,
        amount=amount if amount is not None else 100_000_000 + index * 100_000,
    )


def make_test_bars(count: int) -> list[KlineBar]:
    return [make_test_bar(index) for index in range(count)]


def percentile_response_fixture() -> SentimentPercentileResponse:
    factor = SentimentPercentileFactor(score=50, raw_value=0, raw_unit="%")
    point = SentimentPercentilePoint(
        trade_date="2026-07-21",
        score=50,
        level="中性",
        factors=SentimentPercentileFactors(
            volume=factor,
            index_move_5d=factor,
            price_position=factor,
            amplitude_5d=factor,
            volume_trend=factor,
        ),
    )
    return SentimentPercentileResponse(
        weights={key: 0.2 for key in WEIGHTS},
        latest_complete_trade_date=point.trade_date,
        selected_trade_date=point.trade_date,
        selected=point,
        history=[point],
        source_status=[],
        generated_at="2026-07-22T15:20:00+08:00",
    )


def test_midrank_counts_ties_in_the_middle() -> None:
    values = [1.0] * 250 + [2.0] * 250
    assert midrank_percentile(values, 2.0) == 75.0


def test_calculator_requires_full_factor_warmup() -> None:
    bars = make_test_bars(1020)
    points = calculate_sentiment_percentile(bars)
    assert len(points) == 502
    assert points[0].trade_date == bars[518].date
    assert len(points[-500:]) == 500


def test_future_bar_changes_do_not_change_prior_points() -> None:
    bars = make_test_bars(1020)
    baseline = calculate_sentiment_percentile(bars)
    mutated = [*bars, make_test_bar(1021, close=9999, amount=9_999_999_999)]
    by_date = {point.trade_date: point for point in calculate_sentiment_percentile(mutated)}
    assert all(by_date[point.trade_date] == point for point in baseline)


@pytest.mark.parametrize(
    ("score", "level"),
    [(0, "冰点"), (19.9, "冰点"), (20, "偏冷"), (40, "中性"), (60, "偏热"), (80, "过热")],
)
def test_level_boundaries(score: float, level: str) -> None:
    assert sentiment_percentile_level(score) == level


@pytest.mark.parametrize("direction", [-1, 0, 1])
def test_directional_amplitude_preserves_return_direction(direction: int) -> None:
    assert directional_amplitude(100, 110, 90, 100 + direction) * direction >= 0
```

Add a case proving that a zero 500-day high/low range makes that factor unavailable and skips only the affected composite date. Add `pytest.raises(ValueError)` cases for non-positive OHLC/amount, plus assertions that duplicate dates keep the last record and `WEIGHTS == {key: 0.2 for key in WEIGHTS}`.

- [ ] **Step 2: Run the new test module and verify it fails**

Run: `cd apps/api && uv run pytest tests/test_market_sentiment_percentile.py -q`

Expected: collection or import failure because the new calculator and models do not exist.

- [ ] **Step 3: Add the exact domain models**

Add these contracts to `app/models.py`:

```python
SentimentPercentileLevel = Literal["冰点", "偏冷", "中性", "偏热", "过热"]
SentimentPercentileCacheStatus = Literal["fresh", "cached", "stale"]


class SentimentPercentileFactor(BaseModel):
    score: float = Field(ge=0, le=100)
    raw_value: float
    raw_unit: str


class SentimentPercentileFactors(BaseModel):
    volume: SentimentPercentileFactor
    index_move_5d: SentimentPercentileFactor
    price_position: SentimentPercentileFactor
    amplitude_5d: SentimentPercentileFactor
    volume_trend: SentimentPercentileFactor


class SentimentPercentilePoint(BaseModel):
    trade_date: str
    score: float = Field(ge=0, le=100)
    level: SentimentPercentileLevel
    factors: SentimentPercentileFactors


class SentimentPercentileResponse(BaseModel):
    model_version: str = "market-sentiment-percentile-v1"
    benchmark_symbol: str = "000985.SH"
    benchmark_name: str = "中证全指"
    window_size: int = 500
    weights: dict[str, float]
    latest_complete_trade_date: str
    selected_trade_date: str | None = None
    selected: SentimentPercentilePoint | None = None
    history: list[SentimentPercentilePoint] = Field(default_factory=list)
    cache_status: SentimentPercentileCacheStatus = "fresh"
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str
    notes: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Implement the calculator without data-frame dependencies**

Use these constants and formulas in `market_sentiment_percentile.py`:

```python
MODEL_VERSION = "market-sentiment-percentile-v1"
WINDOW = 500
WEIGHTS = {
    "volume": 0.2,
    "index_move_5d": 0.2,
    "price_position": 0.2,
    "amplitude_5d": 0.2,
    "volume_trend": 0.2,
}


def midrank_percentile(values: list[float], current: float) -> float:
    if len(values) != WINDOW:
        raise ValueError(f"percentile window must contain {WINDOW} values")
    less = sum(value < current for value in values)
    equal = sum(value == current for value in values)
    return round((less + 0.5 * equal) / WINDOW * 100, 1)


def sentiment_percentile_level(score: float) -> SentimentPercentileLevel:
    if score < 20:
        return "冰点"
    if score < 40:
        return "偏冷"
    if score < 60:
        return "中性"
    if score < 80:
        return "偏热"
    return "过热"
```

Normalize by date, reject invalid bars, precompute amount, 5-day return, directional amplitude, and volume-trend arrays, and loop from index `518`. For each index, calculate each percentile from exactly its previous 499 raw values plus the current value. Round factor scores and the equal-weight composite to one decimal.

- [ ] **Step 5: Run calculator tests**

Run: `cd apps/api && uv run pytest tests/test_market_sentiment_percentile.py -q`

Expected: all calculator tests pass.

- [ ] **Step 6: Commit the calculator**

```bash
git add apps/api/app/models.py apps/api/app/services/market_sentiment_percentile.py apps/api/tests/market_sentiment_fixtures.py apps/api/tests/test_market_sentiment_percentile.py
git commit -m "feat: calculate market sentiment percentile"
```

---

### Task 2: Versioned Store And Cache-Aware Service

**Files:**
- Create: `apps/api/app/services/market_sentiment_percentile_store.py`
- Create: `apps/api/app/services/market_sentiment_percentile_service.py`
- Create: `apps/api/tests/test_market_sentiment_percentile_service.py`

**Interfaces:**
- Consumes: a provider exposing `get_klines(symbol: str, count: int) -> list[KlineBar]` and the calculator from Task 1.
- Produces: `MarketSentimentPercentileService.get(as_of: str | None, refresh: bool, now: datetime | None) -> SentimentPercentileResponse` and `MarketSentimentPercentileStore.load()/save()`.

- [ ] **Step 1: Write failing service tests**

Cover these exact behaviors:

```python
class FakeProvider:
    source_name = "fixture TickFlow"

    def __init__(self, bars: list[KlineBar]) -> None:
        self.bars = bars
        self.calls = 0
        self.error: Exception | None = None

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert symbol == "000985.SH"
        return self.bars[-count:]


def service_for(tmp_path: Path, provider: FakeProvider) -> MarketSentimentPercentileService:
    return MarketSentimentPercentileService(
        provider=provider,
        store=MarketSentimentPercentileStore(tmp_path),
    )


def test_before_1510_excludes_current_local_date(tmp_path: Path) -> None:
    bars = make_test_bars(1020)
    bars[-1] = bars[-1].model_copy(update={"date": "2026-07-22"})
    bars[-2] = bars[-2].model_copy(update={"date": "2026-07-21"})
    provider = FakeProvider(bars)
    service = service_for(tmp_path, provider)
    result = service.get(now=datetime.fromisoformat("2026-07-22T15:09:00+08:00"))
    assert result.latest_complete_trade_date == "2026-07-21"


def test_failed_refresh_returns_stale_successful_snapshot(tmp_path: Path) -> None:
    provider = FakeProvider(make_test_bars(1020))
    service = service_for(tmp_path, provider)
    cached = service.get(refresh=True)
    provider.error = RuntimeError("offline")
    stale = service.get(refresh=True)
    assert stale.cache_status == "stale"
    assert stale.history == cached.history
    assert "offline" not in stale.notes


def test_as_of_only_slices_existing_history(tmp_path: Path) -> None:
    result = service_for(tmp_path, FakeProvider(make_test_bars(1020))).get(as_of="2024-09-01")
    assert all(point.trade_date <= "2024-09-01" for point in result.history)
    assert result.selected == result.history[-1]


def test_as_of_before_cached_range_returns_explicit_empty_selection(tmp_path: Path) -> None:
    result = service_for(tmp_path, FakeProvider(make_test_bars(1020))).get(as_of="2022-01-02")
    assert result.history == []
    assert result.selected is None
    assert result.selected_trade_date is None


def test_same_day_cache_hit_does_not_call_provider_twice(tmp_path: Path) -> None:
    provider = FakeProvider(make_test_bars(1020))
    service = service_for(tmp_path, provider)
    now = datetime.fromisoformat("2026-07-22T16:00:00+08:00")
    service.get(refresh=True, now=now)
    service.get(now=now)
    assert provider.calls == 1


def test_corrupt_or_wrong_version_snapshot_is_ignored(tmp_path: Path) -> None:
    store = MarketSentimentPercentileStore(tmp_path)
    store.root_dir.mkdir(parents=True)
    store.latest_path.write_text("{bad json", encoding="utf-8")
    assert store.load() is None
```

For atomic replacement, monkeypatch `Path.replace` and assert the source suffix is `.json.tmp`; for version mismatch, write a valid fixture with `model_version="market-sentiment-percentile-v0"`; for insufficient history, use `FakeProvider(make_test_bars(518))` and assert `StrongStockDataUnavailable`; for source sanitization, raise an exception containing a fake key and assert the key is absent from response notes/status.

- [ ] **Step 2: Run service tests and verify failure**

Run: `cd apps/api && uv run pytest tests/test_market_sentiment_percentile_service.py -q`

Expected: import failure for the missing store/service modules.

- [ ] **Step 3: Implement the atomic store**

```python
class MarketSentimentPercentileStore:
    def __init__(self, data_dir: Path) -> None:
        self.root_dir = data_dir / "sentiment-percentile"
        self.latest_path = self.root_dir / "latest.json"
        self._lock = RLock()

    def load(self) -> SentimentPercentileResponse | None:
        with self._lock:
            if not self.latest_path.exists():
                return None
            try:
                value = SentimentPercentileResponse.model_validate_json(
                    self.latest_path.read_text(encoding="utf-8")
                )
            except Exception:
                return None
            return value if value.model_version == MODEL_VERSION else None

    def save(self, value: SentimentPercentileResponse) -> SentimentPercentileResponse:
        with self._lock:
            self.root_dir.mkdir(parents=True, exist_ok=True)
            temporary = self.latest_path.with_suffix(".json.tmp")
            temporary.write_text(value.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(self.latest_path)
            return value
```

- [ ] **Step 4: Implement completed-bar filtering and service behavior**

`filter_completed_daily_bars` must use `ZoneInfo("Asia/Shanghai")`, remove the local current-date bar before `15:10`, and retain the latest valid prior bar on weekends/holidays. The service requests `count=1020`, keeps `points[-500:]`, writes only successful results, returns a deep copy, and applies `as_of` only after loading/calculating the canonical history. On refresh failure, copy the last snapshot with `cache_status="stale"`, preserve its real data date, and add a sanitized source-status failure.

- [ ] **Step 5: Run service and calculator tests**

Run: `cd apps/api && uv run pytest tests/test_market_sentiment_percentile.py tests/test_market_sentiment_percentile_service.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit the store and service**

```bash
git add apps/api/app/services/market_sentiment_percentile_store.py apps/api/app/services/market_sentiment_percentile_service.py apps/api/tests/test_market_sentiment_percentile_service.py
git commit -m "feat: persist sentiment percentile snapshots"
```

---

### Task 3: Statistical Percentile API

**Files:**
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_market_sentiment_percentile_api.py`

**Interfaces:**
- Consumes: `MarketSentimentPercentileService` from Task 2.
- Produces: `GET /api/short-term/sentiment/percentile?as_of=<date>&refresh=<bool>`.

- [ ] **Step 1: Write failing API contract tests**

```python
class FakePercentileService:
    def __init__(self, response: SentimentPercentileResponse) -> None:
        self.response = response
        self.calls: list[tuple[str | None, bool]] = []

    def get(self, as_of: str | None = None, refresh: bool = False, now=None):
        self.calls.append((as_of, refresh))
        return self.response


def test_percentile_api_returns_selected_history_and_metadata() -> None:
    fixture = percentile_response_fixture()
    app.state.market_sentiment_percentile_service = FakePercentileService(fixture)
    with TestClient(app) as client:
        response = client.get(
            "/api/short-term/sentiment/percentile",
            params={"as_of": "2026-07-21", "refresh": "false"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["model_version"] == "market-sentiment-percentile-v1"
    assert payload["benchmark_symbol"] == "000985.SH"
    assert payload["selected_trade_date"] == "2026-07-21"


def test_percentile_api_rejects_invalid_date() -> None:
    with TestClient(app) as client:
        response = client.get("/api/short-term/sentiment/percentile?as_of=2026-99-99")
    assert response.status_code == 422
```

Add a `RaisingPercentileService(StrongStockDataUnavailable("unavailable"))` fixture and assert `503`; call with `refresh=true` and assert the fake service recorded `(None, True)`.

- [ ] **Step 2: Run the API tests and verify failure**

Run: `cd apps/api && uv run pytest tests/test_market_sentiment_percentile_api.py -q`

Expected: `404` for the missing endpoint.

- [ ] **Step 3: Wire the factory and endpoint**

Add `_market_sentiment_percentile_store()` and `_market_sentiment_percentile_service()` factories that honor `app.state` injections and use `Path(getattr(app.state, "runs_dir", get_settings().data_dir))`. Add a typed endpoint:

```python
@app.get(
    "/api/short-term/sentiment/percentile",
    response_model=SentimentPercentileResponse,
)
def get_market_sentiment_percentile(
    as_of: date | None = None,
    refresh: bool = False,
) -> SentimentPercentileResponse:
    try:
        return _market_sentiment_percentile_service().get(
            as_of=as_of.isoformat() if as_of else None,
            refresh=refresh,
        )
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
```

- [ ] **Step 4: Run API and existing sentiment tests**

Run: `cd apps/api && uv run pytest tests/test_market_sentiment_percentile_api.py tests/test_short_term_sentiment.py -q`

Expected: all tests pass and existing sentiment routes remain unchanged.

- [ ] **Step 5: Commit the statistical API**

```bash
git add apps/api/app/main.py apps/api/tests/test_market_sentiment_percentile_api.py
git commit -m "feat: expose sentiment percentile API"
```

---

### Task 4: Reproducible Walk-Forward Validation CLI

**Files:**
- Create: `apps/api/app/services/market_sentiment_validation.py`
- Create: `apps/api/scripts/run_market_sentiment_validation.py`
- Create: `apps/api/tests/test_market_sentiment_validation.py`

**Interfaces:**
- Consumes: the Task 1 calculator and completed daily bars.
- Produces: `validate_sentiment_percentile(bars) -> SentimentValidationReport`, `/app/data/sentiment-percentile/validation-v1.json`, and an adjacent Markdown report.

- [ ] **Step 1: Write failing validation tests**

Use deterministic bars and assert:

```python
report = validate_sentiment_percentile(make_test_bars(1020))
assert report.model_version == "market-sentiment-percentile-v1"
assert report.horizons == [5, 10, 20]
assert sum(bucket.sample_count for bucket in report.buckets) == len(report.samples)
assert report.buckets[0].windows[0].future_data_end <= report.data_end
```

Mutate only bars after one scored date and assert that date's score is unchanged while its forward validation label may change. Assert mean, median, positive rate, minimum future close drawdown, level-duration averages, and explicit insufficient-sample notes.

- [ ] **Step 2: Run validation tests and verify failure**

Run: `cd apps/api && uv run pytest tests/test_market_sentiment_validation.py -q`

Expected: import failure for the new validation service.

- [ ] **Step 3: Implement validation from calculated historical points**

Define the report contracts in `market_sentiment_validation.py`:

```python
class SentimentValidationWindow(BaseModel):
    horizon: Literal[5, 10, 20]
    sample_count: int
    mean_return_pct: float | None
    median_return_pct: float | None
    positive_rate_pct: float | None
    mean_max_drawdown_pct: float | None
    future_data_end: str


class SentimentValidationBucket(BaseModel):
    level: SentimentPercentileLevel
    sample_count: int
    average_duration_days: float | None
    windows: list[SentimentValidationWindow]


class SentimentValidationReport(BaseModel):
    model_version: str
    benchmark_symbol: str
    data_start: str
    data_end: str
    horizons: list[Literal[5, 10, 20]]
    samples: list[dict[str, object]]
    buckets: list[SentimentValidationBucket]
    conclusion: str
    notes: list[str]
    generated_at: str
```

For each point/date index and each horizon `h`, compute:

```python
forward_return_pct = (bars[index + h].close / bars[index].close - 1) * 100
max_drawdown_pct = (
    min(bar.close for bar in bars[index + 1 : index + h + 1]) / bars[index].close - 1
) * 100
```

Group by the five fixed levels, report sample count, mean/median return, positive-rate percentage, mean maximum drawdown, and contiguous average level duration. Do not pass any forward label back into the calculator.

- [ ] **Step 4: Implement the CLI and atomic report output**

The script loads effective runtime settings, requests `000985.SH` with `count=1020`, filters completed bars, writes JSON to `${data_dir}/sentiment-percentile/validation-v1.json`, writes Markdown to `validation-v1.md`, and supports `--output-dir` and `--as-of`. It exits non-zero on insufficient bars or provider failure.

- [ ] **Step 5: Run tests and CLI help**

Run:

```bash
cd apps/api
uv run pytest tests/test_market_sentiment_validation.py -q
uv run python scripts/run_market_sentiment_validation.py --help
```

Expected: tests pass and help lists `--output-dir` and `--as-of`.

- [ ] **Step 6: Commit validation**

```bash
git add apps/api/app/services/market_sentiment_validation.py apps/api/scripts/run_market_sentiment_validation.py apps/api/tests/test_market_sentiment_validation.py
git commit -m "feat: validate sentiment percentile history"
```

---

### Task 5: Strict LLM Analysis, Input Hash, And Analysis Store

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/services/ai_model_analysis.py`
- Create: `apps/api/app/services/market_sentiment_analysis.py`
- Create: `apps/api/app/services/market_sentiment_analysis_store.py`
- Create: `apps/api/tests/test_market_sentiment_analysis.py`

**Interfaces:**
- Consumes: `SentimentPercentilePoint`, `SentimentSummaryResponse | None`, `SentimentDecisionResponse | None`, validation JSON, and `EffectiveAiAnalysisSettings`.
- Produces: `build_sentiment_analysis_input(...)`, `hash_sentiment_analysis_input(...)`, and `MarketSentimentAnalysisService.generate(..., force=False) -> SentimentPercentileAnalysisResponse`.

- [ ] **Step 1: Add failing input, schema, retry, and cache tests**

Test that the canonical input contains only the allowlisted fields and source dates; the same sorted JSON has the same SHA-256; missing auxiliary context remains explicit; a successful provider/model/hash result is reused; changed input or model generates again; malformed JSON, an unknown posture, and missing fields are retried exactly three times; and no output field can override score, level, weights, or trade permission.

```python
assert response.status == "ready"
assert response.result.risk_posture == "defensive"
assert http_client.post.call_count == 1
assert service.generate(input_payload, config).input_hash == response.input_hash
assert http_client.post.call_count == 1
```

- [ ] **Step 2: Run analysis tests and verify failure**

Run: `cd apps/api && uv run pytest tests/test_market_sentiment_analysis.py -q`

Expected: import failure for the missing analysis modules/models.

- [ ] **Step 3: Add strict Pydantic contracts**

Add:

```python
SentimentAnalysisStatus = Literal[
    "not_generated", "unconfigured", "pending", "ready", "failed"
]
SentimentRiskPosture = Literal["attack", "balanced", "defensive", "wait"]


class SentimentAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    market_conclusion: str = Field(min_length=1, max_length=240)
    key_drivers: list[str] = Field(min_length=2, max_length=4)
    factor_divergence: str = Field(min_length=1, max_length=240)
    historical_context: str = Field(min_length=1, max_length=240)
    risk_posture: SentimentRiskPosture
    next_session_watch: list[str] = Field(min_length=2, max_length=4)
    risk_note: str = Field(min_length=1, max_length=160)


class SentimentPercentileAnalysisResponse(BaseModel):
    trade_date: str
    status: SentimentAnalysisStatus
    model_version: str = "market-sentiment-percentile-v1"
    provider: str | None = None
    llm_model: str | None = None
    input_hash: str | None = None
    attempts: int = 0
    requested_at: str | None = None
    completed_at: str | None = None
    retry_after: str | None = None
    error: str | None = None
    result: SentimentAnalysisResult | None = None
```

Validate that each driver and watch condition contains at least one ASCII digit so the output cites an input number or threshold.

- [ ] **Step 4: Export the existing generic chat parsers**

Rename `_extract_chat_content` to `extract_chat_content` and `_extract_json_object` to `extract_json_object` in `ai_model_analysis.py`, update internal callers, and retain existing behavior. This avoids duplicating response parsing in the new analyzer.

- [ ] **Step 5: Implement allowlisted input and canonical hashing**

The input object contains `trade_date`, `percentile` with five factors, `score_change_1d/5d`, zone transitions, market breadth/limits/boards/seal rate/turnover, at most five main sectors without stock symbols, and validation sample counts/conclusion. Serialize using:

```python
canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

- [ ] **Step 6: Implement atomic per-date analysis storage and three-attempt generation**

Store records at `sentiment-percentile/analysis/YYYY-MM-DD.json` using temporary-file replacement. Before network I/O, persist `pending`. Send low-temperature JSON chat completions with a system instruction that forbids changing the statistic, naming stocks, position sizing, orders, or inventing missing values. Parse and validate `SentimentAnalysisResult`; on success persist `ready`; after three failures persist `failed` with a sanitized exception class/message and `retry_after` 30 minutes later. Return `unconfigured` without network I/O when `enabled` is false or the key is absent. Cache hits require matching trade date, model version, provider, LLM model, and input hash.

- [ ] **Step 7: Run new and existing AI tests**

Run: `cd apps/api && uv run pytest tests/test_market_sentiment_analysis.py tests/test_model_maintenance.py -q`

Expected: all tests pass, including existing model-maintenance analysis parsing.

- [ ] **Step 8: Commit the analysis core**

```bash
git add apps/api/app/models.py apps/api/app/services/ai_model_analysis.py apps/api/app/services/market_sentiment_analysis.py apps/api/app/services/market_sentiment_analysis_store.py apps/api/tests/test_market_sentiment_analysis.py
git commit -m "feat: generate daily LLM sentiment analysis"
```

---

### Task 6: Analysis APIs And 15:15 Daily Sampler

**Files:**
- Modify: `apps/api/app/main.py`
- Create: `apps/api/app/services/market_sentiment_analysis_sampler.py`
- Create: `apps/api/tests/test_market_sentiment_analysis_api.py`
- Create: `apps/api/tests/test_market_sentiment_analysis_sampler.py`

**Interfaces:**
- Consumes: percentile service, analysis service/store, existing sentiment snapshot store, `build_sentiment_decision`, and effective `ai_analysis` settings.
- Produces: analysis `GET`/`POST` endpoints and a lifecycle-managed `MarketSentimentAnalysisSampler`.

- [ ] **Step 1: Write failing sampler tests**

Verify no current-day generation before `15:15`, one generation after `15:15`, no duplicate call after `ready`, catch-up for the latest completed Friday after a weekend restart, 30-minute cooldown after `failed`, exception logging without thread death, and clean `stop_and_wait()`.

```python
clock.current = datetime.fromisoformat("2026-07-22T15:14:00+08:00")
assert sampler.sample_once() is False
clock.current = datetime.fromisoformat("2026-07-22T15:15:00+08:00")
assert sampler.sample_once() is True
assert sampler.sample_once() is False
```

- [ ] **Step 2: Write failing analysis endpoint tests**

Cover:

```http
GET /api/short-term/sentiment/percentile/analysis?trade_date=2026-07-22
POST /api/short-term/sentiment/percentile/analysis/generate?trade_date=2026-07-22&force=false
```

Assert `not_generated`, `unconfigured`, `pending`, `ready`, and `failed` payloads; `404` for a requested date outside percentile history; manual `force=true`; and that a percentile GET can schedule but never wait for LLM network I/O.

- [ ] **Step 3: Run the new tests and verify failure**

Run: `cd apps/api && uv run pytest tests/test_market_sentiment_analysis_api.py tests/test_market_sentiment_analysis_sampler.py -q`

Expected: missing sampler and endpoint failures.

- [ ] **Step 4: Implement the sampler with existing lifecycle conventions**

Follow `EtfThreeFactorSampler`: own `Event`, lifecycle lock, sample lock, daemon thread, `running`, `start`, `stop`, and `stop_and_wait`. Poll every 5 minutes, call a supplied `generate_latest(now)` callback only when a completed date is eligible, and defer retries until the persisted `retry_after`. The callback itself performs provider/model/hash deduplication, so container restarts remain idempotent.

- [ ] **Step 5: Build analysis context without making auxiliary fields mandatory**

In `main.py`, load the selected percentile point first. Then load cached `SentimentSummaryResponse` and market-emotion data for that date; if absent, try `_build_and_persist_sentiment_snapshots(..., refresh=True)` but catch provider errors and continue with `None`. Build `SentimentDecisionResponse` only when summary data exists. Load `validation-v1.json`, representing absent or invalid validation as `{status: "unavailable", sample_count: 0}`.

- [ ] **Step 6: Add factories, endpoints, and lifespan startup/shutdown**

Add factories honoring `app.state` injection for the analysis store/service/sampler. Start the sampler unconditionally in lifespan because an unconfigured LLM is an observable unmet requirement, and stop it before other sentiment services. `GET analysis` only reads state. `POST generate` performs explicit generation. The percentile endpoint may dispatch one daemon catch-up call only when the selected date equals `latest_complete_trade_date`, Shanghai time is at least `15:15`, and that date lacks analysis; it must return its statistical response immediately.

- [ ] **Step 7: Run all new backend tests plus runtime-setting tests**

Run:

```bash
cd apps/api
uv run pytest \
  tests/test_market_sentiment_percentile.py \
  tests/test_market_sentiment_percentile_service.py \
  tests/test_market_sentiment_percentile_api.py \
  tests/test_market_sentiment_validation.py \
  tests/test_market_sentiment_analysis.py \
  tests/test_market_sentiment_analysis_api.py \
  tests/test_market_sentiment_analysis_sampler.py \
  tests/test_api.py -k 'sentiment or ai_analysis' -q
```

Expected: all selected tests pass; public settings continue to contain only masked-key metadata.

- [ ] **Step 8: Commit API and sampler integration**

```bash
git add apps/api/app/main.py apps/api/app/services/market_sentiment_analysis_sampler.py apps/api/tests/test_market_sentiment_analysis_api.py apps/api/tests/test_market_sentiment_analysis_sampler.py
git commit -m "feat: schedule daily sentiment interpretation"
```

---

### Task 7: Vue Types, API Client, And Chart Option

**Files:**
- Modify: `apps/web-vue/src/service/types.ts`
- Modify: `apps/web-vue/src/service/product-api.ts`
- Create: `apps/web-vue/src/utils/charts/sentimentPercentileChart.ts`
- Create: `apps/web-vue/src/utils/charts/sentimentPercentileChart.test.ts`
- Modify: `apps/web-vue/src/service/api.test.ts`

**Interfaces:**
- Consumes: backend response contracts from Tasks 3 and 6.
- Produces: `getMarketSentimentPercentile`, `getMarketSentimentAnalysis`, `generateMarketSentimentAnalysis`, and `buildSentimentPercentileChartOption`.

- [ ] **Step 1: Add failing API-client and chart tests**

Assert URL encoding of `as_of`, `refresh`, `trade_date`, and `force`. For the chart option assert fixed `0..100`, mark areas at `0..20` and `80..100`, mark lines at `20` and `80`, no symbols for ordinary points, symbols for extreme/latest points, complete tooltip factor data, and `animationDuration` no greater than `160` in normal mode and `0` in reduced-motion mode.

```ts
const option = buildSentimentPercentileChartOption(historyFixture(), '2026-07-22', false);
expect((option.yAxis as { min: number; max: number })).toMatchObject({ min: 0, max: 100 });
expect(JSON.stringify(option)).toContain('冰点区');
expect(JSON.stringify(option)).toContain('过热区');
expect(buildSentimentPercentileChartOption(historyFixture(), '2026-07-22', true).animationDuration).toBe(0);
```

- [ ] **Step 2: Run focused Vue tests and verify failure**

Run: `cd apps/web-vue && pnpm test:unit -- src/service/api.test.ts src/utils/charts/sentimentPercentileChart.test.ts`

Expected: missing exports and module failures.

- [ ] **Step 3: Add frontend contracts matching Pydantic field names exactly**

Define `SentimentPercentileFactor`, `SentimentPercentileFactors`, `SentimentPercentilePoint`, `SentimentPercentileResponse`, `SentimentAnalysisResult`, and `SentimentPercentileAnalysisResponse`. Keep status unions exact, including `not_generated | unconfigured | pending | ready | failed`.

- [ ] **Step 4: Add typed API methods**

```ts
export async function getMarketSentimentPercentile(asOf?: string, refresh = false) {
  const params = new URLSearchParams({ refresh: String(refresh) });
  if (asOf) params.set('as_of', asOf);
  const response = await apiFetch(
    `${API_BASE_URL}/api/short-term/sentiment/percentile?${params.toString()}`
  );
  if (!response.ok) {
    throw new Error(`读取市场情绪百分位失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<SentimentPercentileResponse>;
}
```

Use the existing `apiFetch` and local response-error style rather than adding another request wrapper.

- [ ] **Step 5: Build the ECharts option as a pure function**

Use workbench token fallback colors, a category x-axis, fixed value y-axis, `markArea`, `markLine`, and HTML tooltip lines for composite score plus all factor scores/raw values. Set each data item symbol size to `6` only when the point is latest or its level is `冰点/过热`; otherwise `0`. The latest item color comes from its actual level. Accept a `reducedMotion` boolean and set animation duration to `0` when true.

- [ ] **Step 6: Run frontend data/chart tests and typecheck**

Run:

```bash
cd apps/web-vue
pnpm test:unit -- src/service/api.test.ts src/utils/charts/sentimentPercentileChart.test.ts
pnpm typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 7: Commit frontend data contracts**

```bash
git add apps/web-vue/src/service/types.ts apps/web-vue/src/service/product-api.ts apps/web-vue/src/service/api.test.ts apps/web-vue/src/utils/charts/sentimentPercentileChart.ts apps/web-vue/src/utils/charts/sentimentPercentileChart.test.ts
git commit -m "feat: add sentiment percentile frontend client"
```

---

### Task 8: Production Sentiment Percentile And AI Panel

**Files:**
- Create: `apps/web-vue/src/components/sentiment/SentimentPercentilePanel.vue`
- Create: `apps/web-vue/src/components/sentiment/SentimentPercentilePanel.test.ts`
- Modify: `apps/web-vue/src/views/SentimentView.vue`
- Create: `apps/web-vue/src/views/SentimentView.test.ts`

**Interfaces:**
- Consumes: `asOf: string` and `refreshToken: number`; the Task 7 API and chart option helpers.
- Produces: an independent module immediately below `PageHeader`, emitting no changes to existing trade-permission state.

- [ ] **Step 1: Write component tests for rendering and independent failures**

Mount with an `EChart` stub and mocked API. Assert the panel shows current score/level, exactly five factor scales and raw values, a 500-point option, an accessible date selector, AI ready content and metadata, and state-specific copy for loading, `not_generated`, `unconfigured`, `failed`, and retry. Reject percentile loading while fulfilling existing summary/decision calls in `SentimentView.test.ts`, and assert the rest of the page still renders.

- [ ] **Step 2: Run component/view tests and verify failure**

Run: `cd apps/web-vue && pnpm test:unit -- src/components/sentiment/SentimentPercentilePanel.test.ts src/views/SentimentView.test.ts`

Expected: missing component/test target failures.

- [ ] **Step 3: Implement independent panel loading and selection**

The panel watches `[asOf, refreshToken]`, fetches the percentile without sharing `SentimentView.loading`, selects the returned point, then reads analysis for that selected trade date. Keep the last successful percentile visible while refreshing. Chart click handles the shared `EChart` `select` event; an Ant Design Vue `a-select` labeled “查看日期” provides equivalent keyboard selection. Read `window.matchMedia('(prefers-reduced-motion: reduce)')` and pass the result to the chart-option builder. Historical dates without analysis show `not_generated` but never trigger bulk generation.

- [ ] **Step 4: Implement the approved desktop/mobile layout**

Use one `sentiment-panel`: a `minmax(0, 2fr) minmax(260px, 1fr)` desktop grid with a `360px` chart on the left and current score plus five compact horizontal factor scales on the right. Below it, render “AI 盘后解读” as compact structured sections, not chat bubbles. On screens below `768px`, stack chart, factors, and analysis; constrain all text and chart containers with `min-width: 0`; avoid nested decorative cards and horizontal overflow.

- [ ] **Step 5: Integrate immediately below the page header**

In `SentimentView.vue`, add:

```vue
<SentimentPercentilePanel :as-of="tradeDate" :refresh-token="percentileRefreshToken" />
```

Place it after the page-level alert and before `MetricStrip`. Increment `percentileRefreshToken` only from the explicit “刷新数据” action; changing the trade date naturally reloads via `asOf`. Keep the existing `Promise.allSettled` requests and existing panels unchanged.

- [ ] **Step 6: Implement analysis status actions**

`unconfigured` links to `/system` (the current settings route), `failed` shows sanitized error text and a retry button, `pending` uses a stable-height skeleton, and `ready` displays conclusion, posture label, 2–4 drivers, divergence, historical context, 2–4 next-session conditions, model, generation time, and risk note. Manual retry calls `generateMarketSentimentAnalysis(tradeDate, true)` and replaces only analysis state.

- [ ] **Step 7: Run component tests, all Vue tests, typecheck, and build**

Run:

```bash
cd apps/web-vue
pnpm test:unit -- src/components/sentiment/SentimentPercentilePanel.test.ts src/views/SentimentView.test.ts
pnpm test:unit
pnpm typecheck
pnpm build
```

Expected: all commands pass and `dist/index.html` exists.

- [ ] **Step 8: Commit the production UI**

```bash
git add apps/web-vue/src/components/sentiment/SentimentPercentilePanel.vue apps/web-vue/src/components/sentiment/SentimentPercentilePanel.test.ts apps/web-vue/src/views/SentimentView.vue apps/web-vue/src/views/SentimentView.test.ts
git commit -m "feat: add sentiment percentile workbench panel"
```

---

### Task 9: Full Verification, Real-Source Check, And Visual QA

**Files:**
- Modify only when verification exposes a defect in files already listed above.

**Interfaces:**
- Consumes: the completed backend and production Vue implementation.
- Produces: test evidence, a real TickFlow response check, and desktop/mobile visual evidence; no deployment or remote push is part of this task.

- [ ] **Step 1: Run the complete backend suite and lint**

Run:

```bash
cd apps/api
uv run pytest -q
uv run ruff check app tests scripts/run_market_sentiment_validation.py
```

Expected: zero failures and zero Ruff errors.

- [ ] **Step 2: Run the complete production frontend verification**

Run:

```bash
cd apps/web-vue
pnpm test:unit
pnpm typecheck
pnpm build
```

Expected: all tests pass, typecheck exits `0`, and Vite produces `dist/index.html`.

- [ ] **Step 3: Run the real-source validation command**

Run from a configured environment:

```bash
cd apps/api
uv run python scripts/run_market_sentiment_validation.py \
  --output-dir ../../data/sentiment-percentile
```

Expected: at least `1000` valid `000985.SH` bars, `500` displayed history points in the latest snapshot, and JSON/Markdown validation artifacts. Record a provider-unavailable result honestly if TickFlow credentials/network are unavailable; do not substitute fixture output as real data.

- [ ] **Step 4: Build and start the single container locally**

Run:

```bash
docker build -t strong-stock-screener:sentiment-percentile .
docker run --rm -d \
  --name strong-stock-screener-sentiment-percentile \
  -p 3124:3110 \
  --env-file .env \
  -v "$PWD/data:/app/data" \
  strong-stock-screener:sentiment-percentile
curl --fail http://127.0.0.1:3124/health
curl --fail http://127.0.0.1:3124/api/short-term/sentiment/percentile
```

Expected: both requests return `200` after container health becomes ready.

- [ ] **Step 5: Perform Playwright desktop and mobile QA**

Open `http://127.0.0.1:3124/sentiment` at `1440x900` and `390x844`. Verify the panel is immediately below the header, chart is nonblank and fixed to `0–100`, latest/factor values agree, selection updates factor detail, no overlap or horizontal overflow exists, and LLM failures do not hide the chart. Capture screenshots and check `document.documentElement.scrollWidth === document.documentElement.clientWidth` at both widths.

- [ ] **Step 6: Verify LLM deduplication with configured settings**

After `15:15 Asia/Shanghai`, call the generate endpoint twice with `force=false` and assert both responses share `trade_date`, `provider`, `llm_model`, and `input_hash`, while the persisted analysis record reports the original successful request. Confirm `/api/settings` exposes only `api_key_configured`, preview, and source metadata, never the full key.

- [ ] **Step 7: Stop the local verification container**

Run: `docker stop strong-stock-screener-sentiment-percentile`

Expected: the container exits cleanly and no required process remains running.

- [ ] **Step 8: Review final diff and create the verification commit only if fixes were needed**

Run:

```bash
git diff --check
git status --short
git log --oneline --decorate -10
```

If verification required code fixes, stage only those listed feature files and commit with `fix: harden sentiment percentile release`. If no fixes were required, leave the existing task commits unchanged.
