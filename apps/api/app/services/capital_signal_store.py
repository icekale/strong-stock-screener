from __future__ import annotations

from pathlib import Path
from threading import RLock

from pydantic import TypeAdapter

from app.models import (
    EtfHolderPosition,
    EtfRadarOverviewResponse,
    EtfSharePoint,
    HuijinEtfBaseline,
    MarginMarketPoint,
)
from app.services.json_file_store import JsonFileStore


_STORE_LOCK = RLock()
_MARGIN_LIST = TypeAdapter(list[MarginMarketPoint])
_SHARE_LIST = TypeAdapter(list[EtfSharePoint])
_HOLDER_LIST = TypeAdapter(list[EtfHolderPosition])
_HUIJIN_BASELINE_LIST = TypeAdapter(list[HuijinEtfBaseline])


class CapitalSignalStore(JsonFileStore):
    def __init__(self, data_dir: Path) -> None:
        super().__init__(shared_lock=_STORE_LOCK)
        self.root_dir = data_dir / "capital-signals"
        self.margin_history_path = self.root_dir / "margin-history.json"
        self.share_history_path = self.root_dir / "etf-share-history.json"
        self.holder_reports_path = self.root_dir / "etf-holder-reports.json"
        self.huijin_baselines_path = self.root_dir / "huijin-etf-baselines.json"
        self.snapshot_path = self.root_dir / "etf-radar-snapshot.json"

    def load_margin_history(self) -> list[MarginMarketPoint]:
        with self._lock:
            return self.load_list(self.margin_history_path, _MARGIN_LIST, label="资金信号")

    def save_margin_history(self, rows: list[MarginMarketPoint]) -> None:
        with self._lock:
            ordered_dates = list(dict.fromkeys(row.trade_date for row in rows))
            retained_dates = set(ordered_dates[-400:])
            retained = [row for row in rows if row.trade_date in retained_dates]
            self.write_bytes(self.margin_history_path, _MARGIN_LIST.dump_json(retained, indent=2))

    def load_share_history(self) -> list[EtfSharePoint]:
        with self._lock:
            return self.load_list(self.share_history_path, _SHARE_LIST, label="资金信号")

    def save_share_history(self, rows: list[EtfSharePoint]) -> None:
        with self._lock:
            ordered_dates = list(dict.fromkeys(row.trade_date for row in rows))
            retained_dates = set(ordered_dates[-400:])
            retained = [row for row in rows if row.trade_date in retained_dates]
            self.write_bytes(self.share_history_path, _SHARE_LIST.dump_json(retained, indent=2))

    def load_holder_reports(self) -> list[EtfHolderPosition]:
        with self._lock:
            return self.load_list(self.holder_reports_path, _HOLDER_LIST, label="资金信号")

    def save_holder_reports(self, rows: list[EtfHolderPosition]) -> None:
        with self._lock:
            self.write_bytes(self.holder_reports_path, _HOLDER_LIST.dump_json(rows, indent=2))

    def load_huijin_baselines(self) -> list[HuijinEtfBaseline]:
        with self._lock:
            return self.load_list(self.huijin_baselines_path, _HUIJIN_BASELINE_LIST, label="资金信号")

    def save_huijin_baselines(self, rows: list[HuijinEtfBaseline]) -> None:
        with self._lock:
            self.write_bytes(
                self.huijin_baselines_path,
                _HUIJIN_BASELINE_LIST.dump_json(rows, indent=2),
            )

    def load_snapshot(self) -> EtfRadarOverviewResponse | None:
        with self._lock:
            return self.load_model(self.snapshot_path, EtfRadarOverviewResponse, label="资金信号")

    def save_snapshot(self, snapshot: EtfRadarOverviewResponse) -> None:
        with self._lock:
            self.write_bytes(
                self.snapshot_path,
                snapshot.model_dump_json(indent=2).encode("utf-8"),
            )
