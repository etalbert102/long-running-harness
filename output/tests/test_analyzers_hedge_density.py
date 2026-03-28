"""Tests for hedge-density scoring and hedge evidence span extraction."""

from __future__ import annotations

import pytest

from editorial_fit_compiler.analyzers import (
    estimate_hedge_density,
    estimate_hedge_density_in_paragraphs,
)
from editorial_fit_compiler.core.models import Paragraph


def test_estimate_hedge_density_returns_density_and_matched_spans() -> None:
    """Free-text hedge analysis should return score and ordered hedge phrase spans."""
    text = (
        "This may work and perhaps it could scale. "
        "It appears to hold under tests."
    )

    metrics = estimate_hedge_density(text)

    assert metrics.hedge_count == 4
    assert metrics.word_count == 14
    assert metrics.hedge_density_score == pytest.approx(4 / 14)
    assert tuple(span.hedge_phrase for span in metrics.evidence_spans) == (
        "may",
        "perhaps",
        "could",
        "appears to",
    )
    assert tuple(span.start_char for span in metrics.evidence_spans) == (
        text.index("may"),
        text.index("perhaps"),
        text.index("could"),
        text.index("appears to"),
    )
    assert tuple(span.end_char for span in metrics.evidence_spans) == (
        text.index("may") + len("may"),
        text.index("perhaps") + len("perhaps"),
        text.index("could") + len("could"),
        text.index("appears to") + len("appears to"),
    )


def test_estimate_hedge_density_uses_configurable_lexicon() -> None:
    """A caller-supplied lexicon should fully define which hedge phrases match."""
    text = "This ostensibly works and reportedly fails in edge cases."

    metrics = estimate_hedge_density(
        text,
        hedge_lexicon=("ostensibly", "reportedly"),
    )

    assert metrics.hedge_count == 2
    assert metrics.word_count == 9
    assert metrics.hedge_density_score == pytest.approx(2 / 9)
    assert tuple(span.hedge_phrase for span in metrics.evidence_spans) == (
        "ostensibly",
        "reportedly",
    )


def test_estimate_hedge_density_in_paragraphs_reports_absolute_offsets() -> None:
    """Paragraph hedge analysis should include absolute offsets and paragraph IDs."""
    paragraph_one_text = "It may pass."
    paragraph_two_text = "It appears to fail and perhaps recover."
    paragraph_two_start = len(paragraph_one_text) + 2
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
    )

    metrics = estimate_hedge_density_in_paragraphs(paragraphs)

    assert metrics.hedge_count == 3
    assert metrics.word_count == 10
    assert metrics.hedge_density_score == pytest.approx(3 / 10)
    assert tuple(span.paragraph_id for span in metrics.evidence_spans) == ("p1", "p2", "p2")
    assert tuple(span.start_char for span in metrics.evidence_spans) == (
        paragraph_one_text.index("may"),
        paragraph_two_start + paragraph_two_text.index("appears to"),
        paragraph_two_start + paragraph_two_text.index("perhaps"),
    )
