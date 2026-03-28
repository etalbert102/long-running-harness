"""Tests for abstraction-heavy phrase counting with configurable phrase banks."""

from __future__ import annotations

import pytest

from editorial_fit_compiler.analyzers import (
    count_abstraction_phrases,
    count_abstraction_phrases_in_paragraphs,
)
from editorial_fit_compiler.core.models import Paragraph


def test_count_abstraction_phrases_returns_matched_phrases_and_density() -> None:
    """Document analysis should return matched abstraction phrases and density metrics."""
    text = (
        "At a high level we discuss structural dynamics. "
        "In many ways this is a broader context."
    )

    metrics = count_abstraction_phrases(text)

    assert metrics.abstraction_phrase_count == 4
    assert metrics.word_count == 16
    assert metrics.abstraction_phrase_density_score == pytest.approx(4 / 16)
    assert tuple(span.abstraction_phrase for span in metrics.evidence_spans) == (
        "at a high level",
        "structural dynamics",
        "in many ways",
        "broader context",
    )
    assert tuple(span.start_char for span in metrics.evidence_spans) == (
        text.index("At a high level"),
        text.index("structural dynamics"),
        text.index("In many ways"),
        text.index("broader context"),
    )


def test_count_abstraction_phrases_uses_custom_phrase_bank() -> None:
    """Caller-provided phrase banks should fully control abstraction phrase matching."""
    text = "This framing uses policy abstraction and strategic ambiguity."

    metrics = count_abstraction_phrases(
        text,
        phrase_bank=("policy abstraction", "strategic ambiguity"),
    )

    assert metrics.abstraction_phrase_count == 2
    assert metrics.word_count == 8
    assert metrics.abstraction_phrase_density_score == pytest.approx(2 / 8)
    assert tuple(span.abstraction_phrase for span in metrics.evidence_spans) == (
        "policy abstraction",
        "strategic ambiguity",
    )


def test_count_abstraction_phrases_prefers_longest_non_overlapping_match() -> None:
    """Overlapping phrase-bank entries should resolve to a deterministic longest match."""
    text = "The broader context matters."

    metrics = count_abstraction_phrases(
        text,
        phrase_bank=("broader", "broader context"),
    )

    assert metrics.abstraction_phrase_count == 1
    assert metrics.word_count == 4
    assert metrics.abstraction_phrase_density_score == pytest.approx(1 / 4)
    assert tuple(span.abstraction_phrase for span in metrics.evidence_spans) == ("broader context",)


def test_count_abstraction_phrases_in_paragraphs_returns_absolute_offsets() -> None:
    """Paragraph analysis should include paragraph IDs and absolute source offsets."""
    first_text = "At a high level we discuss choices."
    second_text = "In many ways the broader context dominates."
    second_start = len(first_text) + 2
    paragraphs = (
        Paragraph(
            paragraph_id="p1",
            text=first_text,
            start_char=0,
            end_char=len(first_text),
            sentences=(),
        ),
        Paragraph(
            paragraph_id="p2",
            text=second_text,
            start_char=second_start,
            end_char=second_start + len(second_text),
            sentences=(),
        ),
    )

    metrics = count_abstraction_phrases_in_paragraphs(paragraphs)

    assert metrics.abstraction_phrase_count == 3
    assert metrics.word_count == 14
    assert metrics.abstraction_phrase_density_score == pytest.approx(3 / 14)
    assert tuple(span.paragraph_id for span in metrics.evidence_spans) == ("p1", "p2", "p2")
    assert tuple(span.start_char for span in metrics.evidence_spans) == (
        first_text.index("At a high level"),
        second_start + second_text.index("In many ways"),
        second_start + second_text.index("broader context"),
    )
