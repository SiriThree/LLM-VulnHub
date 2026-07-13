from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LLM-VulnHub"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    cors_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?$"

    database_url: str = "sqlite:///./llm_vulnhub.db"
    redis_url: str = "redis://redis:6379/0"

    llm_provider: str = "mock"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    llm_timeout_seconds: int = 45
    llm_max_retries: int = 2
    agent_max_attempts: int = 2
    llm_temperature: float = 0.1
    llm_fallback_to_mock: bool = True
    github_token: str | None = None
    default_actor: str = "local-admin"
    default_role: str = "admin"

    embedding_dim: int = 64
    duplicate_similarity_threshold: float = 0.88

    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
