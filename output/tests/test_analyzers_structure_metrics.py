"""Tests for baseline structure metrics analyzer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from editorial_fit_compiler.analyzers import (
    compute_paragraph_length_distribution,
    compute_paragraph_length_distribution_from_paragraphs,
    compute_sentence_length_distribution,
    compute_sentence_length_distribution_from_paragraphs,
    compute_structure_metrics,
)
from editorial_fit_compiler.core.models import Paragraph, Sentence
from editorial_fit_compiler.core.segmentation import segment_normalized_paragraphs


def _analyzers_fixture_path(filename: str) -> Path:
    """Return a fixture path for analyzer tests."""
    return Path(__file__).parent / "fixtures" / "analyzers" / filename


def test_compute_structure_metrics_matches_fixture_expectations() -> None:
    """Word, section, and paragraph counts should match fixture expectations."""
    draft_text = _analyzers_fixture_path("structure_metrics_draft.md").read_text(encoding="utf-8")
    expected_metrics = json.loads(
        _analyzers_fixture_path("structure_metrics_expected.json").read_text(encoding="utf-8")
    )
    segmented_paragraphs = segment_normalized_paragraphs(draft_text)

    metrics = compute_structure_metrics(segmented_paragraphs)

    assert metrics.word_count == expected_metrics["word_count"]
    assert metrics.section_count == expected_metrics["section_count"]
    assert metrics.paragraph_count == expected_metrics["paragraph_count"]


def test_compute_structure_metrics_handles_empty_segmented_input() -> None:
    """Empty segmented drafts should produce zero-valued metrics."""
    metrics = compute_structure_metrics(())

    assert metrics.word_count == 0
    assert metrics.section_count == 0
    assert metrics.paragraph_count == 0


def test_compute_sentence_length_distribution_reports_average_spread_and_uniform_cadence() -> None:
    """Sentence distribution should report average, spread, and narrow-band cadence indicators."""
    metrics = compute_sentence_length_distribution((10, 12, 11, 9, 10))

    assert metrics.sentence_count == 5
    assert metrics.average_tokens == pytest.approx(10.4)
    assert metrics.variance_tokens == pytest.approx(1.04)
    assert metrics.std_dev_tokens == pytest.approx(1.0198039)
    assert metrics.min_tokens == 9
    assert metrics.max_tokens == 12
    assert metrics.spread_tokens == 3
    assert metrics.cadence_uniformity_ratio == pytest.approx(1.0)
    assert metrics.cadence_narrow_band is True


def test_compute_sentence_length_distribution_flags_non_uniform_cadence() -> None:
    """Large sentence-length spread should not be treated as narrow-band cadence."""
    metrics = compute_sentence_length_distribution((3, 30, 8, 22, 14))

    assert metrics.sentence_count == 5
    assert metrics.average_tokens == pytest.approx(15.4)
    assert metrics.variance_tokens == pytest.approx(93.44)
    assert metrics.std_dev_tokens == pytest.approx(9.6664368)
    assert metrics.spread_tokens == 27
    assert metrics.cadence_uniformity_ratio == pytest.approx(0.2)
    assert metrics.cadence_narrow_band is False


def test_compute_sentence_length_distribution_rejects_negative_counts() -> None:
    """Negative token counts are invalid and should raise an actionable error."""
    with pytest.raises(ValueError, match="non-negative"):
        compute_sentence_length_distribution((4, -1, 6))


def test_compute_sentence_length_distribution_from_paragraphs_uses_sentence_tokens() -> None:
    """Paragraph sentence text should be converted into sentence-level token counts."""
    paragraphs = (
        Paragraph(
            paragraph_id="p1",
            text="One two three. Four five six seven.",
            start_char=0,
            end_char=34,
            sentences=(
                Sentence(sentence_id="p1s1", text="One two three.", start_char=0, end_char=14),
                Sentence(
                    sentence_id="p1s2",
                    text="Four five six seven.",
                    start_char=15,
                    end_char=34,
                ),
            ),
        ),
        Paragraph(
            paragraph_id="p2",
            text="Eight nine ten eleven twelve.",
            start_char=35,
            end_char=64,
            sentences=(
                Sentence(
                    sentence_id="p2s1",
                    text="Eight nine ten eleven twelve.",
                    start_char=35,
                    end_char=64,
                ),
            ),
        ),
    )

    metrics = compute_sentence_length_distribution_from_paragraphs(paragraphs)

    assert metrics.sentence_count == 3
    assert metrics.average_tokens == pytest.approx(4.0)
    assert metrics.variance_tokens == pytest.approx(2 / 3)
    assert metrics.spread_tokens == 2
    assert metrics.cadence_uniformity_ratio == pytest.approx(1 / 3)
    assert metrics.cadence_narrow_band is False


def test_compute_paragraph_length_distribution_flags_outlier_long_and_short_paragraphs() -> None:
    """Paragraph distribution should flag unusually short and long token-count outliers."""
    metrics = compute_paragraph_length_distribution((1, 40, 41, 42, 43, 44, 100))

    assert metrics.paragraph_count == 7
    assert metrics.average_tokens == pytest.approx(44.4285714)
    assert metrics.variance_tokens == pytest.approx(716.2448979)
    assert metrics.std_dev_tokens == pytest.approx(26.76275206)
    assert metrics.min_tokens == 1
    assert metrics.max_tokens == 100
    assert metrics.spread_tokens == 99
    assert metrics.q1_tokens == pytest.approx(40.5)
    assert metrics.q3_tokens == pytest.approx(43.5)
    assert metrics.iqr_tokens == pytest.approx(3.0)
    assert metrics.lower_outlier_threshold == pytest.approx(36.0)
    assert metrics.upper_outlier_threshold == pytest.approx(48.0)
    assert metrics.short_outlier_indices == (0,)
    assert metrics.long_outlier_indices == (6,)


def test_compute_paragraph_length_distribution_handles_empty_input() -> None:
    """Empty paragraph counts should produce zero-valued metrics and no outliers."""
    metrics = compute_paragraph_length_distribution(())

    assert metrics.paragraph_count == 0
    assert metrics.average_tokens == pytest.approx(0.0)
    assert metrics.variance_tokens == pytest.approx(0.0)
    assert metrics.std_dev_tokens == pytest.approx(0.0)
    assert metrics.min_tokens == 0
    assert metrics.max_tokens == 0
    assert metrics.spread_tokens == 0
    assert metrics.q1_tokens == pytest.approx(0.0)
    assert metrics.q3_tokens == pytest.approx(0.0)
    assert metrics.iqr_tokens == pytest.approx(0.0)
    assert metrics.short_outlier_indices == ()
    assert metrics.long_outlier_indices == ()


def test_compute_paragraph_length_distribution_rejects_negative_counts() -> None:
    """Negative paragraph token counts are invalid and should raise an actionable error."""
    with pytest.raises(ValueError, match="non-negative"):
        compute_paragraph_length_distribution((4, -1, 9))


def test_compute_paragraph_length_distribution_from_paragraphs_uses_paragraph_tokens() -> None:
    """Paragraph text should be converted into paragraph-level token counts."""
    paragraphs = (
        Paragraph(
            paragraph_id="p1",
            text="one two three four",
            start_char=0,
            end_char=18,
            sentences=(),
        ),
        Paragraph(
            paragraph_id="p2",
            text="alpha beta gamma delta epsilon zeta eta theta",
            start_char=19,
            end_char=63,
            sentences=(),
        ),
        Paragraph(
            paragraph_id="p3",
            text="x",
            start_char=64,
            end_char=65,
            sentences=(),
        ),
        Paragraph(
            paragraph_id="p4",
            text="lorem ipsum dolor sit amet consectetur adipiscing elit",
            start_char=66,
            end_char=120,
            sentences=(),
        ),
        Paragraph(
            paragraph_id="p5",
            text="tiny",
            start_char=121,
            end_char=125,
            sentences=(),
        ),
    )

    metrics = compute_paragraph_length_distribution_from_paragraphs(paragraphs)

    assert metrics.paragraph_count == 5
    assert metrics.average_tokens == pytest.approx(4.4)
    assert metrics.q1_tokens == pytest.approx(1.0)
    assert metrics.q3_tokens == pytest.approx(8.0)
    assert metrics.short_outlier_indices == ()
    assert metrics.long_outlier_indices == ()
