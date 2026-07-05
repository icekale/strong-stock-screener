# Auction Top3 Model Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add auction Top3 into AI model maintenance, including packet links, two-step AI analysis, Top3 training samples, and trackable simulated performance.

**Architecture:** Extend the existing FastAPI + JSON-file persistence style instead of adding a database. Keep Top3 training logic in a focused backend service/store, let model-maintenance packet generation read cached Top3/training summaries only, and update the Next.js model-maintenance page into a clear packet -> AI analysis -> Codex link workflow.

**Tech Stack:** FastAPI, Pydantic, JSON/JSONL local stores, pytest, Next.js App Router, React, Ant Design, TypeScript, Node test runner.

---

## File Structure

- Modify `apps/api/app/models.py`
  - Add Top3 training sample/performance models.
  - Add `model_sections` and `packet_url` fields to `ModelMaintenancePacket`.

- Create `apps/api/app/services/auction_top3_training.py`
  - Store Top3 signal samples, simulated trade samples, manual trade samples, and performance points under `STRONG_STOCK_DATA_DIR/auction_top3_training`.
  - Generate signal samples from `AuctionModelTop3Response`.
  - Generate daily-line simulated trades from signal samples and `KlineBar` data.
  - Summarize training data and performance.

- Modify `apps/api/app/services/model_maintenance_store.py`
  - Add `load_packet(packet_id)` for link-based packet retrieval.

- Modify `apps/api/app/services/model_maintenance_packet.py`
  - Include GSGF, auction Top3, and Top3 training summary in `model_sections`.
  - Build full packet links.

- Modify `apps/api/app/services/ai_model_analysis.py`
  - Include multi-model and Top3 training context in the AI prompt.
  - Make offline analysis mention Top3/training status.

- Modify `apps/api/app/services/runtime_settings.py` and `apps/api/app/config.py`
  - Add Top3 training toggles and simulated account settings.

- Modify `apps/api/app/main.py`
  - Add packet retrieval endpoint.
  - Add Top3 training summary/performance/manual-trade endpoints.
  - Save signal samples when Top3 results are generated.

- Modify `apps/api/tests/test_model_maintenance.py`
  - Cover packet link, auction Top3 section, and training summary in packets.

- Create `apps/api/tests/test_auction_top3_training.py`
  - Cover signal sample upsert, simulated trade generation, performance tracking, dedupe, and manual training inclusion.

- Modify `apps/api/tests/test_auction_model.py`
  - Cover Top3 API generating signal samples when enabled.

- Modify `apps/web/lib/types.ts`
  - Add packet link, model sections, Top3 training, and performance types.

- Modify `apps/web/lib/api.ts`
  - Add latest packet, packet retrieval, training summary/performance/generate/manual trade API clients.

- Modify `apps/web/app/model-maintenance/ModelMaintenanceWorkspace.tsx`
  - Split “generate packet” and “submit AI analysis”.
  - Add packet status card, AI/offline status, Top3 training data panel, simulated performance overview, and copyable Codex packet link.

- Create `apps/web/app/model-maintenance/packets/[packetId]/page.tsx`
  - Show a readable packet summary and raw JSON API link.

- Modify `apps/web/lib/strongStockWorkbench.test.ts`
  - Assert page strings and API/type wiring.

---

### Task 1: Backend Models And Settings

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/config.py`
- Modify: `apps/api/app/services/runtime_settings.py`
- Test: `apps/api/tests/test_auction_top3_training.py`

- [ ] **Step 1: Write failing model/settings tests**

Create `apps/api/tests/test_auction_top3_training.py` with:

```python
from pathlib import Path

from app.models import (
    AuctionTop3ManualTradeSample,
    AuctionTop3SignalSample,
    AuctionTop3SimulatedPerformancePoint,
    AuctionTop3SimulatedTradeSample,
    ModelMaintenancePacket,
)
from app.services.runtime_settings import (
    AuctionTop3TrainingSettings,
    SettingsUpdate,
    load_runtime_settings,
    save_runtime_settings,
)


def test_auction_top3_training_models_and_packet_section_defaults() -> None:
    signal = AuctionTop3SignalSample(
        sample_id="sig-1",
        trade_date="2026-07-06",
        symbol="300001.SZ",
        name="模型一号",
        rank=1,
        score=0.91,
        model_version="fake-model",
        feature_version="fake-features",
        guard_rule="10:00收益<0则退出，否则持有到T+1收盘",
    )
    trade = AuctionTop3SimulatedTradeSample(
        sample_id="sim-1",
        signal_sample_id="sig-1",
        portfolio_id="default",
        trade_date="2026-07-06",
        symbol="300001.SZ",
        entry_policy="open_0930",
        exit_policy="next_open_exit",
        position_pct=0.33,
        entry_price=10.0,
        exit_price=10.5,
        return_pct=5.0,
        profit_amount=1650.0,
    )
    point = AuctionTop3SimulatedPerformancePoint(
        portfolio_id="default",
        trade_date="2026-07-06",
        entry_policy="open_0930",
        exit_policy="next_open_exit",
        trade_count=1,
        win_count=1,
        loss_count=0,
        daily_return_pct=1.65,
        cumulative_return_pct=1.65,
        equity=101650.0,
        max_drawdown_pct=0,
    )
    manual = AuctionTop3ManualTradeSample(
        sample_id="manual-1",
        signal_sample_id="sig-1",
        trade_date="2026-07-06",
        symbol="300001.SZ",
        bought=True,
        enabled_for_training=False,
    )
    packet = ModelMaintenancePacket(
        packet_id="packet-1",
        model_sections={
            "auction_top3_training": {
                "enabled": True,
                "signal_sample_count": 1,
                "simulated_trade_sample_count": 1,
                "manual_trade_sample_count": 1,
                "simulated_profit_summary": {"latest_equity": 101650.0},
            }
        },
        packet_url="http://localhost:3110/model-maintenance/packets/packet-1",
    )

    assert signal.symbol == "300001.SZ"
    assert trade.label == "win"
    assert point.equity == 101650.0
    assert manual.enabled_for_training is False
    assert packet.model_sections["auction_top3_training"]["signal_sample_count"] == 1
    assert packet.packet_url.endswith("/model-maintenance/packets/packet-1")


def test_runtime_settings_persist_auction_top3_training_options(tmp_path: Path) -> None:
    path = tmp_path / "runtime.json"
    save_runtime_settings(
        path,
        SettingsUpdate(
            auction_top3_training=AuctionTop3TrainingSettings(
                record_signal_samples=True,
                generate_simulated_trade_samples=True,
                include_manual_trade_samples_in_training=True,
                training_window_days=45,
                simulated_initial_capital=200000,
                simulated_position_pct=0.25,
            )
        ),
    )

    loaded = load_runtime_settings(path)

    assert loaded.auction_top3_training.record_signal_samples is True
    assert loaded.auction_top3_training.generate_simulated_trade_samples is True
    assert loaded.auction_top3_training.include_manual_trade_samples_in_training is True
    assert loaded.auction_top3_training.training_window_days == 45
    assert loaded.auction_top3_training.simulated_initial_capital == 200000
    assert loaded.auction_top3_training.simulated_position_pct == 0.25
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=apps/api pytest apps/api/tests/test_auction_top3_training.py -q
```

Expected: FAIL because `AuctionTop3SignalSample` and `AuctionTop3TrainingSettings` do not exist.

- [ ] **Step 3: Add Pydantic models**

In `apps/api/app/models.py`, add literals near existing model literals:

```python
AuctionTop3EntryPolicy = Literal["open_0930", "after_0935_confirm", "before_1000_strength", "close_follow"]
AuctionTop3ExitPolicy = Literal[
    "intraday_stop",
    "intraday_take_profit",
    "close_exit",
    "next_open_exit",
    "next_close_exit",
]
AuctionTop3TradeLabel = Literal["win", "loss", "neutral", "data_incomplete"]
```

Add models after `AuctionModelTop3Response`:

```python
class AuctionTop3SignalSample(BaseModel):
    sample_id: str
    trade_date: str
    symbol: str
    name: str = ""
    industry: str | None = None
    rank: int | None = None
    score: float = 0
    model_version: str
    feature_version: str
    guard_rule: str | None = None
    signals: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    feature_snapshot: dict[str, Any] = Field(default_factory=dict)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))


