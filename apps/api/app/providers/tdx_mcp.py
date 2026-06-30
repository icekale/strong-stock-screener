from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.models import SectorRadarItem, SectorRadarResponse, StrongStockDataUnavailable, StrongStockSourceStatus

TDX_MCP_URL = "https://mcp.tdx.com.cn:3001/mcp"


class TdxMcpProvider:
    source_name = "通达信MCP"

    def __init__(
        self,
        api_key: str = "",
        base_url: str = TDX_MCP_URL,
        timeout_seconds: float = 12,
        http_client: object | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client or httpx.Client(timeout=timeout_seconds)
        self._session_id: str | None = None
        self._request_id = 0

    def status(self) -> StrongStockSourceStatus:
        if not self.api_key:
            return StrongStockSourceStatus(
                source=self.source_name,
                status="missing_key",
                detail="TDX_API_KEY 或 STRONG_STOCK_TDX_API_KEY 未配置",
            )
        return StrongStockSourceStatus(
            source=self.source_name,
            status="success",
            detail=f"base_url={self.base_url}",
        )

    def get_sector_radar(self, limit: int = 20) -> SectorRadarResponse:
        rows = self.query_rows(
            "今日涨停股列表 封单金额 首次涨停时间 涨停原因 连续涨停天数 板型 封成比 所属概念 所属通达信风格",
            size=max(20, min(100, limit * 5)),
        )
        items = _sector_items_from_limit_up_rows(rows, limit=limit)
        return SectorRadarResponse(
            trade_date=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(),
            capital_flow_status="estimated",
            flow_source="通达信MCP涨停概念集中度估算",
            inflow=items,
            outflow=[],
            source_status=[
                StrongStockSourceStatus(
                    source="通达信MCP涨停概念",
                    status="success",
                    detail=f"涨停概念集中度返回 {len(rows)} 只涨停股，聚合 {len(items)} 个概念",
                )
            ],
        )

    def query_rows(self, question: str, size: int = 50, page: int = 1, market_range: str = "AG") -> list[dict[str, Any]]:
        if not self.api_key:
            raise StrongStockDataUnavailable("TDX_API_KEY 或 STRONG_STOCK_TDX_API_KEY 未配置")
        raw = self._call_tool(
            "tdx_wenda_quotes",
            {"question": question, "range": market_range, "size": size, "page": page},
        )
        return _rows_from_tdx_payload(raw)

    def _call_tool(self, name: str, arguments: dict[str, object]) -> dict[str, Any]:
        if self._session_id is None:
            self._initialize()
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if "error" in response:
            raise StrongStockDataUnavailable(f"通达信MCP错误: {response['error']}")
        result = response.get("result")
        if isinstance(result, dict):
            for item in result.get("content", []):
                if isinstance(item, dict) and item.get("type") == "text":
                    text = str(item.get("text") or "")
                    try:
                        parsed = json.loads(text)
                    except json.JSONDecodeError as exc:
                        raise StrongStockDataUnavailable("通达信MCP响应文本不是JSON") from exc
                    if isinstance(parsed, dict):
                        return parsed
        if isinstance(response, dict):
            return response
        raise StrongStockDataUnavailable("通达信MCP响应结构异常")

    def _initialize(self) -> None:
        self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "strong-stock-screener", "version": "0.1.0"},
                },
            }
        )
        try:
            self._post(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                },
                expect_json=False,
            )
        except Exception:
            pass

    def _post(self, payload: dict[str, object], expect_json: bool = True) -> dict[str, Any]:
        headers = {
            "tdx-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        try:
            response = self.http_client.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise StrongStockDataUnavailable(f"通达信MCP请求失败: HTTP {exc.response.status_code}") from exc
        except Exception as exc:
            raise StrongStockDataUnavailable(f"通达信MCP请求失败: {exc.__class__.__name__}") from exc
        session_id = getattr(response, "headers", {}).get("Mcp-Session-Id")
        if session_id:
            self._session_id = session_id
        if not expect_json:
            return {}
        content_type = getattr(response, "headers", {}).get("content-type", "")
        if "text/event-stream" in content_type:
            return _parse_sse_response(getattr(response, "text", ""))
        data = response.json()
        return data if isinstance(data, dict) else {}

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id


def _parse_sse_response(text: str) -> dict[str, Any]:
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            parsed = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and ("result" in parsed or "error" in parsed):
            return parsed
    return {}


def _rows_from_tdx_payload(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise StrongStockDataUnavailable("通达信MCP数据结构异常")
    meta = payload.get("meta")
    if isinstance(meta, dict) and meta.get("code") not in (0, "0", None):
        raise StrongStockDataUnavailable(str(meta.get("message") or "通达信MCP查询失败"))
    headers = payload.get("headers")
    data = payload.get("data")
    if not isinstance(headers, list) or not isinstance(data, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in data:
        if isinstance(row, list):
            rows.append({str(header): value for header, value in zip(headers, row)})
    return rows


def _sector_items_from_limit_up_rows(rows: list[dict[str, Any]], limit: int) -> list[SectorRadarItem]:
    concept_counts: Counter[str] = Counter()
    concept_seal_amounts: defaultdict[str, float] = defaultdict(float)
    concept_leaders: dict[str, tuple[int, str | None]] = {}
    for row in rows:
        concepts = _concepts_from_row(row)
        if not concepts:
            concepts = [_text_field(row, ["所属行业", "行业", "涨停原因"]) or "涨停主线"]
        board_count = _board_count(row)
        name = _text_field(row, ["sec_name", "股票名称", "名称"])
        seal_amount = _number_field(row, ["封单金额", "涨停最大封单额(万)", "封单额", "封单金额(万)"]) or 0
        for concept in concepts:
            concept_counts[concept] += 1
            concept_seal_amounts[concept] += seal_amount
            current = concept_leaders.get(concept)
            if current is None or board_count > current[0]:
                concept_leaders[concept] = (board_count, name)
    items: list[SectorRadarItem] = []
    for concept, count in concept_counts.most_common(max(1, limit)):
        seal_amount = concept_seal_amounts[concept]
        leader_boards, leader = concept_leaders.get(concept, (1, None))
        score = round(count * 18 + leader_boards * 8 + min(seal_amount / 10_000, 20), 2)
        items.append(
            SectorRadarItem(
                name=concept,
                source="通达信MCP涨停概念",
                change_pct=None,
                turnover_cny=None,
                advance_count=count,
                decline_count=0,
                leader=leader,
                net_flow_cny=round(count * 100_000_000 + seal_amount * 10_000, 2),
                strength_score=score,
            )
        )
    return items


def _concepts_from_row(row: dict[str, Any]) -> list[str]:
    raw = _text_field(row, ["所属概念", "所属通达信概念", "所属通达信风格", "概念板块", "涨停原因"]) or ""
    output: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[;；,，、/|【】\s]+", raw):
        concept = part.replace("@", "").strip()
        if not concept or concept in seen:
            continue
        if len(concept) > 12 and any(token in concept for token in ("+", "-")):
            continue
        seen.add(concept)
        output.append(concept)
    return output[:6]


def _board_count(row: dict[str, Any]) -> int:
    for key, value in row.items():
        if "连续涨停" in key or "连板" in key or "几板" in key:
            parsed = _to_float(value)
            if parsed is not None:
                return max(1, int(parsed))
    return 1


def _text_field(row: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    for key, value in row.items():
        if any(name in key for name in keys) and value not in (None, ""):
            return str(value).strip()
    return None


def _number_field(row: dict[str, Any], keys: list[str]) -> float | None:
    text = _text_field(row, keys)
    return _to_float(text)


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None
