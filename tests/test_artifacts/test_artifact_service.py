"""Tests for InMemoryArtifactService."""

import pytest

from soulbot.artifacts import Artifact, InMemoryArtifactService


@pytest.fixture
def service():
    return InMemoryArtifactService()


class TestInMemoryArtifactService:
    @pytest.mark.asyncio
    async def test_save_and_get(self, service):
        data = b"hello world"
        artifact = await service.save_artifact("app", "u1", "s1", "file.txt", data)
        assert artifact.name == "file.txt"
        assert artifact.size == len(data)

        retrieved = await service.get_artifact("app", "u1", "s1", "file.txt")
        assert retrieved == data

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, service):
        result = await service.get_artifact("app", "u1", "s1", "nope.txt")
        assert result is None

    @pytest.mark.asyncio
    async def test_content_type(self, service):
        await service.save_artifact(
            "app", "u1", "s1", "image.png", b"\x89PNG",
            content_type="image/png",
        )
        meta = await service.get_artifact_metadata("app", "u1", "s1", "image.png")
        assert meta.content_type == "image/png"

    @pytest.mark.asyncio
    async def test_metadata(self, service):
        await service.save_artifact(
            "app", "u1", "s1", "report.pdf", b"%PDF",
            metadata={"agent": "writer"},
        )
        meta = await service.get_artifact_metadata("app", "u1", "s1", "report.pdf")
        assert meta.metadata == {"agent": "writer"}

    @pytest.mark.asyncio
    async def test_metadata_nonexistent(self, service):
        meta = await service.get_artifact_metadata("app", "u1", "s1", "nope")
        assert meta is None

    @pytest.mark.asyncio
    async def test_list_artifacts(self, service):
        await service.save_artifact("app", "u1", "s1", "a.txt", b"aaa")
        await service.save_artifact("app", "u1", "s1", "b.txt", b"bbb")
        await service.save_artifact("app", "u1", "s2", "c.txt", b"ccc")

        artifacts = await service.list_artifacts("app", "u1", "s1")
        assert len(artifacts) == 2
        names = {a.name for a in artifacts}
        assert names == {"a.txt", "b.txt"}

    @pytest.mark.asyncio
    async def test_delete_artifact(self, service):
        await service.save_artifact("app", "u1", "s1", "f.txt", b"data")
        await service.delete_artifact("app", "u1", "s1", "f.txt")
        assert await service.get_artifact("app", "u1", "s1", "f.txt") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, service):
        # Should not raise
        await service.delete_artifact("app", "u1", "s1", "nope")

    @pytest.mark.asyncio
    async def test_overwrite(self, service):
        await service.save_artifact("app", "u1", "s1", "f.txt", b"old")
        await service.save_artifact("app", "u1", "s1", "f.txt", b"new content")

        data = await service.get_artifact("app", "u1", "s1", "f.txt")
        assert data == b"new content"

        meta = await service.get_artifact_metadata("app", "u1", "s1", "f.txt")
        assert meta.size == len(b"new content")

    @pytest.mark.asyncio
    async def test_session_isolation(self, service):
        await service.save_artifact("app", "u1", "s1", "f.txt", b"session1")
        await service.save_artifact("app", "u1", "s2", "f.txt", b"session2")

        assert await service.get_artifact("app", "u1", "s1", "f.txt") == b"session1"
        assert await service.get_artifact("app", "u1", "s2", "f.txt") == b"session2"

    @pytest.mark.asyncio
    async def test_binary_data(self, service):
        data = bytes(range(256))
        await service.save_artifact("app", "u1", "s1", "bin", data)
        assert await service.get_artifact("app", "u1", "s1", "bin") == data
