"""Tests for baseline structure metrics analyzer."""

from __future__ import annotations

import json
from pathlib import Path

from editorial_fit_compiler.analyzers import compute_structure_metrics
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
