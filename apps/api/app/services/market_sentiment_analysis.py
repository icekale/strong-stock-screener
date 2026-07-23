from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import RLock
from typing import Any, Literal, Mapping, Sequence

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

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
_PENDING_TIMEOUT = timedelta(minutes=3)
_AI_PROVIDER_TIMEOUT_SECONDS = 60


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

    @field_validator("name")
    @classmethod
    def _reject_security_identifiers(cls, value: str) -> str:
        if _A_SHARE_CODE_PATTERN.search(value) or _SECURITY_IDENTIFIER_PATTERN.search(value):
            raise ValueError("sector names cannot contain security identifiers")
        return value


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
_SECURITY_IDENTIFIER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:SH|SZ|BJ)[.:]?\d{6}(?![A-Za-z0-9])", re.IGNORECASE
)
_NUMBER_TEXT = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_PROHIBITED_RESULT_TEXT_PATTERN = re.compile(
    r"(?:个股|股票(?:代码)?|证券代码|标的|"
    r"\b(?:individual\s+stock|stock\s+code|security\s+recommendation|ticker)\b|"
    r"仓位|轻仓|重仓|满仓|半仓|加仓|减仓|增持|减持|建仓|持仓|持有|空仓|"
    rf"\b(?:maintain|hold|keep)\s+(?:a\s+)?{_NUMBER_TEXT}\s*(?:%|％)?\s+position\b|"
    r"控制资金比例|资金(?:使用|投入|配置|分配|安排)?(?:比例|占比)|"
    rf"(?:建议|计划|可以|可)?\s*(?:投入|配置|分配|安排)\s*{_NUMBER_TEXT}\s*(?:%|％)?\s*资金|"
    r"\b(?:position\s+sizing|position\s+size|portfolio\s+allocation|"
    r"capital\s+allocation|fund\s+allocation|portfolio\s+exposure)\b|"
    r"买入|卖出|申购|认购|赎回|下单|挂单|撤单|报单|委托|开仓|平仓|"
    r"止盈|止损|做多|做空|追涨|抄底|低吸|卖不追|"
    r"\b(?:buy|sell|orders?|go\s+long|go\s+short|stop[- ]?loss|take[- ]?profit)\b)",
    re.IGNORECASE,
)
_TRADE_PERMISSION_CLAIM_PATTERN = re.compile(
    r"(?:交易|操作|买卖)\s*(?:权限|许可|准入)|\b(?:trade|operation)\s+permission\b|"
    r"(?:当前|目前)?\s*(?:策略|操作)\s*(?:允许|许可|可以|可)\s*"
    r"(?:积极|谨慎|适度|重点)?\s*(?:参与|操作|交易|进场)|"
    r"空仓等待|轻仓试错|强势进攻|只低吸|只卖不追",
    re.IGNORECASE,
)
_NUMERIC_CLAIM_PATTERN = re.compile(
    rf"(?<![\d.])(?P<number>{_NUMBER_TEXT})(?P<unit>\s*(?:%|％|万亿|亿|万))?(?![\d.])"
)
_CHINESE_NUMERIC_CLAIM_PATTERN = re.compile(
    r"(?<![零〇一二两三四五六七八九十百千万亿点前])"
    r"(?P<number>[零〇一二两三四五六七八九十百千万亿点]+?)"
    r"(?P<unit>个?百分点|个?点|%|％|万亿|亿|万|家|个|项|次|分|倍|成)"
    r"(?![零〇一二两三四五六七八九十百千万亿点])"
)
_DATE_VALUE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
_NUMBERED_INDEX_ENTITY_PATTERN = re.compile(
    r"(?:沪深|中证|上证|深证|国证|科创|北证|创业板)\d+(?:指数|指)?",
    re.IGNORECASE,
)
_CLAUSE_SPLIT_PATTERN = re.compile(r"[，,。；;！？!?、\n]+")
_CONSEQUENCE_SPLIT_PATTERN = re.compile(r"\s*(?:(?<!否)则|那么|届时|\bthen\b)\s*", re.IGNORECASE)
_MOVEMENT_CONNECTOR_PREFIX_PATTERN = re.compile(r"^\s*(?:且|并且|以及|同时|和|与)\s*")
_THRESHOLD_PREFIX_PATTERN = re.compile(
    r"(?:如果|若|一旦|当|只要|高于|低于|超过|不超过|少于|不少于|至少|至多|"
    r"突破|跌破|达到|维持在|>=|<=|>|<|\bif\b|\bwhen\b|\babove\b|\bbelow\b|"
    r"\bat\s+least\b|\bat\s+most\b)",
    re.IGNORECASE,
)
_THRESHOLD_SUFFIX_PATTERN = re.compile(r"^\s*(?:以上|以下|or\s+(?:more|less)\b)", re.IGNORECASE)
_OVERALL_SCORE_CLAIM_PATTERN = re.compile(
    rf"(?:\b(?:current\s+)?(?:(?:overall|sentiment)\s+)?score\b|"
    rf"(?:当前|目前)?(?:(?:市场|情绪)(?:综合)?(?:分|得分|评分|分数)|"
    rf"(?:综合|整体|总)(?:分|得分|评分|分数)))"
    rf"\s*(?:is|=|:|：|为|是|达(?:到)?|录得|stands?\s+at)?\s*"
    rf"(?P<number>{_NUMBER_TEXT})",
    re.IGNORECASE,
)
_LEVEL_VALUE = (
    r"冰点(?:区|区域|区间|水平|层级)?|偏冷(?:区|区域|区间|水平|层级)?|冷区|"
    r"中性(?:区|区域|区间|水平|层级)?|偏热(?:区|区域|区间|水平|层级)?|热区|"
    r"过热(?:区|区域|区间|水平|层级)?|ice|cold|neutral|hot|overheated"
)
_CURRENT_LEVEL_CLAIM_PATTERN = re.compile(
    rf"(?:\b(?:current\s+)?(?:sentiment\s+)?(?:level|zone)\b\s*(?:is|=|:)?\s*|"
    rf"(?:当前|目前)?(?:市场|情绪)?(?:等级|级别|分层|区域|区间|位置)?\s*"
    rf"(?:为|是|呈|呈现|处于|位于|落在|进入|转为|升至|降至)\s*)"
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
_WEIGHT_TERM = r"(?:权重|系数|占比|比重|贡献度|贡献率)"
_FACTOR_WEIGHT_CLAIM_PATTERNS = (
    (
        "volume",
        re.compile(
            r"(?:成交量|量能)(?:因子)?" + _WEIGHT_TERM + _WEIGHT_CLAIM_SUFFIX,
            re.IGNORECASE,
        ),
    ),
    (
        "index_move_5d",
        re.compile(
            r"(?:指数)?5日(?:涨跌|涨幅)(?:因子)?" + _WEIGHT_TERM + _WEIGHT_CLAIM_SUFFIX
        ),
    ),
    (
        "price_position",
        re.compile(r"(?:价格位置|价格位阶)(?:因子)?" + _WEIGHT_TERM + _WEIGHT_CLAIM_SUFFIX),
    ),
    (
        "amplitude_5d",
        re.compile(r"(?:5日)?振幅(?:因子)?" + _WEIGHT_TERM + _WEIGHT_CLAIM_SUFFIX),
    ),
    (
        "volume_trend",
        re.compile(
            r"(?:成交量|量能)趋势(?:因子)?" + _WEIGHT_TERM + _WEIGHT_CLAIM_SUFFIX
        ),
    ),
)
_GENERAL_WEIGHT_CLAIM_PATTERN = re.compile(
    r"(?:\b(?:current\s+)?(?:factor\s+)?weights?\b|"
    r"(?:当前|目前)?(?:各项?)?(?:因子)?" + _WEIGHT_TERM + r")"
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
    r"(?:市场|情绪)(?:状态)?(?:为|是|处于|进入|转入|转为)?(?:修复|主升|高潮|分歧|退潮)"
)
_VALIDATION_CLAIM_PATTERN = re.compile(r"历史样本|验证样本|样本(?:数|数量)|回测(?:样本|结果)")
_HISTORICAL_LEVEL_CUE_PATTERN = re.compile(r"历史|过去|此前|曾经|曾|前一日|前日|昨日|上日|\d+日前")
_CURRENT_CUE_PATTERN = re.compile(r"当前|目前|现时|now|current", re.IGNORECASE)
_MOVEMENT_PATTERN = re.compile(
    r"上涨(?:了)?|下跌(?:了)?|上升|下降|走高|走低|走强|走弱|反弹|回落|攀升|跳水|"
    r"领涨|领跌|涨幅|跌幅|涨了|跌了|"
    r"\b(?:rise|rises|rose|fall|falls|fell|rally|rallies|drop|drops|dropped)\b",
    re.IGNORECASE,
)
_RECOMMENDATION_AFTER_PATTERN = re.compile(
    r"(?:推荐|看好|关注|首选|建议(?:配置|持有|买入?|卖出?))\s*"
    r"(?P<target>[^，,。；;！？!?\n]+)"
)
_RECOMMENDATION_BEFORE_PATTERN = re.compile(
    r"(?P<target>[^，,。；;！？!?\n]+?)(?:值得关注|可重点关注|值得买|值得卖|是首选)"
)
_ATTENTION_CLAIM_PATTERN = re.compile(
    r"(?P<target>[^，,。；;！？!?\n]+?)(?:的)?表现受到关注"
)
_VALUATION_CLAIM_PATTERN = re.compile(
    r"(?P<target>[^，,。；;！？!?\n]+?)(?:估值|价值)\s*(?:偏高|偏低|高估|低估|合理|昂贵|便宜)"
)
_SUBJECT_QUALIFIER_PATTERN = re.compile(
    r"^(?:(?:若|如果|一旦|当|则|但|而|且|今日|当前|目前|明日|次日|"
    r"当日|下一交易日|较前日|环比|近\s*\d+\s*日|过去\s*\d+\s*日|"
    r"小幅|大幅|明显|继续|整体)\s*)+"
)
_AGGREGATE_ENTITY_PATTERN = re.compile(
    r"^(?:A股市场|全市场|市场(?:整体)?|沪深两市|两市|大盘|指数|沪指|深成指|深证成指|"
    r"沪深\d+(?:指数)?|创业板(?:指)?|科创50(?:指数)?|北证\d+|"
    r"上证[\w\d]{0,8}(?:指数)?|深证[\w\d]{0,8}(?:指数|成指)|"
    r"中证[\w\d]{0,8}(?:指数|指)?|国证[\w\d]{0,8}(?:指数|指)?|"
    r"市场情绪|情绪|综合(?:得)?分|综合评分|评分|得分)$",
    re.IGNORECASE,
)
_GENERIC_METRIC_ENTITY_PATTERN = re.compile(
    r"^(?:涨停(?:数|家数|数量)?|跌停(?:数|家数|数量)?|炸板(?:数|家数|数量)?|"
    r"破板(?:数|家数|数量)?|封板率|连板(?:数|高度)?|成交额|成交量|量能(?:趋势)?|"
    r"价格位置|5日振幅|振幅|市场宽度|历史样本|样本(?:数|数量)?|上涨家数|下跌家数|"
    r"板块|行业|题材)$"
)
_CLAIM_NUMBER = rf"(?P<number>{_NUMBER_TEXT})(?P<unit>\s*(?:%|％|万亿|亿|万))?"
_VALUE_LINK = (
    r"\s*(?:能否|是否|仅|约)?\s*"
    r"(?:为|是|达(?:到)?|录得|升至|上升至|增至|降至|下降至|回落至|"
    r"维持在|高于|低于|超过|不超过|少于|不少于|至少|至多|突破|跌破|=|:|：)?"
    r"\s*(?:仅|约)?\s*"
)
_SECTOR_STRENGTH_CLAIM_PATTERN = re.compile(r"板块强度" + _VALUE_LINK + _CLAIM_NUMBER)
_MARKET_FIELD_CLAIM_PATTERNS = (
    ("limit_up_count", re.compile(r"涨停(?:数|家数|数量)?" + _VALUE_LINK + _CLAIM_NUMBER)),
    ("limit_down_count", re.compile(r"跌停(?:数|家数|数量)?" + _VALUE_LINK + _CLAIM_NUMBER)),
    (
        "break_board_count",
        re.compile(r"(?:炸板|破板)(?:数|家数|数量)?" + _VALUE_LINK + _CLAIM_NUMBER),
    ),
    ("seal_rate_pct", re.compile(r"封板率" + _VALUE_LINK + _CLAIM_NUMBER)),
    ("turnover_cny", re.compile(r"成交额" + _VALUE_LINK + _CLAIM_NUMBER)),
    ("advance_count", re.compile(r"上涨(?:家数|数量)" + _VALUE_LINK + _CLAIM_NUMBER)),
    ("decline_count", re.compile(r"下跌(?:家数|数量)" + _VALUE_LINK + _CLAIM_NUMBER)),
    (
        "max_consecutive_boards",
        re.compile(r"连板(?:数|高度)?" + _VALUE_LINK + _CLAIM_NUMBER),
    ),
)
_FACTOR_SCORE_CLAIM_PATTERNS = tuple(
    (name, re.compile(label + r"(?:因子)?(?:得分|评分|分数|分位)" + _VALUE_LINK + _CLAIM_NUMBER))
    for name, label in (
        ("volume", r"(?:成交量|量能)(?!趋势)"),
        ("index_move_5d", r"(?:(?:指数)?5日|5日指数)(?:涨跌|涨幅)"),
        ("price_position", r"(?:价格位置|价格位阶)"),
        ("amplitude_5d", r"(?:5日)?振幅"),
        ("volume_trend", r"(?:成交量|量能)趋势"),
    )
)
_FACTOR_RAW_CLAIM_PATTERNS = (
    ("volume", re.compile(r"(?:成交量|量能)(?!趋势)(?:原始值|数值|值)?" + _VALUE_LINK + _CLAIM_NUMBER)),
    (
        "index_move_5d",
        re.compile(r"(?:(?:指数)?5日|5日指数)(?:涨跌幅?|涨幅|表现)" + _VALUE_LINK + _CLAIM_NUMBER),
    ),
    (
        "price_position",
        re.compile(r"(?:价格位置|价格位阶)(?:原始值|数值|值)?" + _VALUE_LINK + _CLAIM_NUMBER),
    ),
    (
        "amplitude_5d",
        re.compile(r"(?:5日)?振幅(?:原始值|数值|值)?" + _VALUE_LINK + _CLAIM_NUMBER),
    ),
    (
        "volume_trend",
        re.compile(r"(?:成交量|量能)趋势(?:原始值|数值|值)?" + _VALUE_LINK + _CLAIM_NUMBER),
    ),
)
_MOVEMENT_VALUE_CLAIM_PATTERN = re.compile(
    r"(?P<movement>上涨|下跌|上升|下降|走高|走低|走强|走弱|反弹|回落|攀升|跳水|"
    r"领涨|领跌|涨幅|跌幅|涨|跌)(?:了)?" + _VALUE_LINK + _CLAIM_NUMBER,
    re.IGNORECASE,
)
_FIVE_DAY_SUFFIX_PATTERN = re.compile(r"(?:近|过去)?\s*(?:5|五)\s*日(?:内)?$")
_NEGATIVE_MOVEMENT_PATTERN = re.compile(r"下跌|下降|走低|走弱|回落|跳水|领跌|跌幅|跌")
_SCORE_CHANGE_1D_CLAIM_PATTERN = re.compile(
    r"(?:(?:市场情绪|市场|情绪|综合)?(?:得分|评分|分数)\s*(?:较|比)\s*"
    r"(?:前一日|前日|昨日|上日)|(?:单日|一日|1日)\s*(?:市场情绪|市场|情绪|综合)?"
    r"(?:得分|评分|分数))\s*(?P<direction>变化|变动|上升|下降|增加|减少)"
    r"\s*(?:为|至|了)?\s*" + _CLAIM_NUMBER
)
_SCORE_CHANGE_5D_CLAIM_PATTERN = re.compile(
    r"(?:(?:市场情绪|市场|情绪|综合)?(?:得分|评分|分数)\s*(?:较|比)\s*5日前|"
    r"(?:5日|五日)\s*(?:市场情绪|市场|情绪|综合)?(?:得分|评分|分数))\s*"
    r"(?P<direction>变化|变动|上升|下降|增加|减少)\s*(?:为|至|了)?\s*"
    + _CLAIM_NUMBER
)
_DECISION_SCORE_CHANGE_CLAIM_PATTERN = re.compile(
    r"决策(?:得分|评分|分数)?(?:变化|变动)" + _VALUE_LINK + _CLAIM_NUMBER
)
_ONE_DAY_LEVEL_CUE_PATTERN = re.compile(r"前一日|前日|昨日|上日")
_FIVE_DAY_LEVEL_CUE_PATTERN = re.compile(r"5日前|五日前")


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

    payload = {
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
    return _normalize_analysis_input(payload)


def hash_sentiment_analysis_input(payload: Mapping[str, object]) -> str:
    canonical_input = _normalize_analysis_input(payload)
    canonical = json.dumps(
        canonical_input,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sentiment_analysis_record_matches(
    record: SentimentPercentileAnalysisResponse | None,
    input_payload: Mapping[str, object],
    config: EffectiveAiAnalysisSettings,
) -> bool:
    if record is None:
        return False
    canonical_input = _normalize_analysis_input(input_payload)
    trade_date = _trade_date(canonical_input)
    input_hash = hash_sentiment_analysis_input(canonical_input)
    return _same_identity(record, trade_date, input_hash, config)


def sentiment_analysis_record_is_reusable(
    record: SentimentPercentileAnalysisResponse | None,
    input_payload: Mapping[str, object],
    config: EffectiveAiAnalysisSettings,
) -> bool:
    if not sentiment_analysis_record_matches(record, input_payload, config):
        return False
    if record is None:
        return False
    if record.status == "ready":
        return True
    return _is_matching_cooling_failure(
        record,
        record.trade_date,
        record.input_hash or "",
        config,
    )


def pending_analysis_is_stale(
    record: SentimentPercentileAnalysisResponse | None,
    *,
    now: datetime | None = None,
) -> bool:
    if record is None or record.status != "pending" or not record.requested_at:
        return False
    try:
        requested_at = datetime.fromisoformat(record.requested_at)
    except ValueError:
        return True
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current - requested_at.astimezone(timezone.utc) > _PENDING_TIMEOUT


def _normalize_analysis_input(payload: Mapping[str, object]) -> dict[str, object]:
    return _SentimentAnalysisInput.model_validate(payload).model_dump(mode="json", by_alias=True)


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
        client = self.http_client or httpx.Client(timeout=_AI_PROVIDER_TIMEOUT_SECONDS)
        should_close = self.http_client is None
        last_error: Exception | None = None
        validation_feedback = ""
        attempts = 0
        try:
            for attempt in range(1, 4):
                attempts = attempt
                try:
                    messages: list[dict[str, str]] = [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "instruction": _COMPACT_OUTPUT_PROMPT,
                                    "data": input_payload,
                                },
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                        },
                    ]
                    if validation_feedback:
                        messages.append({"role": "user", "content": validation_feedback})
                    response = client.post(
                        f"{config.base_url.rstrip('/')}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {config.api_key}",
                            "Content-Type": "application/json",
                            "User-Agent": "StockMaster/1.0",
                        },
                        json={
                            "model": config.model,
                            "temperature": 0.0,
                            "max_tokens": 1200,
                            "response_format": {"type": "json_object"},
                            "messages": messages,
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    result = SentimentAnalysisResult.model_validate(
                        _normalize_sentiment_result_payload(
                            extract_json_object(extract_chat_content(payload))
                        )
                    )
                    _validate_result_semantics(result, analysis_input)
                except Exception as exc:
                    last_error = exc
                    if isinstance(exc, httpx.TimeoutException):
                        break
                    validation_feedback = (
                        "上一次短键 JSON 未通过本地校验。只返回 c,d,v,h,p,w,n 这 7 个短键，"
                        "修正格式或数字后重试；只使用输入数据，不要输出其他内容。"
                    )
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
                "attempts": attempts,
                "completed_at": _now(),
                "retry_after": _retry_after(),
                "error": _safe_error(last_error),
            }
        )
        return self.store.save(failed)


