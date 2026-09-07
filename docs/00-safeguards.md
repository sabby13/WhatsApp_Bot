# 00 — Safeguards (non-negotiable)

This bot runs on my **primary** WhatsApp account. I accept the account risk of using an unofficial
WhatsApp integration. In exchange, the following safeguards are **hard requirements** and must be
implemented before any auto-reply capability is enabled. They are listed here so they are never
quietly dropped.

## Rules

1. **Global kill switch.** A single `BOT_ENABLED` flag disables ALL reply generation and sending
   when off. Default: **off**. Nothing sends while it is off, regardless of any contact's mode.

2. **Whitelist-only.** Only contacts on an explicit whitelist can ever trigger AI. Everyone else is
   ignored. Start with **exactly one** whitelisted contact.

3. **Ignore by default.** The bot must ignore:
   - group chats
   - unknown / non-whitelisted contacts
   - status/broadcast and system messages
   - messages sent by *ourselves* (our own account / the bot) — no reply loops

4. **Reply modes** (per contact):
   - `OFF` — never generate or send
   - `ASSIST` — generate a suggestion, store/log it, but **do not send**
   - `AUTOPILOT` — generate and send automatically
   Unknown contacts and groups are always `OFF`.

5. **Duplicate protection.** The same WhatsApp message id must never be processed twice or produce a
   duplicate reply (dedupe on `whatsapp_message_id`).

6. **Rate limiting.** Auto-replies are rate-limited per contact (default: a few per minute) to avoid
   runaway loops.

7. **Never silently fail.** Log every important action locally: `RECEIVED`, `IGNORED`, `GENERATED`,
   `SENT`, `ERROR`.

## Privacy

Local-first. With Ollama, message content stays on this machine. No analytics, telemetry, cloud
databases, or external logging. Never commit `.env`, session data, API keys, or the message database
(enforced by `.gitignore`).

## When these apply

Milestone 1–3 involve **no automatic sending**, so most rules are latent. They become active code in
**Milestone 4 (send replies)** and **Milestone 5 (contacts + modes)**. This document is the checklist
those milestones must satisfy.
