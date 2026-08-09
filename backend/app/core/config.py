"""Application configuration.

Settings are loaded from environment variables first, then from
`backend/.env` and the repository-root `.env` (in that order). Values
come from the real environment when running under Docker Compose.
"""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py lives at <root>/backend/app/core/config.py
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    # App
    app_name: str = "AI Tool Site"
    app_version: str = "0.1.0"
    app_env: str = "dev"  # "dev" or "production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_cors_origins: str = "http://localhost:5173"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tool_site"

    # Redis (used by the cache layer and the optional rate limiter)
    redis_url: str = "redis://localhost:6379/0"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_models: str = "deepseek-v4-flash,deepseek-v4-pro"
    deepseek_default_model: str = "deepseek-v4-flash"

    # Security / rate limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 20

    model_config = SettingsConfigDict(
        env_file=(
            _BACKEND_DIR / ".env",
            _REPO_ROOT / ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]

    @property
    def deepseek_models_list(self) -> list[str]:
        return [m.strip() for m in self.deepseek_models.split(",") if m.strip()]

    @model_validator(mode="after")
    def _validate_settings(self) -> "Settings":
        if self.deepseek_default_model not in self.deepseek_models_list:
            raise ValueError(
                f"deepseek_default_model '{self.deepseek_default_model}' must be one of "
                f"deepseek_models ({self.deepseek_models_list})"
            )
        if self.app_env == "production":
            if self.database_url.startswith("postgresql+asyncpg://postgres:postgres@"):
                raise ValueError(
                    "DATABASE_URL must not use the default 'postgres:postgres' credentials "
                    "when APP_ENV=production"
                )
            if not self.cors_origins_list:
                raise ValueError("APP_CORS_ORIGINS must be set when APP_ENV=production")
        return self


settings = Settings()
