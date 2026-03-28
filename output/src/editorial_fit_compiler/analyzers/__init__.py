"""Analyzer package for the Editorial Fit Compiler architecture."""

from .bullet_usage import (
    BulletUsageEvidence,
    BulletUsageMetrics,
    detect_bullet_usage,
    detect_bullet_usage_in_paragraphs,
)
from .citation_patterns import (
    CitationEvidence,
    CitationPatternMetrics,
    detect_citation_like_patterns,
    detect_citation_like_patterns_in_paragraphs,
)
from .punctuation_markers import (
    ForbiddenPunctuationEvidence,
    ForbiddenPunctuationMetrics,
    detect_forbidden_punctuation,
    detect_forbidden_punctuation_in_paragraphs,
)
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
    "BulletUsageEvidence",
    "BulletUsageMetrics",
    "detect_bullet_usage",
    "detect_bullet_usage_in_paragraphs",
    "CitationEvidence",
    "CitationPatternMetrics",
    "detect_citation_like_patterns",
    "detect_citation_like_patterns_in_paragraphs",
    "ForbiddenPunctuationEvidence",
    "ForbiddenPunctuationMetrics",
    "detect_forbidden_punctuation",
    "detect_forbidden_punctuation_in_paragraphs",
    "ParagraphLengthDistributionMetrics",
    "SentenceLengthDistributionMetrics",
    "StructureMetrics",
    "compute_paragraph_length_distribution",
    "compute_paragraph_length_distribution_from_paragraphs",
    "compute_sentence_length_distribution",
    "compute_sentence_length_distribution_from_paragraphs",
    "compute_structure_metrics",
]
