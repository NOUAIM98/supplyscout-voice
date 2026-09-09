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
    cors_allowed_origins: str = "http://localhost:3000"
    rag_mode: Literal["disabled", "fake", "postgres"] = "disabled"
    rag_embedding_provider: Literal["fastembed"] = "fastembed"
    rag_embedding_model: str = "BAAI/bge-small-en-v1.5"
    database_url: str | None = None
    call_provider_mode: Literal["fake", "calle"] = "fake"
    calle_api_key: str | None = None
    calle_base_url: str = "https://api.heycall-e.com"
    calle_live_enabled: bool = False
    calle_allowed_recipients: str = ""
    calle_recipient_region: str | None = None
    calle_recipient_locale: str | None = None

    @property
    def allowed_calle_recipients(self) -> frozenset[str]:
        return frozenset(
            phone.strip()
            for phone in self.calle_allowed_recipients.split(",")
            if phone.strip()
        )

    @property
    def allowed_cors_origins(self) -> tuple[str, ...]:
        origins = tuple(
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        )
        if "*" in origins:
            raise ValueError("CORS wildcard origins are not allowed")
        return origins or ("http://localhost:3000",)


settings = Settings()
