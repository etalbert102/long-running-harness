"""Tests for undefined key-term detection in early paragraphs."""

from __future__ import annotations

import pytest

from editorial_fit_compiler.analyzers import (
    detect_undefined_key_terms,
    detect_undefined_key_terms_in_paragraphs,
)
from editorial_fit_compiler.core.models import Paragraph


def test_detect_undefined_key_terms_flags_missing_local_definition() -> None:
    """Terms introduced early without nearby definitions should be flagged."""
    paragraphs = (
        Paragraph(
            paragraph_id="p1",
            text="Decision-Space Erosion threatens board accountability.",
            start_char=0,
            end_char=len("Decision-Space Erosion threatens board accountability."),
            sentences=(),
        ),
        Paragraph(
            paragraph_id="p2",
            text="Authority Topology distorts who can act quickly in crisis.",
            start_char=58,
            end_char=58 + len("Authority Topology distorts who can act quickly in crisis."),
            sentences=(),
        ),
        Paragraph(
            paragraph_id="p3",
            text="A later section discusses implementation details.",
            start_char=120,
            end_char=120 + len("A later section discusses implementation details."),
            sentences=(),
        ),
    )

    metrics = detect_undefined_key_terms_in_paragraphs(paragraphs, first_paragraph_count=2)

    assert metrics.first_paragraph_count == 2
    assert metrics.introduced_key_term_count == 2
    assert metrics.unique_introduced_key_term_count == 2
    assert metrics.undefined_key_term_count == 2
    assert tuple(warning.term for warning in metrics.undefined_key_term_warnings) == (
        "Decision-Space Erosion",
        "Authority Topology",
    )
    assert metrics.undefined_key_term_warnings[0].introduction_paragraph_ids == ("p1",)
    assert metrics.undefined_key_term_warnings[1].introduction_paragraph_ids == ("p2",)


def test_detect_undefined_key_terms_respects_definition_window() -> None:
    """Locally defined terms should not be flagged as undefined."""
    text = (
        "Behavioral Compression degrades decision quality.\n\n"
        "Behavioral Compression is the forced collapse of alternatives under time pressure."
    )

    metrics = detect_undefined_key_terms(
        text,
        first_paragraph_count=1,
        definition_window_paragraphs=1,
    )

    assert metrics.first_paragraph_count == 1
    assert metrics.introduced_key_term_count == 1
    assert metrics.undefined_key_term_count == 0
    assert metrics.undefined_key_term_warnings == ()


@pytest.mark.parametrize(
    ("kwargs", "expected_message"),
    [
        ({"first_paragraph_count": 0}, "first_paragraph_count must be at least 1"),
        (
            {"definition_window_paragraphs": -1},
            "definition_window_paragraphs must be at least 0",
        ),
    ],
)
def test_detect_undefined_key_terms_rejects_invalid_parameters(
    kwargs: dict[str, int],
    expected_message: str,
) -> None:
    """Invalid analyzer parameters should fail fast with actionable errors."""
    with pytest.raises(ValueError, match=expected_message):
        detect_undefined_key_terms("Authority Topology constrains response.", **kwargs)

