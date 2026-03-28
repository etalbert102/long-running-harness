"""Tests for discourse-scaffolding phrase counting and repetition warnings."""

from __future__ import annotations

import pytest

from editorial_fit_compiler.analyzers import (
    count_discourse_scaffolding_phrases,
    count_discourse_scaffolding_phrases_in_paragraphs,
)
from editorial_fit_compiler.core.models import Paragraph


def test_count_discourse_scaffolding_phrases_emits_counts_and_repetition_warning() -> None:
    """Free-text analysis should return phrase counts and repeated scaffolding warnings."""
    text = (
        "In other words, we need to act. "
        "In other words, results matter. "
        "To be clear, timing matters."
    )

    metrics = count_discourse_scaffolding_phrases(text)

    assert metrics.scaffolding_phrase_count == 3
    assert metrics.word_count == 17
    assert metrics.scaffolding_phrase_density_score == pytest.approx(3 / 17)
    assert tuple(span.scaffolding_phrase for span in metrics.evidence_spans) == (
        "in other words",
        "in other words",
        "to be clear",
    )
    assert len(metrics.repetition_warnings) == 1
    warning = metrics.repetition_warnings[0]
    assert warning.scaffolding_phrase == "in other words"
    assert warning.occurrence_count == 2
    assert warning.first_start_char == text.index("In other words")
    assert warning.last_end_char == text.index("In other words", 1) + len("In other words")
    assert warning.paragraph_ids == ()


def test_count_discourse_scaffolding_phrases_in_paragraphs_tracks_ids_and_offsets() -> None:
    """Paragraph analysis should preserve paragraph IDs and absolute warning spans."""
    first_text = "In other words, policy moves slowly."
    second_text = "To be clear, timelines matter. In other words, implementation lags."
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

    metrics = count_discourse_scaffolding_phrases_in_paragraphs(paragraphs)

    assert metrics.scaffolding_phrase_count == 3
    assert metrics.word_count == 16
    assert metrics.scaffolding_phrase_density_score == pytest.approx(3 / 16)
    assert tuple(span.paragraph_id for span in metrics.evidence_spans) == ("p1", "p2", "p2")
    assert tuple(span.start_char for span in metrics.evidence_spans) == (
        first_text.index("In other words"),
        second_start + second_text.index("To be clear"),
        second_start + second_text.index("In other words"),
    )
    assert len(metrics.repetition_warnings) == 1
    warning = metrics.repetition_warnings[0]
    assert warning.scaffolding_phrase == "in other words"
    assert warning.occurrence_count == 2
    assert warning.first_start_char == first_text.index("In other words")
    assert warning.last_end_char == second_start + second_text.index("In other words") + len(
        "In other words"
    )
    assert warning.paragraph_ids == ("p1", "p2")
