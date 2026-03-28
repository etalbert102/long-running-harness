"""Span utilities for evidence extraction and paragraph-sentence mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from editorial_fit_compiler.core.models import EvidenceSpan, Paragraph


@dataclass(frozen=True, slots=True)
class SentenceIndexMapping:
    """Lookup metadata describing where a sentence appears in paragraph order."""

    paragraph_id: str
    paragraph_index: int
    sentence_index: int


@dataclass(frozen=True, slots=True)
class SpanIndexMapping:
    """Resolved paragraph/sentence index mapping for a character span."""

    paragraph_id: str
    paragraph_index: int
    sentence_id: str | None
    sentence_index: int | None


def extract_span_text(text: str, start_char: int, end_char: int) -> str:
    """Return the exact end-exclusive slice from ``text`` for the given offsets."""
    _validate_span_offsets(text=text, start_char=start_char, end_char=end_char)
    return text[start_char:end_char]


def build_evidence_span(
    text: str,
    start_char: int,
    end_char: int,
    *,
    paragraph_id: str | None = None,
    sentence_id: str | None = None,
) -> EvidenceSpan:
    """Build an ``EvidenceSpan`` with exact extracted text for the provided offsets."""
    return EvidenceSpan(
        text=extract_span_text(text=text, start_char=start_char, end_char=end_char),
        start_char=start_char,
        end_char=end_char,
        paragraph_id=paragraph_id,
        sentence_id=sentence_id,
    )


def build_sentence_index_map(paragraphs: Sequence[Paragraph]) -> dict[str, SentenceIndexMapping]:
    """Map sentence IDs to paragraph/sentence indices for stable reverse lookups."""
    index_map: dict[str, SentenceIndexMapping] = {}

    for paragraph_index, paragraph in enumerate(paragraphs):
        for sentence_index, sentence in enumerate(paragraph.sentences):
            index_map[sentence.sentence_id] = SentenceIndexMapping(
                paragraph_id=paragraph.paragraph_id,
                paragraph_index=paragraph_index,
                sentence_index=sentence_index,
            )

    return index_map


def map_span_to_indices(
    paragraphs: Sequence[Paragraph],
    start_char: int,
    end_char: int,
) -> SpanIndexMapping | None:
    """Resolve paragraph and sentence index metadata that fully contain a span."""
    _validate_span_offsets(text=" " * end_char, start_char=start_char, end_char=end_char)

    for paragraph_index, paragraph in enumerate(paragraphs):
        if paragraph.start_char <= start_char and end_char <= paragraph.end_char:
            for sentence_index, sentence in enumerate(paragraph.sentences):
                if sentence.start_char <= start_char and end_char <= sentence.end_char:
                    return SpanIndexMapping(
                        paragraph_id=paragraph.paragraph_id,
                        paragraph_index=paragraph_index,
                        sentence_id=sentence.sentence_id,
                        sentence_index=sentence_index,
                    )

            return SpanIndexMapping(
                paragraph_id=paragraph.paragraph_id,
                paragraph_index=paragraph_index,
                sentence_id=None,
                sentence_index=None,
            )

    return None


def _validate_span_offsets(text: str, start_char: int, end_char: int) -> None:
    """Validate that offsets are non-negative, ordered, and within ``text`` bounds."""
    if start_char < 0:
        msg = "start_char must be non-negative"
        raise ValueError(msg)
    if end_char <= start_char:
        msg = "end_char must be greater than start_char"
        raise ValueError(msg)
    if end_char > len(text):
        msg = "end_char cannot exceed text length"
        raise ValueError(msg)
