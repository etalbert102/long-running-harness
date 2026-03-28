"""Detection helpers for hedge density scoring using configurable hedge lexicons."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from editorial_fit_compiler.core.models import Paragraph

_DEFAULT_HEDGE_LEXICON: tuple[str, ...] = (
    "may",
    "might",
    "could",
    "possibly",
    "perhaps",
    "likely",
    "seems",
    "appears to",
    "suggests",
    "arguably",
)

_WORD_RE = re.compile(r"\b[\w']+\b")


@dataclass(frozen=True, slots=True)
class HedgeEvidence:
    """Single hedge-phrase match with source offsets and optional paragraph ID."""

    hedge_phrase: str
    text: str
    start_char: int
    end_char: int
    paragraph_id: str | None = None


@dataclass(frozen=True, slots=True)
class HedgeDensityMetrics:
    """Aggregate hedge count, word count, density score, and supporting spans."""

    hedge_count: int
    word_count: int
    hedge_density_score: float
    evidence_spans: tuple[HedgeEvidence, ...]


def estimate_hedge_density(
    text: str,
    *,
    hedge_lexicon: Sequence[str] | None = None,
) -> HedgeDensityMetrics:
    """Estimate hedge density in free text using a default or caller-supplied lexicon."""
    normalized_lexicon = _normalize_lexicon(hedge_lexicon)
    evidence_spans = tuple(_build_evidence_for_text(text, normalized_lexicon))
    word_count = _count_words(text)
    return HedgeDensityMetrics(
        hedge_count=len(evidence_spans),
        word_count=word_count,
        hedge_density_score=(len(evidence_spans) / word_count) if word_count else 0.0,
        evidence_spans=evidence_spans,
    )


def estimate_hedge_density_in_paragraphs(
    paragraphs: Iterable[Paragraph],
    *,
    hedge_lexicon: Sequence[str] | None = None,
) -> HedgeDensityMetrics:
    """Estimate hedge density from paragraphs and return absolute offsets with paragraph IDs."""
    normalized_lexicon = _normalize_lexicon(hedge_lexicon)
    evidence_spans: list[HedgeEvidence] = []
    word_count = 0

    for paragraph in paragraphs:
        word_count += _count_words(paragraph.text)
        for span in _build_evidence_for_text(paragraph.text, normalized_lexicon):
            evidence_spans.append(
                HedgeEvidence(
                    hedge_phrase=span.hedge_phrase,
                    text=span.text,
                    start_char=paragraph.start_char + span.start_char,
                    end_char=paragraph.start_char + span.end_char,
                    paragraph_id=paragraph.paragraph_id,
                )
            )

    return HedgeDensityMetrics(
        hedge_count=len(evidence_spans),
        word_count=word_count,
        hedge_density_score=(len(evidence_spans) / word_count) if word_count else 0.0,
        evidence_spans=tuple(evidence_spans),
    )


def _normalize_lexicon(hedge_lexicon: Sequence[str] | None) -> tuple[str, ...]:
    """Normalize caller-provided lexicon entries into a stable unique tuple."""
    raw_entries = _DEFAULT_HEDGE_LEXICON if hedge_lexicon is None else tuple(hedge_lexicon)
    normalized: list[str] = []
    seen: set[str] = set()
    for entry in raw_entries:
        normalized_entry = " ".join(entry.strip().lower().split())
        if not normalized_entry or normalized_entry in seen:
            continue
        seen.add(normalized_entry)
        normalized.append(normalized_entry)
    return tuple(normalized)


def _build_evidence_for_text(text: str, hedge_lexicon: Sequence[str]) -> list[HedgeEvidence]:
    """Build ordered, non-overlapping hedge spans from text and a normalized lexicon."""
    candidates: list[HedgeEvidence] = []
    for phrase in hedge_lexicon:
        for match in _compile_hedge_pattern(phrase).finditer(text):
            candidates.append(
                HedgeEvidence(
                    hedge_phrase=phrase,
                    text=match.group(0),
                    start_char=match.start(),
                    end_char=match.end(),
                )
            )

    ordered_candidates = sorted(
        candidates,
        key=lambda span: (span.start_char, -(span.end_char - span.start_char), span.hedge_phrase),
    )

    selected: list[HedgeEvidence] = []
    current_end = -1
    for span in ordered_candidates:
        if span.start_char < current_end:
            continue
        selected.append(span)
        current_end = span.end_char
    return selected


def _compile_hedge_pattern(phrase: str) -> re.Pattern[str]:
    """Compile a case-insensitive whole-phrase hedge regex with flexible whitespace."""
    tokens = tuple(re.escape(token) for token in phrase.split(" "))
    phrase_pattern = r"\s+".join(tokens)
    return re.compile(rf"(?<!\w){phrase_pattern}(?!\w)", flags=re.IGNORECASE)


def _count_words(text: str) -> int:
    """Count words in text for hedge-density normalization."""
    return len(_WORD_RE.findall(text))
