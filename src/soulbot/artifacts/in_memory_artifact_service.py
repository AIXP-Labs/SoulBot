"""InMemoryArtifactService — non-persistent artifact storage."""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Optional

from .base_artifact_service import Artifact, BaseArtifactService

logger = logging.getLogger(__name__)

# 100 MB default cap
_DEFAULT_MAX_BYTES = 100 * 1024 * 1024


class InMemoryArtifactService(BaseArtifactService):
    """Stores artifacts in memory with LRU eviction.

    Args:
        max_total_bytes: Maximum total size of stored artifact data in bytes.
            When exceeded, the least-recently-used artifacts are evicted.
            Set to ``0`` to disable the limit.
    """

    def __init__(self, max_total_bytes: int = _DEFAULT_MAX_BYTES) -> None:
        # Flat LRU index: (app, user, session, name) → (Artifact, bytes)
        self._lru: OrderedDict[tuple[str, str, str, str], tuple[Artifact, bytes]] = (
            OrderedDict()
        )
        self._total_bytes: int = 0
        self._max_bytes: int = max_total_bytes

    def _evict_until(self, needed: int) -> None:
        """Evict oldest entries until *needed* bytes can fit."""
        if self._max_bytes <= 0:
            return
        while self._lru and self._total_bytes + needed > self._max_bytes:
            key, (artifact, _data) = self._lru.popitem(last=False)
            self._total_bytes -= artifact.size
            logger.debug(
                "Evicted artifact %s/%s/%s/%s (%d bytes)",
                *key,
                artifact.size,
            )

    async def save_artifact(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        name: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None,
    ) -> Artifact:
        key = (app_name, user_id, session_id, name)
        size = len(data)

        # Remove old version first (if overwriting)
        if key in self._lru:
            old_artifact, _ = self._lru.pop(key)
            self._total_bytes -= old_artifact.size

        self._evict_until(size)

        artifact = Artifact(
            name=name,
            content_type=content_type,
            size=size,
            metadata=metadata or {},
        )
        self._lru[key] = (artifact, data)
        self._total_bytes += size
        return artifact

    async def get_artifact(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        name: str,
    ) -> Optional[bytes]:
        key = (app_name, user_id, session_id, name)
        entry = self._lru.get(key)
        if entry is None:
            return None
        self._lru.move_to_end(key)  # mark as recently used
        return entry[1]

    async def get_artifact_metadata(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        name: str,
    ) -> Optional[Artifact]:
        key = (app_name, user_id, session_id, name)
        entry = self._lru.get(key)
        if entry is None:
            return None
        self._lru.move_to_end(key)
        return entry[0]

    async def list_artifacts(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> list[Artifact]:
        prefix = (app_name, user_id, session_id)
        return [
            artifact
            for key, (artifact, _) in self._lru.items()
            if key[:3] == prefix
        ]

    async def delete_artifact(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        name: str,
    ) -> None:
        key = (app_name, user_id, session_id, name)
        entry = self._lru.pop(key, None)
        if entry is not None:
            self._total_bytes -= entry[0].size
