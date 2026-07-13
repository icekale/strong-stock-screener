from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from app.models import (
    CZSC_CATALOG_VERSION,
    ChanlunPeriod,
    CzscEvidenceRole,
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


def load_research_catalog(path: Path | None = None) -> ResearchCatalog:
    catalog_path = path or CATALOG_PATH
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    return ResearchCatalog.model_validate(payload)
