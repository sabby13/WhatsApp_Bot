"""OpenWA client — the single place that talks to OpenWA's HTTP API.

Verified against OpenWA v0.23.4:
  POST {base}/api/sessions/{session}/messages/send-text
  header:  X-API-Key: <key>
  body:    { "chatId": "<recipient jid>", "text": "<message>" }
  reply to an individual by its canonical chatId — an `@lid` chatId is accepted and
  delivered as-is (the adapter only rewrites `@c.us`), so we NEVER reconstruct a phone.
  response: 200/201 { "messageId": "...", "timestamp": <epoch> }

The OpenWA API key is never logged, returned, or placed in an error message.
"""
from __future__ import annotations

import httpx

from .config import settings

_TIMEOUT = 15.0


class OpenWASendError(Exception):
    """Raised when a send fails. Message is safe to log (no secrets)."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)

    def safe_message(self) -> str:
        return self.reason


def _safe_detail(resp: httpx.Response) -> str:
    """Short, secret-free error description (OpenWA never echoes our X-API-Key)."""
    try:
        data = resp.json()
        if isinstance(data, dict):
            msg = data.get("message") or data.get("error")
            if msg:
                return str(msg)[:200]
    except ValueError:
        pass
    return resp.text[:200]


def _normalize_base(base_url: str) -> str:
    b = base_url.rstrip("/")
    if b.endswith("/api"):      # tolerate OPENWA_BASE_URL given with or without /api
        b = b[:-4]
    return b


class OpenWAClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        session: str,
        timeout: float = _TIMEOUT,
        transport: httpx.BaseTransport | None = None,  # for tests (httpx.MockTransport)
    ):
        self._base = _normalize_base(base_url)
        self._api_key = api_key
        self._session = session
        self._timeout = timeout
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self._api_key, "Content-Type": "application/json"}

    async def send_text(self, chat_id: str, text: str) -> str:
        """Send a text message to chat_id (the canonical recipient jid). Returns message id."""
        url = f"{self._base}/api/sessions/{self._session}/messages/send-text"
        payload = {"chatId": chat_id, "text": text}
        try:
            async with self._client() as client:
                resp = await client.post(url, json=payload, headers=self._headers())
        except httpx.TimeoutException as e:
            raise OpenWASendError("request timed out") from e
        except httpx.RequestError as e:
            raise OpenWASendError(f"network error ({type(e).__name__})") from e

        if resp.status_code not in (200, 201):
            raise OpenWASendError(f"http {resp.status_code}: {_safe_detail(resp)}")

        try:
            data = resp.json()
            message_id = data.get("messageId") or data.get("id") or data.get("message_id") or ""
        except ValueError:
            message_id = ""
        return str(message_id)

    async def health_check(self) -> bool:
        url = f"{self._base}/api/health/ready"
        try:
            async with self._client() as client:
                resp = await client.get(url, headers=self._headers())
            return resp.status_code == 200
        except httpx.RequestError:
            return False


_client: OpenWAClient | None = None


def get_openwa_client() -> OpenWAClient:
    global _client
    if _client is None:
        _client = OpenWAClient(
            base_url=settings.openwa_base_url,
            api_key=settings.openwa_api_key.get_secret_value(),
            session=settings.openwa_session,
            timeout=settings.ai_timeout_seconds,
        )
    return _client


def reset_openwa_client() -> None:
    global _client
    _client = None
