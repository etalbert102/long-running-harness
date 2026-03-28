"""Detect undefined key terms introduced in early paragraphs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from editorial_fit_compiler.core.models import Paragraph

_TERM_TOKEN = r"[A-Z][A-Za-z0-9-]*"
_CONNECTOR = r"(?:of|and|the|for|to|in|on|with|without|via)"
_KEY_TERM_PATTERN = re.compile(
    rf"\b{_TERM_TOKEN}(?:\s+(?:{_CONNECTOR}\s+)?{_TERM_TOKEN}){{1,3}}\b"
)
_WORD_RE = re.compile(r"\b[\w']+\b")
_DEFINITION_TEMPLATES: tuple[str, ...] = (
    "{term} is ",
    "{term} are ",
    "{term} means ",
    "{term} refers to ",
    "{term} describes ",
    "{term} is defined as ",
    "called {term}",
    "known as {term}",
    "{term}, or ",
    "{term} (",
)


@dataclass(frozen=True, slots=True)
class KeyTermIntroduction:
    """Key-term introduction occurrence in a paragraph."""

    term: str
    normalized_term: str
    text: str
    start_char: int
    end_char: int
    paragraph_id: str | None = None
    paragraph_index: int = 0


@dataclass(frozen=True, slots=True)
class UndefinedKeyTermWarning:
    """Warning for a key term introduced without nearby definition."""

    term: str
    normalized_term: str
    introduction_count: int
    first_start_char: int
    last_end_char: int
    introduction_paragraph_ids: tuple[str, ...]
    introduction_paragraph_indexes: tuple[int, ...]
    nearest_definition_paragraph_index: int | None = None


@dataclass(frozen=True, slots=True)
class UndefinedKeyTermMetrics:
    """Aggregate metrics for early key-term introductions and missing definitions."""

    first_paragraph_count: int
    introduced_key_term_count: int
    unique_introduced_key_term_count: int
    undefined_key_term_count: int
    word_count: int
    introductions: tuple[KeyTermIntroduction, ...]
    undefined_key_term_warnings: tuple[UndefinedKeyTermWarning, ...]


def detect_undefined_key_terms(
    text: str,
    *,
    first_paragraph_count: int = 3,
    definition_window_paragraphs: int = 1,
) -> UndefinedKeyTermMetrics:
    """Detect undefined key terms in early paragraphs from raw text."""
    paragraph_segments = _segment_paragraphs(text)
    paragraphs = tuple(
        Paragraph(
            paragraph_id=f"p{index + 1}",
            text=segment_text,
            start_char=start_char,
            end_char=start_char + len(segment_text),
            sentences=(),
        )
        for index, (segment_text, start_char) in enumerate(paragraph_segments)
    )
    return detect_undefined_key_terms_in_paragraphs(
        paragraphs,
        first_paragraph_count=first_paragraph_count,
        definition_window_paragraphs=definition_window_paragraphs,
    )


def detect_undefined_key_terms_in_paragraphs(
    paragraphs: Iterable[Paragraph],
    *,
    first_paragraph_count: int = 3,
    definition_window_paragraphs: int = 1,
) -> UndefinedKeyTermMetrics:
    """Detect early key terms that do not receive nearby local definitions."""
    _validate_parameters(
        first_paragraph_count=first_paragraph_count,
        definition_window_paragraphs=definition_window_paragraphs,
    )
    paragraph_list = tuple(paragraphs)
    first_paragraphs = paragraph_list[:first_paragraph_count]
    considered_count = len(first_paragraphs)

    introductions = _extract_introductions(first_paragraphs)
    warnings = _build_undefined_warnings(
        introductions,
        paragraph_list=paragraph_list,
        definition_window_paragraphs=definition_window_paragraphs,
    )

    return UndefinedKeyTermMetrics(
        first_paragraph_count=considered_count,
        introduced_key_term_count=len(introductions),
        unique_introduced_key_term_count=len(
            {introduction.normalized_term for introduction in introductions}
        ),
        undefined_key_term_count=len(warnings),
        word_count=sum(_count_words(paragraph.text) for paragraph in paragraph_list),
        introductions=introductions,
        undefined_key_term_warnings=warnings,
    )


def _validate_parameters(
    *,
    first_paragraph_count: int,
    definition_window_paragraphs: int,
) -> None:
    """Validate analyzer parameters with actionable error messages."""
    if first_paragraph_count < 1:
        msg = "first_paragraph_count must be at least 1"
        raise ValueError(msg)
    if definition_window_paragraphs < 0:
        msg = "definition_window_paragraphs must be at least 0"
        raise ValueError(msg)


def _extract_introductions(paragraphs: tuple[Paragraph, ...]) -> tuple[KeyTermIntroduction, ...]:
    """Extract key-term introductions from the selected first paragraphs."""
    introductions: list[KeyTermIntroduction] = []
    for paragraph_index, paragraph in enumerate(paragraphs, start=1):
        for match in _KEY_TERM_PATTERN.finditer(paragraph.text):
            term = match.group(0)
            if not _is_candidate_term(term):
                continue
            introductions.append(
                KeyTermIntroduction(
                    term=term,
                    normalized_term=_normalize_term(term),
                    text=term,
                    start_char=paragraph.start_char + match.start(),
                    end_char=paragraph.start_char + match.end(),
                    paragraph_id=paragraph.paragraph_id,
                    paragraph_index=paragraph_index,
                )
            )
    return tuple(introductions)


def _is_candidate_term(term: str) -> bool:
    """Filter title-cased matches that are likely key concepts."""
    tokens = term.split()
    if len(tokens) < 2:
        return False
    if tokens[0] in {"The", "This", "That", "These", "Those"}:
        return False
    return True


def _normalize_term(term: str) -> str:
    """Normalize a candidate key term for robust matching."""
    cleaned = re.sub(r"[\s\-]+", " ", term.strip().lower())
    return re.sub(r"\s+", " ", cleaned)


def _build_undefined_warnings(
    introductions: tuple[KeyTermIntroduction, ...],
    *,
    paragraph_list: tuple[Paragraph, ...],
    definition_window_paragraphs: int,
) -> tuple[UndefinedKeyTermWarning, ...]:
    """Build warnings for key terms lacking a nearby definition."""
    by_term: dict[str, list[KeyTermIntroduction]] = {}
    for introduction in introductions:
        by_term.setdefault(introduction.normalized_term, []).append(introduction)

    warnings: list[UndefinedKeyTermWarning] = []
    for normalized_term, term_introductions in by_term.items():
        first_intro = term_introductions[0]
        has_definition, nearest_definition_index = _has_nearby_definition(
            normalized_term,
            introduction_paragraph_indexes=tuple(
                intro.paragraph_index for intro in term_introductions
            ),
            paragraph_list=paragraph_list,
            window=definition_window_paragraphs,
        )
        if has_definition:
            continue

        ordered_paragraph_ids = dict.fromkeys(
            introduction.paragraph_id for introduction in term_introductions
        )
        ordered_paragraph_indexes = dict.fromkeys(
            introduction.paragraph_index for introduction in term_introductions
        )
        warnings.append(
            UndefinedKeyTermWarning(
                term=first_intro.term,
                normalized_term=normalized_term,
                introduction_count=len(term_introductions),
                first_start_char=term_introductions[0].start_char,
                last_end_char=term_introductions[-1].end_char,
                introduction_paragraph_ids=tuple(
                    paragraph_id
                    for paragraph_id in ordered_paragraph_ids
                    if paragraph_id is not None
                ),
                introduction_paragraph_indexes=tuple(ordered_paragraph_indexes),
                nearest_definition_paragraph_index=nearest_definition_index,
            )
        )

    warnings.sort(
        key=lambda warning: (
            warning.first_start_char,
            warning.term,
        )
    )
    return tuple(warnings)


def _has_nearby_definition(
    normalized_term: str,
    *,
    introduction_paragraph_indexes: tuple[int, ...],
    paragraph_list: tuple[Paragraph, ...],
    window: int,
) -> tuple[bool, int | None]:
    """Check whether a term has a local definition near its introduction."""
    nearest_definition_index: int | None = None
    for paragraph_index, paragraph in enumerate(paragraph_list, start=1):
        if _contains_definition(normalized_term, paragraph.text):
            if nearest_definition_index is None:
                nearest_definition_index = paragraph_index
            for introduction_index in introduction_paragraph_indexes:
                if abs(paragraph_index - introduction_index) <= window:
                    return True, paragraph_index
    return False, nearest_definition_index


def _contains_definition(normalized_term: str, paragraph_text: str) -> bool:
    """Return true if paragraph text likely defines the given term."""
    lowercase_text = f" {paragraph_text.lower()} "
    for template in _DEFINITION_TEMPLATES:
        if template.format(term=normalized_term) in lowercase_text:
            return True
    return False


def _segment_paragraphs(text: str) -> tuple[tuple[str, int], ...]:
    """Segment text into non-empty paragraphs and absolute starts."""
    if not text.strip():
        return ()
    paragraphs: list[tuple[str, int]] = []
    cursor = 0
    for separator_match in re.finditer(r"(?:\r?\n){2,}", text):
        part = text[cursor : separator_match.start()]
        if part.strip():
            paragraphs.append((part, cursor))
        cursor = separator_match.end()
    part = text[cursor:]
    if part.strip():
        paragraphs.append((part, cursor))
    return tuple(paragraphs)


def _count_words(text: str) -> int:
    """Count words in text for normalization and summary metrics."""
    return len(_WORD_RE.findall(text))