class AuctionTop3SimulatedTradeSample(BaseModel):
    sample_id: str
    signal_sample_id: str
    portfolio_id: str = "default"
    trade_date: str
    symbol: str
    entry_policy: AuctionTop3EntryPolicy
    entry_price: float | None = None
    entry_time: str | None = None
    exit_policy: AuctionTop3ExitPolicy
    exit_price: float | None = None
    exit_time: str | None = None
    position_pct: float = 0.33
    return_pct: float | None = None
    profit_amount: float | None = None
    max_drawdown_pct: float | None = None
    max_favorable_pct: float | None = None
    label: AuctionTop3TradeLabel = "data_incomplete"
    created_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))


class AuctionTop3SimulatedPerformancePoint(BaseModel):
    portfolio_id: str = "default"
    trade_date: str
    entry_policy: AuctionTop3EntryPolicy
    exit_policy: AuctionTop3ExitPolicy
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    daily_return_pct: float | None = None
    cumulative_return_pct: float | None = None
    equity: float | None = None
    max_drawdown_pct: float | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))


class AuctionTop3ManualTradeSample(BaseModel):
    sample_id: str
    signal_sample_id: str
    trade_date: str
    symbol: str
    enabled_for_training: bool = False
    bought: bool = False
    buy_price: float | None = None
    sell_price: float | None = None
    position_pct: float | None = None
    buy_reason: str = ""
    sell_reason: str = ""
    return_pct: float | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))


class AuctionTop3TrainingSummary(BaseModel):
    enabled: bool = True
    signal_sample_count: int = 0
    simulated_trade_sample_count: int = 0
    manual_trade_sample_count: int = 0
    date_range: list[str] = Field(default_factory=list)
    training_window_days: int = 60
    latest_generated_at: str | None = None
    simulated_profit_summary: dict[str, Any] = Field(default_factory=dict)
    quality_notes: list[str] = Field(default_factory=list)


class AuctionTop3PerformanceResponse(BaseModel):
    summary: dict[str, Any] = Field(default_factory=dict)
    points: list[AuctionTop3SimulatedPerformancePoint] = Field(default_factory=list)
    trades: list[AuctionTop3SimulatedTradeSample] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
```

Extend `ModelMaintenancePacket` with:

```python
    model_sections: dict[str, Any] = Field(default_factory=dict)
    packet_url: str | None = None
```

- [ ] **Step 4: Add runtime settings**

In `apps/api/app/services/runtime_settings.py`, add:

```python
class AuctionTop3TrainingSettings(BaseModel):
    record_signal_samples: bool = True
    generate_simulated_trade_samples: bool = False
    include_manual_trade_samples_in_training: bool = False
    training_window_days: int = Field(default=60, ge=5, le=365)
    simulated_initial_capital: float = Field(default=100000, gt=0)
    simulated_position_pct: float = Field(default=0.33, gt=0, le=1)
```

Add `auction_top3_training: AuctionTop3TrainingSettings = Field(default_factory=AuctionTop3TrainingSettings)` to `RuntimeSettings`, `SettingsUpdate`, and `EffectiveRuntimeSettings`.

In `save_runtime_settings()`, merge it:

```python
"auction_top3_training": update.auction_top3_training,
```

In `public_settings_payload()`, expose it:

```python
"auction_top3_training": config.auction_top3_training.model_dump(mode="json"),
```

In `apps/api/app/config.py`, add base defaults:

```python
auction_top3_record_signal_samples: bool = True
auction_top3_generate_simulated_trade_samples: bool = False
auction_top3_include_manual_trade_samples_in_training: bool = False
auction_top3_training_window_days: int = Field(default=60, ge=5, le=365)
auction_top3_simulated_initial_capital: float = Field(default=100000, gt=0)
auction_top3_simulated_position_pct: float = Field(default=0.33, gt=0, le=1)
```

- [ ] **Step 5: Run tests and verify they pass**

Run:

```bash
PYTHONPATH=apps/api pytest apps/api/tests/test_auction_top3_training.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/models.py apps/api/app/config.py apps/api/app/services/runtime_settings.py apps/api/tests/test_auction_top3_training.py
git commit -m "Add auction Top3 training models"
```

---

### Task 2: Top3 Training Store And Simulated Performance

**Files:**
- Create: `apps/api/app/services/auction_top3_training.py`
- Modify: `apps/api/tests/test_auction_top3_training.py`

- [ ] **Step 1: Add failing store and performance tests**

Append to `apps/api/tests/test_auction_top3_training.py`:

```python
from app.models import AuctionModelPredictionItem, AuctionModelTop3Response, KlineBar, StrongStockSourceStatus
from app.services.auction_top3_training import (
    AuctionTop3TrainingStore,
    build_signal_samples_from_top3,
    generate_simulated_trade_samples,
    summarize_simulated_performance,
)


def test_training_store_upserts_signal_samples_by_trade_date_symbol_rank(tmp_path: Path) -> None:
    store = AuctionTop3TrainingStore(tmp_path)
    response = _top3_response()

    first = store.upsert_signal_samples(build_signal_samples_from_top3(response))
    second = store.upsert_signal_samples(build_signal_samples_from_top3(response))
    loaded = store.load_signal_samples("2026-07-06")

    assert len(first) == 2
    assert len(second) == 2
    assert len(loaded) == 2
    assert loaded[0].sample_id == "sig-20260706-300001SZ-1"
    assert loaded[0].feature_snapshot["prob_3pct"] == 0.91
    assert loaded[0].source_status[0].source == "fake-source"


def test_generate_simulated_trade_samples_and_performance_dedupes(tmp_path: Path) -> None:
    store = AuctionTop3TrainingStore(tmp_path)
    signals = store.upsert_signal_samples(build_signal_samples_from_top3(_top3_response()))
    bars_by_symbol = {
        "300001.SZ": [
            KlineBar(date="2026-07-06", open=10, high=10.8, low=9.8, close=10.5, volume=100),
            KlineBar(date="2026-07-07", open=10.7, high=11, low=10.4, close=10.8, volume=120),
        ],
        "300002.SZ": [
            KlineBar(date="2026-07-06", open=20, high=20.2, low=19.2, close=19.4, volume=100),
            KlineBar(date="2026-07-07", open=19.0, high=19.4, low=18.8, close=19.1, volume=90),
        ],
    }

    trades = generate_simulated_trade_samples(
        signals,
        bars_by_symbol,
        initial_capital=100000,
        position_pct=0.5,
        entry_policy="open_0930",
        exit_policy="next_open_exit",
    )
    store.upsert_simulated_trades(trades)
    store.upsert_simulated_trades(trades)
    performance = summarize_simulated_performance(
        store.load_simulated_trades(),
        initial_capital=100000,
        portfolio_id="default",
    )
    store.save_performance_points(performance.points)

    assert len(store.load_simulated_trades()) == 2
    assert performance.summary["complete_sample_count"] == 2
    assert performance.summary["latest_equity"] == 101000.0
    assert performance.summary["cumulative_return_pct"] == 1.0
    assert performance.summary["win_rate"] == 0.5
    assert performance.points[0].trade_date == "2026-07-06"


