"""Tests for draft file ingestion and normalization."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

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


def test_load_document_from_path_loads_docx_in_source_order() -> None:
    """Ingestion should read `.docx` paragraphs in order and tolerate supported formatting."""
    docx_module = pytest.importorskip("docx")
    docx_document_class = docx_module.Document

    temp_dir = Path.cwd() / ".tmp" / "tests"
    temp_dir.mkdir(parents=True, exist_ok=True)
    draft_path = temp_dir / f"sample-{uuid4().hex}.docx"
    source_document = docx_document_class()

    first_paragraph = source_document.add_paragraph()
    first_paragraph.add_run("First")
    first_paragraph.add_run(" paragraph.").bold = True

    second_paragraph = source_document.add_paragraph()
    second_paragraph.add_run("Second")
    second_paragraph.add_run(" paragraph.").italic = True

    source_document.add_paragraph("Third paragraph.")
    source_document.save(str(draft_path))

    try:
        document = load_document_from_path(draft_path)
    finally:
        draft_path.unlink(missing_ok=True)

    assert document.text == "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    assert [paragraph.text for paragraph in document.paragraphs] == [
        "First paragraph.",
        "Second paragraph.",
        "Third paragraph.",
    ]
