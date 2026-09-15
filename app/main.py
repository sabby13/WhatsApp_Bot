"""FastAPI entrypoint for the WhatsApp bot backend.

Milestone 2: only the OpenWA webhook receiver + a health check.
Run with:  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .logging_setup import setup_logging
from .webhooks import router as webhook_router

logger = setup_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "STARTUP | receiver up | bot_enabled=%s | whitelist=%d contact(s) | rate_limit=%d/min "
        "| ai_provider=%s model=%s | openwa_session=%s openwa_key=%s",
        settings.bot_enabled,
        len(settings.whitelist),
        settings.max_auto_replies_per_minute,
        settings.ai_provider,
        settings.groq_model,
        settings.openwa_session,
        "set" if settings.openwa_api_key.get_secret_value() else "MISSING",
    )
    yield
    logger.info("SHUTDOWN | webhook receiver stopped")


app = FastAPI(title="WhatsApp Bot - Webhook Receiver (Milestone 2)", lifespan=lifespan)
app.include_router(webhook_router)


@app.get("/health")
def health():
    return {"status": "ok"}
