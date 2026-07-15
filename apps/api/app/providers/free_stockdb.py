from __future__ import annotations

import re
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

    def get(self, *, table: str, k1: str, k2: str) -> list[Any]:
        params = {
            "cmd": "get",
            "t": f"{table}:{_normalize_selector(k1)}:{_normalize_selector(k2, range_value=True)}",
        }
        return _normalize_get_rows(self._request(params))

    def get_selector(self, selector: str) -> Any:
        return self._request({"cmd": "get", "t": selector})

    def vals(self, *, table: str, k1: str, k2: str) -> list[Any]:
        params = {"cmd": "vals", "t": table, "k1": k1, "k2": k2}
        payload = self._request(params)
        if isinstance(payload, dict):
            return [payload]
        if isinstance(payload, list):
            return payload
        raise FreeStockDbRequestError("free-stockdb 返回结构异常：预期 dict 或 list")

    def _request(self, params: dict[str, str]) -> Any:
        try:
            response = self._http_client.get(self._base_url, params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise FreeStockDbRequestError(f"free-stockdb 请求失败：{exc}") from exc
        except ValueError as exc:
            raise FreeStockDbRequestError("free-stockdb 返回了无效 JSON") from exc
        return payload


def _normalize_selector(value: str, *, range_value: bool = False) -> str:
    normalized = str(value).strip()
    if normalized.lower() in {"all:", "all", ""}:
        return "*"
    if not range_value:
        return normalized
    for operator in ("<", ">"):
        if operator in normalized:
            left, right = normalized.split(operator, 1)
            return f"{_compact_date(left)}{operator}{_compact_date(right)}"
    return normalized


def _compact_date(value: str) -> str:
    match = re.match(r"(\d{8})", value.strip())
    return match.group(1) if match else value.strip()


def _normalize_get_rows(payload: Any) -> list[Any]:
    if isinstance(payload, dict):
        return [payload]
    if not isinstance(payload, list):
        raise FreeStockDbRequestError("free-stockdb 返回结构异常：预期 dict 或 list")
    rows: list[Any] = []
    for item in payload:
        if isinstance(item, list) and len(item) == 2 and isinstance(item[1], dict):
            rows.append(item[1])
        else:
            rows.append(item)
    return rows
