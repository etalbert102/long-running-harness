"""Tests for draft file ingestion and normalization."""

from __future__ import annotations

import builtins
import sys
import types
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from editorial_fit_compiler.core.ingestion import (
    load_document_from_path,
    normalize_draft_text,
)


class _FakeXmlNode:
    """Minimal XML-like node exposing the attributes used by ingestion."""

    def __init__(
        self,
        tag: str,
        *,
        text: str = "",
        children: list[_FakeXmlNode] | None = None,
        row_cells: list[list[_FakeXmlNode]] | None = None,
    ) -> None:
        self.tag = tag
        self.text = text
        self._children = children or []
        self.row_cells = row_cells or []

    def iterchildren(self) -> Any:
        """Yield child XML nodes in source order."""
        return iter(self._children)


class _FakeDocument:
    """Container with a `document.element.body` shape used by ingestion."""

    def __init__(self, body_children: list[_FakeXmlNode]) -> None:
        self.element = types.SimpleNamespace(body=_FakeXmlNode("{w}body", children=body_children))


class _FakeDocxCell:
    """Cell wrapper exposing `_tc` for nested block iteration."""

    def __init__(self, cell_xml: _FakeXmlNode) -> None:
        self._tc = cell_xml


class _FakeDocxRow:
    """Row wrapper exposing `cells` list."""

    def __init__(self, cells: list[_FakeDocxCell]) -> None:
        self.cells = cells


class _FakeDocxTable:
    """Table wrapper exposing rows in source order."""

    def __init__(self, table_xml: _FakeXmlNode, _container: Any) -> None:
        self.rows = [
            _FakeDocxRow([_FakeDocxCell(cell_xml) for cell_xml in row_cells])
            for row_cells in table_xml.row_cells
        ]


class _FakeDocxParagraph:
    """Paragraph wrapper exposing text content."""

    def __init__(self, paragraph_xml: _FakeXmlNode, _container: Any) -> None:
        self.text = paragraph_xml.text


def _ingestion_fixture_path(filename: str) -> Path:
    """Return a fixture path for ingestion tests."""
    return Path(__file__).parent / "fixtures" / "ingestion" / filename


def _docx_temp_path(stem: str) -> Path:
    """Return a temporary `.docx` path for ingestion tests."""
    temp_dir = Path.cwd() / ".tmp" / "tests"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir / f"{stem}-{uuid4().hex}.docx"


def _paragraph_node(text: str) -> _FakeXmlNode:
    """Create a fake Word paragraph node."""
    return _FakeXmlNode("{w}p", text=text)


def _cell_node(text: str) -> _FakeXmlNode:
    """Create a fake Word table-cell node containing one paragraph."""
    return _FakeXmlNode("{w}tc", children=[_paragraph_node(text)])


def _table_node(rows: list[list[str]]) -> _FakeXmlNode:
    """Create a fake Word table node from cell text rows."""
    return _FakeXmlNode(
        "{w}tbl",
        row_cells=[[_cell_node(cell_text) for cell_text in row] for row in rows],
    )


def _install_fake_docx_modules(
    monkeypatch: pytest.MonkeyPatch,
    *,
    document_factory: Any,
) -> None:
    """Install fake `docx` modules so ingestion can be exercised without external deps."""
    docx_module = types.ModuleType("docx")
    docx_module.Document = document_factory

    table_module = types.ModuleType("docx.table")
    table_module.Table = _FakeDocxTable

    text_module = types.ModuleType("docx.text")
    paragraph_module = types.ModuleType("docx.text.paragraph")
    paragraph_module.Paragraph = _FakeDocxParagraph
    text_module.paragraph = paragraph_module

    monkeypatch.setitem(sys.modules, "docx", docx_module)
    monkeypatch.setitem(sys.modules, "docx.table", table_module)
    monkeypatch.setitem(sys.modules, "docx.text", text_module)
    monkeypatch.setitem(sys.modules, "docx.text.paragraph", paragraph_module)


def test_normalize_draft_text_normalizes_line_endings_and_trailing_whitespace() -> None:
    """Normalization should canonicalize line endings and trim trailing spaces per line."""
    raw_text = "\ufeffLine one  \r\nLine two\t\rLine three\n"
    normalized = normalize_draft_text(raw_text)
    assert normalized == "Line one\nLine two\nLine three"


