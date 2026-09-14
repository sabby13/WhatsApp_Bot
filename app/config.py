"""Application configuration, loaded from environment / .env.

Settings used through Milestone 3. More arrive as later milestones need them
(whitelist, kill switch, per-contact modes, ...).
"""
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Our app (where uvicorn binds) ---
    app_host: str = "0.0.0.0"   # 0.0.0.0 so the OpenWA container can reach us via host.docker.internal
    app_port: int = 8000
    log_level: str = "INFO"

    # --- OpenWA webhook security ---
    # If set, every inbound webhook must carry a valid HMAC-SHA256 signature.
    openwa_webhook_secret: str = ""

    # --- Safeguards (Milestone 2 subset; more arrive in M4/M5) ---
    ignore_groups: bool = True
    ignore_self: bool = True

    # --- AI provider (Milestone 3) — provider-independent ---
    ai_provider: str = "groq"            # groq | (later) ollama | xai | gemini | openai-compatible
    ai_timeout_seconds: float = 15.0     # per-request API timeout
    ai_max_tokens: int = 150             # short WhatsApp replies
    ai_temperature: float = 0.7

    # Groq (GroqCloud). SecretStr keeps the key out of logs/reprs; never printed or returned.
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = "https://api.groq.com/openai/v1"


settings = Settings()