def test_manual_trade_samples_count_only_when_enabled_for_training(tmp_path: Path) -> None:
    store = AuctionTop3TrainingStore(tmp_path)
    store.upsert_manual_trade(
        AuctionTop3ManualTradeSample(
            sample_id="manual-1",
            signal_sample_id="sig-1",
            trade_date="2026-07-06",
            symbol="300001.SZ",
            bought=True,
            enabled_for_training=False,
        )
    )
    store.upsert_manual_trade(
        AuctionTop3ManualTradeSample(
            sample_id="manual-2",
            signal_sample_id="sig-2",
            trade_date="2026-07-06",
            symbol="300002.SZ",
            bought=True,
            enabled_for_training=True,
        )
    )

    summary = store.training_summary(training_window_days=60, include_manual_training=True)

    assert summary.manual_trade_sample_count == 1


def _top3_response() -> AuctionModelTop3Response:
    return AuctionModelTop3Response(
        trade_date="2026-07-06",
        feature_end_date="2026-07-03",
        model_version="fake-model",
        feature_version="fake-features",
        guard_rule="fake-guard",
        items=[
            AuctionModelPredictionItem(
                symbol="300001.SZ",
                name="模型一号",
                rank=1,
                prob_3pct=0.91,
                bucket="selected",
                guard_rule="fake-guard",
                trend_reasons=["强趋势"],
            ),
            AuctionModelPredictionItem(
                symbol="300002.SZ",
                name="模型二号",
                rank=2,
                prob_3pct=0.82,
                bucket="selected",
                guard_rule="fake-guard",
                risk_flags=["高开过热"],
            ),
        ],
        source_status=[StrongStockSourceStatus(source="fake-source", status="success", detail="ok")],
    )
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=apps/api pytest apps/api/tests/test_auction_top3_training.py -q
```

Expected: FAIL because `app.services.auction_top3_training` does not exist.

- [ ] **Step 3: Implement store and pure functions**

Create `apps/api/app/services/auction_top3_training.py`:

```python
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app.models import (
    AuctionModelTop3Response,
    AuctionTop3EntryPolicy,
    AuctionTop3ExitPolicy,
    AuctionTop3ManualTradeSample,
    AuctionTop3PerformanceResponse,
    AuctionTop3SignalSample,
    AuctionTop3SimulatedPerformancePoint,
    AuctionTop3SimulatedTradeSample,
    AuctionTop3TrainingSummary,
    KlineBar,
)


class AuctionTop3TrainingStore:
    def __init__(self, data_dir: Path) -> None:
        self.root_dir = data_dir / "auction_top3_training"
        self.signal_dir = self.root_dir / "signals"
        self.simulated_dir = self.root_dir / "simulated_trades"
        self.manual_dir = self.root_dir / "manual_trades"
        self.performance_path = self.root_dir / "performance.json"

    def upsert_signal_samples(self, samples: list[AuctionTop3SignalSample]) -> list[AuctionTop3SignalSample]:
        existing = {_signal_key(sample): sample for sample in self.load_signal_samples()}
        for sample in samples:
            existing[_signal_key(sample)] = sample
        self._write_jsonl_grouped(self.signal_dir, existing.values(), lambda item: item.trade_date)
        return samples

    def load_signal_samples(self, trade_date: str | None = None) -> list[AuctionTop3SignalSample]:
        return _read_jsonl_models(self.signal_dir, AuctionTop3SignalSample, trade_date)

    def upsert_simulated_trades(self, trades: list[AuctionTop3SimulatedTradeSample]) -> list[AuctionTop3SimulatedTradeSample]:
        existing = {_simulated_key(sample): sample for sample in self.load_simulated_trades()}
        for trade in trades:
            existing[_simulated_key(trade)] = trade
        self._write_jsonl_grouped(self.simulated_dir, existing.values(), lambda item: item.trade_date)
        return trades

    def load_simulated_trades(self, trade_date: str | None = None) -> list[AuctionTop3SimulatedTradeSample]:
        return _read_jsonl_models(self.simulated_dir, AuctionTop3SimulatedTradeSample, trade_date)

    def upsert_manual_trade(self, sample: AuctionTop3ManualTradeSample) -> AuctionTop3ManualTradeSample:
        existing = {item.sample_id: item for item in self.load_manual_trades()}
        existing[sample.sample_id] = sample
        self._write_jsonl_grouped(self.manual_dir, existing.values(), lambda item: item.trade_date)
        return sample

    def load_manual_trades(self, trade_date: str | None = None) -> list[AuctionTop3ManualTradeSample]:
        return _read_jsonl_models(self.manual_dir, AuctionTop3ManualTradeSample, trade_date)

    def save_performance_points(self, points: list[AuctionTop3SimulatedPerformancePoint]) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        payload = AuctionTop3PerformanceResponse(points=points).model_dump_json(indent=2)
        self.performance_path.write_text(payload, encoding="utf-8")

    def load_performance(self) -> AuctionTop3PerformanceResponse:
        if not self.performance_path.exists():
            return AuctionTop3PerformanceResponse()
        return AuctionTop3PerformanceResponse.model_validate_json(self.performance_path.read_text(encoding="utf-8"))

    def training_summary(
        self,
        *,
        training_window_days: int,
        include_manual_training: bool,
        enabled: bool = True,
    ) -> AuctionTop3TrainingSummary:
        signals = self.load_signal_samples()
        simulated = self.load_simulated_trades()
        manual = [
            item
            for item in self.load_manual_trades()
            if include_manual_training and item.enabled_for_training
        ]
        performance = summarize_simulated_performance(simulated, initial_capital=100000, portfolio_id="default")
        dates = sorted({sample.trade_date for sample in signals})
        return AuctionTop3TrainingSummary(
            enabled=enabled,
            signal_sample_count=len(signals),
            simulated_trade_sample_count=len(simulated),
            manual_trade_sample_count=len(manual),
            date_range=[dates[0], dates[-1]] if dates else [],
            training_window_days=training_window_days,
            latest_generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            simulated_profit_summary=performance.summary,
            quality_notes=[] if signals else ["暂无竞价 Top3 信号样本"],
        )

    def _write_jsonl_grouped(self, directory: Path, items: object, date_getter: object) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        grouped: dict[str, list[object]] = defaultdict(list)
        for item in items:
            grouped[date_getter(item)].append(item)
        for trade_date, rows in grouped.items():
            path = directory / f"{trade_date}.jsonl"
            path.write_text("".join(row.model_dump_json() + "\n" for row in sorted(rows, key=lambda row: row.model_dump_json())), encoding="utf-8")


def build_signal_samples_from_top3(result: AuctionModelTop3Response) -> list[AuctionTop3SignalSample]:
    samples: list[AuctionTop3SignalSample] = []
    for item in result.items:
        if item.bucket != "selected":
            continue
        rank = item.rank or len(samples) + 1
        sample_id = f"sig-{result.trade_date.replace('-', '')}-{item.symbol.replace('.', '')}-{rank}"
        samples.append(
            AuctionTop3SignalSample(
                sample_id=sample_id,
                trade_date=result.trade_date,
                symbol=item.symbol,
                name=item.name,
                rank=rank,
                score=item.prob_3pct,
                model_version=result.model_version,
                feature_version=result.feature_version,
                guard_rule=item.guard_rule or result.guard_rule,
                signals=item.trend_reasons,
                risk_flags=item.risk_flags,
                feature_snapshot={
                    "prob_3pct": item.prob_3pct,
                    "prev_close_price": item.prev_close_price,
                    "market_cap_float": item.market_cap_float,
                    "avg_amount_3d": item.avg_amount_3d,
                    "feature_end_date": item.feature_end_date,
                    "data_quality": item.data_quality,
                },
                source_status=result.source_status,
            )
        )
    return samples


