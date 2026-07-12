from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Literal

from app.models import (
    ChanlunAnalysisResponse,
    ChanlunFractal,
    ChanlunPeriod,
    ChanlunStroke,
    ChanlunZone,
    KlineBar,
    StrongStockSourceStatus,
)


def _load_czsc() -> tuple[object, object, object]:
    import czsc

    return czsc.RawBar, czsc.Freq, czsc.CZSC


def _freq_for_period(freq: object, period: ChanlunPeriod) -> object:
    return getattr(freq, {"1d": "D", "60m": "F60", "30m": "F30", "5m": "F5"}[period])


def _to_raw_bars(symbol: str, period: ChanlunPeriod, bars: list[KlineBar]) -> list[object]:
    RawBar, Freq, _CZSC = _load_czsc()
    raw_bars: list[object] = []
    previous_at: datetime | None = None

    for index, bar in enumerate(bars):
        values = (bar.open, bar.close, bar.high, bar.low, bar.volume, bar.amount or 0)
        if not all(isfinite(value) for value in values):
            raise ValueError("invalid non-finite bar value")
        if (
            bar.open <= 0
            or bar.close <= 0
            or bar.high <= 0
            or bar.low <= 0
            or bar.volume < 0
            or (bar.amount is not None and bar.amount < 0)
            or bar.low > min(bar.open, bar.close)
            or bar.high < max(bar.open, bar.close)
        ):
            raise ValueError("invalid OHLCV bar")

        occurred_at = datetime.fromisoformat(bar.date)
        if previous_at is not None and occurred_at <= previous_at:
            raise ValueError("bars must be in strictly increasing time order")
        previous_at = occurred_at
        raw_bars.append(
            RawBar(
                id=index,
                symbol=symbol,
                dt=occurred_at,
                freq=_freq_for_period(Freq, period),
                open=bar.open,
                close=bar.close,
                high=bar.high,
                low=bar.low,
                vol=bar.volume,
                amount=bar.amount or 0,
            )
        )
    return raw_bars


class ChanlunAdapter:
    source_name = "czsc"

    def analyze(
        self,
        symbol: str,
        *,
        period: ChanlunPeriod,
        bars: list[KlineBar],
        include_observing: bool = False,
    ) -> ChanlunAnalysisResponse:
        last_closed_bar_at = bars[-1].date if bars else None
        if len(bars) < 3:
            return self._response(
                symbol,
                period,
                bars,
                "insufficient_bars",
                "insufficient closed bars for CZSC analysis",
                last_closed_bar_at,
            )

        try:
            raw_bars = _to_raw_bars(symbol, period, bars)
            _RawBar, _Freq, CZSC = _load_czsc()
            native = CZSC(raw_bars)
            return self._map_native(
                symbol,
                period,
                bars,
                native,
                include_observing=include_observing,
            )
        except (ImportError, OSError) as exc:
            return self._response(
                symbol,
                period,
                bars,
                "unavailable",
                f"native runtime unavailable: {exc}",
                last_closed_bar_at,
            )
        except (AttributeError, IndexError, KeyError, OverflowError, RuntimeError, TypeError, ValueError) as exc:
            return self._response(
                symbol,
                period,
                bars,
                "insufficient_bars",
                f"invalid or insufficient CZSC bar data: {exc}",
                last_closed_bar_at,
            )

    def _map_native(
        self,
        symbol: str,
        period: ChanlunPeriod,
        bars: list[KlineBar],
        native: object,
        *,
        include_observing: bool,
    ) -> ChanlunAnalysisResponse:
        dates_by_id = {index: bar.date for index, bar in enumerate(bars)}
        last_closed_bar_at = bars[-1].date
        completed_pairs: list[tuple[object, ChanlunStroke]] = []
        for native_bi in getattr(native, "finished_bis", []):
            stroke = _map_stroke(native_bi, dates_by_id, status="confirmed")
            if stroke.end_at != last_closed_bar_at:
                completed_pairs.append((native_bi, stroke))

        completed_strokes = [stroke for _, stroke in completed_pairs]
        confirmed_keys = {
            _fractal_key(fractal, dates_by_id)
            for native_bi, _ in completed_pairs
            for fractal in (native_bi.fx_a, native_bi.fx_b)
        }
        fractals: list[ChanlunFractal] = []
        for native_fx in getattr(native, "fx_list", []):
            key = _fractal_key(native_fx, dates_by_id)
            if key in confirmed_keys:
                fractals.append(_map_fractal(native_fx, dates_by_id, status="confirmed"))
            elif include_observing:
                fractals.append(_map_fractal(native_fx, dates_by_id, status="observing"))

        zones = _confirmed_zones(native, completed_pairs, dates_by_id)
        virtual_zone = _virtual_zone(completed_strokes)
        if virtual_zone and not any(
            (zone.high, zone.low) == (virtual_zone.high, virtual_zone.low) for zone in zones
        ):
            zones.append(virtual_zone)

        strokes = list(completed_strokes)
        if include_observing:
            observing = _observing_stroke(getattr(native, "ubi", None), bars, dates_by_id)
            if observing:
                strokes.append(observing)

        return ChanlunAnalysisResponse(
            symbol=symbol,
            period=period,
            availability="ready",
            bars=bars,
            fractals=fractals,
            strokes=strokes,
            segments=_segments(completed_strokes),
            zones=zones,
            source_status=[
                StrongStockSourceStatus(
                    source=self.source_name,
                    status="success",
                    detail="czsc native structures mapped to project-owned layers",
                )
            ],
            last_closed_bar_at=last_closed_bar_at,
        )

    def _response(
        self,
        symbol: str,
        period: ChanlunPeriod,
        bars: list[KlineBar],
        availability: Literal["insufficient_bars", "unavailable"],
        detail: str,
        last_closed_bar_at: str | None,
    ) -> ChanlunAnalysisResponse:
        return ChanlunAnalysisResponse(
            symbol=symbol,
            period=period,
            availability=availability,
            bars=bars,
            source_status=[
                StrongStockSourceStatus(source=self.source_name, status="failed", detail=detail)
            ],
            last_closed_bar_at=last_closed_bar_at,
        )


