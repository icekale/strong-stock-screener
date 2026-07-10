from __future__ import annotations

import base64
import json
from html.parser import HTMLParser
from typing import Any

import httpx
import pyaes

from app.models import (
    SectorReplicaChartSeries,
    SectorReplicaMode,
    SectorReplicaPlate,
    SectorReplicaQxLive,
    SectorReplicaRadarResponse,
    SectorReplicaStockRow,
    StrongStockSourceStatus,
)
from app.services.sector_radar_replica import build_reference_time_axis
from app.services.short_term_cache import TtlCache

_AES_KEY = b"secretkey322yes!!aaaaaaaaaaaaaaa"
_AES_IV = b"fixediv_16valued"


class SectorReplicaLiveProvider:
    source_name = "短线侠 qxlive"

    def __init__(
        self,
        *,
        api_base_url: str = "https://duanxianxia.cn",
        page_base_url: str = "https://duanxianxia.com",
        stock_api_url: str = "https://bm.duanxianxia.com/data/getKaipanStock/web",
        subplate_api_url: str = "https://bm.duanxianxia.com/data/getKaipanSubPlate",
        timeout_seconds: float = 8,
        cache_ttl_seconds: float = 5,
        http_client: object | None = None,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.page_base_url = page_base_url.rstrip("/")
        self.stock_api_url = stock_api_url
        self.subplate_api_url = subplate_api_url
        self.timeout_seconds = timeout_seconds
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client()
        self._radar_cache = TtlCache[dict[str, Any]](
            ttl_seconds=cache_ttl_seconds,
            name="sector-replica-radar",
        )
        self._stocks_cache = TtlCache[list[SectorReplicaStockRow]](
            ttl_seconds=cache_ttl_seconds,
            name="sector-replica-stocks",
        )
        self._subplates_cache = TtlCache[list[tuple[str, str]]](
            ttl_seconds=cache_ttl_seconds,
            name="sector-replica-subplates",
        )

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    def get_radar(
        self,
        *,
        mode: SectorReplicaMode,
        selected_codes: list[str],
        limit: int,
        trade_date: str,
        generated_at: str,
    ) -> SectorReplicaRadarResponse:
        normalized_codes = [
            code
            for code in (_plain_board_code(item) for item in selected_codes)
            if code.isdigit()
        ]
        cache_key = f"{mode}:{','.join(normalized_codes)}"
        payload = self._radar_cache.get_or_set(
            cache_key,
            lambda: self._fetch_payload(mode=mode, selected_codes=normalized_codes),
        )
        return build_sector_replica_live_response(
            payload,
            mode=mode,
            trade_date=trade_date,
            generated_at=generated_at,
            plate_limit=max(1, limit),
        )

    def _fetch_payload(self, *, mode: SectorReplicaMode, selected_codes: list[str]) -> dict[str, Any]:
        plate_type = "money" if mode == "main_flow" else "strong"
        selected = ",".join(
            code
            for code in (_plain_board_code(item) for item in selected_codes)
            if code.isdigit()
        )
        url = f"{self.api_base_url}/api/getLiveByStrong"
        if selected or mode == "main_flow":
            response = self.http_client.post(
                url,
                data={"platetype": plate_type, "platelist": selected},
                headers=_request_headers(self.page_base_url),
                timeout=self.timeout_seconds,
            )
        else:
            response = self.http_client.get(
                url,
                headers=_request_headers(self.page_base_url),
                timeout=self.timeout_seconds,
            )
        response.raise_for_status()
        return decode_duanxianxia_payload(response.text)

    def get_board_stocks(
        self,
        *,
        board_code: str,
        limit: int,
    ) -> list[SectorReplicaStockRow]:
        plate_code = _plain_board_code(board_code)
        if not plate_code.isdigit():
            return []
        rows = self._stocks_cache.get_or_set(
            plate_code,
            lambda: self._fetch_board_stocks(plate_code),
        )
        return rows[: max(1, limit)]

    def get_board_subplates(self, *, board_code: str) -> list[tuple[str, str]]:
        plate_code = _plain_board_code(board_code)
        if not plate_code.isdigit():
            return []
        return self._subplates_cache.get_or_set(
            plate_code,
            lambda: self._fetch_board_subplates(plate_code),
        )

    def _fetch_board_stocks(self, plate_code: str) -> list[SectorReplicaStockRow]:
        response = self.http_client.post(
            self.stock_api_url,
            data={"plateCode": plate_code},
            headers=_request_headers(self.page_base_url),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return []
        return build_sector_replica_live_stock_rows(payload.get("list"))

    def _fetch_board_subplates(self, plate_code: str) -> list[tuple[str, str]]:
        response = self.http_client.post(
            self.subplate_api_url,
            data={"plateCode": plate_code},
            headers=_request_headers(self.page_base_url),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return []
        parser = _SubPlateParser()
        parser.feed(str(payload.get("result") or ""))
        return parser.items


def build_sector_replica_live_response(
    payload: dict[str, Any],
    *,
    mode: SectorReplicaMode,
    trade_date: str,
    generated_at: str,
    plate_limit: int | None = None,
) -> SectorReplicaRadarResponse:
    if payload.get("result") != "success":
        raise ValueError("短线侠 qxlive 返回非 success")

    all_plates = _parse_plates(payload.get("plates"), mode=mode)
    plates = all_plates[:plate_limit] if plate_limit is not None else all_plates
    legend = [str(item) for item in _as_list(payload.get("legend")) if str(item).strip()]
    series = _order_series_by_legend(_parse_series(payload.get("series")), legend)
    if not all_plates or not series:
        raise ValueError("短线侠 qxlive 缺少板块或曲线")
    qxlive = _parse_qxlive(payload.get("qxlive"))

    return SectorReplicaRadarResponse(
        mode=mode,
        trade_date=trade_date,
        axis=build_reference_time_axis(),
        qxlive=qxlive,
        plates=plates,
        checkplate=[_plain_board_code(code) for code in _as_list(payload.get("checkplate"))],
        legend=legend,
        series=series,
        stocks=[],
        related_tags=[],
        source_status=[
            StrongStockSourceStatus(
                source="短线侠 qxlive",
                status="success",
                detail=f"读取真实 getLiveByStrong {mode} 板块分时曲线",
            )
        ],
        generated_at=generated_at,
    )


def decode_duanxianxia_payload(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("短线侠 qxlive 返回空内容")
    if stripped.startswith("{"):
        payload = json.loads(stripped)
    else:
        encrypted = base64.b64decode(stripped)
        mode = pyaes.AESModeOfOperationCBC(_AES_KEY, iv=_AES_IV)
        decrypter = pyaes.Decrypter(mode)
        decrypted = decrypter.feed(encrypted) + decrypter.feed()
        payload = json.loads(decrypted.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("短线侠 qxlive 返回结构不是对象")
    return payload


def build_sector_replica_live_stock_rows(payload: object) -> list[SectorReplicaStockRow]:
    rows: list[SectorReplicaStockRow] = []
    for item in _as_list(payload):
        values = _as_list(item)
        if len(values) < 18:
            continue
        code = str(values[0]).strip()
        name = str(values[1]).strip() or None
        if not code:
            continue
        compat_row = [
            code,
            name,
            _to_float(values[2]),
            _to_float(values[3]),
            _to_float(values[4]),
            _to_float(values[5]),
            None,
            _to_float(values[7]),
            _to_float(values[8]),
            _to_float(values[9]),
            _to_float(values[10]),
            _to_float(values[11]),
            str(values[12]).strip() or "--",
            str(values[13]).strip() or None,
            _to_float(values[14]),
            _to_float(values[15]),
            _to_float(values[16]),
            _to_float(values[17]),
        ]
        rows.append(
            SectorReplicaStockRow(
                symbol=_symbol_from_plain_code(code),
                code=code,
                name=name,
                pct_change=_to_float(values[2]),
                turnover_cny=_to_float(values[8]),
                circulating_value_cny=_to_float(values[7]),
                board_label=str(values[12]).strip() or "--",
                auction_pct_change=_to_float(values[3]),
                auction_amount_cny=_to_float(values[16]),
                auction_volume_ratio=_to_float(values[15]),
                buy_ratio_pct=_to_float(values[14]),
                seal_amount_cny=_to_float(values[17]),
                leader_tag=str(values[13]).strip() or None,
                themes=[],
                industry=None,
                compat_row=compat_row,
            )
        )
    return rows


def _parse_plates(payload: object, *, mode: SectorReplicaMode) -> list[SectorReplicaPlate]:
    output: list[SectorReplicaPlate] = []
    for item in _plate_items(payload):
        if not isinstance(item, dict):
            continue
        code = _plain_board_code(item.get("code"))
        name = str(item.get("name") or "").strip()
        value = _to_float(item.get("val"))
        if not code or not name or value is None:
            continue
        output.append(
            SectorReplicaPlate(
                code=code,
                name=name,
                val=value,
                ztcount=int(_to_float(item.get("ztcount")) or 0),
                display_value=_money_text_from_wan(value) if mode == "main_flow" else None,
            )
        )
    return output


def _parse_series(payload: object) -> list[SectorReplicaChartSeries]:
    output: list[SectorReplicaChartSeries] = []
    for item in _as_list(payload):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        output.append(
            SectorReplicaChartSeries(
                name=name,
                type=str(item.get("type") or "line"),
                data=[_to_float(value) for value in _as_list(item.get("data"))],
                smooth=False,
                showSymbol=bool(item.get("showSymbol", False)),
            )
        )
    return output


def _parse_qxlive(payload: object) -> SectorReplicaQxLive:
    if not isinstance(payload, dict):
        return SectorReplicaQxLive()
    series_payload = payload.get("series")
    series: dict[str, list[float | None]] = {}
    if isinstance(series_payload, dict):
        for key, values in series_payload.items():
            series[str(key)] = [_to_float(value) for value in _as_list(values)]
    return SectorReplicaQxLive(
        Aaxis=[_format_axis_label(value) for value in _as_list(payload.get("Aaxis"))],
        zflist=[value for value in (_to_float(item) for item in _as_list(payload.get("zflist"))) if value is not None],
        series=series,
    )


def _order_series_by_legend(
    series: list[SectorReplicaChartSeries],
    legend: list[str],
) -> list[SectorReplicaChartSeries]:
    if not legend:
        return series
    index_by_name = {name: index for index, name in enumerate(legend)}
    return sorted(series, key=lambda item: (index_by_name.get(item.name, len(legend)), item.name))


def _plate_items(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        def sort_key(item: tuple[object, object]) -> tuple[int, str]:
            key = str(item[0])
            try:
                return (int(key), key)
            except ValueError:
                return (10_000_000, key)

        return [value for _key, value in sorted(payload.items(), key=sort_key)]
    return []


def _as_list(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload
    return []


def _to_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").rstrip("%")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _plain_board_code(value: object) -> str:
    return str(value or "").strip().replace("theme:", "")


def _symbol_from_plain_code(code: str) -> str:
    if code.startswith("6"):
        return f"{code}.SH"
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return code


def _format_axis_label(value: object) -> str:
    text = str(value or "").strip()
    if len(text) == 4 and text.isdigit():
        return f"{text[:2]}:{text[2:]}"
    return text


def _money_text_from_wan(value: float) -> str:
    abs_value = abs(value)
    sign = "-" if value < 0 else ""
    if abs_value >= 10_000:
        return f"{sign}{abs_value / 10_000:.1f}亿"
    return f"{sign}{abs_value:.0f}万"


def _request_headers(page_base_url: str) -> dict[str, str]:
    return {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Origin": page_base_url,
        "Referer": f"{page_base_url}/web/qxlive",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        ),
        "X-Requested-With": "XMLHttpRequest",
    }


class _SubPlateParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[tuple[str, str]] = []
        self._active_code: str | None = None
        self._active_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "button":
            return
        attributes = {key.lower(): value for key, value in attrs}
        classes = str(attributes.get("class") or "").split()
        code = str(attributes.get("platecode") or "").strip()
        if "subplate" in classes and code.isdigit():
            self._active_code = code
            self._active_text = []

    def handle_data(self, data: str) -> None:
        if self._active_code is not None:
            self._active_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "button" or self._active_code is None:
            return
        name = "".join(self._active_text).strip()
        if name:
            self.items.append((self._active_code, name))
        self._active_code = None
        self._active_text = []
