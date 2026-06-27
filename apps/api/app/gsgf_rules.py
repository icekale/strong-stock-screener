from __future__ import annotations

from statistics import mean

from app.models import GsgfAnalysis, GsgfScoreBreakdown, IndustryStrength, KlineBar

GSGF_MODEL_VERSION = "gsgf-v1"


def analyze_gsgf(
    bars: list[KlineBar],
    *,
    industry_strength: IndustryStrength | None = None,
) -> GsgfAnalysis:
    if len(bars) < 60:
        return GsgfAnalysis(
            model_version=GSGF_MODEL_VERSION,
            zone="unknown",
            action="wait_trigger",
            risk_flags=["K线不足60日"],
            explanation=["股是股非模型需要至少60日K线"],
        )
    enriched = _with_ma(bars)
    pressure_flags, pressure_risks, safety_score = _pressure(enriched)
    volume_structure, volume_score, volume_notes = _volume_structure(enriched[-40:])
    zone, ma_score, ma_notes, ma_risks = _zone_and_ma(enriched)
    pattern_score, pattern_tags = _patterns(enriched)
    star_score, trigger_tags, star_risks = _stars(enriched, zone)
    sector_score = _sector_score(industry_strength)
    scores = GsgfScoreBreakdown(
        safety_pressure=safety_score,
        volume_thickness=volume_score,
        ma_alignment=ma_score,
        pattern_space=pattern_score,
        star_trigger=star_score,
        sector_theme=sector_score,
    )
    risk_flags = _dedupe(pressure_risks + ma_risks + star_risks)
    total_score = max(0, min(100, sum(scores.model_dump().values()) - _risk_penalty(risk_flags)))
    action = _action(total_score, zone, risk_flags, trigger_tags)
    return GsgfAnalysis(
        model_version=GSGF_MODEL_VERSION,
        total_score=round(total_score),
        action=action,
        zone=zone,
        volume_structure=volume_structure,
        scores=scores,
        pattern_tags=pattern_tags,
        trigger_tags=trigger_tags,
        pressure_flags=pressure_flags,
        risk_flags=risk_flags,
        explanation=_dedupe(volume_notes + ma_notes + pattern_tags + trigger_tags + pressure_flags + risk_flags),
    )


def _with_ma(bars: list[KlineBar]) -> list[KlineBar]:
    output: list[KlineBar] = []
    for index, bar in enumerate(bars):
        closes = [item.close for item in bars[: index + 1]]
        output.append(
            bar.model_copy(
                update={
                    "ma5": bar.ma5 if bar.ma5 is not None else _ma(closes, 5),
                    "ma10": bar.ma10 if bar.ma10 is not None else _ma(closes, 10),
                    "ma20": bar.ma20 if bar.ma20 is not None else _ma(closes, 20),
                    "ma60": bar.ma60 if bar.ma60 is not None else _ma(closes, 60),
                }
            )
        )
    return output


def _ma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[-window:])


def _pressure(bars: list[KlineBar]) -> tuple[list[str], list[str], int]:
    latest = bars[-1]
    recent20 = bars[-20:]
    avg_volume = mean(bar.volume for bar in bars[-35:])
    gain20 = latest.close / max(recent20[0].close, 1) - 1
    flags: list[str] = []
    risks: list[str] = []
    if gain20 > 0.35 and latest.volume > avg_volume * 2 and _long_upper_shadow(latest):
        risks.append("高位巨量长上影")
    previous_high = max(bar.high for bar in bars[-120:-1]) if len(bars) >= 121 else 0
    if previous_high and latest.close >= previous_high * 0.97 and latest.volume < avg_volume * 1.2:
        flags.append("接近前高压力但放量不足")
    return flags, risks, 8 if risks else 16 if flags else 20


def _volume_structure(bars: list[KlineBar]) -> tuple[str, int, list[str]]:
    red = [bar for bar in bars if bar.close > bar.open]
    green = [bar for bar in bars if bar.close < bar.open]
    red_day_ratio = len(red) / max(len(bars), 1)
    red_volume_ratio = sum(bar.volume for bar in red) / max(sum(bar.volume for bar in bars), 1)
    avg_red = mean([bar.volume for bar in red]) if red else 0
    avg_green = mean([bar.volume for bar in green]) if green else 0
    if red_day_ratio >= 0.55 and red_volume_ratio >= 0.6 and avg_red >= avg_green * 1.15:
        return "three_yang_controls_three_yin", 22, ["三阳控三阴"]
    if red_day_ratio <= 0.45 and red_volume_ratio <= 0.45 and avg_green > avg_red * 1.1:
        return "three_yin_controls_three_yang", 5, ["三阴控三阳"]
    return "neutral", 12, ["量形态中性"]


