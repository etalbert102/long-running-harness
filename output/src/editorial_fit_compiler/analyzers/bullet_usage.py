"""Detection helpers for markdown bullet/list usage and paragraph locations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from editorial_fit_compiler.core.models import Paragraph

_BULLET_LINE_RE = re.compile(
    r"^(?:\s{0,3})(?P<marker>[-+*]|\d{1,3}[.)])\s+(?P<content>\S.*)$",
    re.MULTILINE,
)
_UNORDERED_MARKERS = frozenset({"-", "+", "*"})


@dataclass(frozen=True, slots=True)
class BulletUsageEvidence:
    """Single markdown list-item match with offsets and optional paragraph ID."""

    marker_type: str
    marker_text: str
    text: str
    start_char: int
    end_char: int
    paragraph_id: str | None = None


@dataclass(frozen=True, slots=True)
class BulletUsageMetrics:
    """Aggregate markdown bullet counts and paragraph-location metadata."""

    total_bullet_count: int
    unordered_bullet_count: int
    ordered_bullet_count: int
    bullet_paragraph_count: int
    bullet_paragraph_ids: tuple[str, ...]
    evidence_spans: tuple[BulletUsageEvidence, ...]


def detect_bullet_usage(text: str) -> BulletUsageMetrics:
    """Detect markdown list-item usage in free text and return count statistics."""
    evidence_spans = tuple(_build_evidence_for_text(text))
    return _build_metrics(evidence_spans)


def detect_bullet_usage_in_paragraphs(paragraphs: Iterable[Paragraph]) -> BulletUsageMetrics:
    """Detect markdown list-item usage in segmented paragraphs with absolute offsets."""
    evidence_spans: list[BulletUsageEvidence] = []
    paragraph_ids_with_bullets: list[str] = []
    seen_paragraph_ids: set[str] = set()

    for paragraph in paragraphs:
        paragraph_has_bullet = False
        for span in _build_evidence_for_text(paragraph.text):
            paragraph_has_bullet = True
            evidence_spans.append(
                BulletUsageEvidence(
                    marker_type=span.marker_type,
                    marker_text=span.marker_text,
                    text=span.text,
                    start_char=paragraph.start_char + span.start_char,
                    end_char=paragraph.start_char + span.end_char,
                    paragraph_id=paragraph.paragraph_id,
                )
            )
        if paragraph_has_bullet and paragraph.paragraph_id not in seen_paragraph_ids:
            seen_paragraph_ids.add(paragraph.paragraph_id)
            paragraph_ids_with_bullets.append(paragraph.paragraph_id)

    return _build_metrics(tuple(evidence_spans), paragraph_ids=tuple(paragraph_ids_with_bullets))


def _build_evidence_for_text(text: str) -> list[BulletUsageEvidence]:
    """Return ordered bullet/list-item matches from a block of text."""
    evidence_spans: list[BulletUsageEvidence] = []
    for match in _BULLET_LINE_RE.finditer(text):
        marker_text = match.group("marker")
        evidence_spans.append(
            BulletUsageEvidence(
                marker_type=_marker_type_for_marker(marker_text),
                marker_text=marker_text,
                text=match.group(0),
                start_char=match.start(),
                end_char=match.end(),
            )
        )
    return evidence_spans


def _marker_type_for_marker(marker_text: str) -> str:
    """Resolve a list marker into a stable ordered/unordered marker type."""
    if marker_text in _UNORDERED_MARKERS:
        return "unordered"
    return "ordered"


def _build_metrics(
    evidence_spans: tuple[BulletUsageEvidence, ...],
    *,
    paragraph_ids: tuple[str, ...] = (),
) -> BulletUsageMetrics:
    """Build aggregate bullet-usage metrics from evidence spans and paragraph IDs."""
    unordered_bullet_count = sum(1 for span in evidence_spans if span.marker_type == "unordered")
    ordered_bullet_count = len(evidence_spans) - unordered_bullet_count
    return BulletUsageMetrics(
        total_bullet_count=len(evidence_spans),
        unordered_bullet_count=unordered_bullet_count,
        ordered_bullet_count=ordered_bullet_count,
        bullet_paragraph_count=len(paragraph_ids),
        bullet_paragraph_ids=paragraph_ids,
        evidence_spans=evidence_spans,
    )
