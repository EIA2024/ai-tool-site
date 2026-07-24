from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "AI Tool Site"
    app_version: str = "0.1.0"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_cors_origins: str = "http://localhost:5173"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tool_site"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "ai_tool_site"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_host: str = "localhost"
    redis_port: int = 6379

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
