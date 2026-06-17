from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.config import Settings

CandidateProviderName = Literal["recent_limit_up", "thsdk"]
KlineProviderName = Literal["tickflow"]
QuoteProviderName = Literal["tickflow"]


class RuntimeSettings(BaseModel):
    candidate_provider: CandidateProviderName | None = None
    kline_provider: KlineProviderName | None = None
    quote_provider: QuoteProviderName | None = None
    tickflow_api_key: str | None = None
    tickflow_base_url: str | None = None
    provider_timeout_seconds: float | None = Field(default=None, ge=1, le=60)


class SettingsUpdate(BaseModel):
    candidate_provider: CandidateProviderName
    kline_provider: KlineProviderName
    quote_provider: QuoteProviderName
    tickflow_api_key: str | None = None
    tickflow_base_url: str
    provider_timeout_seconds: float = Field(ge=1, le=60)


class EffectiveRuntimeSettings(BaseModel):
    candidate_provider: CandidateProviderName
    kline_provider: KlineProviderName
    quote_provider: QuoteProviderName
    tickflow_api_key: str
    tickflow_base_url: str
    provider_timeout_seconds: float
    runtime_config_path: str
    tickflow_api_key_source: Literal["runtime", "env", "none"]


def load_runtime_settings(path: Path) -> RuntimeSettings:
    if not path.exists():
        return RuntimeSettings()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return RuntimeSettings()
    return RuntimeSettings.model_validate(payload)


def save_runtime_settings(path: Path, update: SettingsUpdate) -> RuntimeSettings:
    current = load_runtime_settings(path)
    next_settings = current.model_copy(
        update={
            "candidate_provider": update.candidate_provider,
            "kline_provider": update.kline_provider,
            "quote_provider": update.quote_provider,
            "tickflow_base_url": update.tickflow_base_url.strip(),
            "provider_timeout_seconds": update.provider_timeout_seconds,
        }
    )
    if update.tickflow_api_key is not None:
        next_settings = next_settings.model_copy(update={"tickflow_api_key": update.tickflow_api_key.strip()})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        next_settings.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )
    return next_settings


def effective_runtime_settings(base: Settings, path: Path) -> EffectiveRuntimeSettings:
    runtime = load_runtime_settings(path)
    runtime_key = runtime.tickflow_api_key or ""
    env_key = base.tickflow_api_key or ""
    if runtime_key:
        key_source: Literal["runtime", "env", "none"] = "runtime"
    elif env_key:
        key_source = "env"
    else:
        key_source = "none"

    return EffectiveRuntimeSettings(
        candidate_provider=(runtime.candidate_provider or base.candidate_provider),  # type: ignore[arg-type]
        kline_provider=(runtime.kline_provider or base.kline_provider),  # type: ignore[arg-type]
        quote_provider=(runtime.quote_provider or base.quote_provider),  # type: ignore[arg-type]
        tickflow_api_key=runtime_key or env_key,
        tickflow_base_url=(runtime.tickflow_base_url or base.tickflow_base_url).rstrip("/"),
        provider_timeout_seconds=runtime.provider_timeout_seconds or base.provider_timeout_seconds,
        runtime_config_path=str(path),
        tickflow_api_key_source=key_source,
    )


def public_settings_payload(config: EffectiveRuntimeSettings) -> dict[str, object]:
    return {
        "candidate_provider": config.candidate_provider,
        "kline_provider": config.kline_provider,
        "quote_provider": config.quote_provider,
        "tickflow_api_key_configured": bool(config.tickflow_api_key),
        "tickflow_api_key_preview": _mask_key(config.tickflow_api_key),
        "tickflow_api_key_source": config.tickflow_api_key_source,
        "tickflow_base_url": config.tickflow_base_url,
        "provider_timeout_seconds": config.provider_timeout_seconds,
        "runtime_config_path": config.runtime_config_path,
    }


def _mask_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}...{value[-4:]}"
