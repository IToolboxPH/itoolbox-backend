from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    platform_env: str = "local"

    # Platform database (users, investigations). Plain Postgres locally via compose.
    database_url: str = "postgresql+asyncpg://itoolbox:itoolbox@localhost:5435/itoolbox_db"

    # JWT — HS256, signed locally. compose.yaml refuses to start without a real value.
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8  # 8 hours

    # CORS — comma-separated origins outside local.
    allowed_origins: str = "*"

    # First super_admin, created on startup when the user table is empty. Leave
    # the password unset to skip; nothing is created with a default password.
    seed_admin_email: str = ""
    seed_admin_password: str = ""
    seed_admin_name: str = "IToolbox Admin"

    # ── Data harness: the Zetaris platform ────────────────────────────────────
    # The agent reaches data only through Zetaris, never through a database
    # driver of its own. Locally Zetaris runs from ../itoolbox-zetaris-platform; inside
    # compose its API is at host.docker.internal:8888.
    zetaris_api_url: str = "http://localhost:8888"
    zetaris_org_id: int = 1
    # Prefer an API key (Zetaris: POST /api/v1.0/auth/api-key). The username /
    # password pair is the fallback, exchanged for a token at /auth/login.
    zetaris_api_key: str = ""
    zetaris_username: str = ""
    zetaris_password: str = ""
    zetaris_timeout_seconds: float = 120.0

    # ── Agent ─────────────────────────────────────────────────────────────────
    agent_default_model: str = "nemotron"
    agent_max_steps: int = 24
    # Rows shown to the model per query, and rows kept as evidence for the UI.
    agent_model_row_limit: int = 50
    agent_evidence_row_limit: int = 200

    # Every model is a real LLM from a provider; there is no scripted agent.

    # NVIDIA Nemotron — OpenAI-compatible API (build.nvidia.com).
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"

    # Nemotron through Meterless Nightshift, the desktop runtime on this machine.
    # Nightshift holds the NVIDIA key itself; the agent sends only its runtime
    # token (Nightshift's Console). Inside compose the host is host.docker.internal.
    # Nightshift 1.2.7 holds back nemotron-3.5-super-vl (a quality hold), so this
    # route uses Nemotron 3.5 Lightning, which starts a step in seconds; Nemotron 3
    # Ultra took 2.5 minutes to its first tool call. Ids: Nightshift's GET /v1/models.
    meterless_runtime_token: str = ""
    meterless_base_url: str = "http://127.0.0.1:8088/v1"
    meterless_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"

    # OpenAI GPT — the model id is whatever platform.openai.com/docs/models lists.
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.5"

    # xAI Grok — OpenAI-compatible API.
    xai_api_key: str = ""
    xai_base_url: str = "https://api.x.ai/v1"
    xai_model: str = "grok-4.6"

    # Anthropic Claude.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: str = "high"


@lru_cache
def get_settings() -> Settings:
    return Settings()
