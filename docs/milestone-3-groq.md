# Milestone 3 — Groq AI reply (log only)

**Goal:** `WhatsApp → OpenWA → FastAPI → GroqCloud → generated reply → LOG ONLY.`
Nothing is sent back to WhatsApp. No personalities, memory, DB, or auto-send yet.

Flow: after **all** Milestone 2 safeguards pass (self / group / status / channel / duplicate),
the receiver calls `GroqProvider.generate_reply()` and logs:

```
RECEIVED  | ... text='what you doing'
GENERATED | sender=... | reply="not much, what's up?"
```

Ignored and duplicate messages never reach Groq.

## Provider architecture

```
app/ai/
  base.py          # AIProvider ABC (generate_reply, health_check) + AIError
  prompt.py        # PromptBuilder — simple reply prompt (one place for all prompts)
  groq_provider.py # GroqProvider — Groq OpenAI-compatible endpoint via httpx
  factory.py       # get_ai_provider() — maps AI_PROVIDER -> concrete provider
```

Adding Ollama / xAI-Grok / Gemini later = one new module + one branch in `factory.py`; no caller changes.

## Reliability & security

- Per-request timeout (`AI_TIMEOUT_SECONDS`), full exception handling, empty-response handling.
- Any Groq failure is caught and logged as `AI_ERROR` — the webhook **still returns 200** so OpenWA
  does not retry and create duplicate events. The receiver never crashes.
- `GROQ_API_KEY` is loaded as a secret and is never printed, returned, logged, or included in any
  error message. `.env` is gitignored.

## 1. Install dependencies

No new packages beyond Milestone 2 (Groq is called over plain HTTPS via `httpx`). If starting fresh:

```powershell
cd C:\Users\sahib\OneDrive\Desktop\WhatsApp_Bot
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Add these to your `.env` (create it from `.env.example` if needed)

```
AI_PROVIDER=groq
GROQ_API_KEY=<your real GroqCloud key from https://console.groq.com/keys>
GROQ_MODEL=llama-3.1-8b-instant
GROQ_BASE_URL=https://api.groq.com/openai/v1
```

Keep the real key in `.env` only (never `.env.example`, never committed).

## 3. Recommended model for this test

**`llama-3.1-8b-instant`** — fastest and cheapest current Groq production model, ideal for short
WhatsApp replies. Higher quality alternative: `llama-3.3-70b-versatile` (slower). Both are current
production model IDs.

## 4. Start the backend

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Startup log should show `ai_provider=groq model=llama-3.1-8b-instant`.

## 5. Run the automated tests (never calls real Groq)

```powershell
python -m pytest -q      # expect: 23 passed
```

Groq is mocked everywhere, so tests consume **no** API credits.

## 6. One real end-to-end test

1. Make sure OpenWA is running and the `message.received` webhook is still registered
   (`http://host.docker.internal:8000/webhooks/openwa`).
2. Start the backend (step 4) and watch its console.
3. From another WhatsApp account, send your linked number: **`what you doing`**
4. In the backend log you should see:
   ```
   RECEIVED  | ... text='what you doing'
   GENERATED | sender=...@lid | reply="...something short..."
   ```
   The reply is **only logged** — nothing is sent back to WhatsApp. ✅

## Troubleshooting

- `AI_ERROR | groq: http 401 ...` → the `GROQ_API_KEY` in `.env` is missing/invalid. Fix it, restart.
- `AI_ERROR | groq: http 400 ... model` → the `GROQ_MODEL` is wrong/decommissioned; use
  `llama-3.1-8b-instant`.
- `AI_ERROR | groq: request timed out` → network/slow; raise `AI_TIMEOUT_SECONDS` or retry.
- No `GENERATED` line but `RECEIVED` shows → check the reason on the `IGNORED`/`AI_ERROR` line just
  around it; ignored/duplicate messages intentionally skip Groq.
