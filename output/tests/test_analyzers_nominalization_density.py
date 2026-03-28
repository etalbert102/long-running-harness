"""Tests for nominalization density using suffix and lexicon heuristics."""

from __future__ import annotations

import pytest

from editorial_fit_compiler.analyzers import (
    estimate_nominalization_density,
    estimate_nominalization_density_in_paragraphs,
)
from editorial_fit_compiler.core.models import Paragraph


def test_estimate_nominalization_density_reports_suffix_and_lexicon_matches() -> None:
    """Free-text nominalization analysis should report density and heuristic evidence."""
    text = "Coordination improved after analysis and growth."

    metrics = estimate_nominalization_density(text)

    assert metrics.nominalization_count == 3
    assert metrics.word_count == 6
    assert metrics.nominalization_density_score == pytest.approx(3 / 6)
    assert metrics.paragraph_densities == ()
    assert tuple(span.nominalization for span in metrics.evidence_spans) == (
        "coordination",
        "analysis",
        "growth",
    )
    assert tuple(span.heuristic for span in metrics.evidence_spans) == (
        "suffix",
        "lexicon",
        "lexicon",
    )


def test_estimate_nominalization_density_supports_custom_suffix_and_lexicon() -> None:
    """Caller-provided heuristics should drive what is counted as nominalization."""
    text = "Friendship and choice matter while coordination continues."

    metrics = estimate_nominalization_density(
        text,
        nominalization_suffixes=("ship",),
        nominalization_lexicon=("choice",),
    )

    assert metrics.nominalization_count == 2
    assert metrics.word_count == 7
    assert metrics.nominalization_density_score == pytest.approx(2 / 7)
    assert tuple(span.nominalization for span in metrics.evidence_spans) == (
        "friendship",
        "choice",
    )
    assert tuple(span.heuristic for span in metrics.evidence_spans) == ("suffix", "lexicon")


def test_estimate_nominalization_density_allows_custom_suffix_exclusion_behavior() -> None:
    """Suffix exclusions should be caller-configurable for custom heuristics."""
    text = "Business and friendship improved."

    default_metrics = estimate_nominalization_density(
        text,
        nominalization_suffixes=("ness", "ship"),
        nominalization_lexicon=(),
    )
    without_exclusions_metrics = estimate_nominalization_density(
        text,
        nominalization_suffixes=("ness", "ship"),
        nominalization_lexicon=(),
        suffix_exclusion_lexicon=(),
    )

    assert default_metrics.nominalization_count == 1
    assert tuple(span.nominalization for span in default_metrics.evidence_spans) == ("friendship",)
    assert without_exclusions_metrics.nominalization_count == 2
    assert tuple(span.nominalization for span in without_exclusions_metrics.evidence_spans) == (
        "business",
        "friendship",
    )


def test_estimate_nominalization_density_avoids_known_suffix_false_positives() -> None:
    """Suffix matching should not count known lexical false positives such as business."""
    text = "The business expanded after coordination."

    metrics = estimate_nominalization_density(text)

    assert metrics.nominalization_count == 1
    assert metrics.word_count == 5
    assert metrics.nominalization_density_score == pytest.approx(1 / 5)
    assert tuple(span.nominalization for span in metrics.evidence_spans) == ("coordination",)
    assert tuple(span.heuristic for span in metrics.evidence_spans) == ("suffix",)


def test_estimate_nominalization_density_tokenizes_unicode_and_punctuation_boundaries() -> None:
    """Unicode words should contribute to denominator and lexicon hits despite punctuation."""
    text = "Évidence, policy; naïve coordination."

    metrics = estimate_nominalization_density(text)

    assert metrics.nominalization_count == 3
    assert metrics.word_count == 4
    assert metrics.nominalization_density_score == pytest.approx(3 / 4)
    assert tuple(span.nominalization for span in metrics.evidence_spans) == (
        "évidence",
        "policy",
        "coordination",
    )
    assert tuple(span.text for span in metrics.evidence_spans) == (
        "Évidence",
        "policy",
        "coordination",
    )
    assert tuple(span.heuristic for span in metrics.evidence_spans) == (
        "lexicon",
        "lexicon",
        "suffix",
    )


