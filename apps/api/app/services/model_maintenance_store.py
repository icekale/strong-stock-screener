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
        self.root_dir.mkdir(parents=True, exist_ok=True)
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
        self.root_dir.mkdir(parents=True, exist_ok=True)
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
        next_suggestions: list[ModelMaintenanceSuggestion] = []
        for suggestion in report.suggestions:
            if suggestion.suggestion_id == suggestion_id:
                suggestion = suggestion.model_copy(update={"status": status})
                updated = suggestion
            next_suggestions.append(suggestion)

        if updated is None:
            raise KeyError(suggestion_id)

        self.save_report(report.model_copy(update={"suggestions": next_suggestions}))
        return updated


def new_model_maintenance_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"
