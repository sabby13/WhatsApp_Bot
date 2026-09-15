"""Application configuration, loaded from environment / .env.

Settings used through Milestone 4. More arrive as later milestones need them
(per-contact modes, personalities, ...).
"""
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Our app (where uvicorn binds) ---
    app_host: str = "0.0.0.0"   # 0.0.0.0 so the OpenWA container can reach us via host.docker.internal
    app_port: int = 8000
    log_level: str = "INFO"

    # --- OpenWA connection (webhook in + send out) ---
    openwa_base_url: str = "http://localhost:2785"      # /api is appended by the client; a trailing /api here is tolerated
    openwa_api_key: SecretStr = SecretStr("")           # X-API-Key value; never logged/returned
    openwa_session: str = Field(
        default="whatsapp-bot",
        validation_alias=AliasChoices("OPENWA_SESSION", "OPENWA_SESSION_ID"),
    )
    openwa_webhook_secret: str = ""                      # optional inbound HMAC verification

    # --- Safeguards ---
    ignore_groups: bool = True
    ignore_self: bool = True

    # --- Milestone 4: controlled outbound sending ---
    bot_enabled: bool = False                            # GLOBAL KILL SWITCH. MUST default false.
    whitelisted_contacts: str = ""                       # comma-separated WhatsApp ids (@lid or @c.us)
    max_auto_replies_per_minute: int = 5                 # per-contact in-memory rate limit

    # --- AI provider (Milestone 3) — provider-independent ---
    ai_provider: str = "groq"
    ai_timeout_seconds: float = 15.0
    ai_max_tokens: int = 150
    ai_temperature: float = 0.7

    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    @property
    def whitelist(self) -> set[str]:
        """Normalized (lowercased, trimmed) set of whitelisted contact ids."""
        return {c.strip().lower() for c in self.whitelisted_contacts.split(",") if c.strip()}


settings = Settings()
