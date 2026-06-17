from __future__ import annotations

from statistics import mean

from app.models import (
    KlineBar,
    RiskAction,
    ScreenStatus,
    StrongStockCandidate,
    StrongStockRiskItem,
    StrongStockScreeningItem,
)


def analyze_screening_item(
    candidate: StrongStockCandidate,
    bars: list[KlineBar],
    trade_date: str,
) -> StrongStockScreeningItem:
    if len(bars) < 220:
        return StrongStockScreeningItem(
            symbol=candidate.symbol,
            name=candidate.name,
            industry=candidate.industry,
            status="data_incomplete",
            score=0,
            rule_hits=list(candidate.limit_up_evidence),
            risk_flags=["K线不足220日"],
            intraday_notes=_intraday_notes("wait_pullback"),
            metrics={},
            data_status="incomplete",
            source_trace=[trade_date],
        )

    enriched = _with_moving_averages(bars)
    latest = enriched[-1]
    previous = enriched[-2]
    recent20 = enriched[-20:]
    recent200 = enriched[-200:]
    score = 0
    rule_hits = list(candidate.limit_up_evidence or ["20日内涨停"])
    risk_flags: list[str] = list(candidate.abnormal_flags)

    red_body, green_body, up_volume, down_volume = _body_and_volume_metrics(recent20)
    if red_body > green_body:
        score += 25
        rule_hits.append("阳线实体强于阴线")
    else:
        risk_flags.append("阴线实体不弱")
    if up_volume > down_volume:
        score += 15
        rule_hits.append("上涨日量能强于下跌日")
    else:
        risk_flags.append("下跌日放量")

    if latest.close > (latest.ma5 or latest.close):
        score += 20
        rule_hits.append("收盘价在MA5上方")
    else:
        risk_flags.append("跌在均线下方")

    is_200d_high = latest.high >= max(bar.high for bar in recent200)
    if is_200d_high:
        score += 20
        rule_hits.append("200日新高")

    volume_ratio_5d = latest.volume / max(mean(bar.volume for bar in enriched[-5:]), 1)
    daily_pct = (latest.close - previous.close) / previous.close * 100 if previous.close else 0.0
    if daily_pct > 0 and volume_ratio_5d >= 1.2:
        score += 15
        rule_hits.append("放量上涨")
    if volume_ratio_5d >= 1.8 and daily_pct < 1.0:
        risk_flags.append("放量滞涨")
        score -= 20

    ma5_down = (latest.ma5 or latest.close) < (previous.ma5 or previous.close)
    if ma5_down:
        risk_flags.append("MA5拐头向下")
        score -= 20
    if latest.close < (latest.ma10 or latest.close):
        risk_flags.append("跌在均线下方")
        score -= 15
    if latest.close < latest.open and abs(latest.open - latest.close) / max(latest.open, 1) >= 0.03:
        risk_flags.append("实体阴线")
        score -= 15

    score = max(0, min(100, round(score)))
    kdj_j = _kdj_j(enriched[-9:])
    if "放量滞涨" in risk_flags:
        status: ScreenStatus = "reduce_risk"
    elif ma5_down or latest.close < (latest.ma10 or latest.close):
        status = "wait_pullback"
    elif score >= 70:
        status = "focus"
    else:
        status = "wait_pullback"

    return StrongStockScreeningItem(
        symbol=candidate.symbol,
        name=candidate.name,
        industry=candidate.industry,
        status=status,
        score=score,
        rule_hits=_dedupe(rule_hits),
        risk_flags=_dedupe(risk_flags),
        intraday_notes=_intraday_notes(status),
        metrics={
            "close": latest.close,
            "ma5": latest.ma5,
            "ma10": latest.ma10,
            "ma20": latest.ma20,
            "volume_ratio_5d": round(volume_ratio_5d, 2),
            "is_200d_high": is_200d_high,
            "kdj_j": round(kdj_j, 2) if kdj_j is not None else None,
        },
        source_trace=[trade_date],
    )


