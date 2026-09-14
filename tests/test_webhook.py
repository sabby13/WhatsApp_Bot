"""Milestone 2 verification tests.

Run from the project root:  python -m pytest -q
These exercise the webhook receiver with sample payloads for BOTH engine shapes
(whatsapp-web.js style and Baileys style) and confirm the safeguards.
"""
import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_incoming_wwebjs_shape():
    payload = {
        "event": "message.received",
        "sessionId": "whatsapp-bot",
        "data": {
            "id": "true_9199xxxx@c.us_ABC123",
            "from": "9199xxxx@c.us",
            "body": "Khaana kha liya?",
            "type": "text",
            "timestamp": 1719312000,
            "fromMe": False,
            "isGroup": False,
        },
    }
    r = client.post("/webhooks/openwa", json=payload)
    assert r.status_code == 200 and r.json()["status"] == "received"


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


def test_ignore_from_me():
    payload = {"event": "message.received", "data": {"id": "m1", "from": "x@c.us", "body": "hi", "fromMe": True}}
    r = client.post("/webhooks/openwa", json=payload)
    assert r.json()["reason"] == "from_me"


def test_ignore_group():
    payload = {"event": "message.received", "data": {"id": "m2", "from": "12345-678@g.us", "body": "hi"}}
    r = client.post("/webhooks/openwa", json=payload)
    assert r.json()["reason"] == "group"


def test_ignore_status():
    payload = {"event": "message.received", "data": {"id": "m3", "from": "status@broadcast", "body": "story"}}
    r = client.post("/webhooks/openwa", json=payload)
    assert r.json()["reason"] == "status"


def test_ignore_non_message_event():
    payload = {"event": "session.status", "data": {"status": "connected"}}
    r = client.post("/webhooks/openwa", json=payload)
    assert r.json()["reason"] == "event"


def test_dedupe():
    payload = {"event": "message.received", "data": {"id": "dup-1", "from": "x@c.us", "body": "hi"}}
    first = client.post("/webhooks/openwa", json=payload)
    second = client.post("/webhooks/openwa", json=payload)
    assert first.json()["status"] == "received"
    assert second.json()["reason"] == "duplicate"


def test_signature_enforced(monkeypatch):
    from app import webhooks

    monkeypatch.setattr(webhooks.settings, "openwa_webhook_secret", "s3cret")
    body = {"event": "message.received", "data": {"id": "sig-1", "from": "x@c.us", "body": "hi"}}
    raw = json.dumps(body).encode()

    # No signature -> rejected
    assert client.post("/webhooks/openwa", content=raw,
                       headers={"content-type": "application/json"}).status_code == 401

    # Correct signature -> accepted
    sig = hmac.new(b"s3cret", raw, hashlib.sha256).hexdigest()
    ok = client.post("/webhooks/openwa", content=raw,
                     headers={"content-type": "application/json", "X-Webhook-Signature": sig})
    assert ok.status_code == 200 and ok.json()["status"] == "received"
