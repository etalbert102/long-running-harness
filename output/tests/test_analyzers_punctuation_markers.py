"""Tests for em-dash and forbidden punctuation marker detection."""

from __future__ import annotations

from editorial_fit_compiler.analyzers import (
    detect_forbidden_punctuation,
    detect_forbidden_punctuation_in_paragraphs,
)
from editorial_fit_compiler.core.models import Paragraph


def test_detect_forbidden_punctuation_reports_em_dash_count_and_evidence_spans() -> None:
    """Raw text punctuation detection should return em-dash counts and marker evidence."""
    text = "Alpha\u2014beta. Gamma--delta. Epsilon\u2013zeta."

    metrics = detect_forbidden_punctuation(text)

    assert metrics.em_dash_count == 1
    assert metrics.forbidden_marker_count == 3
    assert tuple(span.marker for span in metrics.evidence_spans) == (
        "em_dash",
        "double_hyphen",
        "en_dash",
    )
    assert tuple(span.start_char for span in metrics.evidence_spans) == (
        text.index("\u2014"),
        text.index("--"),
        text.index("\u2013"),
    )
    assert tuple(span.end_char for span in metrics.evidence_spans) == (
        text.index("\u2014") + 1,
        text.index("--") + 2,
        text.index("\u2013") + 1,
    )


def test_detect_forbidden_punctuation_in_paragraphs_reports_absolute_offsets() -> None:
    """Paragraph detection should include paragraph IDs and absolute source offsets."""
    paragraph_one_text = "Intro\u2014note."
    paragraph_two_text = "Body -- detail and aside\u2014appendix."
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
            start_char=len(paragraph_one_text) + 2,
            end_char=len(paragraph_one_text) + 2 + len(paragraph_two_text),
            sentences=(),
        ),
    )

    metrics = detect_forbidden_punctuation_in_paragraphs(paragraphs)

    assert metrics.em_dash_count == 2
    assert metrics.forbidden_marker_count == 3
    assert tuple(span.paragraph_id for span in metrics.evidence_spans) == ("p1", "p2", "p2")
    assert tuple(span.start_char for span in metrics.evidence_spans) == (
        5,
        paragraphs[1].start_char + paragraph_two_text.index("--"),
        paragraphs[1].start_char + paragraph_two_text.index("\u2014"),
    )
    assert tuple(span.end_char for span in metrics.evidence_spans) == (
        6,
        paragraphs[1].start_char + paragraph_two_text.index("--") + 2,
        paragraphs[1].start_char + paragraph_two_text.index("\u2014") + 1,
    )
