from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.models import ChanlunAnalysisResponse, ChanlunSignal, StrongStockSourceStatus
from app.services.chanlun.alerts import ChanlunAlertStore
from app.services.chanlun.alert_service import ChanlunAlertService


SHANGHAI = ZoneInfo("Asia/Shanghai")


def signal(identifier: str, occurred_at: str) -> ChanlunSignal:
    return ChanlunSignal(
        id=identifier,
        type="two_buy",
        occurred_at=occurred_at,
        price=10.0,
        stroke_id="stroke:test",
        status="confirmed",
    )


def test_alert_store_baselines_first_refresh_and_records_only_new_confirmed_signal_keys(tmp_path: Path) -> None:
    store = ChanlunAlertStore(tmp_path / "chanlun" / "alerts.sqlite3")
    first = signal("signal:first", "2026-07-10T10:00:00+08:00")

    baseline = store.observe("600000.SH", "5m", [first], now=datetime(2026, 7, 10, 10, 1, tzinfo=SHANGHAI))
    repeated = store.observe("600000.SH", "5m", [first], now=datetime(2026, 7, 10, 10, 2, tzinfo=SHANGHAI))
    second = store.observe(
        "600000.SH",
        "5m",
        [first, signal("signal:second", "2026-07-10T10:05:00+08:00")],
        now=datetime(2026, 7, 10, 10, 6, tzinfo=SHANGHAI),
    )

    assert baseline.baselined is True
    assert baseline.created == []
    assert repeated.baselined is False
    assert repeated.created == []
    assert [item.occurred_at for item in second.created] == ["2026-07-10T10:05:00+08:00"]
    assert [item.occurred_at for item in store.list(symbol="600000.SH")] == ["2026-07-10T10:05:00+08:00"]


def test_alert_service_only_emits_signal_that_appears_after_the_baseline(tmp_path: Path) -> None:
    first = signal("signal:first", "2026-07-10T10:00:00+08:00")

    class AnalysisService:
        signals = [first]

        def analysis(self, symbol, *, period, lookback, include_observing):
            return ChanlunAnalysisResponse(
                symbol=symbol,
                period=period,
                availability="ready",
                signals=self.signals,
                source_status=[StrongStockSourceStatus(source="fixture", status="success", detail="fixture")],
            )

    analysis_service = AnalysisService()
    service = ChanlunAlertService(
        analysis_service=analysis_service,
        store=ChanlunAlertStore(tmp_path / "chanlun" / "alerts.sqlite3"),
    )

    initial = service.refresh("600000.SH", period="5m", lookback=120)
    analysis_service.signals = [first, signal("signal:second", "2026-07-10T10:05:00+08:00")]
    refreshed = service.refresh("600000.SH", period="5m", lookback=120)

    assert initial.baselined is True
    assert initial.created == []
    assert [item.key for item in refreshed.created] == ["600000.SH:5m:two_buy:2026-07-10T10:05:00+08:00:cl-v1"]
