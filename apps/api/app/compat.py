"""跨模块转发层。

让 routers/lifespan 通过运行时转发访问 deps/helpers 的下划线可调用符号，
使得测试 patch deps.X / helpers.X 时对所有消费方实时生效。

循环依赖约束：compat 只依赖 deps/helpers（及 models 等叶子模块），
不依赖 main/lifespan/routers。
"""

from __future__ import annotations

import app.deps as _deps
import app.helpers as _helpers
from app.services.common import dedupe_symbols as _dedupe_symbols

# 值转发（公开常量）：
from app.deps import (
    AUCTION_SNAPSHOT_CACHE,
    CACHE_DEFINITIONS,
    CACHE_GROUPS,
    CACHE_REGISTRY,
    CAPITAL_SUMMARY_CACHE,
    MARKET_EMOTION_CACHE,
    MARKET_OVERVIEW_CACHE,
    MARKET_RANKINGS_CACHE,
    PLATE_ROTATION_REFERENCE_CACHE,
    SECTOR_INTRADAY_CACHE,
    SECTOR_RADAR_CACHE,
    SECTOR_STOCK_INDUSTRY_TIMEOUT_SECONDS,
    SECTOR_THEME_ROWS_CACHE,
    SHORT_TERM_SENTIMENT_CACHE,
    STOCK_KLINE_CACHE,
    STOCK_RESEARCH_CACHE,
    WATCHLIST_GSGF_CACHE,
    app_state,
    bind_app,
    logger,
)

# 值转发（下划线常量/单例）：
from app.deps import (
    _CHANLUN_RESEARCH_LOCK,
    _MARKET_EMOTION_HISTORY_WRITE_LOCK,
    _MARKET_EMOTION_SAMPLE_INTERVAL,
    _WATCHLIST_GSGF_MAX_SYMBOLS,
    _app,
)

from app.helpers import (
    _MARKET_SENTIMENT_ANALYSIS_CATCHUP_DATES,
    _MARKET_SENTIMENT_ANALYSIS_CATCHUP_LOCK,
)

# 下划线可调用 → 运行时转发包装器

def _auction_model_result_store(*args, **kwargs):
    return _deps._auction_model_result_store(*args, **kwargs)

def _auction_model_service(*args, **kwargs):
    return _deps._auction_model_service(*args, **kwargs)

def _auction_review_store(*args, **kwargs):
    return _deps._auction_review_store(*args, **kwargs)

def _auction_snapshot_store(*args, **kwargs):
    return _deps._auction_snapshot_store(*args, **kwargs)

def _auction_top3_live_confirmation_store(*args, **kwargs):
    return _deps._auction_top3_live_confirmation_store(*args, **kwargs)

def _auction_top3_training_store(*args, **kwargs):
    return _deps._auction_top3_training_store(*args, **kwargs)

def _background_job_store(*args, **kwargs):
    return _deps._background_job_store(*args, **kwargs)

def _build_and_persist_sentiment_snapshots(*args, **kwargs):
    return _deps._build_and_persist_sentiment_snapshots(*args, **kwargs)

def _build_market_sentiment_analysis_input(*args, **kwargs):
    return _deps._build_market_sentiment_analysis_input(*args, **kwargs)

def _cached_default_provider(*args, **kwargs):
    return _deps._cached_default_provider(*args, **kwargs)

def _cached_market_overview(*args, **kwargs):
    return _deps._cached_market_overview(*args, **kwargs)

def _cached_short_term_sentiment(*args, **kwargs):
    return _deps._cached_short_term_sentiment(*args, **kwargs)

def _candidate_provider(*args, **kwargs):
    return _deps._candidate_provider(*args, **kwargs)

def _capital_signal_service(*args, **kwargs):
    return _deps._capital_signal_service(*args, **kwargs)

def _chanlun_adapter(*args, **kwargs):
    return _deps._chanlun_adapter(*args, **kwargs)

def _chanlun_alert_service(*args, **kwargs):
    return _deps._chanlun_alert_service(*args, **kwargs)

