# AI Model Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first usable AI-assisted model maintenance loop: structured GSGF maintenance packets, validated AI reports, suggestion status management, APIs, settings fields, and a dedicated `/model-maintenance` page.

**Architecture:** Keep the feature behind explicit APIs and a separate page. The backend generates deterministic JSON packets from existing screening/review/calibration data, then optionally runs an OpenAI-compatible analysis adapter that returns a validated report and suggestions. The frontend removes complex model diagnostics from the homepage and links to a dedicated maintenance workspace.

**Tech Stack:** FastAPI + Pydantic + file-backed stores in `apps/api`; Next.js + React + Ant Design in `apps/web`; existing runtime settings and notification infrastructure.

---

## File Structure

- Create `apps/api/app/services/model_maintenance_store.py`
  - Owns packet/report persistence and suggestion status updates.
- Create `apps/api/app/services/model_maintenance_packet.py`
  - Builds a compact `ModelMaintenancePacket` from latest screen run, GSGF review, calibration, and source state.
- Create `apps/api/app/services/ai_model_analysis.py`
  - OpenAI-compatible adapter, prompt construction, JSON validation, and fallback deterministic summary when no provider is configured.
- Modify `apps/api/app/models.py`
  - Add packet, report, suggestion, request, and AI config models.
- Modify `apps/api/app/services/runtime_settings.py`
  - Persist public AI analysis settings without exposing API keys.
- Modify `apps/api/app/main.py`
  - Add `/api/model-maintenance/*` endpoints and wire store/service singletons.
- Create `apps/api/tests/test_model_maintenance.py`
  - Packet/store/AI adapter unit tests and API tests.
- Modify `apps/web/lib/types.ts`
  - Add API response and config types.
- Modify `apps/web/lib/api.ts`
  - Add model maintenance API client functions and settings payload fields.
- Create `apps/web/app/model-maintenance/page.tsx`
  - Dynamic page entry.
- Create `apps/web/app/model-maintenance/ModelMaintenanceWorkspace.tsx`
  - Report, suggestions, provider status, and manual analyze UI.
- Modify `apps/web/components/AppShell.tsx`
  - Add navigation entry.
- Modify `apps/web/components/ScreenerWorkbench.tsx`
  - Replace homepage diagnostics panel with lightweight model status link.
- Modify `apps/web/app/settings/SettingsWorkspace.tsx`
  - Add AI analysis provider configuration.
- Modify `apps/web/lib/strongStockWorkbench.test.ts`
  - Assert homepage uses a lightweight model maintenance link.

---

### Task 1: Backend Models And Store

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/services/model_maintenance_store.py`
- Test: `apps/api/tests/test_model_maintenance.py`

- [ ] **Step 1: Write failing store/model tests**

Add tests proving reports and suggestion statuses are persisted:

```python
from pathlib import Path

from app.models import (
    ModelMaintenanceReport,
    ModelMaintenanceSuggestion,
)
from app.services.model_maintenance_store import ModelMaintenanceStore


def test_model_maintenance_store_saves_latest_report_and_updates_suggestion(tmp_path: Path) -> None:
    store = ModelMaintenanceStore(tmp_path)
    report = ModelMaintenanceReport(
        report_id="report-1",
        packet_id="packet-1",
        provider="openai_compatible",
        model="test-model",
        health_status="watch",
        summary="模型处于观察状态。",
        key_findings=["放量突破样本表现稳定"],
        suggestions=[
            ModelMaintenanceSuggestion(
                suggestion_id="s1",
                type="observe",
                title="继续观察放量滞涨规则",
                reason="样本不足，不直接调参。",
                risk="过早调整可能增加误判。",
                confidence=0.52,
                suggested_action="观察三个交易日",
            )
        ],
    )

    store.save_report(report)
    loaded = store.load_latest_report()

    assert loaded is not None
    assert loaded.report_id == "report-1"
    assert loaded.suggestions[0].status == "pending"

    updated = store.update_suggestion_status("s1", "ignored")

    assert updated.status == "ignored"
    assert store.load_latest_report().suggestions[0].status == "ignored"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/api && uv run pytest tests/test_model_maintenance.py::test_model_maintenance_store_saves_latest_report_and_updates_suggestion -q
