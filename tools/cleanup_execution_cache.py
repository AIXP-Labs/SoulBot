"""Fix 9 — retention + rotation for _spans.jsonl / _events.jsonl.

Responsibilities:
- Rotate live ``_spans.jsonl`` / ``_events.jsonl`` to dated filenames
  (``_spans-YYYYMMDD.jsonl``) once per day, so each file is bounded.
- Compress files older than ``compress_after_days`` (default 7) using zstd
  if available, otherwise gzip (B5: Windows-safe zipfile-style fallback).
- Delete compressed files older than ``delete_after_days`` (default 30).

Design notes:
- Pure functions where possible so unit tests can exercise everything
  without a cron / filesystem watcher. The ``main()`` at bottom wires
  them for CLI use (``python -m tools.cleanup_execution_cache``).
- zstd uses the system binary (``shutil.which("zstd")``). Python-level
  zstandard is not required; if neither zstd nor gzip are available,
  compression silently no-ops (never hard-fail).

Reference: Doc 12 v2.3 §10 + Doc 11 v3.2 §5.3
"""
from __future__ import annotations

import argparse
import gzip
import logging
import shutil
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

SEC_PER_DAY = 86_400


def choose_archiver() -> str:
    """Return "zstd" if the binary is on PATH, else "gzip".

    Never raises; callers can rely on this to pick an implementation.
    """
    return "zstd" if shutil.which("zstd") else "gzip"


def compress_file(path: Path) -> Path:
    """Compress ``path`` in place (original deleted). Returns new path.

    Uses zstd if available, else gzip. Raises FileNotFoundError if
    ``path`` does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(path)

    archiver = choose_archiver()
    if archiver == "zstd":
        out = path.with_suffix(path.suffix + ".zst")
        subprocess.run(
            ["zstd", "-q", "-f", str(path), "-o", str(out)], check=True
        )
    else:
        out = path.with_suffix(path.suffix + ".gz")
        with open(path, "rb") as fi, gzip.open(out, "wb") as fo:
            shutil.copyfileobj(fi, fo)

    path.unlink()
    return out


def _today() -> str:
    return time.strftime("%Y%m%d")


def rotate_live_file(
    live_path: Path,
    *,
    today: str | None = None,
) -> Path | None:
    """Rename ``_spans.jsonl`` → ``_spans-YYYYMMDD.jsonl`` if non-empty.

    Returns the rotated path, or None if nothing was rotated (file missing
    or empty). The live filename is preserved so the writer can keep
    appending without reopening.

    If a rotated file for the same date already exists, appends to it
    rather than overwriting (concurrent-safe at daily resolution).
    """
    today = today or _today()
    if not live_path.exists() or live_path.stat().st_size == 0:
        return None

    stem = live_path.stem  # "_spans"
    ext = "".join(live_path.suffixes)  # ".jsonl"
    dated = live_path.with_name(f"{stem}-{today}{ext}")

    if dated.exists():
        # Append new content into existing dated file
        with open(live_path, "rb") as fi, open(dated, "ab") as fo:
            shutil.copyfileobj(fi, fo)
        live_path.unlink()
        # Recreate empty live file so writer can resume
        live_path.touch()
    else:
        live_path.rename(dated)
        live_path.touch()

    return dated


def compress_old_files(
    directory: Path,
    *,
    pattern: str = "_spans-*.jsonl",
    compress_after_days: int = 7,
    now: float | None = None,
) -> list[Path]:
    """Compress rotated files older than ``compress_after_days``.

    Returns list of resulting compressed paths. Files that cannot be
    compressed (missing / permission error) are logged and skipped.
    """
    now = now if now is not None else time.time()
    out: list[Path] = []
    for p in directory.glob(pattern):
        age_days = (now - p.stat().st_mtime) / SEC_PER_DAY
        if age_days <= compress_after_days:
            continue
        try:
            out.append(compress_file(p))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to compress %s: %s", p, exc)
    return out


def delete_expired_archives(
    directory: Path,
    *,
    patterns: tuple[str, ...] = ("_spans-*.jsonl.zst", "_spans-*.jsonl.gz",
                                 "_events-*.jsonl.zst", "_events-*.jsonl.gz"),
    delete_after_days: int = 30,
    now: float | None = None,
) -> list[Path]:
    """Delete compressed archives older than ``delete_after_days``.

    Returns list of deleted paths.
    """
    now = now if now is not None else time.time()
    out: list[Path] = []
    for pat in patterns:
        for p in directory.glob(pat):
            age_days = (now - p.stat().st_mtime) / SEC_PER_DAY
            if age_days <= delete_after_days:
                continue
            p.unlink()
            out.append(p)
    return out


def cleanup_directory(
    directory: Path,
    *,
    live_names: tuple[str, ...] = ("_spans.jsonl", "_events.jsonl"),
    compress_after_days: int = 7,
    delete_after_days: int = 30,
) -> dict:
    """Full cleanup pass: rotate → compress → delete.

    Returns a summary dict for logging / CI output.
    """
    summary: dict = {"rotated": [], "compressed": [], "deleted": []}
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    for name in live_names:
        rotated = rotate_live_file(directory / name)
        if rotated:
            summary["rotated"].append(str(rotated))

    summary["compressed"].extend(
        str(p) for p in compress_old_files(
            directory, pattern="_spans-*.jsonl",
            compress_after_days=compress_after_days,
        )
    )
    summary["compressed"].extend(
        str(p) for p in compress_old_files(
            directory, pattern="_events-*.jsonl",
            compress_after_days=compress_after_days,
        )
    )

    summary["deleted"].extend(
        str(p) for p in delete_expired_archives(
            directory, delete_after_days=delete_after_days,
        )
    )
    return summary


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Rotate + compress + expire SoulBot observability files."
    )
    parser.add_argument("directory", type=Path, help="cache directory to clean")
    parser.add_argument("--compress-after-days", type=int, default=7)
    parser.add_argument("--delete-after-days", type=int, default=30)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    summary = cleanup_directory(
        args.directory,
        compress_after_days=args.compress_after_days,
        delete_after_days=args.delete_after_days,
    )
    for k, v in summary.items():
        logger.info("%s: %d", k, len(v))


if __name__ == "__main__":  # pragma: no cover
    _cli()
