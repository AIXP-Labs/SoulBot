"""Fix 9 — retention/rotation/compression unit tests."""
from __future__ import annotations

import gzip
import time
from pathlib import Path

import pytest

from tools.cleanup_execution_cache import (
    SEC_PER_DAY,
    choose_archiver,
    cleanup_directory,
    compress_file,
    compress_old_files,
    delete_expired_archives,
    rotate_live_file,
)


class TestChooseArchiver:
    def test_returns_string(self):
        assert choose_archiver() in ("zstd", "gzip")


class TestCompressFile:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            compress_file(tmp_path / "nope.jsonl")

    def test_gzip_fallback_roundtrip(self, tmp_path, monkeypatch):
        """Force gzip path; ensure content is recoverable."""
        monkeypatch.setattr("tools.cleanup_execution_cache.shutil.which", lambda _: None)
        p = tmp_path / "_spans.jsonl"
        # write_bytes to keep exact content (avoid Windows CRLF translation)
        p.write_bytes(b"line1\nline2\n")
        out = compress_file(p)
        assert out.suffix == ".gz"
        assert not p.exists()
        with gzip.open(out, "rb") as f:
            assert f.read() == b"line1\nline2\n"


class TestRotateLiveFile:
    def test_missing_file_returns_none(self, tmp_path):
        assert rotate_live_file(tmp_path / "missing.jsonl") is None

    def test_empty_file_returns_none(self, tmp_path):
        p = tmp_path / "_spans.jsonl"
        p.touch()
        assert rotate_live_file(p) is None

    def test_rotates_non_empty_file(self, tmp_path):
        p = tmp_path / "_spans.jsonl"
        p.write_text("a\n", encoding="utf-8")
        rotated = rotate_live_file(p, today="20260101")
        assert rotated == tmp_path / "_spans-20260101.jsonl"
        assert rotated.exists()
        assert rotated.read_text(encoding="utf-8") == "a\n"
        # Live file recreated empty so writer can resume
        assert p.exists()
        assert p.read_text(encoding="utf-8") == ""

    def test_appends_when_dated_file_exists(self, tmp_path):
        p = tmp_path / "_spans.jsonl"
        dated = tmp_path / "_spans-20260101.jsonl"
        dated.write_text("existing\n", encoding="utf-8")
        p.write_text("new\n", encoding="utf-8")
        rotate_live_file(p, today="20260101")
        assert dated.read_text(encoding="utf-8") == "existing\nnew\n"


class TestCompressOldFiles:
    def test_compresses_only_old(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.cleanup_execution_cache.shutil.which", lambda _: None)
        old = tmp_path / "_spans-20250101.jsonl"
        old.write_text("old", encoding="utf-8")
        # Set mtime to 10 days ago
        old_mtime = time.time() - 10 * SEC_PER_DAY
        import os
        os.utime(old, (old_mtime, old_mtime))

        fresh = tmp_path / "_spans-20260410.jsonl"
        fresh.write_text("fresh", encoding="utf-8")

        compressed = compress_old_files(tmp_path, compress_after_days=7)
        assert len(compressed) == 1
        assert compressed[0].suffix == ".gz"
        assert not old.exists()
        assert fresh.exists()


class TestDeleteExpiredArchives:
    def test_deletes_only_old_archives(self, tmp_path):
        import os

        old_archive = tmp_path / "_spans-20250101.jsonl.gz"
        old_archive.write_bytes(b"x")
        os.utime(old_archive, (time.time() - 40 * SEC_PER_DAY, time.time() - 40 * SEC_PER_DAY))

        recent = tmp_path / "_spans-20260401.jsonl.gz"
        recent.write_bytes(b"x")

        deleted = delete_expired_archives(tmp_path, delete_after_days=30)
        assert len(deleted) == 1
        assert not old_archive.exists()
        assert recent.exists()


class TestCleanupDirectory:
    def test_end_to_end(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.cleanup_execution_cache.shutil.which", lambda _: None)
        # live spans with data → should rotate
        (tmp_path / "_spans.jsonl").write_text("span1\n", encoding="utf-8")
        summary = cleanup_directory(tmp_path)
        assert len(summary["rotated"]) == 1
        # No other side effects for a fresh dir
        assert summary["compressed"] == []
        assert summary["deleted"] == []
