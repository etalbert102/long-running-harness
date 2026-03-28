"""Deterministic text segmentation helpers for normalized draft content."""

from __future__ import annotations

from editorial_fit_compiler.core.models import Paragraph

_PARAGRAPH_DELIMITER = "\n\n"


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
