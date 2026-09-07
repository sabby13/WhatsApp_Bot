# WhatsApp Bot

A **local-first, AI-powered WhatsApp assistant**. It uses [OpenWA](https://github.com/rmyndharis/OpenWA)
as the WhatsApp infrastructure layer and a separate Python/FastAPI application for all the
intelligence: message processing, per-contact personalities, conversation context, and reply modes.

The long-term goal is a bot that replies **the way I actually would**, and differently depending
on *who* it is talking to — not a generic assistant voice.

## Architecture

```
WhatsApp
  ↓
OpenWA                (WhatsApp connectivity — treated as infrastructure, not modified)
  ↓  webhook: message.received
Webhook Receiver      (FastAPI)      ┐
  ↓                                  │
Message Router                       │
  ↓                                  │
Contact Profile                      │  our application
  ↓                                  │  (built milestone-by-milestone)
Conversation Context / Memory        │
  ↓                                  │
AI Provider           (Ollama, ...)  │
  ↓                                  │
Reply Decision (OFF / ASSIST / AUTOPILOT)
  ↓                                  ┘
OpenWA Send Message API
  ↓
WhatsApp
```

**OpenWA handles** WhatsApp connectivity only. **Our app handles** incoming message processing,
contact identification, AI generation, personality profiles, conversation context, memory,
reply modes, configuration, and logging.

## Tech stack

- **WhatsApp layer:** OpenWA (NestJS, self-hosted) — run via Docker, unmodified
- **Our backend:** Python + FastAPI + SQLite + SQLAlchemy + Pydantic + HTTPX
- **AI:** provider-independent abstraction; first provider = Ollama (local)
- Config via `.env`. No Redis/Postgres/K8s/vector-DB/queues in *our* app unless proven necessary.

## Repository layout

```
WhatsApp_Bot/
├── README.md
├── .gitignore
├── .env.example
└── docs/
    ├── 00-safeguards.md        # non-negotiable safety rules
    └── milestone-1-openwa.md   # current milestone: run OpenWA + connect WhatsApp
```

> OpenWA itself is cloned separately (outside this folder — see the Milestone 1 doc) so its
> session credentials and data never sync to OneDrive and so we keep infra cleanly separate
> from our code.

## Milestones

| # | Milestone            | Status         |
|---|----------------------|----------------|
| 1 | OpenWA connection    | **in progress** |
| 2 | Webhook receiver     | not started    |
| 3 | Basic AI reply       | not started    |
| 4 | Send replies         | not started    |
| 5 | Contacts + modes     | not started    |
| 6 | Personality engine   | not started    |
| 7 | Conversation context | not started    |
| 8 | Memory               | not started    |
| 9 | Management UI        | not started    |

We build **one milestone at a time** and stop for confirmation after each.

## Safety first

This bot can send messages on my behalf. Before any auto-reply capability exists, the rules in
[`docs/00-safeguards.md`](docs/00-safeguards.md) are treated as hard requirements: whitelist-only,
ignore groups/unknown/self, rate-limiting, duplicate protection, and a global kill switch.
