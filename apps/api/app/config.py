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
    provider_timeout_seconds: float = 12
    cors_allow_origins: str = "http://localhost:3110,http://127.0.0.1:3110"

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
