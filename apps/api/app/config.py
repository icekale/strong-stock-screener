from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    data_dir: Path = Path("./data")
    candidate_provider: str = "thsdk"
    kline_provider: str = "baidu"
    quote_provider: str = "tickflow"
    tickflow_api_key: str = ""
    tickflow_base_url: str = "https://api.tickflow.org"
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


@lru_cache
def get_settings() -> Settings:
    return Settings()

