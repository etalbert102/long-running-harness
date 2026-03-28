"""Deterministic text segmentation helpers for normalized draft content."""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol, cast

from editorial_fit_compiler.core.models import Paragraph

_PARAGRAPH_DELIMITER = "\n\n"
SentenceSpan = tuple[int, int]
_DEFAULT_BACKEND_ORDER: tuple[str, ...] = ("spacy", "nltk", "regex")
_TITLE_ABBREVIATIONS = frozenset({"dr", "mr", "mrs", "ms", "prof", "sr", "jr", "st"})
_COMMON_ABBREVIATIONS = frozenset(
    {
        "etc",
        "e.g",
        "i.e",
        "vs",
        "a.m",
        "p.m",
        "u.s",
        "u.k",
    }
)
_UPPERCASE_WORD_RE = re.compile(r"[A-Z][A-Za-z'\-]*$")


class SentenceSegmentationProvider(Protocol):
    """Provider interface for sentence-boundary segmentation."""

    def segment_sentence_spans(self, paragraph_text: str) -> tuple[SentenceSpan, ...]:
        """Return sentence spans relative to `paragraph_text` using end-exclusive offsets."""


@dataclass(frozen=True, slots=True)
class SentenceSegment:
    """Provider-neutral sentence segment with text and absolute character offsets."""

    text: str
    start_char: int
    end_char: int


class _BackendUnavailableError(RuntimeError):
    """Raised when a sentence-segmentation backend cannot be initialized."""


@lru_cache(maxsize=1)
def _load_spacy_pipeline() -> Any:
    """Load and cache the spaCy English pipeline once per process."""
    try:
        spacy_module = importlib.import_module("spacy")
    except ImportError as exc:
        msg = "spaCy is not installed"
        raise _BackendUnavailableError(msg) from exc

    try:
        return spacy_module.load("en_core_web_sm", disable=["ner", "lemmatizer", "tagger"])
    except OSError as exc:
        msg = "spaCy English model is unavailable"
        raise _BackendUnavailableError(msg) from exc


@lru_cache(maxsize=1)
def _load_nltk_tokenizer() -> Any:
    """Load and cache a non-pickle NLTK sentence tokenizer."""
    try:
        punkt_module = importlib.import_module("nltk.tokenize.punkt")
    except ImportError as exc:
        msg = "NLTK is not installed"
        raise _BackendUnavailableError(msg) from exc

    punkt_tokenizer = getattr(punkt_module, "PunktTokenizer", None)
    if punkt_tokenizer is not None:
        try:
            return punkt_tokenizer("english")
        except LookupError as exc:
            msg = "NLTK punkt resources are unavailable"
            raise _BackendUnavailableError(msg) from exc

    punkt_sentence_tokenizer = getattr(punkt_module, "PunktSentenceTokenizer", None)
    if punkt_sentence_tokenizer is not None:
        return punkt_sentence_tokenizer()

    msg = "NLTK punkt tokenizer is unavailable"
    raise _BackendUnavailableError(msg)


