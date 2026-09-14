# Milestone 2 — FastAPI webhook receiver

**Goal:** `Someone messages me → WhatsApp → OpenWA → webhook → our FastAPI backend → the message is logged.`

No AI. No database. No automatic replies. Just: an incoming message reliably appears in our backend logs,
with self-messages, groups, status/broadcast, and duplicates safely ignored.

Everything runs on your Windows machine. OpenWA (from Milestone 1) must be running.

---

## What was built

```
app/
  __init__.py
  config.py          # settings from .env (pydantic-settings)
  logging_setup.py   # local logging → stdout + logs/bot.log, with action tags
  main.py            # FastAPI app: /health + the webhook router
  webhooks.py        # POST /webhooks/openwa — parse, apply safeguards, log
tests/
  test_webhook.py    # 9 tests (both engine payload shapes + every safeguard)
requirements.txt
```

The parser is **defensive on purpose**: OpenWA can run the *whatsapp-web.js* or the *Baileys* engine and
their payloads differ, so we look for each field under several likely names (and nested `key`/`message`
locations). Set `LOG_LEVEL=DEBUG` to also log the raw payload and see your build's exact shape.

Actions logged: `STARTUP`, `RECEIVED`, `IGNORED` (with reason: from_me / group / status / duplicate / event),
`ERROR`, `SHUTDOWN`.

---

## Part A — Start the backend

Open **PowerShell** in the project folder:

```powershell
cd C:\Users\sahib\OneDrive\Desktop\WhatsApp_Bot

# one-time: copy env template
copy .env.example .env

# one-time: create + activate a virtual env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
#   If activation is blocked by execution policy, run this once then re-activate:
#   Set-ExecutionPolicy -Scope Process -Bypass

# one-time: install deps
pip install -r requirements.txt

# run it (leave this window open)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- If **Windows Firewall** prompts, click **Allow** (private networks) so the container can reach port 8000.
- Verify in a browser: `http://localhost:8000/health` → `{"status":"ok"}` and `http://localhost:8000/docs` for Swagger.

### Quick self-test (no OpenWA needed)

In a **second** PowerShell window:

```powershell
# run the automated tests (from the project folder, venv activated)
python -m pytest -q      # expect: 9 passed

# or fire a fake incoming message at the endpoint directly
curl.exe -X POST http://localhost:8000/webhooks/openwa `
  -H "Content-Type: application/json" `
  -d "{\"event\":\"message.received\",\"data\":{\"id\":\"t1\",\"from\":\"9199@c.us\",\"body\":\"hello\",\"fromMe\":false}}"
```

You should see a `RECEIVED | from=9199@c.us ... text='hello'` line in the uvicorn window.

---

## Part B — Point OpenWA's webhook at the backend

The OpenWA container reaches your PC at **`host.docker.internal`** (not `localhost`, which inside the
container means the container itself). So the webhook URL is:

```
http://host.docker.internal:8000/webhooks/openwa
```

**Recommended: use Swagger (it matches your exact v0.23.4 build).**

1. Open `http://localhost:2785/api/docs`.
2. Click **Authorize** and paste your API key (from the OpenWA dashboard settings).
3. Find the **create-webhook** endpoint (look for a `POST` path containing `webhooks`). Send this body:

   ```json
   {
     "url": "http://host.docker.internal:8000/webhooks/openwa",
     "events": ["message.received"]
   }
   ```

   Leave `secret` empty for the first test. Your session id is **`whatsapp-bot`**.

**Alternative: curl (PowerShell).** The exact path depends on the build — try the per-session one first:

```powershell
curl.exe -X POST "http://localhost:2785/api/sessions/whatsapp-bot/webhooks" `
  -H "X-API-Key: YOUR_API_KEY" -H "Content-Type: application/json" `
  -d "{\"url\":\"http://host.docker.internal:8000/webhooks/openwa\",\"events\":[\"message.received\"]}"
```

If that returns 404, try the global path and include the session id in the body:

```powershell
curl.exe -X POST "http://localhost:2785/api/webhooks" `
  -H "X-API-Key: YOUR_API_KEY" -H "Content-Type: application/json" `
  -d "{\"sessionId\":\"whatsapp-bot\",\"url\":\"http://host.docker.internal:8000/webhooks/openwa\",\"events\":[\"message.received\"]}"
```

Whichever path `/api/docs` lists for your build is the correct one.

---

## Part C — Test the full round trip

1. Keep the uvicorn window open and watch it.
2. From **another phone**, send a WhatsApp message to your linked number.
3. In the uvicorn window (and in `logs/bot.log`) you should see:
   `RECEIVED | from=<their number>@c.us | id=... | text='...'`
4. Sanity-check the safeguards: a message you send from your own linked account should log
   `IGNORED | from self`, and a group message should log `IGNORED | group`.

**Milestone 2 is done when an incoming WhatsApp message shows a `RECEIVED` line in the backend logs.**
Then stop — I won't start Milestone 3 (the AI provider) until you confirm.

---

## Troubleshooting

- **Nothing arrives in the backend:**
  - Confirm uvicorn printed `STARTUP` and `http://localhost:8000/health` works in a browser.
  - The webhook URL **must** be `host.docker.internal`, not `localhost`.
  - Windows Firewall: allow Python inbound on port 8000.
  - Watch OpenWA's side: `docker compose -f docker-compose.dev.yml logs -f` for webhook delivery attempts/errors.
  - Confirm the webhook registered: list webhooks via `/api/docs`.
- **`401` in our logs:** a signing secret is set on one side but not the other. For the first test use **no**
  secret on both sides. To enable signing later: put the same value in the OpenWA webhook `secret` **and** in
  `.env` as `OPENWA_WEBHOOK_SECRET`, then restart uvicorn.
- **Message logged but text is empty / fields look off:** set `LOG_LEVEL=DEBUG` in `.env`, restart, and the
  `RAW | {...}` line shows the exact payload — send it to me and I'll tighten the parser for your engine.
- **Port 8000 busy:** change `--port` (and the webhook URL to match).
