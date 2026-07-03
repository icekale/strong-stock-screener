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
)


class SectorWorkbenchSampleStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def append(self, response: SectorWorkbenchResponse) -> None:
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
                    "mode": response.mode,
                    "scope": response.scope,
                    "name": series.name,
                    "metric": series.metric,
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
    ) -> list[SectorWorkbenchSeries]:
        if not trade_date:
            return []
        samples = self._read(self._path(trade_date)).get("samples", [])
        output: list[SectorWorkbenchSeries] = []
        for name in selected:
            points = [
                SectorWorkbenchPoint(
                    time=str(sample.get("time") or ""),
                    value=float(sample.get("value") or 0),
                    sampled_at=str(sample.get("sampled_at") or ""),
                )
                for sample in samples
                if isinstance(sample, dict)
                and sample.get("mode") == mode
                and sample.get("scope") == scope
                and sample.get("metric") == metric
                and sample.get("name") == name
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

    def _path(self, trade_date: str) -> Path:
        return self.base_dir / f"{trade_date}.json"

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
    def _read(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"samples": []}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"samples": []}
        return payload if isinstance(payload, dict) else {"samples": []}

    def _write(self, path: Path, payload: dict[str, Any]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