def test_load_document_from_path_loads_markdown_and_creates_paragraphs() -> None:
    """Ingestion should load markdown text and map paragraph spans into a document model."""
    draft_path = _ingestion_fixture_path("sample.md")
    document = load_document_from_path(draft_path)

    assert document.text == "First paragraph.\n\nSecond paragraph."
    assert document.source_path == str(draft_path.resolve())
    assert len(document.paragraphs) == 2
    assert document.paragraphs[0].text == "First paragraph."
    assert document.paragraphs[1].text == "Second paragraph."
    assert document.paragraphs[0].start_char == 0
    assert document.paragraphs[0].end_char == len("First paragraph.")


def test_load_document_from_path_rejects_unsupported_extensions() -> None:
    """Ingestion should fail fast for unsupported file extensions."""
    draft_path = _ingestion_fixture_path("unsupported.rtf")
    with pytest.raises(ValueError, match="Unsupported draft file extension"):
        load_document_from_path(draft_path)


def test_load_document_from_path_loads_docx_in_source_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ingestion should read `.docx` paragraphs in source order."""
    draft_path = _docx_temp_path("sample")
    draft_path.write_bytes(b"fake-docx")

    fake_document = _FakeDocument(
        [
            _paragraph_node("First paragraph."),
            _paragraph_node("Second paragraph."),
            _paragraph_node("Third paragraph."),
        ]
    )
    _install_fake_docx_modules(
        monkeypatch,
        document_factory=lambda path: fake_document,
    )

    try:
        document = load_document_from_path(draft_path)
    finally:
        draft_path.unlink(missing_ok=True)

    assert document.text == "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    assert [paragraph.text for paragraph in document.paragraphs] == [
        "First paragraph.",
        "Second paragraph.",
        "Third paragraph.",
    ]


def test_load_document_from_path_extracts_docx_tables_in_source_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ingestion should include table cell text inline with surrounding body content."""
    draft_path = _docx_temp_path("sample-table")
    draft_path.write_bytes(b"fake-docx")

    fake_document = _FakeDocument(
        [
            _paragraph_node("Intro paragraph."),
            _table_node([["R1C1", "R1C2"], ["R2C1", "R2C2"]]),
            _paragraph_node("Closing paragraph."),
        ]
    )
    _install_fake_docx_modules(
        monkeypatch,
        document_factory=lambda path: fake_document,
    )

    try:
        document = load_document_from_path(draft_path)
    finally:
        draft_path.unlink(missing_ok=True)

    assert document.text == (
        "Intro paragraph.\n\nR1C1\n\nR1C2\n\nR2C1\n\nR2C2\n\nClosing paragraph."
    )
    assert [paragraph.text for paragraph in document.paragraphs] == [
        "Intro paragraph.",
        "R1C1",
        "R1C2",
        "R2C1",
        "R2C2",
        "Closing paragraph.",
    ]


def test_load_document_from_path_docx_dependency_error_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ingestion should raise a user-actionable error when `python-docx` is unavailable."""
    draft_path = _docx_temp_path("sample-missing-docx")
    draft_path.write_bytes(b"")

    monkeypatch.delitem(sys.modules, "docx", raising=False)
    monkeypatch.delitem(sys.modules, "docx.table", raising=False)
    monkeypatch.delitem(sys.modules, "docx.text", raising=False)
    monkeypatch.delitem(sys.modules, "docx.text.paragraph", raising=False)

    original_import = builtins.__import__

    def import_without_docx(
        name: str,
        globals_dict: dict[str, object] | None = None,
        locals_dict: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == "docx":
            raise ModuleNotFoundError("No module named 'docx'")
        return original_import(name, globals_dict, locals_dict, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_without_docx)
    try:
        with pytest.raises(RuntimeError, match="DOCX ingestion requires python-docx"):
            load_document_from_path(draft_path)
    finally:
        draft_path.unlink(missing_ok=True)


def test_load_document_from_path_rejects_invalid_docx_with_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ingestion should provide a clear message when a `.docx` file cannot be parsed."""
    draft_path = _docx_temp_path("sample-invalid-docx")
    draft_path.write_text("not a docx", encoding="utf-8")

    def failing_document_factory(path: str) -> Any:
        raise ValueError(f"bad docx payload: {path}")

    _install_fake_docx_modules(
        monkeypatch,
        document_factory=failing_document_factory,
    )

    try:
        with pytest.raises(ValueError, match="Unable to read DOCX draft"):
            load_document_from_path(draft_path)
    finally:
        draft_path.unlink(missing_ok=True)
