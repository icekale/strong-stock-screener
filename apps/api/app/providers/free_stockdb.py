from __future__ import annotations

from typing import Any

import httpx


class FreeStockDbRequestError(RuntimeError):
    pass


class FreeStockDbClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 10.0,
        http_client: object | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._http_client = http_client or httpx.Client(timeout=timeout_seconds)

    def vals(self, *, table: str, k1: str, k2: str) -> list[Any]:
        params = {"cmd": "vals", "t": table, "k1": k1, "k2": k2}
        try:
            response = self._http_client.get(self._base_url, params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise FreeStockDbRequestError(f"free-stockdb 请求失败：{exc}") from exc
        except ValueError as exc:
            raise FreeStockDbRequestError("free-stockdb 返回了无效 JSON") from exc
        if not isinstance(payload, list):
            raise FreeStockDbRequestError("free-stockdb 返回结构异常：预期 list")
        return payload