@dataclass(frozen=True, slots=True)
class DefaultSentenceSegmentationProvider:
    """Default provider with deterministic backend fallbacks.

    The backend order is deterministic and attempted left-to-right:
    ``spaCy`` -> ``NLTK`` -> regex fallback.
    """

    backend_order: tuple[str, ...] = _DEFAULT_BACKEND_ORDER

    def __post_init__(self) -> None:
        """Validate configured backend names."""
        valid_backends = {"spacy", "nltk", "regex"}
        unknown_backends = set(self.backend_order) - valid_backends
        if unknown_backends:
            formatted = ", ".join(sorted(unknown_backends))
            msg = f"unsupported sentence segmentation backend(s): {formatted}"
            raise ValueError(msg)

    def segment_sentence_spans(self, paragraph_text: str) -> tuple[SentenceSpan, ...]:
        """Return sentence spans using the first available backend."""
        if not paragraph_text.strip():
            return ()

        for backend_name in self.backend_order:
            try:
                if backend_name == "spacy":
                    return self._segment_with_spacy(paragraph_text)
                if backend_name == "nltk":
                    return self._segment_with_nltk(paragraph_text)
                if backend_name == "regex":
                    return self._segment_with_regex(paragraph_text)
            except _BackendUnavailableError:
                continue

        return self._segment_with_regex(paragraph_text)

    def _segment_with_spacy(self, paragraph_text: str) -> tuple[SentenceSpan, ...]:
        """Segment with spaCy when the package and English model are available."""
        nlp = _load_spacy_pipeline()
        doc = nlp(paragraph_text)
        spans = tuple((sentence.start_char, sentence.end_char) for sentence in cast(Any, doc).sents)
        return spans if spans else self._segment_with_regex(paragraph_text)

    def _segment_with_nltk(self, paragraph_text: str) -> tuple[SentenceSpan, ...]:
        """Segment with NLTK Punkt when tokenizer resources are available."""
        tokenizer = _load_nltk_tokenizer()
        sentence_spans = cast(Any, tokenizer).span_tokenize(paragraph_text)
        spans = tuple((start, end) for start, end in sentence_spans)
        return spans if spans else self._segment_with_regex(paragraph_text)

    def _segment_with_regex(self, paragraph_text: str) -> tuple[SentenceSpan, ...]:
        """Segment deterministically using abbreviation-aware punctuation heuristics."""
        text = paragraph_text
        spans: list[SentenceSpan] = []
        start_char = 0
        index = 0
        text_length = len(text)

        while index < text_length:
            char = text[index]
            if char not in ".!?":
                index += 1
                continue

            if char == "." and not _should_split_on_period(text, index):
                index += 1
                continue

            end_char = index + 1
            while end_char < text_length and text[end_char] in "\"')]":
                end_char += 1

            if start_char < end_char:
                trimmed_start = start_char
                while trimmed_start < end_char and text[trimmed_start].isspace():
                    trimmed_start += 1
                trimmed_end = end_char
                while trimmed_end > trimmed_start and text[trimmed_end - 1].isspace():
                    trimmed_end -= 1
                if trimmed_start < trimmed_end:
                    spans.append((trimmed_start, trimmed_end))

            start_char = end_char
            index = end_char

        tail_start = start_char
        while tail_start < text_length and text[tail_start].isspace():
            tail_start += 1
        tail_end = text_length
        while tail_end > tail_start and text[tail_end - 1].isspace():
            tail_end -= 1
        if tail_start < tail_end:
            spans.append((tail_start, tail_end))

        if spans:
            return tuple(spans)

        stripped_text = paragraph_text.strip()
        if not stripped_text:
            return ()
        start_char = paragraph_text.index(stripped_text)
        end_char = start_char + len(stripped_text)
        return ((start_char, end_char),)


def _should_split_on_period(text: str, period_index: int) -> bool:
    """Return whether a period should terminate the current sentence."""
    if (
        period_index + 2 < len(text)
        and text[period_index + 1].isalpha()
        and text[period_index + 2] == "."
    ):
        return False

    token = _token_before_period(text, period_index).lower()
    if not token:
        return True

    next_word = _next_word_after_index(text, period_index + 1)
    if token in _TITLE_ABBREVIATIONS and _UPPERCASE_WORD_RE.match(next_word) is not None:
        return False

    if token in _COMMON_ABBREVIATIONS and next_word and next_word[:1].islower():
        return False

    if _is_initialism(token) and next_word and next_word[:1].islower():
        return False

    return True


def _token_before_period(text: str, period_index: int) -> str:
    """Return the token immediately preceding a period index."""
    end = period_index
    start = end
    while start > 0 and text[start - 1].isalpha():
        start -= 1
    if start == end:
        return ""

    token = text[start:end]
    cursor = start
    while cursor > 1 and text[cursor - 1] == "." and text[cursor - 2].isalpha():
        inner_end = cursor - 1
        inner_start = inner_end - 1
        while inner_start > 0 and text[inner_start - 1].isalpha():
            inner_start -= 1
        token = f"{text[inner_start:inner_end]}.{token}"
        cursor = inner_start

    return token


