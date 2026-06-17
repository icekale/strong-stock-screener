from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from app.models import StrongStockSourceStatus
from app.providers.thsdk_candidates import normalize_symbol

NegativeNewsStatus = Literal["triggered", "clear", "unknown"]

NEGATIVE_NEWS_KEYWORDS = (
    "立案",
    "处罚",
    "监管函",
    "问询函",
    "警示函",
    "减持",
    "业绩预亏",
    "预亏",
    "诉讼",
    "冻结",
    "退市风险",
    "财务造假",
    "信披违规",
    "债务逾期",
    "被执行",
    "失信",
)

NewsFetcher = Callable[[str], list[dict[str, object]]]


@dataclass(frozen=True)
class NegativeNewsRisk:
    status: NegativeNewsStatus
    flags: list[str]


class EastmoneyNewsRiskProvider:
    source_name = "东方财富个股新闻"

    def __init__(self, news_fetcher: NewsFetcher | None, max_rows: int = 20) -> None:
        self.news_fetcher = news_fetcher
        self.max_rows = max_rows

    @classmethod
    def from_akshare(cls) -> "EastmoneyNewsRiskProvider":
        try:
            import akshare as ak
        except ModuleNotFoundError:
            return cls(news_fetcher=None)

        def fetch(symbol: str) -> list[dict[str, object]]:
            plain_symbol = _plain_symbol(symbol)
            try:
                frame = ak.stock_news_em(symbol=plain_symbol)
            except TypeError:
                frame = ak.stock_news_em(stock=plain_symbol)
            if frame is None:
                return []
            return [dict(row) for row in frame.to_dict(orient="records")]

        return cls(news_fetcher=fetch)

    def get_negative_news_risk(self, symbol: str) -> NegativeNewsRisk:
        if self.news_fetcher is None:
            return NegativeNewsRisk(status="unknown", flags=["负面新闻未知: AKShare 未安装或个股新闻源不可用"])
        try:
            rows = self.news_fetcher(symbol)
        except Exception as exc:
            return NegativeNewsRisk(status="unknown", flags=[f"负面新闻未知: {exc}"])
        return analyze_negative_news_rows(rows[: self.max_rows])

    def status(self) -> StrongStockSourceStatus:
        if self.news_fetcher is None:
            return StrongStockSourceStatus(
                source=self.source_name,
                status="failed",
                detail="AKShare 未安装或个股新闻源不可用",
            )
        return StrongStockSourceStatus(
            source=self.source_name,
            status="success",
            detail=f"东方财富个股新闻已配置，最多检查最近 {self.max_rows} 条",
        )


def analyze_negative_news_rows(rows: list[dict[str, object]]) -> NegativeNewsRisk:
    flags: list[str] = []
    for row in rows:
        title = _text_value(row, "新闻标题", "标题", "title")
        content = _text_value(row, "新闻内容", "内容", "content")
        if not title and not content:
            continue
        haystack = f"{title} {content}"
        if not any(keyword in haystack for keyword in NEGATIVE_NEWS_KEYWORDS):
            continue
        time_text = (
            _text_value(row, "发布时间", "新闻发布时间", "时间", "datetime", "publish_time", "public_time")
            or "时间未知"
        )
        source = _text_value(row, "文章来源", "来源", "source") or "来源未知"
        display_title = title or content[:30]
        flags.append(f"负面新闻待核验: {time_text} {display_title}（{source}）")
    if flags:
        return NegativeNewsRisk(status="triggered", flags=_dedupe(flags))
    return NegativeNewsRisk(status="clear", flags=[])


def _plain_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    if normalized:
        return normalized.split(".", 1)[0]
    return symbol.strip()


def _text_value(row: dict[str, object], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output
