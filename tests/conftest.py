"""Shared test fixtures.

An autouse fixture replaces the real AI provider with a FakeProvider for EVERY test,
so the suite never makes a real Groq call or consumes credits. Tests that care about
AI behaviour take the `ai` fixture to inspect call count or set reply/error.
"""
import pytest

from app.ai.base import AIProvider


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


@pytest.fixture(autouse=True)
def ai(monkeypatch):
    fp = FakeProvider()
    from app.ai import factory
    monkeypatch.setattr(factory, "get_ai_provider", lambda: fp)
    return fp
