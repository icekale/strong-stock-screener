from __future__ import annotations

import statistics
from collections.abc import Iterable

from app.models import EtfShareChange, EtfSynchronization


MODEL_VERSION = "heuristic-v1"
POOL_VERSION = "core-a-share-v1"


def build_share_change(
    *,
    current_shares: float,
    previous_shares: float | None,
    close: float | None,
) -> EtfShareChange:
    if previous_shares is None:
        return EtfShareChange()
    share_change = current_shares - previous_shares
    return EtfShareChange(
        share_change=share_change,
        estimated_subscription_cny=(share_change * close if close is not None else None),
    )


def robust_z_score(value: float | None, history: list[float]) -> float | None:
    if value is None or len(history) < 3:
        return None
    median = statistics.median(history)
    mad = statistics.median(abs(item - median) for item in history)
    if mad == 0:
        return None
    return (value - median) / (1.4826 * mad)


def synchronization_ratio(values: Iterable[bool | None]) -> EtfSynchronization:
    valid_values = [value for value in values if value is not None]
    positive_count = sum(value is True for value in valid_values)
    return EtfSynchronization(
        positive_count=positive_count,
        valid_count=len(valid_values),
        ratio=(positive_count / len(valid_values) if valid_values else None),
    )
