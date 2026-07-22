from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Literal, Mapping, Sequence

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.models import (
    SentimentAnalysisResult,
    SentimentDecisionResponse,
    SentimentPercentileAnalysisResponse,
    SentimentPercentilePoint,
    SentimentSummaryResponse,
)
from app.services.ai_model_analysis import extract_chat_content, extract_json_object
from app.services.market_sentiment_analysis_store import MarketSentimentAnalysisStore
from app.services.market_sentiment_percentile import MODEL_VERSION, WEIGHTS
from app.services.runtime_settings import EffectiveAiAnalysisSettings


_FACTOR_NAMES = (
    "volume",
    "index_move_5d",
    "price_position",
    "amplitude_5d",
    "volume_trend",
)
_RETRY_DELAY = timedelta(minutes=30)


class _StrictAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _FactorInput(_StrictAnalysisInput):
    score: float
    raw_value: float
    raw_unit: Literal["CNY", "%"]


class _FactorsInput(_StrictAnalysisInput):
    volume: _FactorInput
    index_move_5d: _FactorInput
    price_position: _FactorInput
    amplitude_5d: _FactorInput
    volume_trend: _FactorInput


class _WeightsInput(_StrictAnalysisInput):
    volume: float
    index_move_5d: float
    price_position: float
    amplitude_5d: float
    volume_trend: float


class _PercentileInput(_StrictAnalysisInput):
    score: float
    level: Literal["冰点", "偏冷", "中性", "偏热", "过热"]
    weights: _WeightsInput
    factors: _FactorsInput


class _ZoneTransitionInput(_StrictAnalysisInput):
    from_: Literal["冰点", "偏冷", "中性", "偏热", "过热"] | None = Field(alias="from")
    to: Literal["冰点", "偏冷", "中性", "偏热", "过热"]


class _ZoneTransitionsInput(_StrictAnalysisInput):
    one_day: _ZoneTransitionInput
    five_day: _ZoneTransitionInput


class _MarketBreadthInput(_StrictAnalysisInput):
    advance_count: int | None
    decline_count: int | None


class _MarketLimitsInput(_StrictAnalysisInput):
    limit_up_count: int | None
    limit_down_count: int | None
    break_board_count: int | None


class _MarketBoardsInput(_StrictAnalysisInput):
    max_consecutive_boards: int | None


class _MarketInput(_StrictAnalysisInput):
    source_date: str | None
    status: Literal["available", "unavailable"]
    breadth: _MarketBreadthInput
    limits: _MarketLimitsInput
    boards: _MarketBoardsInput
    seal_rate_pct: float | None
    turnover_cny: float | None


class _DecisionInput(_StrictAnalysisInput):
    source_date: str | None
    status: Literal["available", "unavailable"]
    market_state: Literal["冰点", "修复", "主升", "高潮", "分歧", "退潮"] | None
    trade_permission: Literal["空仓等待", "轻仓试错", "强势进攻", "只低吸", "只卖不追"] | None
    risk_level: Literal["低", "中", "高"] | None
    score_change: float | None


class _MainSectorInput(_StrictAnalysisInput):
    name: str
    strength_score: float
    limit_up_count: int
    break_board_count: int
    max_consecutive_boards: int


class _MainSectorsInput(_StrictAnalysisInput):
    source_date: str | None
    status: Literal["available", "unavailable"]
    items: list[_MainSectorInput] = Field(max_length=5)


class _ValidationInput(_StrictAnalysisInput):
    source_date: str | None
    status: Literal["available", "unavailable"]
    sample_count: int
    sample_counts: dict[Literal["冰点", "偏冷", "中性", "偏热", "过热"], int]
    conclusion: str | None


class _SentimentAnalysisInput(_StrictAnalysisInput):
    trade_date: str
    percentile: _PercentileInput
    score_change_1d: float | None
    score_change_5d: float | None
    zone_transitions: _ZoneTransitionsInput
    market: _MarketInput
    decision: _DecisionInput
    main_sectors: _MainSectorsInput
    validation: _ValidationInput


