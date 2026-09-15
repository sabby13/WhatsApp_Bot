"""Milestone 2 verification tests.

Run from the project root:  python -m pytest -q

The main payloads below mirror the REAL OpenWA v0.23.4 `message.received` shape
(engine-neutral IncomingMessage), including a LID sender like the one observed in
the live test (16608722419787@lid, id "false_..."). A Baileys-shaped payload is
also covered so the parser survives an engine switch.
"""
import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _wwebjs_v0234(**over):
    """A realistic v0.23.4 message.received payload; override any field via kwargs."""
    data = {
        "id": "false_16608722419787@lid_3EB0ABCDEF12",
        "from": "16608722419787@lid",
        "to": "919812345678@c.us",
        "chatId": "16608722419787@lid",
        "body": "Hello",
        "type": "text",
        "timestamp": 1757800000,
        "fromMe": False,
        "isGroup": False,
        "kind": "individual",
        "isStatusBroadcast": False,
        "isLidSender": True,
        "contact": {"pushName": "Test Sender"},
    }
    data.update(over)
    return {"event": "message.received", "sessionId": "whatsapp-bot", "data": data}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_incoming_lid_v0234():
    """Real shape: LID sender is accepted, JID kept verbatim, id preserved, LID flagged."""
    r = client.post("/webhooks/openwa", json=_wwebjs_v0234())
    body = r.json()
    assert r.status_code == 200 and body["status"] == "received"
    assert body["sender"] == "16608722419787@lid"      # not rewritten to @c.us
    assert body["is_lid"] is True
    assert body["id"] == "false_16608722419787@lid_3EB0ABCDEF12"  # false_ prefix is correct


def test_incoming_phone_user():
    r = client.post("/webhooks/openwa", json=_wwebjs_v0234(
        **{"id": "false_919812345678@c.us_XYZ", "from": "919812345678@c.us",
           "chatId": "919812345678@c.us", "isLidSender": False, "body": "hi"}
    ))
    body = r.json()
    assert body["status"] == "received" and body["is_lid"] is False
    assert body["sender"] == "919812345678@c.us"


def test_incoming_baileys_shape():
    payload = {
        "event": "message.received",
        "data": {
            "key": {"remoteJid": "9199yyyy@s.whatsapp.net", "id": "BAE5XYZ", "fromMe": False},
            "message": {"conversation": "kab aaega ghar"},
            "messageTimestamp": 1719312123,
        },
    }
    r = client.post("/webhooks/openwa", json=payload)
    assert r.status_code == 200 and r.json()["status"] == "received"


def test_group_via_author_and_kind():
    """Group message: real sender is `author`; ignored by the group safeguard (kind=group)."""
    r = client.post("/webhooks/openwa", json=_wwebjs_v0234(
        **{"chatId": "12345-678@g.us", "from": "12345-678@g.us",
           "author": "919812345678@c.us", "isGroup": True, "kind": "group",
           "id": "false_12345-678@g.us_GRP"}
    ))
    assert r.json()["reason"] == "group"


def test_ignore_from_me():
    r = client.post("/webhooks/openwa", json=_wwebjs_v0234(**{"fromMe": True, "id": "true_x_1"}))
    assert r.json()["reason"] == "from_me"


def test_ignore_status_via_flag():
    r = client.post("/webhooks/openwa", json=_wwebjs_v0234(
        **{"chatId": "status@broadcast", "from": "status@broadcast",
           "kind": "status", "isStatusBroadcast": True, "id": "false_status_1"}
    ))
    assert r.json()["reason"] == "status"


def test_ignore_channel():
    r = client.post("/webhooks/openwa", json=_wwebjs_v0234(
        **{"chatId": "12036@newsletter", "from": "12036@newsletter",
           "kind": "channel", "id": "false_ch_1"}
    ))
    assert r.json()["reason"] == "channel"


def test_ignore_non_message_event():
    payload = {"event": "session.status", "data": {"status": "connected"}}
    r = client.post("/webhooks/openwa", json=payload)
    assert r.json()["reason"] == "event"


