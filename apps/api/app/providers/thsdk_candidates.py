from __future__ import annotations

import re
from typing import Any

from app.models import StrongStockCandidate, StrongStockDataUnavailable
from app.models import StrongStockSourceStatus


class ThsdkCandidateProvider:
    source_name = "THSDK 问财"

    def __init__(self, client_factory: object | None = None) -> None:
        self.client_factory = client_factory

    @classmethod
    def from_installed_package(cls) -> "ThsdkCandidateProvider":
        try:
            from thsdk import THS
        except ModuleNotFoundError:
            return cls(client_factory=None)
        return cls(client_factory=THS)

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        if self.client_factory is None:
            raise StrongStockDataUnavailable("THSDK 未安装，无法查询20日内涨停候选池")
        query = "20日内有过涨停，非ST，A股"
        with self.client_factory() as ths:
            response = ths.wencai_nlp(query)
        if not getattr(response, "success", False):
            raise StrongStockDataUnavailable(str(getattr(response, "error", "") or "THSDK 问财返回失败"))
        return parse_thsdk_candidate_rows(getattr(response, "data", None) or [])

    def status(self) -> StrongStockSourceStatus:
        if self.client_factory is None:
            return StrongStockSourceStatus(
                source=self.source_name,
                status="failed",
                detail="THSDK 未安装，无法查询20日内涨停候选池",
            )
        return StrongStockSourceStatus(
            source=self.source_name,
            status="success",
            detail="THSDK 已安装",
        )


def parse_thsdk_candidate_rows(rows: object) -> list[StrongStockCandidate]:
    if not isinstance(rows, list):
        return []
    candidates: list[StrongStockCandidate] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _text_value(row, "股票简称", "名称", "name")
        code = _text_value(row, "股票代码", "代码", "code")
        if not name or not code or "ST" in name.upper() or not _has_limit_up_evidence(row):
            continue
        symbol = normalize_symbol(code)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        candidates.append(
            StrongStockCandidate(
                symbol=symbol,
                name=name,
                limit_up_evidence=["20日内涨停"],
                board_note=_limit_up_note(row),
            )
        )
    return candidates


def normalize_symbol(value: str) -> str:
    code = value.strip().upper()
    if "." in code:
        raw, exchange = code.split(".", 1)
        return f"{raw.zfill(6)}.{exchange}"
    code = re.sub(r"\D", "", code)
    if len(code) != 6:
        return ""
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("8", "4")):
        return f"{code}.BJ"
    return f"{code}.SZ"


def _has_limit_up_evidence(row: dict[str, Any]) -> bool:
    for key, value in row.items():
        if "涨停" not in str(key):
            continue
        if value in (None, "", 0, "0", "0.0"):
            continue
        return True
    return False


def _text_value(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _limit_up_note(row: dict[str, Any]) -> str | None:
    for key, value in row.items():
        if "涨停" in str(key) and value not in (None, ""):
            return f"{key}: {value}"
    return None
