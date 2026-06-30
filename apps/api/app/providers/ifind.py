from __future__ import annotations

import json
from typing import Any

import httpx

from app.models import StockResearchResponse, StrongStockDataUnavailable, StrongStockSourceStatus


IFIND_MCP_SERVICES: dict[str, str] = {
    "hexin-ifind-ds-stock-mcp": "iFinD A股数据",
    "hexin-ifind-ds-news-mcp": "iFinD 新闻公告",
    "hexin-ifind-ds-index-mcp": "iFinD 指数板块",
}


class IfindMcpProvider:
    source_name = "iFinD MCP"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout_seconds: float = 12,
        http_client: object | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client()

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    def status(self) -> StrongStockSourceStatus:
        if not self.api_key:
            return StrongStockSourceStatus(
                source=self.source_name,
                status="missing_key",
                detail="STRONG_STOCK_IFIND_API_KEY 或 IFIND_API_KEY 未配置",
            )
        return StrongStockSourceStatus(
            source=self.source_name,
            status="success",
            detail=f"base_url={self.base_url}",
        )

    def probe_tools(self, service_id: str) -> StrongStockSourceStatus:
        if not self.api_key:
            return self.status()
        try:
            response = self._post_json_rpc(
                service_id=service_id,
                method="tools/list",
                params=None,
                request_id=1,
            )
            tools = _extract_tools(response.json())
            return StrongStockSourceStatus(
                source=IFIND_MCP_SERVICES.get(service_id, service_id),
                status="success",
                detail=f"tools/list 返回 {len(tools)} 个工具",
            )
        except StrongStockDataUnavailable:
            raise
        except httpx.HTTPStatusError as exc:
            raise StrongStockDataUnavailable(
                f"iFinD MCP 请求失败: HTTP {exc.response.status_code}"
            ) from exc
        except Exception as exc:
            raise StrongStockDataUnavailable(f"iFinD MCP 请求失败: {exc.__class__.__name__}") from exc

    def call_tool(self, service_id: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        if not self.api_key:
            raise StrongStockDataUnavailable("iFinD MCP Key 未配置")
        try:
            response = self._post_json_rpc(
                service_id=service_id,
                method="tools/call",
                params={"name": tool_name, "arguments": arguments},
                request_id=f"{service_id}:{tool_name}",
            )
            response.raise_for_status()
            return _extract_tool_call_result(response.json())
        except StrongStockDataUnavailable:
            raise
        except httpx.HTTPStatusError as exc:
            raise StrongStockDataUnavailable(
                f"iFinD MCP 工具调用失败: HTTP {exc.response.status_code}"
            ) from exc
        except Exception as exc:
            raise StrongStockDataUnavailable(f"iFinD MCP 工具调用失败: {exc.__class__.__name__}") from exc

    def get_stock_research(self, symbol: str) -> StockResearchResponse:
        if not self.api_key:
            return StockResearchResponse(symbol=symbol, source_status=[self.status()])

        response = StockResearchResponse(symbol=symbol)
        profile, status = self._safe_tool_call(
            service_id="hexin-ifind-ds-stock-mcp",
            tool_name="get_stock_info",
            arguments={"query": f"{symbol} 的公司简称、所属行业、主营业务、上市日期"},
            source="iFinD A股资料",
        )
        response.source_status.append(status)
        response.profile = _coerce_mapping(profile)

        financials, status = self._safe_tool_call(
            service_id="hexin-ifind-ds-stock-mcp",
            tool_name="get_stock_financials",
            arguments={
                "query": f"{symbol} 最新报告期的ROE、营收增速、净利润增速、总市值、动态市盈率、静态市盈率、市盈率TTM、市净率"
            },
            source="iFinD 财务估值",
        )
        response.source_status.append(status)
        finance_payload = _coerce_mapping(financials)
        response.financials = finance_payload
        response.valuation = _pick_fields(
            finance_payload,
            [
                "总市值",
                "总市值(元)",
                "总市值（元）",
                "总市值(亿元)",
                "总市值（亿元）",
                "动态市盈率",
                "市盈率动态",
                "市盈率(动态)",
                "市盈率（动态）",
                "PE动态",
                "动态PE",
                "市盈率TTM",
                "PE TTM",
                "PE_TTM",
                "静态市盈率",
                "市盈率静态",
                "市盈率(静态)",
                "市盈率（静态）",
                "PE静态",
                "静态PE",
                "市盈率",
                "PE",
                "市净率",
                "PB",
                "市销率",
                "PS",
            ],
        )

        events, status = self._safe_tool_call(
            service_id="hexin-ifind-ds-stock-mcp",
            tool_name="get_stock_events",
            arguments={"query": f"{symbol} 近一年严重异动、监管问询、减持、解禁、诉讼、风险警示"},
            source="iFinD 风险事件",
        )
        response.source_status.append(status)
        response.events = _coerce_records(events)

        news, status = self._safe_tool_call(
            service_id="hexin-ifind-ds-news-mcp",
            tool_name="search_news",
            arguments={
                "query": f"{symbol} 负面 风险 监管 减持 解禁",
                "time_start": "2025-01-01",
                "time_end": "2026-12-31",
                "size": 5,
            },
            source="iFinD 新闻",
        )
        response.source_status.append(status)
        response.news = _coerce_records(news)

        notices, status = self._safe_tool_call(
            service_id="hexin-ifind-ds-news-mcp",
            tool_name="search_notice",
            arguments={
                "query": f"{symbol} 公告 风险 监管 减持 解禁 严重异动",
                "time_start": "2025-01-01",
                "time_end": "2026-12-31",
                "size": 5,
            },
            source="iFinD 公告",
        )
        response.source_status.append(status)
        response.notices = _coerce_records(notices)

        sector, status = self._safe_tool_call(
            service_id="hexin-ifind-ds-index-mcp",
            tool_name="sector_data",
            arguments={"query": f"{symbol} 所属行业板块近5个交易日涨跌幅、成交额、成分股数量"},
            source="iFinD 板块",
        )
        response.source_status.append(status)
        response.sector = _coerce_mapping(sector)
        return response

    def _safe_tool_call(
        self,
        service_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        source: str,
    ) -> tuple[Any, StrongStockSourceStatus]:
        try:
            payload = self.call_tool(service_id, tool_name, arguments)
            size = len(payload) if hasattr(payload, "__len__") else 1
            return payload, StrongStockSourceStatus(
                source=source,
                status="success",
                detail=f"{tool_name} 返回 {size} 条/项",
            )
        except StrongStockDataUnavailable as exc:
            return None, StrongStockSourceStatus(source=source, status="failed", detail=str(exc))

    def _post_json_rpc(
        self,
        service_id: str,
        method: str,
        params: dict[str, Any] | None,
        request_id: int | str,
    ) -> httpx.Response:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        response = self.http_client.post(
            f"{self.base_url}/ds-mcp-servers/{service_id}",
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response


def _extract_tools(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise StrongStockDataUnavailable("iFinD MCP 响应结构异常")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise StrongStockDataUnavailable("iFinD MCP 响应缺少 result")
    tools = result.get("tools")
    if not isinstance(tools, list):
        raise StrongStockDataUnavailable("iFinD MCP 响应缺少 tools")
    return [item for item in tools if isinstance(item, dict)]


def _extract_tool_call_result(payload: object) -> Any:
    if not isinstance(payload, dict):
        raise StrongStockDataUnavailable("iFinD MCP 响应结构异常")
    if payload.get("error"):
        raise StrongStockDataUnavailable(f"iFinD MCP 返回错误: {payload['error']}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise StrongStockDataUnavailable("iFinD MCP 响应缺少 result")
    if "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content")
    if isinstance(content, list):
        text_parts = [item.get("text", "") for item in content if isinstance(item, dict)]
        text = "\n".join(part for part in text_parts if part)
        return _try_parse_json(text) if text else content
    if "content" in result:
        return result["content"]
    return result


def _try_parse_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        answer_rows = _extract_answer_table_rows(value)
        if answer_rows:
            return {**value, **answer_rows[0]}
        return value
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        return value[0]
    if isinstance(value, str) and value.strip():
        return {"摘要": value.strip()}
    return {}


def _coerce_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        records = []
        for item in value:
            if isinstance(item, dict):
                records.append(item)
            elif isinstance(item, str) and item.strip():
                records.append({"摘要": item.strip()})
        return records
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str) and value.strip():
        return [{"摘要": value.strip()}]
    return []


def _extract_answer_table_rows(value: dict[str, Any]) -> list[dict[str, str]]:
    data = value.get("data")
    if not isinstance(data, dict):
        return []
    answer = data.get("answer")
    if not isinstance(answer, str):
        return []
    table = _markdown_table(answer)
    if len(table) < 2:
        return []
    header = table[0]
    rows: list[dict[str, str]] = []
    for row in table[1:]:
        item: dict[str, str] = {}
        for index in range(min(len(header), len(row))):
            key = _normalize_ifind_field_name(header[index])
            value_text = row[index].strip()
            if key and value_text:
                item[key] = value_text
        if item:
            rows.append(item)
    return rows


def _markdown_table(value: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in value.splitlines():
        text = line.strip()
        if not text.startswith("|") or "---" in text:
            continue
        rows.append([cell.strip() for cell in text.strip("|").split("|")])
    return rows


def _normalize_ifind_field_name(value: str) -> str:
    text = value.strip()
    for marker in ("（单位：", "（单位:", "(单位：", "(单位:"):
        if marker in text:
            text = text.split(marker, 1)[0].strip()
            break
    return text


def _pick_fields(payload: dict[str, Any], names: list[str]) -> dict[str, Any]:
    normalized = _with_valuation_aliases(payload)
    return {name: normalized[name] for name in names if name in normalized}


def _with_valuation_aliases(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    if "总市值" not in result:
        for key in ("总市值(元)", "总市值（元）", "总市值(亿元)", "总市值（亿元）"):
            if key in result:
                result["总市值"] = result[key]
                break
    if "动态市盈率" not in result:
        for key in ("市盈率(PE,TTM)", "市盈率（PE，TTM）", "市盈率TTM", "PE TTM", "PE_TTM"):
            if key in result:
                result["动态市盈率"] = result[key]
                break
    if "静态市盈率" not in result:
        for key in ("市盈率（PE，LYR）", "市盈率(PE,LYR)", "市盈率(静态)", "市盈率（静态）", "市盈率", "PE"):
            if key in result:
                result["静态市盈率"] = result[key]
                break
    return result
