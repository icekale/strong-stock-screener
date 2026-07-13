import copy
import json
from pathlib import Path
from typing import Callable

import pytest

from app.services.chanlun.research_catalog import load_research_catalog


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