def _chanlun_alert_store(*args, **kwargs):
    return _deps._chanlun_alert_store(*args, **kwargs)

def _chanlun_analysis_service(*args, **kwargs):
    return _deps._chanlun_analysis_service(*args, **kwargs)

def _chanlun_daily_provider(*args, **kwargs):
    return _deps._chanlun_daily_provider(*args, **kwargs)

def _chanlun_history_provider(*args, **kwargs):
    return _deps._chanlun_history_provider(*args, **kwargs)

def _chanlun_minute_store(*args, **kwargs):
    return _deps._chanlun_minute_store(*args, **kwargs)

def _chanlun_paper_order_service(*args, **kwargs):
    return _deps._chanlun_paper_order_service(*args, **kwargs)

def _chanlun_paper_order_store(*args, **kwargs):
    return _deps._chanlun_paper_order_store(*args, **kwargs)

def _chanlun_rc8_client(*args, **kwargs):
    return _deps._chanlun_rc8_client(*args, **kwargs)

def _chanlun_research_catalog(*args, **kwargs):
    return _deps._chanlun_research_catalog(*args, **kwargs)

def _chanlun_research_service(*args, **kwargs):
    return _deps._chanlun_research_service(*args, **kwargs)

def _chanlun_research_store(*args, **kwargs):
    return _deps._chanlun_research_store(*args, **kwargs)

def _chanlun_shadow_scheduler(*args, **kwargs):
    return _deps._chanlun_shadow_scheduler(*args, **kwargs)

def _chanlun_symbol_search_service(*args, **kwargs):
    return _deps._chanlun_symbol_search_service(*args, **kwargs)

def _close_default_data_source_providers(*args, **kwargs):
    return _deps._close_default_data_source_providers(*args, **kwargs)

def _close_provider(*args, **kwargs):
    return _deps._close_provider(*args, **kwargs)

def _concept_provider(*args, **kwargs):
    return _deps._concept_provider(*args, **kwargs)

def _cors_allow_origin_regex(*args, **kwargs):
    return _deps._cors_allow_origin_regex(*args, **kwargs)

def _cors_allow_origins(*args, **kwargs):
    return _deps._cors_allow_origins(*args, **kwargs)

def _daily_kline_provider(*args, **kwargs):
    return _deps._daily_kline_provider(*args, **kwargs)

def _effective_settings(*args, **kwargs):
    return _deps._effective_settings(*args, **kwargs)

def _etf_excess_flow_service(*args, **kwargs):
    return _deps._etf_excess_flow_service(*args, **kwargs)

def _etf_price_history_service(*args, **kwargs):
    return _deps._etf_price_history_service(*args, **kwargs)

def _etf_three_factor_monitor(*args, **kwargs):
    return _deps._etf_three_factor_monitor(*args, **kwargs)

def _generate_latest_market_sentiment_analysis(*args, **kwargs):
    return _deps._generate_latest_market_sentiment_analysis(*args, **kwargs)

def _generate_market_sentiment_analysis(*args, **kwargs):
    return _deps._generate_market_sentiment_analysis(*args, **kwargs)

def _gsgf_auto_review_service(*args, **kwargs):
    return _deps._gsgf_auto_review_service(*args, **kwargs)

def _gsgf_model_health(*args, **kwargs):
    return _deps._gsgf_model_health(*args, **kwargs)

def _gsgf_review_store(*args, **kwargs):
    return _deps._gsgf_review_store(*args, **kwargs)

def _heatmap_provider(*args, **kwargs):
    return _deps._heatmap_provider(*args, **kwargs)

def _ifind_provider(*args, **kwargs):
    return _deps._ifind_provider(*args, **kwargs)

def _kline_provider(*args, **kwargs):
    return _deps._kline_provider(*args, **kwargs)

def _latest_completed_market_sentiment_trade_date(*args, **kwargs):
    return _deps._latest_completed_market_sentiment_trade_date(*args, **kwargs)

def _latest_market_emotion_sampled_at(*args, **kwargs):
    return _deps._latest_market_emotion_sampled_at(*args, **kwargs)

