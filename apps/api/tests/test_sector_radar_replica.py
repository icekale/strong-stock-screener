from __future__ import annotations

import hashlib
import json
from datetime import datetime
from time import sleep
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    SectorWorkbenchPoint,
    SectorWorkbenchResponse,
    SectorWorkbenchSeries,
    SectorWorkbenchStock,
    SectorWorkbenchTheme,
    StrongStockSourceStatus,
)
from app.services.sector_radar_replica import (
    build_reference_time_axis,
    build_sector_radar_replica_response,
    build_sector_replica_stock_rows,
    missing_replica_series_names,
    replica_theme_names_for_codes,
)
from app.services.sector_replica_live import (
    SectorReplicaLiveProvider,
    build_sector_replica_live_response,
    build_sector_replica_live_stock_rows,
)


def test_live_replica_response_uses_duanxianxia_plate_names_and_minute_series() -> None:
    response = build_sector_replica_live_response(
        {
            "result": "success",
            "checkplate": ["801001", "801660"],
            "legend": ["芯片", "通信"],
            "plates": {
                "1": {"name": "芯片", "val": "33228", "code": "801001", "ztcount": "48"},
                "2": {"name": "通信", "val": "7981", "code": "801660", "ztcount": "25"},
                "3": {"name": "算力", "val": "7562", "code": "801807", "ztcount": "17"},
            },
            "series": [
                {
                    "name": "通信",
                    "type": "line",
                    "showSymbol": False,
                    "data": ["-7257", "-5982", "-3051", "7981"],
                },
                {
                    "name": "芯片",
                    "type": "line",
                    "showSymbol": False,
                    "data": ["6006", "8112", "5165", "33228"],
                },
            ],
            "qxlive": {
                "Aaxis": ["0915", "0916", "0917", "0918"],
                "zflist": ["0", "1"],
                "series": {"QX": ["62", "63"], "ZT": ["48", "49"]},
            },
        },
        mode="strength",
        trade_date="2026-07-09",
        generated_at="2026-07-09T10:30:00+08:00",
    )

    assert [item.name for item in response.plates[:3]] == ["芯片", "通信", "算力"]
    assert response.plates[0].code == "801001"
    assert response.plates[0].val == 33228
    assert response.plates[0].ztcount == 48
    assert response.checkplate == ["801001", "801660"]
    assert response.legend == ["芯片", "通信"]
    assert response.series[0].name == "芯片"
    assert response.series[0].smooth is False
    assert response.series[0].data[:4] == [6006, 8112, 5165, 33228]
    assert response.axis == build_reference_time_axis()
    assert response.axis[-1] == "15:00"
    assert len(response.series[0].data) < len(response.axis)
    assert response.qxlive.Aaxis == ["09:15", "09:16", "09:17", "09:18"]
    assert response.qxlive.series["QX"] == [62, 63]


def test_live_provider_reuses_short_lived_radar_payload_cache() -> None:
    client = _FakeLiveHttpClient()
    provider = SectorReplicaLiveProvider(http_client=client, cache_ttl_seconds=5)

    for generated_at in ("2026-07-09T10:30:00+08:00", "2026-07-09T10:30:01+08:00"):
        provider.get_radar(
            mode="strength",
            selected_codes=["801001"],
            limit=5,
            trade_date="2026-07-09",
            generated_at=generated_at,
        )

    assert client.get_calls == 0
    assert client.post_calls == 1


def test_live_provider_does_not_hide_failed_refresh_behind_stale_radar_data() -> None:
    client = _FakeLiveHttpClient()
    provider = SectorReplicaLiveProvider(http_client=client, cache_ttl_seconds=0.01)
    provider.get_radar(
        mode="strength",
        selected_codes=["801001"],
        limit=5,
        trade_date="2026-07-09",
        generated_at="2026-07-09T10:30:00+08:00",
    )
    sleep(0.02)
    client.fail_requests = True

    with pytest.raises(RuntimeError, match="upstream unavailable"):
        provider.get_radar(
            mode="strength",
            selected_codes=["801001"],
            limit=5,
            trade_date="2026-07-09",
            generated_at="2026-07-09T10:31:00+08:00",
        )