def _map_fractal(native_fx: object, dates_by_id: dict[int, str], *, status: str) -> ChanlunFractal:
    occurred_at = _occurred_at(native_fx, dates_by_id)
    mark = _mark(getattr(native_fx, "mark"))
    return ChanlunFractal(
        id=f"fractal:{occurred_at}:{mark}",
        occurred_at=occurred_at,
        price=float(getattr(native_fx, "fx")),
        mark=mark,
        status=status,
    )


def _map_stroke(native_bi: object, dates_by_id: dict[int, str], *, status: str) -> ChanlunStroke:
    start_fx = native_bi.fx_a
    end_fx = native_bi.fx_b
    start_at = _occurred_at(start_fx, dates_by_id)
    end_at = _occurred_at(end_fx, dates_by_id)
    direction = _direction(getattr(native_bi, "direction"))
    return ChanlunStroke(
        id=f"stroke:{start_at}:{end_at}",
        start_at=start_at,
        start_price=float(getattr(start_fx, "fx")),
        end_at=end_at,
        end_price=float(getattr(end_fx, "fx")),
        direction=direction,
        status=status,
    )


def _confirmed_zones(
    native: object,
    completed_pairs: list[tuple[object, ChanlunStroke]],
    dates_by_id: dict[int, str],
) -> list[ChanlunZone]:
    native_zones = getattr(native, "zs_list", None)
    if native_zones is not None:
        mapped_strokes = {id(native_bi): stroke for native_bi, stroke in completed_pairs}
        zones: list[ChanlunZone] = []
        for native_zone in native_zones:
            strokes = [mapped_strokes[id(bi)] for bi in getattr(native_zone, "bis", []) if id(bi) in mapped_strokes]
            zone = _zone(strokes, virtual=False, status="confirmed")
            if zone:
                zones.append(zone)
        return zones

    zones: list[ChanlunZone] = []
    strokes = [stroke for _, stroke in completed_pairs]
    for index in range(len(strokes) - 2):
        candidate = _zone(strokes[index : index + 3], virtual=False, status="confirmed")
        if candidate is None:
            continue
        if zones and candidate.low <= zones[-1].high and candidate.high >= zones[-1].low:
            previous = zones[-1]
            merged_high = min(previous.high, candidate.high)
            merged_low = max(previous.low, candidate.low)
            zones[-1] = ChanlunZone(
                id=f"zone:{previous.start_at}:{candidate.end_at}",
                start_at=previous.start_at,
                end_at=candidate.end_at,
                high=merged_high,
                low=merged_low,
                status="confirmed",
            )
        else:
            zones.append(candidate)
    return zones


