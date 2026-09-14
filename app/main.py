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
        "STARTUP | webhook receiver up | ignore_groups=%s ignore_self=%s signature=%s | ai_provider=%s model=%s",
        settings.ignore_groups,
        settings.ignore_self,
        "on" if settings.openwa_webhook_secret else "off",
        settings.ai_provider,
        settings.groq_model,
    )
    yield
    logger.info("SHUTDOWN | webhook receiver stopped")


app = FastAPI(title="WhatsApp Bot - Webhook Receiver (Milestone 2)", lifespan=lifespan)
app.include_router(webhook_router)


@app.get("/health")
def health():
    return {"status": "ok"}
