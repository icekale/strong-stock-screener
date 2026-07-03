from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.models import (
    SectorWorkbenchMode,
    SectorWorkbenchResponse,
    SectorWorkbenchScope,
    SectorWorkbenchSeries,
    SectorWorkbenchPoint,
    StrongStockSourceStatus,
)

SECTOR_WORKBENCH_SAMPLE_SCHEMA_VERSION = 8


class SectorThemeRowsStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def save(
        self,
        *,
        trade_date: str,
        rows: list[dict[str, Any]],
        status_source: str,
        status_detail: str,
        status: str = "success",
    ) -> None:
        if not trade_date:
            return
        payload = {
            "schema_version": 1,
            "trade_date": trade_date,
            "rows": rows,
            "source_status": {
                "source": status_source,
                "status": status,
                "detail": status_detail,
            },
        }
        self._write(self._path(trade_date), payload)

    def load(self, trade_date: str) -> tuple[list[dict[str, Any]], StrongStockSourceStatus | None]:
        if not trade_date:
            return [], None
        payload = self._read(self._path(trade_date))
        rows = payload.get("rows")
        status_payload = payload.get("source_status")
        status = None
        if isinstance(status_payload, dict):
            try:
                status = StrongStockSourceStatus.model_validate(status_payload)
            except Exception:
                status = None
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else [], status

    def _path(self, trade_date: str) -> Path:
        return self.base_dir / f"{trade_date}.json"

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write(self, path: Path, payload: dict[str, Any]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )


class SectorWorkbenchSampleStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def append(self, response: SectorWorkbenchResponse, *, sample_source: str = "snapshot") -> None:
        if not response.trade_date:
            return
        path = self._path(response.trade_date)
        payload = self._read(path)
        samples = payload.setdefault("samples", [])
        by_key = {
            self._sample_key(sample): sample
            for sample in samples
            if isinstance(sample, dict)
        }
        for series in response.series:
            for point in series.points:
                sample = {
                    "trade_date": response.trade_date,
                    "schema_version": SECTOR_WORKBENCH_SAMPLE_SCHEMA_VERSION,
                    "mode": response.mode,
                    "scope": response.scope,
                    "name": series.name,
                    "metric": series.metric,
                    "sample_source": sample_source,
                    "time": point.time,
                    "value": point.value,
                    "sampled_at": point.sampled_at,
                }
                by_key[self._sample_key(sample)] = sample
        payload["samples"] = sorted(
            by_key.values(),
            key=lambda sample: (
                str(sample.get("mode") or ""),
                str(sample.get("scope") or ""),
                str(sample.get("name") or ""),
                str(sample.get("sampled_at") or ""),
            ),
        )
        self._write(path, payload)

    def series_for(
        self,
        *,
        trade_date: str | None,
        mode: SectorWorkbenchMode,
        scope: SectorWorkbenchScope,
        selected: list[str],
        metric: SectorWorkbenchMode,
        sample_source: str | None = None,
    ) -> list[SectorWorkbenchSeries]:
        if not trade_date:
            return []
        samples = self._read(self._path(trade_date)).get("samples", [])
        output: list[SectorWorkbenchSeries] = []
        for name in selected:
            raw_points: list[tuple[SectorWorkbenchPoint, int]] = []
            for sample in samples:
                if (
                    not isinstance(sample, dict)
                    or sample.get("mode") != mode
                    or sample.get("scope") != scope
                    or sample.get("metric") != metric
                    or sample.get("name") != name
                ):
                    continue
                time_text = str(sample.get("time") or "")
                if not self._is_trading_time(time_text):
                    continue
                if sample_source is not None and not self._sample_source_matches(sample, sample_source):
                    continue
                raw_points.append(
                    (
                        SectorWorkbenchPoint(
                            time=time_text,
                            value=float(sample.get("value") or 0),
                            sampled_at=str(sample.get("sampled_at") or ""),
                        ),
                        self._sample_version(sample),
                    )
                )
            points = [
                point
                for point, version in raw_points
                if metric != "strength" or version >= SECTOR_WORKBENCH_SAMPLE_SCHEMA_VERSION
            ]
            points.sort(key=lambda point: point.sampled_at)
            if points:
                output.append(
                    SectorWorkbenchSeries(
                        name=name,
                        scope=scope,
                        metric=metric,
                        points=points,
                    )
                )
        return output

    def prune(self, keep_days: int = 60) -> None:
        cutoff = date.today() - timedelta(days=max(1, keep_days))
        if not self.base_dir.exists():
            return
        for path in self.base_dir.glob("*.json"):
            try:
                trade_date = date.fromisoformat(path.stem)
            except ValueError:
                continue
            if trade_date < cutoff:
                path.unlink(missing_ok=True)

    def summary(self, trade_date: str | None) -> dict[str, Any]:
        if not trade_date:
            return self._empty_summary(trade_date)
        samples = [
            sample
            for sample in self._read(self._path(trade_date)).get("samples", [])
            if isinstance(sample, dict)
        ]
        if not samples:
            return self._empty_summary(trade_date)
        latest_sampled_at = max(str(sample.get("sampled_at") or "") for sample in samples) or None
        return {
            "trade_date": trade_date,
            "sample_count": len(samples),
            "latest_sampled_at": latest_sampled_at,
            "modes": self._unique_sorted(sample.get("mode") for sample in samples),
            "scopes": self._unique_sorted(sample.get("scope") for sample in samples),
            "metrics": self._unique_sorted(sample.get("metric") for sample in samples),
            "sample_sources": self._unique_sorted(sample.get("sample_source") or "snapshot" for sample in samples),
            "names": self._unique_sorted(sample.get("name") for sample in samples),
        }

    def _path(self, trade_date: str) -> Path:
        return self.base_dir / f"{trade_date}.json"

    @staticmethod
    def _empty_summary(trade_date: str | None) -> dict[str, Any]:
        return {
            "trade_date": trade_date,
            "sample_count": 0,
            "latest_sampled_at": None,
            "modes": [],
            "scopes": [],
            "metrics": [],
            "sample_sources": [],
            "names": [],
        }

    @staticmethod
    def _sample_key(sample: dict[str, Any]) -> tuple[str, str, str, str, str]:
        sampled_at = str(sample.get("sampled_at") or "")
        minute = sampled_at[:16]
        return (
            str(sample.get("mode") or ""),
            str(sample.get("scope") or ""),
            str(sample.get("name") or ""),
            str(sample.get("metric") or ""),
            minute,
        )

    @staticmethod
    def _unique_sorted(values: object) -> list[str]:
        output = {
            str(value).strip()
            for value in values
            if str(value or "").strip()
        }
        return sorted(output)

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"samples": []}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"samples": []}
        return payload if isinstance(payload, dict) else {"samples": []}

    @staticmethod
    def _sample_version(sample: dict[str, Any]) -> int:
        try:
            return int(sample.get("schema_version") or 1)
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _sample_source_matches(sample: dict[str, Any], expected: str) -> bool:
        actual = str(sample.get("sample_source") or "")
        if expected == "snapshot":
            return actual in {"", "snapshot"}
        return actual == expected

    @staticmethod
    def _is_trading_time(value: str) -> bool:
        parts = value.split(":")
        if len(parts) < 2:
            return False
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            return False
        seconds = hour * 3600 + minute * 60
        preopen = (9 * 3600 + 15 * 60) <= seconds <= (9 * 3600 + 25 * 60)
        morning = (9 * 3600 + 30 * 60) <= seconds <= (11 * 3600 + 30 * 60)
        afternoon = (13 * 3600) <= seconds <= (15 * 3600)
        return preopen or morning or afternoon

    def _write(self, path: Path, payload: dict[str, Any]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
