from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import RLock
from time import monotonic

from app.models import (
    AuctionSnapshotResponse,
    AuctionTimelinePoint,
    AuctionTimelineResponse,
    StrongStockSourceStatus,
)
from app.services.auction_review import build_auction_review_records
from app.services.auction_review_store import AuctionReviewStore


AUCTION_TIMELINE_TARGETS: tuple[tuple[str, str, int, int], ...] = (
    ("09:20", "09:20", 9 * 3600 + 20 * 60, 9 * 3600 + 20 * 60 + 29),
    ("09:23", "09:23", 9 * 3600 + 23 * 60, 9 * 3600 + 23 * 60 + 29),
    ("09:24:50", "09:24:50", 9 * 3600 + 24 * 60 + 45, 9 * 3600 + 24 * 60 + 59),
    ("09:25", "09:25", 9 * 3600 + 25 * 60, 9 * 3600 + 25 * 60 + 30),
)
AUCTION_LOCK_SECONDS = 9 * 3600 + 25 * 60 + 30


def auction_timeline_label(captured_at: datetime) -> str | None:
    seconds = captured_at.hour * 3600 + captured_at.minute * 60 + captured_at.second
    for label, _target_time, start_seconds, end_seconds in AUCTION_TIMELINE_TARGETS:
        if start_seconds <= seconds <= end_seconds:
            return label
    return None


class AuctionSnapshotStore:
    def __init__(self, review_store: AuctionReviewStore | None = None, data_dir: Path | None = None) -> None:
        self._lock = RLock()
        self._saved_at: float | None = None
        self._snapshot: AuctionSnapshotResponse | None = None
        self._locked_trade_date: str | None = None
        self._timeline: dict[str, tuple[str, AuctionSnapshotResponse]] = {}
        self._review_store = review_store
        self._root_dir = data_dir / "auction_snapshots" if data_dir is not None else None
        self._load_locked_snapshot()

    def save(
        self,
        snapshot: AuctionSnapshotResponse,
        *,
        captured_at: datetime | None = None,
    ) -> AuctionSnapshotResponse:
        stored = snapshot.model_copy(deep=True, update={"snapshot_status": "fresh", "cache_age_seconds": 0.0})
        current = captured_at or datetime.now().astimezone()
        timeline_label = auction_timeline_label(current)
        with self._lock:
            if (
                self._snapshot is not None
                and self._locked_trade_date is not None
                and _is_after_auction_lock(current)
                and self._locked_trade_date == snapshot.trade_date
            ):
                self._snapshot = _backfill_locked_static_metadata(self._snapshot, stored)
                self._persist_locked_snapshot(self._snapshot)
                return self._snapshot.model_copy(deep=True)
            self._snapshot = stored
            self._saved_at = monotonic()
            if timeline_label is not None:
                self._timeline[timeline_label] = (current.isoformat(timespec="seconds"), stored)
                if timeline_label == "09:25":
                    self._locked_trade_date = stored.trade_date
                    self._persist_locked_snapshot(stored)
                if self._review_store is not None:
                    self._review_store.upsert_records(
                        build_auction_review_records(
                            stored,
                            selected_at_label=timeline_label,
                            selected_at=current,
                            limit=100,
                        )
                    )
        return stored.model_copy(deep=True)

    def latest(self, *, max_age_seconds: float = 120, limit: int | None = None) -> AuctionSnapshotResponse:
        with self._lock:
            snapshot = self._snapshot.model_copy(deep=True) if self._snapshot is not None else None
            saved_at = self._saved_at
        if snapshot is None or saved_at is None:
            return AuctionSnapshotResponse(
                snapshot_status="missing",
                source_status=[
                    StrongStockSourceStatus(
                        source="竞价雷达缓存",
                        status="disabled",
                        detail="暂无后台竞价快照，请等待自动采样或手动刷新",
                    )
                ],
            )

        age = max(0.0, monotonic() - saved_at)
        status = "cached" if age <= max_age_seconds else "stale"
        source_status = "success" if status == "cached" else "stale"
        items = snapshot.items[:limit] if limit is not None else snapshot.items
        is_locked = snapshot.trade_date is not None and snapshot.trade_date == self._locked_trade_date
        cache_detail = (
            f"返回 09:25 竞价锁定快照，盘中刷新不会覆盖主榜，缓存年龄 {age:.1f} 秒"
            if is_locked
            else f"返回最新竞价快照，缓存年龄 {age:.1f} 秒"
        )
        return snapshot.model_copy(
            deep=True,
            update={
                "items": items,
                "snapshot_status": status,
                "cache_age_seconds": round(age, 2),
                "source_status": [
                    *snapshot.source_status,
                    StrongStockSourceStatus(
                        source="竞价雷达缓存",
                        status=source_status,
                        detail=cache_detail,
                    ),
                ],
            },
        )

    def backfill_industries(self, industry_by_symbol: dict[str, str]) -> AuctionSnapshotResponse:
        with self._lock:
            if self._snapshot is None:
                return AuctionSnapshotResponse(snapshot_status="missing")
            items = [
                item.model_copy(update={"industry": industry_by_symbol[item.symbol]})
                if not item.industry and industry_by_symbol.get(item.symbol)
                else item
                for item in self._snapshot.items
            ]
            self._snapshot = self._snapshot.model_copy(deep=True, update={"items": items})
            if self._snapshot.trade_date is not None and self._snapshot.trade_date == self._locked_trade_date:
                self._persist_locked_snapshot(self._snapshot)
            return self._snapshot.model_copy(deep=True)

    def timeline(self, *, limit: int = 8) -> AuctionTimelineResponse:
        bounded_limit = max(1, min(limit, 20))
        with self._lock:
            timeline = {
                label: (captured_at, snapshot.model_copy(deep=True))
                for label, (captured_at, snapshot) in self._timeline.items()
            }
        points: list[AuctionTimelinePoint] = []
        for label, target_time, _start_seconds, _end_seconds in AUCTION_TIMELINE_TARGETS:
            captured = timeline.get(label)
            if captured is None:
                points.append(
                    AuctionTimelinePoint(
                        label=label,
                        target_time=target_time,
                        snapshot_status="waiting",
                    )
                )
                continue
            captured_at, snapshot = captured
            points.append(
                AuctionTimelinePoint(
                    label=label,
                    target_time=target_time,
                    snapshot_status="captured",
                    captured_at=captured_at,
                    metrics=snapshot.metrics,
                    items=snapshot.items[:bounded_limit],
                )
            )
        return AuctionTimelineResponse(
            points=points,
            source_status=[
                StrongStockSourceStatus(
                    source="竞价时间轴缓存",
                    status="success" if any(point.snapshot_status == "captured" for point in points) else "disabled",
                    detail="记录 09:20、09:23、09:24:50、09:25 四个关键竞价观察点",
                )
            ],
        )

    @property
    def _locked_snapshot_path(self) -> Path | None:
        return self._root_dir / "locked_0925.json" if self._root_dir is not None else None

    def _persist_locked_snapshot(self, snapshot: AuctionSnapshotResponse) -> None:
        path = self._locked_snapshot_path
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")

    def _load_locked_snapshot(self) -> None:
        path = self._locked_snapshot_path
        if path is None or not path.exists():
            return
        try:
            snapshot = AuctionSnapshotResponse.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return
        self._snapshot = snapshot.model_copy(deep=True, update={"snapshot_status": "fresh", "cache_age_seconds": 0.0})
        self._saved_at = monotonic()
        self._locked_trade_date = snapshot.trade_date


