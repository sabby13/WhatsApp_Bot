"""GroqProvider unit tests — mock the HTTP layer with httpx.MockTransport.

No network, no API key, no credits consumed. Verifies request shape, success parsing,
empty handling, error mapping to AIError, timeout mapping, and that the API key never
appears in an error message.
"""
import asyncio

import httpx
import pytest

from app.ai.base import AIError
from app.ai.groq_provider import GroqProvider


def _provider(handler):
    return GroqProvider(
        api_key="SECRET-KEY-DO-NOT-LEAK",
        model="llama-3.1-8b-instant",
        base_url="https://api.groq.com/openai/v1",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )


def test_success_parses_content_and_sends_auth():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers.get("Authorization")
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"choices": [{"message": {"content": "  not much, you?  "}}]})

    reply = asyncio.run(_provider(handler).generate_reply("what you doing"))
    assert reply == "not much, you?"                       # trimmed
    assert seen["auth"] == "Bearer SECRET-KEY-DO-NOT-LEAK"  # key sent correctly
    assert seen["url"].endswith("/openai/v1/chat/completions")


def test_empty_response_returns_empty_string():
    def handler(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})

    assert asyncio.run(_provider(handler).generate_reply("hi")) == ""


def test_http_error_raises_aierror():
    def handler(req):
        return httpx.Response(401, json={"error": {"message": "Invalid API Key"}})

    with pytest.raises(AIError):
        asyncio.run(_provider(handler).generate_reply("hi"))


def test_timeout_raises_aierror():
    def handler(req):
        raise httpx.TimeoutException("timed out")

    with pytest.raises(AIError):
        asyncio.run(_provider(handler).generate_reply("hi"))


def test_bad_shape_raises_aierror():
    def handler(req):
        return httpx.Response(200, json={"unexpected": True})

    with pytest.raises(AIError):
        asyncio.run(_provider(handler).generate_reply("hi"))


def test_error_message_never_contains_api_key():
    def handler(req):
        return httpx.Response(500, text="internal error")

    try:
        asyncio.run(_provider(handler).generate_reply("hi"))
        assert False, "should have raised"
    except AIError as e:
        assert "SECRET-KEY-DO-NOT-LEAK" not in e.safe_message()
        assert "SECRET-KEY-DO-NOT-LEAK" not in str(e)
