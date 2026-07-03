from __future__ import annotations

from typing import Any

import httpx

from app.providers.thsdk_candidates import normalize_symbol

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class EastmoneyConceptBlockProvider:
    source_name = "东财 slist 概念归属"

    def __init__(self, timeout_seconds: float = 12, http_client: object | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client or httpx.Client(timeout=timeout_seconds)
        self._cache: dict[str, list[str]] = {}

    def get_concept_tags(self, symbol: str) -> list[str]:
        normalized = normalize_symbol(symbol)
        if not normalized:
            return []
        if normalized in self._cache:
            return list(self._cache[normalized])

        secid = _eastmoney_secid(normalized)
        if not secid:
            return []
        response = self.http_client.get(
            "https://push2.eastmoney.com/api/qt/slist/get",
            params={
                "fltt": "2",
                "invt": "2",
                "secid": secid,
                "spt": "3",
                "pi": "0",
                "pz": "200",
                "po": "1",
                "fields": "f12,f14,f3,f128",
            },
            headers={"User-Agent": USER_AGENT, "Referer": "https://quote.eastmoney.com/"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        tags = _concept_tags_from_payload(response.json())
        self._cache[normalized] = tags
        return list(tags)


def _eastmoney_secid(symbol: str) -> str:
    code, _, exchange = symbol.partition(".")
    if len(code) != 6:
        return ""
    market = "1" if exchange == "SH" else "0"
    return f"{market}.{code}"


def _concept_tags_from_payload(payload: dict[str, Any]) -> list[str]:
    diff = (payload.get("data") or {}).get("diff") or []
    items = diff.values() if isinstance(diff, dict) else diff
    tags: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("f14") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        tags.append(name)
    return tags
