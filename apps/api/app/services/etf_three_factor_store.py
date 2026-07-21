from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from threading import RLock

from pydantic import TypeAdapter

from app.models import EtfActivityAlert, EtfThreeFactorHistoryPoint, EtfThreeFactorResponse


_STORE_LOCK = RLock()
_HISTORY_LIST = TypeAdapter(list[EtfThreeFactorHistoryPoint])
_ALERT_LIST = TypeAdapter(list[EtfActivityAlert])


class EtfThreeFactorStore:
    def __init__(self, data_dir: Path) -> None:
        self.root_dir = data_dir / "capital-signals"
        self.snapshot_path = self.root_dir / "etf-three-factor-snapshot.json"
        self.history_path = self.root_dir / "etf-three-factor-history.json"
        self.alerts_path = self.root_dir / "etf-activity-alerts.json"

    def load_snapshot(self) -> EtfThreeFactorResponse | None:
        with _STORE_LOCK:
            if not self.snapshot_path.exists():
                return None
            try:
                return EtfThreeFactorResponse.model_validate_json(self.snapshot_path.read_bytes())
            except Exception:
                return None

    def save_snapshot(self, response: EtfThreeFactorResponse) -> None:
        with _STORE_LOCK:
            self._write_bytes(self.snapshot_path, response.model_dump_json(indent=2).encode("utf-8"))

    def load_history(self, symbol: str, days: int) -> list[EtfThreeFactorHistoryPoint]:
        with _STORE_LOCK:
            points = [point for point in self._load_list(self.history_path, _HISTORY_LIST) if point.symbol == symbol]
            points.sort(key=lambda point: point.trade_date)
            return points[-max(days, 0) :] if days else []

    def upsert_history(self, points: list[EtfThreeFactorHistoryPoint]) -> None:
        with _STORE_LOCK:
            rows = self._load_list(self.history_path, _HISTORY_LIST)
            merged = {(row.symbol, row.trade_date): row for row in rows}
            merged.update({(point.symbol, point.trade_date): point for point in points})
            retained_dates = sorted({point.trade_date for point in merged.values()})[-60:]
            retained = [point for point in merged.values() if point.trade_date in set(retained_dates)]
            retained.sort(key=lambda point: (point.trade_date, point.symbol))
            self._write_bytes(self.history_path, _HISTORY_LIST.dump_json(retained, indent=2))

    def load_alerts(self, unread_only: bool = False) -> list[EtfActivityAlert]:
        with _STORE_LOCK:
            alerts = self._retained_alerts(self._load_list(self.alerts_path, _ALERT_LIST))
            if unread_only:
                alerts = [alert for alert in alerts if not alert.read]
            return sorted(alerts, key=lambda alert: alert.triggered_at, reverse=True)

    def upsert_alert(self, alert: EtfActivityAlert, cooldown_minutes: int = 30) -> bool:
        with _STORE_LOCK:
            alerts = self._retained_alerts(self._load_list(self.alerts_path, _ALERT_LIST))
            if alert.alert_type != "single_upgrade" and self._is_duplicate(
                alert, alerts, cooldown_minutes
            ):
                return False
            alerts.append(alert)
            self._save_alerts(alerts)
            return True

    def mark_read(self, alert_id: str) -> None:
        with _STORE_LOCK:
            alerts = self._retained_alerts(self._load_list(self.alerts_path, _ALERT_LIST))
            self._save_alerts(
                [
                    alert.model_copy(update={"read": True}) if alert.alert_id == alert_id else alert
                    for alert in alerts
                ]
            )

    def mark_all_read(self) -> None:
        with _STORE_LOCK:
            self._save_alerts(
                [
                    alert.model_copy(update={"read": True})
                    for alert in self._retained_alerts(self._load_list(self.alerts_path, _ALERT_LIST))
                ]
            )

    @staticmethod
    def _load_list(path: Path, adapter: TypeAdapter) -> list:
        if not path.exists():
            return []
        try:
            return adapter.validate_json(path.read_bytes())
        except Exception:
            return []

    def _save_alerts(self, alerts: list[EtfActivityAlert]) -> None:
        retained = self._retained_alerts(alerts)
        self._write_bytes(self.alerts_path, _ALERT_LIST.dump_json(retained, indent=2))

    @staticmethod
    def _retained_alerts(alerts: list[EtfActivityAlert]) -> list[EtfActivityAlert]:
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        return [alert for alert in alerts if alert.trade_date >= cutoff]

    @staticmethod
    def _is_duplicate(
        alert: EtfActivityAlert,
        alerts: list[EtfActivityAlert],
        cooldown_minutes: int,
    ) -> bool:
        triggered_at = _parse_datetime(alert.triggered_at)
        if triggered_at is None:
            return False
        for existing in alerts:
            if not _same_alert_key(alert, existing):
                continue
            previous_at = _parse_datetime(existing.last_triggered_at)
            if previous_at is None:
                continue
            elapsed = triggered_at - previous_at
            if timedelta(0) <= elapsed < timedelta(minutes=cooldown_minutes):
                return True
        return False

    @staticmethod
    def _write_bytes(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_bytes(payload)
        temp_path.replace(path)


def _same_alert_key(current: EtfActivityAlert, existing: EtfActivityAlert) -> bool:
    if current.alert_type.startswith("market_"):
        return (
            existing.alert_type == current.alert_type
            and existing.level == current.level
        )
    return existing.symbol == current.symbol and existing.level == current.level


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
