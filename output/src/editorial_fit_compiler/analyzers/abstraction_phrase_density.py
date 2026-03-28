"""Count abstraction-heavy phrase patterns with configurable phrase banks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from editorial_fit_compiler.core.models import Paragraph

_DEFAULT_ABSTRACTION_PHRASE_BANK: tuple[str, ...] = (
    "in many ways",
    "at a high level",
    "broader context",
    "systemic level",
    "conceptual framework",
    "strategic perspective",
    "structural dynamics",
    "underlying logic",
)

_WORD_RE = re.compile(r"\b[\w']+\b")


@dataclass(frozen=True, slots=True)
class AbstractionPhraseEvidence:
    """Single abstraction phrase match with offsets and optional paragraph linkage."""

    abstraction_phrase: str
    text: str
    start_char: int
    end_char: int
    paragraph_id: str | None = None


@dataclass(frozen=True, slots=True)
class AbstractionPhraseMetrics:
    """Aggregate phrase count, word count, density score, and evidence spans."""

    abstraction_phrase_count: int
    word_count: int
    abstraction_phrase_density_score: float
    evidence_spans: tuple[AbstractionPhraseEvidence, ...]


def count_abstraction_phrases(
    text: str,
    *,
    phrase_bank: Sequence[str] | None = None,
) -> AbstractionPhraseMetrics:
    """Count abstraction-heavy phrase matches and density for free text."""
    normalized_phrase_bank = _normalize_phrase_bank(phrase_bank)
    evidence_spans = tuple(_build_evidence_for_text(text, normalized_phrase_bank))
    word_count = _count_words(text)
    return AbstractionPhraseMetrics(
        abstraction_phrase_count=len(evidence_spans),
        word_count=word_count,
        abstraction_phrase_density_score=(len(evidence_spans) / word_count) if word_count else 0.0,
        evidence_spans=evidence_spans,
    )


def count_abstraction_phrases_in_paragraphs(
    paragraphs: Iterable[Paragraph],
    *,
    phrase_bank: Sequence[str] | None = None,
) -> AbstractionPhraseMetrics:
    """Count abstraction-heavy phrase matches and density for segmented paragraphs."""
    normalized_phrase_bank = _normalize_phrase_bank(phrase_bank)
    evidence_spans: list[AbstractionPhraseEvidence] = []
    word_count = 0

    for paragraph in paragraphs:
        word_count += _count_words(paragraph.text)
        paragraph_evidence = _build_evidence_for_text(paragraph.text, normalized_phrase_bank)
        for span in paragraph_evidence:
            evidence_spans.append(
                AbstractionPhraseEvidence(
                    abstraction_phrase=span.abstraction_phrase,
                    text=span.text,
                    start_char=paragraph.start_char + span.start_char,
                    end_char=paragraph.start_char + span.end_char,
                    paragraph_id=paragraph.paragraph_id,
                )
            )

    return AbstractionPhraseMetrics(
        abstraction_phrase_count=len(evidence_spans),
        word_count=word_count,
        abstraction_phrase_density_score=(len(evidence_spans) / word_count) if word_count else 0.0,
        evidence_spans=tuple(evidence_spans),
    )


def _normalize_phrase_bank(phrase_bank: Sequence[str] | None) -> tuple[str, ...]:
    """Normalize caller-provided phrase banks into lowercase, deduplicated entries."""
    raw_entries = _DEFAULT_ABSTRACTION_PHRASE_BANK if phrase_bank is None else tuple(phrase_bank)
    normalized: list[str] = []
    seen: set[str] = set()
    for entry in raw_entries:
        normalized_entry = " ".join(entry.strip().lower().split())
        if not normalized_entry or normalized_entry in seen:
            continue
        seen.add(normalized_entry)
        normalized.append(normalized_entry)
    return tuple(normalized)


def _build_evidence_for_text(
    text: str,
    phrase_bank: Sequence[str],
) -> list[AbstractionPhraseEvidence]:
    """Build ordered, non-overlapping abstraction phrase evidence for text."""
    candidates: list[AbstractionPhraseEvidence] = []
    for phrase in phrase_bank:
        for match in _compile_phrase_pattern(phrase).finditer(text):
            candidates.append(
                AbstractionPhraseEvidence(
                    abstraction_phrase=phrase,
                    text=match.group(0),
                    start_char=match.start(),
                    end_char=match.end(),
                )
            )

    ordered_candidates = sorted(
        candidates,
        key=lambda span: (
            span.start_char,
            -(span.end_char - span.start_char),
            span.abstraction_phrase,
        ),
    )

    selected: list[AbstractionPhraseEvidence] = []
    current_end = -1
    for span in ordered_candidates:
        if span.start_char < current_end:
            continue
        selected.append(span)
        current_end = span.end_char
    return selected


def _compile_phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Compile a case-insensitive whole-phrase regex with flexible whitespace."""
    tokens = tuple(re.escape(token) for token in phrase.split(" "))
    phrase_pattern = r"\s+".join(tokens)
    return re.compile(rf"(?<!\w){phrase_pattern}(?!\w)", flags=re.IGNORECASE)


def _count_words(text: str) -> int:
    """Count words in text for abstraction phrase density normalization."""
    return len(_WORD_RE.findall(text))
