from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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
    r"\b(?:individual\s+stock|stock\s+code|security\s+recommendation|ticker)\b|"
    r"仓位|轻仓|重仓|满仓|半仓|加仓|减仓|建仓|持仓|空仓|"
    r"控制资金比例|资金(?:使用|投入|配置|分配|安排)?(?:比例|占比)|"
    r"\b(?:position\s+sizing|position\s+size|portfolio\s+allocation|"
    r"capital\s+allocation|fund\s+allocation|portfolio\s+exposure)\b|"
    r"买入|卖出|下单|挂单|开仓|平仓|止盈|止损|做多|做空|追涨|抄底|低吸|卖不追|"
    r"\b(?:buy|sell|orders?|go\s+long|go\s+short|stop[- ]?loss|take[- ]?profit)\b)",
    re.IGNORECASE,
)
_TRADE_PERMISSION_CLAIM_PATTERN = re.compile(
    r"(?:交易|操作|买卖)\s*(?:权限|许可|准入)|\b(?:trade|operation)\s+permission\b|"
    r"空仓等待|轻仓试错|强势进攻|只低吸|只卖不追",
    re.IGNORECASE,
)
_NUMBER_TEXT = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_NUMERIC_CLAIM_PATTERN = re.compile(
    rf"(?<![\d.])(?P<number>{_NUMBER_TEXT})(?P<unit>\s*(?:%|％|万亿|亿|万))?(?![\d.])"
)
_DATE_VALUE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
_CLAUSE_SPLIT_PATTERN = re.compile(r"[，,。；;！？!?\n]+")
_CONDITIONAL_ITEM_PATTERN = re.compile(r"^\s*(?:如果|若|一旦|当|只要|\bif\b|\bwhen\b)", re.IGNORECASE)
_THRESHOLD_PREFIX_PATTERN = re.compile(
    r"(?:如果|若|一旦|当|只要|高于|低于|超过|不超过|少于|不少于|至少|至多|"
    r"突破|跌破|达到|维持在|>=|<=|>|<|\bif\b|\bwhen\b|\babove\b|\bbelow\b|"
    r"\bat\s+least\b|\bat\s+most\b)",
    re.IGNORECASE,
)
_THRESHOLD_SUFFIX_PATTERN = re.compile(r"^\s*(?:以上|以下|or\s+(?:more|less)\b)", re.IGNORECASE)
_OVERALL_SCORE_CLAIM_PATTERN = re.compile(
    rf"(?:\b(?:current\s+)?(?:(?:overall|sentiment)\s+)?score\b|"
    rf"(?:当前|目前)?(?:市场|情绪)?(?:综合分|(?:综合|整体|总)?(?:得分|评分|分数)))"
    rf"\s*(?:is|=|:|：|为|是|达(?:到)?|录得|stands?\s+at)?\s*"
    rf"(?P<number>{_NUMBER_TEXT})",
    re.IGNORECASE,
)
_LEVEL_VALUE = (
    r"冰点(?:区|区域|区间)?|偏冷(?:区|区域|区间)?|冷区|中性(?:区|区域|区间)?|"
    r"偏热(?:区|区域|区间)?|热区|过热(?:区|区域|区间)?|ice|cold|neutral|hot|overheated"
)
_CURRENT_LEVEL_CLAIM_PATTERN = re.compile(
    rf"(?:\b(?:current\s+)?(?:sentiment\s+)?(?:level|zone)\b\s*(?:is|=|:)?\s*|"
    rf"(?:当前|目前)?(?:市场|情绪)?(?:等级|级别|分层|区域|区间|位置)?\s*"
    rf"(?:为|是|处于|位于|落在|进入|转为|升至|降至)\s*)"
    rf"(?P<level>{_LEVEL_VALUE})",
    re.IGNORECASE,
)
_LEVEL_ALIASES = {
    "冰点区": "冰点",
    "冰点区域": "冰点",
    "冰点区间": "冰点",
    "偏冷区": "偏冷",
    "偏冷区域": "偏冷",
    "偏冷区间": "偏冷",
    "冷区": "偏冷",
    "中性区": "中性",
    "中性区域": "中性",
    "中性区间": "中性",
    "偏热区": "偏热",
    "偏热区域": "偏热",
    "偏热区间": "偏热",
    "热区": "偏热",
    "过热区": "过热",
    "过热区域": "过热",
    "过热区间": "过热",
    "ice": "冰点",
    "cold": "偏冷",
    "neutral": "中性",
    "hot": "偏热",
    "overheated": "过热",
}
_WEIGHT_CLAIM_SUFFIX = (
    rf"\s*(?:are|is|=|:|：|为|是|达到)?\s*(?P<number>{_NUMBER_TEXT})\s*(?P<percent>%|％)?"
)
_FACTOR_WEIGHT_CLAIM_PATTERNS = (
    (
        "volume",
        re.compile(
            r"(?:成交量|量能)(?:因子)?(?:权重|系数|占比)" + _WEIGHT_CLAIM_SUFFIX,
            re.IGNORECASE,
        ),
    ),
    (
        "index_move_5d",
        re.compile(r"(?:指数)?5日(?:涨跌|涨幅)(?:因子)?(?:权重|系数)" + _WEIGHT_CLAIM_SUFFIX),
    ),
    (
        "price_position",
        re.compile(r"(?:价格位置|价格位阶)(?:因子)?(?:权重|系数)" + _WEIGHT_CLAIM_SUFFIX),
    ),
    (
        "amplitude_5d",
        re.compile(r"(?:5日)?振幅(?:因子)?(?:权重|系数)" + _WEIGHT_CLAIM_SUFFIX),
    ),
    (
        "volume_trend",
        re.compile(r"(?:成交量|量能)趋势(?:因子)?(?:权重|系数)" + _WEIGHT_CLAIM_SUFFIX),
    ),
)
_GENERAL_WEIGHT_CLAIM_PATTERN = re.compile(
    r"(?:\b(?:current\s+)?(?:factor\s+)?weights?\b|"
    r"(?:当前|目前)?(?:各项?)?(?:因子)?(?:权重|系数|占比))"
    + _WEIGHT_CLAIM_SUFFIX,
    re.IGNORECASE,
)
_MARKET_METRIC_CLAIM_PATTERN = re.compile(
    r"涨停|跌停|炸板|破板|封板率|连板(?:数|高度)?|上涨(?:家数|数量)|下跌(?:家数|数量)|"
    r"成交额|市场宽度"
)
_SECTOR_LIMIT_METRIC_PATTERN = re.compile(r"涨停|炸板|破板|连板(?:数|高度)?")
_MAIN_SECTOR_CLAIM_PATTERN = re.compile(r"主线板块|主要板块|板块强度|行业强度|板块(?:涨停|炸板|连板)")
_DECISION_CLAIM_PATTERN = re.compile(
    r"市场状态|情绪状态|风险(?:等级|级别)|决策(?:评分|得分)?变化|"
    r"(?:市场|情绪)(?:状态)?(?:为|是|处于|进入)?(?:修复|主升|高潮|分歧|退潮)"
)
_VALIDATION_CLAIM_PATTERN = re.compile(r"历史样本|验证样本|样本(?:数|数量)|回测(?:样本|结果)")
_HISTORICAL_LEVEL_CUE_PATTERN = re.compile(r"历史|过去|此前|曾经|曾|前一日|前日|昨日|上日|\d+日前")
_CURRENT_CUE_PATTERN = re.compile(r"当前|目前|现时|now|current", re.IGNORECASE)
_MOVEMENT_PATTERN = re.compile(
    r"上涨|下跌|上升|下降|走高|走低|走强|走弱|反弹|回落|攀升|跳水|领涨|领跌|涨幅|跌幅|"
    r"\b(?:rise|rises|rose|fall|falls|fell|rally|rallies|drop|drops|dropped)\b",
    re.IGNORECASE,
)
_RECOMMENDATION_AFTER_PATTERN = re.compile(r"(?:推荐|看好|关注|首选)\s*(?P<target>[^，,。；;！？!?\n]+)")
_RECOMMENDATION_BEFORE_PATTERN = re.compile(
    r"(?P<target>[^，,。；;！？!?\n]+?)(?:值得关注|可重点关注)"
)
_SUBJECT_QUALIFIER_PATTERN = re.compile(
    r"^(?:(?:若|如果|一旦|当|则|但|而|且|今日|当前|目前|明日|次日|"
    r"下一交易日|较前日|环比|近\s*\d+\s*日|过去\s*\d+\s*日|"
    r"小幅|大幅|明显|继续|整体)\s*)+"
)
_AGGREGATE_ENTITY_PATTERN = re.compile(
    r"^(?:A股市场|全市场|市场(?:整体)?|沪深两市|两市|大盘|指数|沪指|深成指|深证成指|"
    r"创业板指|科创\d+|北证\d+|上证[\w\d]{0,8}(?:指数)?|深证[\w\d]{0,8}(?:指数|成指)|"
    r"中证[\w\d]{0,8}(?:指数|指)?|国证[\w\d]{0,8}(?:指数|指)?|"
    r"市场情绪|情绪|综合(?:得)?分|综合评分|评分|得分)$",
    re.IGNORECASE,
)
_GENERIC_METRIC_ENTITY_PATTERN = re.compile(
    r"^(?:涨停|跌停|炸板|破板|封板率|连板(?:数|高度)?|成交额|成交量|量能(?:趋势)?|"
    r"价格位置|5日振幅|振幅|市场宽度|历史样本|样本(?:数|数量)?|上涨家数|下跌家数|"
    r"板块|行业|题材)$"
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
    "trade permission. Do not state any trade or operation permission. Do not name or recommend "
    "individual stocks, position sizing, fund allocation, or orders. Do not invent missing values; "
    "state unavailable data as unavailable. Every factual number must equal a provided input value. "
    "Only next-session watch conditions may introduce a new number, and only as an explicit "
    "conditional threshold. Describe movements only for market aggregates, indexes, or supplied "
    "sectors. Every key driver and next session watch condition must cite an ASCII digit."
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
    canonical_numbers = _canonical_numbers(analysis_input)
    canonical_dates = _canonical_dates(analysis_input)
    sector_names = tuple(item.name for item in analysis_input.main_sectors.items)

    for field_name, text in _result_text_items(result):
        _validate_prohibited_semantics(text, sector_names)
        _validate_protected_claims(text, analysis_input)
        _validate_movement_subjects(text, sector_names)

        for clause in _CLAUSE_SPLIT_PATTERN.split(text):
            if not clause:
                continue
            allows_watch_thresholds = field_name == "next_session_watch"
            _validate_source_availability(
                clause,
                analysis_input,
                sector_names,
                allow_threshold=allows_watch_thresholds and _is_threshold_clause(clause),
            )
            _validate_numeric_evidence(
                clause,
                canonical_numbers,
                canonical_dates,
                allow_thresholds=allows_watch_thresholds,
            )


def _result_text_items(result: SentimentAnalysisResult) -> tuple[tuple[str, str], ...]:
    return (
        ("market_conclusion", result.market_conclusion),
        *(("key_drivers", item) for item in result.key_drivers),
        ("factor_divergence", result.factor_divergence),
        ("historical_context", result.historical_context),
        ("risk_posture", result.risk_posture),
        *(("next_session_watch", item) for item in result.next_session_watch),
        ("risk_note", result.risk_note),
    )


def _canonical_numbers(analysis_input: _SentimentAnalysisInput) -> set[Decimal]:
    numbers: set[Decimal] = set()

    def collect(value: object, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            number = Decimal(str(value))
            numbers.add(number)
            if len(path) >= 2 and path[-2] == "weights":
                numbers.add(number * Decimal("100"))
            return
        if isinstance(value, Mapping):
            for key, child in value.items():
                collect(child, (*path, str(key)))
        elif isinstance(value, list):
            for child in value:
                collect(child, path)

    collect(analysis_input.model_dump(mode="python", by_alias=True))
    return numbers


def _canonical_dates(analysis_input: _SentimentAnalysisInput) -> set[str]:
    dates: set[str] = set()

    def collect(value: object) -> None:
        if isinstance(value, str) and _DATE_VALUE_PATTERN.fullmatch(value):
            dates.add(value)
        elif isinstance(value, Mapping):
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(analysis_input.model_dump(mode="python", by_alias=True))
    return dates


def _validate_prohibited_semantics(text: str, sector_names: Sequence[str]) -> None:
    if _A_SHARE_CODE_PATTERN.search(text) or _PROHIBITED_RESULT_TEXT_PATTERN.search(text):
        raise ValueError("AI response contains prohibited investment guidance")
    if _TRADE_PERMISSION_CLAIM_PATTERN.search(text):
        raise ValueError("AI response contains prohibited trade permission")

    for pattern in (_RECOMMENDATION_AFTER_PATTERN, _RECOMMENDATION_BEFORE_PATTERN):
        for match in pattern.finditer(text):
            if not _is_allowed_entity_reference(match.group("target"), sector_names):
                raise ValueError("AI response recommends a non-aggregate security")


def _validate_protected_claims(
    text: str,
    analysis_input: _SentimentAnalysisInput,
) -> None:
    expected_score = Decimal(str(analysis_input.percentile.score))
    for match in _OVERALL_SCORE_CLAIM_PATTERN.finditer(text):
        if _decimal(match.group("number")) != expected_score:
            raise ValueError("AI response changes the current score")

    for match in _CURRENT_LEVEL_CLAIM_PATTERN.finditer(text):
        if _is_historical_level_claim(text, match):
            continue
        raw_level = match.group("level").lower()
        claimed_level = _LEVEL_ALIASES.get(raw_level, raw_level)
        if claimed_level != analysis_input.percentile.level:
            raise ValueError("AI response changes the current level")

    weights = analysis_input.percentile.weights.model_dump()
    for factor_name, pattern in _FACTOR_WEIGHT_CLAIM_PATTERNS:
        for match in pattern.finditer(text):
            if _weight_value(match) != Decimal(str(weights[factor_name])):
                raise ValueError("AI response changes a factor coefficient")

    expected_weights = {Decimal(str(value)) for value in weights.values()}
    for match in _GENERAL_WEIGHT_CLAIM_PATTERN.finditer(text):
        if _weight_value(match) not in expected_weights:
            raise ValueError("AI response changes the current weights")


def _validate_movement_subjects(text: str, sector_names: Sequence[str]) -> None:
    for clause in _CLAUSE_SPLIT_PATTERN.split(text):
        for match in _MOVEMENT_PATTERN.finditer(clause):
            subject = _movement_subject(clause[: match.start()])
            if subject and not _is_allowed_entity_reference(subject, sector_names):
                raise ValueError("AI response names a non-aggregate movement subject")


def _movement_subject(prefix: str) -> str:
    subject = _SUBJECT_QUALIFIER_PATTERN.sub("", prefix).strip()
    subject = re.sub(r"^(?:近|过去)?\s*\d+(?:\.\d+)?\s*(?:日|周|月|年)(?:内)?\s*", "", subject)
    return subject.rstrip("的 ").strip()


def _is_allowed_entity_reference(text: str, sector_names: Sequence[str]) -> bool:
    reference = text.strip().rstrip("的 ")
    reference = re.split(r"(?:为|是|处于|位于|维持|高于|低于|达到|超过|\d)", reference, maxsplit=1)[0]
    reference = reference.strip().rstrip("的 ")
    if not reference:
        return True

    parts = [part.strip().rstrip("的 ") for part in re.split(r"[、与和及/]", reference) if part.strip()]
    return bool(parts) and all(_is_allowed_entity_part(part, sector_names) for part in parts)


def _is_allowed_entity_part(part: str, sector_names: Sequence[str]) -> bool:
    normalized = _SUBJECT_QUALIFIER_PATTERN.sub("", part).strip()
    normalized = re.sub(r"^(?:近|过去)?\s*\d+\s*(?:日|周|月|年)\s*", "", normalized)
    normalized = normalized.removesuffix("板块").removesuffix("行业").removesuffix("题材")
    if normalized in sector_names:
        return True
    return bool(
        _AGGREGATE_ENTITY_PATTERN.fullmatch(normalized)
        or _GENERIC_METRIC_ENTITY_PATTERN.fullmatch(normalized)
    )


def _validate_source_availability(
    clause: str,
    analysis_input: _SentimentAnalysisInput,
    sector_names: Sequence[str],
    *,
    allow_threshold: bool,
) -> None:
    if allow_threshold:
        return

    has_named_sector = any(name in clause for name in sector_names)
    has_sector_metric = has_named_sector and bool(_SECTOR_LIMIT_METRIC_PATTERN.search(clause))
    if _MARKET_METRIC_CLAIM_PATTERN.search(clause) and not has_sector_metric:
        if analysis_input.market.status == "unavailable":
            raise ValueError("AI response claims unavailable market metrics")
    if _MAIN_SECTOR_CLAIM_PATTERN.search(clause) and analysis_input.main_sectors.status == "unavailable":
        raise ValueError("AI response claims unavailable sector metrics")
    if _DECISION_CLAIM_PATTERN.search(clause) and analysis_input.decision.status == "unavailable":
        raise ValueError("AI response claims unavailable decision metrics")
    if _VALIDATION_CLAIM_PATTERN.search(clause) and analysis_input.validation.status == "unavailable":
        raise ValueError("AI response claims unavailable validation metrics")


def _validate_numeric_evidence(
    clause: str,
    canonical_numbers: set[Decimal],
    canonical_dates: set[str],
    *,
    allow_thresholds: bool,
) -> None:
    factual_text = clause
    for date in canonical_dates:
        factual_text = factual_text.replace(date, "")

    for match in _NUMERIC_CLAIM_PATTERN.finditer(factual_text):
        if _normalized_claim_number(match) in canonical_numbers:
            continue
        if allow_thresholds and _number_is_threshold(factual_text, match):
            continue
        raise ValueError("AI response contains an ungrounded factual number")


def _is_threshold_clause(clause: str) -> bool:
    matches = list(_NUMERIC_CLAIM_PATTERN.finditer(clause))
    return bool(matches) and all(_number_is_threshold(clause, match) for match in matches)


def _number_is_threshold(clause: str, match: re.Match[str]) -> bool:
    if _CONDITIONAL_ITEM_PATTERN.search(clause):
        return True

    previous_end = 0
    next_start = len(clause)
    for candidate in _NUMERIC_CLAIM_PATTERN.finditer(clause):
        if candidate.end() <= match.start():
            previous_end = candidate.end()
        elif candidate.start() > match.start():
            next_start = candidate.start()
            break

    prefix = clause[previous_end : match.start()]
    suffix = clause[match.end() : next_start]
    return bool(_THRESHOLD_PREFIX_PATTERN.search(prefix) or _THRESHOLD_SUFFIX_PATTERN.search(suffix))


def _is_historical_level_claim(text: str, match: re.Match[str]) -> bool:
    clause_start = max(text.rfind(delimiter, 0, match.start()) for delimiter in "，,。；;！？!?\n") + 1
    prefix = text[clause_start : match.start()]
    return bool(_HISTORICAL_LEVEL_CUE_PATTERN.search(prefix)) and not bool(
        _CURRENT_CUE_PATTERN.search(prefix)
    )


def _normalized_claim_number(match: re.Match[str]) -> Decimal:
    number = _decimal(match.group("number"))
    unit = (match.group("unit") or "").strip()
    if unit == "万":
        return number * Decimal("10000")
    if unit == "亿":
        return number * Decimal("100000000")
    if unit == "万亿":
        return number * Decimal("1000000000000")
    return number


def _weight_value(match: re.Match[str]) -> Decimal:
    value = _decimal(match.group("number"))
    return value / Decimal("100") if match.group("percent") else value


def _decimal(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


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
