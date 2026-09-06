from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    rag_mode: Literal["disabled", "fake", "postgres"] = "disabled"
    database_url: str | None = None
    call_provider_mode: Literal["fake", "calle"] = "fake"
    calle_api_key: str | None = None
    calle_base_url: str = "https://api.heycall-e.com"


settings = Settings()
