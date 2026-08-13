"""Application configuration.

Settings are loaded from environment variables first, then from
`backend/.env` and the repository-root `.env` (in that order). Values
come from the real environment when running under Docker Compose.
"""

import json
from pathlib import Path

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py lives at <root>/backend/app/core/config.py
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_DIR.parent


class ProviderConfig(BaseModel):
    """One model provider (an OpenAI-compatible ``/chat/completions`` service).

    Providers are data-driven: adding a new provider is a ``LLM_PROVIDERS``
    entry plus a Settings field for its API key — no client code. The wire
    format seam is ``api_style`` (only ``"openai"`` is implemented today; an
    Anthropic/Gemini native adapter would add a branch in the client).
    """

    id: str
    name: str
    base_url: str  # scheme + host, e.g. https://api.deepseek.com
    # Name of the Settings field holding this provider's API key
    # (e.g. "deepseek_api_key" → DEEPSEEK_API_KEY in .env).
    api_key_env: str
    models: list[str]
    default_model: str
    # Documented ceilings (api-docs.deepseek.com): a 1M-token context and a
    # 384K-token max output. Other providers override with their own numbers.
    max_output_tokens: int = 384_000
    context_length: int = 1_000_000
    # Session/transient keys must start with this prefix; "" accepts any
    # non-empty key (DeepSeek keys start with "sk-").
    session_key_prefix: str = ""
    # Send the V4 thinking/reasoning_effort extensions to this provider.
    supports_thinking: bool = False
    # Extra auth headers for non-bearer providers (future seam, e.g. x-api-key).
    extra_headers: dict[str, str] = Field(default_factory=dict)
    api_style: str = "openai"

    @model_validator(mode="after")
    def _validate_provider(self) -> "ProviderConfig":
        if self.default_model not in self.models:
            raise ValueError(
                f"default_model '{self.default_model}' must be one of "
                f"this provider's models ({self.models})"
            )
        if self.api_style != "openai":
            raise ValueError(f"api_style '{self.api_style}' is not implemented yet")
        return self


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

    # Model providers. The registry is data-driven: ``LLM_PROVIDERS`` is JSON
    # describing one or more OpenAI-compatible providers, and each provider
    # points at a Settings field (``api_key_env``) holding its API key. Adding
    # a provider (OpenAI, GLM, Moonshot/Kimi, Qwen, ...) is one JSON entry +
    # one ``xxx_api_key`` field — no client code. See
    # docs/ai-tool-development-handbook.md → "Adding a model provider".
    deepseek_api_key: str = ""

    llm_providers: str = json.dumps(
        [
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "base_url": "https://api.deepseek.com",
                "api_key_env": "deepseek_api_key",
                "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
                "default_model": "deepseek-v4-flash",
                # Documented DeepSeek V4 limits (api-docs.deepseek.com →
                # Models & Pricing): a 1M-token context window and a 384K-token
                # maximum output. Grounded here instead of magic numbers.
                "max_output_tokens": 384_000,
                "context_length": 1_000_000,
                # DeepSeek keys start with "sk-"; session keys are validated
                # against this prefix.
                "session_key_prefix": "sk-",
                # DeepSeek V4 supports the thinking/reasoning_effort
                # extensions (chat disables thinking by default to avoid the
                # token-burn empty-reply failure — see below).
                "supports_thinking": True,
            }
        ],
        ensure_ascii=False,
    )
    llm_default_provider: str = "deepseek"
    # Empty → the default provider's own default_model.
    llm_default_model: str = ""

    # Chat history bounds: cap stored messages per session so long-running
    # conversations don't grow the table without bound (the model context is
    # already bounded separately). Set to 0 to disable pruning.
    chat_max_messages_per_session: int = 500

    # Chat model budget, grounded in the default provider's documented output
    # ceiling. V4 models default to high-effort thinking, and thinking counts
    # toward max_tokens — a request that over-thinks ends with finish_reason
    # "length" and an empty answer. Chat therefore disables thinking by default
    # (fast, cheap, and that failure mode becomes impossible) and gives the
    # answer a 16_384-token budget: ~4x the longest answer we have observed in
    # testing, ~23x below the 384K ceiling, so it bounds cost/latency without
    # ever truncating a normal reply. Operators who want chat to reason can set
    # CHAT_THINKING=true and CHAT_REASONING_EFFORT (default "low") to cap the
    # thinking burn. CHAT_REASONING_EFFORT="" omits the field entirely.
    chat_max_tokens: int = 16_384
    chat_thinking: bool = False
    chat_reasoning_effort: str = "low"

    # Audit-log retention: prune the oldest tool-call records once the table
    # exceeds this count, so a long-lived deployment can't grow the audit log
    # without bound. Set to 0 to keep every record (not recommended).
    audit_max_records: int = 50_000
    # Optional credential for retrieving raw audit input/output. Public audit
    # responses always contain metadata only.
    audit_operator_token: str = ""

    # Task Decomposer history retention: prune the oldest analyses once the
    # table exceeds this count. Same rationale as audit_max_records. Set to 0
    # to keep every record (not recommended).
    task_decomposer_history_max_records: int = 500

    # Security / rate limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 20
    # Total invoke budget across all clients per minute. Bounds worst-case
    # DeepSeek spend even if clients rotate IPs or hide behind a shared proxy.
    rate_limit_global_per_minute: int = 200
    # When running behind a reverse proxy (e.g. nginx/traefik) that overwrites
    # X-Forwarded-For, set this to true so per-IP limits use the real client.
    # Keep it false when the app is directly reachable — otherwise a client
    # can spoof the header and bypass per-IP rate limiting.
    trust_proxy_headers: bool = False

    model_config = SettingsConfigDict(
        env_file=(
            _BACKEND_DIR / ".env",
            _REPO_ROOT / ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
        # An empty env value (e.g. `LLM_PROVIDERS=` or a commented-out line
        # passed through docker-compose as ``${VAR:-}``) means "use the
        # default", never "set this to empty". Without this, an unset registry
        # override would blank the default JSON and fail startup validation.
        env_ignore_empty=True,
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]

    @property
    def llm_provider_list(self) -> list[ProviderConfig]:
        """Parse ``LLM_PROVIDERS`` into ``ProviderConfig`` objects.

        Re-parsed on each access: the list is small, and this keeps tests able
        to inject/swap providers by patching ``settings.llm_providers`` without
        a cached copy going stale.
        """
        return [
            ProviderConfig.model_validate(entry)
            for entry in json.loads(self.llm_providers)
        ]

    @model_validator(mode="after")
    def _validate_settings(self) -> "Settings":
        providers = self.llm_provider_list
        if not providers:
            raise ValueError("LLM_PROVIDERS must declare at least one provider")
        provider_ids = [p.id for p in providers]
        if self.llm_default_provider not in provider_ids:
            raise ValueError(
                f"llm_default_provider '{self.llm_default_provider}' must be one "
                f"of the declared providers ({provider_ids})"
            )
        if self.llm_default_model:
            all_models = {m for p in providers for m in p.models}
            if self.llm_default_model not in all_models:
                raise ValueError(
                    f"llm_default_model '{self.llm_default_model}' must be among "
                    f"the declared models ({sorted(all_models)})"
                )
        default_ceiling = next(
            p.max_output_tokens
            for p in providers
            if p.id == self.llm_default_provider
        )
        if self.chat_max_tokens > default_ceiling:
            raise ValueError(
                f"chat_max_tokens ({self.chat_max_tokens}) exceeds the default "
                f"provider's max output ceiling ({default_ceiling})"
            )
        if self.chat_reasoning_effort not in ("", "low", "high", "max"):
            raise ValueError(
                "chat_reasoning_effort must be one of '', 'low', 'high', 'max'"
            )
        if self.app_env == "production":
            if self.database_url.startswith("postgresql+asyncpg://postgres:postgres@"):
                raise ValueError(
                    "DATABASE_URL must not use the default 'postgres:postgres' credentials "
                    "when APP_ENV=production"
                )
            if not self.cors_origins_list:
                raise ValueError("APP_CORS_ORIGINS must be set when APP_ENV=production")
            if self.rate_limit_global_per_minute <= 0:
                raise ValueError("RATE_LIMIT_GLOBAL_PER_MINUTE must be > 0")
        return self


settings = Settings()