def _zone_and_ma(bars: list[KlineBar]) -> tuple[str, int, list[str], list[str]]:
    latest = bars[-1]
    previous = bars[-2]
    ma5 = latest.ma5 or latest.close
    ma10 = latest.ma10 or latest.close
    ma20 = latest.ma20 or latest.close
    ma60 = latest.ma60 or latest.close
    ma_values = [ma5, ma10, ma20]
    tight = max(ma_values) / max(min(ma_values), 1) - 1
    slopes_up = sum(
        1
        for current, prev in [
            (latest.ma5, previous.ma5),
            (latest.ma10, previous.ma10),
            (latest.ma20, previous.ma20),
        ]
        if current is not None and prev is not None and current > prev
    )
    if latest.close < ma10 and slopes_up <= 1:
        return "c_zone", 2, [], ["C区风险"]
    if tight < 0.06 and latest.close > max(ma_values) and slopes_up >= 2:
        return "a_zone", 18, ["A区均线归位"], []
    trend_ok = ma20 > ma60 and latest.close > ma10 and abs(latest.low / max(ma20, 1) - 1) < 0.06
    if trend_ok:
        return "b_zone_a_point", 15, ["B区A点"], []
    return "unformed", 8, ["均线结构未完全成型"], []


def _patterns(bars: list[KlineBar]) -> tuple[int, list[str]]:
    latest = bars[-1]
    recent60 = bars[-60:]
    high60 = max(bar.high for bar in recent60[:-1])
    low60 = min(bar.low for bar in recent60)
    tags: list[str] = []
    score = 0
    if latest.close >= high60 * 0.98:
        tags.append("颈位附近")
        score += 6
    if (high60 - low60) / max(latest.close, 1) < 0.22:
        tags.append("箱体收敛")
        score += 5
    if _higher_lows(recent60):
        tags.append("低点抬高")
        score += 4
    return min(15, score), tags


def _stars(bars: list[KlineBar], zone: str) -> tuple[int, list[str], list[str]]:
    recent = bars[-4:-1]
    latest = bars[-1]
    trigger_tags: list[str] = []
    risks: list[str] = []
    star_count = sum(1 for bar in recent if _is_star(bar))
    avg_volume20 = mean(bar.volume for bar in bars[-20:])
    if star_count >= 2 and mean(bar.volume for bar in recent) < avg_volume20 * 0.9:
        if zone in {"a_zone", "b_zone_a_point"}:
            trigger_tags.append("星线蓄势")
        else:
            trigger_tags.append("星线平台待确认")
    if _long_upper_shadow(latest) and latest.volume > avg_volume20 * 1.8:
        risks.append("高位巨量长上影")
    return (8 if "星线蓄势" in trigger_tags else 4 if trigger_tags else 0), trigger_tags, risks


def _sector_score(industry_strength: IndustryStrength | None) -> int:
    if industry_strength == "strong":
        return 10
    if industry_strength == "weak":
        return 2
    return 5


def _action(total_score: int, zone: str, risk_flags: list[str], trigger_tags: list[str]) -> str:
    if "C区风险" in risk_flags or "高位巨量长上影" in risk_flags:
        return "avoid"
    if total_score >= 80 and zone in {"a_zone", "b_zone_a_point"}:
        return "strong_candidate"
    if total_score >= 65:
        return "watch_candidate"
    if trigger_tags:
        return "wait_trigger"
    return "avoid" if total_score < 45 else "wait_trigger"


def _risk_penalty(risk_flags: list[str]) -> int:
    penalty = 0
    if "C区风险" in risk_flags:
        penalty += 20
    if "高位巨量长上影" in risk_flags:
        penalty += 25
    return penalty


def _is_star(bar: KlineBar) -> bool:
    spread = bar.high - bar.low
    if spread <= 0:
        return False
    return abs(bar.close - bar.open) / spread <= 0.3


def _long_upper_shadow(bar: KlineBar) -> bool:
    spread = bar.high - bar.low
    if spread <= 0:
        return False
    upper = bar.high - max(bar.open, bar.close)
    return upper / spread > 0.45


def _higher_lows(bars: list[KlineBar]) -> bool:
    if len(bars) < 45:
        return False
    chunks = [bars[-60:-40], bars[-40:-20], bars[-20:]]
    lows = [min(bar.low for bar in chunk) for chunk in chunks if chunk]
    return len(lows) == 3 and lows[0] < lows[1] < lows[2]


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output
