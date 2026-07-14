from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from app.models import StrongStockCandidate


@dataclass(frozen=True)
class ResearchCandidateRecord:
    candidate: StrongStockCandidate
    last_limit_up_date: str
    limit_up_hits_20d: int
    decision_date: str


def reconstruct_candidates(
    rows: Iterable[dict[str, object]],
    *,
    trade_date: str,
) -> list[ResearchCandidateRecord]:
    decision = _parse_date(trade_date)
    usable_rows = [row for row in rows if _row_date(row) is not None and _row_date(row) <= decision]
    sessions = sorted({_row_date(row) for row in usable_rows if _row_date(row) is not None})[-20:]
    session_set = set(sessions)
    by_code: dict[str, list[dict[str, object]]] = {}
    for row in usable_rows:
        row_date = _row_date(row)
        code = _raw_code(row.get("code"))
        if row_date in session_set and code:
            by_code.setdefault(code, []).append(row)

    records: list[ResearchCandidateRecord] = []
    for code, code_rows in by_code.items():
        latest = max(code_rows, key=lambda row: _row_date(row) or date.min)
        name = str(latest.get("name") or code)
        if "ST" in name.upper() or not _is_common_a_share_code(code):
            continue
        limit_dates = [
            _row_date(row)
            for row in code_rows
            if _is_limit_up(row, code)
        ]
        if not limit_dates:
            continue
        records.append(
            ResearchCandidateRecord(
                candidate=StrongStockCandidate(
                    symbol=_symbol(code),
                    name=name,
                    industry=_text_or_none(latest.get("industry")),
                    circulating_market_cap_cny=_number_or_none(latest.get("float_mv")),
                    total_market_cap_cny=_number_or_none(latest.get("total_mv")),
                ),
                last_limit_up_date=max(limit_dates).isoformat(),
                limit_up_hits_20d=len(limit_dates),
                decision_date=decision.isoformat(),
            )
        )
    return sorted(
        records,
        key=lambda item: (-item.limit_up_hits_20d, item.last_limit_up_date, item.candidate.symbol),
    )


def _is_limit_up(row: dict[str, object], code: str) -> bool:
    close = _number_or_none(row.get("close"))
    previous = _number_or_none(row.get("prev_close"))
    if close is None or previous is None or previous <= 0:
        return False
    threshold = 0.195 if code.startswith(("300", "301", "688")) else 0.295 if code.startswith(("4", "8", "92")) else 0.095
    return close / previous - 1 >= threshold


def _row_date(row: dict[str, object]) -> date | None:
    value = row.get("date")
    if value is None:
        return None
    text = str(value).strip()
    try:
        if len(text) >= 8 and text[:8].isdigit():
            return datetime.strptime(text[:8], "%Y%m%d").date()
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_date(value: str) -> date:
    text = str(value).strip()
    if len(text) >= 8 and text[:8].isdigit():
        return datetime.strptime(text[:8], "%Y%m%d").date()
    return date.fromisoformat(text[:10])


def _raw_code(value: object) -> str:
    text = str(value or "").strip().upper()
    return text.split(".", 1)[0].removeprefix("SH").removeprefix("SZ").removeprefix("BJ")


def _symbol(code: str) -> str:
    suffix = "BJ" if code.startswith(("4", "8", "92")) else "SH" if code.startswith(("6", "9")) else "SZ"
    return f"{code}.{suffix}"


def _is_common_a_share_code(code: str) -> bool:
    return len(code) == 6 and code.startswith(("000", "001", "002", "003", "300", "301", "600", "601", "603", "605", "688", "4", "8", "92"))


def _number_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _text_or_none(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