def _load_sentiment_validation(*args, **kwargs):
    return _deps._load_sentiment_validation(*args, **kwargs)

def _market_emotion_history_store(*args, **kwargs):
    return _deps._market_emotion_history_store(*args, **kwargs)

def _market_overview_provider(*args, **kwargs):
    return _deps._market_overview_provider(*args, **kwargs)

def _market_sentiment_analysis_sampler(*args, **kwargs):
    return _deps._market_sentiment_analysis_sampler(*args, **kwargs)

def _market_sentiment_analysis_service(*args, **kwargs):
    return _deps._market_sentiment_analysis_service(*args, **kwargs)

def _market_sentiment_analysis_store(*args, **kwargs):
    return _deps._market_sentiment_analysis_store(*args, **kwargs)

def _market_sentiment_percentile_service(*args, **kwargs):
    return _deps._market_sentiment_percentile_service(*args, **kwargs)

def _market_sentiment_percentile_store(*args, **kwargs):
    return _deps._market_sentiment_percentile_store(*args, **kwargs)

def _model_maintenance_store(*args, **kwargs):
    return _deps._model_maintenance_store(*args, **kwargs)

def _news_risk_provider(*args, **kwargs):
    return _deps._news_risk_provider(*args, **kwargs)

def _optional_sentiment_analysis_context(*args, **kwargs):
    return _deps._optional_sentiment_analysis_context(*args, **kwargs)

def _percentile_point_for_trade_date(*args, **kwargs):
    return _deps._percentile_point_for_trade_date(*args, **kwargs)

def _plate_rotation_reference_provider(*args, **kwargs):
    return _deps._plate_rotation_reference_provider(*args, **kwargs)

def _provider_cache_key(*args, **kwargs):
    return _deps._provider_cache_key(*args, **kwargs)

def _public_saved_settings(*args, **kwargs):
    return _deps._public_saved_settings(*args, **kwargs)

def _quote_provider(*args, **kwargs):
    return _deps._quote_provider(*args, **kwargs)

def _recent_screen_trade_dates(*args, **kwargs):
    return _deps._recent_screen_trade_dates(*args, **kwargs)

def _run_gsgf_daily_review(*args, **kwargs):
    return _deps._run_gsgf_daily_review(*args, **kwargs)

def _run_store(*args, **kwargs):
    return _deps._run_store(*args, **kwargs)

def _runtime_config_path(*args, **kwargs):
    return _deps._runtime_config_path(*args, **kwargs)

def _sanitized_health_error(*args, **kwargs):
    return _deps._sanitized_health_error(*args, **kwargs)

def _sector_replica_live_provider(*args, **kwargs):
    return _deps._sector_replica_live_provider(*args, **kwargs)

def _sector_theme_rows_store(*args, **kwargs):
    return _deps._sector_theme_rows_store(*args, **kwargs)

def _sector_workbench_store(*args, **kwargs):
    return _deps._sector_workbench_store(*args, **kwargs)

def _send_sentiment_monitor_notification(*args, **kwargs):
    return _deps._send_sentiment_monitor_notification(*args, **kwargs)

def _sentiment_monitor(*args, **kwargs):
    return _deps._sentiment_monitor(*args, **kwargs)

def _sentiment_review_store(*args, **kwargs):
    return _deps._sentiment_review_store(*args, **kwargs)

def _sentiment_snapshot_store(*args, **kwargs):
    return _deps._sentiment_snapshot_store(*args, **kwargs)

def _should_persist_market_emotion_sample(*args, **kwargs):
    return _deps._should_persist_market_emotion_sample(*args, **kwargs)

def _start_gsgf_weekly_calibration(*args, **kwargs):
    return _deps._start_gsgf_weekly_calibration(*args, **kwargs)

def _tdx_provider(*args, **kwargs):
    return _deps._tdx_provider(*args, **kwargs)

def _valuation_quote_provider(*args, **kwargs):
    return _deps._valuation_quote_provider(*args, **kwargs)

def _watchlist_path(*args, **kwargs):
    return _deps._watchlist_path(*args, **kwargs)

