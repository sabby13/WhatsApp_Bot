"""Application configuration, loaded from environment / .env.

Only the settings actually used by Milestone 2 live here. More will be added
as later milestones need them (AI provider, whitelist, kill switch, ...).
"""
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
    # Leave blank to disable verification (fine for the first Milestone 2 test).
    openwa_webhook_secret: str = ""

    # --- Safeguards (Milestone 2 subset; more arrive in M4/M5) ---
    ignore_groups: bool = True
    ignore_self: bool = True


settings = Settings()
