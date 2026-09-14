"""Prompt construction — kept in one place so prompts never scatter through the code.

Milestone 3 is deliberately minimal: no contact personalities, no "talk like me",
no memory. Those layer in here in later milestones.
"""
from __future__ import annotations

SYSTEM_PROMPT = (
    "You write short, natural WhatsApp replies. "
    "Respond with ONLY the reply text — no quotes, no preamble, no explanation."
)

INSTRUCTION = (
    "Generate a short, natural WhatsApp reply to the following message. "
    "Respond only with the reply text."
)


def build_reply_messages(incoming_text: str) -> list[dict[str, str]]:
    """Return OpenAI-style chat messages for a simple reply."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{INSTRUCTION}\n\nMessage: {incoming_text}"},
    ]
