# Milestone 1 — Get OpenWA running & connect WhatsApp

**Goal:** OpenWA running locally, WhatsApp session connected, one test message sent through OpenWA,
and one incoming message observed. **No AI, no FastAPI app yet.**

Everything below is run by *you* in a **Windows PowerShell** terminal (Docker runs on Windows, and
the QR scan happens on your phone). Our project scaffold already lives in this `WhatsApp_Bot` folder;
OpenWA is cloned **separately**, on purpose.

---

## Why clone OpenWA outside this folder?

The dev compose persists WhatsApp session credentials to a `./data` folder next to the repo. This
`WhatsApp_Bot` folder is inside OneDrive, and you do **not** want login credentials/session data
syncing to the cloud. Cloning to a plain path also avoids OneDrive/Docker file-lock issues. So:

- **OpenWA (infrastructure):** `C:\Users\sahib\OpenWA`  ← cloned here
- **Our app (this repo):** `C:\Users\sahib\OneDrive\Desktop\WhatsApp_Bot`

---

## Step 1 — Clone OpenWA

Open **PowerShell** and run:

```powershell
cd C:\Users\sahib
git clone https://github.com/rmyndharis/OpenWA.git
cd OpenWA
```

## Step 2 — Start it with Docker

```powershell
docker compose -f docker-compose.dev.yml up -d
```

This builds and starts a single container (`openwa-api`) with SQLite — no Redis/Postgres to manage.
First build can take a few minutes.

Check it is healthy:

```powershell
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml logs -f
```

Wait until logs show the app listening on port **2785**. (Health endpoint: `http://localhost:2785/api/health/ready`.)
Press `Ctrl+C` to stop following logs — the container keeps running in the background.

## Step 3 — Open the dashboard

In your browser go to:

```
http://localhost:2785
```

- API base: `http://localhost:2785/api`
- Swagger (interactive API docs): `http://localhost:2785/api/docs`

## Step 4 — Create a session & scan the QR

1. In the dashboard, **create a new session** (name it e.g. `dev-bot`).
2. If asked for an **engine**, choose the **whatsapp-web.js** engine (classic QR scan).
3. A **QR code** appears. On your phone: **WhatsApp → Settings → Linked Devices → Link a Device**,
   then scan the QR.
4. Wait for the session status to become **connected / ready**.

> This links WhatsApp Web to your account (same as WhatsApp Web in a browser). It does not log you
> out of your phone.

## Step 5 — Send a test message through OpenWA

Easiest: use the dashboard's send/chat UI if present.

Via API (PowerShell) — you need the **API key**. Find it in the dashboard settings, or in the
first-run container logs (`docker compose -f docker-compose.dev.yml logs | Select-String -Pattern "api key","apikey","x-api-key"`).
WhatsApp ids look like `<countrycode><number>@c.us` — for India: `91XXXXXXXXXX@c.us`.

```powershell
curl.exe -X POST "http://localhost:2785/api/sessions/dev-bot/messages/send-text" `
  -H "Content-Type: application/json" `
  -H "X-API-Key: YOUR_API_KEY" `
  -d "{\"chatId\":\"91XXXXXXXXXX@c.us\",\"text\":\"test from OpenWA\"}"
```

Send it to a friend, or to your own "Message yourself" chat, and confirm it arrives on WhatsApp.

## Step 6 — Observe an incoming message

Keep the logs open in one terminal:

```powershell
docker compose -f docker-compose.dev.yml logs -f
```

Now have someone message the linked number (or message it from another device). You should see the
incoming message appear in the logs and/or in the dashboard chat view.

---

## Milestone 1 is done when ALL of these are true

- [ ] `docker compose ... ps` shows `openwa-api` healthy/running
- [ ] Dashboard loads at `http://localhost:2785`
- [ ] A session shows **connected/ready** after scanning the QR
- [ ] A test message sent via OpenWA **arrives** on WhatsApp
- [ ] An **incoming** message is visible in the logs/dashboard

**Then stop and tell me it works.** I will not start Milestone 2 (the FastAPI webhook receiver)
until you confirm.

---

## Troubleshooting

- **`docker: command not found` / daemon not running:** start Docker Desktop first.
- **Port 2785 in use:** stop the other process, or change the port mapping in the compose file.
- **Build fails on first run:** re-run `docker compose -f docker-compose.dev.yml up -d --build`.
- **QR expired:** refresh the session in the dashboard to get a new QR.
- **Can't find API key:** check dashboard Settings, or grep the logs (Step 5). See also
  `docs/12-troubleshooting` in the OpenWA repo.
- **Stop everything:** `docker compose -f docker-compose.dev.yml down` (add `-v` to also wipe data —
  this unlinks the session).

## Useful OpenWA docs (in the cloned repo, under `docs/`)
`01-project-overview`, `06-api-specification`, `07-api-collection`, `10-devops-infrastructure`,
`12-troubleshooting`. Examples include *Session Phone-Number Pairing* (pairing-code alternative to QR)
and *Webhook Signature Verification* (we'll use this in Milestone 2).