def generate_simulated_trade_samples(
    signals: list[AuctionTop3SignalSample],
    bars_by_symbol: dict[str, list[KlineBar]],
    *,
    initial_capital: float,
    position_pct: float,
    entry_policy: AuctionTop3EntryPolicy = "open_0930",
    exit_policy: AuctionTop3ExitPolicy = "next_open_exit",
    portfolio_id: str = "default",
) -> list[AuctionTop3SimulatedTradeSample]:
    trades: list[AuctionTop3SimulatedTradeSample] = []
    for signal in signals:
        bars = bars_by_symbol.get(signal.symbol, [])
        trade_bar = _bar_for_date(bars, signal.trade_date)
        next_bar = _next_bar_after_date(bars, signal.trade_date)
        sample_id = f"sim-{signal.sample_id}-{entry_policy}-{exit_policy}"
        entry_price = trade_bar.open if trade_bar and entry_policy == "open_0930" else None
        exit_price = _exit_price(exit_policy, trade_bar, next_bar)
        label = "data_incomplete"
        return_pct = None
        profit_amount = None
        max_drawdown_pct = None
        max_favorable_pct = None
        if entry_price and exit_price:
            return_pct = round((exit_price - entry_price) / entry_price * 100, 2)
            profit_amount = round(initial_capital * position_pct * return_pct / 100, 2)
            label = "win" if return_pct > 0 else "loss" if return_pct < 0 else "neutral"
            if trade_bar:
                max_drawdown_pct = round((trade_bar.low - entry_price) / entry_price * 100, 2)
                max_favorable_pct = round((trade_bar.high - entry_price) / entry_price * 100, 2)
        trades.append(
            AuctionTop3SimulatedTradeSample(
                sample_id=sample_id,
                signal_sample_id=signal.sample_id,
                portfolio_id=portfolio_id,
                trade_date=signal.trade_date,
                symbol=signal.symbol,
                entry_policy=entry_policy,
                entry_price=entry_price,
                entry_time=f"{signal.trade_date} 09:30" if entry_price else None,
                exit_policy=exit_policy,
                exit_price=exit_price,
                exit_time=_exit_time(exit_policy, signal.trade_date, next_bar),
                position_pct=position_pct,
                return_pct=return_pct,
                profit_amount=profit_amount,
                max_drawdown_pct=max_drawdown_pct,
                max_favorable_pct=max_favorable_pct,
                label=label,
            )
        )
    return trades


def summarize_simulated_performance(
    trades: list[AuctionTop3SimulatedTradeSample],
    *,
    initial_capital: float,
    portfolio_id: str,
) -> AuctionTop3PerformanceResponse:
    complete = [trade for trade in trades if trade.portfolio_id == portfolio_id and trade.label != "data_incomplete" and trade.profit_amount is not None]
    grouped: dict[str, list[AuctionTop3SimulatedTradeSample]] = defaultdict(list)
    for trade in complete:
        grouped[trade.trade_date].append(trade)
    equity = initial_capital
    peak = initial_capital
    points: list[AuctionTop3SimulatedPerformancePoint] = []
    for trade_date in sorted(grouped):
        daily_profit = sum(float(trade.profit_amount or 0) for trade in grouped[trade_date])
        equity += daily_profit
        peak = max(peak, equity)
        daily_return = daily_profit / initial_capital * 100
        cumulative_return = (equity - initial_capital) / initial_capital * 100
        drawdown = (equity - peak) / peak * 100 if peak else 0
        wins = sum(1 for trade in grouped[trade_date] if trade.label == "win")
        losses = sum(1 for trade in grouped[trade_date] if trade.label == "loss")
        first = grouped[trade_date][0]
        points.append(
            AuctionTop3SimulatedPerformancePoint(
                portfolio_id=portfolio_id,
                trade_date=trade_date,
                entry_policy=first.entry_policy,
                exit_policy=first.exit_policy,
                trade_count=len(grouped[trade_date]),
                win_count=wins,
                loss_count=losses,
                daily_return_pct=round(daily_return, 2),
                cumulative_return_pct=round(cumulative_return, 2),
                equity=round(equity, 2),
                max_drawdown_pct=round(drawdown, 2),
            )
        )
    wins = [trade for trade in complete if trade.label == "win"]
    losses = [trade for trade in complete if trade.label == "loss"]
    avg_win = sum(float(trade.return_pct or 0) for trade in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(float(trade.return_pct or 0) for trade in losses) / len(losses)) if losses else 0
    policy_returns: dict[str, float] = defaultdict(float)
    for trade in complete:
        policy_key = f"{trade.entry_policy}->{trade.exit_policy}"
        policy_returns[policy_key] += float(trade.profit_amount or 0)
    best_policy = max(policy_returns.items(), key=lambda item: item[1])[0] if policy_returns else None
    worst_policy = min(policy_returns.items(), key=lambda item: item[1])[0] if policy_returns else None
    summary = {
        "portfolio_id": portfolio_id,
        "latest_equity": round(equity, 2),
        "today_return_pct": points[-1].daily_return_pct if points else None,
        "cumulative_return_pct": points[-1].cumulative_return_pct if points else None,
        "max_drawdown_pct": min((point.max_drawdown_pct or 0 for point in points), default=0),
        "win_rate": round(len(wins) / len(complete), 4) if complete else None,
        "profit_loss_ratio": round(avg_win / avg_loss, 4) if avg_loss else None,
        "complete_sample_count": len(complete),
        "incomplete_sample_count": len([trade for trade in trades if trade.label == "data_incomplete"]),
        "best_policy": best_policy,
        "worst_policy": worst_policy,
    }
    return AuctionTop3PerformanceResponse(summary=summary, points=points, trades=trades)
```

Add these helper functions in the same file:

```python
from typing import TypeVar

T = TypeVar("T")


def _signal_key(sample: AuctionTop3SignalSample) -> tuple[str, str, int | None]:
    return (sample.trade_date, sample.symbol, sample.rank)


def _simulated_key(sample: AuctionTop3SimulatedTradeSample) -> tuple[str, str, str, str]:
    return (sample.trade_date, sample.signal_sample_id, sample.entry_policy, sample.exit_policy)


def _read_jsonl_models(directory: Path, model: type[T], trade_date: str | None = None) -> list[T]:
    paths = [directory / f"{trade_date}.jsonl"] if trade_date else sorted(directory.glob("*.jsonl"))
    records: list[T] = []
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(model.model_validate_json(line))
    return records


def _bar_for_date(bars: list[KlineBar], trade_date: str) -> KlineBar | None:
    return next((bar for bar in bars if bar.date[:10] == trade_date), None)


def _next_bar_after_date(bars: list[KlineBar], trade_date: str) -> KlineBar | None:
    ordered = sorted(bars, key=lambda bar: bar.date)
    for bar in ordered:
        if bar.date[:10] > trade_date:
            return bar
    return None


def _exit_price(
    exit_policy: AuctionTop3ExitPolicy,
    trade_bar: KlineBar | None,
    next_bar: KlineBar | None,
) -> float | None:
    if exit_policy == "close_exit" and trade_bar:
        return trade_bar.close
    if exit_policy == "next_open_exit" and next_bar:
        return next_bar.open
    if exit_policy == "next_close_exit" and next_bar:
        return next_bar.close
    return None


def _exit_time(exit_policy: AuctionTop3ExitPolicy, trade_date: str, next_bar: KlineBar | None) -> str | None:
    if exit_policy == "close_exit":
        return f"{trade_date} 15:00"
    if exit_policy in {"next_open_exit", "next_close_exit"} and next_bar:
        clock = "09:30" if exit_policy == "next_open_exit" else "15:00"
        return f"{next_bar.date[:10]} {clock}"
    return None
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
PYTHONPATH=apps/api pytest apps/api/tests/test_auction_top3_training.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/auction_top3_training.py apps/api/tests/test_auction_top3_training.py
git commit -m "Add auction Top3 training store"
```

---

### Task 3: Top3 Training APIs And Signal Capture

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_auction_model.py`
- Modify: `apps/api/tests/test_auction_top3_training.py`

- [ ] **Step 1: Add failing API tests**

Append to `apps/api/tests/test_auction_model.py`:

