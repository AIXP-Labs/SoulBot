"""BaseArtifactService — abstract interface for agent-produced file management."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, Field


class Artifact(BaseModel):
    """Metadata for an agent-produced artifact."""

    name: str
    """File name or identifier."""

    content_type: str = "application/octet-stream"
    """MIME type of the artifact."""

    size: int = 0
    """Size in bytes."""

    metadata: dict = Field(default_factory=dict)
    """Arbitrary metadata (agent name, session id, etc.)."""

    created_at: float = Field(default_factory=time.time)


class BaseArtifactService(ABC):
    """Abstract base for artifact (file) storage."""

    @abstractmethod
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
        """Save an artifact and return its metadata."""
        ...

    @abstractmethod
    async def get_artifact(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        name: str,
    ) -> Optional[bytes]:
        """Retrieve artifact data by name.  Returns None if not found."""
        ...

    @abstractmethod
    async def get_artifact_metadata(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        name: str,
    ) -> Optional[Artifact]:
        """Retrieve artifact metadata.  Returns None if not found."""
        ...

    @abstractmethod
    async def list_artifacts(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> list[Artifact]:
        """List all artifacts for a session."""
        ...

    @abstractmethod
    async def delete_artifact(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        name: str,
    ) -> None:
        """Delete an artifact."""
        ...
