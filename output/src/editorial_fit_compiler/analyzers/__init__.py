"""Analyzer package for the Editorial Fit Compiler architecture."""

from .abstraction_phrase_density import (
    AbstractionPhraseEvidence,
    AbstractionPhraseMetrics,
    count_abstraction_phrases,
    count_abstraction_phrases_in_paragraphs,
)
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
from .discourse_scaffolding import (
    DiscourseScaffoldingEvidence,
    DiscourseScaffoldingMetrics,
    ScaffoldRepetitionWarning,
    count_discourse_scaffolding_phrases,
    count_discourse_scaffolding_phrases_in_paragraphs,
)
from .hedge_density import (
    HedgeDensityMetrics,
    HedgeEvidence,
    estimate_hedge_density,
    estimate_hedge_density_in_paragraphs,
)
from .nominalization_density import (
    NominalizationDensityMetrics,
    NominalizationEvidence,
    ParagraphNominalizationDensity,
    estimate_nominalization_density,
    estimate_nominalization_density_in_paragraphs,
)
from .punctuation_markers import (
    ForbiddenPunctuationEvidence,
    ForbiddenPunctuationMetrics,
    detect_forbidden_punctuation,
    detect_forbidden_punctuation_in_paragraphs,
)
from .sentence_opener_repetition import (
    OpenerPatternCluster,
    SentenceOpenerPattern,
    SentenceOpenerRepetitionMetrics,
    detect_repeated_sentence_openers,
    detect_repeated_sentence_openers_in_paragraphs,
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
    "AbstractionPhraseEvidence",
    "AbstractionPhraseMetrics",
    "count_abstraction_phrases",
    "count_abstraction_phrases_in_paragraphs",
    "BulletUsageEvidence",
    "BulletUsageMetrics",
    "detect_bullet_usage",
    "detect_bullet_usage_in_paragraphs",
    "CitationEvidence",
    "CitationPatternMetrics",
    "detect_citation_like_patterns",
    "detect_citation_like_patterns_in_paragraphs",
    "DiscourseScaffoldingEvidence",
    "DiscourseScaffoldingMetrics",
    "ScaffoldRepetitionWarning",
    "count_discourse_scaffolding_phrases",
    "count_discourse_scaffolding_phrases_in_paragraphs",
    "HedgeDensityMetrics",
    "HedgeEvidence",
    "estimate_hedge_density",
    "estimate_hedge_density_in_paragraphs",
    "NominalizationDensityMetrics",
    "NominalizationEvidence",
    "ParagraphNominalizationDensity",
    "estimate_nominalization_density",
    "estimate_nominalization_density_in_paragraphs",
    "ForbiddenPunctuationEvidence",
    "ForbiddenPunctuationMetrics",
    "detect_forbidden_punctuation",
    "detect_forbidden_punctuation_in_paragraphs",
    "OpenerPatternCluster",
    "SentenceOpenerPattern",
    "SentenceOpenerRepetitionMetrics",
    "detect_repeated_sentence_openers",
    "detect_repeated_sentence_openers_in_paragraphs",
    "ParagraphLengthDistributionMetrics",
    "SentenceLengthDistributionMetrics",
    "StructureMetrics",
    "compute_paragraph_length_distribution",
    "compute_paragraph_length_distribution_from_paragraphs",
    "compute_sentence_length_distribution",
    "compute_sentence_length_distribution_from_paragraphs",
    "compute_structure_metrics",
]
