# Milestone 4 — controlled outbound replies

**Goal:** `Incoming WhatsApp → OpenWA → FastAPI → safeguards → whitelist → rate limit → Groq → OpenWA → WhatsApp reply.`

Automatic sending works for **exactly one whitelisted contact** and nobody else. Everything is off by
default (`BOT_ENABLED=false`). No personalities, DB, modes, memory, media, or typing indicators yet.

## Processing order (each step logs)

```
message.received
  → safeguards: fromMe / group / status / channel / duplicate     (IGNORED | <reason>)
  → RECEIVED
  → kill switch:  BOT_ENABLED=false                                (IGNORED | bot_disabled)
  → whitelist:    sender not in WHITELISTED_CONTACTS               (IGNORED | not_whitelisted)
  → rate limit:   > MAX_AUTO_REPLIES_PER_MINUTE per contact        (IGNORED | rate_limited)
  → Groq                                                           (GENERATED | reply=...  or  AI_ERROR)
  → OpenWA send_text to the canonical chatId                       (SENT | message_id=...  or  SEND_ERROR)
```

The webhook always returns HTTP 200 so OpenWA acknowledges the event and never retry-storms.

## Key design points

- **Kill switch** (`BOT_ENABLED`, default `false`): when off, messages are still received/logged but
  **no Groq call and no send** happen — `IGNORED | bot_disabled`.
- **Whitelist** (`WHITELISTED_CONTACTS`): only listed senders trigger Groq/sending. Supports `@lid` and
  `@c.us`. Empty list = nobody. A LID is **never** turned into a phone number.
- **Loop prevention:** `fromMe` messages are dropped, and we only subscribe to `message.received`. The
  bot's own outbound messages can never re-trigger it.
- **Rate limit** (`MAX_AUTO_REPLIES_PER_MINUTE`, per contact, in-memory): excess → `IGNORED | rate_limited`,
  no Groq/no send.
- **Recipient identity:** replies go to the incoming message's **canonical `chatId`** (the `@lid` for a
  LID sender). Verified against v0.23.4 `wwebjs-messaging.ts`: an `@lid` chatId is accepted and delivered
  as-is; only `@c.us` ids get resolved. No phone reconstruction.
- **Failure handling:** Groq failure → no send, stable 200. OpenWA failure → `SEND_ERROR`, **no regenerate,
  no retry loop**, stable 200. Neither the Groq nor the OpenWA API key is ever logged or put in an error.

## Files

New: `app/openwa_client.py` (OpenWAClient.send_text + OpenWASendError), `app/rate_limit.py`,
`tests/test_openwa_client.py`. Modified: `app/config.py` (M4 settings + `whitelist` property),
`app/webhooks.py` (kill switch → whitelist → rate limit → Groq → send), `app/main.py` (startup log),
`tests/conftest.py` (fake OpenWA + bot-enabled baseline), `tests/test_webhook.py` (M4 cases),
`.env.example`.

## 1. Install dependencies

No new packages (OpenWA is called over HTTP via `httpx`):

```powershell
cd C:\Users\sahib\OneDrive\Desktop\WhatsApp_Bot
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Get the OpenWA API key (without exposing it)

OpenWA seeds an admin key on first run. Get it either way:

```powershell
# printed at startup, or read the seed file inside the container:
docker exec openwa-api cat /app/data/.api-key
```

Paste it into `.env` as `OPENWA_API_KEY=` **only**. It is gitignored and the app never logs it (startup
shows only `openwa_key=set`).

## 3. Get the session UUID (NOT the name)

The send endpoint `POST /api/sessions/:sessionId/messages/send-text` keys the running engine by the
session's **UUID primary key**, not the display name. Passing the name `whatsapp-bot` fails with
`400 Session 'whatsapp-bot' is not active`. Get the UUID either way:

```powershell
# from the API (find the object whose "name" is whatsapp-bot, copy its "id"):
curl.exe -s http://localhost:2785/api/sessions -H "X-API-Key: <your key>"
# or: copy the "Session ID" shown for whatsapp-bot in the OpenWA dashboard.
```

## 4. `.env` variables to add

```
OPENWA_API_KEY=<the owa_k1_... key from step 2>
OPENWA_BASE_URL=http://localhost:2785
OPENWA_SESSION=<the session UUID from step 3, e.g. 3f9c1e2a-....>   # NOT "whatsapp-bot"
MAX_AUTO_REPLIES_PER_MINUTE=5

# LEAVE THESE OFF for now — you will flip them on manually for the test:
BOT_ENABLED=false
WHITELISTED_CONTACTS=
```

(Groq vars from Milestone 3 stay as they are. If you ever delete & recreate the session, its UUID
changes — update `OPENWA_SESSION` again.)

## 4. Run the tests (never touches real Groq or WhatsApp)

```powershell
python -m pytest -q      # expect: 39 passed
```

## 5. Start the backend

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Startup log shows `bot_enabled=... | whitelist=N contact(s) | ... | openwa_key=set`.

## 6. Controlled real-world test

1. Confirm the `message.received` webhook is still registered in OpenWA
   (`http://host.docker.internal:8000/webhooks/openwa`).
2. In `.env`, set **exactly**:
   ```
   BOT_ENABLED=true
   WHITELISTED_CONTACTS=<the exact @lid we observed, e.g. 16608722419787@lid>
   ```
   Restart the backend (Ctrl+C, then the command in step 5).
3. From **that one whitelisted contact**, send your WhatsApp: `hey bot test`
   Expected log + a real reply arriving in that chat:
   ```
   RECEIVED  | ... text='hey bot test'
   GENERATED | sender=...@lid | reply='...'
   SENT      | recipient=...@lid | message_id=...
   ```
4. From a **different, non-whitelisted** contact, send anything. Expected:
   ```
   RECEIVED  | ...
   IGNORED | not_whitelisted | sender=...
   ```
   No reply is generated or sent.

To stop all sending instantly at any time: set `BOT_ENABLED=false` and restart.

## Troubleshooting

- `SEND_ERROR | ... http 400: Session '...' is not active. Start the session first.` → `OPENWA_SESSION`
  holds the session **name** instead of its **UUID**. The engine registry is keyed by the session UUID, so
  put the UUID (step 3) in `OPENWA_SESSION`. The session is fine; do not stop/recreate it.
- `SEND_ERROR | ... http 401` → wrong/missing `OPENWA_API_KEY`. Re-read it (step 2), update `.env`, restart.
- `SEND_ERROR | ... http 404` → check `OPENWA_BASE_URL` and that OpenWA is running on :2785.
- Reply generated but not delivered, `RecipientUnreachable`-style error → the contact could not be resolved;
  confirm you whitelisted the exact `@lid` from the `RECEIVED` log.
- Nothing happens on a whitelisted message → check the line after `RECEIVED`: `bot_disabled` (flip
  `BOT_ENABLED=true`), `not_whitelisted` (id mismatch), or `rate_limited`.
