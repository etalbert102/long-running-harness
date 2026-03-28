"""Draft ingestion helpers for supported file-based inputs."""

from __future__ import annotations

import re
from pathlib import Path

from editorial_fit_compiler.core.models import Document, Paragraph

SUPPORTED_DRAFT_EXTENSIONS: tuple[str, ...] = (".md", ".txt", ".docx")


def normalize_draft_text(raw_text: str) -> str:
    """Normalize raw draft text to stable newlines and trimmed trailing whitespace."""
    normalized_line_endings = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized_line_endings.startswith("\ufeff"):
        normalized_line_endings = normalized_line_endings[1:]

    lines = normalized_line_endings.split("\n")
    trimmed_lines = [line.rstrip() for line in lines]
    return "\n".join(trimmed_lines).strip("\n")


def _paragraphs_from_text(normalized_text: str) -> tuple[Paragraph, ...]:
    """Create deterministic paragraph spans from normalized text."""
    segments = re.split(r"\n\s*\n+", normalized_text)
    paragraphs: list[Paragraph] = []
    cursor = 0
    for index, segment in enumerate(segments, start=1):
        if not segment.strip():
            continue
        start = normalized_text.find(segment, cursor)
        if start < 0:
            continue
        end = start + len(segment)
        paragraph = Paragraph(
            paragraph_id=f"p{index}",
            text=segment,
            start_char=start,
            end_char=end,
        )
        paragraphs.append(paragraph)
        cursor = end
    return tuple(paragraphs)


def _extract_docx_text(draft_path: Path) -> str:
    """Extract `.docx` paragraph text in source order as normalized draft text."""
    from docx import Document as DocxDocument

    docx_document = DocxDocument(str(draft_path))
    paragraph_texts = [
        paragraph.text
        for paragraph in docx_document.paragraphs
        if paragraph.text.strip()
    ]
    return normalize_draft_text("\n\n".join(paragraph_texts))


def load_document_from_path(draft_path: Path) -> Document:
    """Load a supported draft file path into a normalized document model."""
    suffix = draft_path.suffix.lower()
    if suffix not in SUPPORTED_DRAFT_EXTENSIONS:
        msg = f"Unsupported draft file extension: {suffix or '<none>'}"
        raise ValueError(msg)
    if not draft_path.exists() or not draft_path.is_file():
        msg = f"Draft file not found: {draft_path}"
        raise FileNotFoundError(msg)

    if suffix == ".docx":
        normalized_text = _extract_docx_text(draft_path)
    else:
        raw_text = draft_path.read_text(encoding="utf-8")
        normalized_text = normalize_draft_text(raw_text)
    if not normalized_text.strip():
        msg = f"Draft file is empty after normalization: {draft_path}"
        raise ValueError(msg)

    return Document(
        document_id=f"doc-{draft_path.stem}",
        text=normalized_text,
        source_path=str(draft_path.resolve()),
        paragraphs=_paragraphs_from_text(normalized_text),
    )
