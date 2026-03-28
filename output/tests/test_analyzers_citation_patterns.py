"""Tests for citation-like pattern detection and evidence span offsets."""

from __future__ import annotations

from editorial_fit_compiler.analyzers import (
    detect_citation_like_patterns,
    detect_citation_like_patterns_in_paragraphs,
)
from editorial_fit_compiler.core.models import Paragraph


def test_detect_citation_like_patterns_counts_likely_citations_with_offsets() -> None:
    """Free-text detection should count citation-like patterns and return source spans."""
    text = (
        "A finding appears (Smith, 2020). "
        "Support appears in [12] and [13-15]. "
        "See footnote [^n1]."
    )

    metrics = detect_citation_like_patterns(text)

    assert metrics.likely_citation_count == 4
    assert tuple(span.citation_type for span in metrics.evidence_spans) == (
        "author_year_parenthetical",
        "numeric_bracket",
        "numeric_bracket",
        "markdown_footnote",
    )
    assert tuple(span.start_char for span in metrics.evidence_spans) == (
        text.index("(Smith, 2020)"),
        text.index("[12]"),
        text.index("[13-15]"),
        text.index("[^n1]"),
    )
    assert tuple(span.end_char for span in metrics.evidence_spans) == (
        text.index("(Smith, 2020)") + len("(Smith, 2020)"),
        text.index("[12]") + len("[12]"),
        text.index("[13-15]") + len("[13-15]"),
        text.index("[^n1]") + len("[^n1]"),
    )


def test_detect_citation_like_patterns_in_paragraphs_reports_absolute_offsets() -> None:
    """Paragraph detection should include paragraph IDs and absolute citation offsets."""
    paragraph_one_text = "Claim text (Garcia, 2019)."
    paragraph_two_text = "Evidence [7] and appendix note [^a2]."
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

    metrics = detect_citation_like_patterns_in_paragraphs(paragraphs)

    assert metrics.likely_citation_count == 3
    assert tuple(span.paragraph_id for span in metrics.evidence_spans) == ("p1", "p2", "p2")
    assert tuple(span.start_char for span in metrics.evidence_spans) == (
        paragraph_one_text.index("(Garcia, 2019)"),
        paragraph_two_start + paragraph_two_text.index("[7]"),
        paragraph_two_start + paragraph_two_text.index("[^a2]"),
    )
    assert tuple(span.end_char for span in metrics.evidence_spans) == (
        paragraph_one_text.index("(Garcia, 2019)") + len("(Garcia, 2019)"),
        paragraph_two_start + paragraph_two_text.index("[7]") + len("[7]"),
        paragraph_two_start + paragraph_two_text.index("[^a2]") + len("[^a2]"),
    )
