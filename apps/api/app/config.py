from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    data_dir: Path = Path("./data")
    candidate_provider: str = "recent_limit_up"
    kline_provider: str = "tickflow"
    quote_provider: str = "tickflow"
    tickflow_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("STRONG_STOCK_TICKFLOW_API_KEY", "TICKFLOW_API_KEY"),
    )
    tickflow_base_url: str = "https://api.tickflow.org"
    ifind_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("STRONG_STOCK_IFIND_API_KEY", "IFIND_API_KEY"),
    )
    ifind_base_url: str = "https://api-mcp.51ifind.com:8643"
    ifind_service_id: str = "hexin-ifind-ds-stock-mcp"
    tdx_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("STRONG_STOCK_TDX_API_KEY", "TDX_API_KEY"),
    )
    tdx_base_url: str = "https://mcp.tdx.com.cn:3001/mcp"
    ai_analysis_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("STRONG_STOCK_AI_ANALYSIS_API_KEY", "AI_ANALYSIS_API_KEY"),
    )
    ai_analysis_provider: str = "openai_compatible"
    ai_analysis_base_url: str = "https://api.openai.com/v1"
    ai_analysis_model: str = "gpt-4.1-mini"
    provider_timeout_seconds: float = 12
    cors_allow_origins: str = "http://localhost:3110,http://127.0.0.1:3110"
    screen_run_retention_count: int = Field(default=120, ge=1, le=2000)
    gsgf_review_retention_records: int = Field(default=5000, ge=1, le=100000)
    sentiment_snapshot_retention_days: int = Field(default=30, ge=1, le=365)
    market_emotion_history_retention_days: int = Field(default=30, ge=1, le=365)
    market_emotion_samples_per_day: int = Field(default=360, ge=1, le=2000)
    auction_review_retention_days: int = Field(default=120, ge=1, le=365)
    auction_model_free_stockdb_base_url: str = "http://192.168.5.221:7899"
    auction_model_model_path: Path = (
        Path("./artifacts/morning_auction/free_stockdb_lgbm_20210703_20260703_l120_t1close.pkl")
    )
    auction_model_metadata_path: Path = (
        Path(
            "./artifacts/morning_auction/"
            "free_stockdb_lgbm_20210703_20260703_l120_t1close.metadata.json"
        )
    )
    auction_model_performance_path: Path = (
        Path(
            "./artifacts/morning_auction/"
            "free_stockdb_holdout_20260101_20260703_l120_t1close_execution_constraints.json"
        )
    )
    auction_model_lookback: int = Field(default=120, ge=20, le=260)
    auction_model_top_n: int = Field(default=3, ge=1, le=10)
    auction_model_max_items: int = Field(default=50, ge=3, le=200)
    auction_model_kline_workers: int = Field(default=12, ge=1, le=64)
    auction_model_timeout_seconds: float = Field(default=180, ge=5, le=300)
    auction_top3_record_signal_samples: bool = True
    auction_top3_generate_simulated_trade_samples: bool = False
    auction_top3_include_manual_trade_samples_in_training: bool = False
    auction_top3_training_window_days: int = Field(default=60, ge=5, le=365)
    auction_top3_simulated_initial_capital: float = Field(default=100000, gt=0)
    auction_top3_simulated_position_pct: float = Field(default=0.33, gt=0, le=1)
    chanlun_history_days: int = Field(default=60, ge=5, le=240)
    chanlun_minute_retention_days: int = Field(default=180, ge=30, le=730)
    chanlun_cache_seconds: int = Field(default=30, ge=5, le=600)
    chanlun_backfill_max_bars: int = Field(default=4800, ge=240, le=24000)
    chanlun_tdx_enabled: bool = True
    chanlun_tdx_timeout_seconds: float = Field(default=4, ge=1, le=15)

    model_config = SettingsConfigDict(
        env_prefix="STRONG_STOCK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def watchlist_path(self) -> Path:
        return self.data_dir / "watchlist.txt"


@lru_cache
def get_settings() -> Settings:
    return Settings()