def test_live_provider_uses_configured_stock_api_url() -> None:
    client = _FakeLiveHttpClient()
    provider = SectorReplicaLiveProvider(
        http_client=client,
        stock_api_url="https://example.test/stocks",
    )

    provider.get_board_stocks(board_code="801001", limit=10)

    assert client.last_post_url == "https://example.test/stocks"


def test_live_provider_reads_real_subplate_names_and_codes() -> None:
    client = _FakeLiveHttpClient()
    provider = SectorReplicaLiveProvider(
        http_client=client,
        subplate_api_url="https://example.test/subplates",
    )

    subplates = provider.get_board_subplates(board_code="801001")

    assert subplates[:2] == [("801722", "存储"), ("801490", "半导体设备")]
    assert client.last_post_url == "https://example.test/subplates"


def test_live_stock_rows_keep_duanxianxia_table_field_order() -> None:
    rows = build_sector_replica_live_stock_rows(
        [
            [
                "603137",
                "恒尚节能",
                10,
                5.67,
                5,
                25.2,
                15.86,
                2_097_984_017,
                327_029_554,
                8_877_576,
                205_602_790,
                -196_725_214,
                "8连板",
                "龙一",
                62.87,
                68.74,
                115_656_012,
                148_919_200,
                248_542_544,
            ]
        ]
    )

    assert rows[0].symbol == "603137.SH"
    assert rows[0].code == "603137"
    assert rows[0].name == "恒尚节能"
    assert rows[0].pct_change == 10
    assert rows[0].turnover_cny == 327_029_554
    assert rows[0].circulating_value_cny == 2_097_984_017
    assert rows[0].board_label == "8连板"
    assert rows[0].auction_pct_change == 5.67
    assert rows[0].auction_amount_cny == 115_656_012
    assert rows[0].auction_volume_ratio == 68.74
    assert rows[0].buy_ratio_pct == 62.87
    assert rows[0].seal_amount_cny == 148_919_200
    assert rows[0].leader_tag == "龙一"
    assert rows[0].compat_row[0] == "603137"