def analyze_watchlist_risk(
    candidate: StrongStockCandidate,
    bars: list[KlineBar],
    trade_date: str,
) -> StrongStockRiskItem:
    if len(bars) < 20:
        return StrongStockRiskItem(
            symbol=candidate.symbol,
            name=candidate.name,
            industry=candidate.industry,
            risk_action="hold_watch",
            risk_flags=["K线不足20日"],
            intraday_notes=_intraday_notes("wait_pullback"),
            source_trace=[trade_date],
        )
    enriched = _with_moving_averages(bars)
    latest = enriched[-1]
    previous = enriched[-2]
    risk_flags: list[str] = []
    ma5_down = (latest.ma5 or latest.close) < (previous.ma5 or previous.close)
    if ma5_down:
        risk_flags.append("MA5拐头向下")
    if latest.close < (latest.ma5 or latest.close) or latest.close < (latest.ma10 or latest.close):
        risk_flags.append("跌在均线下方")
    if latest.close < latest.open and abs(latest.open - latest.close) / max(latest.open, 1) >= 0.03:
        risk_flags.append("实体阴线且断板未修复")
    if {"MA5拐头向下", "跌在均线下方"} <= set(risk_flags) or "实体阴线且断板未修复" in risk_flags:
        action: RiskAction = "empty"
    elif risk_flags:
        action = "reduce"
    else:
        action = "hold_watch"
    return StrongStockRiskItem(
        symbol=candidate.symbol,
        name=candidate.name,
        industry=candidate.industry,
        risk_action=action,
        risk_flags=_dedupe(risk_flags),
        intraday_notes=_intraday_notes(action),
        metrics={"close": latest.close, "ma5": latest.ma5, "ma10": latest.ma10, "ma20": latest.ma20},
        source_trace=[trade_date],
    )


def _with_moving_averages(bars: list[KlineBar]) -> list[KlineBar]:
    output: list[KlineBar] = []
    for index, bar in enumerate(bars):
        closes = [item.close for item in bars[: index + 1]]
        output.append(
            bar.model_copy(
                update={
                    "ma5": bar.ma5 if bar.ma5 is not None else _ma(closes, 5),
                    "ma10": bar.ma10 if bar.ma10 is not None else _ma(closes, 10),
                    "ma20": bar.ma20 if bar.ma20 is not None else _ma(closes, 20),
                }
            )
        )
    return output


def _ma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return round(mean(values[-window:]), 4)


def _body_and_volume_metrics(bars: list[KlineBar]) -> tuple[float, float, float, float]:
    red_bodies = [bar.close - bar.open for bar in bars if bar.close > bar.open]
    green_bodies = [bar.open - bar.close for bar in bars if bar.open > bar.close]
    up_volumes = [bar.volume for bar in bars if bar.close > bar.open]
    down_volumes = [bar.volume for bar in bars if bar.open > bar.close]
    return (
        mean(red_bodies) if red_bodies else 0.0,
        mean(green_bodies) if green_bodies else 0.0,
        mean(up_volumes) if up_volumes else 0.0,
        mean(down_volumes) if down_volumes else 0.0,
    )


def _kdj_j(bars: list[KlineBar]) -> float | None:
    if not bars:
        return None
    highest = max(bar.high for bar in bars)
    lowest = min(bar.low for bar in bars)
    if highest <= lowest:
        return None
    latest = bars[-1]
    rsv = (latest.close - lowest) / (highest - lowest) * 100
    k = (2 / 3) * 50 + (1 / 3) * rsv
    d = (2 / 3) * 50 + (1 / 3) * k
    return 3 * k - 2 * d


def _intraday_notes(status_or_action: str) -> list[str]:
    if status_or_action == "focus":
        return ["买点优先看分歧回落承接，不追红盘急拉"]
    if status_or_action in {"reduce_risk", "reduce", "empty"}:
        return ["冲高反弹优先兑现，不在绿盘恐慌卖出"]
    return ["趋势或买点不明确，等待回踩承接确认"]


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output
