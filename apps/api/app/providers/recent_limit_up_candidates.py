from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from app.models import StrongStockCandidate, StrongStockDataUnavailable, StrongStockSourceStatus
from app.providers.thsdk_candidates import normalize_symbol

PoolFetcher = Callable[[str], list[dict[str, object]]]


class RecentLimitUpCandidateProvider:
    source_name = "近20日涨停池"
    preserve_candidate_order = True

    def __init__(
        self,
        pool_fetcher: PoolFetcher | None,
        trading_days: int = 20,
        calendar_day_factor: int = 3,
    ) -> None:
        self.pool_fetcher = pool_fetcher
        self.trading_days = trading_days
        self.calendar_day_factor = calendar_day_factor

    @classmethod
    def from_akshare(cls) -> "RecentLimitUpCandidateProvider":
        try:
            import akshare as ak
        except ModuleNotFoundError:
            return cls(pool_fetcher=None)

        def fetch(date: str) -> list[dict[str, object]]:
            frame = ak.stock_zt_pool_em(date=date)
            if frame is None:
                return []
            return [dict(row) for row in frame.to_dict(orient="records")]

        return cls(pool_fetcher=fetch)

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        if self.pool_fetcher is None:
            raise StrongStockDataUnavailable("AKShare 未安装，无法查询东方财富近20日涨停池")

        rows_by_date: list[tuple[str, list[dict[str, object]]]] = []
        errors: list[str] = []
        for date in _recent_calendar_dates(trade_date, self.trading_days * self.calendar_day_factor):
            if len(rows_by_date) >= self.trading_days:
                break
            try:
                rows = self.pool_fetcher(date)
            except Exception as exc:
                errors.append(f"{date}: {exc}")
                continue
            if not rows:
                continue
            rows_by_date.append((date, rows))

        candidates = parse_recent_limit_up_rows(rows_by_date)
        if not candidates:
            detail = "东方财富近20日涨停池为空"
            if errors:
                detail = f"{detail}；最近错误: {errors[-1]}"
            raise StrongStockDataUnavailable(detail)
        return candidates

    def status(self) -> StrongStockSourceStatus:
        if self.pool_fetcher is None:
            return StrongStockSourceStatus(
                source=self.source_name,
                status="failed",
                detail="AKShare 未安装，无法查询东方财富近20日涨停池",
            )
        return StrongStockSourceStatus(
            source=self.source_name,
            status="success",
            detail=f"东方财富涨停池已配置，回看最近 {self.trading_days} 个交易日",
        )


def parse_recent_limit_up_rows(
    rows_by_date: list[tuple[str, list[dict[str, object]]]],
) -> list[StrongStockCandidate]:
    by_symbol: dict[str, dict[str, Any]] = {}
    for date, rows in rows_by_date:
        for row in rows:
            code = _text_value(row, "代码", "股票代码", "code", "symbol")
            name = _text_value(row, "名称", "股票简称", "name")
            if not code or not name or "ST" in name.upper():
                continue
            symbol = normalize_symbol(code)
            if not symbol:
                continue
            item = by_symbol.setdefault(
                symbol,
                {
                    "symbol": symbol,
                    "name": name,
                    "industry": _industry(row),
                    "dates": [],
                    "latest_date": date,
                    "latest_row": row,
                },
            )
            item["dates"].append(date)
            if date > item["latest_date"]:
                item["name"] = name
                item["industry"] = _industry(row)
                item["latest_date"] = date
                item["latest_row"] = row

    candidates = []
    for item in by_symbol.values():
        dates = sorted(set(item["dates"]), reverse=True)
        latest_row = item["latest_row"]
        latest_date = item["latest_date"]
        candidates.append(
            StrongStockCandidate(
                symbol=item["symbol"],
                name=item["name"],
                industry=item["industry"],
                total_market_cap_cny=_number_value(latest_row, "总市值"),
                circulating_market_cap_cny=_number_value(latest_row, "流通市值"),
                limit_up_evidence=[
                    "20日内涨停",
                    f"最近涨停: {latest_date}",
                    f"20日涨停次数: {len(dates)}",
                ],
                board_note=_board_note(dates, latest_row),
                abnormal_status=_abnormal_status(latest_row),
                abnormal_flags=_abnormal_flags(latest_row),
            )
        )

    return sorted(
        candidates,
        key=lambda candidate: (
            _last_limit_up_date(candidate),
            _limit_up_hits(candidate),
            candidate.symbol,
        ),
        reverse=True,
    )


def _recent_calendar_dates(trade_date: str, calendar_days: int) -> list[str]:
    parsed_date = _parse_date(trade_date)
    return [
        (parsed_date - timedelta(days=offset)).strftime("%Y%m%d")
        for offset in range(calendar_days)
    ]


def _parse_date(value: str) -> datetime:
    text = value.strip()
    if "-" in text:
        return datetime.strptime(text, "%Y-%m-%d")
    return datetime.strptime(text, "%Y%m%d")


def _text_value(row: dict[str, object], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _number_value(row: dict[str, object], *names: str) -> float | None:
    for name in names:
        value = row.get(name)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _industry(row: dict[str, object]) -> str | None:
    return _text_value(row, "所属行业", "所属同花顺行业", "行业", "申万行业") or None


def _board_note(dates: list[str], latest_row: dict[str, object]) -> str:
    notes = [f"涨停日期: {','.join(dates)}"]
    for key in ("涨停统计", "连板数", "炸板次数", "首次封板时间", "最后封板时间"):
        value = latest_row.get(key)
        if value not in (None, ""):
            notes.append(f"{key}: {value}")
    return "; ".join(notes)


def _abnormal_flags(row: dict[str, object]) -> list[str]:
    flags: list[str] = []
    for key, value in row.items():
        key_text = str(key)
        value_text = str(value).strip()
        if "异动" not in key_text:
            continue
        if value in (None, "", 0, "0", "否", "无", "False", False):
            continue
        if "严重" in key_text or "严重" in value_text:
            flags.append(f"{key_text}: {value_text}")
    return flags


def _abnormal_status(row: dict[str, object]) -> str:
    saw_abnormal_field = False
    for key, value in row.items():
        key_text = str(key)
        value_text = str(value).strip()
        if "异动" not in key_text:
            continue
        saw_abnormal_field = True
        if value not in (None, "", 0, "0", "否", "无", "False", False) and (
            "严重" in key_text or "严重" in value_text
        ):
            return "triggered"
    return "clear" if saw_abnormal_field else "unknown"


def _last_limit_up_date(candidate: StrongStockCandidate) -> str:
    for evidence in candidate.limit_up_evidence:
        if evidence.startswith("最近涨停: "):
            return evidence.removeprefix("最近涨停: ")
    return ""


def _limit_up_hits(candidate: StrongStockCandidate) -> int:
    for evidence in candidate.limit_up_evidence:
        if evidence.startswith("20日涨停次数: "):
            try:
                return int(evidence.removeprefix("20日涨停次数: "))
            except ValueError:
                return 0
    return 0
