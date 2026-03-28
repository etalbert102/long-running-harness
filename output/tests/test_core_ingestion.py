"""Tests for draft file ingestion and normalization."""

from __future__ import annotations

from pathlib import Path

import pytest

from editorial_fit_compiler.core.ingestion import (
    load_document_from_path,
    normalize_draft_text,
)


def _ingestion_fixture_path(filename: str) -> Path:
    """Return a fixture path for ingestion tests."""
    return Path(__file__).parent / "fixtures" / "ingestion" / filename


def test_normalize_draft_text_normalizes_line_endings_and_trailing_whitespace() -> None:
    """Normalization should canonicalize line endings and trim trailing spaces per line."""
    raw_text = "\ufeffLine one  \r\nLine two\t\rLine three\n"
    normalized = normalize_draft_text(raw_text)
    assert normalized == "Line one\nLine two\nLine three"


def test_load_document_from_path_loads_markdown_and_creates_paragraphs() -> None:
    """Ingestion should load markdown text and map paragraph spans into a document model."""
    draft_path = _ingestion_fixture_path("sample.md")
    document = load_document_from_path(draft_path)

    assert document.text == "First paragraph.\n\nSecond paragraph."
    assert document.source_path == str(draft_path.resolve())
    assert len(document.paragraphs) == 2
    assert document.paragraphs[0].text == "First paragraph."
    assert document.paragraphs[1].text == "Second paragraph."
    assert document.paragraphs[0].start_char == 0
    assert document.paragraphs[0].end_char == len("First paragraph.")


def test_load_document_from_path_rejects_unsupported_extensions() -> None:
    """Ingestion should fail fast for unsupported file extensions."""
    draft_path = _ingestion_fixture_path("unsupported.rtf")
    with pytest.raises(ValueError, match="Unsupported draft file extension"):
        load_document_from_path(draft_path)