```

Expected: fail because `ModelMaintenanceReport` and `ModelMaintenanceStore` do not exist.

- [ ] **Step 3: Add Pydantic models**

Add to `apps/api/app/models.py`:

```python
ModelMaintenanceProvider = Literal["openai", "deepseek", "openai_compatible"]
ModelMaintenanceHealthStatus = Literal["normal", "watch", "degraded", "insufficient_sample", "data_unreliable"]
ModelMaintenanceRuleStatus = Literal["effective", "neutral", "over_strict", "under_strict", "degraded", "insufficient_sample"]
ModelMaintenanceSuggestionType = Literal[
    "observe",
    "adjust_weight",
    "loosen_filter",
    "tighten_filter",
    "disable_rule_temporarily",
    "data_check",
]
ModelMaintenanceSuggestionStatus = Literal["pending", "accepted", "ignored", "snoozed"]


class ModelMaintenanceSuggestion(BaseModel):
    suggestion_id: str
    type: ModelMaintenanceSuggestionType = "observe"
    title: str
    reason: str
    evidence_refs: list[str] = Field(default_factory=list)
    risk: str = "仅供模型维护参考，不构成投资建议。"
    confidence: float = Field(default=0, ge=0, le=1)
    suggested_action: str = "观察，不自动调整。"
    status: ModelMaintenanceSuggestionStatus = "pending"


class ModelMaintenanceRuleDiagnostic(BaseModel):
    rule_name: str
    status: ModelMaintenanceRuleStatus = "neutral"
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)


class ModelMaintenancePacket(BaseModel):
    packet_id: str
    generated_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
    trade_date: str | None = None
    model_name: str = "gsgf"
    model_version: str | None = None
    screen_strategy: str | None = None
    screen_params: dict[str, Any] = Field(default_factory=dict)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    latest_screen_run: dict[str, Any] = Field(default_factory=dict)
    review_summary: dict[str, Any] = Field(default_factory=dict)
    calibration_summary: dict[str, Any] = Field(default_factory=dict)
    false_negative_cases: list[dict[str, Any]] = Field(default_factory=list)
    false_positive_cases: list[dict[str, Any]] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)


class ModelMaintenanceReport(BaseModel):
    report_id: str
    packet_id: str
    provider: ModelMaintenanceProvider = "openai_compatible"
    model: str
    generated_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
    health_status: ModelMaintenanceHealthStatus = "insufficient_sample"
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    rule_diagnostics: list[ModelMaintenanceRuleDiagnostic] = Field(default_factory=list)
    suggestions: list[ModelMaintenanceSuggestion] = Field(default_factory=list)
    disclaimer: str = "仅供模型复盘与参数维护参考，不构成投资建议。"
```

- [ ] **Step 4: Implement file-backed store**

Create `apps/api/app/services/model_maintenance_store.py`:

```python
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.models import (
    ModelMaintenancePacket,
    ModelMaintenanceReport,
    ModelMaintenanceSuggestion,
    ModelMaintenanceSuggestionStatus,
)


