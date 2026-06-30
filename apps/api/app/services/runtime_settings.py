from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.config import Settings
from app.services.notification_channels import (
    NotificationChannelConfig,
    NotificationSettings,
    public_notification_settings,
)
from app.services.sentiment_monitor import SentimentMonitorConfig

CandidateProviderName = Literal["recent_limit_up", "thsdk"]
KlineProviderName = Literal["tickflow"]
QuoteProviderName = Literal["tickflow"]
IfindServiceId = Literal[
    "hexin-ifind-ds-stock-mcp",
    "hexin-ifind-ds-news-mcp",
    "hexin-ifind-ds-index-mcp",
]


class RuntimeSettings(BaseModel):
    candidate_provider: CandidateProviderName | None = None
    kline_provider: KlineProviderName | None = None
    quote_provider: QuoteProviderName | None = None
    tickflow_api_key: str | None = None
    tickflow_base_url: str | None = None
    ifind_api_key: str | None = None
    ifind_base_url: str | None = None
    ifind_service_id: IfindServiceId | None = None
    tdx_api_key: str | None = None
    tdx_base_url: str | None = None
    provider_timeout_seconds: float | None = Field(default=None, ge=1, le=60)
    notification_channels: list[NotificationChannelConfig] = Field(default_factory=list)
    sentiment_monitor: SentimentMonitorConfig = Field(default_factory=SentimentMonitorConfig)


class SettingsUpdate(BaseModel):
    candidate_provider: CandidateProviderName
    kline_provider: KlineProviderName
    quote_provider: QuoteProviderName
    tickflow_api_key: str | None = None
    tickflow_base_url: str
    ifind_api_key: str | None = None
    ifind_base_url: str = "https://api-mcp.51ifind.com:8643"
    ifind_service_id: IfindServiceId = "hexin-ifind-ds-stock-mcp"
    tdx_api_key: str | None = None
    tdx_base_url: str = "https://mcp.tdx.com.cn:3001/mcp"
    provider_timeout_seconds: float = Field(ge=1, le=60)
    notification_channels: list[NotificationChannelConfig] = Field(default_factory=list)
    sentiment_monitor: SentimentMonitorConfig = Field(default_factory=SentimentMonitorConfig)


