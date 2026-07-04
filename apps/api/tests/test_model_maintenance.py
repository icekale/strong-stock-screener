from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    GsgfReviewBucket,
    GsgfReviewSummary,
    ModelMaintenancePacket,
    ModelMaintenanceReport,
    ModelMaintenanceSuggestion,
    StrongStockSourceStatus,
)
from app.services.ai_model_analysis import (
    analyze_model_maintenance_packet,
    build_offline_model_maintenance_report,
)
from app.services.model_maintenance_packet import build_model_maintenance_packet
from app.services.model_maintenance_store import ModelMaintenanceStore
from app.services.runtime_settings import AiAnalysisSettings, EffectiveAiAnalysisSettings, SettingsUpdate, save_runtime_settings


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


def test_online_ai_report_uses_openai_compatible_chat_completion() -> None:
    packet = ModelMaintenancePacket(
        packet_id="packet-1",
        trade_date="2026-07-04",
        review_summary={"record_count": 12, "buckets": []},
    )
    http_client = FakeAiHttpClient()

    report = analyze_model_maintenance_packet(
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

    assert http_client.request is not None
    assert http_client.request["url"] == "https://api.deepseek.com/chat/completions"
    assert http_client.request["headers"]["Authorization"] == "Bearer deepseek-test-key"
    assert http_client.request["json"]["model"] == "deepseek-reasoner"
    assert "packet-1" in http_client.request["json"]["messages"][1]["content"]
    assert report.provider == "deepseek"
    assert report.model == "deepseek-reasoner"
    assert report.health_status == "watch"
    assert report.suggestions[0].status == "pending"


def test_model_maintenance_api_generates_packet_and_report(tmp_path: Path) -> None:
    app.state.runs_dir = tmp_path
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


def test_model_maintenance_api_uses_configured_ai_analysis_provider(tmp_path: Path) -> None:
    app.state.runs_dir = tmp_path / "runs"
    app.state.runtime_config_path = tmp_path / "runtime_config.json"
    app.state.model_maintenance_http_client = FakeAiHttpClient()
    save_runtime_settings(
        app.state.runtime_config_path,
        SettingsUpdate(
            candidate_provider="recent_limit_up",
            kline_provider="tickflow",
            quote_provider="tickflow",
            tickflow_base_url="https://api.tickflow.test",
            provider_timeout_seconds=3,
            ai_analysis=AiAnalysisSettings(
                enabled=True,
                provider="deepseek",
                base_url="https://api.deepseek.com",
                model="deepseek-reasoner",
                api_key="deepseek-test-key",
            ),
        ),
    )

    try:
        client = TestClient(app)
        packet_response = client.post("/api/model-maintenance/packets/generate")
        assert packet_response.status_code == 200

        response = client.post("/api/model-maintenance/analyze")

        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "deepseek"
        assert payload["model"] == "deepseek-reasoner"
        assert app.state.model_maintenance_http_client.request is not None
    finally:
        delattr(app.state, "runs_dir")
        delattr(app.state, "runtime_config_path")
        delattr(app.state, "model_maintenance_http_client")


class FakeAiResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "content": """
                        {
                          "health_status": "watch",
                          "summary": "样本可观察，暂不自动调参。",
                          "key_findings": ["确认买点样本需要继续跟踪"],
                          "rule_diagnostics": [
                            {
                              "rule_name": "确认买点",
                              "status": "neutral",
                              "evidence": ["样本 12 条"],
                              "confidence": 0.58
                            }
                          ],
                          "suggestions": [
                            {
                              "type": "observe",
                              "title": "继续观察确认买点",
                              "reason": "当前样本尚不足以调权。",
                              "risk": "过早调参可能过拟合。",
                              "confidence": 0.58,
                              "suggested_action": "继续观察三天"
                            }
                          ]
                        }
                        """
                    }
                }
            ]
        }


class FakeAiHttpClient:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None

    def post(self, url: str, **kwargs: object) -> FakeAiResponse:
        self.request = {"url": url, **kwargs}
        return FakeAiResponse()