def _watchlist_snapshot(*args, **kwargs):
    return _deps._watchlist_snapshot(*args, **kwargs)

def _append_empty_hot_theme_status(*args, **kwargs):
    return _helpers._append_empty_hot_theme_status(*args, **kwargs)

def _attribute_running_status(*args, **kwargs):
    return _helpers._attribute_running_status(*args, **kwargs)

def _auction_hot_theme_refs(*args, **kwargs):
    return _helpers._auction_hot_theme_refs(*args, **kwargs)

def _auction_model_result_store(*args, **kwargs):
    return _helpers._auction_model_result_store(*args, **kwargs)

def _auction_model_service(*args, **kwargs):
    return _helpers._auction_model_service(*args, **kwargs)

def _auction_now(*args, **kwargs):
    return _helpers._auction_now(*args, **kwargs)

def _auction_review_minute_bars(*args, **kwargs):
    return _helpers._auction_review_minute_bars(*args, **kwargs)

def _auction_review_quote_day_outcome(*args, **kwargs):
    return _helpers._auction_review_quote_day_outcome(*args, **kwargs)

def _auction_review_selected_at(*args, **kwargs):
    return _helpers._auction_review_selected_at(*args, **kwargs)

def _auction_review_summary(*args, **kwargs):
    return _helpers._auction_review_summary(*args, **kwargs)

def _auction_sampler_running_status(*args, **kwargs):
    return _helpers._auction_sampler_running_status(*args, **kwargs)

def _auction_snapshot_store(*args, **kwargs):
    return _helpers._auction_snapshot_store(*args, **kwargs)

def _auction_top3_training_store(*args, **kwargs):
    return _helpers._auction_top3_training_store(*args, **kwargs)

def _backfill_auction_snapshot_industries(*args, **kwargs):
    return _helpers._backfill_auction_snapshot_industries(*args, **kwargs)

def _background_job_store(*args, **kwargs):
    return _helpers._background_job_store(*args, **kwargs)

def _build_and_save_model_maintenance_packet(*args, **kwargs):
    return _helpers._build_and_save_model_maintenance_packet(*args, **kwargs)

def _build_market_sentiment_analysis_input(*args, **kwargs):
    return _helpers._build_market_sentiment_analysis_input(*args, **kwargs)

def _build_sector_theme_rows(*args, **kwargs):
    return _helpers._build_sector_theme_rows(*args, **kwargs)

def _build_watchlist_gsgf_status(*args, **kwargs):
    return _helpers._build_watchlist_gsgf_status(*args, **kwargs)

def _cached_auction_snapshot(*args, **kwargs):
    return _helpers._cached_auction_snapshot(*args, **kwargs)

def _cached_capital_summary(*args, **kwargs):
    return _helpers._cached_capital_summary(*args, **kwargs)

def _cached_market_overview(*args, **kwargs):
    return _helpers._cached_market_overview(*args, **kwargs)

def _cached_market_rankings(*args, **kwargs):
    return _helpers._cached_market_rankings(*args, **kwargs)

def _cached_sector_intraday_series(*args, **kwargs):
    return _helpers._cached_sector_intraday_series(*args, **kwargs)

def _cached_sector_intraday_status(*args, **kwargs):
    return _helpers._cached_sector_intraday_status(*args, **kwargs)

def _cached_sector_radar(*args, **kwargs):
    return _helpers._cached_sector_radar(*args, **kwargs)

def _cached_stock_kline(*args, **kwargs):
    return _helpers._cached_stock_kline(*args, **kwargs)

def _cached_stock_research(*args, **kwargs):
    return _helpers._cached_stock_research(*args, **kwargs)

def _candidate_provider(*args, **kwargs):
    return _helpers._candidate_provider(*args, **kwargs)

def _capital_signal_service(*args, **kwargs):
    return _helpers._capital_signal_service(*args, **kwargs)

def _chanlun_adapter(*args, **kwargs):
    return _helpers._chanlun_adapter(*args, **kwargs)

