"""Text IO helpers for robust cross-platform file reading."""

from pathlib import Path


def read_text_file(path: Path) -> str:
    """Read text as UTF-8 with replacement for invalid bytes."""
    return path.read_text(encoding="utf-8", errors="replace")