```python
def test_auction_model_api_records_top3_signal_samples(tmp_path: Path) -> None:
    app.state.auction_model_service = FakeAuctionModelService()
    app.state.auction_model_result_store = AuctionModelResultStore(tmp_path)
    client = TestClient(app)
    try:
        response = client.get("/api/auction/model/top3?trade_date=2026-07-06&refresh=true")
        summary = client.get("/api/model-maintenance/auction-top3/training/summary")
    finally:
        delattr(app.state, "auction_model_service")
        delattr(app.state, "auction_model_result_store")

    assert response.status_code == 200
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["signal_sample_count"] == 1
    assert payload["date_range"] == ["2026-07-06", "2026-07-06"]
```

Append to `apps/api/tests/test_auction_top3_training.py`:

```python
from fastapi.testclient import TestClient
from app.main import app


def test_training_performance_api_returns_summary(tmp_path: Path) -> None:
    app.state.runs_dir = tmp_path
    store = AuctionTop3TrainingStore(tmp_path)
    signals = store.upsert_signal_samples(build_signal_samples_from_top3(_top3_response()))
    trades = generate_simulated_trade_samples(
        signals,
        {
            "300001.SZ": [
                KlineBar(date="2026-07-06", open=10, high=11, low=9.8, close=10.4, volume=1),
                KlineBar(date="2026-07-07", open=10.5, high=10.8, low=10.2, close=10.6, volume=1),
            ]
        },
        initial_capital=100000,
        position_pct=0.33,
    )
    store.upsert_simulated_trades(trades)
    client = TestClient(app)
    try:
        response = client.get("/api/model-maintenance/auction-top3/training/performance")
    finally:
        delattr(app.state, "runs_dir")

    assert response.status_code == 200
    assert response.json()["summary"]["complete_sample_count"] == 1
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=apps/api pytest apps/api/tests/test_auction_model.py::test_auction_model_api_records_top3_signal_samples apps/api/tests/test_auction_top3_training.py::test_training_performance_api_returns_summary -q
```

Expected: FAIL because API endpoints and Top3 signal capture are missing.

- [ ] **Step 3: Wire store and endpoints**

In `apps/api/app/main.py`, import:

```python
from app.services.auction_top3_training import (
    AuctionTop3TrainingStore,
    build_signal_samples_from_top3,
    generate_simulated_trade_samples,
    summarize_simulated_performance,
)
```

In `apps/api/app/main.py`, add this exact helper:

```python
def _auction_top3_training_store() -> AuctionTop3TrainingStore:
    data_dir = Path(getattr(app.state, "runs_dir", get_settings().data_dir))
    existing = getattr(app.state, "auction_top3_training_store", None)
    existing_data_dir = getattr(app.state, "auction_top3_training_store_data_dir", None)
    if existing is not None and existing_data_dir == data_dir:
        return existing
    store = AuctionTop3TrainingStore(data_dir)
    app.state.auction_top3_training_store = store
    app.state.auction_top3_training_store_data_dir = data_dir
    return store
```

In `get_auction_model_top3()`, after saving a generated result, add:

```python
settings = _effective_settings().auction_top3_training
if settings.record_signal_samples:
    _auction_top3_training_store().upsert_signal_samples(build_signal_samples_from_top3(result))
```

Add endpoints near model-maintenance endpoints:

```python
@app.get("/api/model-maintenance/auction-top3/training/summary")
def get_auction_top3_training_summary() -> dict[str, object]:
    settings = _effective_settings().auction_top3_training
    summary = _auction_top3_training_store().training_summary(
        training_window_days=settings.training_window_days,
        include_manual_training=settings.include_manual_trade_samples_in_training,
        enabled=settings.record_signal_samples,
    )
    return summary.model_dump(mode="json")


@app.get("/api/model-maintenance/auction-top3/training/performance")
def get_auction_top3_training_performance() -> dict[str, object]:
    settings = _effective_settings().auction_top3_training
    trades = _auction_top3_training_store().load_simulated_trades()
    response = summarize_simulated_performance(
        trades,
        initial_capital=settings.simulated_initial_capital,
        portfolio_id="default",
    )
    return response.model_dump(mode="json")
```

Add `POST /api/model-maintenance/auction-top3/training/generate` using `_kline_provider()`:

```python
@app.post("/api/model-maintenance/auction-top3/training/generate")
def generate_auction_top3_training_samples(trade_date: str | None = None) -> dict[str, object]:
    settings = _effective_settings().auction_top3_training
    store = _auction_top3_training_store()
    signals = store.load_signal_samples(trade_date)
    bars_by_symbol: dict[str, list[KlineBar]] = {}
    provider = _kline_provider()
    for symbol in _dedupe_symbols([sample.symbol for sample in signals]):
        try:
            bars_by_symbol[symbol] = provider.get_klines(symbol, count=8)
        except Exception:
            bars_by_symbol[symbol] = []
    trades = generate_simulated_trade_samples(
        signals,
        bars_by_symbol,
        initial_capital=settings.simulated_initial_capital,
        position_pct=settings.simulated_position_pct,
    )
    saved = store.upsert_simulated_trades(trades)
    performance = summarize_simulated_performance(
        store.load_simulated_trades(),
        initial_capital=settings.simulated_initial_capital,
        portfolio_id="default",
    )
    store.save_performance_points(performance.points)
    return {"saved_count": len(saved), "performance": performance.model_dump(mode="json")}
```

Add manual trade endpoints:

```python
@app.post("/api/model-maintenance/auction-top3/manual-trades", response_model=AuctionTop3ManualTradeSample)
def save_auction_top3_manual_trade(sample: AuctionTop3ManualTradeSample) -> AuctionTop3ManualTradeSample:
    return _auction_top3_training_store().upsert_manual_trade(sample)


@app.patch("/api/model-maintenance/auction-top3/manual-trades/{sample_id}", response_model=AuctionTop3ManualTradeSample)
def update_auction_top3_manual_trade(sample_id: str, sample: AuctionTop3ManualTradeSample) -> AuctionTop3ManualTradeSample:
    if sample.sample_id != sample_id:
        raise HTTPException(status_code=422, detail="sample_id mismatch")
    return _auction_top3_training_store().upsert_manual_trade(sample)
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
PYTHONPATH=apps/api pytest apps/api/tests/test_auction_model.py::test_auction_model_api_records_top3_signal_samples apps/api/tests/test_auction_top3_training.py::test_training_performance_api_returns_summary -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/main.py apps/api/tests/test_auction_model.py apps/api/tests/test_auction_top3_training.py
git commit -m "Expose auction Top3 training APIs"
```

---

### Task 4: Model Maintenance Packet Links And Auction Sections

**Files:**
- Modify: `apps/api/app/services/model_maintenance_store.py`
- Modify: `apps/api/app/services/model_maintenance_packet.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_model_maintenance.py`

- [ ] **Step 1: Add failing packet tests**

Append to `apps/api/tests/test_model_maintenance.py`:

