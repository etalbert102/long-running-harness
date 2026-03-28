"""Tests for deterministic paragraph segmentation on normalized text."""

from __future__ import annotations

import pytest

from editorial_fit_compiler.core import segmentation as segmentation_module
from editorial_fit_compiler.core.segmentation import (
    DefaultSentenceSegmentationProvider,
    SentenceSpan,
    _BackendUnavailableError,
    segment_normalized_paragraphs,
    segment_sentences,
)


class StubSentenceProvider:
    """Test sentence provider that returns preconfigured sentence spans."""

    def __init__(self, spans: tuple[SentenceSpan, ...]) -> None:
        """Create a deterministic provider with fixed output spans."""
        self._spans = spans

    def segment_sentence_spans(self, paragraph_text: str) -> tuple[SentenceSpan, ...]:
        """Return configured spans regardless of paragraph content."""
        _ = paragraph_text
        return self._spans


@pytest.fixture(autouse=True)
def clear_backend_caches() -> None:
    """Reset backend loader caches before each test for deterministic behavior."""
    segmentation_module._load_spacy_pipeline.cache_clear()
    segmentation_module._load_nltk_tokenizer.cache_clear()


def test_segment_normalized_paragraphs_preserves_source_order_and_offsets() -> None:
    """Segmentation should preserve paragraph order and exact document offsets."""
    normalized_text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

    paragraphs = segment_normalized_paragraphs(normalized_text)

    assert [paragraph.paragraph_id for paragraph in paragraphs] == ["p1", "p2", "p3"]
    assert [paragraph.text for paragraph in paragraphs] == [
        "First paragraph.",
        "Second paragraph.",
        "Third paragraph.",
    ]
    assert [(paragraph.start_char, paragraph.end_char) for paragraph in paragraphs] == [
        (0, 16),
        (18, 35),
        (37, 53),
    ]


def test_segment_normalized_paragraphs_is_reproducible_for_same_input() -> None:
    """Segmentation should return deterministic paragraph IDs and spans for repeat calls."""
    normalized_text = "Alpha.\n\nBeta.\n\nGamma."

    first_run = segment_normalized_paragraphs(normalized_text)
    second_run = segment_normalized_paragraphs(normalized_text)

    assert [paragraph.model_dump(mode="json") for paragraph in first_run] == [
        paragraph.model_dump(mode="json") for paragraph in second_run
    ]


def test_segment_normalized_paragraphs_ignores_empty_content() -> None:
    """Segmentation should return no paragraphs for blank normalized content."""
    assert segment_normalized_paragraphs("   \n\n\t") == ()


def test_segment_sentences_returns_provider_neutral_spans_and_text() -> None:
    """Sentence segmentation should return text segments with absolute offsets."""
    paragraph_text = "One short sentence. Two more words."
    provider = StubSentenceProvider(((0, 19), (20, 35)))

    segments = segment_sentences(paragraph_text, provider=provider, offset=100)

    assert [segment.text for segment in segments] == [
        "One short sentence.",
        "Two more words.",
    ]
    assert [(segment.start_char, segment.end_char) for segment in segments] == [
        (100, 119),
        (120, 135),
    ]


def test_segment_sentences_returns_empty_for_blank_paragraph() -> None:
    """Blank paragraph text should produce no sentence segments."""
    provider = StubSentenceProvider(((0, 4),))
    assert segment_sentences("  \t", provider=provider) == ()


def test_segment_sentences_rejects_overlapping_provider_spans() -> None:
    """Provider spans must be ordered and non-overlapping."""
    provider = StubSentenceProvider(((0, 5), (4, 8)))

    with pytest.raises(ValueError, match="ordered and non-overlapping"):
        _ = segment_sentences("abcdefghi", provider=provider)


def test_segment_sentences_uses_default_provider_when_unspecified() -> None:
    """Calling segment_sentences without a provider should use the default backend stack."""
    paragraph_text = "One short sentence. Two more words."

    segments = segment_sentences(paragraph_text)

    assert [segment.text for segment in segments] == [
        "One short sentence.",
        "Two more words.",
    ]
    assert [(segment.start_char, segment.end_char) for segment in segments] == [
        (0, 19),
        (20, 35),
    ]