def _chanlun_minute_store(*args, **kwargs):
    return _helpers._chanlun_minute_store(*args, **kwargs)

def _chanlun_research_health(*args, **kwargs):
    return _helpers._chanlun_research_health(*args, **kwargs)

def _chanlun_research_service(*args, **kwargs):
    return _helpers._chanlun_research_service(*args, **kwargs)

def _chanlun_screening_summarizer(*args, **kwargs):
    return _helpers._chanlun_screening_summarizer(*args, **kwargs)

def _chanlun_shadow_scheduler(*args, **kwargs):
    return _helpers._chanlun_shadow_scheduler(*args, **kwargs)

def _close_default_data_source_providers(*args, **kwargs):
    return _helpers._close_default_data_source_providers(*args, **kwargs)

def _concept_provider(*args, **kwargs):
    return _helpers._concept_provider(*args, **kwargs)

def _diagnostic_detail(*args, **kwargs):
    return _helpers._diagnostic_detail(*args, **kwargs)

def _effective_settings(*args, **kwargs):
    return _helpers._effective_settings(*args, **kwargs)

def _enrich_sector_replica_stock_rows(*args, **kwargs):
    return _helpers._enrich_sector_replica_stock_rows(*args, **kwargs)

def _estimated_sector_radar(*args, **kwargs):
    return _helpers._estimated_sector_radar(*args, **kwargs)

def _estimated_sector_radar_item(*args, **kwargs):
    return _helpers._estimated_sector_radar_item(*args, **kwargs)

def _execute_screen_run(*args, **kwargs):
    return _helpers._execute_screen_run(*args, **kwargs)

def _execute_screen_run_job(*args, **kwargs):
    return _helpers._execute_screen_run_job(*args, **kwargs)

def _fill_auction_review_close_from_quotes(*args, **kwargs):
    return _helpers._fill_auction_review_close_from_quotes(*args, **kwargs)

def _fill_auction_review_record_close_from_quote(*args, **kwargs):
    return _helpers._fill_auction_review_record_close_from_quote(*args, **kwargs)

def _generate_auction_top3_for_date(*args, **kwargs):
    return _helpers._generate_auction_top3_for_date(*args, **kwargs)

def _generate_market_sentiment_analysis(*args, **kwargs):
    return _helpers._generate_market_sentiment_analysis(*args, **kwargs)

def _gsgf_review_store(*args, **kwargs):
    return _helpers._gsgf_review_store(*args, **kwargs)

def _ifind_provider(*args, **kwargs):
    return _helpers._ifind_provider(*args, **kwargs)

def _intraday_watchlist_items(*args, **kwargs):
    return _helpers._intraday_watchlist_items(*args, **kwargs)

def _kline_provider(*args, **kwargs):
    return _helpers._kline_provider(*args, **kwargs)

def _mark_auction_review_kline_unavailable(*args, **kwargs):
    return _helpers._mark_auction_review_kline_unavailable(*args, **kwargs)

def _market_overview_provider(*args, **kwargs):
    return _helpers._market_overview_provider(*args, **kwargs)

def _market_sentiment_analysis_now(*args, **kwargs):
    return _helpers._market_sentiment_analysis_now(*args, **kwargs)

def _market_sentiment_analysis_store(*args, **kwargs):
    return _helpers._market_sentiment_analysis_store(*args, **kwargs)

def _market_sentiment_percentile_store(*args, **kwargs):
    return _helpers._market_sentiment_percentile_store(*args, **kwargs)

def _model_maintenance_store(*args, **kwargs):
    return _helpers._model_maintenance_store(*args, **kwargs)

def _news_risk_provider(*args, **kwargs):
    return _helpers._news_risk_provider(*args, **kwargs)

def _parse_chanlun_backtest_horizons(*args, **kwargs):
    return _helpers._parse_chanlun_backtest_horizons(*args, **kwargs)

def _persisted_percentile_point_for_trade_date(*args, **kwargs):
    return _helpers._persisted_percentile_point_for_trade_date(*args, **kwargs)

