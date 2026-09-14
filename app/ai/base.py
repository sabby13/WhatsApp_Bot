"""Provider-independent AI abstraction.

Every AI backend (Groq now; Ollama / xAI-Grok / Gemini / other OpenAI-compatible
APIs later) implements this interface, so the rest of the app never depends on a
specific provider or SDK.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class AIError(Exception):
    """Raised when a provider fails (network, timeout, HTTP error, bad response).

    The message is deliberately safe to log: it carries only a provider name and a
    short reason, never the API key, auth header, or request body.
    """

    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"{provider}: {reason}")

    def safe_message(self) -> str:
        return f"{self.provider}: {self.reason}"


class AIProvider(ABC):
    """Common contract for all AI providers."""

    @abstractmethod
    async def generate_reply(self, message: str) -> str:
        """Return a reply string for the given incoming message.

        Returns an empty string if the model produced no content.
        Raises AIError on any failure (never leaks secrets).
        """
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is reachable/usable."""
        raise NotImplementedError
