from __future__ import annotations

from typing import Any

from app.config import settings
from app.retrievers.base import Retriever


class PrimarySourceRetriever(Retriever):
    channel_name = "primary_source"

    def is_available(self) -> bool:
        return bool(settings.PRIMARY_SOURCE_PROVIDER and settings.PRIMARY_SOURCE_API_KEY)

    def search(self, subclaim: Any | None, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        if not self.is_available():
            return []
        return []