def _plate_rotation_reference_provider(*args, **kwargs):
    return _helpers._plate_rotation_reference_provider(*args, **kwargs)

def _probe(*args, **kwargs):
    return _helpers._probe(*args, **kwargs)

def _provider_cache_key(*args, **kwargs):
    return _helpers._provider_cache_key(*args, **kwargs)

def _quote_pct_from_base(*args, **kwargs):
    return _helpers._quote_pct_from_base(*args, **kwargs)

def _quote_provider(*args, **kwargs):
    return _helpers._quote_provider(*args, **kwargs)

def _quote_time_matches_trade_date(*args, **kwargs):
    return _helpers._quote_time_matches_trade_date(*args, **kwargs)

def _quote_valuation_for_symbol(*args, **kwargs):
    return _helpers._quote_valuation_for_symbol(*args, **kwargs)

def _read_watchlist_pool(*args, **kwargs):
    return _helpers._read_watchlist_pool(*args, **kwargs)

def _refresh_auction_snapshot(*args, **kwargs):
    return _helpers._refresh_auction_snapshot(*args, **kwargs)

def _refresh_market_rankings(*args, **kwargs):
    return _helpers._refresh_market_rankings(*args, **kwargs)

def _refresh_sector_theme_rows(*args, **kwargs):
    return _helpers._refresh_sector_theme_rows(*args, **kwargs)

def _request_base_url(*args, **kwargs):
    return _helpers._request_base_url(*args, **kwargs)

def _run_auction_model_top3_generation_job(*args, **kwargs):
    return _helpers._run_auction_model_top3_generation_job(*args, **kwargs)

def _run_auction_snapshot_refresh_job(*args, **kwargs):
    return _helpers._run_auction_snapshot_refresh_job(*args, **kwargs)

def _run_store(*args, **kwargs):
    return _helpers._run_store(*args, **kwargs)

def _runtime_config_path(*args, **kwargs):
    return _helpers._runtime_config_path(*args, **kwargs)

def _safe_status_running(*args, **kwargs):
    return _helpers._safe_status_running(*args, **kwargs)

def _safe_thread_running(*args, **kwargs):
    return _helpers._safe_thread_running(*args, **kwargs)

def _sanitized_health_error(*args, **kwargs):
    return _helpers._sanitized_health_error(*args, **kwargs)

def _save_sentiment_monitor_config(*args, **kwargs):
    return _helpers._save_sentiment_monitor_config(*args, **kwargs)

def _schedule_market_sentiment_analysis_catchup(*args, **kwargs):
    return _helpers._schedule_market_sentiment_analysis_catchup(*args, **kwargs)

def _schedule_sector_intraday_refresh(*args, **kwargs):
    return _helpers._schedule_sector_intraday_refresh(*args, **kwargs)

def _schedule_sector_theme_rows_refresh(*args, **kwargs):
    return _helpers._schedule_sector_theme_rows_refresh(*args, **kwargs)

def _sector_intraday_cache_key(*args, **kwargs):
    return _helpers._sector_intraday_cache_key(*args, **kwargs)

def _sector_intraday_refresh_key(*args, **kwargs):
    return _helpers._sector_intraday_refresh_key(*args, **kwargs)

def _sector_now(*args, **kwargs):
    return _helpers._sector_now(*args, **kwargs)

def _sector_theme_rows(*args, **kwargs):
    return _helpers._sector_theme_rows(*args, **kwargs)

def _sector_theme_rows_store(*args, **kwargs):
    return _helpers._sector_theme_rows_store(*args, **kwargs)

def _sector_workbench_store(*args, **kwargs):
    return _helpers._sector_workbench_store(*args, **kwargs)

def _sentiment_monitor_running_status(*args, **kwargs):
    return _helpers._sentiment_monitor_running_status(*args, **kwargs)

def _status_unavailable_detail(*args, **kwargs):
    return _helpers._status_unavailable_detail(*args, **kwargs)

def _stock_industry_for_symbol(*args, **kwargs):
    return _helpers._stock_industry_for_symbol(*args, **kwargs)