def _next_word_after_index(text: str, index: int) -> str:
    """Return the next alphabetical token after the provided index."""
    text_length = len(text)
    cursor = index
    while cursor < text_length and (text[cursor].isspace() or text[cursor] in "\"')]"):
        cursor += 1
    start = cursor
    while cursor < text_length and text[cursor].isalpha():
        cursor += 1
    return text[start:cursor]


def _is_initialism(token: str) -> bool:
    """Return true for dot-separated all-uppercase initialisms like U.S."""
    pieces = token.split(".")
    if len(pieces) < 2:
        return False
    return all(len(piece) == 1 and piece.isalpha() for piece in pieces)


def _build_sentence_segments(
    paragraph_text: str,
    spans: tuple[SentenceSpan, ...],
    *,
    offset: int,
) -> tuple[SentenceSegment, ...]:
    """Validate provider spans and materialize sentence segments."""
    segments: list[SentenceSegment] = []
    previous_end = 0
    text_length = len(paragraph_text)

    for start_char, end_char in spans:
        if start_char < 0:
            msg = "sentence span start must be non-negative"
            raise ValueError(msg)
        if end_char <= start_char:
            msg = "sentence span end must be greater than start"
            raise ValueError(msg)
        if end_char > text_length:
            msg = "sentence span end cannot exceed paragraph length"
            raise ValueError(msg)
        if start_char < previous_end:
            msg = "sentence spans must be ordered and non-overlapping"
            raise ValueError(msg)
        previous_end = end_char

        text_segment = paragraph_text[start_char:end_char]
        segments.append(
            SentenceSegment(
                text=text_segment,
                start_char=start_char + offset,
                end_char=end_char + offset,
            )
        )

    return tuple(segments)


def segment_normalized_paragraphs(normalized_text: str) -> tuple[Paragraph, ...]:
    """Segment normalized text into source-ordered paragraphs with stable IDs.

    The input is expected to follow the canonical output contract of
    ``normalize_draft_text`` where paragraph boundaries are represented by
    double-newline delimiters.
    """
    if not normalized_text.strip():
        return ()

    segments = normalized_text.split(_PARAGRAPH_DELIMITER)
    paragraphs: list[Paragraph] = []
    cursor = 0
    paragraph_index = 0

    for segment in segments:
        segment_length = len(segment)
        if not segment.strip():
            cursor += segment_length + len(_PARAGRAPH_DELIMITER)
            continue

        paragraph_index += 1
        start_char = cursor
        end_char = start_char + segment_length
        paragraphs.append(
            Paragraph(
                paragraph_id=f"p{paragraph_index}",
                text=segment,
                start_char=start_char,
                end_char=end_char,
            )
        )
        cursor = end_char + len(_PARAGRAPH_DELIMITER)

    return tuple(paragraphs)


def segment_sentences(
    paragraph_text: str,
    *,
    provider: SentenceSegmentationProvider | None = None,
    offset: int = 0,
) -> tuple[SentenceSegment, ...]:
    """Segment paragraph text via a provider-neutral interface.

    Args:
        paragraph_text: Paragraph content to segment.
        provider: Sentence-boundary provider implementation. Defaults to
            ``DefaultSentenceSegmentationProvider``.
        offset: Absolute character-offset base added to each returned span.
    """
    if offset < 0:
        msg = "offset must be non-negative"
        raise ValueError(msg)
    if not paragraph_text.strip():
        return ()

    active_provider = provider or DefaultSentenceSegmentationProvider()
    spans = active_provider.segment_sentence_spans(paragraph_text)
    return _build_sentence_segments(paragraph_text, spans, offset=offset)