def test_dedupe_real_id():
    p = _wwebjs_v0234(**{"id": "false_16608722419787@lid_DUP"})
    first = client.post("/webhooks/openwa", json=p)
    second = client.post("/webhooks/openwa", json=p)
    assert first.json()["status"] == "received"
    assert second.json()["reason"] == "duplicate"


def test_empty_id_not_deduped():
    """Two distinct messages with the unreadable-id sentinel ('') are both processed."""
    a = client.post("/webhooks/openwa", json=_wwebjs_v0234(**{"id": "", "body": "one"}))
    b = client.post("/webhooks/openwa", json=_wwebjs_v0234(**{"id": "", "body": "two"}))
    assert a.json()["status"] == "received"
    assert b.json()["status"] == "received"


def test_signature_enforced(monkeypatch):
    from app import webhooks

    monkeypatch.setattr(webhooks.settings, "openwa_webhook_secret", "s3cret")
    raw = json.dumps(_wwebjs_v0234(**{"id": "false_sig_1"})).encode()

    # No signature -> rejected
    assert client.post("/webhooks/openwa", content=raw,
                       headers={"content-type": "application/json"}).status_code == 401

    # Correct signature -> accepted
    sig = hmac.new(b"s3cret", raw, hashlib.sha256).hexdigest()
    ok = client.post("/webhooks/openwa", content=raw,
                     headers={"content-type": "application/json", "X-Webhook-Signature": sig})
    assert ok.status_code == 200 and ok.json()["status"] == "received"


# --------------------------------------------------------------------------------------
# Milestone 3 — AI (Groq) integration, log-only. `ai` is the autouse FakeProvider fixture.
# --------------------------------------------------------------------------------------

def test_valid_message_calls_groq_once(ai):
    r = client.post("/webhooks/openwa", json=_wwebjs_v0234(**{"id": "false_m3_valid", "body": "what you doing"}))
    body = r.json()
    assert r.status_code == 200 and body["status"] == "received"
    assert body["reply_generated"] is True
    assert ai.calls == 1


def test_ignored_message_never_calls_groq(ai):
    # from self
    client.post("/webhooks/openwa", json=_wwebjs_v0234(**{"id": "true_m3_self", "fromMe": True}))
    # group
    client.post("/webhooks/openwa", json=_wwebjs_v0234(
        **{"id": "false_m3_grp", "chatId": "1-2@g.us", "from": "1-2@g.us", "isGroup": True, "kind": "group"}))
    # status
    client.post("/webhooks/openwa", json=_wwebjs_v0234(
        **{"id": "false_m3_status", "chatId": "status@broadcast", "kind": "status", "isStatusBroadcast": True}))
    assert ai.calls == 0


def test_duplicate_never_calls_groq_again(ai):
    p = _wwebjs_v0234(**{"id": "false_m3_dupe", "body": "hi"})
    client.post("/webhooks/openwa", json=p)
    client.post("/webhooks/openwa", json=p)
    assert ai.calls == 1  # second is deduped before the provider is reached


def test_groq_failure_keeps_webhook_stable(ai):
    from app.ai.base import AIError
    ai.error = AIError("groq", "boom")
    r = client.post("/webhooks/openwa", json=_wwebjs_v0234(**{"id": "false_m3_fail", "body": "hi"}))
    assert r.status_code == 200
    assert r.json()["status"] == "received" and r.json()["reply_generated"] is False
    assert ai.calls == 1


def test_empty_model_response_handled(ai):
    ai.reply = ""
    r = client.post("/webhooks/openwa", json=_wwebjs_v0234(**{"id": "false_m3_empty", "body": "hi"}))
    assert r.status_code == 200
    assert r.json()["status"] == "received" and r.json()["reply_generated"] is False
    assert ai.calls == 1


# --------------------------------------------------------------------------------------
# Milestone 4 — controlled outbound sending. `ai`/`owa`/`env` are autouse fixtures.
# --------------------------------------------------------------------------------------

