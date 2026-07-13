import copy
import json
from pathlib import Path
from typing import Callable

import pytest

from app.services.chanlun.research_catalog import (
    ResearchCatalog,
    load_research_catalog,
    map_raw_state,
)


CATALOG_PATH = (
    Path(__file__).parents[1] / "app/services/chanlun/research_catalog.json"
)


def _write_catalog(
    tmp_path: Path,
    mutate: Callable[[dict[str, object]], None],
) -> Path:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    mutate(payload)
    path = tmp_path / "research_catalog.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_catalog_expands_only_the_approved_signal_whitelist() -> None:
    catalog = load_research_catalog()
    expanded = catalog.expanded_configs()

    assert catalog.version == "czsc-v2-catalog-1"
    assert {item.name for item in catalog.entries} == {
        "cxt_bi_status_V230101",
        "cxt_bi_base_V230228",
        "cxt_second_bs_V240524",
        "cxt_second_bs_V230320",
        "cxt_third_buy_V230228",
        "cxt_third_bs_V230319",
        "cxt_zhong_shu_gong_zhen_V221221",
        "tas_macd_bc_V240307",
    }
    assert len(expanded) == 16
    assert len({item.id for item in expanded}) == 16
    assert all(item.params is not None for item in expanded)


def test_catalog_expanded_params_are_immutable() -> None:
    config = load_research_catalog().expanded_configs()[0]

    with pytest.raises(TypeError):
        config.params["di"] = 2


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update({"unknown": True}),
        lambda payload: payload["entries"][0].update({"unknown": True}),
        lambda payload: payload.update({"catalog_version": "unsupported"}),
        lambda payload: payload["entries"][0].update({"name": "arbitrary_signal"}),
        lambda payload: payload["entries"][0].update({"periods": []}),
        lambda payload: payload["entries"].append(copy.deepcopy(payload["entries"][0])),
        lambda payload: payload["entries"][0].update({"params": {"di": 1}}),
        lambda payload: payload["entries"][0].update({"periods": ["1d"]}),
        lambda payload: payload["entries"][0].update({"role": "risk"}),
        lambda payload: payload["entries"][0].update({"key_template": "changed"}),
        lambda payload: payload["entries"].pop(),
    ],
    ids=[
        "unknown-root-key",
        "unknown-entry-key",
        "unsupported-version",
        "unapproved-signal",
        "empty-periods",
        "duplicate-expanded-id",
        "changed-params",
        "changed-periods",
        "changed-role",
        "changed-key-template",
        "missing-entry",
    ],
)
def test_catalog_rejects_invalid_forms(
    tmp_path: Path,
    mutate: Callable[[dict[str, object]], None],
) -> None:
    path = _write_catalog(tmp_path, mutate)

    with pytest.raises(ValueError):
        load_research_catalog(path)


def _raw_state(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "symbol": "300308.SZ",
        "catalog_id": "buy3.structure",
        "period": "5m",
        "value_fields": {"v1": "三买", "v2": "6笔", "v3": "任意", "score": 0},
        "raw_key": "5分钟_D1_三买辅助V230228",
        "raw_value": "三买_6笔_任意_0",
        "occurred_at": "2026-07-10T10:00:00+08:00",
        "last_closed_bar_at": "2026-07-10T10:00:00+08:00",
        "input_snapshot_id": "sha256:abc",
        "engine_version": "1.0.0rc8",
    }
    payload.update(overrides)
    return payload


def test_map_raw_state_uses_catalog_identity_not_string_business_rules() -> None:
    evidence = map_raw_state(**_raw_state())

    assert evidence is not None
    assert evidence.family == "third_buy"
    assert evidence.direction == "bullish"
    assert evidence.role == "primary"
    assert evidence.reason == "5分钟结构出现三买"
    assert evidence.params["v1"] == "三买"
    assert evidence.params["di"] == 1


def test_map_raw_state_discards_inactive_other_value() -> None:
    evidence = map_raw_state(
        **_raw_state(
            value_fields={"v1": "其他", "v2": "其他", "v3": "任意", "score": 0},
            raw_value="其他_其他_任意_0",
        )
    )

    assert evidence is None


def test_map_raw_state_never_parses_the_audit_value() -> None:
    expected = map_raw_state(**_raw_state())
    changed_audit = map_raw_state(**_raw_state(raw_value="完全不同的审计文本"))

    assert expected is not None and changed_audit is not None
    assert (changed_audit.family, changed_audit.direction, changed_audit.role) == (
        expected.family,
        expected.direction,
        expected.role,
    )
    assert changed_audit.id == expected.id


def test_map_raw_state_retains_structured_trend_values() -> None:
    evidence = map_raw_state(
        **_raw_state(
            catalog_id="trend.bi-base",
            period="60m",
            value_fields={"v1": "向上", "v2": "中继", "v3": "任意", "score": 0},
            raw_key="60分钟_D0BL9_V230228",
            raw_value="向上_中继_任意_0",
        )
    )

    assert evidence is not None
    assert evidence.family == "trend_context"
    assert evidence.direction == "bullish"
    assert evidence.params["v1"] == "向上"
    assert evidence.params["v2"] == "中继"


def test_map_raw_state_rejects_unrecognized_active_value() -> None:
    with pytest.raises(ValueError):
        map_raw_state(
            **_raw_state(
                value_fields={"v1": "未知新语义", "v2": "任意", "v3": "任意", "score": 0}
            )
        )


def test_evidence_identity_includes_symbol_and_all_structured_values() -> None:
    first = map_raw_state(**_raw_state())
    other_symbol = map_raw_state(**_raw_state(symbol="000001.SZ"))
    other_v2 = map_raw_state(
        **_raw_state(
            value_fields={"v1": "三买", "v2": "8笔", "v3": "任意", "score": 0}
        )
    )

    assert first is not None and other_symbol is not None and other_v2 is not None
    assert len({first.id, other_symbol.id, other_v2.id}) == 3


@pytest.mark.parametrize(
    "value_fields",
    [
        {"v1": "三买", "v2": "6笔", "v3": "任意", "score": 0, "extra": "bad"},
        {"v1": "三买", "v2": "6笔", "v3": "任意", "score": 101},
        {"v1": "三买", "v2": "6笔", "v3": "错误", "score": 0},
        {"v1": "三买", "v2": "7笔", "v3": "任意", "score": 0},
    ],
    ids=["extra-key", "score-out-of-range", "invalid-v3", "invalid-catalog-v2"],
)
def test_map_raw_state_rejects_malformed_structured_values(
    value_fields: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        map_raw_state(**_raw_state(value_fields=value_fields))


def test_default_catalog_and_expanded_index_are_reused() -> None:
    assert load_research_catalog() is load_research_catalog()


def test_injected_catalog_builds_its_expanded_index_once(monkeypatch) -> None:
    catalog = ResearchCatalog.model_validate_json(CATALOG_PATH.read_text(encoding="utf-8"))
    original = ResearchCatalog.expanded_configs
    calls = 0

    def counted(catalog_instance: ResearchCatalog):
        nonlocal calls
        calls += 1
        return original(catalog_instance)

    monkeypatch.setattr(ResearchCatalog, "expanded_configs", counted)

    map_raw_state(**_raw_state(catalog=catalog))
    map_raw_state(**_raw_state(catalog=catalog, occurred_at="2026-07-10T10:05:00+08:00"))

    assert calls == 1
