"""Tests for deterministic paragraph segmentation on normalized text."""

from __future__ import annotations

import pytest

from editorial_fit_compiler.core.segmentation import (
    SentenceSpan,
    segment_normalized_paragraphs,
    segment_sentences,
)


class StubSentenceProvider:
    """Test sentence provider that returns preconfigured sentence spans."""

    def __init__(self, spans: tuple[SentenceSpan, ...]) -> None:
        """Create a deterministic provider with fixed output spans."""
        self._spans = spans

    def segment_sentence_spans(self, paragraph_text: str) -> tuple[SentenceSpan, ...]:
        """Return configured spans regardless of paragraph content."""
        _ = paragraph_text
        return self._spans


def test_segment_normalized_paragraphs_preserves_source_order_and_offsets() -> None:
    """Segmentation should preserve paragraph order and exact document offsets."""
    normalized_text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

    paragraphs = segment_normalized_paragraphs(normalized_text)

    assert [paragraph.paragraph_id for paragraph in paragraphs] == ["p1", "p2", "p3"]
    assert [paragraph.text for paragraph in paragraphs] == [
        "First paragraph.",
        "Second paragraph.",
        "Third paragraph.",
    ]
    assert [(paragraph.start_char, paragraph.end_char) for paragraph in paragraphs] == [
        (0, 16),
        (18, 35),
        (37, 53),
    ]


def test_segment_normalized_paragraphs_is_reproducible_for_same_input() -> None:
    """Segmentation should return deterministic paragraph IDs and spans for repeat calls."""
    normalized_text = "Alpha.\n\nBeta.\n\nGamma."

    first_run = segment_normalized_paragraphs(normalized_text)
    second_run = segment_normalized_paragraphs(normalized_text)

    assert [paragraph.model_dump(mode="json") for paragraph in first_run] == [
        paragraph.model_dump(mode="json") for paragraph in second_run
    ]


def test_segment_normalized_paragraphs_ignores_empty_content() -> None:
    """Segmentation should return no paragraphs for blank normalized content."""
    assert segment_normalized_paragraphs("   \n\n\t") == ()


def test_segment_sentences_returns_provider_neutral_spans_and_text() -> None:
    """Sentence segmentation should return text segments with absolute offsets."""
    paragraph_text = "One short sentence. Two more words."
    provider = StubSentenceProvider(((0, 19), (20, 35)))

    segments = segment_sentences(paragraph_text, provider=provider, offset=100)

    assert [segment.text for segment in segments] == [
        "One short sentence.",
        "Two more words.",
    ]
    assert [(segment.start_char, segment.end_char) for segment in segments] == [
        (100, 119),
        (120, 135),
    ]


def test_segment_sentences_returns_empty_for_blank_paragraph() -> None:
    """Blank paragraph text should produce no sentence segments."""
    provider = StubSentenceProvider(((0, 4),))
    assert segment_sentences("  \t", provider=provider) == ()


def test_segment_sentences_rejects_overlapping_provider_spans() -> None:
    """Provider spans must be ordered and non-overlapping."""
    provider = StubSentenceProvider(((0, 5), (4, 8)))

    with pytest.raises(ValueError, match="ordered and non-overlapping"):
        _ = segment_sentences("abcdefghi", provider=provider)
