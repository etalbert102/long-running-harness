"""Tests for repeated rhetorical-template analysis with contrast constructions."""

from __future__ import annotations

import pytest

from editorial_fit_compiler.analyzers import (
    detect_repeated_rhetorical_templates,
    detect_repeated_rhetorical_templates_in_paragraphs,
)
from editorial_fit_compiler.core.models import Paragraph


def test_detect_repeated_rhetorical_templates_computes_frequency_and_flags_repetition() -> None:
    """Recurring contrast templates should produce frequencies and repeated warnings."""
    text = (
        "The policy is not final but adaptable. "
        "The rollout was not fast but stable. "
        "The process felt not elegant but practical. "
        "While constraints changed, teams adjusted quickly."
    )

    metrics = detect_repeated_rhetorical_templates(text)

    assert metrics.template_match_count == 4
    assert metrics.word_count == 27
    assert metrics.template_density_score == pytest.approx(4 / 27)
    assert tuple(span.template_key for span in metrics.evidence_spans) == (
        "contrast_not_but",
        "contrast_not_but",
        "contrast_not_but",
        "contrast_while_clause",
    )
    assert tuple(frequency.template_key for frequency in metrics.template_frequencies) == (
        "contrast_not_but",
        "contrast_while_clause",
    )
    assert metrics.template_frequencies[0].occurrence_count == 3
    assert metrics.template_frequencies[0].repeated is True
    assert metrics.template_frequencies[1].occurrence_count == 1
    assert metrics.template_frequencies[1].repeated is False
    assert len(metrics.repeated_template_warnings) == 1
    warning = metrics.repeated_template_warnings[0]
    assert warning.template_key == "contrast_not_but"
    assert warning.occurrence_count == 3
    assert warning.paragraph_ids == ()


def test_detect_repeated_rhetorical_templates_in_paragraphs_tracks_absolute_offsets() -> None:
    """Paragraph analysis should preserve paragraph IDs and absolute warning spans."""
    first_text = "The plan is not perfect but workable."
    second_text = (
        "The timeline is not short but realistic. "
        "Although resistance rose, progress continued."
    )
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

    metrics = detect_repeated_rhetorical_templates_in_paragraphs(paragraphs)

    assert metrics.template_match_count == 3
    assert metrics.word_count == 19
    assert metrics.template_density_score == pytest.approx(3 / 19)
    assert tuple(span.paragraph_id for span in metrics.evidence_spans) == ("p1", "p2", "p2")
    assert tuple(span.start_char for span in metrics.evidence_spans) == (
        first_text.index("not perfect but workable"),
        second_start + second_text.index("not short but realistic"),
        second_start + second_text.index("Although resistance rose, progress continued"),
    )
    assert len(metrics.repeated_template_warnings) == 1
    warning = metrics.repeated_template_warnings[0]
    assert warning.template_key == "contrast_not_but"
    assert warning.occurrence_count == 2
    assert warning.first_start_char == first_text.index("not perfect but workable")
    assert warning.last_end_char == second_start + second_text.index(
        "not short but realistic"
    ) + len("not short but realistic")
    assert warning.paragraph_ids == ("p1", "p2")


def test_detect_repeated_rhetorical_templates_clamps_low_repetition_threshold() -> None:
    """Threshold values below 2 should be clamped to avoid single-match warnings."""
    text = "The policy is not final but adaptable."

    metrics = detect_repeated_rhetorical_templates(
        text,
        repetition_threshold=1,
    )

    assert metrics.template_match_count == 1
    assert len(metrics.repeated_template_warnings) == 0
    assert metrics.template_frequencies[0].repeated is False