_A_SHARE_CODE_PATTERN = re.compile(
    r"(?<!\d)(?:[034689]\d{5})(?:\.(?:SH|SZ|BJ))?(?!\d)", re.IGNORECASE
)
_PROHIBITED_RESULT_TEXT_PATTERN = re.compile(
    r"(?:个股|股票(?:代码)?|证券代码|标的|"
    r"\b(?:individual\s+stock|stock\s+code|ticker)\b|"
    r"仓位|轻仓|重仓|满仓|半仓|加仓|减仓|建仓|持仓|空仓|"
    r"\b(?:position\s+sizing|position|allocation)\b|"
    r"买入|卖出|下单|挂单|开仓|平仓|止盈|止损|做多|做空|追涨|抄底|低吸|卖不追|"
    r"\b(?:buy|sell|order|trade|trading|long|short|stop[- ]?loss|take[- ]?profit)\b)",
    re.IGNORECASE,
)
_CURRENT_SCORE_PATTERN = re.compile(
    r"(?:\b(?:current\s+)?(?:sentiment\s+)?score\b|"
    r"(?:当前|目前)?(?:情绪)?(?:综合分|分数|评分))\s*(?:is|=|:|：|为|是)?\s*"
    r"(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_CURRENT_LEVEL_PATTERN = re.compile(
    r"(?:\b(?:current\s+)?(?:sentiment\s+)?level\b|"
    r"(?:当前|目前)?(?:市场)?情绪(?:等级|级别|分层)?|(?:当前|目前)(?:等级|级别|分层))\s*"
    r"(?:is|=|:|：|为|是|处于)?\s*(冰点|偏冷|中性|偏热|过热|ice|cold|neutral|hot|overheated)",
    re.IGNORECASE,
)
_LEVEL_ALIASES = {
    "ice": "冰点",
    "cold": "偏冷",
    "neutral": "中性",
    "hot": "偏热",
    "overheated": "过热",
}
_CURRENT_WEIGHT_PATTERN = re.compile(
    r"(?:\b(?:current\s+)?(?:factor\s+)?weights?\b|(?:当前|目前)?(?:因子)?权重)\s*"
    r"(?:are|is|=|:|：|为|是)?\s*(-?\d+(?:\.\d+)?)(%)?",
    re.IGNORECASE,
)
_CURRENT_TRADE_PERMISSION_PATTERN = re.compile(
    r"(?:\b(?:current\s+)?trade\s+permission\b|(?:当前|目前)?交易许可)\s*"
    r"(?:is|=|:|：|为|是)?\s*(空仓等待|轻仓试错|强势进攻|只低吸|只卖不追)",
    re.IGNORECASE,
)


def build_sentiment_analysis_input(
    percentile: SentimentPercentilePoint,
    history: Sequence[SentimentPercentilePoint],
    summary: SentimentSummaryResponse | None,
    decision: SentimentDecisionResponse | None,
    validation: Mapping[str, Any] | None,
) -> dict[str, object]:
    context_history = _history_through(percentile, history)
    point_index = next(index for index, point in enumerate(context_history) if point == percentile)
    previous_point = context_history[point_index - 1] if point_index else None
    five_day_point = context_history[point_index - 5] if point_index >= 5 else None
    market_available = summary is not None and summary.snapshot_status != "missing"
    metrics = summary.metrics if market_available else None

    return {
        "trade_date": percentile.trade_date,
        "percentile": {
            "score": percentile.score,
            "level": percentile.level,
            "weights": dict(WEIGHTS),
            "factors": {
                name: _factor_payload(getattr(percentile.factors, name))
                for name in _FACTOR_NAMES
            },
        },
        "score_change_1d": _score_change(percentile, previous_point),
        "score_change_5d": _score_change(percentile, five_day_point),
        "zone_transitions": {
            "one_day": _zone_transition(previous_point, percentile),
            "five_day": _zone_transition(five_day_point, percentile),
        },
        "market": {
            "source_date": summary.trade_date if market_available else None,
            "status": "available" if market_available else "unavailable",
            "breadth": {
                "advance_count": metrics.advance_count if metrics else None,
                "decline_count": metrics.decline_count if metrics else None,
            },
            "limits": {
                "limit_up_count": metrics.limit_up_count if metrics else None,
                "limit_down_count": metrics.limit_down_count if metrics else None,
                "break_board_count": metrics.break_board_count if metrics else None,
            },
            "boards": {"max_consecutive_boards": metrics.max_consecutive_boards if metrics else None},
            "seal_rate_pct": metrics.seal_rate_pct if metrics else None,
            "turnover_cny": metrics.turnover_cny if metrics else None,
        },
        "decision": {
            "source_date": decision.trade_date if decision else None,
            "status": "available" if decision else "unavailable",
            "market_state": decision.market_state if decision else None,
            "trade_permission": decision.trade_permission if decision else None,
            "risk_level": decision.risk_level if decision else None,
            "score_change": decision.score_change if decision else None,
        },
        "main_sectors": {
            "source_date": decision.trade_date if decision else None,
            "status": "available" if decision else "unavailable",
            "items": [
                {
                    "name": sector.name,
                    "strength_score": sector.strength_score,
                    "limit_up_count": sector.limit_up_count,
                    "break_board_count": sector.break_board_count,
                    "max_consecutive_boards": sector.max_consecutive_boards,
                }
                for sector in (decision.main_sectors[:5] if decision else [])
            ],
        },
        "validation": _validation_payload(validation),
    }