class ModelMaintenanceStore:
    def __init__(self, data_dir: Path) -> None:
        self.root_dir = data_dir / "model_maintenance"
        self.packets_dir = self.root_dir / "packets"
        self.reports_dir = self.root_dir / "reports"
        self.latest_packet_path = self.root_dir / "latest_packet.json"
        self.latest_report_path = self.root_dir / "latest_report.json"

    def save_packet(self, packet: ModelMaintenancePacket) -> ModelMaintenancePacket:
        self.packets_dir.mkdir(parents=True, exist_ok=True)
        payload = packet.model_dump_json(indent=2)
        (self.packets_dir / f"{packet.packet_id}.json").write_text(payload, encoding="utf-8")
        self.latest_packet_path.parent.mkdir(parents=True, exist_ok=True)
        self.latest_packet_path.write_text(payload, encoding="utf-8")
        return packet

    def load_latest_packet(self) -> ModelMaintenancePacket | None:
        if not self.latest_packet_path.exists():
            return None
        return ModelMaintenancePacket.model_validate_json(self.latest_packet_path.read_text(encoding="utf-8"))

    def save_report(self, report: ModelMaintenanceReport) -> ModelMaintenanceReport:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        payload = report.model_dump_json(indent=2)
        (self.reports_dir / f"{report.report_id}.json").write_text(payload, encoding="utf-8")
        self.latest_report_path.parent.mkdir(parents=True, exist_ok=True)
        self.latest_report_path.write_text(payload, encoding="utf-8")
        return report

    def load_latest_report(self) -> ModelMaintenanceReport | None:
        if not self.latest_report_path.exists():
            return None
        return ModelMaintenanceReport.model_validate_json(self.latest_report_path.read_text(encoding="utf-8"))

    def list_reports(self, limit: int = 20) -> list[ModelMaintenanceReport]:
        if not self.reports_dir.exists():
            return []
        paths = sorted(self.reports_dir.glob("*.json"), reverse=True)[: max(1, min(limit, 100))]
        return [ModelMaintenanceReport.model_validate_json(path.read_text(encoding="utf-8")) for path in paths]

    def update_suggestion_status(
        self,
        suggestion_id: str,
        status: ModelMaintenanceSuggestionStatus,
    ) -> ModelMaintenanceSuggestion:
        report = self.load_latest_report()
        if report is None:
            raise KeyError(suggestion_id)
        updated: ModelMaintenanceSuggestion | None = None
        for suggestion in report.suggestions:
            if suggestion.suggestion_id == suggestion_id:
                suggestion.status = status
                updated = suggestion
                break
        if updated is None:
            raise KeyError(suggestion_id)
        self.save_report(report)
        return updated


def new_model_maintenance_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"
```

- [ ] **Step 5: Run store/model test**

Run:

```bash
cd apps/api && uv run pytest tests/test_model_maintenance.py::test_model_maintenance_store_saves_latest_report_and_updates_suggestion -q
```

Expected: pass.

---

### Task 2: Packet Builder And AI Analysis Adapter

**Files:**
- Create: `apps/api/app/services/model_maintenance_packet.py`
- Create: `apps/api/app/services/ai_model_analysis.py`
- Modify: `apps/api/tests/test_model_maintenance.py`

- [ ] **Step 1: Write failing tests**

Append:

```python
from app.models import GsgfReviewBucket, GsgfReviewSummary, ModelMaintenancePacket, StrongStockSourceStatus
from app.services.ai_model_analysis import build_offline_model_maintenance_report
from app.services.model_maintenance_packet import build_model_maintenance_packet


def test_model_maintenance_packet_includes_review_and_quality_notes() -> None:
    review = GsgfReviewSummary(
        windows=[1, 3, 5],
        record_count=2,
        buckets=[
            GsgfReviewBucket(
                signal_type="确认买点",
                status="确认买点",
                sample_count=2,
                confirmed_count=1,
                avg_return_pct=2.5,
                avg_max_drawdown_pct=-3.2,
            )
        ],
    )

    packet = build_model_maintenance_packet(
        trade_date="2026-07-04",
        latest_screen_run=None,
        review_summary=review,
        calibration_summary=None,
        source_status=[StrongStockSourceStatus(source="tickflow", status="success", detail="ok")],
    )

    assert packet.trade_date == "2026-07-04"
    assert packet.review_summary["record_count"] == 2
    assert packet.review_summary["buckets"][0]["signal_type"] == "确认买点"
    assert packet.data_quality_notes == []


def test_offline_ai_report_marks_small_samples_as_insufficient() -> None:
    packet = ModelMaintenancePacket(
        packet_id="packet-1",
        trade_date="2026-07-04",
        review_summary={"record_count": 2, "buckets": []},
    )

    report = build_offline_model_maintenance_report(packet)

    assert report.health_status == "insufficient_sample"
    assert report.suggestions[0].type == "observe"
    assert "不构成投资建议" in report.disclaimer
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd apps/api && uv run pytest tests/test_model_maintenance.py::test_model_maintenance_packet_includes_review_and_quality_notes tests/test_model_maintenance.py::test_offline_ai_report_marks_small_samples_as_insufficient -q
```

Expected: fail because modules do not exist.

- [ ] **Step 3: Implement packet builder**

Create `apps/api/app/services/model_maintenance_packet.py`:

```python
from __future__ import annotations

