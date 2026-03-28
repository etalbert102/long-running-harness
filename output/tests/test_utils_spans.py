"""Tests for span helpers used by evidence extraction and index mapping."""

from __future__ import annotations

import pytest

from editorial_fit_compiler.core.models import Paragraph, Sentence
from editorial_fit_compiler.utils.spans import (
    SentenceIndexMapping,
    SpanIndexMapping,
    build_evidence_span,
    build_sentence_index_map,
    extract_span_text,
    map_span_to_indices,
)


def _build_paragraphs() -> tuple[Paragraph, ...]:
    """Create deterministic paragraph and sentence offsets for mapping tests."""
    return (
        Paragraph(
            paragraph_id="p1",
            text="Alpha one. Beta two.",
            start_char=0,
            end_char=20,
            sentences=(
                Sentence(sentence_id="s1", text="Alpha one.", start_char=0, end_char=10),
                Sentence(sentence_id="s2", text="Beta two.", start_char=11, end_char=20),
            ),
        ),
        Paragraph(
            paragraph_id="p2",
            text="Gamma three.",
            start_char=22,
            end_char=34,
            sentences=(
                Sentence(sentence_id="s3", text="Gamma three.", start_char=22, end_char=34),
            ),
        ),
    )


def test_extract_span_text_returns_exact_end_exclusive_slice() -> None:
    """Span extraction should return exact evidence text for the supplied offsets."""
    text = "Alpha one. Beta two.\n\nGamma three."

    extracted = extract_span_text(text, 11, 20)

    assert extracted == "Beta two."


def test_extract_span_text_rejects_offsets_outside_text_bounds() -> None:
    """Out-of-range offsets should fail fast with a descriptive error."""
    with pytest.raises(ValueError, match="cannot exceed text length"):
        _ = extract_span_text("short", 0, 10)


def test_build_evidence_span_materializes_text_and_ids() -> None:
    """Evidence span helper should include exact text and optional source IDs."""
    text = "Alpha one. Beta two."

    span = build_evidence_span(text, 11, 20, paragraph_id="p1", sentence_id="s2")

    assert span.text == "Beta two."
    assert span.start_char == 11
    assert span.end_char == 20
    assert span.paragraph_id == "p1"
    assert span.sentence_id == "s2"


def test_build_sentence_index_map_returns_paragraph_sentence_positions() -> None:
    """Sentence IDs should map to deterministic paragraph and sentence indexes."""
    paragraphs = _build_paragraphs()

    index_map = build_sentence_index_map(paragraphs)

    assert index_map == {
        "s1": SentenceIndexMapping(paragraph_id="p1", paragraph_index=0, sentence_index=0),
        "s2": SentenceIndexMapping(paragraph_id="p1", paragraph_index=0, sentence_index=1),
        "s3": SentenceIndexMapping(paragraph_id="p2", paragraph_index=1, sentence_index=0),
    }


def test_map_span_to_indices_returns_sentence_and_paragraph_mapping() -> None:
    """Span-to-index mapping should resolve both paragraph and sentence when contained."""
    paragraphs = _build_paragraphs()

    mapping = map_span_to_indices(paragraphs, 11, 20)

    assert mapping == SpanIndexMapping(
        paragraph_id="p1",
        paragraph_index=0,
        sentence_id="s2",
        sentence_index=1,
    )


def test_map_span_to_indices_returns_paragraph_mapping_without_sentence_match() -> None:
    """A paragraph-contained span crossing sentence boundaries should omit sentence mapping."""
    paragraphs = _build_paragraphs()

    mapping = map_span_to_indices(paragraphs, 9, 12)

    assert mapping == SpanIndexMapping(
        paragraph_id="p1",
        paragraph_index=0,
        sentence_id=None,
        sentence_index=None,
    )


def test_map_span_to_indices_returns_none_when_span_not_in_any_paragraph() -> None:
    """Spans outside all paragraph offsets should return no mapping."""
    paragraphs = _build_paragraphs()

    mapping = map_span_to_indices(paragraphs, 40, 45)

    assert mapping is None