def test_default_provider_falls_back_deterministically_when_backends_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unavailable primary backends should fall through to deterministic fallback logic."""

    def fail_spacy(
        self: DefaultSentenceSegmentationProvider, paragraph_text: str
    ) -> tuple[SentenceSpan, ...]:
        _ = self, paragraph_text
        raise _BackendUnavailableError("spaCy unavailable")

    def fail_nltk(
        self: DefaultSentenceSegmentationProvider, paragraph_text: str
    ) -> tuple[SentenceSpan, ...]:
        _ = self, paragraph_text
        raise _BackendUnavailableError("NLTK unavailable")

    monkeypatch.setattr(DefaultSentenceSegmentationProvider, "_segment_with_spacy", fail_spacy)
    monkeypatch.setattr(DefaultSentenceSegmentationProvider, "_segment_with_nltk", fail_nltk)

    paragraph_text = "Alpha one. Beta two? Gamma three!"
    first_run = segment_sentences(paragraph_text)
    second_run = segment_sentences(paragraph_text)

    assert [segment.text for segment in first_run] == ["Alpha one.", "Beta two?", "Gamma three!"]
    assert [(segment.start_char, segment.end_char) for segment in first_run] == [
        (segment.start_char, segment.end_char) for segment in second_run
    ]


def test_default_provider_rejects_unknown_backends() -> None:
    """Default provider should fail fast on unsupported backend configuration values."""
    with pytest.raises(ValueError, match="unsupported sentence segmentation backend"):
        _ = DefaultSentenceSegmentationProvider(backend_order=("unknown", "regex"))


def test_regex_fallback_handles_common_abbreviations_without_fragmenting() -> None:
    """Regex fallback should keep abbreviation-heavy prose segmented consistently."""
    provider = DefaultSentenceSegmentationProvider(backend_order=("regex",))
    paragraph_text = "Dr. Smith arrived at 5 p.m. in the U.S. He left."

    spans = provider.segment_sentence_spans(paragraph_text)

    assert spans == ((0, 39), (40, 48))
    assert [paragraph_text[start:end] for start, end in spans] == [
        "Dr. Smith arrived at 5 p.m. in the U.S.",
        "He left.",
    ]


def test_nltk_backend_uses_safe_tokenizer_initialization_without_pickle_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NLTK backend should avoid nltk.data.load pickle-based initialization."""
    import_calls: list[str] = []

    class FakeTokenizer:
        """Minimal fake tokenizer returning deterministic sentence spans."""

        def span_tokenize(self, paragraph_text: str) -> tuple[SentenceSpan, ...]:
            return ((0, len(paragraph_text)),)

    class FakePunktModule:
        """Fake punkt module exposing only safe tokenizer constructors."""

        @staticmethod
        def PunktTokenizer(language: str) -> FakeTokenizer:
            assert language == "english"
            return FakeTokenizer()

    def fake_import_module(name: str) -> object:
        import_calls.append(name)
        if name == "nltk.tokenize.punkt":
            return FakePunktModule()
        raise ImportError(name)

    monkeypatch.setattr(segmentation_module.importlib, "import_module", fake_import_module)
    provider = DefaultSentenceSegmentationProvider(backend_order=("nltk", "regex"))

    spans = provider.segment_sentence_spans("One sentence.")

    assert spans == ((0, 13),)
    assert import_calls == ["nltk.tokenize.punkt"]


def test_spacy_backend_load_is_cached_across_repeated_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """spaCy backend should load heavy model once and reuse it."""
    load_calls = 0

    class FakeSentence:
        """Simple sentence object with start/end offsets."""

        def __init__(self, start_char: int, end_char: int) -> None:
            self.start_char = start_char
            self.end_char = end_char

    class FakeDoc:
        """Simple doc exposing a sentence iterator."""

        def __init__(self, text: str) -> None:
            split_point = text.index(".") + 1
            self.sents = [FakeSentence(0, split_point), FakeSentence(split_point + 1, len(text))]

    class FakeNlp:
        """Callable fake NLP pipeline."""

        def __call__(self, text: str) -> FakeDoc:
            return FakeDoc(text)

    class FakeSpacyModule:
        """Fake spaCy module tracking model-load calls."""

        @staticmethod
        def load(model_name: str, disable: list[str]) -> FakeNlp:
            nonlocal load_calls
            load_calls += 1
            assert model_name == "en_core_web_sm"
            assert disable == ["ner", "lemmatizer", "tagger"]
            return FakeNlp()

    def fake_import_module(name: str) -> object:
        if name == "spacy":
            return FakeSpacyModule()
        raise ImportError(name)

    monkeypatch.setattr(segmentation_module.importlib, "import_module", fake_import_module)
    provider = DefaultSentenceSegmentationProvider(backend_order=("spacy",))

    first_run = provider.segment_sentence_spans("Alpha one. Beta two.")
    second_run = provider.segment_sentence_spans("Alpha one. Beta two.")

    assert first_run == second_run == ((0, 10), (11, 20))
    assert load_calls == 1


def test_nltk_backend_load_is_cached_across_repeated_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NLTK backend should initialize tokenizer once and reuse it."""
    init_calls = 0

    class FakeTokenizer:
        """Tokenizer with deterministic sentence span output."""

        def span_tokenize(self, paragraph_text: str) -> tuple[SentenceSpan, ...]:
            midpoint = paragraph_text.index(".") + 1
            return ((0, midpoint), (midpoint + 1, len(paragraph_text)))

    class FakePunktModule:
        """Fake punkt module tracking tokenizer initialization."""

        @staticmethod
        def PunktTokenizer(language: str) -> FakeTokenizer:
            nonlocal init_calls
            init_calls += 1
            assert language == "english"
            return FakeTokenizer()

    def fake_import_module(name: str) -> object:
        if name == "nltk.tokenize.punkt":
            return FakePunktModule()
        raise ImportError(name)

    monkeypatch.setattr(segmentation_module.importlib, "import_module", fake_import_module)
    provider = DefaultSentenceSegmentationProvider(backend_order=("nltk",))

    first_run = provider.segment_sentence_spans("Alpha one. Beta two.")
    second_run = provider.segment_sentence_spans("Alpha one. Beta two.")

    assert first_run == second_run == ((0, 10), (11, 20))
    assert init_calls == 1
