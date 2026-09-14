"""GroqProvider — first concrete AIProvider (GroqCloud).

Uses Groq's OpenAI-compatible Chat Completions endpoint via httpx (no vendor SDK,
keeping the app provider-independent). Verified against Groq docs:
  POST {base_url}/chat/completions      base_url default https://api.groq.com/openai/v1
  Authorization: Bearer <GROQ_API_KEY>
  body: { model, messages, temperature, max_completion_tokens }

The API key is never logged, printed, returned, or placed in an exception message.
"""
from __future__ import annotations

import httpx

from .base import AIError, AIProvider
from .prompt import build_reply_messages

_PROVIDER = "groq"


def _safe_detail(resp: httpx.Response) -> str:
    """A short, secret-free description of an error response (Groq never echoes our key)."""
    try:
        data = resp.json()
        msg = data.get("error", {}).get("message") if isinstance(data, dict) else None
        return str(msg)[:200] if msg else resp.text[:200]
    except ValueError:
        return resp.text[:200]


class GroqProvider(AIProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.groq.com/openai/v1",
        timeout: float = 15.0,
        max_tokens: int = 150,
        temperature: float = 0.7,
        transport: httpx.BaseTransport | None = None,  # for tests (httpx.MockTransport)
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    async def generate_reply(self, message: str) -> str:
        payload = {
            "model": self._model,
            "messages": build_reply_messages(message),
            "temperature": self._temperature,
            "max_completion_tokens": self._max_tokens,
        }
        url = f"{self._base_url}/chat/completions"
        try:
            async with self._client() as client:
                resp = await client.post(url, json=payload, headers=self._headers())
        except httpx.TimeoutException as e:
            raise AIError(_PROVIDER, "request timed out") from e
        except httpx.RequestError as e:
            # type name only — never the message, which could contain the URL/params
            raise AIError(_PROVIDER, f"network error ({type(e).__name__})") from e

        if resp.status_code != 200:
            raise AIError(_PROVIDER, f"http {resp.status_code}: {_safe_detail(resp)}")

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise AIError(_PROVIDER, "unexpected response shape") from e

        return (content or "").strip()

    async def health_check(self) -> bool:
        url = f"{self._base_url}/models"
        try:
            async with self._client() as client:
                resp = await client.get(url, headers=self._headers())
            return resp.status_code == 200
        except httpx.RequestError:
            return False
