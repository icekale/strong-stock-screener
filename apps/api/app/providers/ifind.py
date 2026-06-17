from __future__ import annotations

from typing import Any

import httpx

from app.models import StrongStockDataUnavailable, StrongStockSourceStatus


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
            response = self.http_client.post(
                f"{self.base_url}/ds-mcp-servers/{service_id}",
                headers={
                    "Authorization": self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
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