def test_replica_response_uses_qxlive_shape_and_selected_board_series() -> None:
    response = build_sector_radar_replica_response(
        workbench=_workbench_response(),
        mode="strength",
        selected_codes=["theme:cpo"],
        sampled_at=datetime(2026, 7, 9, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert response.result == "success"
    assert response.checkplate == ["theme:cpo"]
    assert response.legend == ["CPO"]
    assert [item.name for item in response.plates][:2] == ["CPO", "机器人"]
    assert response.plates[0].ztcount == 2
    assert response.series[0].name == "CPO"
    assert response.series[0].type == "line"
    assert response.series[0].showSymbol is False
    assert response.series[0].data[0] == 1200
    segment_start = response.axis.index("09:16")
    segment_end = response.axis.index("10:30")
    checkpoint = response.axis.index("09:30")
    linear_checkpoint = 1800 + (7875 - 1800) * ((checkpoint - segment_start) / (segment_end - segment_start))
    assert 1800 < response.series[0].data[checkpoint] < 7875
    assert abs(response.series[0].data[checkpoint] - linear_checkpoint) > 20
    assert response.series[0].data[response.axis.index("10:30")] == 7875
    assert response.series[0].data[response.axis.index("10:31")] is None
    assert response.qxlive.Aaxis[:3] == ["09:15", "09:16", "09:17"]
    assert response.qxlive.series["QX"]


def test_replica_series_estimates_reference_curve_from_single_sample() -> None:
    workbench = _workbench_response()
    workbench.series = [
        SectorWorkbenchSeries(
            name="CPO",
            scope="theme",
            metric="strength",
            points=[
                SectorWorkbenchPoint(
                    time="14:58",
                    value=7875,
                    sampled_at="2026-07-09T14:58:00+08:00",
                )
            ],
        )
    ]

    response = build_sector_radar_replica_response(
        workbench=workbench,
        mode="strength",
        selected_codes=["theme:cpo"],
        sampled_at=datetime(2026, 7, 9, 14, 58, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    data = response.series[0].data
    visible_values = [point for point in data if point is not None]
    distinct_values = {round(point, 2) for point in visible_values}

    assert len(distinct_values) > 20
    assert visible_values[0] != 7875
    assert data[response.axis.index("14:58")] == 7875
    assert data[response.axis.index("14:59")] is None


def test_replica_time_axis_contains_reference_session_labels() -> None:
    axis = build_reference_time_axis()

    assert axis[:3] == ["09:15", "09:16", "09:17"]
    assert "11:30" in axis
    assert "13:00" in axis
    assert axis[-1] == "15:00"
    assert "11:31" not in axis
    assert "12:59" not in axis


def test_replica_stock_rows_keep_reference_column_order() -> None:
    rows = build_sector_replica_stock_rows(_workbench_response(), board_code="theme:cpo")

    first = rows[0]
    assert first.compat_row[0] == "603690"
    assert first.compat_row[1] == "至纯科技"
    assert first.compat_row[2] == 10.0
    assert first.compat_row[8] == 320_000_000
    assert first.compat_row[12] == "2连板"
    assert first.compat_row[13] == "龙一"
    assert first.compat_row[17] == 120_000_000


def test_replica_main_flow_displays_money_values_and_estimated_status() -> None:
    response = build_sector_radar_replica_response(
        workbench=_workbench_response(),
        mode="main_flow",
        selected_codes=[],
        sampled_at=datetime(2026, 7, 9, 10, 31, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert response.mode == "main_flow"
    assert response.plates[0].display_value == "1.6亿"
    assert response.checkplate[:2] == ["theme:cpo", "theme:robot"]
    assert any(item.source == "短线侠兼容板块雷达" and item.status == "success" for item in response.source_status)


def test_replica_board_codes_are_stable_for_unknown_chinese_theme_names() -> None:
    workbench = _workbench_response()
    workbench.themes.append(
        SectorWorkbenchTheme(
            name="先进封装",
            scope="theme",
            limit_up_count=1,
            strength_score=1200,
            main_flow_cny=30_000_000,
            turnover_cny=90_000_000,
            change_pct=2.1,
            leader="封装一号",
            member_count=1,
            source="测试题材",
            flow_status="estimated",
        )
    )

    response = build_sector_radar_replica_response(
        workbench=workbench,
        mode="strength",
        selected_codes=[],
        sampled_at=datetime(2026, 7, 9, 10, 32, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    expected = hashlib.sha1("先进封装".encode("utf-8")).hexdigest()[:10]
    assert response.plates[-1].code == f"theme:cn-{expected}"


def test_replica_theme_names_for_codes_defaults_to_five_boards() -> None:
    workbench = _workbench_response()
    workbench.themes.extend(
        [
            SectorWorkbenchTheme(
                name=f"题材{i}",
                scope="theme",
                limit_up_count=0,
                strength_score=1000 - i,
                main_flow_cny=10_000_000,
                turnover_cny=20_000_000,
                change_pct=1.0,
                leader=None,
                member_count=1,
                source="测试题材",
                flow_status="estimated",
            )
            for i in range(3)
        ]
    )

    names = replica_theme_names_for_codes(workbench.themes, selected_codes=[])
    selected = replica_theme_names_for_codes(workbench.themes, selected_codes=["theme:robot"])

    assert names == ["CPO", "机器人", "题材0", "题材1", "题材2"]
    assert selected == ["机器人"]


def test_missing_replica_series_names_detects_partial_intraday_history() -> None:
    workbench = _workbench_response()
    workbench.series = [workbench.series[0]]

    assert missing_replica_series_names(workbench, ["CPO", "机器人"]) == ["机器人"]


def _workbench_response() -> SectorWorkbenchResponse:
    sampled_at = "2026-07-09T10:30:00+08:00"
    return SectorWorkbenchResponse(
        scope="theme",
        mode="strength",
        trade_date="2026-07-09",
        themes=[
            SectorWorkbenchTheme(
                name="CPO",
                scope="theme",
                limit_up_count=2,
                strength_score=7875,
                main_flow_cny=156_000_000,
                turnover_cny=480_000_000,
                change_pct=5.8,
                leader="至纯科技",
                member_count=3,
                source="测试题材",
                flow_status="estimated",
            ),
            SectorWorkbenchTheme(
                name="机器人",
                scope="theme",
                limit_up_count=1,
                strength_score=3819,
                main_flow_cny=82_000_000,
                turnover_cny=260_000_000,
                change_pct=3.2,
                leader="机器人一号",
                member_count=2,
                source="测试题材",
                flow_status="estimated",
            ),
        ],
        selected_themes=["CPO", "机器人"],
        series=[
            SectorWorkbenchSeries(
                name="CPO",
                scope="theme",
                metric="strength",
                points=[
                    SectorWorkbenchPoint(time="09:15", value=1200, sampled_at=sampled_at),
                    SectorWorkbenchPoint(time="09:16", value=1800, sampled_at=sampled_at),
                    SectorWorkbenchPoint(time="10:30", value=7875, sampled_at=sampled_at),
                ],
            ),
            SectorWorkbenchSeries(
                name="机器人",
                scope="theme",
                metric="strength",
                points=[
                    SectorWorkbenchPoint(time="09:15", value=-500, sampled_at=sampled_at),
                    SectorWorkbenchPoint(time="09:16", value=600, sampled_at=sampled_at),
                    SectorWorkbenchPoint(time="10:30", value=3819, sampled_at=sampled_at),
                ],
            ),
        ],
        related_tags=["存储", "半导体设备", "电子气体"],
        stocks=[
            SectorWorkbenchStock(
                symbol="603690.SH",
                name="至纯科技",
                industry="半导体设备",
                themes=["CPO", "半导体设备"],
                pct_change=10.0,
                turnover_cny=320_000_000,
                turnover_rate=6.8,
                limit_up=True,
                board_count=2,
                auction_pct_change=5.67,
                auction_turnover_cny=116_000_000,
                seal_amount_cny=120_000_000,
                risk_flags=["龙一"],
            ),
            SectorWorkbenchStock(
                symbol="300001.SZ",
                name="机器人一号",
                industry="机器人",
                themes=["机器人"],
                pct_change=6.2,
                turnover_cny=180_000_000,
                turnover_rate=4.2,
                limit_up=False,
                board_count=0,
                auction_pct_change=3.1,
                auction_turnover_cny=22_000_000,
                seal_amount_cny=None,
            ),
        ],
        source_status=[
            StrongStockSourceStatus(
                source="测试板块源",
                status="success",
                detail="测试数据",
            )
        ],
        generated_at=sampled_at,
    )


class _FakeLiveResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload
        self.text = json.dumps(payload, ensure_ascii=False)

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


class _FakeLiveHttpClient:
    def __init__(self) -> None:
        self.get_calls = 0
        self.post_calls = 0
        self.last_post_url: str | None = None
        self.fail_requests = False

    def get(self, _url: str, **_kwargs: object) -> _FakeLiveResponse:
        if self.fail_requests:
            raise RuntimeError("upstream unavailable")
        self.get_calls += 1
        return _FakeLiveResponse(_live_payload())

    def post(self, url: str, **_kwargs: object) -> _FakeLiveResponse:
        if self.fail_requests:
            raise RuntimeError("upstream unavailable")
        self.post_calls += 1
        self.last_post_url = url
        if url.endswith("/subplates") or "getKaipanSubPlate" in url:
            return _FakeLiveResponse(
                {
                    "result": (
                        "<button class='subplate' plateCode='801722'>存储</button>"
                        "<button class='subplate' plateCode='801490'>半导体设备</button>"
                    )
                }
            )
        if url.endswith("/stocks") or "getKaipanStock" in url:
            return _FakeLiveResponse({"list": []})
        return _FakeLiveResponse(_live_payload())


def _live_payload() -> dict[str, object]:
    return {
        "result": "success",
        "checkplate": ["801001"],
        "legend": ["芯片"],
        "plates": {
            "1": {"name": "芯片", "val": "33228", "code": "801001", "ztcount": "48"}
        },
        "series": [
            {
                "name": "芯片",
                "type": "line",
                "showSymbol": False,
                "data": ["6006", "8112"],
            }
        ],
        "qxlive": {
            "Aaxis": ["0915", "0916"],
            "zflist": ["0", "1"],
            "series": {"QX": ["62", "63"]},
        },
    }
