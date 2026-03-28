"""Detect repeated sentence-opener patterns across nearby sentences."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from editorial_fit_compiler.core.models import Paragraph, Sentence

_WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", flags=re.UNICODE)


@dataclass(frozen=True, slots=True)
class SentenceOpenerPattern:
    """Detected opener pattern for a sentence."""

    sentence_id: str
    sentence_index: int
    opener: str
    start_char: int
    end_char: int
    paragraph_id: str | None = None


@dataclass(frozen=True, slots=True)
class OpenerPatternCluster:
    """Cluster of repeated opener patterns across nearby sentences."""

    opener: str
    occurrence_count: int
    first_sentence_index: int
    last_sentence_index: int
    max_sentence_gap: int
    severity: str
    sentence_ids: tuple[str, ...]
    paragraph_ids: tuple[str, ...]
    first_start_char: int
    last_end_char: int


@dataclass(frozen=True, slots=True)
class SentenceOpenerRepetitionMetrics:
    """Aggregate opener patterns and repeated-pattern clusters."""

    sentence_count: int
    opener_pattern_count: int
    opener_patterns: tuple[SentenceOpenerPattern, ...]
    repeated_pattern_clusters: tuple[OpenerPatternCluster, ...]


def detect_repeated_sentence_openers(
    sentences: Iterable[Sentence],
    *,
    opener_token_count: int = 2,
    nearby_sentence_window: int = 2,
    min_cluster_occurrences: int = 2,
) -> SentenceOpenerRepetitionMetrics:
    """Detect repeated opener patterns among ordered sentences."""
    sentence_list = tuple(sentences)
    return _build_repetition_metrics(
        sentence_list,
        opener_token_count=opener_token_count,
        nearby_sentence_window=nearby_sentence_window,
        min_cluster_occurrences=min_cluster_occurrences,
        paragraph_ids=(None,) * len(sentence_list),
    )


def detect_repeated_sentence_openers_in_paragraphs(
    paragraphs: Iterable[Paragraph],
    *,
    opener_token_count: int = 2,
    nearby_sentence_window: int = 2,
    min_cluster_occurrences: int = 2,
) -> SentenceOpenerRepetitionMetrics:
    """Detect repeated opener patterns while preserving paragraph linkage."""
    paragraph_list = tuple(paragraphs)
    sentences = tuple(sentence for paragraph in paragraph_list for sentence in paragraph.sentences)
    paragraph_ids = tuple(
        paragraph.paragraph_id
        for paragraph in paragraph_list
        for _sentence in paragraph.sentences
    )
    return _build_repetition_metrics(
        sentences,
        opener_token_count=opener_token_count,
        nearby_sentence_window=nearby_sentence_window,
        min_cluster_occurrences=min_cluster_occurrences,
        paragraph_ids=paragraph_ids,
    )


def _build_repetition_metrics(
    sentences: tuple[Sentence, ...],
    *,
    opener_token_count: int,
    nearby_sentence_window: int,
    min_cluster_occurrences: int,
    paragraph_ids: tuple[str | None, ...],
) -> SentenceOpenerRepetitionMetrics:
    """Materialize opener patterns and repeated nearby clusters for sentences."""
    _validate_repetition_parameters(
        opener_token_count=opener_token_count,
        nearby_sentence_window=nearby_sentence_window,
        min_cluster_occurrences=min_cluster_occurrences,
    )
    if len(paragraph_ids) != len(sentences):
        msg = "paragraph_ids length must match sentences length"
        raise ValueError(msg)

    opener_patterns = _extract_opener_patterns(
        sentences,
        opener_token_count=opener_token_count,
        paragraph_ids=paragraph_ids,
    )
    repeated_pattern_clusters = _build_clusters(
        opener_patterns,
        nearby_sentence_window=nearby_sentence_window,
        min_cluster_occurrences=min_cluster_occurrences,
    )
    return SentenceOpenerRepetitionMetrics(
        sentence_count=len(sentences),
        opener_pattern_count=len(opener_patterns),
        opener_patterns=opener_patterns,
        repeated_pattern_clusters=repeated_pattern_clusters,
    )


def _extract_opener_patterns(
    sentences: tuple[Sentence, ...],
    *,
    opener_token_count: int,
    paragraph_ids: tuple[str | None, ...],
) -> tuple[SentenceOpenerPattern, ...]:
    """Extract normalized opener patterns from ordered sentences."""
    patterns: list[SentenceOpenerPattern] = []
    for sentence_index, (sentence, paragraph_id) in enumerate(zip(sentences, paragraph_ids)):
        opener = _extract_sentence_opener(sentence.text, opener_token_count=opener_token_count)
        if opener is None:
            continue
        patterns.append(
            SentenceOpenerPattern(
                sentence_id=sentence.sentence_id,
                sentence_index=sentence_index,
                opener=opener,
                start_char=sentence.start_char,
                end_char=sentence.end_char,
                paragraph_id=paragraph_id,
            )
        )
    return tuple(patterns)


def _validate_repetition_parameters(
    *,
    opener_token_count: int,
    nearby_sentence_window: int,
    min_cluster_occurrences: int,
) -> None:
    """Validate analyzer parameters and fail fast on invalid values."""
    if opener_token_count < 1:
        msg = "opener_token_count must be at least 1"
        raise ValueError(msg)
    if nearby_sentence_window < 1:
        msg = "nearby_sentence_window must be at least 1"
        raise ValueError(msg)
    if min_cluster_occurrences < 2:
        msg = "min_cluster_occurrences must be at least 2"
        raise ValueError(msg)


def _build_clusters(
    opener_patterns: tuple[SentenceOpenerPattern, ...],
    *,
    nearby_sentence_window: int,
    min_cluster_occurrences: int,
) -> tuple[OpenerPatternCluster, ...]:
    """Build repeated opener clusters constrained by nearby sentence windows."""
    opener_to_patterns: dict[str, list[SentenceOpenerPattern]] = {}
    for pattern in opener_patterns:
        opener_to_patterns.setdefault(pattern.opener, []).append(pattern)

    clusters: list[OpenerPatternCluster] = []
    for opener, patterns in opener_to_patterns.items():
        sorted_patterns = sorted(patterns, key=lambda pattern: pattern.sentence_index)
        current_cluster: list[SentenceOpenerPattern] = []

        for pattern in sorted_patterns:
            if not current_cluster:
                current_cluster.append(pattern)
                continue

            previous = current_cluster[-1]
            if pattern.sentence_index - previous.sentence_index <= nearby_sentence_window:
                current_cluster.append(pattern)
                continue

            _append_cluster_if_repeated(
                clusters,
                opener=opener,
                cluster_patterns=tuple(current_cluster),
                min_cluster_occurrences=min_cluster_occurrences,
            )
            current_cluster = [pattern]

        _append_cluster_if_repeated(
            clusters,
            opener=opener,
            cluster_patterns=tuple(current_cluster),
            min_cluster_occurrences=min_cluster_occurrences,
        )

    clusters.sort(
        key=lambda cluster: (
            -cluster.occurrence_count,
            cluster.first_sentence_index,
            cluster.opener,
        )
    )
    return tuple(clusters)


def _append_cluster_if_repeated(
    clusters: list[OpenerPatternCluster],
    *,
    opener: str,
    cluster_patterns: tuple[SentenceOpenerPattern, ...],
    min_cluster_occurrences: int,
) -> None:
    """Append a repeated opener cluster when it meets the occurrence threshold."""
    if len(cluster_patterns) < min_cluster_occurrences:
        return

    sentence_ids = tuple(pattern.sentence_id for pattern in cluster_patterns)
    unique_paragraph_ids = dict.fromkeys(pattern.paragraph_id for pattern in cluster_patterns)
    paragraph_ids = tuple(
        paragraph_id for paragraph_id in unique_paragraph_ids if paragraph_id is not None
    )
    max_sentence_gap = max(
        (
            current.sentence_index - previous.sentence_index
            for previous, current in zip(cluster_patterns, cluster_patterns[1:])
        ),
        default=0,
    )
    occurrence_count = len(cluster_patterns)
    clusters.append(
        OpenerPatternCluster(
            opener=opener,
            occurrence_count=occurrence_count,
            first_sentence_index=cluster_patterns[0].sentence_index,
            last_sentence_index=cluster_patterns[-1].sentence_index,
            max_sentence_gap=max_sentence_gap,
            severity=_cluster_severity(occurrence_count, max_sentence_gap),
            sentence_ids=sentence_ids,
            paragraph_ids=paragraph_ids,
            first_start_char=cluster_patterns[0].start_char,
            last_end_char=cluster_patterns[-1].end_char,
        )
    )


def _cluster_severity(occurrence_count: int, max_sentence_gap: int) -> str:
    """Map repetition intensity and proximity to low/medium/high severity labels."""
    if occurrence_count >= 4 and max_sentence_gap <= 1:
        return "high"
    if occurrence_count >= 3:
        return "medium"
    return "low"


def _extract_sentence_opener(text: str, *, opener_token_count: int) -> str | None:
    """Extract a normalized opener from the first N lexical tokens."""
    tokens = tuple(match.group(0).lower() for match in _WORD_RE.finditer(text))
    if len(tokens) < opener_token_count:
        return None
    return " ".join(tokens[:opener_token_count])