def _system_job_degraded(*args, **kwargs):
    return _helpers._system_job_degraded(*args, **kwargs)

def _system_jobs(*args, **kwargs):
    return _helpers._system_jobs(*args, **kwargs)

def _tdx_provider(*args, **kwargs):
    return _helpers._tdx_provider(*args, **kwargs)

def _thread_running_status(*args, **kwargs):
    return _helpers._thread_running_status(*args, **kwargs)

def _tickflow_sector_radar(*args, **kwargs):
    return _helpers._tickflow_sector_radar(*args, **kwargs)

def _validate_chanlun_lookback(*args, **kwargs):
    return _helpers._validate_chanlun_lookback(*args, **kwargs)

def _valuation_quote_provider(*args, **kwargs):
    return _helpers._valuation_quote_provider(*args, **kwargs)

def _watchlist_path(*args, **kwargs):
    return _helpers._watchlist_path(*args, **kwargs)

def _watchlist_snapshot(*args, **kwargs):
    return _helpers._watchlist_snapshot(*args, **kwargs)

__all__ = [
    "AUCTION_SNAPSHOT_CACHE",
    "CACHE_DEFINITIONS",
    "CACHE_GROUPS",
    "CACHE_REGISTRY",
    "CAPITAL_SUMMARY_CACHE",
    "MARKET_EMOTION_CACHE",
    "MARKET_OVERVIEW_CACHE",
    "MARKET_RANKINGS_CACHE",
    "PLATE_ROTATION_REFERENCE_CACHE",
    "SECTOR_INTRADAY_CACHE",
    "SECTOR_RADAR_CACHE",
    "SECTOR_STOCK_INDUSTRY_TIMEOUT_SECONDS",
    "SECTOR_THEME_ROWS_CACHE",
    "SHORT_TERM_SENTIMENT_CACHE",
    "STOCK_KLINE_CACHE",
    "STOCK_RESEARCH_CACHE",
    "WATCHLIST_GSGF_CACHE",
    "_CHANLUN_RESEARCH_LOCK",
    "_MARKET_EMOTION_HISTORY_WRITE_LOCK",
    "_MARKET_EMOTION_SAMPLE_INTERVAL",
    "_MARKET_SENTIMENT_ANALYSIS_CATCHUP_DATES",
    "_MARKET_SENTIMENT_ANALYSIS_CATCHUP_LOCK",
    "_WATCHLIST_GSGF_MAX_SYMBOLS",
    "__all__",
    "_app",
    "_append_empty_hot_theme_status",
    "_attribute_running_status",
    "_auction_hot_theme_refs",
    "_auction_model_result_store",
    "_auction_model_service",
    "_auction_now",
    "_auction_review_minute_bars",
    "_auction_review_quote_day_outcome",
    "_auction_review_selected_at",
    "_auction_review_store",
    "_auction_review_summary",
    "_auction_sampler_running_status",
    "_auction_snapshot_store",
    "_auction_top3_live_confirmation_store",
    "_auction_top3_training_store",
    "_backfill_auction_snapshot_industries",
    "_background_job_store",
    "_build_and_persist_sentiment_snapshots",
    "_build_and_save_model_maintenance_packet",
    "_build_market_sentiment_analysis_input",
    "_build_sector_theme_rows",
    "_build_watchlist_gsgf_status",
    "_cached_auction_snapshot",
    "_cached_capital_summary",
    "_cached_default_provider",
    "_cached_market_overview",
    "_cached_market_rankings",
    "_cached_sector_intraday_series",
    "_cached_sector_intraday_status",
    "_cached_sector_radar",
    "_cached_short_term_sentiment",
    "_cached_stock_kline",
    "_cached_stock_research",
    "_candidate_provider",
    "_capital_signal_service",
    "_chanlun_adapter",
    "_chanlun_alert_service",
    "_chanlun_alert_store",
    "_chanlun_analysis_service",
    "_chanlun_daily_provider",
    "_chanlun_history_provider",
    "_chanlun_minute_store",
    "_chanlun_paper_order_service",
    "_chanlun_paper_order_store",
    "_chanlun_rc8_client",
    "_chanlun_research_catalog",
    "_chanlun_research_health",
    "_chanlun_research_service",
    "_chanlun_research_store",
    "_chanlun_screening_summarizer",
    "_chanlun_shadow_scheduler",
    "_chanlun_symbol_search_service",
    "_close_default_data_source_providers",
    "_close_provider",
    "_concept_provider",
    "_cors_allow_origin_regex",
    "_cors_allow_origins",
    "_daily_kline_provider",
    "_dedupe_symbols",
    "_diagnostic_detail",
    "_effective_settings",
    "_enrich_sector_replica_stock_rows",
    "_estimated_sector_radar",
    "_estimated_sector_radar_item",
    "_etf_excess_flow_service",
    "_etf_price_history_service",
    "_etf_three_factor_monitor",
    "_execute_screen_run",
    "_execute_screen_run_job",
    "_fill_auction_review_close_from_quotes",
    "_fill_auction_review_record_close_from_quote",
    "_generate_auction_top3_for_date",
    "_generate_latest_market_sentiment_analysis",
    "_generate_market_sentiment_analysis",
    "_gsgf_auto_review_service",
    "_gsgf_model_health",
    "_gsgf_review_store",
    "_heatmap_provider",
    "_ifind_provider",
    "_intraday_watchlist_items",
    "_kline_provider",
    "_latest_completed_market_sentiment_trade_date",
    "_latest_market_emotion_sampled_at",
    "_load_sentiment_validation",
    "_mark_auction_review_kline_unavailable",
    "_market_emotion_history_store",
    "_market_overview_provider",
    "_market_sentiment_analysis_now",
    "_market_sentiment_analysis_sampler",
    "_market_sentiment_analysis_service",
    "_market_sentiment_analysis_store",
    "_market_sentiment_percentile_service",
    "_market_sentiment_percentile_store",
    "_model_maintenance_store",
    "_news_risk_provider",
    "_optional_sentiment_analysis_context",
    "_parse_chanlun_backtest_horizons",
    "_percentile_point_for_trade_date",
    "_persisted_percentile_point_for_trade_date",
    "_plate_rotation_reference_provider",
    "_probe",
    "_provider_cache_key",
    "_public_saved_settings",
    "_quote_pct_from_base",
    "_quote_provider",
    "_quote_time_matches_trade_date",
    "_quote_valuation_for_symbol",
    "_read_watchlist_pool",
    "_recent_screen_trade_dates",
    "_refresh_auction_snapshot",
    "_refresh_market_rankings",
    "_refresh_sector_theme_rows",
    "_request_base_url",
    "_run_auction_model_top3_generation_job",
    "_run_auction_snapshot_refresh_job",
    "_run_gsgf_daily_review",
    "_run_store",
    "_runtime_config_path",
    "_safe_status_running",
    "_safe_thread_running",
    "_sanitized_health_error",
    "_save_sentiment_monitor_config",
    "_schedule_market_sentiment_analysis_catchup",
    "_schedule_sector_intraday_refresh",
    "_schedule_sector_theme_rows_refresh",
    "_sector_intraday_cache_key",
    "_sector_intraday_refresh_key",
    "_sector_now",
    "_sector_replica_live_provider",
    "_sector_theme_rows",
    "_sector_theme_rows_store",
    "_sector_workbench_store",
    "_send_sentiment_monitor_notification",
    "_sentiment_monitor",
    "_sentiment_monitor_running_status",
    "_sentiment_review_store",
    "_sentiment_snapshot_store",
    "_should_persist_market_emotion_sample",
    "_start_gsgf_weekly_calibration",
    "_status_unavailable_detail",
    "_stock_industry_for_symbol",
    "_system_job_degraded",
    "_system_jobs",
    "_tdx_provider",
    "_thread_running_status",
    "_tickflow_sector_radar",
    "_validate_chanlun_lookback",
    "_valuation_quote_provider",
    "_watchlist_path",
    "_watchlist_snapshot",
    "app_state",
    "bind_app",
    "logger",
]
