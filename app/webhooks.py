"""OpenWA webhook receiver (Milestone 2).

Goal for this milestone: an incoming WhatsApp message reliably shows up in our
logs. No AI, no database, no automatic replies.

Payload shape (verified against OpenWA v0.23.4 source):
`message.received` delivers `{ event, sessionId, data }` where `data` is the
engine-neutral IncomingMessage:
  id                serialized message id, e.g. "false_<jid>_<hash>"
                    (the "false_"/"true_" prefix is the fromMe flag — correct & unique)
  from / to         JIDs; `from` is the sender for incoming, our account for fromMe
  chatId            canonical conversation id (== from for incoming, to for fromMe)
  author            group messages only: the participant WID that actually sent it
  isLidSender       true when the sender is identified by a privacy id (<num>@lid)
  kind              'individual' | 'group' | 'channel' | 'status' | 'broadcast'
  isGroup / isStatusBroadcast   authoritative booleans
  contact.pushName  sender's display name (no extra lookup)
  body, type, timestamp, fromMe

Design notes:
* We read the authoritative fields above, and only fall back to JID-suffix guessing
  for the Baileys engine shape (key.remoteJid / message.conversation), so the parser
  works whichever engine OpenWA runs.
* A `@lid` sender is a legitimate user whose phone number is hidden. We keep the JID
  verbatim (never assume `@c.us`) and flag it so later milestones can resolve/whitelist
  it correctly.
* Safeguards enforced here: ignore self, groups, status/broadcast, channels, and drop
  duplicate message ids (in-memory, no DB yet).
"""
from __future__ import annotations

import hashlib
import hmac
import json
from collections import deque
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from .ai import factory
from .ai.base import AIError
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


def _as_str_id(value: Any) -> str:
    """Message id is a string in v0.23.4; guard the case some path sends the raw wid object."""
    if isinstance(value, dict):
        return str(_first(value, "_serialized", "id", "$1", default="") or "")
    return "" if value is None else str(value)


def _is_duplicate(msg_id: str) -> bool:
    # An empty id ('' sentinel = "received, id unreadable") is never treated as a duplicate,
    # so two distinct unreadable-id messages are both processed rather than collapsed into one.
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

    # Keep the raw shape available for inspection (set LOG_LEVEL=DEBUG to see it).
    logger.debug("RAW     | %s", json.dumps(payload)[:4000])

    event = str(_first(payload, "event", "type", default="")).lower()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    key = data.get("key") if isinstance(data.get("key"), dict) else {}

    # If an event name is present and it isn't an incoming message, ignore it.
    if event and event not in _INCOMING_EVENTS:
        logger.info("IGNORED | event=%s (not an incoming message)", event)
        return {"status": "ignored", "reason": "event"}

    # Canonical conversation id: prefer chatId (v0.23.4), then from; Baileys: key.remoteJid.
    chat_id = _first(data, "chatId", "chat_id", "from", "sender") or _first(key, "remoteJid")
    chat_str = str(chat_id or "")

    # Real sender: author in groups, else from. Baileys: key.participant / key.remoteJid.
    sender_id = (
        _first(data, "author", "participant")
        or _first(key, "participant")
        or _first(data, "from", "sender")
        or _first(key, "remoteJid")
        or chat_str
    )
    sender_str = str(sender_id or "")

    msg_id = _as_str_id(_first(data, "id", "messageId", "message_id") or _first(key, "id"))
    # Text: wwebjs-neutral uses `body`; Baileys nests it under `message.conversation`
    # (or message.extendedTextMessage.text). Never let a nested object become the "text".
    text = _first(data, "body", "text", "caption")
    msg_field = data.get("message")
    if not text and isinstance(msg_field, str):
        text = msg_field
    elif not text and isinstance(msg_field, dict):
        ext = msg_field.get("extendedTextMessage") if isinstance(msg_field.get("extendedTextMessage"), dict) else {}
        text = msg_field.get("conversation") or ext.get("text") or ""
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    timestamp = _first(data, "timestamp", "t", "messageTimestamp")
    from_me = bool(_first(data, "fromMe", "isFromMe", default=False) or _first(key, "fromMe", default=False))

    # LID: a user identified only by a privacy id. Prefer the authoritative flag; keep the JID as-is.
    is_lid = bool(_first(data, "isLidSender", default=False)) or sender_str.endswith("@lid")

    # Conversation kind — prefer authoritative fields, fall back to JID suffix (Baileys).
    kind = str(_first(data, "kind", default="")).lower()
    is_group = bool(_first(data, "isGroup", default=False)) or kind == "group" or chat_str.endswith("@g.us")
    is_status = (
        bool(_first(data, "isStatusBroadcast", default=False))
        or kind == "status"
        or chat_str.endswith("@broadcast")
        or chat_str == "status@broadcast"
    )
    is_channel = kind in ("channel", "broadcast") or chat_str.endswith("@newsletter")
    push_name = _first(data.get("contact") if isinstance(data.get("contact"), dict) else {}, "pushName", "name")

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
    if is_channel:
        logger.info("IGNORED | channel    | chat=%s", chat_str)
        return {"status": "ignored", "reason": "channel"}
    if _is_duplicate(msg_id):
        logger.info("IGNORED | duplicate  | id=%s", msg_id)
        return {"status": "ignored", "reason": "duplicate"}

    logger.info(
        "RECEIVED | chat=%s | sender=%s%s | name=%s | id=%s | ts=%s | text=%r",
        chat_str,
        sender_str,
        " [LID]" if is_lid else "",
        push_name or "-",
        msg_id,
        timestamp,
        text,
    )

    # --- Milestone 3: generate a reply with the AI provider (LOG ONLY — nothing is sent) ---
    # Only runs AFTER every safeguard above has passed, so ignored/duplicate messages never
    # reach the provider. Any failure is caught: the webhook still returns 200 so OpenWA does
    # not retry and create duplicate events.
    reply_generated = False
    if text and text.strip():
        try:
            provider = factory.get_ai_provider()
            reply = await provider.generate_reply(text)
        except AIError as e:
            logger.warning("AI_ERROR | sender=%s | id=%s | %s", sender_str, msg_id, e.safe_message())
        except Exception as e:  # defensive: AI must never crash the receiver
            logger.warning("AI_ERROR | sender=%s | id=%s | unexpected: %s", sender_str, msg_id, type(e).__name__)
        else:
            if reply:
                reply_generated = True
                logger.info("GENERATED | sender=%s | reply=%r", sender_str, reply)
            else:
                logger.warning("AI_ERROR | sender=%s | id=%s | empty response from provider", sender_str, msg_id)
    else:
        logger.info("SKIPPED  | empty message body | id=%s", msg_id)

    return {
        "status": "received",
        "chat": chat_str,
        "sender": sender_str,
        "is_lid": is_lid,
        "id": msg_id,
        "reply_generated": reply_generated,
    }
