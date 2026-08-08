"""数据源 provider 装配注册表。

从 deps.py 拆出的纯数据源装配工厂：每个工厂按运行时配置实例化并缓存
数据源 provider（日K/实时行情/市场概览/指数/分钟历史等），实例挂在
app_state().state 上，由 deps._close_default_data_source_providers 统一关闭。

约定（与 deps 拆分时的 compat 转发层同一哲学）：
- 本模块不直接 import deps（避免循环导入）；对 app_state/_effective_settings/
  _cached_default_provider/get_settings 的引用一律经 _deps() 运行时惰性获取——
  这样测试 patch deps.X 仍实时生效（运行时绑定而非 import 时绑定）。
- 工厂之间的交叉调用（如 _market_overview_provider → _quote_provider）同样走
  deps 转发，保证被 patch 的工厂能替换内部依赖。
- deps.py 保留同名薄转发函数，compat/main/helpers 消费链不变。
"""

from __future__ import annotations

from typing import Any

from app.providers.concept_blocks import EastmoneyConceptBlockProvider
from app.providers.eastmoney_kline import EastmoneyKlineProvider
from app.providers.eastmoney_minute_history import EastmoneyMinuteHistoryProvider
from app.providers.eastmoney_quote import EastmoneyQuoteProvider
from app.providers.heatmap import HeatmapProvider
from app.providers.ifind import IfindMcpProvider
from app.providers.market_overview import EastmoneyMarketOverviewProvider
from app.providers.news_risk import EastmoneyNewsRiskProvider
from app.providers.recent_limit_up_candidates import RecentLimitUpCandidateProvider
from app.providers.tdx_mcp import TdxMcpProvider
from app.providers.tencent_quote import TencentQuoteProvider
from app.providers.thsdk_candidates import ThsdkCandidateProvider
from app.providers.tickflow import TickFlowDailyKlineProvider, TickFlowQuoteProvider
from app.services.plate_rotation_reference import PlateRotationReferenceProvider
from app.services.sector_replica_live import SectorReplicaLiveProvider


def _deps() -> Any:
    """运行时惰性获取 deps 模块，避免 registry↔deps 循环导入。"""
    from app import deps  # noqa: PLC0415

    return deps


def _sector_replica_live_provider() -> object:
    deps = _deps()
    injected = getattr(deps.app_state().state, "sector_replica_live_provider", None)
    if injected is not None:
        return injected
    settings = deps._effective_settings()
    provider = SectorReplicaLiveProvider(timeout_seconds=settings.provider_timeout_seconds)
    deps.app_state().state.sector_replica_live_provider = provider
    return provider


def _plate_rotation_reference_provider() -> object:
    deps = _deps()
    injected = getattr(deps.app_state().state, "plate_rotation_reference_provider", None)
    if injected is not None:
        return injected
    settings = deps._effective_settings()
    provider = PlateRotationReferenceProvider(timeout_seconds=settings.provider_timeout_seconds)
    deps.app_state().state.plate_rotation_reference_provider = provider
    return provider


def _market_overview_provider() -> object:
    deps = _deps()
    injected = getattr(deps.app_state().state, "market_overview_provider", None)
    if injected is not None:
        return injected
    settings = deps._effective_settings()
    base_settings = deps.get_settings()
    quote_provider = deps._quote_provider()
    ifind_provider = deps._ifind_provider()
    kline_provider = deps._kline_provider()
    return deps._cached_default_provider(
        attribute="default_market_overview_provider",
        key=(
            settings.provider_timeout_seconds,
            id(quote_provider),
            id(ifind_provider),
            id(kline_provider),
            str(base_settings.data_dir),
        ),
        factory=lambda: EastmoneyMarketOverviewProvider(
            timeout_seconds=settings.provider_timeout_seconds,
            realtime_quote_provider=quote_provider,
            ifind_index_provider=ifind_provider,
            ifind_stock_provider=ifind_provider,
            daily_kline_provider=kline_provider,
            turnover_cache_path=base_settings.data_dir / "market-overview" / "turnover-history.json",
            sentiment_snapshot_dir=base_settings.data_dir / "sentiment_snapshots",
        ),
    )


def _ifind_provider() -> IfindMcpProvider:
    deps = _deps()
    injected = getattr(deps.app_state().state, "ifind_provider", None)
    if injected is not None:
        return injected
    settings = deps._effective_settings()
    return deps._cached_default_provider(
        attribute="default_ifind_provider",
        key=(
            settings.ifind_api_key,
            settings.ifind_base_url,
            settings.provider_timeout_seconds,
            settings.ifind_service_id,
        ),
        factory=lambda: IfindMcpProvider(
            api_key=settings.ifind_api_key,
            base_url=settings.ifind_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            http_client=getattr(deps.app_state().state, "ifind_http_client", None),
        ),
    )


def _chanlun_history_provider() -> EastmoneyMinuteHistoryProvider:
    deps = _deps()
    injected = getattr(deps.app_state().state, "chanlun_history_provider", None)
    if injected is not None:
        return injected
    settings = deps.get_settings()
    provider = EastmoneyMinuteHistoryProvider(
        enabled=settings.chanlun_tdx_enabled,
        timeout_seconds=max(
            settings.chanlun_tdx_timeout_seconds, settings.provider_timeout_seconds
        ),
    )
    deps.app_state().state.chanlun_history_provider = provider
    return provider


