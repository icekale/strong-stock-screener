from __future__ import annotations

from math import isfinite

from app.models import ChanlunStroke, ChanlunZone


VISUAL_RULE_VERSION = "cl-v2-visual"


def map_confirmed_zones(
    completed_pairs: list[tuple[object, ChanlunStroke]],
) -> list[ChanlunZone]:
    if len(completed_pairs) < 3:
        return []

    try:
        from czsc.utils.sig import get_zs_seq

        native_zones = get_zs_seq([native_bi for native_bi, _ in completed_pairs])
    except (AttributeError, ImportError, IndexError, RuntimeError, TypeError, ValueError):
        return []

    strokes_by_native_id = {id(native_bi): stroke for native_bi, stroke in completed_pairs}
    zones: list[ChanlunZone] = []
    seen: set[tuple[str, str, float, float]] = set()
    for native_zone in native_zones:
        native_bis = list(getattr(native_zone, "bis", []))
        if len(native_bis) < 3 or not _is_valid_zone(native_zone):
            continue
        strokes = [strokes_by_native_id.get(id(native_bi)) for native_bi in native_bis]
        if any(stroke is None for stroke in strokes):
            continue
        mapped_strokes = [stroke for stroke in strokes if stroke is not None]
        try:
            high = float(getattr(native_zone, "zg"))
            low = float(getattr(native_zone, "zd"))
        except (AttributeError, TypeError, ValueError):
            continue
        if not isfinite(high) or not isfinite(low) or high < low:
            continue

        key = (mapped_strokes[0].start_at, mapped_strokes[-1].end_at, high, low)
        if key in seen:
            continue
        seen.add(key)
        zones.append(
            ChanlunZone(
                id=f"zone:{key[0]}:{key[1]}",
                start_at=key[0],
                end_at=key[1],
                high=high,
                low=low,
                status="confirmed",
            )
        )
    return zones


def _is_valid_zone(native_zone: object) -> bool:
    validity = getattr(native_zone, "is_valid", False)
    try:
        return bool(validity() if callable(validity) else validity)
    except (AttributeError, IndexError, RuntimeError, TypeError, ValueError):
        return False