from typing import Any

from app.models import (
    GsgfRealCalibrationSummary,
    GsgfReviewSummary,
    ModelMaintenancePacket,
    StrongStockScreeningResult,
    StrongStockSourceStatus,
)
from app.services.model_maintenance_store import new_model_maintenance_id


def build_model_maintenance_packet(
    *,
    trade_date: str | None,
    latest_screen_run: StrongStockScreeningResult | None,
    review_summary: GsgfReviewSummary | None,
    calibration_summary: GsgfRealCalibrationSummary | None,
    source_status: list[StrongStockSourceStatus],
) -> ModelMaintenancePacket:
    selected_items = latest_screen_run.items if latest_screen_run else []
    first_gsgf = next((item.gsgf for item in selected_items if item.gsgf is not None), None)
    notes = _data_quality_notes(source_status)
    return ModelMaintenancePacket(
        packet_id=new_model_maintenance_id("packet"),
        trade_date=trade_date or (latest_screen_run.trade_date if latest_screen_run else None),
        model_version=first_gsgf.model_version if first_gsgf else None,
        screen_strategy=latest_screen_run.strategy if latest_screen_run else None,
        screen_params={
            "limit": latest_screen_run.limit,
            "scan_limit": latest_screen_run.scan_limit,
            "filters": latest_screen_run.filters,
        }
        if latest_screen_run
        else {},
        source_status=source_status,
        latest_screen_run=_screen_run_summary(latest_screen_run),
        review_summary=_review_summary(review_summary),
        calibration_summary=_calibration_summary(calibration_summary),
        false_negative_cases=[],
        false_positive_cases=_false_positive_cases(latest_screen_run),
        data_quality_notes=notes,
    )


def _screen_run_summary(result: StrongStockScreeningResult | None) -> dict[str, Any]:
    if result is None:
        return {}
    return {
        "run_id": result.run_id,
        "result_hash": result.result_hash,
        "candidate_pool_hash": result.candidate_pool_hash,
        "candidate_count": result.candidate_count,
        "selected_count": len(result.items),
        "sort_version": result.sort_version,
        "rule_version": result.rule_version,
    }


def _review_summary(summary: GsgfReviewSummary | None) -> dict[str, Any]:
    if summary is None:
        return {}
    return {
        "windows": summary.windows,
        "record_count": summary.record_count,
        "buckets": [bucket.model_dump() for bucket in summary.buckets[:20]],
    }


def _calibration_summary(summary: GsgfRealCalibrationSummary | None) -> dict[str, Any]:
    if summary is None:
        return {}
    return {
        "trade_dates": summary.trade_dates,
        "scanned_count": summary.scanned_count,
        "target_sample_count": summary.target_sample_count,
        "skipped_count": summary.skipped_count,
        "buckets": [bucket.model_dump() for bucket in summary.buckets[:20]],
        "diagnostic_groups": [group.model_dump() for group in summary.diagnostic_groups[:20]],
    }


def _false_positive_cases(result: StrongStockScreeningResult | None) -> list[dict[str, Any]]:
    if result is None:
        return []
    output: list[dict[str, Any]] = []
    for item in result.items[:20]:
        if item.risk_flags:
            output.append(
                {
                    "symbol": item.symbol,
                    "name": item.name,
                    "score": item.score,
                    "risk_flags": item.risk_flags[:5],
                    "gsgf_status": item.gsgf.final_status if item.gsgf else None,
                }
            )
    return output


def _data_quality_notes(source_status: list[StrongStockSourceStatus]) -> list[str]:
    notes: list[str] = []
    for status in source_status:
        if status.status != "success":
            notes.append(f"{status.source}: {status.status} · {status.detail}")
    return notes
```

- [ ] **Step 4: Implement offline AI report builder**

Create `apps/api/app/services/ai_model_analysis.py`:

```python
from __future__ import annotations

