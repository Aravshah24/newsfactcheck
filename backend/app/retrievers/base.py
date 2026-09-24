from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SearchResult:
    title: str | None = None
    url: str | None = None
    publisher: str | None = None
    publication_date: datetime | None = None
    content: str | None = None
    retrieval_channel: str = "other"
    query: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class Retriever(ABC):
    """Abstract retrieval interface for all investigation channels."""

    channel_name: str = "retriever"

    @abstractmethod
    def search(self, subclaim: Any | None, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    def is_available(self) -> bool:
        return True
