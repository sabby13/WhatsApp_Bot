"""OpenWA webhook receiver (Milestone 2).

Goal for this milestone: an incoming WhatsApp message reliably shows up in our
logs. No AI, no database, no automatic replies.

Design notes:
* Parsing is intentionally *defensive*. OpenWA can run either the whatsapp-web.js
  or the Baileys engine, and their payload shapes differ. Rather than bind to one
  shape, we look for a field under several likely names (and a couple of nested
  locations) and always log the raw payload at DEBUG so we can see the real shape.
* Safeguards enforced here: ignore messages from ourselves, ignore group chats,
  ignore status/broadcast, and drop duplicate message ids (in-memory, no DB yet).
"""
from __future__ import annotations

import hashlib
import hmac
import json
from collections import deque
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from .config import settings
from .logging_setup import setup_logging

logger = setup_logging(settings.log_level)
router = APIRouter()

# In-memory dedupe of recently seen message ids. Bounded; oldest auto-evicted.
# (A durable, DB-backed version comes in a later milestone.)
_seen_ids: deque[str] = deque(maxlen=1000)

# Event names (lower-cased) we treat as "an incoming message".
_INCOMING_EVENTS = {"message.received", "message", "message.any", "onmessage", "onanymessage"}


def _first(d: Any, *keys: str, default: Any = None) -> Any:
    """Return the first present, non-empty value among keys in dict d."""
    if not isinstance(d, dict):
        return default
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return default


def _is_duplicate(msg_id: str) -> bool:
    if not msg_id:
        return False
    if msg_id in _seen_ids:
        return True
    _seen_ids.append(msg_id)
    return False


def _verify_signature(raw: bytes, signature: str | None) -> bool:
    """HMAC-SHA256 verification. Disabled when no secret is configured."""
    secret = settings.openwa_webhook_secret
    if not secret:
        return True
    if not signature:
        return False
    sig = signature.split("=", 1)[1] if signature.startswith("sha256=") else signature
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig.strip())


@router.post("/webhooks/openwa")
async def openwa_webhook(
    request: Request,
    x_webhook_signature: str | None = Header(default=None),
):
    raw = await request.body()

    if not _verify_signature(raw, x_webhook_signature):
        logger.warning("ERROR   | rejected webhook: bad or missing signature")
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        logger.warning("ERROR   | rejected webhook: body was not valid JSON")
        raise HTTPException(status_code=400, detail="invalid json")

    # Always keep the raw shape available for inspection (DEBUG only).
    logger.debug("RAW     | %s", json.dumps(payload)[:2000])

    event = str(_first(payload, "event", "type", default="")).lower()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    key = data.get("key") if isinstance(data.get("key"), dict) else {}

    # If an event name is present and it isn't an incoming message, ignore it.
    if event and event not in _INCOMING_EVENTS:
        logger.info("IGNORED | event=%s (not an incoming message)", event)
        return {"status": "ignored", "reason": "event"}

    chat_id = _first(data, "from", "chatId", "chat_id", "sender", "author") or _first(key, "remoteJid")
    chat_str = str(chat_id or "")
    text = (
        _first(data, "body", "text", "message", "caption")
        or _first(data.get("message") if isinstance(data.get("message"), dict) else {}, "conversation")
        or ""
    )
    msg_id = _first(data, "id", "messageId", "message_id") or _first(key, "id") or ""
    timestamp = _first(data, "timestamp", "t", "messageTimestamp")
    from_me = bool(_first(data, "fromMe", "isFromMe", default=False) or _first(key, "fromMe", default=False))
    is_group = bool(_first(data, "isGroup", default=False)) or chat_str.endswith("@g.us")
    is_status = chat_str.endswith("@broadcast") or chat_str == "status@broadcast"

    # --- Safeguards ---
    if settings.ignore_self and from_me:
        logger.info("IGNORED | from self  | id=%s", msg_id)
        return {"status": "ignored", "reason": "from_me"}
    if is_status:
        logger.info("IGNORED | status/broadcast | chat=%s", chat_str)
        return {"status": "ignored", "reason": "status"}
    if settings.ignore_groups and is_group:
        logger.info("IGNORED | group      | chat=%s id=%s", chat_str, msg_id)
        return {"status": "ignored", "reason": "group"}
    if _is_duplicate(msg_id):
        logger.info("IGNORED | duplicate  | id=%s", msg_id)
        return {"status": "ignored", "reason": "duplicate"}

    logger.info("RECEIVED | from=%s | id=%s | ts=%s | text=%r", chat_str, msg_id, timestamp, text)
    return {"status": "received", "from": chat_str, "id": msg_id}