from app.models import ModelMaintenancePacket, ModelMaintenanceReport, ModelMaintenanceSuggestion
from app.services.model_maintenance_store import new_model_maintenance_id


def build_offline_model_maintenance_report(packet: ModelMaintenancePacket) -> ModelMaintenanceReport:
    record_count = int(packet.review_summary.get("record_count") or 0)
    data_unreliable = bool(packet.data_quality_notes)
    if data_unreliable:
        health_status = "data_unreliable"
        summary = "数据源存在异常，建议优先检查数据质量，再判断模型表现。"
        suggestion_type = "data_check"
        title = "检查模型维护数据源"
    elif record_count < 5:
        health_status = "insufficient_sample"
        summary = "模型维护样本不足，当前只适合观察，不建议调整参数。"
        suggestion_type = "observe"
        title = "继续积累模型维护样本"
    else:
        health_status = "watch"
        summary = "模型样本已可观察，建议结合规则分桶继续跟踪。"
        suggestion_type = "observe"
        title = "观察近期规则分桶表现"
    return ModelMaintenanceReport(
        report_id=new_model_maintenance_id("report"),
        packet_id=packet.packet_id,
        provider="openai_compatible",
        model="offline-rule-summary",
        health_status=health_status,
        summary=summary,
        key_findings=[summary],
        suggestions=[
            ModelMaintenanceSuggestion(
                suggestion_id=new_model_maintenance_id("suggestion"),
                type=suggestion_type,
                title=title,
                reason=summary,
                evidence_refs=[packet.packet_id],
                confidence=0.5 if record_count < 5 else 0.6,
                suggested_action="先观察，不自动修改模型参数。",
            )
        ],
    )
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd apps/api && uv run pytest tests/test_model_maintenance.py -q
```

Expected: pass.

---

### Task 3: Backend APIs

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_model_maintenance.py`

- [ ] **Step 1: Write failing API test**

Append:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_model_maintenance_api_generates_packet_and_report() -> None:
    client = TestClient(app)

    packet_response = client.post("/api/model-maintenance/packets/generate")
    assert packet_response.status_code == 200
    packet_payload = packet_response.json()
    assert packet_payload["packet_id"].startswith("packet-")

    analyze_response = client.post("/api/model-maintenance/analyze")
    assert analyze_response.status_code == 200
    report_payload = analyze_response.json()
    assert report_payload["packet_id"] == packet_payload["packet_id"]
    assert report_payload["suggestions"]

    suggestion_id = report_payload["suggestions"][0]["suggestion_id"]
    ignore_response = client.post(f"/api/model-maintenance/suggestions/{suggestion_id}/ignore")
    assert ignore_response.status_code == 200
    assert ignore_response.json()["status"] == "ignored"
```

- [ ] **Step 2: Run API test to verify failure**

Run:

```bash
cd apps/api && uv run pytest tests/test_model_maintenance.py::test_model_maintenance_api_generates_packet_and_report -q
```

Expected: fail with 404.

- [ ] **Step 3: Wire stores and endpoints**

In `apps/api/app/main.py`:

- Import `ModelMaintenancePacket`, `ModelMaintenanceReport`, `ModelMaintenanceSuggestion`.
- Import `build_offline_model_maintenance_report`.
- Import `build_model_maintenance_packet`.
- Import `ModelMaintenanceStore`.
- Add singleton `MODEL_MAINTENANCE_STORE = ModelMaintenanceStore(get_settings().data_dir_path)`.
- Add helper `_latest_model_maintenance_packet()` that loads latest packet or generates one.
- Add endpoints:

```python
@app.post("/api/model-maintenance/packets/generate", response_model=ModelMaintenancePacket)
def generate_model_maintenance_packet() -> ModelMaintenancePacket:
    packet = build_model_maintenance_packet(
        trade_date=None,
        latest_screen_run=RUN_STORE.load_latest(),
        review_summary=GSGF_REVIEW_STORE.load_latest_summary(),
        calibration_summary=BACKGROUND_JOBS.load_latest_calibration(),
        source_status=_data_source_status_items(),
    )
    return MODEL_MAINTENANCE_STORE.save_packet(packet)


