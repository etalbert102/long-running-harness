"""Baseline structure metrics for segmented drafts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from editorial_fit_compiler.core.models import Paragraph

_WORD_RE = re.compile(r"\b[0-9A-Za-z]+(?:[-'][0-9A-Za-z]+)*\b")
_SECTION_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")


@dataclass(frozen=True, slots=True)
class StructureMetrics:
    """Deterministic baseline metrics for draft structure."""

    word_count: int
    section_count: int
    paragraph_count: int


def compute_structure_metrics(paragraphs: Iterable[Paragraph]) -> StructureMetrics:
    """Compute baseline word, section, and paragraph counts from segmented paragraphs."""
    paragraph_list = tuple(paragraphs)
    word_count = sum(len(_WORD_RE.findall(paragraph.text)) for paragraph in paragraph_list)
    section_count = sum(
        1 for paragraph in paragraph_list if _SECTION_HEADING_RE.match(paragraph.text) is not None
    )
    return StructureMetrics(
        word_count=word_count,
        section_count=section_count,
        paragraph_count=len(paragraph_list),
    )
