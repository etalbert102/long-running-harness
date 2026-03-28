"""Draft ingestion helpers for supported draft inputs."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from editorial_fit_compiler.core.models import Document, Paragraph

SUPPORTED_DRAFT_EXTENSIONS: tuple[str, ...] = (".md", ".txt", ".docx")
_URL_FRAGMENT_RE = re.compile(r"^(?:https?://|www\.)\S*$")
_EMAIL_FRAGMENT_RE = re.compile(r"^[^\s@]+@[^\s@]*$")
_TOKEN_HEAD_RE = re.compile(r"^\S+")
_TOKEN_TAIL_RE = re.compile(r"\S+$")


def _merge_wrapped_line(previous: str, current: str) -> str:
    """Merge two logical lines while preserving token semantics across wraps."""
    if not previous:
        return current
    if not current:
        return previous

    previous_tail_match = _TOKEN_TAIL_RE.search(previous)
    current_head_match = _TOKEN_HEAD_RE.search(current)
    previous_tail = previous_tail_match.group(0) if previous_tail_match else ""
    current_head = current_head_match.group(0) if current_head_match else ""

    if re.search(r"[A-Za-z]-$", previous_tail) and re.match(r"^[A-Za-z]", current_head):
        # Treat terminal hyphen + alpha-start as a discretionary wrap hyphen.
        return f"{previous[:-1]}{current}"

    if _URL_FRAGMENT_RE.match(previous_tail):
        return f"{previous}{current}"
    if _EMAIL_FRAGMENT_RE.match(previous_tail):
        return f"{previous}{current}"
    if previous_tail.endswith(("/", "@", ":", "=", "+", "_", "\\")):
        return f"{previous}{current}"

    return f"{previous} {current}"


def _normalize_paragraph_lines(lines: list[str]) -> str:
    """Normalize wrapped lines inside one paragraph without changing token meaning."""
    if not lines:
        return ""
    merged = lines[0]
    for line in lines[1:]:
        merged = _merge_wrapped_line(merged, line)
    return merged


def normalize_draft_text(raw_text: str) -> str:
    """Normalize raw text into canonical paragraph-separated prose.

    The normalization rules preserve token meaning while producing deterministic
    whitespace:
    - line endings are normalized to ``\n``
    - horizontal whitespace runs collapse to a single space
    - one or more blank lines delimit paragraphs
    - line wraps inside a paragraph collapse deterministically, preserving tokens
    """
    normalized_line_endings = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized_line_endings.startswith("\ufeff"):
        normalized_line_endings = normalized_line_endings[1:]

    lines = normalized_line_endings.split("\n")
    paragraphs: list[str] = []
    current_paragraph_lines: list[str] = []

    for line in lines:
        canonical_line = re.sub(r"[^\S\n]+", " ", line).strip()
        if not canonical_line:
            if current_paragraph_lines:
                paragraphs.append(_normalize_paragraph_lines(current_paragraph_lines))
                current_paragraph_lines = []
            continue
        current_paragraph_lines.append(canonical_line)

    if current_paragraph_lines:
        paragraphs.append(_normalize_paragraph_lines(current_paragraph_lines))

    return "\n\n".join(paragraphs)


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
    try:
        from docx import Document as DocxDocument
        from docx.table import Table
        from docx.text.paragraph import Paragraph as DocxParagraph
    except ModuleNotFoundError as exc:
        msg = (
            "DOCX ingestion requires python-docx. Install dependencies with "
            "`pip install -e .` or `pip install python-docx`."
        )
        raise RuntimeError(msg) from exc

    try:
        docx_document = DocxDocument(str(draft_path))
    except Exception as exc:
        msg = (
            f"Unable to read DOCX draft: {draft_path}. Ensure it is a valid, "
            "non-corrupted `.docx` file."
        )
        raise ValueError(msg) from exc

    def iter_block_texts(container: Any) -> Iterator[str]:
        """Yield paragraph text from paragraphs and table cells in source order."""
        if hasattr(container, "element") and hasattr(container.element, "body"):
            parent_element = container.element.body
        elif hasattr(container, "_tc"):
            parent_element = container._tc
        else:
            return

        for child in parent_element.iterchildren():
            if child.tag.endswith("}p"):
                paragraph = DocxParagraph(child, container)
                paragraph_text = paragraph.text.strip()
                if paragraph_text:
                    yield paragraph_text
                continue
            if not child.tag.endswith("}tbl"):
                continue
            table = Table(child, container)
            for row in table.rows:
                seen_cells: set[int] = set()
                for cell in row.cells:
                    cell_id = id(cell._tc)
                    if cell_id in seen_cells:
                        continue
                    seen_cells.add(cell_id)
                    yield from iter_block_texts(cell)

    paragraph_texts = list(iter_block_texts(docx_document))
    return normalize_draft_text("\n\n".join(paragraph_texts))


def load_document_from_text(raw_text: str, *, source_name: str = "<stdin>") -> Document:
    """Load raw draft text into a normalized document model."""
    normalized_text = normalize_draft_text(raw_text)
    if not normalized_text.strip():
        msg = f"Draft text is empty after normalization: {source_name}"
        raise ValueError(msg)

    return Document(
        document_id=f"doc-{source_name.strip('<>') or 'input'}",
        text=normalized_text,
        source_path=source_name,
        paragraphs=_paragraphs_from_text(normalized_text),
    )


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
        normalized_text = raw_text
    return load_document_from_text(normalized_text, source_name=str(draft_path.resolve()))