_SYSTEM_PROMPT = "只返回 JSON。"
_COMPACT_OUTPUT_PROMPT = (
    "请做收盘市场统计摘要，只返回 JSON，且只能使用短键 c、d、v、h、p、w、n。"
    "c 是市场结论，d 是 2 到 4 条带数字的主要驱动，v 是因子背离，h 是历史位置，"
    "p 只能是 attack、balanced、defensive、wait，w 是 2 到 4 条带数字的次日观察，"
    "n 只能写数据缺失、样本限制或模型局限。只使用输入数字，保持简洁；不要输出数据表、"
    "个股、买卖建议、仓位或持有建议。"
)


def _normalize_sentiment_result_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        "market_conclusion": "c",
        "key_drivers": "d",
        "factor_divergence": "v",
        "historical_context": "h",
        "risk_posture": "p",
        "next_session_watch": "w",
        "risk_note": "n",
    }
    if any(key in payload for key in aliases):
        return payload
    return {
        field_name: payload.get(compact_key)
        for field_name, compact_key in aliases.items()
    }


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

        previous_sector: str | None = None
        for clause, allows_watch_thresholds in _validation_segments(field_name, text):
            current_sector = next((name for name in sector_names if name in clause), None)
            is_market_clause = bool(re.search(r"全(?:市场|市)|市场", clause))
            continues_sector = (
                previous_sector is not None
                and current_sector is None
                and not is_market_clause
                and bool(_SECTOR_LIMIT_METRIC_PATTERN.search(clause))
            )
            validation_clause = f"{previous_sector}{clause}" if continues_sector else clause
            _validate_field_specific_claims(
                validation_clause,
                analysis_input,
                allow_thresholds=allows_watch_thresholds,
            )
            _validate_source_availability(
                validation_clause,
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
            previous_sector = current_sector or (previous_sector if continues_sector else None)


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


def _validation_segments(field_name: str, text: str) -> tuple[tuple[str, bool], ...]:
    segments: list[tuple[str, bool]] = []
    for clause in _CLAUSE_SPLIT_PATTERN.split(text):
        if not clause:
            continue
        if field_name != "next_session_watch":
            segments.append((clause, False))
            continue

        parts = [part for part in _CONSEQUENCE_SPLIT_PATTERN.split(clause) if part]
        if not parts:
            continue
        segments.append((parts[0], True))
        segments.extend((part, False) for part in parts[1:])
    return tuple(segments)


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
    for match in _ATTENTION_CLAIM_PATTERN.finditer(text):
        if not _is_allowed_entity_reference(match.group("target"), sector_names):
            raise ValueError("AI response gives attention to a non-aggregate security")
    for match in _VALUATION_CLAIM_PATTERN.finditer(text):
        if not _is_allowed_entity_reference(match.group("target"), sector_names):
            raise ValueError("AI response evaluates a non-aggregate security")


def _validate_protected_claims(
    text: str,
    analysis_input: _SentimentAnalysisInput,
) -> None:
    expected_score = Decimal(str(analysis_input.percentile.score))
    for match in _OVERALL_SCORE_CLAIM_PATTERN.finditer(text):
        if _decimal(match.group("number")) != expected_score:
            raise ValueError("AI response changes the current score")

    for match in _CURRENT_LEVEL_CLAIM_PATTERN.finditer(text):
        expected_level = analysis_input.percentile.level
        if _is_historical_level_claim(text, match):
            expected_level = _prior_level_for_claim(text, match, analysis_input)
        if expected_level is None or _canonical_level(match.group("level")) != expected_level:
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


def _validate_field_specific_claims(
    clause: str,
    analysis_input: _SentimentAnalysisInput,
    *,
    allow_thresholds: bool,
) -> None:
    _validate_sector_strength_claims(clause, analysis_input, allow_thresholds=allow_thresholds)
    _validate_movement_value_claims(clause, analysis_input, allow_thresholds=allow_thresholds)

    for field_name, pattern in _MARKET_FIELD_CLAIM_PATTERNS:
        value = _market_field_value(field_name, clause, analysis_input)
        _validate_claim_matches(
            pattern,
            clause,
            value,
            allow_thresholds=allow_thresholds,
            error="AI response changes a market metric",
        )

    for factor_name, pattern in _FACTOR_SCORE_CLAIM_PATTERNS:
        value = Decimal(str(getattr(analysis_input.percentile.factors, factor_name).score))
        _validate_claim_matches(
            pattern,
            clause,
            value,
            allow_thresholds=allow_thresholds,
            error="AI response changes a factor score",
        )
    for factor_name, pattern in _FACTOR_RAW_CLAIM_PATTERNS:
        value = Decimal(str(getattr(analysis_input.percentile.factors, factor_name).raw_value))
        _validate_claim_matches(
            pattern,
            clause,
            value,
            allow_thresholds=allow_thresholds,
            error="AI response changes a factor value",
        )

    _validate_claim_matches(
        _SCORE_CHANGE_1D_CLAIM_PATTERN,
        clause,
        _decimal_or_none(analysis_input.score_change_1d),
        allow_thresholds=allow_thresholds,
        error="AI response claims an unavailable one-day score change",
        signed_change=True,
    )
    _validate_claim_matches(
        _SCORE_CHANGE_5D_CLAIM_PATTERN,
        clause,
        _decimal_or_none(analysis_input.score_change_5d),
        allow_thresholds=allow_thresholds,
        error="AI response claims an unavailable five-day score change",
        signed_change=True,
    )
    decision_change = (
        _decimal_or_none(analysis_input.decision.score_change)
        if analysis_input.decision.status == "available"
        else None
    )
    _validate_claim_matches(
        _DECISION_SCORE_CHANGE_CLAIM_PATTERN,
        clause,
        decision_change,
        allow_thresholds=allow_thresholds,
        error="AI response claims an unavailable decision score change",
    )


def _validate_movement_value_claims(
    clause: str,
    analysis_input: _SentimentAnalysisInput,
    *,
    allow_thresholds: bool,
) -> None:
    score_change_spans = _score_change_spans(clause)
    index_factor_spans = tuple(
        factor_match.span()
        for factor_name, pattern in _FACTOR_RAW_CLAIM_PATTERNS
        if factor_name == "index_move_5d"
        for factor_match in pattern.finditer(clause)
    )
    for match in _MOVEMENT_VALUE_CLAIM_PATTERN.finditer(clause):
        if _match_within_spans(match, score_change_spans):
            continue
        if any(pattern.search(clause) for _, pattern in _MARKET_FIELD_CLAIM_PATTERNS):
            continue
        if allow_thresholds and _number_is_threshold(clause, match):
            continue
        if _match_within_spans(match, index_factor_spans):
            continue
        movement_prefix = _movement_local_prefix(clause, match.start(), score_change_spans)
        subject = _movement_subject(movement_prefix)
        if _GENERIC_METRIC_ENTITY_PATTERN.fullmatch(subject):
            continue
        has_five_day_horizon = bool(
            _FIVE_DAY_SUFFIX_PATTERN.search(movement_prefix.rstrip("的 ").strip())
        )
        names_sector = any(item.name in subject for item in analysis_input.main_sectors.items)
        if not has_five_day_horizon or names_sector:
            raise ValueError("AI response uses an unavailable movement horizon")

        claimed_value = _normalized_claim_number(match)
        if _NEGATIVE_MOVEMENT_PATTERN.search(match.group("movement")):
            claimed_value = -abs(claimed_value)
        else:
            claimed_value = abs(claimed_value)
        expected_value = Decimal(str(analysis_input.percentile.factors.index_move_5d.raw_value))
        if claimed_value != expected_value:
            raise ValueError("AI response changes the five-day index movement")


def _validate_sector_strength_claims(
    clause: str,
    analysis_input: _SentimentAnalysisInput,
    *,
    allow_thresholds: bool,
) -> None:
    for match in _SECTOR_STRENGTH_CLAIM_PATTERN.finditer(clause):
        if allow_thresholds and _number_is_threshold(clause, match):
            continue

        prefix = clause[: match.start()].strip().rstrip("的 ")
        sector = next(
            (item for item in analysis_input.main_sectors.items if prefix.endswith(item.name)),
            None,
        )
        if sector is None and not prefix and len(analysis_input.main_sectors.items) == 1:
            sector = analysis_input.main_sectors.items[0]
        expected_value = (
            Decimal(str(sector.strength_score))
            if sector is not None and analysis_input.main_sectors.status == "available"
            else None
        )
        if expected_value is None or _normalized_claim_number(match) != expected_value:
            raise ValueError("AI response changes a sector strength score")


def _market_field_value(
    field_name: str,
    clause: str,
    analysis_input: _SentimentAnalysisInput,
) -> Decimal | None:
    sector = next((item for item in analysis_input.main_sectors.items if item.name in clause), None)
    if sector is not None and field_name in {
        "limit_up_count",
        "break_board_count",
        "max_consecutive_boards",
    }:
        if analysis_input.main_sectors.status == "unavailable":
            return None
        return Decimal(str(getattr(sector, field_name)))

    if analysis_input.market.status == "unavailable":
        return None
    if field_name in {"advance_count", "decline_count"}:
        value = getattr(analysis_input.market.breadth, field_name)
    elif field_name in {"limit_up_count", "limit_down_count", "break_board_count"}:
        value = getattr(analysis_input.market.limits, field_name)
    elif field_name == "max_consecutive_boards":
        value = analysis_input.market.boards.max_consecutive_boards
    else:
        value = getattr(analysis_input.market, field_name)
    return _decimal_or_none(value)


def _validate_claim_matches(
    pattern: re.Pattern[str],
    clause: str,
    expected_value: Decimal | None,
    *,
    allow_thresholds: bool,
    error: str,
    signed_change: bool = False,
) -> None:
    for match in pattern.finditer(clause):
        if allow_thresholds and _number_is_threshold(clause, match):
            continue
        claimed_value = _normalized_claim_number(match)
        if signed_change:
            claimed_value = _signed_claim_value(match, claimed_value)
        if expected_value is None or claimed_value != expected_value:
            raise ValueError(error)


def _validate_movement_subjects(text: str, sector_names: Sequence[str]) -> None:
    factor_movement_patterns = (
        *(pattern for _name, pattern in _FACTOR_SCORE_CLAIM_PATTERNS),
        *(pattern for _name, pattern in _FACTOR_RAW_CLAIM_PATTERNS),
    )
    for clause in _CLAUSE_SPLIT_PATTERN.split(text):
        score_change_spans = _score_change_spans(clause)
        factor_movement_spans = tuple(
            match.span()
            for pattern in factor_movement_patterns
            for match in pattern.finditer(clause)
        )
        for match in _MOVEMENT_PATTERN.finditer(clause):
            if _match_within_spans(match, score_change_spans) or _match_within_spans(
                match,
                factor_movement_spans,
            ):
                continue
            subject = _movement_subject(
                _movement_local_prefix(clause, match.start(), score_change_spans)
            )
            if subject and not _is_allowed_entity_reference(subject, sector_names):
                raise ValueError("AI response names a non-aggregate movement subject")


def _score_change_spans(clause: str) -> tuple[tuple[int, int], ...]:
    return tuple(
        match.span()
        for pattern in (
            _SCORE_CHANGE_1D_CLAIM_PATTERN,
            _SCORE_CHANGE_5D_CLAIM_PATTERN,
            _DECISION_SCORE_CHANGE_CLAIM_PATTERN,
        )
        for match in pattern.finditer(clause)
    )


def _match_within_spans(
    match: re.Match[str],
    spans: Sequence[tuple[int, int]],
) -> bool:
    return any(start <= match.start() and match.end() <= end for start, end in spans)


def _movement_local_prefix(
    clause: str,
    movement_start: int,
    score_change_spans: Sequence[tuple[int, int]],
) -> str:
    prior_end = max(
        (end for _start, end in score_change_spans if end <= movement_start),
        default=0,
    )
    return _MOVEMENT_CONNECTOR_PREFIX_PATTERN.sub("", clause[prior_end:movement_start])


def _movement_subject(prefix: str) -> str:
    subject = _SUBJECT_QUALIFIER_PATTERN.sub("", prefix).strip()
    subject = re.sub(r"^(?:近|过去)?\s*\d+(?:\.\d+)?\s*(?:日|周|月|年)(?:内)?\s*", "", subject)
    subject = _FIVE_DAY_SUFFIX_PATTERN.sub("", subject).strip()
    return subject.rstrip("的 ").strip()


def _is_allowed_entity_reference(text: str, sector_names: Sequence[str]) -> bool:
    reference = text.strip().rstrip("的 ")
    reference = re.split(
        r"(?:为|是|呈|处于|位于|维持|能否|是否|高于|低于|达到|超过)",
        reference,
        maxsplit=1,
    )[0]
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
    has_named_sector = any(name in clause for name in sector_names)
    has_sector_metric = has_named_sector and bool(_SECTOR_LIMIT_METRIC_PATTERN.search(clause))
    if _MARKET_METRIC_CLAIM_PATTERN.search(clause) and not has_sector_metric and not allow_threshold:
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
    factual_text = _NUMBERED_INDEX_ENTITY_PATTERN.sub("", clause)
    for date in canonical_dates:
        factual_text = factual_text.replace(date, "")

    numeric_matches = list(_NUMERIC_CLAIM_PATTERN.finditer(factual_text))
    if numeric_matches and _MARKET_METRIC_CLAIM_PATTERN.search(factual_text):
        if not any(pattern.search(clause) for _, pattern in _MARKET_FIELD_CLAIM_PATTERNS):
            raise ValueError("AI response contains an ungrounded market metric")

    for match in _CHINESE_NUMERIC_CLAIM_PATTERN.finditer(factual_text):
        if allow_thresholds and _number_is_threshold(factual_text, match):
            continue
        raise ValueError("AI response contains an ungrounded Chinese-number claim")

    for match in numeric_matches:
        if _normalized_claim_number(match) in canonical_numbers:
            continue
        if allow_thresholds and _number_is_threshold(factual_text, match):
            continue
        raise ValueError("AI response contains an ungrounded factual number")


def _is_threshold_clause(clause: str) -> bool:
    matches = list(_NUMERIC_CLAIM_PATTERN.finditer(clause))
    return bool(matches) and all(_number_is_threshold(clause, match) for match in matches)


def _number_is_threshold(clause: str, match: re.Match[str]) -> bool:
    number_start = match.start("number")
    number_end = match.end("number")
    previous_end = 0
    next_start = len(clause)
    for candidate in _NUMERIC_CLAIM_PATTERN.finditer(clause):
        if candidate.end() <= number_start:
            previous_end = candidate.end()
        elif candidate.start() > number_start:
            next_start = candidate.start()
            break

    prefix = clause[previous_end:number_start]
    suffix = clause[number_end:next_start]
    return bool(_THRESHOLD_PREFIX_PATTERN.search(prefix) or _THRESHOLD_SUFFIX_PATTERN.search(suffix))


def _is_historical_level_claim(text: str, match: re.Match[str]) -> bool:
    clause_start = max(text.rfind(delimiter, 0, match.start()) for delimiter in "，,。；;！？!?\n") + 1
    prefix = text[clause_start : match.start()]
    return bool(_HISTORICAL_LEVEL_CUE_PATTERN.search(prefix)) and not bool(
        _CURRENT_CUE_PATTERN.search(prefix)
    )


def _prior_level_for_claim(
    text: str,
    match: re.Match[str],
    analysis_input: _SentimentAnalysisInput,
) -> str | None:
    clause_start = max(text.rfind(delimiter, 0, match.start()) for delimiter in "，,。；;！？!?\n") + 1
    prefix = text[clause_start : match.start()]
    if _FIVE_DAY_LEVEL_CUE_PATTERN.search(prefix):
        return analysis_input.zone_transitions.five_day.from_
    if _ONE_DAY_LEVEL_CUE_PATTERN.search(prefix):
        return analysis_input.zone_transitions.one_day.from_
    return None


def _canonical_level(raw_level: str) -> str:
    normalized = raw_level.lower()
    if normalized in _LEVEL_ALIASES:
        return _LEVEL_ALIASES[normalized]
    for suffix in ("区域", "区间", "水平", "层级", "区"):
        normalized = normalized.removesuffix(suffix)
    return _LEVEL_ALIASES.get(normalized, normalized)


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


def _signed_claim_value(match: re.Match[str], value: Decimal) -> Decimal:
    direction = match.groupdict().get("direction")
    if direction in {"下降", "减少"}:
        return -abs(value)
    if direction in {"上升", "增加"}:
        return abs(value)
    return value


def _weight_value(match: re.Match[str]) -> Decimal:
    value = _decimal(match.group("number"))
    return value / Decimal("100") if match.group("percent") else value


def _decimal(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def _decimal_or_none(value: int | float | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


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
    if isinstance(error, httpx.TimeoutException):
        return "TimeoutError: AI provider request timed out"
    if isinstance(error, ValidationError):
        return "ValidationError: AI response does not match the required schema"
    if isinstance(error, ValueError):
        return "ValueError: AI response could not be parsed"
    if isinstance(error, httpx.HTTPError):
        return f"{type(error).__name__}: AI provider request failed"
    return f"{type(error).__name__ if error else 'RuntimeError'}: AI generation failed"
