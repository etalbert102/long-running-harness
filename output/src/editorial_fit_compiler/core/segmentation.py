"""Deterministic text segmentation helpers for normalized draft content."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from editorial_fit_compiler.core.models import Paragraph

_PARAGRAPH_DELIMITER = "\n\n"
SentenceSpan = tuple[int, int]


class SentenceSegmentationProvider(Protocol):
    """Provider interface for sentence-boundary segmentation."""

    def segment_sentence_spans(self, paragraph_text: str) -> tuple[SentenceSpan, ...]:
        """Return sentence spans relative to `paragraph_text` using end-exclusive offsets."""


@dataclass(frozen=True, slots=True)
class SentenceSegment:
    """Provider-neutral sentence segment with text and absolute character offsets."""

    text: str
    start_char: int
    end_char: int


def _build_sentence_segments(
    paragraph_text: str,
    spans: tuple[SentenceSpan, ...],
    *,
    offset: int,
) -> tuple[SentenceSegment, ...]:
    """Validate provider spans and materialize sentence segments."""
    segments: list[SentenceSegment] = []
    previous_end = 0
    text_length = len(paragraph_text)

    for start_char, end_char in spans:
        if start_char < 0:
            msg = "sentence span start must be non-negative"
            raise ValueError(msg)
        if end_char <= start_char:
            msg = "sentence span end must be greater than start"
            raise ValueError(msg)
        if end_char > text_length:
            msg = "sentence span end cannot exceed paragraph length"
            raise ValueError(msg)
        if start_char < previous_end:
            msg = "sentence spans must be ordered and non-overlapping"
            raise ValueError(msg)
        previous_end = end_char

        text_segment = paragraph_text[start_char:end_char]
        segments.append(
            SentenceSegment(
                text=text_segment,
                start_char=start_char + offset,
                end_char=end_char + offset,
            )
        )

    return tuple(segments)


def segment_normalized_paragraphs(normalized_text: str) -> tuple[Paragraph, ...]:
    """Segment normalized text into source-ordered paragraphs with stable IDs.

    The input is expected to follow the canonical output contract of
    ``normalize_draft_text`` where paragraph boundaries are represented by
    double-newline delimiters.
    """
    if not normalized_text.strip():
        return ()

    segments = normalized_text.split(_PARAGRAPH_DELIMITER)
    paragraphs: list[Paragraph] = []
    cursor = 0
    paragraph_index = 0

    for segment in segments:
        segment_length = len(segment)
        if not segment.strip():
            cursor += segment_length + len(_PARAGRAPH_DELIMITER)
            continue

        paragraph_index += 1
        start_char = cursor
        end_char = start_char + segment_length
        paragraphs.append(
            Paragraph(
                paragraph_id=f"p{paragraph_index}",
                text=segment,
                start_char=start_char,
                end_char=end_char,
            )
        )
        cursor = end_char + len(_PARAGRAPH_DELIMITER)

    return tuple(paragraphs)


def segment_sentences(
    paragraph_text: str,
    *,
    provider: SentenceSegmentationProvider,
    offset: int = 0,
) -> tuple[SentenceSegment, ...]:
    """Segment paragraph text via a provider-neutral interface.

    Args:
        paragraph_text: Paragraph content to segment.
        provider: Sentence-boundary provider implementation.
        offset: Absolute character-offset base added to each returned span.
    """
    if offset < 0:
        msg = "offset must be non-negative"
        raise ValueError(msg)
    if not paragraph_text.strip():
        return ()

    spans = provider.segment_sentence_spans(paragraph_text)
    return _build_sentence_segments(paragraph_text, spans, offset=offset)
