"""Per-process sliding-window limiter for the auth endpoints.

In memory, so it resets on restart and is not shared between workers. That is
enough to slow down password guessing against a single local instance.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_hits: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(bucket: str, limit: int, window_seconds: int):
    async def _check(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        hits = _hits[f"{bucket}:{client}"]
        now = time.monotonic()
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts, try again later",
            )
        hits.append(now)

    return _check
