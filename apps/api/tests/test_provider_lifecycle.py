from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.main as main
import app.deps as deps


@pytest.fixture(autouse=True)
def clear_provider_state(monkeypatch: pytest.MonkeyPatch):
    for attribute in (
        "candidate_provider",
        "kline_provider",
        "quote_provider",
        "ifind_provider",
        "ifind_http_client",
        "tdx_provider",
        "tdx_http_client",
        "default_kline_provider",
        "default_kline_provider_key",
        "default_quote_provider",
        "default_quote_provider_key",
        "default_ifind_provider",
        "default_ifind_provider_key",
        "default_tdx_provider",
        "default_tdx_provider_key",
        "default_market_overview_provider",
        "default_market_overview_provider_key",
    ):
        monkeypatch.delattr(main.app.state, attribute, raising=False)


def _settings(suffix: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        kline_provider="tickflow",
        tickflow_api_key="tickflow-key",
        tickflow_base_url=f"https://tickflow{suffix}.test",
        provider_timeout_seconds=5,
        ifind_api_key="ifind-key",
        ifind_base_url=f"https://ifind{suffix}.test",
        ifind_service_id="hexin-ifind-ds-stock-mcp",
        tdx_api_key="tdx-key",
        tdx_base_url=f"https://tdx{suffix}.test",
    )


def test_default_http_providers_are_reused_for_same_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(deps, "_effective_settings", lambda: _settings())

    assert main._kline_provider() is main._kline_provider()
    assert main._quote_provider() is main._quote_provider()
    assert main._ifind_provider() is main._ifind_provider()
    assert main._tdx_provider() is main._tdx_provider()


def test_configuration_change_closes_and_replaces_default_http_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = {"value": _settings()}
    monkeypatch.setattr(deps, "_effective_settings", lambda: current["value"])

    old_kline = main._kline_provider()
    old_quote = main._quote_provider()
    old_ifind = main._ifind_provider()
    old_tdx = main._tdx_provider()

    current["value"] = _settings("-new")

    new_kline = main._kline_provider()
    new_quote = main._quote_provider()
    new_ifind = main._ifind_provider()
    new_tdx = main._tdx_provider()

    assert new_kline is not old_kline
    assert new_quote is not old_quote
    assert new_ifind is not old_ifind
    assert new_tdx is not old_tdx
    assert old_kline.http_client.is_closed
    assert old_quote.http_client.is_closed
    assert old_ifind.http_client.is_closed
    assert old_tdx.http_client.is_closed


def test_clear_data_source_caches_closes_default_http_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(deps, "_effective_settings", lambda: _settings())

    kline = main._kline_provider()
    quote = main._quote_provider()
    ifind = main._ifind_provider()
    tdx = main._tdx_provider()

    main._clear_data_source_caches()

    assert kline.http_client.is_closed
    assert quote.http_client.is_closed
    assert ifind.http_client.is_closed
    assert tdx.http_client.is_closed
    assert not hasattr(main.app.state, "default_kline_provider")
    assert not hasattr(main.app.state, "default_quote_provider")
    assert not hasattr(main.app.state, "default_ifind_provider")
    assert not hasattr(main.app.state, "default_tdx_provider")
