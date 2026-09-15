"""Lightweight in-memory, per-contact rate limiter (no Redis, no DB).

A sliding 60-second window per key. Good enough for a personal bot; a durable
version can come later if ever needed.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, window_seconds: float = 60.0):
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, max_per_window: int) -> bool:
        """Record and allow a hit for `key`, unless it would exceed max_per_window."""
        if max_per_window <= 0:
            return False
        now = time.monotonic()
        dq = self._hits[key]
        while dq and now - dq[0] >= self._window:
            dq.popleft()
        if len(dq) >= max_per_window:
            return False
        dq.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()