```python
from app.models import AuctionModelPredictionItem, AuctionModelTop3Response, AuctionTop3TrainingSummary


def test_model_maintenance_packet_includes_auction_top3_and_training_sections() -> None:
    auction_run = AuctionModelTop3Response(
        trade_date="2026-07-06",
        feature_end_date="2026-07-03",
        model_version="auction-model",
        feature_version="auction-features",
        guard_rule="guard",
        items=[
            AuctionModelPredictionItem(
                symbol="300001.SZ",
                name="模型一号",
                rank=1,
                prob_3pct=0.91,
                bucket="selected",
                guard_rule="guard",
            )
        ],
    )
    training = AuctionTop3TrainingSummary(
        signal_sample_count=3,
        simulated_trade_sample_count=3,
        simulated_profit_summary={"latest_equity": 102000, "cumulative_return_pct": 2.0},
    )

    packet = build_model_maintenance_packet(
        trade_date="2026-07-06",
        latest_screen_run=None,
        review_summary=None,
        calibration_summary=None,
        source_status=[],
        auction_top3_run=auction_run,
        auction_top3_training_summary=training,
        packet_base_url="http://testserver",
    )

    assert packet.packet_url == f"http://testserver/model-maintenance/packets/{packet.packet_id}"
    assert packet.model_sections["auction_top3"]["available"] is True
    assert packet.model_sections["auction_top3"]["items"][0]["symbol"] == "300001.SZ"
    assert packet.model_sections["auction_top3_training"]["signal_sample_count"] == 3
    assert packet.model_sections["auction_top3_training"]["simulated_profit_summary"]["latest_equity"] == 102000


def test_model_maintenance_store_loads_packet_by_id(tmp_path: Path) -> None:
    store = ModelMaintenanceStore(tmp_path)
    saved = store.save_packet(ModelMaintenancePacket(packet_id="packet-abc"))

    loaded = store.load_packet(saved.packet_id)

    assert loaded is not None
    assert loaded.packet_id == "packet-abc"


def test_model_maintenance_api_serves_packet_link(tmp_path: Path) -> None:
    app.state.runs_dir = tmp_path
    client = TestClient(app)
    try:
        generated = client.post("/api/model-maintenance/packets/generate")
        packet_id = generated.json()["packet_id"]
        fetched = client.get(f"/api/model-maintenance/packets/{packet_id}")
    finally:
        delattr(app.state, "runs_dir")

    assert generated.status_code == 200
    assert generated.json()["packet_url"].endswith(f"/model-maintenance/packets/{packet_id}")
    assert fetched.status_code == 200
    assert fetched.json()["packet_id"] == packet_id
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=apps/api pytest apps/api/tests/test_model_maintenance.py -q
```

Expected: FAIL because `auction_top3_run`, `auction_top3_training_summary`, `packet_url`, and packet-by-id loading are missing.

- [ ] **Step 3: Extend packet store**

In `apps/api/app/services/model_maintenance_store.py`, add:

```python
    def load_packet(self, packet_id: str) -> ModelMaintenancePacket | None:
        path = self.packets_dir / f"{packet_id}.json"
        if not path.exists():
            return None
        return ModelMaintenancePacket.model_validate_json(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Extend packet builder**

In `apps/api/app/services/model_maintenance_packet.py`, import `AuctionModelTop3Response` and `AuctionTop3TrainingSummary`. Update signature:

```python
    auction_top3_run: AuctionModelTop3Response | None = None,
    auction_top3_training_summary: AuctionTop3TrainingSummary | None = None,
    packet_base_url: str | None = None,
```

Build `packet_id = new_model_maintenance_id("packet")` before constructing the packet and set:

```python
model_sections={
    "gsgf": _gsgf_section(latest_screen_run),
    "auction_top3": _auction_top3_section(auction_top3_run),
    "auction_top3_training": _auction_top3_training_section(auction_top3_training_summary),
},
packet_url=f"{packet_base_url.rstrip('/')}/model-maintenance/packets/{packet_id}" if packet_base_url else None,
```

Implement `_auction_top3_section()`:

```python
def _auction_top3_section(run: AuctionModelTop3Response | None) -> dict[str, Any]:
    if run is None:
        return {"enabled": True, "available": False, "items": [], "notes": ["竞价 Top3 无缓存，本次未纳入模型维护。"]}
    selected = [item for item in run.items if item.bucket == "selected"]
    return {
        "enabled": True,
        "available": True,
        "trade_date": run.trade_date,
        "feature_end_date": run.feature_end_date,
        "model_version": run.model_version,
        "feature_version": run.feature_version,
        "guard_rule": run.guard_rule,
        "mode": run.mode,
        "cache_status": run.cache_status,
        "generated_at": run.generated_at,
        "top_count": len(selected),
        "watch_count": len([item for item in run.items if item.bucket in {"attack", "watch"}]),
        "backtest_summary": run.backtest.model_dump(mode="json") if run.backtest else None,
        "items": [
            {
                "symbol": item.symbol,
                "name": item.name,
                "rank": item.rank,
                "bucket": item.bucket,
                "prob_3pct": item.prob_3pct,
                "guard_rule": item.guard_rule,
                "trend_reasons": item.trend_reasons[:5],
                "risk_flags": item.risk_flags[:5],
                "data_quality": item.data_quality[:5],
            }
            for item in run.items[:10]
        ],
        "source_status": [status.model_dump(mode="json") for status in run.source_status],
        "notes": [],
    }
```

Implement `_auction_top3_training_section()`:

```python
def _auction_top3_training_section(summary: AuctionTop3TrainingSummary | None) -> dict[str, Any]:
    if summary is None:
        return {
            "enabled": True,
            "signal_sample_count": 0,
            "simulated_trade_sample_count": 0,
            "manual_trade_sample_count": 0,
            "simulated_profit_summary": {},
            "quality_notes": ["暂无竞价 Top3 训练样本摘要"],
        }
    return summary.model_dump(mode="json")
```

- [ ] **Step 5: Wire API packet generation and packet retrieval**

In `apps/api/app/main.py`, add helper:

```python
def _request_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")
```

Change packet route signature:

```python
@app.post("/api/model-maintenance/packets/generate", response_model=ModelMaintenancePacket)
def generate_model_maintenance_packet(request: Request) -> ModelMaintenancePacket:
```

Load cached auction run:

```python
trade_date = latest_screen_run.trade_date if latest_screen_run is not None else None
auction_top3_run = _auction_model_result_store().load_top3(trade_date) if trade_date else None
settings = _effective_settings().auction_top3_training
training_summary = _auction_top3_training_store().training_summary(
    training_window_days=settings.training_window_days,
    include_manual_training=settings.include_manual_trade_samples_in_training,
    enabled=settings.record_signal_samples,
)
```

Pass `packet_base_url=_request_base_url(request)`.

Add route:

```python
@app.get("/api/model-maintenance/packets/{packet_id}", response_model=ModelMaintenancePacket)
def get_model_maintenance_packet(packet_id: str) -> ModelMaintenancePacket:
    packet = _model_maintenance_store().load_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="维护包不存在")
    return packet
```

Update `analyze_model_maintenance()` to call a helper that does not need `Request` when no packet exists:

```python
if packet is None:
    packet = build_and_save_model_maintenance_packet(packet_base_url=None)
```

Create `build_and_save_model_maintenance_packet(packet_base_url: str | None)`.

- [ ] **Step 6: Run tests and verify they pass**

Run:

```bash
PYTHONPATH=apps/api pytest apps/api/tests/test_model_maintenance.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/services/model_maintenance_store.py apps/api/app/services/model_maintenance_packet.py apps/api/app/main.py apps/api/tests/test_model_maintenance.py
git commit -m "Include auction Top3 in maintenance packets"
```

---

### Task 5: AI Prompt And Offline Report

**Files:**
- Modify: `apps/api/app/services/ai_model_analysis.py`
- Modify: `apps/api/tests/test_model_maintenance.py`

- [ ] **Step 1: Add failing AI analysis tests**

Append to `apps/api/tests/test_model_maintenance.py`:

```python
def test_offline_ai_report_mentions_auction_top3_training_when_present() -> None:
    packet = ModelMaintenancePacket(
        packet_id="packet-1",
        trade_date="2026-07-06",
        model_sections={
            "auction_top3": {"available": True, "top_count": 3},
            "auction_top3_training": {
                "signal_sample_count": 9,
                "simulated_trade_sample_count": 6,
                "simulated_profit_summary": {"cumulative_return_pct": 3.2, "max_drawdown_pct": -1.1},
            },
        },
    )

    report = build_offline_model_maintenance_report(packet)

    assert "竞价 Top3" in report.summary
    assert any("模拟收益" in finding for finding in report.key_findings)


