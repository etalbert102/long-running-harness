"""Utility package for the Editorial Fit Compiler architecture."""

from .spans import (
    SentenceIndexMapping,
    SpanIndexMapping,
    build_evidence_span,
    build_sentence_index_map,
    extract_span_text,
    map_span_to_indices,
)

__all__ = [
    "SentenceIndexMapping",
    "SpanIndexMapping",
    "build_evidence_span",
    "build_sentence_index_map",
    "extract_span_text",
    "map_span_to_indices",
]
