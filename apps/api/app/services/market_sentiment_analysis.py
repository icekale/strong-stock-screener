from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Mapping, Sequence

import httpx
from pydantic import ValidationError

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
    metrics = summary.metrics if summary else None

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
            "source_date": summary.trade_date if summary else None,
            "status": "available" if summary else "unavailable",
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
        trade_date = _trade_date(input_payload)
        input_hash = hash_sentiment_analysis_input(input_payload)
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
            return self._generate_after_pending(pending, input_payload, config)

    def _generate_after_pending(
        self,
        pending: SentimentPercentileAnalysisResponse,
        input_payload: Mapping[str, object],
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