def test_online_ai_prompt_contains_auction_sections() -> None:
    packet = ModelMaintenancePacket(
        packet_id="packet-1",
        trade_date="2026-07-06",
        model_sections={"auction_top3": {"available": True}, "auction_top3_training": {"signal_sample_count": 3}},
    )
    http_client = FakeAiHttpClient()

    analyze_model_maintenance_packet(
        packet,
        EffectiveAiAnalysisSettings(
            enabled=True,
            provider="deepseek",
            base_url="https://api.deepseek.com",
            model="deepseek-reasoner",
            api_key="deepseek-test-key",
            api_key_source="runtime",
            run_after_daily_review=True,
            run_after_weekly_calibration=False,
        ),
        http_client=http_client,
    )

    prompt = http_client.request["json"]["messages"][1]["content"]
    assert "auction_top3" in prompt
    assert "auction_top3_training" in prompt
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=apps/api pytest apps/api/tests/test_model_maintenance.py::test_offline_ai_report_mentions_auction_top3_training_when_present apps/api/tests/test_model_maintenance.py::test_online_ai_prompt_contains_auction_sections -q
```

Expected: FAIL because offline report and prompt do not mention auction sections.

- [ ] **Step 3: Extend prompt and offline analysis**

In `apps/api/app/services/ai_model_analysis.py`, update the system prompt to include:

```python
"维护包可能同时包含 GSGF 选股模型、竞价 Top3 模型和 auction_top3_training 训练样本摘要。必须分别评价，不得把模拟交易收益当真实收益。"
```

In offline report builder:

```python
sections = packet.model_sections or {}
auction = sections.get("auction_top3", {})
training = sections.get("auction_top3_training", {})
if auction.get("available"):
    findings.append(f"竞价 Top3 已纳入维护包，Top 数量 {auction.get('top_count', 0)}。")
if training:
    profit = training.get("simulated_profit_summary") or {}
    findings.append(
        "竞价 Top3 训练样本：信号 {signals} 条，模拟交易 {trades} 条，模拟收益 {ret}%。".format(
            signals=training.get("signal_sample_count", 0),
            trades=training.get("simulated_trade_sample_count", 0),
            ret=profit.get("cumulative_return_pct", "--"),
        )
    )
```

Ensure `summary` says:

```python
"已生成 GSGF 与竞价 Top3 的离线模型维护摘要。"
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
PYTHONPATH=apps/api pytest apps/api/tests/test_model_maintenance.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/ai_model_analysis.py apps/api/tests/test_model_maintenance.py
git commit -m "Analyze auction Top3 maintenance context"
```

---

### Task 6: Web API Types And Packet Reader

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Create: `apps/web/app/model-maintenance/packets/[packetId]/page.tsx`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Add failing frontend wiring test**

In `apps/web/lib/strongStockWorkbench.test.ts`, add assertions in the model maintenance test block:

```ts
assert.match(typesSource, /AuctionTop3TrainingSummary/);
assert.match(typesSource, /AuctionTop3PerformanceResponse/);
assert.match(typesSource, /packet_url: string \\| null/);
assert.match(apiSource, /getLatestModelMaintenancePacket/);
assert.match(apiSource, /getModelMaintenancePacket/);
assert.match(apiSource, /getAuctionTop3TrainingSummary/);
assert.match(apiSource, /getAuctionTop3TrainingPerformance/);
assert.match(apiSource, /generateAuctionTop3TrainingSamples/);
```

Add a file source read for `../app/model-maintenance/packets/[packetId]/page.tsx` and assert:

```ts
assert.match(packetPageSource, /维护包链接/);
assert.match(packetPageSource, /api\\/model-maintenance\\/packets/);
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd apps/web && pnpm test -- strongStockWorkbench
```

Expected: FAIL because types/API/page do not exist.

- [ ] **Step 3: Add frontend types**

In `apps/web/lib/types.ts`, add:

```ts
export type AuctionTop3TrainingSummary = {
  enabled: boolean;
  signal_sample_count: number;
  simulated_trade_sample_count: number;
  manual_trade_sample_count: number;
  date_range: string[];
  training_window_days: number;
  latest_generated_at: string | null;
  simulated_profit_summary: Record<string, unknown>;
  quality_notes: string[];
};

export type AuctionTop3SimulatedPerformancePoint = {
  portfolio_id: string;
  trade_date: string;
  entry_policy: string;
  exit_policy: string;
  trade_count: number;
  win_count: number;
  loss_count: number;
  daily_return_pct: number | null;
  cumulative_return_pct: number | null;
  equity: number | null;
  max_drawdown_pct: number | null;
  created_at: string;
};

export type AuctionTop3PerformanceResponse = {
  summary: Record<string, unknown>;
  points: AuctionTop3SimulatedPerformancePoint[];
  trades: Array<Record<string, unknown>>;
  generated_at: string;
};
```

Extend `ModelMaintenancePacket`:

```ts
  model_sections: Record<string, unknown>;
  packet_url: string | null;