class EffectiveRuntimeSettings(BaseModel):
    candidate_provider: CandidateProviderName
    kline_provider: KlineProviderName
    quote_provider: QuoteProviderName
    tickflow_api_key: str
    tickflow_base_url: str
    ifind_api_key: str
    ifind_base_url: str
    ifind_service_id: IfindServiceId
    tdx_api_key: str
    tdx_base_url: str
    provider_timeout_seconds: float
    runtime_config_path: str
    tickflow_api_key_source: Literal["runtime", "env", "none"]
    ifind_api_key_source: Literal["runtime", "env", "none"]
    tdx_api_key_source: Literal["runtime", "env", "none"]


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
            "ifind_base_url": update.ifind_base_url.strip(),
            "ifind_service_id": update.ifind_service_id,
            "tdx_base_url": update.tdx_base_url.strip(),
            "provider_timeout_seconds": update.provider_timeout_seconds,
            "notification_channels": _merge_notification_channels(
                current.notification_channels,
                update.notification_channels,
            ),
            "sentiment_monitor": update.sentiment_monitor,
        }
    )
    if update.tickflow_api_key is not None:
        next_settings = next_settings.model_copy(update={"tickflow_api_key": update.tickflow_api_key.strip()})
    if update.ifind_api_key is not None:
        next_settings = next_settings.model_copy(update={"ifind_api_key": update.ifind_api_key.strip()})
    if update.tdx_api_key is not None:
        next_settings = next_settings.model_copy(update={"tdx_api_key": update.tdx_api_key.strip()})
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

    runtime_ifind_key = runtime.ifind_api_key or ""
    env_ifind_key = base.ifind_api_key or ""
    if runtime_ifind_key:
        ifind_key_source: Literal["runtime", "env", "none"] = "runtime"
    elif env_ifind_key:
        ifind_key_source = "env"
    else:
        ifind_key_source = "none"

    runtime_tdx_key = runtime.tdx_api_key or ""
    env_tdx_key = base.tdx_api_key or ""
    if runtime_tdx_key:
        tdx_key_source: Literal["runtime", "env", "none"] = "runtime"
    elif env_tdx_key:
        tdx_key_source = "env"
    else:
        tdx_key_source = "none"

    return EffectiveRuntimeSettings(
        candidate_provider=(runtime.candidate_provider or base.candidate_provider),  # type: ignore[arg-type]
        kline_provider=(runtime.kline_provider or base.kline_provider),  # type: ignore[arg-type]
        quote_provider=(runtime.quote_provider or base.quote_provider),  # type: ignore[arg-type]
        tickflow_api_key=runtime_key or env_key,
        tickflow_base_url=(runtime.tickflow_base_url or base.tickflow_base_url).rstrip("/"),
        ifind_api_key=runtime_ifind_key or env_ifind_key,
        ifind_base_url=(runtime.ifind_base_url or base.ifind_base_url).rstrip("/"),
        ifind_service_id=(runtime.ifind_service_id or base.ifind_service_id),  # type: ignore[arg-type]
        tdx_api_key=runtime_tdx_key or env_tdx_key,
        tdx_base_url=(runtime.tdx_base_url or base.tdx_base_url).rstrip("/"),
        provider_timeout_seconds=runtime.provider_timeout_seconds or base.provider_timeout_seconds,
        runtime_config_path=str(path),
        tickflow_api_key_source=key_source,
        ifind_api_key_source=ifind_key_source,
        tdx_api_key_source=tdx_key_source,
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
        "ifind_api_key_configured": bool(config.ifind_api_key),
        "ifind_api_key_preview": _mask_key(config.ifind_api_key),
        "ifind_api_key_source": config.ifind_api_key_source,
        "ifind_base_url": config.ifind_base_url,
        "ifind_service_id": config.ifind_service_id,
        "tdx_api_key_configured": bool(config.tdx_api_key),
        "tdx_api_key_preview": _mask_key(config.tdx_api_key),
        "tdx_api_key_source": config.tdx_api_key_source,
        "tdx_base_url": config.tdx_base_url,
        "provider_timeout_seconds": config.provider_timeout_seconds,
        "runtime_config_path": config.runtime_config_path,
        "notifications": public_notification_settings(
            NotificationSettings(
                channels=load_runtime_settings(Path(config.runtime_config_path)).notification_channels
            )
        ),
        "sentiment_monitor": load_runtime_settings(Path(config.runtime_config_path))
        .sentiment_monitor.model_dump(mode="json"),
    }


def _mask_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}...{value[-4:]}"


def _merge_notification_channels(
    current: list[NotificationChannelConfig],
    update: list[NotificationChannelConfig],
) -> list[NotificationChannelConfig]:
    current_by_id = {channel.id: channel for channel in current}
    merged: list[NotificationChannelConfig] = []
    for channel in update:
        existing = current_by_id.get(channel.id)
        if existing is None:
            merged.append(_strip_channel_strings(channel))
            continue
        data = channel.model_dump()
        for secret_key in ("webhook_url", "bot_token", "smtp_password"):
            if not data.get(secret_key):
                data[secret_key] = getattr(existing, secret_key)
        merged.append(_strip_channel_strings(NotificationChannelConfig.model_validate(data)))
    return merged


def _strip_channel_strings(channel: NotificationChannelConfig) -> NotificationChannelConfig:
    data = channel.model_dump()
    for key, value in list(data.items()):
        if isinstance(value, str):
            data[key] = value.strip()
    data["smtp_recipients"] = [recipient.strip() for recipient in channel.smtp_recipients if recipient.strip()]
    return NotificationChannelConfig.model_validate(data)
