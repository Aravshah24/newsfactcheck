from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from app.config import settings

logger = logging.getLogger(__name__)


def run_in_parallel(calls: list[Callable[[], Any]]) -> list[tuple[Any, Exception | None]]:
    """Run independent network calls concurrently, preserving input order.

    Each call's result (or raised exception) is returned at its original index,
    so callers keep deterministic ordering while the underlying I/O overlaps.
    Database work must stay outside this function: SQLAlchemy sessions are not
    thread-safe, so only the pure retrieval calls belong here.
    """
    if not calls:
        return []

    workers = max(1, min(len(calls), int(settings.RETRIEVAL_MAX_WORKERS)))
    outcomes: list[tuple[Any, Exception | None]] = [(None, None) for _ in calls]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(call) for call in calls]
        for index, future in enumerate(futures):
            try:
                outcomes[index] = (future.result(), None)
            except Exception as exc:  # noqa: BLE001 - the caller isolates each channel
                outcomes[index] = (None, exc)
    return outcomes
