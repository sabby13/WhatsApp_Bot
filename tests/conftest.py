"""Shared test fixtures.

Autouse fixtures guarantee NO test ever makes a real Groq or OpenWA call, and give
each test a clean, bot-enabled, whitelisted baseline. Individual tests override
settings (bot_enabled, whitelist, rate limit) or fake behaviour (reply/error) as needed.
"""
import pytest

from app.ai.base import AIProvider

# Senders used by the "valid message" tests — whitelisted by default so they flow through.
DEFAULT_WHITELIST = "16608722419787@lid,919812345678@c.us,9199yyyy@s.whatsapp.net"


class FakeProvider(AIProvider):
    def __init__(self):
        self.calls = 0
        self.reply = "not much, you?"
        self.error: Exception | None = None

    async def generate_reply(self, message: str) -> str:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.reply

    async def health_check(self) -> bool:
        return True


class FakeOpenWA:
    def __init__(self):
        self.sends: list[tuple[str, str]] = []   # (chat_id, text)
        self.error: Exception | None = None

    async def send_text(self, chat_id: str, text: str) -> str:
        if self.error is not None:
            raise self.error
        self.sends.append((chat_id, text))
        return "wamid.TEST123"

    async def health_check(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def ai(monkeypatch):
    fp = FakeProvider()
    from app.ai import factory
    monkeypatch.setattr(factory, "get_ai_provider", lambda: fp)
    return fp


@pytest.fixture(autouse=True)
def owa(monkeypatch):
    fake = FakeOpenWA()
    from app import openwa_client
    monkeypatch.setattr(openwa_client, "get_openwa_client", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def env(monkeypatch):
    """Bot enabled + default whitelist + generous rate limit; in-memory state reset each test."""
    from app.config import settings
    from app import webhooks
    monkeypatch.setattr(settings, "bot_enabled", True)
    monkeypatch.setattr(settings, "whitelisted_contacts", DEFAULT_WHITELIST)
    monkeypatch.setattr(settings, "max_auto_replies_per_minute", 100)
    webhooks._rate_limiter.reset()
    webhooks._seen_ids.clear()
    yield
