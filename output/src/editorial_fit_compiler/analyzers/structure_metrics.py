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


@dataclass(frozen=True, slots=True)
class ParagraphLengthDistributionMetrics:
    """Distribution metrics and outlier flags for paragraph token lengths."""

    paragraph_count: int
    average_tokens: float
    variance_tokens: float
    std_dev_tokens: float
    min_tokens: int
    max_tokens: int
    spread_tokens: int
    q1_tokens: float
    q3_tokens: float
    iqr_tokens: float
    lower_outlier_threshold: float
    upper_outlier_threshold: float
    short_outlier_indices: tuple[int, ...]
    long_outlier_indices: tuple[int, ...]


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


def _percentile(sorted_values: tuple[int, ...], fraction: float) -> float:
    """Compute a percentile using linear interpolation between nearest ranks."""
    if not sorted_values:
        msg = "percentiles require at least one value"
        raise ValueError(msg)
    if not 0 <= fraction <= 1:
        msg = "fraction must be between 0 and 1"
        raise ValueError(msg)

    if len(sorted_values) == 1:
        return float(sorted_values[0])

    index = fraction * (len(sorted_values) - 1)
    lower_index = int(index)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    weight = index - lower_index
    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    return lower_value + (upper_value - lower_value) * weight


def compute_paragraph_length_distribution(
    paragraph_token_counts: Iterable[int],
) -> ParagraphLengthDistributionMetrics:
    """Compute paragraph token distribution metrics and IQR outlier flags."""
    token_counts = tuple(paragraph_token_counts)
    if any(token_count < 0 for token_count in token_counts):
        msg = "paragraph token counts must be non-negative integers"
        raise ValueError(msg)

    if not token_counts:
        return ParagraphLengthDistributionMetrics(
            paragraph_count=0,
            average_tokens=0.0,
            variance_tokens=0.0,
            std_dev_tokens=0.0,
            min_tokens=0,
            max_tokens=0,
            spread_tokens=0,
            q1_tokens=0.0,
            q3_tokens=0.0,
            iqr_tokens=0.0,
            lower_outlier_threshold=0.0,
            upper_outlier_threshold=0.0,
            short_outlier_indices=(),
            long_outlier_indices=(),
        )

    paragraph_count = len(token_counts)
    average_tokens = sum(token_counts) / paragraph_count
    variance_tokens = sum((token_count - average_tokens) ** 2 for token_count in token_counts) / (
        paragraph_count
    )
    std_dev_tokens = sqrt(variance_tokens)
    min_tokens = min(token_counts)
    max_tokens = max(token_counts)
    spread_tokens = max_tokens - min_tokens

    sorted_counts = tuple(sorted(token_counts))
    q1_tokens = _percentile(sorted_counts, 0.25)
    q3_tokens = _percentile(sorted_counts, 0.75)
    iqr_tokens = q3_tokens - q1_tokens
    lower_outlier_threshold = q1_tokens - (1.5 * iqr_tokens)
    upper_outlier_threshold = q3_tokens + (1.5 * iqr_tokens)

    short_outlier_indices = tuple(
        index
        for index, token_count in enumerate(token_counts)
        if token_count < lower_outlier_threshold
    )
    long_outlier_indices = tuple(
        index
        for index, token_count in enumerate(token_counts)
        if token_count > upper_outlier_threshold
    )

    return ParagraphLengthDistributionMetrics(
        paragraph_count=paragraph_count,
        average_tokens=average_tokens,
        variance_tokens=variance_tokens,
        std_dev_tokens=std_dev_tokens,
        min_tokens=min_tokens,
        max_tokens=max_tokens,
        spread_tokens=spread_tokens,
        q1_tokens=q1_tokens,
        q3_tokens=q3_tokens,
        iqr_tokens=iqr_tokens,
        lower_outlier_threshold=lower_outlier_threshold,
        upper_outlier_threshold=upper_outlier_threshold,
        short_outlier_indices=short_outlier_indices,
        long_outlier_indices=long_outlier_indices,
    )


def compute_paragraph_length_distribution_from_paragraphs(
    paragraphs: Iterable[Paragraph],
) -> ParagraphLengthDistributionMetrics:
    """Compute paragraph-length distribution metrics from segmented paragraphs."""
    paragraph_token_counts = tuple(
        len(_WORD_RE.findall(paragraph.text)) for paragraph in paragraphs
    )
    return compute_paragraph_length_distribution(paragraph_token_counts)