def _is_after_auction_lock(current: datetime) -> bool:
    seconds = current.hour * 3600 + current.minute * 60 + current.second
    return seconds > AUCTION_LOCK_SECONDS


def _backfill_locked_static_metadata(
    locked: AuctionSnapshotResponse,
    refreshed: AuctionSnapshotResponse,
) -> AuctionSnapshotResponse:
    refreshed_by_symbol = {item.symbol: item for item in refreshed.items}
    items = []
    for item in locked.items:
        source = refreshed_by_symbol.get(item.symbol)
        if source is None:
            items.append(item)
            continue
        update: dict[str, object] = {}
        if not item.industry and source.industry:
            update["industry"] = source.industry
        if not item.themes and source.themes:
            update["themes"] = source.themes
        if item.hot_theme_rank is None and source.hot_theme_rank is not None:
            update["hot_theme_rank"] = source.hot_theme_rank
        if item.hot_theme_score is None and source.hot_theme_score is not None:
            update["hot_theme_score"] = source.hot_theme_score
        if item.theme_auction_rank is None and source.theme_auction_rank is not None:
            update["theme_auction_rank"] = source.theme_auction_rank
        if not item.theme_resonance and source.theme_resonance:
            update["theme_resonance"] = source.theme_resonance
        items.append(item.model_copy(update=update) if update else item)
    return locked.model_copy(deep=True, update={"items": items})
