"""Analyzer package for the Editorial Fit Compiler architecture."""

from .structure_metrics import (
    SentenceLengthDistributionMetrics,
    StructureMetrics,
    compute_sentence_length_distribution,
    compute_sentence_length_distribution_from_paragraphs,
    compute_structure_metrics,
)

__all__ = [
    "SentenceLengthDistributionMetrics",
    "StructureMetrics",
    "compute_sentence_length_distribution",
    "compute_sentence_length_distribution_from_paragraphs",
    "compute_structure_metrics",
]
