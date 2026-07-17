"""Environment-backed application settings."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "RetailPulse AI"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    postgres_db: str = "retailpulse"
    postgres_user: str = "retail_user"
    postgres_password: SecretStr = SecretStr("change_me")
    postgres_host: str = "db"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    database_url: str | None = None

    ai_enabled: bool = False
    ai_provider: Literal["openai"] = "openai"
    openai_api_key: SecretStr | None = None
    ai_model: str | None = None
    ai_row_limit: int = Field(default=10, ge=1, le=20)
    ai_query_timeout_ms: int = Field(default=2_000, ge=100, le=10_000)

    @model_validator(mode="after")
    def validate_ai_configuration(self) -> Self:
        """Require explicit AI credentials only if the future feature is enabled."""
        api_key = self.openai_api_key.get_secret_value() if self.openai_api_key else ""
        if self.ai_enabled and not api_key.strip():
            raise ValueError("OPENAI_API_KEY is required when AI_ENABLED is true")
        if self.ai_enabled and not (self.ai_model or "").strip():
            raise ValueError("AI_MODEL is required when AI_ENABLED is true")
        return self

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return an explicit URL or construct one from PostgreSQL settings."""
        if self.database_url:
            return self.database_url
        password = self.postgres_password.get_secret_value()
        return (
            f"postgresql+psycopg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def allowed_cors_origins(self) -> list[str]:
        """Return normalized browser origins for CORS middleware."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings object per process."""
    return Settings()
