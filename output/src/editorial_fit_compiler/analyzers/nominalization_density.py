"""Nominalization-density heuristics based on suffixes and lexical exceptions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

from editorial_fit_compiler.core.models import Paragraph

_DEFAULT_NOMINALIZATION_SUFFIXES: tuple[str, ...] = (
    "tion",
    "sion",
    "ment",
    "ness",
    "ity",
    "ance",
    "ence",
    "ship",
    "ism",
    "acy",
)
_DEFAULT_NOMINALIZATION_LEXICON: tuple[str, ...] = (
    "analysis",
    "choice",
    "evidence",
    "failure",
    "growth",
    "policy",
    "pressure",
)
_WORD_RE = re.compile(r"\b[0-9A-Za-z]+(?:[-'][0-9A-Za-z]+)*\b")


@dataclass(frozen=True, slots=True)
class NominalizationEvidence:
    """Single nominalization match with offsets and optional paragraph linkage."""

    nominalization: str
    text: str
    start_char: int
    end_char: int
    heuristic: Literal["suffix", "lexicon"]
    paragraph_id: str | None = None


@dataclass(frozen=True, slots=True)
class ParagraphNominalizationDensity:
    """Paragraph-level nominalization density values."""

    paragraph_id: str
    nominalization_count: int
    word_count: int
    nominalization_density_score: float


@dataclass(frozen=True, slots=True)
class NominalizationDensityMetrics:
    """Document-level and paragraph-level nominalization density metrics."""

    nominalization_count: int
    word_count: int
    nominalization_density_score: float
    paragraph_densities: tuple[ParagraphNominalizationDensity, ...]
    evidence_spans: tuple[NominalizationEvidence, ...]


def estimate_nominalization_density(
    text: str,
    *,
    nominalization_suffixes: Sequence[str] | None = None,
    nominalization_lexicon: Sequence[str] | None = None,
) -> NominalizationDensityMetrics:
    """Estimate nominalization density in free text using suffix and lexicon heuristics."""
    normalized_suffixes, normalized_lexicon = _normalize_heuristics(
        nominalization_suffixes=nominalization_suffixes,
        nominalization_lexicon=nominalization_lexicon,
    )
    evidence_spans = tuple(
        _build_evidence_for_text(
            text,
            nominalization_suffixes=normalized_suffixes,
            nominalization_lexicon=normalized_lexicon,
        )
    )
    word_count = _count_words(text)
    return NominalizationDensityMetrics(
        nominalization_count=len(evidence_spans),
        word_count=word_count,
        nominalization_density_score=(len(evidence_spans) / word_count) if word_count else 0.0,
        paragraph_densities=(),
        evidence_spans=evidence_spans,
    )


def estimate_nominalization_density_in_paragraphs(
    paragraphs: Iterable[Paragraph],
    *,
    nominalization_suffixes: Sequence[str] | None = None,
    nominalization_lexicon: Sequence[str] | None = None,
) -> NominalizationDensityMetrics:
    """Estimate paragraph and document nominalization density using segmented paragraphs."""
    normalized_suffixes, normalized_lexicon = _normalize_heuristics(
        nominalization_suffixes=nominalization_suffixes,
        nominalization_lexicon=nominalization_lexicon,
    )
    evidence_spans: list[NominalizationEvidence] = []
    paragraph_densities: list[ParagraphNominalizationDensity] = []
    word_count = 0

    for paragraph in paragraphs:
        paragraph_word_count = _count_words(paragraph.text)
        paragraph_word_count = max(paragraph_word_count, 0)
        word_count += paragraph_word_count

        paragraph_evidence = _build_evidence_for_text(
            paragraph.text,
            nominalization_suffixes=normalized_suffixes,
            nominalization_lexicon=normalized_lexicon,
        )
        paragraph_densities.append(
            ParagraphNominalizationDensity(
                paragraph_id=paragraph.paragraph_id,
                nominalization_count=len(paragraph_evidence),
                word_count=paragraph_word_count,
                nominalization_density_score=(
                    len(paragraph_evidence) / paragraph_word_count
                )
                if paragraph_word_count
                else 0.0,
            )
        )

        for span in paragraph_evidence:
            evidence_spans.append(
                NominalizationEvidence(
                    nominalization=span.nominalization,
                    text=span.text,
                    start_char=paragraph.start_char + span.start_char,
                    end_char=paragraph.start_char + span.end_char,
                    heuristic=span.heuristic,
                    paragraph_id=paragraph.paragraph_id,
                )
            )

    return NominalizationDensityMetrics(
        nominalization_count=len(evidence_spans),
        word_count=word_count,
        nominalization_density_score=(len(evidence_spans) / word_count) if word_count else 0.0,
        paragraph_densities=tuple(paragraph_densities),
        evidence_spans=tuple(evidence_spans),
    )


def _normalize_heuristics(
    *,
    nominalization_suffixes: Sequence[str] | None,
    nominalization_lexicon: Sequence[str] | None,
) -> tuple[tuple[str, ...], frozenset[str]]:
    """Normalize suffix and lexicon inputs into stable lowercased matching sets."""
    suffixes = _normalize_entries(
        _DEFAULT_NOMINALIZATION_SUFFIXES
        if nominalization_suffixes is None
        else tuple(nominalization_suffixes),
    )
    lexicon = frozenset(
        _normalize_entries(
            _DEFAULT_NOMINALIZATION_LEXICON
            if nominalization_lexicon is None
            else tuple(nominalization_lexicon),
        )
    )
    return suffixes, lexicon


def _normalize_entries(entries: Sequence[str]) -> tuple[str, ...]:
    """Normalize configurable entries into lowercase, deduplicated, stable order."""
    normalized: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        normalized_entry = entry.strip().lower()
        if not normalized_entry or normalized_entry in seen:
            continue
        seen.add(normalized_entry)
        normalized.append(normalized_entry)
    return tuple(normalized)


def _build_evidence_for_text(
    text: str,
    *,
    nominalization_suffixes: Sequence[str],
    nominalization_lexicon: frozenset[str],
) -> list[NominalizationEvidence]:
    """Return token-level nominalization evidence in source order for a text block."""
    evidence_spans: list[NominalizationEvidence] = []
    for match in _WORD_RE.finditer(text):
        token_text = match.group(0)
        normalized_token = token_text.lower()
        heuristic = _match_heuristic(
            token=normalized_token,
            nominalization_suffixes=nominalization_suffixes,
            nominalization_lexicon=nominalization_lexicon,
        )
        if heuristic is None:
            continue
        evidence_spans.append(
            NominalizationEvidence(
                nominalization=normalized_token,
                text=token_text,
                start_char=match.start(),
                end_char=match.end(),
                heuristic=heuristic,
            )
        )
    return evidence_spans


def _match_heuristic(
    *,
    token: str,
    nominalization_suffixes: Sequence[str],
    nominalization_lexicon: frozenset[str],
) -> Literal["suffix", "lexicon"] | None:
    """Return the heuristic that matched a token, or None if not nominalized."""
    if token in nominalization_lexicon:
        return "lexicon"

    for suffix in nominalization_suffixes:
        if len(token) <= len(suffix) + 1:
            continue
        if token.endswith(suffix):
            return "suffix"
    return None


def _count_words(text: str) -> int:
    """Count word-like tokens for density denominator normalization."""
    return len(_WORD_RE.findall(text))
