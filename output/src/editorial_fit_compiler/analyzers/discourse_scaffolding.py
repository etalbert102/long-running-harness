"""Count discourse-scaffolding phrases and flag repeated scaffold dependence."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Sequence

from editorial_fit_compiler.core.models import Paragraph

_DEFAULT_SCAFFOLDING_PHRASE_BANK: tuple[str, ...] = (
    "it is important to note",
    "it should be noted",
    "in other words",
    "to be clear",
    "at this point",
    "in conclusion",
    "moreover",
    "furthermore",
)

_WORD_RE = re.compile(r"\b[\w']+\b")


@dataclass(frozen=True, slots=True)
class DiscourseScaffoldingEvidence:
    """Single discourse-scaffolding match with offsets and optional paragraph linkage."""

    scaffolding_phrase: str
    text: str
    start_char: int
    end_char: int
    paragraph_id: str | None = None


@dataclass(frozen=True, slots=True)
class ScaffoldRepetitionWarning:
    """Repeated-scaffold warning for phrases used at or above a frequency threshold."""

    scaffolding_phrase: str
    occurrence_count: int
    first_start_char: int
    last_end_char: int
    paragraph_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DiscourseScaffoldingMetrics:
    """Aggregate scaffolding count, density, evidence spans, and repetition warnings."""

    scaffolding_phrase_count: int
    word_count: int
    scaffolding_phrase_density_score: float
    evidence_spans: tuple[DiscourseScaffoldingEvidence, ...]
    repetition_warnings: tuple[ScaffoldRepetitionWarning, ...]


def count_discourse_scaffolding_phrases(
    text: str,
    *,
    phrase_bank: Sequence[str] | None = None,
    repetition_threshold: int = 2,
) -> DiscourseScaffoldingMetrics:
    """Count discourse-scaffolding phrases and emit repeated-scaffold warnings."""
    normalized_phrase_bank = _normalize_phrase_bank(phrase_bank)
    evidence_spans = tuple(_build_evidence_for_text(text, normalized_phrase_bank))
    word_count = _count_words(text)
    return DiscourseScaffoldingMetrics(
        scaffolding_phrase_count=len(evidence_spans),
        word_count=word_count,
        scaffolding_phrase_density_score=(len(evidence_spans) / word_count) if word_count else 0.0,
        evidence_spans=evidence_spans,
        repetition_warnings=_build_repetition_warnings(
            evidence_spans,
            repetition_threshold=repetition_threshold,
        ),
    )


def count_discourse_scaffolding_phrases_in_paragraphs(
    paragraphs: Iterable[Paragraph],
    *,
    phrase_bank: Sequence[str] | None = None,
    repetition_threshold: int = 2,
) -> DiscourseScaffoldingMetrics:
    """Count scaffolding phrases in paragraphs with absolute offsets and warnings."""
    normalized_phrase_bank = _normalize_phrase_bank(phrase_bank)
    evidence_spans: list[DiscourseScaffoldingEvidence] = []
    word_count = 0

    for paragraph in paragraphs:
        word_count += _count_words(paragraph.text)
        paragraph_evidence = _build_evidence_for_text(paragraph.text, normalized_phrase_bank)
        for span in paragraph_evidence:
            evidence_spans.append(
                DiscourseScaffoldingEvidence(
                    scaffolding_phrase=span.scaffolding_phrase,
                    text=span.text,
                    start_char=paragraph.start_char + span.start_char,
                    end_char=paragraph.start_char + span.end_char,
                    paragraph_id=paragraph.paragraph_id,
                )
            )

    frozen_evidence = tuple(evidence_spans)
    return DiscourseScaffoldingMetrics(
        scaffolding_phrase_count=len(frozen_evidence),
        word_count=word_count,
        scaffolding_phrase_density_score=(len(frozen_evidence) / word_count) if word_count else 0.0,
        evidence_spans=frozen_evidence,
        repetition_warnings=_build_repetition_warnings(
            frozen_evidence,
            repetition_threshold=repetition_threshold,
        ),
    )


def _normalize_phrase_bank(phrase_bank: Sequence[str] | None) -> tuple[str, ...]:
    """Normalize caller-provided phrase banks into lowercase, deduplicated entries."""
    raw_entries = _DEFAULT_SCAFFOLDING_PHRASE_BANK if phrase_bank is None else tuple(phrase_bank)
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
) -> list[DiscourseScaffoldingEvidence]:
    """Build ordered, non-overlapping scaffolding evidence for text."""
    candidates: list[DiscourseScaffoldingEvidence] = []
    for phrase in phrase_bank:
        for match in _compile_phrase_pattern(phrase).finditer(text):
            candidates.append(
                DiscourseScaffoldingEvidence(
                    scaffolding_phrase=phrase,
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
            span.scaffolding_phrase,
        ),
    )

    selected: list[DiscourseScaffoldingEvidence] = []
    current_end = -1
    for span in ordered_candidates:
        if span.start_char < current_end:
            continue
        selected.append(span)
        current_end = span.end_char
    return selected


def _build_repetition_warnings(
    evidence_spans: tuple[DiscourseScaffoldingEvidence, ...],
    *,
    repetition_threshold: int,
) -> tuple[ScaffoldRepetitionWarning, ...]:
    """Build warnings for scaffolding phrases repeated at or above a threshold."""
    if repetition_threshold < 2:
        repetition_threshold = 2

    counts = Counter(span.scaffolding_phrase for span in evidence_spans)
    warnings: list[ScaffoldRepetitionWarning] = []
    for phrase, occurrence_count in counts.items():
        if occurrence_count < repetition_threshold:
            continue
        phrase_spans = tuple(span for span in evidence_spans if span.scaffolding_phrase == phrase)
        unique_paragraph_ids = dict.fromkeys(span.paragraph_id for span in phrase_spans)
        paragraph_ids = tuple(
            paragraph_id for paragraph_id in unique_paragraph_ids if paragraph_id is not None
        )
        warnings.append(
            ScaffoldRepetitionWarning(
                scaffolding_phrase=phrase,
                occurrence_count=occurrence_count,
                first_start_char=phrase_spans[0].start_char,
                last_end_char=phrase_spans[-1].end_char,
                paragraph_ids=paragraph_ids,
            )
        )

    warnings.sort(
        key=lambda warning: (
            -warning.occurrence_count,
            warning.first_start_char,
            warning.scaffolding_phrase,
        )
    )
    return tuple(warnings)


def _compile_phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Compile a case-insensitive whole-phrase regex with flexible whitespace."""
    tokens = tuple(re.escape(token) for token in phrase.split(" "))
    phrase_pattern = r"\s+".join(tokens)
    return re.compile(rf"(?<!\w){phrase_pattern}(?!\w)", flags=re.IGNORECASE)


def _count_words(text: str) -> int:
    """Count words in text for scaffolding-phrase density normalization."""
    return len(_WORD_RE.findall(text))