@app.get("/api/model-maintenance/packets/latest", response_model=ModelMaintenancePacket | None)
def get_latest_model_maintenance_packet() -> ModelMaintenancePacket | None:
    return MODEL_MAINTENANCE_STORE.load_latest_packet()


@app.post("/api/model-maintenance/analyze", response_model=ModelMaintenanceReport)
def analyze_model_maintenance() -> ModelMaintenanceReport:
    packet = MODEL_MAINTENANCE_STORE.load_latest_packet()
    if packet is None:
        packet = generate_model_maintenance_packet()
    report = build_offline_model_maintenance_report(packet)
    return MODEL_MAINTENANCE_STORE.save_report(report)


@app.get("/api/model-maintenance/reports/latest", response_model=ModelMaintenanceReport | None)
def get_latest_model_maintenance_report() -> ModelMaintenanceReport | None:
    return MODEL_MAINTENANCE_STORE.load_latest_report()


@app.get("/api/model-maintenance/reports", response_model=list[ModelMaintenanceReport])
def list_model_maintenance_reports(limit: int = 20) -> list[ModelMaintenanceReport]:
    return MODEL_MAINTENANCE_STORE.list_reports(limit)


@app.post("/api/model-maintenance/suggestions/{suggestion_id}/ignore", response_model=ModelMaintenanceSuggestion)
def ignore_model_maintenance_suggestion(suggestion_id: str) -> ModelMaintenanceSuggestion:
    try:
        return MODEL_MAINTENANCE_STORE.update_suggestion_status(suggestion_id, "ignored")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="建议不存在") from exc
```

Add similar `accept` and `snooze` endpoints.

- [ ] **Step 4: Run API tests**

Run:

```bash
cd apps/api && uv run pytest tests/test_model_maintenance.py -q
```

Expected: pass.

---

### Task 4: Frontend Types, API Client, And Page

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Create: `apps/web/app/model-maintenance/page.tsx`
- Create: `apps/web/app/model-maintenance/ModelMaintenanceWorkspace.tsx`
- Modify: `apps/web/components/AppShell.tsx`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Write failing frontend wiring test**

Append assertions in `apps/web/lib/strongStockWorkbench.test.ts`:

```ts
const modelMaintenancePageUrl = new URL("../app/model-maintenance/page.tsx", import.meta.url);
const modelMaintenancePageSource = existsSync(modelMaintenancePageUrl) ? readFileSync(modelMaintenancePageUrl, "utf8") : "";
const modelMaintenanceWorkspaceUrl = new URL("../app/model-maintenance/ModelMaintenanceWorkspace.tsx", import.meta.url);
const modelMaintenanceWorkspaceSource = existsSync(modelMaintenanceWorkspaceUrl)
  ? readFileSync(modelMaintenanceWorkspaceUrl, "utf8")
  : "";
const modelMaintenanceFeatureSource = [modelMaintenancePageSource, modelMaintenanceWorkspaceSource].join("\\n");

