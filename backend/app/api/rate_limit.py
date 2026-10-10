from __future__ import annotations

import time
from collections import deque
from threading import Lock

from fastapi import HTTPException, Request, status

from app.config import settings

#: Sliding window, in seconds. The investigation endpoint is expensive and
#: synchronous, so a small per-IP budget protects the process from a single
#: client queueing many long runs.
_WINDOW_SECONDS = 60.0

_hits: dict[str, deque[float]] = {}
_lock = Lock()


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request) -> None:
    """Dependency that rejects requests beyond ``RATE_LIMIT_PER_MINUTE`` per IP."""
    limit = max(1, int(settings.RATE_LIMIT_PER_MINUTE))
    now = time.monotonic()
    key = _client_key(request)
    with _lock:
        hits = _hits.setdefault(key, deque())
        cutoff = now - _WINDOW_SECONDS
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = int(_WINDOW_SECONDS - (now - hits[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many investigations requested. Try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)
