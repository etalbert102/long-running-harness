"""Nominalization-density heuristics based on suffixes and lexical exceptions."""

from __future__ import annotations

import re
import unicodedata
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
_DEFAULT_SUFFIX_EXCLUSION_LEXICON: frozenset[str] = frozenset(
    {
        "business",
        "witness",
    }
)
_WORD_RE = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", re.UNICODE)
_TOKEN_CONNECTORS: frozenset[str] = frozenset({"-", "'"})


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
    suffix_exclusion_lexicon: Sequence[str] | None = None,
) -> NominalizationDensityMetrics:
    """Estimate nominalization density in free text using suffix and lexicon heuristics.

    Pass `suffix_exclusion_lexicon=()` to disable default suffix false-positive exclusions.
    """
    normalized_suffixes, normalized_lexicon, normalized_suffix_exclusions = _normalize_heuristics(
        nominalization_suffixes=nominalization_suffixes,
        nominalization_lexicon=nominalization_lexicon,
        suffix_exclusion_lexicon=suffix_exclusion_lexicon,
    )
    evidence_spans = tuple(
        _build_evidence_for_text(
            text,
            nominalization_suffixes=normalized_suffixes,
            nominalization_lexicon=normalized_lexicon,
            suffix_exclusion_lexicon=normalized_suffix_exclusions,
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
    suffix_exclusion_lexicon: Sequence[str] | None = None,
) -> NominalizationDensityMetrics:
    """Estimate paragraph and document nominalization density using segmented paragraphs.

    Pass `suffix_exclusion_lexicon=()` to disable default suffix false-positive exclusions.
    """
    normalized_suffixes, normalized_lexicon, normalized_suffix_exclusions = _normalize_heuristics(
        nominalization_suffixes=nominalization_suffixes,
        nominalization_lexicon=nominalization_lexicon,
        suffix_exclusion_lexicon=suffix_exclusion_lexicon,
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
            suffix_exclusion_lexicon=normalized_suffix_exclusions,
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
    suffix_exclusion_lexicon: Sequence[str] | None,
) -> tuple[tuple[str, ...], frozenset[str], frozenset[str]]:
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
    suffix_exclusions = frozenset(
        _normalize_entries(
            _DEFAULT_SUFFIX_EXCLUSION_LEXICON
            if suffix_exclusion_lexicon is None
            else tuple(suffix_exclusion_lexicon),
        )
    )
    return suffixes, lexicon, suffix_exclusions


def _normalize_entries(entries: Sequence[str]) -> tuple[str, ...]:
    """Normalize configurable entries into lowercase, deduplicated, stable order."""
    normalized: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        normalized_entry = _normalize_for_matching(entry)
        if not normalized_entry or normalized_entry in seen:
            continue
        seen.add(normalized_entry)
        normalized.append(normalized_entry)
    return tuple(normalized)


def _normalize_for_matching(value: str) -> str:
    """Normalize text for lexical matching across case and accented variants."""
    stripped = value.strip().casefold()
    if not stripped:
        return ""
    decomposed = unicodedata.normalize("NFKD", stripped)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _build_evidence_for_text(
    text: str,
    *,
    nominalization_suffixes: Sequence[str],
    nominalization_lexicon: frozenset[str],
    suffix_exclusion_lexicon: frozenset[str],
) -> list[NominalizationEvidence]:
    """Return token-level nominalization evidence in source order for a text block."""
    evidence_spans: list[NominalizationEvidence] = []
    for token_text, token_start, token_end in _iter_word_tokens(text):
        normalized_token = unicodedata.normalize("NFC", token_text).casefold()
        normalized_token_for_matching = _normalize_for_matching(token_text)
        heuristic = _match_heuristic(
            token=normalized_token_for_matching,
            nominalization_suffixes=nominalization_suffixes,
            nominalization_lexicon=nominalization_lexicon,
            suffix_exclusion_lexicon=suffix_exclusion_lexicon,
        )
        if heuristic is None:
            continue
        evidence_spans.append(
            NominalizationEvidence(
                nominalization=normalized_token,
                text=token_text,
                start_char=token_start,
                end_char=token_end,
                heuristic=heuristic,
            )
        )
    return evidence_spans


def _match_heuristic(
    *,
    token: str,
    nominalization_suffixes: Sequence[str],
    nominalization_lexicon: frozenset[str],
    suffix_exclusion_lexicon: frozenset[str],
) -> Literal["suffix", "lexicon"] | None:
    """Return the heuristic that matched a token, or None if not nominalized."""
    if token in nominalization_lexicon:
        return "lexicon"
    if token in suffix_exclusion_lexicon:
        return None

    for suffix in nominalization_suffixes:
        # A minimum 3-character stem reduces short-word suffix false positives.
        if len(token) <= len(suffix) + 2:
            continue
        if token.endswith(suffix):
            return "suffix"
    return None


def _count_words(text: str) -> int:
    """Count word-like tokens for density denominator normalization."""
    return sum(1 for _token in _iter_word_tokens(text))


def _iter_word_tokens(text: str) -> Iterable[tuple[str, int, int]]:
    """Yield `(token, start, end)` tuples with Unicode-aware letter/mark tokenization."""
    index = 0
    text_length = len(text)

    while index < text_length:
        if not _is_word_start_character(text[index]):
            index += 1
            continue

        start = index
        index += 1
        while index < text_length and _is_word_continue_character(text[index]):
            index += 1

        while index < text_length and text[index] in _TOKEN_CONNECTORS:
            connector_index = index
            next_index = connector_index + 1
            if next_index >= text_length or not _is_word_start_character(text[next_index]):
                break
            index = next_index + 1
            while index < text_length and _is_word_continue_character(text[index]):
                index += 1

        yield text[start:index], start, index


def _is_word_start_character(character: str) -> bool:
    """Return whether a character can start a word token in analyzer tokenization."""
    return unicodedata.category(character).startswith("L")


def _is_word_continue_character(character: str) -> bool:
    """Return whether a character can continue a token after a letter."""
    category = unicodedata.category(character)
    return category.startswith("L") or unicodedata.combining(character) > 0