def hash_sentiment_analysis_input(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class MarketSentimentAnalysisService:
    def __init__(
        self,
        store: MarketSentimentAnalysisStore,
        *,
        http_client: Any | None = None,
    ) -> None:
        self.store = store
        self.http_client = http_client
        self._lock = RLock()

    def generate(
        self,
        input_payload: Mapping[str, object],
        config: EffectiveAiAnalysisSettings,
        *,
        force: bool = False,
    ) -> SentimentPercentileAnalysisResponse:
        analysis_input = _SentimentAnalysisInput.model_validate(input_payload)
        canonical_input = analysis_input.model_dump(mode="json", by_alias=True)
        trade_date = _trade_date(canonical_input)
        input_hash = hash_sentiment_analysis_input(canonical_input)
        if not config.enabled or not config.api_key:
            return SentimentPercentileAnalysisResponse(
                trade_date=trade_date,
                status="unconfigured",
                provider=config.provider,
                llm_model=config.model,
                input_hash=input_hash,
            )

        with self._lock:
            existing = self.store.load(trade_date)
            if not force and _is_matching_ready(existing, trade_date, input_hash, config):
                return existing
            if not force and _is_matching_cooling_failure(existing, trade_date, input_hash, config):
                return existing

            requested_at = _now()
            pending = SentimentPercentileAnalysisResponse(
                trade_date=trade_date,
                status="pending",
                provider=config.provider,
                llm_model=config.model,
                input_hash=input_hash,
                requested_at=requested_at,
            )
            self.store.save(pending)
            return self._generate_after_pending(pending, canonical_input, analysis_input, config)

    def _generate_after_pending(
        self,
        pending: SentimentPercentileAnalysisResponse,
        input_payload: Mapping[str, object],
        analysis_input: _SentimentAnalysisInput,
        config: EffectiveAiAnalysisSettings,
    ) -> SentimentPercentileAnalysisResponse:
        client = self.http_client or httpx.Client(timeout=45)
        should_close = self.http_client is None
        last_error: Exception | None = None
        try:
            for attempt in range(1, 4):
                try:
                    response = client.post(
                        f"{config.base_url.rstrip('/')}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {config.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": config.model,
                            "temperature": 0.1,
                            "response_format": {"type": "json_object"},
                            "messages": [
                                {"role": "system", "content": _SYSTEM_PROMPT},
                                {
                                    "role": "user",
                                    "content": json.dumps(
                                        input_payload,
                                        ensure_ascii=False,
                                        sort_keys=True,
                                        separators=(",", ":"),
                                    ),
                                },
                            ],
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    result = SentimentAnalysisResult.model_validate(
                        extract_json_object(extract_chat_content(payload))
                    )
                    _validate_result_semantics(result, analysis_input)
                except Exception as exc:
                    last_error = exc
                    continue

                ready = pending.model_copy(
                    update={
                        "status": "ready",
                        "attempts": attempt,
                        "completed_at": _now(),
                        "result": result,
                    }
                )
                return self.store.save(ready)
        finally:
            if should_close and hasattr(client, "close"):
                client.close()

        failed = pending.model_copy(
            update={
                "status": "failed",
                "attempts": 3,
                "completed_at": _now(),
                "retry_after": _retry_after(),
                "error": _safe_error(last_error),
            }
        )
        return self.store.save(failed)


_SYSTEM_PROMPT = (
    "You are a post-close market-statistics interpreter. Return only one JSON object matching the "
    "requested schema. Do not modify or override any statistic, score, level, factor weights, or "
    "trade permission. Do not name individual stocks. Do not recommend position sizing or orders. "
    "Do not invent missing values; state unavailable data as unavailable. Every key driver and next "
    "session watch condition must cite an input number or threshold using an ASCII digit."
)


def _factor_payload(factor: Any) -> dict[str, object]:
    return {
        "score": factor.score,
        "raw_value": factor.raw_value,
        "raw_unit": factor.raw_unit,
    }


def _history_through(
    percentile: SentimentPercentilePoint,
    history: Sequence[SentimentPercentilePoint],
) -> list[SentimentPercentilePoint]:
    by_date = {point.trade_date: point for point in history if point.trade_date <= percentile.trade_date}
    by_date[percentile.trade_date] = percentile
    return [by_date[trade_date] for trade_date in sorted(by_date)]


def _score_change(
    current: SentimentPercentilePoint,
    prior: SentimentPercentilePoint | None,
) -> float | None:
    return round(current.score - prior.score, 1) if prior else None


def _zone_transition(
    prior: SentimentPercentilePoint | None,
    current: SentimentPercentilePoint,
) -> dict[str, str | None]:
    return {"from": prior.level if prior else None, "to": current.level}


def _validation_payload(validation: Mapping[str, Any] | None) -> dict[str, object]:
    if not validation or validation.get("status") == "unavailable":
        return {
            "source_date": None,
            "status": "unavailable",
            "sample_count": 0,
            "sample_counts": {},
            "conclusion": None,
        }

    buckets = validation.get("buckets")
    sample_counts: dict[str, int] = {}
    if isinstance(buckets, list):
        for bucket in buckets:
            if not isinstance(bucket, Mapping):
                continue
            level = bucket.get("level")
            sample_count = bucket.get("sample_count")
            if isinstance(level, str) and isinstance(sample_count, int) and not isinstance(sample_count, bool):
                sample_counts[level] = sample_count
    data_end = validation.get("data_end")
    conclusion = validation.get("conclusion")
    return {
        "source_date": data_end if isinstance(data_end, str) else None,
        "status": "available",
        "sample_count": sum(sample_counts.values()),
        "sample_counts": sample_counts,
        "conclusion": conclusion if isinstance(conclusion, str) else None,
    }


def _validate_result_semantics(
    result: SentimentAnalysisResult,
    analysis_input: _SentimentAnalysisInput,
) -> None:
    text = "\n".join(
        [
            result.market_conclusion,
            *result.key_drivers,
            result.factor_divergence,
            result.historical_context,
            result.risk_posture,
            *result.next_session_watch,
            result.risk_note,
        ]
    )
    if _A_SHARE_CODE_PATTERN.search(text) or _PROHIBITED_RESULT_TEXT_PATTERN.search(text):
        raise ValueError("AI response contains prohibited investment guidance")

    for match in _CURRENT_SCORE_PATTERN.finditer(text):
        if float(match.group(1)) != analysis_input.percentile.score:
            raise ValueError("AI response changes the current score")

    for match in _CURRENT_LEVEL_PATTERN.finditer(text):
        claimed_level = _LEVEL_ALIASES.get(match.group(1).lower(), match.group(1))
        if claimed_level != analysis_input.percentile.level:
            raise ValueError("AI response changes the current level")

    for match in _CURRENT_WEIGHT_PATTERN.finditer(text):
        claimed_weight = float(match.group(1)) / 100 if match.group(2) else float(match.group(1))
        if claimed_weight not in analysis_input.percentile.weights.model_dump().values():
            raise ValueError("AI response changes the current weights")

    for match in _CURRENT_TRADE_PERMISSION_PATTERN.finditer(text):
        if match.group(1) != analysis_input.decision.trade_permission:
            raise ValueError("AI response changes the current trade permission")


def _trade_date(input_payload: Mapping[str, object]) -> str:
    trade_date = input_payload.get("trade_date")
    if not isinstance(trade_date, str):
        raise ValueError("analysis input missing trade_date")
    return trade_date


def _is_matching_ready(
    record: SentimentPercentileAnalysisResponse | None,
    trade_date: str,
    input_hash: str,
    config: EffectiveAiAnalysisSettings,
) -> bool:
    return bool(record and record.status == "ready" and _same_identity(record, trade_date, input_hash, config))


def _is_matching_cooling_failure(
    record: SentimentPercentileAnalysisResponse | None,
    trade_date: str,
    input_hash: str,
    config: EffectiveAiAnalysisSettings,
) -> bool:
    if not record or record.status != "failed" or not _same_identity(record, trade_date, input_hash, config):
        return False
    if not record.retry_after:
        return False
    try:
        return datetime.fromisoformat(record.retry_after) > datetime.now(timezone.utc)
    except ValueError:
        return False


def _same_identity(
    record: SentimentPercentileAnalysisResponse,
    trade_date: str,
    input_hash: str,
    config: EffectiveAiAnalysisSettings,
) -> bool:
    return (
        record.trade_date == trade_date
        and record.model_version == MODEL_VERSION
        and record.provider == config.provider
        and record.llm_model == config.model
        and record.input_hash == input_hash
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _retry_after() -> str:
    return (datetime.now(timezone.utc) + _RETRY_DELAY).isoformat(timespec="seconds")


def _safe_error(error: Exception | None) -> str:
    if isinstance(error, ValidationError):
        return "ValidationError: AI response does not match the required schema"
    if isinstance(error, ValueError):
        return "ValueError: AI response could not be parsed"
    if isinstance(error, httpx.HTTPError):
        return f"{type(error).__name__}: AI provider request failed"
    return f"{type(error).__name__ if error else 'RuntimeError'}: AI generation failed"
