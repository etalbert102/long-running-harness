"""Baseline structure metrics for segmented drafts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import sqrt
from typing import Iterable

from editorial_fit_compiler.core.models import Paragraph

_WORD_RE = re.compile(r"\b[0-9A-Za-z]+(?:[-'][0-9A-Za-z]+)*\b")
_SECTION_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")


@dataclass(frozen=True, slots=True)
class StructureMetrics:
    """Deterministic baseline metrics for draft structure."""

    word_count: int
    section_count: int
    paragraph_count: int


@dataclass(frozen=True, slots=True)
class SentenceLengthDistributionMetrics:
    """Distribution and cadence metrics for sentence token lengths."""

    sentence_count: int
    average_tokens: float
    variance_tokens: float
    std_dev_tokens: float
    min_tokens: int
    max_tokens: int
    spread_tokens: int
    cadence_uniformity_ratio: float
    cadence_narrow_band: bool


def compute_structure_metrics(paragraphs: Iterable[Paragraph]) -> StructureMetrics:
    """Compute baseline word, section, and paragraph counts from segmented paragraphs."""
    paragraph_list = tuple(paragraphs)
    word_count = sum(len(_WORD_RE.findall(paragraph.text)) for paragraph in paragraph_list)
    section_count = sum(
        1 for paragraph in paragraph_list if _SECTION_HEADING_RE.match(paragraph.text) is not None
    )
    return StructureMetrics(
        word_count=word_count,
        section_count=section_count,
        paragraph_count=len(paragraph_list),
    )


def compute_sentence_length_distribution(
    sentence_token_counts: Iterable[int],
) -> SentenceLengthDistributionMetrics:
    """Compute sentence-length average, spread, and cadence-uniformity indicators."""
    token_counts = tuple(sentence_token_counts)
    if any(token_count < 0 for token_count in token_counts):
        msg = "sentence token counts must be non-negative integers"
        raise ValueError(msg)

    if not token_counts:
        return SentenceLengthDistributionMetrics(
            sentence_count=0,
            average_tokens=0.0,
            variance_tokens=0.0,
            std_dev_tokens=0.0,
            min_tokens=0,
            max_tokens=0,
            spread_tokens=0,
            cadence_uniformity_ratio=0.0,
            cadence_narrow_band=False,
        )

    sentence_count = len(token_counts)
    average_tokens = sum(token_counts) / sentence_count
    variance_tokens = sum((token_count - average_tokens) ** 2 for token_count in token_counts) / (
        sentence_count
    )
    std_dev_tokens = sqrt(variance_tokens)
    min_tokens = min(token_counts)
    max_tokens = max(token_counts)
    spread_tokens = max_tokens - min_tokens

    cadence_band_half_width = average_tokens * 0.2
    lower_bound = average_tokens - cadence_band_half_width
    upper_bound = average_tokens + cadence_band_half_width
    cadence_uniformity_ratio = sum(
        1 for token_count in token_counts if lower_bound <= token_count <= upper_bound
    ) / sentence_count
    cadence_narrow_band = sentence_count >= 3 and cadence_uniformity_ratio >= 0.8

    return SentenceLengthDistributionMetrics(
        sentence_count=sentence_count,
        average_tokens=average_tokens,
        variance_tokens=variance_tokens,
        std_dev_tokens=std_dev_tokens,
        min_tokens=min_tokens,
        max_tokens=max_tokens,
        spread_tokens=spread_tokens,
        cadence_uniformity_ratio=cadence_uniformity_ratio,
        cadence_narrow_band=cadence_narrow_band,
    )


def compute_sentence_length_distribution_from_paragraphs(
    paragraphs: Iterable[Paragraph],
) -> SentenceLengthDistributionMetrics:
    """Compute sentence-length distribution metrics from segmented paragraphs."""
    sentence_token_counts = tuple(
        len(_WORD_RE.findall(sentence.text))
        for paragraph in paragraphs
        for sentence in paragraph.sentences
    )
    return compute_sentence_length_distribution(sentence_token_counts)