def test_kill_switch_off_no_ai_no_send(ai, owa, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "bot_enabled", False)
    r = client.post("/webhooks/openwa", json=_wwebjs_v0234(**{"id": "false_m4_off"}))
    assert r.status_code == 200 and r.json()["reason"] == "bot_disabled"
    assert ai.calls == 0 and owa.sends == []


def test_whitelisted_sender_ai_once_send_once(ai, owa):
    r = client.post("/webhooks/openwa", json=_wwebjs_v0234(**{"id": "false_m4_ok", "body": "hey bot test"}))
    body = r.json()
    assert body["status"] == "received" and body["sent"] is True and body["message_id"] == "wamid.TEST123"
    assert ai.calls == 1
    assert len(owa.sends) == 1


def test_non_whitelisted_no_ai_no_send(ai, owa):
    r = client.post("/webhooks/openwa", json=_wwebjs_v0234(
        **{"id": "false_m4_nowl", "from": "999999@c.us", "chatId": "999999@c.us", "isLidSender": False}))
    assert r.json()["reason"] == "not_whitelisted"
    assert ai.calls == 0 and owa.sends == []


def test_self_message_no_ai_no_send(ai, owa):
    client.post("/webhooks/openwa", json=_wwebjs_v0234(**{"id": "true_m4_self", "fromMe": True}))
    assert ai.calls == 0 and owa.sends == []


def test_group_no_ai_no_send(ai, owa):
    client.post("/webhooks/openwa", json=_wwebjs_v0234(
        **{"id": "false_m4_grp", "chatId": "1-2@g.us", "from": "1-2@g.us", "isGroup": True, "kind": "group"}))
    assert ai.calls == 0 and owa.sends == []


def test_duplicate_no_second_ai_or_send(ai, owa):
    p = _wwebjs_v0234(**{"id": "false_m4_dupe", "body": "hi"})
    client.post("/webhooks/openwa", json=p)
    client.post("/webhooks/openwa", json=p)
    assert ai.calls == 1 and len(owa.sends) == 1


def test_rate_limit_blocks(ai, owa, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "max_auto_replies_per_minute", 1)
    a = client.post("/webhooks/openwa", json=_wwebjs_v0234(**{"id": "false_m4_rl_1", "body": "one"}))
    b = client.post("/webhooks/openwa", json=_wwebjs_v0234(**{"id": "false_m4_rl_2", "body": "two"}))
    assert a.json()["sent"] is True
    assert b.json()["reason"] == "rate_limited"
    assert ai.calls == 1 and len(owa.sends) == 1   # second never reached Groq or send


def test_groq_failure_no_send(ai, owa):
    from app.ai.base import AIError
    ai.error = AIError("groq", "boom")
    r = client.post("/webhooks/openwa", json=_wwebjs_v0234(**{"id": "false_m4_aifail", "body": "hi"}))
    assert r.status_code == 200 and r.json()["reason"] == "ai_error"
    assert r.json()["sent"] is False
    assert ai.calls == 1 and owa.sends == []   # nothing sent


def test_openwa_failure_handled_no_retry_loop(ai, owa):
    from app.openwa_client import OpenWASendError
    owa.error = OpenWASendError("http 500: server error")
    r = client.post("/webhooks/openwa", json=_wwebjs_v0234(**{"id": "false_m4_sendfail", "body": "hi"}))
    assert r.status_code == 200 and r.json()["reason"] == "send_error"
    assert r.json()["reply_generated"] is True and r.json()["sent"] is False
    assert ai.calls == 1   # generated once, no regenerate loop


def test_lid_reply_targets_canonical_identity(ai, owa):
    """Reply must go to the incoming @lid chatId, never a reconstructed phone."""
    client.post("/webhooks/openwa", json=_wwebjs_v0234(
        **{"id": "false_m4_lid", "from": "16608722419787@lid", "chatId": "16608722419787@lid",
           "isLidSender": True, "body": "hey"}))
    assert len(owa.sends) == 1
    recipient, _text = owa.sends[0]
    assert recipient == "16608722419787@lid"
