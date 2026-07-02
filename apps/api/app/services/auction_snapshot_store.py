from __future__ import annotations

from datetime import datetime
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


def auction_timeline_label(captured_at: datetime) -> str | None:
    seconds = captured_at.hour * 3600 + captured_at.minute * 60 + captured_at.second
    for label, _target_time, start_seconds, end_seconds in AUCTION_TIMELINE_TARGETS:
        if start_seconds <= seconds <= end_seconds:
            return label
    return None


class AuctionSnapshotStore:
    def __init__(self, review_store: AuctionReviewStore | None = None) -> None:
        self._lock = RLock()
        self._saved_at: float | None = None
        self._snapshot: AuctionSnapshotResponse | None = None
        self._timeline: dict[str, tuple[str, AuctionSnapshotResponse]] = {}
        self._review_store = review_store

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
            self._snapshot = stored
            self._saved_at = monotonic()
            if timeline_label is not None:
                self._timeline[timeline_label] = (current.isoformat(timespec="seconds"), stored)
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
                        detail=f"返回最新竞价快照，缓存年龄 {age:.1f} 秒",
                    ),
                ],
            },
        )

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
