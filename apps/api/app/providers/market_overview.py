from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.models import (
    MarketAdvanceDeclineSummary,
    MarketOverviewResponse,
    MarketSectorStrengthItem,
    MarketTurnoverSummary,
    SectorRadarItem,
    SectorRadarResponse,
    StrongStockSourceStatus,
)


INDEX_SECIDS = ("1.000001", "0.399001", "0.899050")
TICKFLOW_INDEX_SYMBOLS = ["000001.SH", "399001.SZ", "899050.BJ"]
IFIND_INDEX_SYMBOLS = "000001.SH,399001.SZ,899050.BJ"
IFIND_INDEX_INDICATORS = "最新价,涨跌幅,成交额,上涨家数,下跌家数"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class EastmoneyMarketOverviewProvider:
    source_name = "东方财富全市场"

    def __init__(
        self,
        timeout_seconds: float = 12,
        http_client: object | None = None,
        realtime_quote_provider: object | None = None,
        ifind_index_provider: object | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.realtime_quote_provider = realtime_quote_provider
        self.ifind_index_provider = ifind_index_provider
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client()

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    def get_overview(self) -> MarketOverviewResponse:
        source_status: list[StrongStockSourceStatus] = []
        trade_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        turnover = MarketTurnoverSummary()
        advance_decline = MarketAdvanceDeclineSummary()
        sectors: list[MarketSectorStrengthItem] = []

        if self.ifind_index_provider is None:
            source_status.append(
                StrongStockSourceStatus(
                    source="iFinD 实时指数",
                    status="disabled",
                    detail="未配置 iFinD 指数源，实时市场概览使用备用源",
                )
            )
        else:
            try:
                ifind = self._fetch_ifind_realtime_overview()
                turnover.total_cny = round(ifind["total_cny"], 2)
                advance_decline = MarketAdvanceDeclineSummary(
                    advance_count=ifind.get("advance_count"),
                    decline_count=ifind.get("decline_count"),
                )
                if ifind.get("trade_date"):
                    trade_date = str(ifind["trade_date"])
                source_status.append(
                    StrongStockSourceStatus(
                        source="iFinD 实时指数",
                        status="success",
                        detail=f"index_highfreq_quotes 返回 {ifind['quote_count']} 个指数",
                    )
                )
            except Exception as exc:
                source_status.append(
                    StrongStockSourceStatus(
                        source="iFinD 实时指数",
                        status="failed",
                        detail=f"实时指数获取失败: {exc.__class__.__name__}; fallback 到 TickFlow",
                    )
                )

        if turnover.total_cny is not None:
            pass
        elif self.realtime_quote_provider is None:
            source_status.append(
                StrongStockSourceStatus(
                    source="TickFlow 实时指数",
                    status="disabled",
                    detail="未配置实时行情源，今日成交额使用 fallback",
                )
            )
        else:
            try:
                tickflow = self._fetch_tickflow_realtime_turnover()
                turnover.total_cny = round(tickflow["total_cny"], 2)
                if tickflow.get("trade_date"):
                    trade_date = str(tickflow["trade_date"])
                source_status.append(
                    StrongStockSourceStatus(
                        source="TickFlow 实时指数",
                        status="success",
                        detail=f"沪深北指数实时成交额，返回 {tickflow['quote_count']} 个指数",
                    )
                )
            except Exception as exc:
                source_status.append(
                    StrongStockSourceStatus(
                        source="TickFlow 实时指数",
                        status="failed",
                        detail=f"实时成交额获取失败: {exc.__class__.__name__}; fallback 到东方财富",
                    )
                )

        try:
            index_rows = self._fetch_index_snapshot()
            if turnover.total_cny is None:
                turnover.total_cny = round(sum(_number(row.get("f6")) or 0 for row in index_rows), 2)
                index_detail = "沪深北指数成交额与上涨/下跌/平盘家数，fallback 今日成交额"
            elif advance_decline.advance_count is not None and advance_decline.decline_count is not None:
                index_detail = "iFinD 已提供实时涨跌家数，东方财富仅作兜底校验"
            else:
                index_detail = "沪深北指数上涨/下跌/平盘家数，今日成交额由实时源提供"
            if advance_decline.advance_count is None or advance_decline.decline_count is None:
                advance_decline = MarketAdvanceDeclineSummary(
                    advance_count=sum(_integer(row.get("f104")) or 0 for row in index_rows),
                    decline_count=sum(_integer(row.get("f105")) or 0 for row in index_rows),
                    unchanged_count=sum(_integer(row.get("f106")) or 0 for row in index_rows),
                )
            elif advance_decline.unchanged_count is None:
                advance_decline.unchanged_count = sum(_integer(row.get("f106")) or 0 for row in index_rows)
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富全A指数",
                    status="success",
                    detail=index_detail,
                )
            )
        except Exception as exc:
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富全A指数",
                    status="failed",
                    detail=f"指数快照获取失败: {exc.__class__.__name__}",
                )
            )

        try:
            history = self._fetch_index_amount_history()
            if history["trade_date"]:
                trade_date = str(history["trade_date"])
            previous_total = _number(history.get("previous_total_cny"))
            if previous_total is not None:
                turnover.previous_total_cny = round(previous_total, 2)
            if turnover.total_cny is not None and turnover.previous_total_cny:
                turnover.change_cny = round(turnover.total_cny - turnover.previous_total_cny, 2)
                turnover.change_pct = round(
                    turnover.change_cny / turnover.previous_total_cny * 100,
                    2,
                )
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富指数日K",
                    status="success",
                    detail="沪深北指数日K成交额用于昨日对比",
                )
            )
        except Exception as exc:
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富指数日K",
                    status="failed",
                    detail=f"昨日成交额获取失败: {exc.__class__.__name__}",
                )
            )

        try:
            sectors = self._fetch_sector_strength(limit=20)
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富行业板块",
                    status="success",
                    detail=f"返回 {len(sectors)} 个全市场板块",
                )
            )
        except Exception as exc:
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富行业板块",
                    status="failed",
                    detail=f"板块强度获取失败: {exc.__class__.__name__}",
                )
            )

        return MarketOverviewResponse(
            trade_date=trade_date,
            turnover=turnover,
            advance_decline=advance_decline,
            sectors=sectors,
            source_status=source_status,
        )

    def get_sector_radar(self, limit: int = 20) -> SectorRadarResponse:
        bounded_limit = max(1, min(limit, 50))
        source_status: list[StrongStockSourceStatus] = []
        trade_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        try:
            inflow = self._fetch_sector_capital_flow(limit=bounded_limit, direction="inflow")
            outflow = self._fetch_sector_capital_flow(limit=bounded_limit, direction="outflow")
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富行业板块资金流",
                    status="success",
                    detail=f"返回净流入 {len(inflow)} 个 / 净流出 {len(outflow)} 个板块",
                )
            )
            return SectorRadarResponse(
                trade_date=trade_date,
                capital_flow_status="direct",
                flow_source="东方财富行业板块资金净额",
                inflow=inflow,
                outflow=outflow,
                source_status=source_status,
            )
        except Exception as exc:
            source_status.append(
                StrongStockSourceStatus(
                    source="东方财富行业板块资金流",
                    status="failed",
                    detail=f"资金净额获取失败: {exc.__class__.__name__}; fallback 到涨跌额估算",
                )
            )
            overview = self.get_overview()
            items = [_sector_radar_item(sector) for sector in overview.sectors if sector.turnover_cny is not None]
            inflow = sorted(
                [item for item in items if item.net_flow_cny is not None and item.net_flow_cny > 0],
                key=lambda item: item.net_flow_cny or 0,
                reverse=True,
            )[:bounded_limit]
            outflow = sorted(
                [item for item in items if item.net_flow_cny is not None and item.net_flow_cny < 0],
                key=lambda item: item.net_flow_cny or 0,
            )[:bounded_limit]
            return SectorRadarResponse(
                trade_date=overview.trade_date,
                capital_flow_status="estimated",
                flow_source="东方财富行业板块涨跌额估算",
                inflow=inflow,
                outflow=outflow,
                source_status=[*source_status, *overview.source_status],
            )

    def _fetch_ifind_realtime_overview(self) -> dict[str, Any]:
        payload = self.ifind_index_provider.call_tool(
            "hexin-ifind-ds-index-mcp",
            "index_highfreq_quotes",
            {
                "symbols": IFIND_INDEX_SYMBOLS,
                "indicators": IFIND_INDEX_INDICATORS,
                "data_mode": "real_time",
            },
        )
        rows = _ifind_table_rows(payload)
        if not rows:
            raise ValueError("empty ifind index rows")

        total = 0.0
        advance_count = 0
        decline_count = 0
        has_advance = False
        has_decline = False
        trade_dates: list[str] = []
        for row in rows:
            amount = _number(row.get("成交额"))
            if amount is not None:
                total += amount
            up_count = _integer(row.get("上涨家数"))
            if up_count is not None:
                advance_count += up_count
                has_advance = True
            down_count = _integer(row.get("下跌家数"))
            if down_count is not None:
                decline_count += down_count
                has_decline = True
            trade_date = _date_from_quote_time(row.get("time"))
            if trade_date:
                trade_dates.append(trade_date)
        if total <= 0:
            raise ValueError("empty ifind amount")
        return {
            "total_cny": total,
            "advance_count": advance_count if has_advance else None,
            "decline_count": decline_count if has_decline else None,
            "trade_date": max(trade_dates) if trade_dates else None,
            "quote_count": len(rows),
        }

    def _fetch_tickflow_realtime_turnover(self) -> dict[str, Any]:
        quotes = self.realtime_quote_provider.get_quotes(TICKFLOW_INDEX_SYMBOLS)
        amounts = [_number(getattr(quote, "turnover_cny", None)) for quote in quotes]
        valid_amounts = [amount for amount in amounts if amount is not None]
        if not valid_amounts:
            raise ValueError("empty tickflow turnover")
        trade_dates = [
            trade_date
            for trade_date in (
                _date_from_quote_time(getattr(quote, "quote_time", None)) for quote in quotes
            )
            if trade_date
        ]
        return {
            "total_cny": sum(valid_amounts),
            "trade_date": max(trade_dates) if trade_dates else None,
            "quote_count": len(valid_amounts),
        }

    def _fetch_index_snapshot(self) -> list[dict[str, Any]]:
        response = self.http_client.get(
            "https://push2.eastmoney.com/api/qt/ulist.np/get",
            params={
                "secids": ",".join(INDEX_SECIDS),
                "fields": "f2,f3,f6,f12,f14,f104,f105,f106",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        rows = _extract_diff(response.json())
        if not rows:
            raise ValueError("empty index snapshot")
        return rows

    def _fetch_index_amount_history(self) -> dict[str, object]:
        latest_total = 0.0
        previous_total = 0.0
        trade_dates: list[str] = []
        for secid in INDEX_SECIDS:
            response = self.http_client.get(
                "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                params={
                    "secid": secid,
                    "klt": "101",
                    "fqt": "1",
                    "lmt": "2",
                    "end": "20500101",
                    "iscca": "1",
                    "fields1": "f1,f2,f3,f4,f5,f6",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                },
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            klines = response.json().get("data", {}).get("klines", [])
            if not isinstance(klines, list) or len(klines) < 2:
                raise ValueError(f"index kline missing: {secid}")
            previous = _parse_kline_amount(str(klines[-2]))
            latest = _parse_kline_amount(str(klines[-1]))
            previous_total += previous["amount"]
            latest_total += latest["amount"]
            trade_dates.append(latest["date"])
        return {
            "trade_date": max(trade_dates) if trade_dates else None,
            "latest_total_cny": latest_total,
            "previous_total_cny": previous_total,
        }

    def _fetch_sector_strength(self, limit: int) -> list[MarketSectorStrengthItem]:
        response = self.http_client.get(
            "https://push2.eastmoney.com/api/qt/clist/get",
            params={
                "pn": "1",
                "pz": str(max(1, min(limit, 50))),
                "po": "1",
                "fid": "f3",
                "np": "1",
                "fltt": "2",
                "invt": "2",
                "fs": "m:90+t:2",
                "fields": "f3,f6,f12,f14,f104,f105,f136,f140",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        rows = _extract_diff(response.json())
        sectors = [
            MarketSectorStrengthItem(
                name=str(row.get("f14") or ""),
                change_pct=_number(row.get("f3")),
                turnover_cny=_number(row.get("f6")),
                advance_count=_integer(row.get("f104")),
                decline_count=_integer(row.get("f105")),
                leader=_text(row.get("f140")),
                source="东方财富行业板块",
            )
            for row in rows
            if row.get("f14")
        ]
        return sorted(
            sectors,
            key=lambda item: (
                item.change_pct if item.change_pct is not None else -999,
                item.turnover_cny if item.turnover_cny is not None else 0,
            ),
            reverse=True,
        )

    def _fetch_sector_capital_flow(self, limit: int, direction: str) -> list[SectorRadarItem]:
        response = self.http_client.get(
            "https://push2.eastmoney.com/api/qt/clist/get",
            params={
                "pn": "1",
                "pz": str(max(1, min(limit, 50))),
                "po": "1" if direction == "inflow" else "0",
                "fid": "f62",
                "np": "1",
                "fltt": "2",
                "invt": "2",
                "fs": "m:90+t:2",
                "fields": "f3,f6,f12,f14,f62,f184,f104,f105,f140",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        rows = _extract_diff(response.json())
        items = [
            _sector_radar_item(
                MarketSectorStrengthItem(
                    name=str(row.get("f14") or ""),
                    change_pct=_number(row.get("f3")),
                    turnover_cny=_number(row.get("f6")),
                    advance_count=_integer(row.get("f104")),
                    decline_count=_integer(row.get("f105")),
                    leader=_text(row.get("f140")),
                    source="东方财富行业板块资金流",
                ),
                net_flow_cny=_number(row.get("f62")),
            )
            for row in rows
            if row.get("f14")
        ]
        if not items:
            raise ValueError("empty sector capital flow")
        return items


def _extract_diff(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("invalid payload")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("missing data")
    diff = data.get("diff")
    if not isinstance(diff, list):
        raise ValueError("missing diff")
    return [row for row in diff if isinstance(row, dict)]


def _sector_radar_item(
    sector: MarketSectorStrengthItem,
    net_flow_cny: float | None = None,
) -> SectorRadarItem:
    resolved_net_flow_cny = net_flow_cny
    if resolved_net_flow_cny is None and sector.turnover_cny is not None and sector.change_pct is not None:
        resolved_net_flow_cny = round(sector.turnover_cny * sector.change_pct / 100, 2)

    breadth_score = 0.0
    if sector.advance_count is not None and sector.decline_count is not None:
        total = sector.advance_count + sector.decline_count
        if total > 0:
            breadth_score = (sector.advance_count - sector.decline_count) / total * 10

    turnover_score = min((sector.turnover_cny or 0) / 10_000_000_000, 20)
    change_score = (sector.change_pct or 0) * 10
    return SectorRadarItem(
        name=sector.name,
        source=sector.source,
        change_pct=sector.change_pct,
        turnover_cny=sector.turnover_cny,
        advance_count=sector.advance_count,
        decline_count=sector.decline_count,
        leader=sector.leader,
        net_flow_cny=resolved_net_flow_cny,
        strength_score=round(change_score + breadth_score + turnover_score, 2),
    )


def _parse_kline_amount(value: str) -> dict[str, Any]:
    parts = value.split(",")
    if len(parts) < 7:
        raise ValueError("invalid kline row")
    return {"date": parts[0], "amount": float(parts[6])}


def _ifind_table_rows(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        raise ValueError("invalid ifind payload")
    data = payload.get("data")
    if isinstance(data, str):
        data = json.loads(data)
    if isinstance(data, dict) and isinstance(data.get("tables"), list):
        table = data["tables"]
    elif isinstance(data, dict) and isinstance(data.get("text"), str):
        table = _markdown_table(data["text"])
    else:
        raise ValueError("missing ifind tables")
    if not table:
        return []
    header = table[0]
    if not isinstance(header, list):
        raise ValueError("invalid ifind header")
    rows: list[dict[str, object]] = []
    for item in table[1:]:
        if not isinstance(item, list):
            continue
        rows.append({str(header[index]): item[index] for index in range(min(len(header), len(item)))})
    return rows


def _markdown_table(value: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in value.splitlines():
        text = line.strip()
        if not text.startswith("|") or "---" in text:
            continue
        rows.append([cell.strip() for cell in text.strip("|").split("|")])
    return rows


def _date_from_quote_time(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        timestamp = float(text)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, ZoneInfo("Asia/Shanghai")).date().isoformat()
    except ValueError:
        pass
    try:
        normalized = text.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    except ValueError:
        return None


def _number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: object) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
