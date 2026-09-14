"""Provider selection — one place that maps AI_PROVIDER config to a concrete provider.

Adding a provider later (Ollama, xAI/Grok, Gemini, ...) means adding one branch here
and a new module; no caller changes.
"""
from __future__ import annotations

from ..config import settings
from .base import AIProvider
from .groq_provider import GroqProvider

_provider: AIProvider | None = None


def build_ai_provider() -> AIProvider:
    name = settings.ai_provider.strip().lower()
    if name == "groq":
        return GroqProvider(
            api_key=settings.groq_api_key.get_secret_value(),
            model=settings.groq_model,
            base_url=settings.groq_base_url,
            timeout=settings.ai_timeout_seconds,
            max_tokens=settings.ai_max_tokens,
            temperature=settings.ai_temperature,
        )
    raise ValueError(f"Unknown AI_PROVIDER: {settings.ai_provider!r}")


def get_ai_provider() -> AIProvider:
    """Lazily build and cache the configured provider."""
    global _provider
    if _provider is None:
        _provider = build_ai_provider()
    return _provider


def reset_ai_provider() -> None:
    """Test hook: drop the cached provider."""
    global _provider
    _provider = None
