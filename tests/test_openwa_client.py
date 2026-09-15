"""OpenWAClient unit tests — mock the HTTP layer with httpx.MockTransport.

No network, no real WhatsApp message. Verifies URL, auth header, body (chatId/text),
message-id parsing, @lid recipient passthrough, error mapping, and that the API key
never appears in an error message.
"""
import asyncio
import json

import httpx
import pytest

from app.openwa_client import OpenWAClient, OpenWASendError, _normalize_base


def _client(handler, base="http://localhost:2785"):
    return OpenWAClient(
        base_url=base,
        api_key="owa_k1_SECRET",
        session="whatsapp-bot",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )


def test_normalize_base_tolerates_api_suffix():
    assert _normalize_base("http://localhost:2785/api") == "http://localhost:2785"
    assert _normalize_base("http://localhost:2785/") == "http://localhost:2785"


def test_send_success_parses_message_id_and_sends_auth_and_body():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["key"] = req.headers.get("X-API-Key")
        seen["body"] = json.loads(req.read().decode())
        return httpx.Response(201, json={"messageId": "wamid.ABC", "timestamp": 1719312000})

    mid = asyncio.run(_client(handler).send_text("16608722419787@lid", "hey"))
    assert mid == "wamid.ABC"
    assert seen["url"] == "http://localhost:2785/api/sessions/whatsapp-bot/messages/send-text"
    assert seen["key"] == "owa_k1_SECRET"
    assert seen["body"] == {"chatId": "16608722419787@lid", "text": "hey"}


def test_send_to_lid_recipient_passthrough():
    def handler(req):
        body = req.read().decode()
        assert "16608722419787@lid" in body   # @lid used verbatim
        return httpx.Response(200, json={"messageId": "wamid.LID"})

    assert asyncio.run(_client(handler).send_text("16608722419787@lid", "hi")) == "wamid.LID"


def test_http_error_raises():
    def handler(req):
        return httpx.Response(500, json={"message": "boom"})

    with pytest.raises(OpenWASendError):
        asyncio.run(_client(handler).send_text("x@c.us", "hi"))


def test_timeout_raises():
    def handler(req):
        raise httpx.TimeoutException("t")

    with pytest.raises(OpenWASendError):
        asyncio.run(_client(handler).send_text("x@c.us", "hi"))


def test_error_never_contains_api_key():
    def handler(req):
        return httpx.Response(401, text="unauthorized")

    try:
        asyncio.run(_client(handler).send_text("x@c.us", "hi"))
        assert False, "should have raised"
    except OpenWASendError as e:
        assert "owa_k1_SECRET" not in e.safe_message()
        assert "owa_k1_SECRET" not in str(e)
