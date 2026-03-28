"""Detect repeated rhetorical templates, including contrast constructions."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from editorial_fit_compiler.core.models import Paragraph

_WORD_RE = re.compile(r"\b[\w']+\b")

_TEMPLATE_REGEXES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "contrast_not_but",
        "contrast",
        re.compile(r"\bnot\b[^.!?\n]{1,120}?\bbut\b[^.!?\n]{1,120}", flags=re.IGNORECASE),
    ),
    (
        "contrast_while_clause",
        "contrast",
        re.compile(r"\bwhile\b[^.!?\n]{1,120}?,\s*[^.!?\n]{1,120}", flags=re.IGNORECASE),
    ),
    (
        "contrast_although_clause",
        "contrast",
        re.compile(r"\balthough\b[^.!?\n]{1,120}?,\s*[^.!?\n]{1,120}", flags=re.IGNORECASE),
    ),
    (
        "contrast_on_the_one_hand",
        "contrast",
        re.compile(
            r"\bon the one hand\b[^.!?\n]{1,200}?\bon the other hand\b[^.!?\n]{0,120}",
            flags=re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class RhetoricalTemplateEvidence:
    """Single rhetorical-template match with optional paragraph linkage."""

    template_key: str
    template_family: str
    text: str
    start_char: int
    end_char: int
    paragraph_id: str | None = None


@dataclass(frozen=True, slots=True)
class RhetoricalTemplateFrequency:
    """Occurrence count for a matched rhetorical template."""

    template_key: str
    template_family: str
    occurrence_count: int
    repeated: bool


@dataclass(frozen=True, slots=True)
class RepeatedRhetoricalTemplateWarning:
    """Flag describing a template repeated at or above the threshold."""

    template_key: str
    template_family: str
    occurrence_count: int
    first_start_char: int
    last_end_char: int
    paragraph_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RhetoricalTemplateRepetitionMetrics:
    """Aggregate rhetorical-template frequencies and repeated-template warnings."""

    template_match_count: int
    word_count: int
    template_density_score: float
    evidence_spans: tuple[RhetoricalTemplateEvidence, ...]
    template_frequencies: tuple[RhetoricalTemplateFrequency, ...]
    repeated_template_warnings: tuple[RepeatedRhetoricalTemplateWarning, ...]


def detect_repeated_rhetorical_templates(
    text: str,
    *,
    repetition_threshold: int = 2,
) -> RhetoricalTemplateRepetitionMetrics:
    """Detect rhetorical templates in free text and flag repeated template patterns."""
    normalized_threshold = max(2, repetition_threshold)
    evidence_spans = _build_evidence_for_text(text)
    word_count = _count_words(text)
    return RhetoricalTemplateRepetitionMetrics(
        template_match_count=len(evidence_spans),
        word_count=word_count,
        template_density_score=(len(evidence_spans) / word_count) if word_count else 0.0,
        evidence_spans=evidence_spans,
        template_frequencies=_build_template_frequencies(
            evidence_spans,
            repetition_threshold=normalized_threshold,
        ),
        repeated_template_warnings=_build_repetition_warnings(
            evidence_spans,
            repetition_threshold=normalized_threshold,
        ),
    )


def detect_repeated_rhetorical_templates_in_paragraphs(
    paragraphs: Iterable[Paragraph],
    *,
    repetition_threshold: int = 2,
) -> RhetoricalTemplateRepetitionMetrics:
    """Detect repeated rhetorical templates across paragraphs with absolute offsets."""
    normalized_threshold = max(2, repetition_threshold)
    evidence_spans: list[RhetoricalTemplateEvidence] = []
    word_count = 0
    for paragraph in paragraphs:
        word_count += _count_words(paragraph.text)
        paragraph_evidence = _build_evidence_for_text(paragraph.text)
        for span in paragraph_evidence:
            evidence_spans.append(
                RhetoricalTemplateEvidence(
                    template_key=span.template_key,
                    template_family=span.template_family,
                    text=span.text,
                    start_char=paragraph.start_char + span.start_char,
                    end_char=paragraph.start_char + span.end_char,
                    paragraph_id=paragraph.paragraph_id,
                )
            )

    frozen_evidence = tuple(evidence_spans)
    return RhetoricalTemplateRepetitionMetrics(
        template_match_count=len(frozen_evidence),
        word_count=word_count,
        template_density_score=(len(frozen_evidence) / word_count) if word_count else 0.0,
        evidence_spans=frozen_evidence,
        template_frequencies=_build_template_frequencies(
            frozen_evidence,
            repetition_threshold=normalized_threshold,
        ),
        repeated_template_warnings=_build_repetition_warnings(
            frozen_evidence,
            repetition_threshold=normalized_threshold,
        ),
    )


def _build_evidence_for_text(text: str) -> tuple[RhetoricalTemplateEvidence, ...]:
    """Build ordered rhetorical-template evidence for text."""
    evidence_spans: list[RhetoricalTemplateEvidence] = []
    for template_key, template_family, pattern in _TEMPLATE_REGEXES:
        for match in pattern.finditer(text):
            evidence_spans.append(
                RhetoricalTemplateEvidence(
                    template_key=template_key,
                    template_family=template_family,
                    text=match.group(0),
                    start_char=match.start(),
                    end_char=match.end(),
                )
            )

    evidence_spans.sort(
        key=lambda span: (
            span.start_char,
            span.template_key,
            span.end_char,
        )
    )
    return tuple(evidence_spans)


def _build_template_frequencies(
    evidence_spans: tuple[RhetoricalTemplateEvidence, ...],
    *,
    repetition_threshold: int,
) -> tuple[RhetoricalTemplateFrequency, ...]:
    """Compute per-template frequencies and repeated flags."""
    counts = Counter(span.template_key for span in evidence_spans)
    family_by_template = {
        template_key: template_family
        for template_key, template_family, _ in _TEMPLATE_REGEXES
    }
    frequencies = tuple(
        RhetoricalTemplateFrequency(
            template_key=template_key,
            template_family=family_by_template[template_key],
            occurrence_count=occurrence_count,
            repeated=occurrence_count >= repetition_threshold,
        )
        for template_key, occurrence_count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    )
    return frequencies


def _build_repetition_warnings(
    evidence_spans: tuple[RhetoricalTemplateEvidence, ...],
    *,
    repetition_threshold: int,
) -> tuple[RepeatedRhetoricalTemplateWarning, ...]:
    """Build warnings for templates repeated at or above the threshold."""
    if repetition_threshold < 2:
        repetition_threshold = 2

    warnings: list[RepeatedRhetoricalTemplateWarning] = []
    by_template: dict[str, list[RhetoricalTemplateEvidence]] = {}
    for span in evidence_spans:
        by_template.setdefault(span.template_key, []).append(span)

    for template_key, template_evidence in by_template.items():
        occurrence_count = len(template_evidence)
        if occurrence_count < repetition_threshold:
            continue
        unique_paragraph_ids = dict.fromkeys(span.paragraph_id for span in template_evidence)
        paragraph_ids = tuple(
            paragraph_id for paragraph_id in unique_paragraph_ids if paragraph_id is not None
        )
        warnings.append(
            RepeatedRhetoricalTemplateWarning(
                template_key=template_key,
                template_family=template_evidence[0].template_family,
                occurrence_count=occurrence_count,
                first_start_char=template_evidence[0].start_char,
                last_end_char=template_evidence[-1].end_char,
                paragraph_ids=paragraph_ids,
            )
        )

    warnings.sort(
        key=lambda warning: (
            -warning.occurrence_count,
            warning.first_start_char,
            warning.template_key,
        )
    )
    return tuple(warnings)


def _count_words(text: str) -> int:
    """Count words in text for rhetorical-template density normalization."""
    return len(_WORD_RE.findall(text))
