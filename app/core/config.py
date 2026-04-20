"""Environment-based settings for the loyalty agent."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Apoli · Techapoli Loyalty"
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 9000
    cors_origins: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.2

    loyalty_api_base_url: str = "http://localhost:8000"
    loyalty_api_timeout_seconds: float = 15.0
    loyalty_agent_service_email: str = ""
    loyalty_agent_service_password: str = ""
    loyalty_token_cache_ttl_seconds: int = 1500

    agent_database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/loyalty_agent"
    )
    refresh_token_encryption_key: str = ""

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""

    whatsapp_verify_token: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_graph_version: str = "v21.0"

    agent_memory_ttl_hours: int = 168
    agent_max_tool_iterations: int = 8
    confirmation_expiry_minutes: int = 10

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
