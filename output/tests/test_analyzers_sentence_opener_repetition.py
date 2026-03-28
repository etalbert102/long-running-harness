"""Tests for repeated sentence-opener analysis and nearby clustering severity."""

from __future__ import annotations

import pytest

from editorial_fit_compiler.analyzers import (
    detect_repeated_sentence_openers,
    detect_repeated_sentence_openers_in_paragraphs,
)
from editorial_fit_compiler.core.models import Paragraph, Sentence


def _build_sentence(sentence_id: str, text: str, start_char: int) -> Sentence:
    """Create a sentence model with deterministic character offsets."""
    return Sentence(
        sentence_id=sentence_id,
        text=text,
        start_char=start_char,
        end_char=start_char + len(text),
    )


def test_detect_repeated_sentence_openers_forms_cluster_with_medium_severity() -> None:
    """Nearby opener repetition should produce a cluster and medium severity for three repeats."""
    texts = (
        "In this context, policy adapts slowly.",
        "In this context, implementation follows.",
        "The committee revised guidance.",
        "In this context, funding remains uneven.",
    )
    offset = 0
    sentences: list[Sentence] = []
    for index, text in enumerate(texts, start=1):
        sentence = _build_sentence(f"s{index}", text, offset)
        sentences.append(sentence)
        offset = sentence.end_char + 1

    metrics = detect_repeated_sentence_openers(sentences)

    assert metrics.sentence_count == 4
    assert metrics.opener_pattern_count == 4
    assert len(metrics.repeated_pattern_clusters) == 1
    cluster = metrics.repeated_pattern_clusters[0]
    assert cluster.opener == "in this"
    assert cluster.occurrence_count == 3
    assert cluster.first_sentence_index == 0
    assert cluster.last_sentence_index == 3
    assert cluster.max_sentence_gap == 2
    assert cluster.severity == "medium"
    assert cluster.sentence_ids == ("s1", "s2", "s4")
    assert cluster.paragraph_ids == ()
    assert cluster.first_start_char == sentences[0].start_char
    assert cluster.last_end_char == sentences[3].end_char


def test_detect_repeated_sentence_openers_splits_distant_repeats_by_window() -> None:
    """Repeated openers outside the nearby window should not merge into one cluster."""
    texts = (
        "In this context, policy adapts slowly.",
        "In this context, implementation follows.",
        "Results remained mixed.",
        "Leaders debated alternatives.",
        "The report closed with next steps.",
        "In this context, compliance improved.",
    )
    offset = 0
    sentences: list[Sentence] = []
    for index, text in enumerate(texts, start=1):
        sentence = _build_sentence(f"s{index}", text, offset)
        sentences.append(sentence)
        offset = sentence.end_char + 1

    metrics = detect_repeated_sentence_openers(
        sentences,
        nearby_sentence_window=1,
    )

    assert len(metrics.repeated_pattern_clusters) == 1
    cluster = metrics.repeated_pattern_clusters[0]
    assert cluster.opener == "in this"
    assert cluster.occurrence_count == 2
    assert cluster.first_sentence_index == 0
    assert cluster.last_sentence_index == 1
    assert cluster.max_sentence_gap == 1
    assert cluster.severity == "low"
    assert cluster.sentence_ids == ("s1", "s2")


def test_detect_repeated_sentence_openers_in_paragraphs_tracks_paragraph_ids() -> None:
    """Paragraph-based analysis should preserve paragraph IDs in repeated opener clusters."""
    p1_text = "In this context, policy adapts slowly. In this context, implementation follows."
    p2_text = "In this context, funding remains uneven."
    p1_sentences = (
        _build_sentence("s1", "In this context, policy adapts slowly.", 0),
        _build_sentence(
            "s2",
            "In this context, implementation follows.",
            len("In this context, policy adapts slowly. "),
        ),
    )
    p2_start = len(p1_text) + 2
    p2_sentences = (_build_sentence("s3", p2_text, p2_start),)
    paragraphs = (
        Paragraph(
            paragraph_id="p1",
            text=p1_text,
            start_char=0,
            end_char=len(p1_text),
            sentences=p1_sentences,
        ),
        Paragraph(
            paragraph_id="p2",
            text=p2_text,
            start_char=p2_start,
            end_char=p2_start + len(p2_text),
            sentences=p2_sentences,
        ),
    )

    metrics = detect_repeated_sentence_openers_in_paragraphs(paragraphs)

    assert metrics.sentence_count == 3
    assert metrics.opener_pattern_count == 3
    assert len(metrics.repeated_pattern_clusters) == 1
    cluster = metrics.repeated_pattern_clusters[0]
    assert cluster.occurrence_count == 3
    assert cluster.severity == "medium"
    assert cluster.sentence_ids == ("s1", "s2", "s3")
    assert cluster.paragraph_ids == ("p1", "p2")


def test_detect_repeated_sentence_openers_in_paragraphs_handles_duplicate_sentence_ids() -> None:
    """Paragraph linkage should remain correct even when sentence IDs repeat across paragraphs."""
    p1_text = "In this context, the first paragraph opens."
    p2_text = "In this context, the second paragraph opens."
    p1_sentences = (_build_sentence("s1", p1_text, 0),)
    p2_start = len(p1_text) + 2
    p2_sentences = (_build_sentence("s1", p2_text, p2_start),)
    paragraphs = (
        Paragraph(
            paragraph_id="p1",
            text=p1_text,
            start_char=0,
            end_char=len(p1_text),
            sentences=p1_sentences,
        ),
        Paragraph(
            paragraph_id="p2",
            text=p2_text,
            start_char=p2_start,
            end_char=p2_start + len(p2_text),
            sentences=p2_sentences,
        ),
    )

    metrics = detect_repeated_sentence_openers_in_paragraphs(paragraphs)

    assert len(metrics.repeated_pattern_clusters) == 1
    cluster = metrics.repeated_pattern_clusters[0]
    assert cluster.sentence_ids == ("s1", "s1")
    assert cluster.paragraph_ids == ("p1", "p2")


def test_detect_repeated_sentence_openers_supports_unicode_openers() -> None:
    """Unicode letters in opener tokens should be preserved for matching."""
    sentences = (
        _build_sentence("s1", "Élan vital shapes reform.", 0),
        _build_sentence("s2", "Élan vital drives consensus.", 28),
    )

    metrics = detect_repeated_sentence_openers(sentences)

    assert len(metrics.repeated_pattern_clusters) == 1
    cluster = metrics.repeated_pattern_clusters[0]
    assert cluster.opener == "élan vital"
    assert cluster.sentence_ids == ("s1", "s2")


@pytest.mark.parametrize(
    ("kwargs", "expected_message"),
    [
        ({"opener_token_count": 0}, "opener_token_count must be at least 1"),
        ({"nearby_sentence_window": 0}, "nearby_sentence_window must be at least 1"),
        ({"min_cluster_occurrences": 1}, "min_cluster_occurrences must be at least 2"),
    ],
)
def test_detect_repeated_sentence_openers_rejects_invalid_parameters(
    kwargs: dict[str, int],
    expected_message: str,
) -> None:
    """Invalid analysis parameters should fail fast with actionable errors."""
    sentences = (_build_sentence("s1", "In this context, policy adapts slowly.", 0),)

    with pytest.raises(ValueError, match=expected_message):
        detect_repeated_sentence_openers(sentences, **kwargs)
