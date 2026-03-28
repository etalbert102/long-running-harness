"""Tests for deterministic paragraph segmentation on normalized text."""

from __future__ import annotations

from editorial_fit_compiler.core.segmentation import segment_normalized_paragraphs


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