assert.match(typesSource, /ModelMaintenanceReport/);
assert.match(apiSource, /getLatestModelMaintenanceReport/);
assert.match(apiSource, /analyzeModelMaintenance/);
assert.match(appShellSource, /模型维护/);
assert.match(modelMaintenanceFeatureSource, /AI 模型维护/);
assert.match(modelMaintenanceFeatureSource, /待确认建议/);
```

- [ ] **Step 2: Run frontend test to verify failure**

Run:

```bash
cd apps/web && npm test
```

Expected: fail because model maintenance frontend files and API client functions do not exist.

- [ ] **Step 3: Add frontend types and API functions**

Add `ModelMaintenanceSuggestion`, `ModelMaintenanceReport`, `ModelMaintenancePacket` to `apps/web/lib/types.ts`.

Add functions to `apps/web/lib/api.ts`:

```ts
export async function generateModelMaintenancePacket(): Promise<ModelMaintenancePacket> {
  const response = await fetch(`${API_BASE_URL}/api/model-maintenance/packets/generate`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`生成模型维护复盘包失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<ModelMaintenancePacket>;
}

export async function getLatestModelMaintenanceReport(): Promise<ModelMaintenanceReport | null> {
  const response = await fetch(`${API_BASE_URL}/api/model-maintenance/reports/latest`);
  if (!response.ok) {
    throw new Error(`读取模型维护报告失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<ModelMaintenanceReport | null>;
}

export async function analyzeModelMaintenance(): Promise<ModelMaintenanceReport> {
  const response = await fetch(`${API_BASE_URL}/api/model-maintenance/analyze`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`生成模型维护 AI 分析失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<ModelMaintenanceReport>;
}

export async function updateModelMaintenanceSuggestion(
  suggestionId: string,
  action: "accept" | "ignore" | "snooze",
): Promise<ModelMaintenanceSuggestion> {
  const response = await fetch(`${API_BASE_URL}/api/model-maintenance/suggestions/${encodeURIComponent(suggestionId)}/${action}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`更新模型维护建议失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<ModelMaintenanceSuggestion>;
}
```

- [ ] **Step 4: Add page and workspace**

Create a dynamic page that renders a client workspace. The workspace should:

- Load latest report on mount.
- Show empty state if no report.
- Provide “生成复盘包并分析” button.
- Render health status, summary, key findings, and suggestions.
- Let user accept/ignore/snooze suggestions.

- [ ] **Step 5: Add navigation entry**

Add `/model-maintenance` entry to `apps/web/components/AppShell.tsx`.

- [ ] **Step 6: Run frontend tests**

Run:

```bash
cd apps/web && npm test
```

Expected: pass.

---

### Task 5: Settings And Homepage Simplification

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/services/runtime_settings.py`
- Modify: `apps/web/app/settings/SettingsWorkspace.tsx`
- Modify: `apps/web/components/ScreenerWorkbench.tsx`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Write failing tests**

Add frontend assertions:

```ts
assert.match(settingsFeatureSource, /AI 分析服务/);
assert.match(settingsFeatureSource, /DeepSeek/);
assert.match(screenerFeatureSource, /查看模型维护/);
assert.doesNotMatch(screenerFeatureSource, /<GsgfReviewPanel/);
assert.doesNotMatch(screenerFeatureSource, /<GsgfCalibrationPanel/);
```

- [ ] **Step 2: Run frontend test to verify failure**

Run:

```bash
cd apps/web && npm test
```

Expected: fail because settings fields and homepage simplification are not implemented.

- [ ] **Step 3: Add AI settings model**

Add AI analysis config to runtime settings and public payload. Do not expose API key; expose only key preview/configured status.

- [ ] **Step 4: Add settings UI fields**

Add a Settings card with:

- Enable AI analysis.
- Provider select: OpenAI/Codex, DeepSeek, custom compatible.
- Base URL.
- Model name.
- API Key input.
- Run after daily review switch.
- Run after weekly calibration switch.

- [ ] **Step 5: Simplify homepage model diagnostics**

Remove `GsgfReviewPanel`, `GsgfCalibrationPanel`, and `GsgfFunnelPanel` from homepage render path. Replace with a compact panel linking to `/model-maintenance`.

- [ ] **Step 6: Run frontend tests**

Run:

```bash
cd apps/web && npm test
```

Expected: pass.

---

### Task 6: Final Verification

**Files:**
- All modified files.

- [ ] **Step 1: Run backend tests**

Run:

```bash
cd apps/api && uv run pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run backend lint**

Run:

```bash
cd apps/api && uv run ruff check app tests
```

Expected: no lint errors.

- [ ] **Step 3: Run frontend tests**

Run:

```bash
cd apps/web && npm test
```

Expected: all tests pass.

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd apps/web && NEXT_TELEMETRY_DISABLED=1 npm run build
```

Expected: build succeeds.

- [ ] **Step 5: Commit implementation**

Run:

```bash
git status --short
git add apps/api apps/web docs/superpowers/plans/2026-07-04-ai-model-maintenance-implementation.md
git commit -m "Add AI model maintenance workflow"
```

Expected: implementation committed on `codex/ai-model-maintenance`.
