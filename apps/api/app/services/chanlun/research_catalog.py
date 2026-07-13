from __future__ import annotations

import hashlib
import json
import re
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from app.models import (
    CZSC_CATALOG_VERSION,
    ChanlunPeriod,
    CzscEvidenceDirection,
    CzscEvidenceFamily,
    CzscEvidenceRole,
    CzscSignalEvidence,
    FrozenDict,
)


CATALOG_PATH = Path(__file__).with_name("research_catalog.json")
APPROVED_CATALOG_ENTRIES: dict[str, dict[str, Any]] = {
    "trend.bi-status": {
        "name": "cxt_bi_status_V230101",
        "periods": ("1d", "60m", "30m"),
        "pairs": None,
        "params": {},
        "key_template": "{freq}_D1_表里关系V230101",
        "role": "primary",
    },
    "trend.bi-base": {
        "name": "cxt_bi_base_V230228",
        "periods": ("1d", "60m", "30m"),
        "pairs": None,
        "params": {"bi_init_length": 9},
        "key_template": "{freq}_D0BL9_V230228",
        "role": "primary",
    },
    "buy2.overlap": {
        "name": "cxt_second_bs_V240524",
        "periods": ("5m",),
        "pairs": None,
        "params": {"di": 1, "w": 9, "t": 2},
        "key_template": "{freq}_D1W9T2_第二买卖点V240524",
        "role": "primary",
    },
    "buy2.ma-confirm": {
        "name": "cxt_second_bs_V230320",
        "periods": ("5m",),
        "pairs": None,
        "params": {"di": 1, "ma_type": "SMA", "timeperiod": 21},
        "key_template": "{freq}_D1#SMA#21_BS2辅助V230320",
        "role": "confirmation",
    },
    "buy3.structure": {
        "name": "cxt_third_buy_V230228",
        "periods": ("5m",),
        "pairs": None,
        "params": {"di": 1},
        "key_template": "{freq}_D1_三买辅助V230228",
        "role": "primary",
    },
    "buy3.ma-confirm": {
        "name": "cxt_third_bs_V230319",
        "periods": ("5m",),
        "pairs": None,
        "params": {"di": 1, "ma_type": "SMA", "timeperiod": 34},
        "key_template": "{freq}_D1#SMA#34_BS3辅助V230319",
        "role": "confirmation",
    },
    "zone.resonance": {
        "name": "cxt_zhong_shu_gong_zhen_V221221",
        "periods": None,
        "pairs": (("1d", "60m"), ("60m", "30m")),
        "params": {},
        "key_template": "{freq1}_{freq2}_中枢共振V221221",
        "role": "primary",
    },
    "risk.macd-divergence": {
        "name": "tas_macd_bc_V240307",
        "periods": ("1d", "60m", "30m", "5m"),
        "pairs": None,
        "params": {"di": 1, "n": 20},
        "key_template": "{freq}_D1N20柱子背驰_BS辅助V240307",
        "role": "risk",
    },
}
VALUE_MAP: dict[
    tuple[str, str],
    tuple[CzscEvidenceFamily, CzscEvidenceDirection, CzscEvidenceRole],
] = {
    ("buy2.overlap", "二买"): ("second_buy", "bullish", "primary"),
    ("buy2.overlap", "二卖"): ("sell_risk", "bearish", "risk"),
    ("buy2.ma-confirm", "二买"): ("second_buy", "bullish", "confirmation"),
    ("buy2.ma-confirm", "二卖"): ("sell_risk", "bearish", "risk"),
    ("buy3.structure", "三买"): ("third_buy", "bullish", "primary"),
    ("buy3.ma-confirm", "三买"): ("third_buy", "bullish", "confirmation"),
    ("buy3.ma-confirm", "三卖"): ("sell_risk", "bearish", "risk"),
    ("risk.macd-divergence", "顶背驰"): ("divergence", "bearish", "risk"),
    ("risk.macd-divergence", "底背驰"): ("divergence", "bullish", "observation"),
    ("zone.resonance", "看多"): ("zone_confluence", "bullish", "primary"),
    ("zone.resonance", "看空"): ("sell_risk", "bearish", "risk"),
}
_PERIOD_LABELS: dict[ChanlunPeriod, str] = {
    "1d": "日线",
    "60m": "60分钟",
    "30m": "30分钟",
    "5m": "5分钟",
}
_ACTIVE_V2_VALUES: dict[str, frozenset[str]] = {
    "trend.bi-status": frozenset({"延伸", "顶分", "底分"}),
    "trend.bi-base": frozenset({"中继", "转折"}),
    "buy2.overlap": frozenset({"任意"}),
    "buy2.ma-confirm": frozenset({"任意"}),
    "buy3.structure": frozenset({"6笔", "8笔", "10笔", "12笔", "14笔"}),
    "buy3.ma-confirm": frozenset(
        {"均线新高", "均线新低", "均线底分", "均线顶分", "均线否定"}
    ),
    "zone.resonance": frozenset({"任意"}),
}


class ResearchCatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_id: str
    name: str
    periods: tuple[ChanlunPeriod, ...] | None = None
    pairs: tuple[tuple[ChanlunPeriod, ChanlunPeriod], ...] | None = None
    params: Mapping[str, Any] = Field(default_factory=dict, frozen=True)
    key_template: str
    role: CzscEvidenceRole

    @field_validator("params", mode="after")
    @classmethod
    def _freeze_params(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return FrozenDict(value)

    @field_serializer("params")
    def _serialize_params(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return FrozenDict(value).to_dict()

    @model_validator(mode="after")
    def _validate_identity_and_periods(self) -> ResearchCatalogEntry:
        if bool(self.periods) == bool(self.pairs):
            raise ValueError("catalog entry must define exactly one non-empty period source")
        expected = APPROVED_CATALOG_ENTRIES.get(self.catalog_id)
        actual = {
            "name": self.name,
            "periods": self.periods,
            "pairs": self.pairs,
            "params": dict(self.params),
            "key_template": self.key_template,
            "role": self.role,
        }
        if expected != actual:
            raise ValueError("catalog entry does not match the approved fixed definition")
        return self


class ExpandedResearchSignalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_id: str
    name: str
    period: ChanlunPeriod | None = None
    higher_period: ChanlunPeriod | None = None
    lower_period: ChanlunPeriod | None = None
    params: Mapping[str, Any] = Field(default_factory=dict, frozen=True)
    key_template: str
    role: CzscEvidenceRole

    @field_validator("params", mode="after")
    @classmethod
    def _freeze_params(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return FrozenDict(value)

    @field_serializer("params")
    def _serialize_params(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return FrozenDict(value).to_dict()

    @property
    def id(self) -> str:
        if self.period is not None:
            return f"{self.catalog_id}:{self.period}"
        return f"{self.catalog_id}:{self.higher_period}:{self.lower_period}"


class ResearchCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_version: str
    entries: tuple[ResearchCatalogEntry, ...]

    @property
    def version(self) -> str:
        return self.catalog_version

    def expanded_configs(self) -> tuple[ExpandedResearchSignalConfig, ...]:
        expanded: list[ExpandedResearchSignalConfig] = []
        for entry in self.entries:
            for period in entry.periods or ():
                expanded.append(
                    ExpandedResearchSignalConfig(
                        catalog_id=entry.catalog_id,
                        name=entry.name,
                        period=period,
                        params=entry.params,
                        key_template=entry.key_template,
                        role=entry.role,
                    )
                )
            for higher_period, lower_period in entry.pairs or ():
                expanded.append(
                    ExpandedResearchSignalConfig(
                        catalog_id=entry.catalog_id,
                        name=entry.name,
                        higher_period=higher_period,
                        lower_period=lower_period,
                        params=entry.params,
                        key_template=entry.key_template,
                        role=entry.role,
                    )
                )
        return tuple(expanded)

    @cached_property
    def expanded_index(
        self,
    ) -> dict[
        tuple[str, ChanlunPeriod | None, ChanlunPeriod | None, ChanlunPeriod | None],
        ExpandedResearchSignalConfig,
    ]:
        return {
            (item.catalog_id, item.period, item.higher_period, item.lower_period): item
            for item in self.expanded_configs()
        }

    @model_validator(mode="after")
    def _validate_catalog(self) -> ResearchCatalog:
        if self.catalog_version != CZSC_CATALOG_VERSION:
            raise ValueError(f"unsupported catalog version: {self.catalog_version}")
        if not self.entries:
            raise ValueError("catalog entries cannot be empty")
        catalog_ids = [entry.catalog_id for entry in self.entries]
        if len(catalog_ids) != len(set(catalog_ids)):
            raise ValueError("catalog contains duplicate catalog IDs")
        if set(catalog_ids) != set(APPROVED_CATALOG_ENTRIES):
            raise ValueError("catalog must contain every approved fixed entry")
        expanded_ids = [item.id for item in self.expanded_configs()]
        if len(expanded_ids) != len(set(expanded_ids)):
            raise ValueError("catalog contains duplicate expanded IDs")
        return self


@lru_cache(maxsize=16)
def load_research_catalog(path: Path | None = None) -> ResearchCatalog:
    catalog_path = path or CATALOG_PATH
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    return ResearchCatalog.model_validate(payload)


def map_raw_state(
    *,
    symbol: str,
    catalog_id: str,
    value_fields: Mapping[str, object],
    raw_key: str,
    raw_value: str,
    occurred_at: str,
    last_closed_bar_at: str,
    input_snapshot_id: str,
    engine_version: str,
    period: ChanlunPeriod | None = None,
    higher_period: ChanlunPeriod | None = None,
    lower_period: ChanlunPeriod | None = None,
    catalog: ResearchCatalog | None = None,
) -> CzscSignalEvidence | None:
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol cannot be empty")
    config = _resolve_expanded_config(
        catalog_id=catalog_id,
        period=period,
        higher_period=higher_period,
        lower_period=lower_period,
        catalog=catalog,
    )
    v1, v2, v3, signal_score = _validate_value_fields(value_fields)
    if v1 == "其他":
        return None

    if catalog_id in {"trend.bi-status", "trend.bi-base"} and v1 in {"向上", "向下"}:
        mapped: tuple[CzscEvidenceFamily, CzscEvidenceDirection, CzscEvidenceRole] = (
            "trend_context",
            "bullish" if v1 == "向上" else "bearish",
            "primary",
        )
    else:
        mapped = VALUE_MAP.get((catalog_id, v1))
        if mapped is None:
            raise ValueError(f"unrecognized active value for {catalog_id}: {v1}")
    _validate_active_value(catalog_id=catalog_id, v2=v2, v3=v3)

    family, direction, role = mapped
    scope = period or f"{higher_period}-{lower_period}"
    params = {
        **dict(config.params),
        "v1": v1,
        "v2": v2,
        "v3": v3,
        "score": signal_score,
    }
    identity = {
        "symbol": normalized_symbol,
        "catalog_version": CZSC_CATALOG_VERSION,
        "catalog_id": catalog_id,
        "scope": scope,
        "params": params,
        "occurred_at": occurred_at,
    }
    identity_hash = hashlib.sha256(
        json.dumps(
            identity,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    return CzscSignalEvidence(
        id=f"{normalized_symbol}:{catalog_id}.{scope}:{occurred_at}:{v1}:{identity_hash}",
        catalog_id=catalog_id,
        family=family,
        role=role,
        direction=direction,
        period=period,
        higher_period=higher_period,
        lower_period=lower_period,
        occurred_at=occurred_at,
        last_closed_bar_at=last_closed_bar_at,
        signal_name=config.name,
        params=params,
        raw_key=raw_key,
        raw_value=raw_value,
        reason=_evidence_reason(
            catalog_id=catalog_id,
            v1=v1,
            v2=v2,
            period=period,
            higher_period=higher_period,
            lower_period=lower_period,
        ),
        input_snapshot_id=input_snapshot_id,
        engine_version=engine_version,
    )


def _resolve_expanded_config(
    *,
    catalog_id: str,
    period: ChanlunPeriod | None,
    higher_period: ChanlunPeriod | None,
    lower_period: ChanlunPeriod | None,
    catalog: ResearchCatalog | None,
) -> ExpandedResearchSignalConfig:
    if period is not None and (higher_period is not None or lower_period is not None):
        raise ValueError("single-period signal cannot include a period pair")
    if period is None and (higher_period is None or lower_period is None):
        raise ValueError("multi-period signal requires both higher and lower periods")

    key = (catalog_id, period, higher_period, lower_period)
    index = _expanded_index(catalog) if catalog is not None else _default_expanded_index()
    try:
        return index[key]
    except KeyError as exc:
        raise ValueError(f"catalog signal scope is not approved: {catalog_id}") from exc


def _expanded_index(
    catalog: ResearchCatalog,
) -> dict[
    tuple[str, ChanlunPeriod | None, ChanlunPeriod | None, ChanlunPeriod | None],
    ExpandedResearchSignalConfig,
]:
    return catalog.expanded_index


@lru_cache(maxsize=1)
def _default_expanded_index() -> dict[
    tuple[str, ChanlunPeriod | None, ChanlunPeriod | None, ChanlunPeriod | None],
    ExpandedResearchSignalConfig,
]:
    return _expanded_index(load_research_catalog())


def _validate_value_fields(value_fields: Mapping[str, object]) -> tuple[str, str, str, int]:
    if set(value_fields) != {"v1", "v2", "v3", "score"}:
        raise ValueError("signal value fields must contain exactly v1, v2, v3, and score")
    v1 = value_fields.get("v1")
    v2 = value_fields.get("v2")
    v3 = value_fields.get("v3")
    score = value_fields.get("score")
    if not all(isinstance(value, str) for value in (v1, v2, v3)):
        raise ValueError("signal v1, v2, and v3 must be strings")
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
        raise ValueError("signal score must be an integer between 0 and 100")
    return v1, v2, v3, score


def _validate_active_value(*, catalog_id: str, v2: str, v3: str) -> None:
    if v3 != "任意":
        raise ValueError(f"unexpected v3 for {catalog_id}: {v3}")
    if catalog_id == "risk.macd-divergence":
        if re.fullmatch(r"第[1-9]\d*次", v2) is None:
            raise ValueError(f"unexpected v2 for {catalog_id}: {v2}")
        return
    if v2 not in _ACTIVE_V2_VALUES[catalog_id]:
        raise ValueError(f"unexpected v2 for {catalog_id}: {v2}")


def _evidence_reason(
    *,
    catalog_id: str,
    v1: str,
    v2: str,
    period: ChanlunPeriod | None,
    higher_period: ChanlunPeriod | None,
    lower_period: ChanlunPeriod | None,
) -> str:
    if period is not None:
        label = _PERIOD_LABELS[period]
    else:
        assert higher_period is not None and lower_period is not None
        label = f"{_PERIOD_LABELS[higher_period]}与{_PERIOD_LABELS[lower_period]}"

    if catalog_id == "trend.bi-status":
        return f"{label}笔状态{v1}（{v2}）"
    if catalog_id == "trend.bi-base":
        return f"{label}笔方向{v1}（{v2}）"
    if catalog_id in {"buy2.overlap", "buy3.structure"}:
        return f"{label}结构出现{v1}"
    if catalog_id in {"buy2.ma-confirm", "buy3.ma-confirm"}:
        return f"{label}均线确认{v1}"
    if catalog_id == "zone.resonance":
        return f"{label}中枢{v1}共振"
    if catalog_id == "risk.macd-divergence":
        return f"{label}出现{v1}"
    raise ValueError(f"cannot explain catalog signal: {catalog_id}")
