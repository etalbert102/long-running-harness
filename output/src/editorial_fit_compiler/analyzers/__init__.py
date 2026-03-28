"""Analyzer package for the Editorial Fit Compiler architecture."""

from .structure_metrics import (
    ParagraphLengthDistributionMetrics,
    SentenceLengthDistributionMetrics,
    StructureMetrics,
    compute_paragraph_length_distribution,
    compute_paragraph_length_distribution_from_paragraphs,
    compute_sentence_length_distribution,
    compute_sentence_length_distribution_from_paragraphs,
    compute_structure_metrics,
)

__all__ = [
    "ParagraphLengthDistributionMetrics",
    "SentenceLengthDistributionMetrics",
    "StructureMetrics",
    "compute_paragraph_length_distribution",
    "compute_paragraph_length_distribution_from_paragraphs",
    "compute_sentence_length_distribution",
    "compute_sentence_length_distribution_from_paragraphs",
    "compute_structure_metrics",
]
