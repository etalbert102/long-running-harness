"""Tests for artifact/report path resolution and safe output writing."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

from editorial_fit_compiler.core.paths import resolve_artifact_paths, write_text_artifact


def test_resolve_artifact_paths_uses_dedicated_artifact_directory() -> None:
    """Resolved report outputs should be placed under an artifacts directory."""
    test_root = _new_local_temp_dir()
    try:
        draft_path = test_root / "drafts" / "input.md"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text("Original draft content", encoding="utf-8")

        resolved = resolve_artifact_paths(draft_path)

        assert resolved.draft_path == draft_path.resolve()
        assert resolved.artifact_dir == draft_path.parent / "artifacts"
        assert resolved.report_markdown_path == resolved.artifact_dir / "input_report.md"
        assert resolved.report_json_path == resolved.artifact_dir / "input_report.json"
        assert resolved.report_markdown_path != draft_path.resolve()
        assert resolved.report_json_path != draft_path.resolve()
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def test_write_text_artifact_writes_output_without_modifying_draft() -> None:
    """Artifact writing should not mutate source draft contents."""
    test_root = _new_local_temp_dir()
    try:
        draft_path = test_root / "input.md"
        draft_content = "Source draft should stay unchanged."
        draft_path.write_text(draft_content, encoding="utf-8")
        output_path = test_root / "artifacts" / "input_report.md"

        written_path = write_text_artifact(
            output_path,
            "Generated report",
            source_draft_path=draft_path,
        )

        assert written_path == output_path.resolve()
        assert output_path.read_text(encoding="utf-8") == "Generated report"
        assert draft_path.read_text(encoding="utf-8") == draft_content
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def test_write_text_artifact_rejects_source_draft_target() -> None:
    """Writing directly to the source draft path should raise a clear error."""
    test_root = _new_local_temp_dir()
    try:
        draft_path = test_root / "input.md"
        draft_path.write_text("Original", encoding="utf-8")

        with pytest.raises(ValueError, match="must not match the source draft path"):
            write_text_artifact(draft_path, "Overwrite attempt", source_draft_path=draft_path)
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def _new_local_temp_dir() -> Path:
    """Create a unique, repo-local temporary directory for path tests."""
    root = Path(".tmp") / "test_core_paths" / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()
