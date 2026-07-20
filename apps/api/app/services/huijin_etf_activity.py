from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType

from app.models import (
    EtfActivityDirection,
    EtfHolderPosition,
    HuijinEtfActivityItem,
    HuijinEtfBaseline,
    HuijinEtfRole,
    HuijinEtfValidationGroup,
)


POOL_VERSION = "huijin-public-v1"
MODEL_VERSION = "huijin-public-rule-v1"
TENFOLD_BASELINE_PCT = 0.1
_HUIJIN_LEGAL_ENTITIES = frozenset({
    "中央汇金投资有限责任公司",
    "中央汇金资产管理有限责任公司",
})


@dataclass(frozen=True)
class EtfDefinition:
    name: str
    index_name: str
    role: HuijinEtfRole
    paired_symbol: str | None = None


CORE_ETFS: Mapping[str, EtfDefinition] = MappingProxyType({
    "510050.SH": EtfDefinition("上证50ETF华夏", "上证50", "core"),
    "510300.SH": EtfDefinition("沪深300ETF华泰柏瑞", "沪深300", "core", "159919.SZ"),
    "510500.SH": EtfDefinition("中证500ETF南方", "中证500", "core", "159922.SZ"),
    "512100.SH": EtfDefinition("中证1000ETF南方", "中证1000", "core", "159845.SZ"),
    "159915.SZ": EtfDefinition("创业板ETF易方达", "创业板", "core"),
    "510230.SH": EtfDefinition("金融ETF国泰", "金融", "core"),
    "588080.SH": EtfDefinition("科创50ETF易方达", "科创50", "core"),
})

VALIDATION_ETFS: Mapping[str, EtfDefinition] = MappingProxyType({
    "159919.SZ": EtfDefinition("沪深300ETF嘉实", "沪深300", "validator", "510300.SH"),
    "159922.SZ": EtfDefinition("中证500ETF嘉实", "中证500", "validator", "510500.SH"),
    "159845.SZ": EtfDefinition("中证1000ETF华夏", "中证1000", "validator", "512100.SH"),
})

ALL_ETFS: Mapping[str, EtfDefinition] = MappingProxyType(
    {**CORE_ETFS, **VALIDATION_ETFS}
)


def build_baselines(positions: list[EtfHolderPosition]) -> list[HuijinEtfBaseline]:
    entity_disclosures: dict[tuple[str, str, str], tuple[float, float]] = {}
    conflicting_groups: set[tuple[str, str]] = set()
    for position in positions:
        if (
            position.symbol not in ALL_ETFS
            or position.entity_name not in _HUIJIN_LEGAL_ENTITIES
        ):
            continue
        shares = position.shares
        holding_pct = position.holding_pct
        if (
            shares is None
            or holding_pct is None
            or not isfinite(shares)
            or not isfinite(holding_pct)
            or shares <= 0
            or holding_pct <= 0
            or holding_pct > 100
        ):
            continue
        group_key = (position.report_period, position.symbol)
        disclosure_key = (*group_key, position.entity_name)
        disclosure = (shares, holding_pct)
        existing = entity_disclosures.get(disclosure_key)
        if existing is None:
            entity_disclosures[disclosure_key] = disclosure
        elif existing != disclosure:
            conflicting_groups.add(group_key)

    grouped: dict[tuple[str, str], tuple[float, float]] = {}
    for disclosure_key, disclosure in sorted(entity_disclosures.items()):
        group_key = disclosure_key[:2]
        if group_key in conflicting_groups:
            continue
        shares, holding_pct = grouped.get(group_key, (0, 0))
        grouped[group_key] = (
            shares + disclosure[0],
            holding_pct + disclosure[1],
        )

    baselines = []
    report_periods = sorted({report_period for report_period, _ in grouped})
    for report_period in report_periods:
        for symbol, definition in ALL_ETFS.items():
            shares, holding_pct = grouped.get((report_period, symbol), (0, 0))
            if (
                not isfinite(shares)
                or not isfinite(holding_pct)
                or shares <= 0
                or holding_pct <= 0
                or holding_pct > 100
            ):
                continue
            baseline_total_shares = shares / (holding_pct / 100)
            if not isfinite(baseline_total_shares) or baseline_total_shares <= 0:
                continue
            baselines.append(
                HuijinEtfBaseline(
                    baseline_id=f"{report_period}:{POOL_VERSION}:{symbol}",
                    pool_version=POOL_VERSION,
                    symbol=symbol,
                    name=definition.name,
                    index_name=definition.index_name,
                    role=definition.role,
                    paired_symbol=definition.paired_symbol,
                    report_period=report_period,
                    baseline_total_shares=baseline_total_shares,
                    confirmed_huijin_shares=shares,
                    confirmed_huijin_holding_pct=holding_pct,
                    source_kind="derived",
                    source="基金持有人披露持仓与比例推导",
                )
            )
    return baselines