```

- [ ] **Step 4: Add API clients**

In `apps/web/lib/api.ts`, add:

```ts
export async function getLatestModelMaintenancePacket(): Promise<ModelMaintenancePacket | null> {
  const response = await fetch(`${API_BASE_URL}/api/model-maintenance/packets/latest`);
  if (!response.ok) {
    throw new Error(`读取模型维护包失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<ModelMaintenancePacket | null>;
}

export async function getModelMaintenancePacket(packetId: string): Promise<ModelMaintenancePacket> {
  const response = await fetch(`${API_BASE_URL}/api/model-maintenance/packets/${encodeURIComponent(packetId)}`);
  if (!response.ok) {
    throw new Error(`读取模型维护包失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<ModelMaintenancePacket>;
}

export async function getAuctionTop3TrainingSummary(): Promise<AuctionTop3TrainingSummary> {
  const response = await fetch(`${API_BASE_URL}/api/model-maintenance/auction-top3/training/summary`);
  if (!response.ok) {
    throw new Error(`读取竞价 Top3 训练摘要失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<AuctionTop3TrainingSummary>;
}

export async function getAuctionTop3TrainingPerformance(): Promise<AuctionTop3PerformanceResponse> {
  const response = await fetch(`${API_BASE_URL}/api/model-maintenance/auction-top3/training/performance`);
  if (!response.ok) {
    throw new Error(`读取竞价 Top3 模拟收益失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<AuctionTop3PerformanceResponse>;
}

export async function generateAuctionTop3TrainingSamples(tradeDate?: string): Promise<Record<string, unknown>> {
  const params = new URLSearchParams();
  if (tradeDate) params.set("trade_date", tradeDate);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}/api/model-maintenance/auction-top3/training/generate${suffix}`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`生成竞价 Top3 训练样本失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<Record<string, unknown>>;
}
```

- [ ] **Step 5: Add packet reader page**

Create `apps/web/app/model-maintenance/packets/[packetId]/page.tsx`:

```tsx
import { API_BASE_URL } from "../../../../lib/api";

type PageProps = { params: Promise<{ packetId: string }> };

export default async function ModelMaintenancePacketPage({ params }: PageProps) {
  const { packetId } = await params;
  const apiUrl = `${API_BASE_URL}/api/model-maintenance/packets/${encodeURIComponent(packetId)}`;
  return (
    <main className="workbench-page min-h-screen p-5">
      <div className="mb-4">
        <p className="workbench-muted text-xs font-semibold uppercase">Model Maintenance Packet</p>
        <h1 className="m-0 text-2xl font-black text-[#11100e]">维护包链接</h1>
        <p className="workbench-muted mt-2">把下面的 JSON 链接复制给 Codex，即可基于同一份维护包分析。</p>
      </div>
      <section className="workbench-panel rounded-xl border p-4">
        <p className="text-sm text-[#6f6a62]">维护包 ID</p>
        <p className="font-mono text-base text-[#11100e]">{packetId}</p>
        <p className="mt-4 text-sm text-[#6f6a62]">JSON API</p>
        <a className="break-all font-mono text-sm text-[#b42318]" href={apiUrl}>
          {apiUrl}
        </a>
      </section>
    </main>
  );
}
```

- [ ] **Step 6: Run tests and verify they pass**

Run:

```bash
cd apps/web && pnpm test -- strongStockWorkbench
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/web/lib/types.ts apps/web/lib/api.ts apps/web/app/model-maintenance/packets/[packetId]/page.tsx apps/web/lib/strongStockWorkbench.test.ts
git commit -m "Add model maintenance packet clients"
```

---

### Task 7: Model Maintenance Workspace UI

**Files:**
- Modify: `apps/web/app/model-maintenance/ModelMaintenanceWorkspace.tsx`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Add failing UI string test**

In `apps/web/lib/strongStockWorkbench.test.ts`, assert in the model maintenance component source:

```ts
assert.match(modelMaintenanceFeatureSource, /生成维护包/);
assert.match(modelMaintenanceFeatureSource, /提交给 AI 分析/);
assert.match(modelMaintenanceFeatureSource, /复制 Codex 分析链接/);
assert.match(modelMaintenanceFeatureSource, /Top3 训练数据/);
assert.match(modelMaintenanceFeatureSource, /模拟收益概览/);
assert.match(modelMaintenanceFeatureSource, /离线规则摘要/);
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd apps/web && pnpm test -- strongStockWorkbench
```

Expected: FAIL because the new UI strings are missing.

- [ ] **Step 3: Update workspace state and data loading**

In `ModelMaintenanceWorkspace.tsx`, import the new API functions and types. Add state:

```ts
const [packet, setPacket] = useState<ModelMaintenancePacket | null>(null);
const [trainingSummary, setTrainingSummary] = useState<AuctionTop3TrainingSummary | null>(null);
const [performance, setPerformance] = useState<AuctionTop3PerformanceResponse | null>(null);
const [generatingPacket, setGeneratingPacket] = useState(false);
const [generatingTraining, setGeneratingTraining] = useState(false);
```

Change initial load to fetch latest report, packet, training summary, and performance with `Promise.allSettled()`. Keep partial data if one request fails.

- [ ] **Step 4: Split actions**

Replace `handleAnalyze()` with:

```ts
async function handleGeneratePacket() {
  setGeneratingPacket(true);
  setError(null);
  try {
    const nextPacket = await generateModelMaintenancePacket();
    setPacket(nextPacket);
    void message.success("维护包已生成，下一步可提交给 AI 分析或复制给 Codex");
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : "生成维护包失败";
    setError(errorMessage);
    void message.error(errorMessage);
  } finally {
    setGeneratingPacket(false);
  }
}

async function handleSubmitAiAnalysis() {
  setAnalyzing(true);
  setError(null);
  try {
    const nextReport = await analyzeModelMaintenance();
    setReport(nextReport);
    void message.success(nextReport.model === "offline-rule-summary" ? "已生成离线规则摘要" : "AI 模型维护分析已生成");
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : "提交 AI 分析失败";
    setError(errorMessage);
    void message.error(errorMessage);
  } finally {
    setAnalyzing(false);
  }
}
```

Add copy handler:

```ts
async function handleCopyCodexLink(withPrompt = false) {
  if (!packet?.packet_url) {
    void message.warning("请先生成维护包");
    return;
  }
  const text = withPrompt
    ? `请打开这个维护包链接，分析 GSGF 和竞价 Top3 模型是否退化，并给出只观察不自动改规则的建议：${packet.packet_url}`
    : packet.packet_url;
  await navigator.clipboard.writeText(text);
  void message.success("已复制 Codex 分析链接");
}
```

Add `handleGenerateTrainingSamples()` to call `generateAuctionTop3TrainingSamples()`, then reload summary/performance.

- [ ] **Step 5: Add cards**

Add cards above report content:

- `维护包`
  - packet id, generated time, trade date, packet link, buttons.
- `AI 分析`
  - report provider/model, show `离线规则摘要` alert when `report?.model === "offline-rule-summary"`.
- `Top3 训练数据`
  - training sample counts, training window, simulated profit summary.
  - show `模拟收益概览` with cumulative return, today return, max drawdown, win rate.
  - render an Ant Design `Table` for `performance.points.slice(-10)` with columns `日期`、`交易数`、`胜`、`负`、`日收益`、`累计收益`、`权益`、`最大回撤`.

Do not add a charting library. Use Ant Design cards, descriptions, tags, and a compact table/list to keep scope small.

- [ ] **Step 6: Run frontend tests**

Run:

```bash
cd apps/web && pnpm test -- strongStockWorkbench
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/web/app/model-maintenance/ModelMaintenanceWorkspace.tsx apps/web/lib/strongStockWorkbench.test.ts
git commit -m "Improve model maintenance workflow UI"
```

---

### Task 8: Settings UI For Top3 Training Toggles

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/app/settings/SettingsWorkspace.tsx`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Add failing settings test**

In the existing settings test source assertions, add:

```ts
assert.match(settingsFeatureSource, /竞价 Top3 训练/);
assert.match(settingsFeatureSource, /记录 Top3 信号样本/);
assert.match(settingsFeatureSource, /生成模拟交易样本/);
assert.match(settingsFeatureSource, /模拟账户本金/);
assert.match(settingsFeatureSource, /模拟仓位比例/);
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd apps/web && pnpm test -- strongStockWorkbench
```

Expected: FAIL because settings UI does not show Top3 training config.

- [ ] **Step 3: Add settings types and form fields**

In `apps/web/lib/types.ts`, add:

```ts
export type AuctionTop3TrainingSettings = {
  record_signal_samples: boolean;
  generate_simulated_trade_samples: boolean;
  include_manual_trade_samples_in_training: boolean;
  training_window_days: number;
  simulated_initial_capital: number;
  simulated_position_pct: number;
};
```

Add `auction_top3_training: AuctionTop3TrainingSettings` to runtime config types and settings update payload.

In `SettingsWorkspace.tsx`, add draft fields:

```ts
auction_top3_record_signal_samples: boolean;
auction_top3_generate_simulated_trade_samples: boolean;
auction_top3_include_manual_trade_samples_in_training: boolean;
auction_top3_training_window_days: number;
auction_top3_simulated_initial_capital: number;
auction_top3_simulated_position_pct: number;
```

Add a card titled `竞价 Top3 训练` with switches and numeric inputs.

- [ ] **Step 4: Run test and verify it passes**

Run:

```bash
cd apps/web && pnpm test -- strongStockWorkbench
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/types.ts apps/web/app/settings/SettingsWorkspace.tsx apps/web/lib/strongStockWorkbench.test.ts
git commit -m "Add auction Top3 training settings"
```

---

### Task 9: Full Verification

**Files:**
- No planned edits unless verification exposes defects.

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
PYTHONPATH=apps/api pytest \
  apps/api/tests/test_auction_top3_training.py \
  apps/api/tests/test_auction_model.py \
  apps/api/tests/test_model_maintenance.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run focused frontend tests**

Run:

```bash
cd apps/web && pnpm test -- strongStockWorkbench
```

Expected: PASS.

- [ ] **Step 3: Run lint/build checks used by this repo**

Run:

```bash
cd apps/web && pnpm build
```

Expected: PASS.

- [ ] **Step 4: Manual API smoke test**

Run the local app and check:

```bash
curl -s http://127.0.0.1:3110/api/model-maintenance/auction-top3/training/summary | jq .
curl -s -X POST http://127.0.0.1:3110/api/model-maintenance/packets/generate | jq '.packet_id,.packet_url,.model_sections.auction_top3_training'
```

Expected: summary JSON is returned; packet JSON includes `packet_url` and `model_sections.auction_top3_training`.

- [ ] **Step 5: Commit any verification fixes**

If verification required fixes:

```bash
git add apps/api/app apps/api/tests apps/web/app apps/web/lib
git commit -m "Stabilize auction Top3 maintenance workflow"
```

If no fixes were needed, do not create an empty commit.
