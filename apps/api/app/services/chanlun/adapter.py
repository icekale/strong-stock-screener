from __future__ import annotations

from datetime import datetime, timedelta
from math import isfinite
from typing import Literal
from zoneinfo import ZoneInfo

from app.models import (
    ChanlunAnalysisResponse,
    ChanlunFractal,
    ChanlunPeriod,
    ChanlunStroke,
    KlineBar,
    StrongStockSourceStatus,
)
from app.services.chanlun.signals import derive_confirmed_events
from app.services.chanlun.structures import (
    VISUAL_RULE_VERSION,
    StructureMappingError,
    map_confirmed_zones,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")


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
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=SHANGHAI)
        if previous_at is not None and occurred_at <= previous_at:
            raise ValueError("bars must be in strictly increasing time order")
        previous_at = occurred_at
        raw_at = occurred_at.astimezone(SHANGHAI) + timedelta(hours=8)
        raw_bars.append(
            RawBar(
                id=index,
                symbol=symbol,
                dt=raw_at,
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
        except (ValueError, OverflowError) as exc:
            return self._response(
                symbol,
                period,
                bars,
                "insufficient_bars",
                f"invalid or insufficient CZSC bar data: {exc}",
                last_closed_bar_at,
            )
        except (ImportError, OSError, AttributeError, IndexError, KeyError, RuntimeError, TypeError) as exc:
            return self._response(
                symbol,
                period,
                bars,
                "unavailable",
                f"native runtime unavailable: {exc}",
                last_closed_bar_at,
            )

        try:
            _RawBar, _Freq, CZSC = _load_czsc()
            native = CZSC(raw_bars)
            return self._map_native(
                symbol,
                period,
                bars,
                native,
                include_observing=include_observing,
            )
        except (ImportError, OSError, AttributeError, IndexError, KeyError, OverflowError, RuntimeError, TypeError, ValueError) as exc:
            return self._response(
                symbol,
                period,
                bars,
                "unavailable",
                f"native analysis or mapping unavailable: {exc}",
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
        chart_dates = _chart_dates(bars)
        last_closed_bar_at = bars[-1].date
        completed_pairs: list[tuple[object, ChanlunStroke]] = []
        for native_bi in getattr(native, "finished_bis", []):
            stroke = _map_stroke(native_bi, chart_dates, status="confirmed")
            if stroke.end_at != last_closed_bar_at:
                completed_pairs.append((native_bi, stroke))

        completed_strokes = [stroke for _, stroke in completed_pairs]
        confirmed_keys = {
            _fractal_key(fractal, chart_dates)
            for native_bi, _ in completed_pairs
            for fractal in (native_bi.fx_a, native_bi.fx_b)
        }
        fractals: list[ChanlunFractal] = []
        for native_fx in getattr(native, "fx_list", []):
            key = _fractal_key(native_fx, chart_dates)
            if key in confirmed_keys:
                fractals.append(_map_fractal(native_fx, chart_dates, status="confirmed"))
            elif include_observing:
                fractals.append(_map_fractal(native_fx, chart_dates, status="observing"))

        zones = map_confirmed_zones(completed_pairs)

        strokes = list(completed_strokes)
        if include_observing:
            observing = _observing_stroke(getattr(native, "ubi", None), bars, chart_dates)
            if observing:
                strokes.append(observing)

        # 背驰与买卖点信号：strokes 的 start_at/end_at 已是 _chart_datetime 归一化格式，
        # 因此喂给信号推导的 bars 也必须用相同日期键，否则日K/分钟线都无法匹配。
        signal_bars = [
            bar.model_copy(update={"date": _chart_datetime(bar.date)}) for bar in bars
        ]
        try:
            divergences, signals = derive_confirmed_events(
                signal_bars,
                completed_strokes,
                zones,
                rule_version=VISUAL_RULE_VERSION,
            )
        except (IndexError, KeyError, ValueError):
            divergences, signals = [], []

        return ChanlunAnalysisResponse(
            symbol=symbol,
            period=period,
            availability="ready",
            bars=bars,
            fractals=fractals,
            strokes=strokes,
            segments=[],
            zones=zones,
            divergences=divergences,
            signals=signals,
            source_status=[
                StrongStockSourceStatus(
                    source=self.source_name,
                    status="success",
                    detail="czsc native fractals, strokes, and maintained zone sequence mapped",
                ),
                StrongStockSourceStatus(
                    source="Chanlun衍生结构",
                    status="success",
                    detail=f"已产出 {len(divergences)} 个背驰、{len(signals)} 个买卖点信号",
                ),
            ],
            last_closed_bar_at=last_closed_bar_at,
            rule_version=VISUAL_RULE_VERSION,
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
            rule_version=VISUAL_RULE_VERSION,
        )


def _chart_dates(bars: list[KlineBar]) -> set[str]:
    return {_chart_datetime(bar.date) for bar in bars}


def _chart_datetime(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI).isoformat(timespec="seconds")


def _native_datetime(value: object) -> str:
    try:
        timestamp = getattr(value, "dt")
        parsed = timestamp if isinstance(timestamp, datetime) else datetime.fromisoformat(str(timestamp))
    except (AttributeError, TypeError, ValueError) as exc:
        raise StructureMappingError(f"native item has no valid dt: {exc}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI).isoformat(timespec="seconds")


def _map_fractal(native_fx: object, chart_dates: set[str], *, status: str) -> ChanlunFractal:
    occurred_at = _occurred_at(native_fx, chart_dates)
    mark = _mark(getattr(native_fx, "mark"))
    return ChanlunFractal(
        id=f"fractal:{occurred_at}:{mark}",
        occurred_at=occurred_at,
        price=float(getattr(native_fx, "fx")),
        mark=mark,
        status=status,
    )


def _map_stroke(native_bi: object, chart_dates: set[str], *, status: str) -> ChanlunStroke:
    start_fx = native_bi.fx_a
    end_fx = native_bi.fx_b
    start_at = _occurred_at(start_fx, chart_dates)
    end_at = _occurred_at(end_fx, chart_dates)
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


def _observing_stroke(
    ubi: object, bars: list[KlineBar], chart_dates: set[str]
) -> ChanlunStroke | None:
    if not isinstance(ubi, dict) or not ubi.get("fx_a"):
        return None
    start_fx = ubi["fx_a"]
    start_at = _occurred_at(start_fx, chart_dates)
    direction = _direction(ubi.get("direction"))
    end_bar = ubi["high_bar"] if direction == "up" else ubi["low_bar"]
    end_at = _occurred_at(end_bar, chart_dates)
    end_price = float(ubi["high"] if direction == "up" else ubi["low"])
    if start_at >= end_at:
        return None
    return ChanlunStroke(
        id=f"stroke:observing:{start_at}:{end_at}",
        start_at=start_at,
        start_price=float(getattr(start_fx, "fx")),
        end_at=end_at,
        end_price=end_price,
        direction=direction,
        status="observing",
    )


def _fractal_key(native_fx: object, chart_dates: set[str]) -> tuple[str, str, float]:
    return (
        _occurred_at(native_fx, chart_dates),
        _mark(getattr(native_fx, "mark")),
        float(getattr(native_fx, "fx")),
    )


def _occurred_at(native_item: object, chart_dates: set[str]) -> str:
    occurred_at = _native_datetime(native_item)
    if occurred_at not in chart_dates:
        raise StructureMappingError(f"native dt is outside canonical chart bars: {occurred_at}")
    return occurred_at


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