def _virtual_zone(strokes: list[ChanlunStroke]) -> ChanlunZone | None:
    return _zone(strokes[-3:], virtual=True, status="provisional") if len(strokes) >= 3 else None


def _zone(
    strokes: list[ChanlunStroke], *, virtual: bool, status: str
) -> ChanlunZone | None:
    if len(strokes) < 3 or not _alternating(strokes):
        return None
    high = min(max(stroke.start_price, stroke.end_price) for stroke in strokes)
    low = max(min(stroke.start_price, stroke.end_price) for stroke in strokes)
    if high < low:
        return None
    prefix = "virtual-zone" if virtual else "zone"
    return ChanlunZone(
        id=f"{prefix}:{strokes[0].start_at}:{strokes[-1].end_at}",
        start_at=strokes[0].start_at,
        end_at=strokes[-1].end_at,
        high=high,
        low=low,
        virtual=virtual,
        status=status,
    )


def _segments(strokes: list[ChanlunStroke]) -> list[ChanlunStroke]:
    segments: list[ChanlunStroke] = []
    for index in range(0, len(strokes) - 2, 3):
        window = strokes[index : index + 3]
        if not _alternating(window):
            continue
        direction = "up" if window[-1].end_price >= window[0].start_price else "down"
        segments.append(
            ChanlunStroke(
                id=f"segment:{window[0].start_at}:{window[-1].end_at}",
                start_at=window[0].start_at,
                start_price=window[0].start_price,
                end_at=window[-1].end_at,
                end_price=window[-1].end_price,
                direction=direction,
                status="confirmed",
            )
        )
    return segments


def _observing_stroke(
    ubi: object, bars: list[KlineBar], dates_by_id: dict[int, str]
) -> ChanlunStroke | None:
    if not isinstance(ubi, dict) or not ubi.get("fx_a"):
        return None
    start_fx = ubi["fx_a"]
    start_at = _occurred_at(start_fx, dates_by_id)
    end_at = bars[-1].date
    if start_at >= end_at:
        return None
    direction = _direction(ubi.get("direction"))
    end_price = bars[-1].high if direction == "up" else bars[-1].low
    return ChanlunStroke(
        id=f"stroke:observing:{start_at}:{end_at}",
        start_at=start_at,
        start_price=float(getattr(start_fx, "fx")),
        end_at=end_at,
        end_price=end_price,
        direction=direction,
        status="observing",
    )


def _fractal_key(native_fx: object, dates_by_id: dict[int, str]) -> tuple[str, str, float]:
    return (
        _occurred_at(native_fx, dates_by_id),
        _mark(getattr(native_fx, "mark")),
        float(getattr(native_fx, "fx")),
    )


def _occurred_at(native_item: object, dates_by_id: dict[int, str]) -> str:
    elements = getattr(native_item, "elements", [])
    if elements:
        center = elements[1] if len(elements) > 1 else elements[0]
        source_id = getattr(center, "id", None)
        if source_id in dates_by_id:
            return dates_by_id[source_id]
    source_id = getattr(native_item, "id", None)
    if source_id in dates_by_id:
        return dates_by_id[source_id]
    occurred_at = getattr(native_item, "dt")
    return occurred_at.isoformat(timespec="seconds")


def _mark(mark: object) -> Literal["top", "bottom"]:
    value = str(getattr(mark, "value", mark)).lower()
    if value in {"top", "g", "顶分型"}:
        return "top"
    if value in {"bottom", "d", "底分型"}:
        return "bottom"
    raise ValueError(f"unsupported fractal mark: {mark}")


def _direction(direction: object) -> Literal["up", "down"]:
    value = str(getattr(direction, "value", direction)).lower()
    if value in {"up", "向上"}:
        return "up"
    if value in {"down", "向下"}:
        return "down"
    raise ValueError(f"unsupported stroke direction: {direction}")


def _alternating(strokes: list[ChanlunStroke]) -> bool:
    return all(current.direction != previous.direction for previous, current in zip(strokes, strokes[1:]))
