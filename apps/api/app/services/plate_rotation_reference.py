from __future__ import annotations

import re
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from app.models import StrongStockSourceStatus

PlateRotationSource = Literal["kaipan", "ths"]


class PlateRotationThemeItem(BaseModel):
    rank: int
    code: str
    name: str
    score: float
    value_type: str = "score"
    color: str = "red"


class PlateRotationReferenceResponse(BaseModel):
    source: str = "kaipan"
    themes: list[PlateRotationThemeItem] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)


class PlateRotationReferenceProvider:
    source_name = "短线侠/开盘啦题材榜单"

    def __init__(
        self,
        *,
        base_url: str = "https://duanxianxia.com",
        timeout_seconds: float = 8,
        http_client: object | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client()

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    def get_today_themes(
        self,
        *,
        limit: int = 20,
        source: PlateRotationSource = "kaipan",
        days: int = 20,
    ) -> PlateRotationReferenceResponse:
        bounded_limit = max(1, min(limit, 50))
        try:
            response = self.http_client.post(
                f"{self.base_url}/api/getPlateRotatData",
                data={"from": source, "days": str(days)},
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Origin": self.base_url,
                    "Referer": f"{self.base_url}/web/main",
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
                    ),
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            themes = parse_plate_rotation_rows(response.json(), source=source)[:bounded_limit]
            status = StrongStockSourceStatus(
                source=self.source_name,
                status="success" if themes else "stale",
                detail=(
                    f"抓取 {len(themes)} 个开盘啦题材强度榜单"
                    if themes
                    else "接口返回成功，但未解析到题材榜单"
                ),
            )
            return PlateRotationReferenceResponse(source=source, themes=themes, source_status=[status])
        except Exception as exc:
            return PlateRotationReferenceResponse(
                source=source,
                themes=[],
                source_status=[
                    StrongStockSourceStatus(
                        source=self.source_name,
                        status="failed",
                        detail=f"题材榜单抓取失败: {exc.__class__.__name__}",
                    )
                ],
            )


def parse_plate_rotation_rows(
    payload: dict[str, Any],
    *,
    source: PlateRotationSource = "kaipan",
) -> list[PlateRotationThemeItem]:
    html = str(payload.get("html") or "")
    rows = re.split(r"<span class='rank'[^>]*>(\d+)</span>", html)
    output: list[PlateRotationThemeItem] = []
    for index in range(1, len(rows), 2):
        rank = _safe_int(rows[index])
        rest = rows[index + 1] if index + 1 < len(rows) else ""
        match = re.search(
            r"<td class='plate plate\d+'\s*code='(\d+)'\s*name='([^']+)'[^>]*>"
            r".*?<span style='color:(red|green);'>([\d.\-]+%?)</span>",
            rest,
            re.S,
        )
        if not match or rank is None:
            continue
        code, name, color, raw_value = match.groups()
        value_type = "pct" if raw_value.endswith("%") else "score"
        score = _safe_float(raw_value.rstrip("%"))
        if score is None:
            continue
        output.append(
            PlateRotationThemeItem(
                rank=rank,
                code=code,
                name=name,
                score=score,
                value_type=value_type if source == "ths" else "score",
                color=color,
            )
        )
    return output


def _safe_int(value: object) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _safe_float(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None
