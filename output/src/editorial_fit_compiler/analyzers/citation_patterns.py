"""Detection helpers for citation-like patterns and evidence spans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from editorial_fit_compiler.core.models import Paragraph

_CITATION_PATTERN_TEXT: dict[str, str] = {
    "numeric_bracket": r"\[(?:\d{1,3}(?:\s*[-,]\s*\d{1,3})*)\]",
    "author_year_parenthetical": (
        r"\((?=[^)]{0,120}\b\d{4}[a-z]?\b)"
        r"(?=[^)]{0,120}\b[A-Z][A-Za-z'`-]+\b)[^)\n]+\)"
    ),
    "markdown_footnote": r"\[\^[A-Za-z0-9_-]+\]",
}
_CITATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern)) for name, pattern in _CITATION_PATTERN_TEXT.items()
)


@dataclass(frozen=True, slots=True)
class CitationEvidence:
    """Single citation-like match with source offsets and optional paragraph ID."""

    citation_type: str
    text: str
    start_char: int
    end_char: int
    paragraph_id: str | None = None


@dataclass(frozen=True, slots=True)
class CitationPatternMetrics:
    """Aggregate citation-like count and supporting evidence spans."""

    likely_citation_count: int
    evidence_spans: tuple[CitationEvidence, ...]


def detect_citation_like_patterns(text: str) -> CitationPatternMetrics:
    """Detect likely citations in free text and return count with source offsets."""
    evidence_spans = tuple(_build_evidence_for_text(text))
    return CitationPatternMetrics(
        likely_citation_count=len(evidence_spans),
        evidence_spans=evidence_spans,
    )


def detect_citation_like_patterns_in_paragraphs(
    paragraphs: Iterable[Paragraph],
) -> CitationPatternMetrics:
    """Detect likely citations in segmented paragraphs and return absolute offsets."""
    evidence_spans: list[CitationEvidence] = []

    for paragraph in paragraphs:
        for span in _build_evidence_for_text(paragraph.text):
            evidence_spans.append(
                CitationEvidence(
                    citation_type=span.citation_type,
                    text=span.text,
                    start_char=paragraph.start_char + span.start_char,
                    end_char=paragraph.start_char + span.end_char,
                    paragraph_id=paragraph.paragraph_id,
                )
            )

    return CitationPatternMetrics(
        likely_citation_count=len(evidence_spans),
        evidence_spans=tuple(evidence_spans),
    )


def _build_evidence_for_text(text: str) -> list[CitationEvidence]:
    """Build ordered, non-overlapping citation-like evidence spans from free text."""
    deduped_matches: dict[tuple[int, int], CitationEvidence] = {}
    for citation_type, pattern in _CITATION_PATTERNS:
        for match in pattern.finditer(text):
            key = (match.start(), match.end())
            if key in deduped_matches:
                continue
            deduped_matches[key] = CitationEvidence(
                citation_type=citation_type,
                text=match.group(0),
                start_char=match.start(),
                end_char=match.end(),
            )

    return [
        deduped_matches[key]
        for key in sorted(deduped_matches, key=lambda item: (item[0], item[1]))
    ]
