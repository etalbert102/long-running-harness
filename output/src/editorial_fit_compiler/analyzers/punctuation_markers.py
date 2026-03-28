"""Detection helpers for em dashes and related forbidden punctuation markers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from editorial_fit_compiler.core.models import Paragraph

_FORBIDDEN_MARKER_PATTERNS: dict[str, str] = {
    "em_dash": "\u2014",
    "en_dash": "\u2013",
    "horizontal_bar": "\u2015",
    "double_hyphen": "--",
}
_FORBIDDEN_MARKERS_RE = re.compile(
    "|".join(
        re.escape(_FORBIDDEN_MARKER_PATTERNS[key])
        for key in ("em_dash", "en_dash", "horizontal_bar", "double_hyphen")
    )
)


@dataclass(frozen=True, slots=True)
class ForbiddenPunctuationEvidence:
    """Single forbidden punctuation match with source offsets and optional paragraph ID."""

    marker: str
    text: str
    start_char: int
    end_char: int
    paragraph_id: str | None = None


@dataclass(frozen=True, slots=True)
class ForbiddenPunctuationMetrics:
    """Aggregate forbidden punctuation counts and evidence spans."""

    em_dash_count: int
    forbidden_marker_count: int
    evidence_spans: tuple[ForbiddenPunctuationEvidence, ...]


def detect_forbidden_punctuation(text: str) -> ForbiddenPunctuationMetrics:
    """Detect forbidden punctuation markers in free text and return counts with evidence."""
    evidence_spans = tuple(_build_evidence_for_text(text))
    em_dash_count = sum(1 for span in evidence_spans if span.marker == "em_dash")
    return ForbiddenPunctuationMetrics(
        em_dash_count=em_dash_count,
        forbidden_marker_count=len(evidence_spans),
        evidence_spans=evidence_spans,
    )


def detect_forbidden_punctuation_in_paragraphs(
    paragraphs: Iterable[Paragraph],
) -> ForbiddenPunctuationMetrics:
    """Detect forbidden punctuation markers in segmented paragraphs."""
    evidence_spans: list[ForbiddenPunctuationEvidence] = []
    em_dash_count = 0

    for paragraph in paragraphs:
        for match in _FORBIDDEN_MARKERS_RE.finditer(paragraph.text):
            marker = _marker_name_for_text(match.group(0))
            start_char = paragraph.start_char + match.start()
            end_char = paragraph.start_char + match.end()
            evidence_spans.append(
                ForbiddenPunctuationEvidence(
                    marker=marker,
                    text=match.group(0),
                    start_char=start_char,
                    end_char=end_char,
                    paragraph_id=paragraph.paragraph_id,
                )
            )
            if marker == "em_dash":
                em_dash_count += 1

    return ForbiddenPunctuationMetrics(
        em_dash_count=em_dash_count,
        forbidden_marker_count=len(evidence_spans),
        evidence_spans=tuple(evidence_spans),
    )


def _build_evidence_for_text(text: str) -> list[ForbiddenPunctuationEvidence]:
    """Build evidence spans for all forbidden punctuation markers in ``text``."""
    evidence_spans: list[ForbiddenPunctuationEvidence] = []
    for match in _FORBIDDEN_MARKERS_RE.finditer(text):
        evidence_spans.append(
            ForbiddenPunctuationEvidence(
                marker=_marker_name_for_text(match.group(0)),
                text=match.group(0),
                start_char=match.start(),
                end_char=match.end(),
            )
        )
    return evidence_spans


def _marker_name_for_text(marker_text: str) -> str:
    """Resolve a matched punctuation marker text into a stable marker key."""
    for marker_name, pattern_text in _FORBIDDEN_MARKER_PATTERNS.items():
        if marker_text == pattern_text:
            return marker_name
    msg = f"Unsupported forbidden punctuation marker {marker_text!r}"
    raise ValueError(msg)