def test_estimate_nominalization_density_handles_canonical_unicode_equivalence() -> None:
    """Composed and decomposed accents should produce equivalent document-level metrics."""
    composed_text = "Évidence supports coordination."
    decomposed_text = "E\u0301vidence supports coordination."

    composed_metrics = estimate_nominalization_density(composed_text)
    decomposed_metrics = estimate_nominalization_density(decomposed_text)

    assert composed_metrics.nominalization_count == 2
    assert decomposed_metrics.nominalization_count == 2
    assert composed_metrics.word_count == 3
    assert decomposed_metrics.word_count == 3
    assert composed_metrics.nominalization_density_score == pytest.approx(2 / 3)
    assert decomposed_metrics.nominalization_density_score == pytest.approx(2 / 3)
    assert tuple(span.nominalization for span in composed_metrics.evidence_spans) == (
        "évidence",
        "coordination",
    )
    assert tuple(span.nominalization for span in decomposed_metrics.evidence_spans) == (
        "évidence",
        "coordination",
    )


def test_estimate_nominalization_density_in_paragraphs_reports_paragraph_and_document_scores(
) -> None:
    """Paragraph analysis should emit per-paragraph and document-level density."""
    paragraph_one_text = "Implementation and coordination improved."
    paragraph_two_text = "Teams adapt quickly."
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

    metrics = estimate_nominalization_density_in_paragraphs(paragraphs)

    assert metrics.nominalization_count == 2
    assert metrics.word_count == 7
    assert metrics.nominalization_density_score == pytest.approx(2 / 7)
    assert tuple(item.paragraph_id for item in metrics.paragraph_densities) == ("p1", "p2")
    assert tuple(item.nominalization_count for item in metrics.paragraph_densities) == (2, 0)
    assert tuple(item.word_count for item in metrics.paragraph_densities) == (4, 3)
    assert tuple(item.nominalization_density_score for item in metrics.paragraph_densities) == (
        pytest.approx(2 / 4),
        pytest.approx(0.0),
    )
    assert tuple(span.paragraph_id for span in metrics.evidence_spans) == ("p1", "p1")
    assert tuple(span.start_char for span in metrics.evidence_spans) == (
        paragraph_one_text.index("Implementation"),
        paragraph_one_text.index("coordination"),
    )


def test_estimate_nominalization_density_in_paragraphs_supports_mixed_case_matching() -> None:
    """Paragraph metrics should preserve IDs while matching nominalizations case-insensitively."""
    first_text = "COORDINATION happens."
    second_text = "Analysis improves."
    second_start = len(first_text) + 1
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

    metrics = estimate_nominalization_density_in_paragraphs(paragraphs)

    assert metrics.nominalization_count == 2
    assert metrics.word_count == 4
    assert metrics.nominalization_density_score == pytest.approx(2 / 4)
    assert tuple(item.paragraph_id for item in metrics.paragraph_densities) == ("p1", "p2")
    assert tuple(item.nominalization_count for item in metrics.paragraph_densities) == (1, 1)
    assert tuple(span.nominalization for span in metrics.evidence_spans) == (
        "coordination",
        "analysis",
    )
    assert tuple(span.text for span in metrics.evidence_spans) == ("COORDINATION", "Analysis")


def test_estimate_nominalization_density_in_paragraphs_handles_canonical_unicode_equivalence(
) -> None:
    """Paragraph-level metrics should remain stable for composed/decomposed accents."""
    first_text = "Évidence supports coordination."
    second_text = "E\u0301vidence supports coordination."
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

    metrics = estimate_nominalization_density_in_paragraphs(paragraphs)

    assert metrics.nominalization_count == 4
    assert metrics.word_count == 6
    assert metrics.nominalization_density_score == pytest.approx(4 / 6)
    assert tuple(item.nominalization_count for item in metrics.paragraph_densities) == (2, 2)
    assert tuple(item.word_count for item in metrics.paragraph_densities) == (3, 3)
    assert tuple(span.paragraph_id for span in metrics.evidence_spans) == ("p1", "p1", "p2", "p2")
    assert tuple(span.nominalization for span in metrics.evidence_spans) == (
        "évidence",
        "coordination",
        "évidence",
        "coordination",
    )
