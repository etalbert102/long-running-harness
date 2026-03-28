"""Tests for markdown bullet/list-item detection and paragraph locations."""

from __future__ import annotations

from editorial_fit_compiler.analyzers import (
    detect_bullet_usage,
    detect_bullet_usage_in_paragraphs,
)
from editorial_fit_compiler.core.models import Paragraph


def test_detect_bullet_usage_reports_count_statistics_from_markdown_text() -> None:
    """Free-text bullet analysis should return ordered/unordered count statistics."""
    text = (
        "Overview paragraph.\n"
        "- first bullet\n"
        "* second bullet\n"
        "1. ordered item\n"
        "2) ordered item two\n"
    )

    metrics = detect_bullet_usage(text)

    assert metrics.total_bullet_count == 4
    assert metrics.unordered_bullet_count == 2
    assert metrics.ordered_bullet_count == 2
    assert metrics.bullet_paragraph_count == 0
    assert metrics.bullet_paragraph_ids == ()
    assert tuple(span.marker_type for span in metrics.evidence_spans) == (
        "unordered",
        "unordered",
        "ordered",
        "ordered",
    )


def test_detect_bullet_usage_in_paragraphs_reports_bullet_paragraph_locations() -> None:
    """Paragraph-based analysis should return bullet counts and paragraph IDs with bullets."""
    paragraph_one_text = "Intro paragraph without list items."
    paragraph_two_text = "- alpha\n- beta\n2. gamma"
    paragraph_three_text = "Closing paragraph."
    paragraph_two_start = len(paragraph_one_text) + 2
    paragraph_three_start = paragraph_two_start + len(paragraph_two_text) + 2
    paragraphs = (
        Paragraph(
            paragraph_id="p1",
            text=paragraph_one_text,
            start_char=0,
            end_char=len(paragraph_one_text),
            sentences=(),
        ),
        Paragraph(
            paragraph_id="p2",
            text=paragraph_two_text,
            start_char=paragraph_two_start,
            end_char=paragraph_two_start + len(paragraph_two_text),
            sentences=(),
        ),
        Paragraph(
            paragraph_id="p3",
            text=paragraph_three_text,
            start_char=paragraph_three_start,
            end_char=paragraph_three_start + len(paragraph_three_text),
            sentences=(),
        ),
    )

    metrics = detect_bullet_usage_in_paragraphs(paragraphs)

    assert metrics.total_bullet_count == 3
    assert metrics.unordered_bullet_count == 2
    assert metrics.ordered_bullet_count == 1
    assert metrics.bullet_paragraph_count == 1
    assert metrics.bullet_paragraph_ids == ("p2",)
    assert tuple(span.paragraph_id for span in metrics.evidence_spans) == ("p2", "p2", "p2")
    assert tuple(span.start_char for span in metrics.evidence_spans) == (
        paragraph_two_start + paragraph_two_text.index("- alpha"),
        paragraph_two_start + paragraph_two_text.index("- beta"),
        paragraph_two_start + paragraph_two_text.index("2. gamma"),
    )