def _tdx_provider() -> TdxMcpProvider:
    deps = _deps()
    injected = getattr(deps.app_state().state, "tdx_provider", None)
    if injected is not None:
        return injected
    settings = deps._effective_settings()
    return deps._cached_default_provider(
        attribute="default_tdx_provider",
        key=(settings.tdx_api_key, settings.tdx_base_url, settings.provider_timeout_seconds),
        factory=lambda: TdxMcpProvider(
            api_key=settings.tdx_api_key,
            base_url=settings.tdx_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            http_client=getattr(deps.app_state().state, "tdx_http_client", None),
        ),
    )


def _heatmap_provider() -> HeatmapProvider:
    deps = _deps()
    provider = getattr(deps.app_state().state, "heatmap_provider", None)
    if provider is None:
        settings = deps.get_settings()
        provider = HeatmapProvider(
            turnover_cache_path=settings.data_dir / "heatmap" / "turnover-history.json"
        )
        deps.app_state().state.heatmap_provider = provider
    return provider


def _concept_provider() -> object:
    deps = _deps()
    injected = getattr(deps.app_state().state, "concept_provider", None)
    if injected is not None:
        return injected
    cached = getattr(deps.app_state().state, "default_concept_provider", None)
    if cached is None:
        settings = deps._effective_settings()
        cached = EastmoneyConceptBlockProvider(timeout_seconds=settings.provider_timeout_seconds)
        deps.app_state().state.default_concept_provider = cached
    return cached


def _news_risk_provider() -> object:
    deps = _deps()
    injected = getattr(deps.app_state().state, "news_risk_provider", None)
    if injected is not None:
        return injected
    return EastmoneyNewsRiskProvider.from_akshare()


def _valuation_quote_provider() -> object:
    deps = _deps()
    injected = getattr(deps.app_state().state, "valuation_quote_provider", None)
    if injected is not None:
        return injected
    settings = deps._effective_settings()
    return deps._cached_default_provider(
        attribute="default_valuation_quote_provider",
        key=(settings.provider_timeout_seconds,),
        factory=lambda: TencentQuoteProvider(timeout_seconds=settings.provider_timeout_seconds),
    )


def _quote_provider() -> object:
    deps = _deps()
    injected = getattr(deps.app_state().state, "quote_provider", None)
    if injected is not None:
        return injected
    settings = deps._effective_settings()
    if getattr(settings, "quote_provider", "eastmoney") == "eastmoney":
        return deps._cached_default_provider(
            attribute="default_quote_provider",
            key=("eastmoney", settings.provider_timeout_seconds),
            factory=lambda: EastmoneyQuoteProvider(
                timeout_seconds=settings.provider_timeout_seconds,
            ),
        )
    return deps._cached_default_provider(
        attribute="default_quote_provider",
        key=(settings.tickflow_api_key, settings.tickflow_base_url, settings.provider_timeout_seconds),
        factory=lambda: TickFlowQuoteProvider(
            api_key=settings.tickflow_api_key,
            base_url=settings.tickflow_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
        ),
    )


def _chanlun_daily_provider() -> object:
    deps = _deps()
    injected = getattr(deps.app_state().state, "kline_provider", None)
    if injected is not None:
        return injected
    settings = deps._effective_settings()
    if getattr(settings, "kline_provider", "eastmoney") == "eastmoney":
        return deps._cached_default_provider(
            attribute="default_chanlun_daily_provider",
            key=("eastmoney", settings.provider_timeout_seconds),
            factory=lambda: EastmoneyKlineProvider(
                timeout_seconds=settings.provider_timeout_seconds,
                adjust="none",
            ),
        )
    return deps._cached_default_provider(
        attribute="default_chanlun_daily_provider",
        key=(settings.tickflow_api_key, settings.tickflow_base_url, settings.provider_timeout_seconds),
        factory=lambda: TickFlowDailyKlineProvider(
            api_key=settings.tickflow_api_key,
            base_url=settings.tickflow_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            adjust="none",
        ),
    )


def _daily_kline_provider() -> object:
    return _kline_provider()


def _kline_provider() -> object:
    deps = _deps()
    injected = getattr(deps.app_state().state, "kline_provider", None)
    if injected is not None:
        return injected
    settings = deps._effective_settings()
    provider_name = getattr(settings, "kline_provider", "eastmoney")
    if provider_name == "eastmoney":
        return deps._cached_default_provider(
            attribute="default_kline_provider",
            key=("eastmoney", settings.provider_timeout_seconds),
            factory=lambda: EastmoneyKlineProvider(
                timeout_seconds=settings.provider_timeout_seconds,
                adjust="forward",
            ),
        )
    return deps._cached_default_provider(
        attribute="default_kline_provider",
        key=(settings.tickflow_api_key, settings.tickflow_base_url, settings.provider_timeout_seconds),
        factory=lambda: TickFlowDailyKlineProvider(
            api_key=settings.tickflow_api_key,
            base_url=settings.tickflow_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
        ),
    )


def _candidate_provider() -> object:
    deps = _deps()
    injected = getattr(deps.app_state().state, "candidate_provider", None)
    if injected is not None:
        return injected
    settings = deps._effective_settings()
    if settings.candidate_provider == "thsdk":
        return ThsdkCandidateProvider.from_installed_package()
    return RecentLimitUpCandidateProvider.from_akshare()