def calculate_activity(
    *,
    symbol: str,
    name: str,
    index_name: str,
    role: HuijinEtfRole,
    trade_date: str,
    total_shares: float | None,
    previous_total_shares: float | None,
    baseline: HuijinEtfBaseline | None,
) -> HuijinEtfActivityItem:
    share_delta = None
    daily_change_pct = None
    baseline_change_pct = None
    multiple = None
    direction: EtfActivityDirection = "unknown"

    if total_shares is not None and previous_total_shares is not None and previous_total_shares > 0:
        share_delta = total_shares - previous_total_shares
        daily_change_pct = share_delta / previous_total_shares * 100
        direction = _direction(share_delta)
        if baseline is not None:
            baseline_change_pct = share_delta / baseline.baseline_total_shares * 100
            multiple = abs(baseline_change_pct) / TENFOLD_BASELINE_PCT

    cumulative_baseline_change_pct = None
    if total_shares is not None and baseline is not None:
        cumulative_baseline_change_pct = (
            (total_shares - baseline.baseline_total_shares)
            / baseline.baseline_total_shares
            * 100
        )

    definition = ALL_ETFS.get(symbol)
    return HuijinEtfActivityItem(
        symbol=symbol,
        name=name,
        index_name=index_name,
        role=role,
        paired_symbol=definition.paired_symbol if definition is not None else None,
        trade_date=trade_date,
        total_shares=total_shares,
        previous_total_shares=previous_total_shares,
        share_delta=share_delta,
        daily_change_pct=daily_change_pct,
        baseline_change_pct=baseline_change_pct,
        cumulative_baseline_change_pct=cumulative_baseline_change_pct,
        multiple=multiple,
        direction=direction,
        is_tenfold=multiple is not None and multiple >= 10,
        report_period=baseline.report_period if baseline is not None else None,
        baseline_total_shares=baseline.baseline_total_shares if baseline is not None else None,
        confirmed_huijin_shares=baseline.confirmed_huijin_shares if baseline is not None else None,
        confirmed_huijin_holding_pct=(
            baseline.confirmed_huijin_holding_pct if baseline is not None else None
        ),
        baseline_source_kind=baseline.source_kind if baseline is not None else None,
    )


def validate_pair(
    core: HuijinEtfActivityItem,
    validator: HuijinEtfActivityItem,
) -> HuijinEtfValidationGroup:
    if "unknown" in {core.direction, validator.direction}:
        state = "incomplete"
    elif core.direction == validator.direction == "increase":
        state = "confirmed_increase"
    elif core.direction == validator.direction == "decrease":
        state = "confirmed_decrease"
    else:
        state = "divergent"

    if state in {"confirmed_increase", "confirmed_decrease"}:
        conservative_daily_change_pct = _smaller_absolute(
            core.daily_change_pct, validator.daily_change_pct
        )
        conservative_baseline_change_pct = _smaller_absolute(
            core.baseline_change_pct, validator.baseline_change_pct
        )
        conservative_multiple = (
            min(core.multiple, validator.multiple)
            if core.multiple is not None and validator.multiple is not None
            else None
        )
    else:
        conservative_daily_change_pct = None
        conservative_baseline_change_pct = None
        conservative_multiple = None

    return HuijinEtfValidationGroup(
        index_name=core.index_name,
        core_symbol=core.symbol,
        validator_symbol=validator.symbol,
        state=state,
        conservative_daily_change_pct=conservative_daily_change_pct,
        conservative_baseline_change_pct=conservative_baseline_change_pct,
        conservative_multiple=conservative_multiple,
    )


def _direction(share_delta: float) -> EtfActivityDirection:
    if share_delta > 0:
        return "increase"
    if share_delta < 0:
        return "decrease"
    return "flat"


def _smaller_absolute(first: float | None, second: float | None) -> float | None:
    if first is None or second is None:
        return None
    return min((first, second), key=abs)
