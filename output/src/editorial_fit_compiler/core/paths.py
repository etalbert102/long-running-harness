"""Artifact and report path management for draft processing outputs."""

from __future__ import annotations

from pathlib import Path

from .models import DomainModel


class ArtifactPaths(DomainModel):
    """Resolved output locations for a single draft analysis run."""

    draft_path: Path
    artifact_dir: Path
    report_markdown_path: Path
    report_json_path: Path


def resolve_artifact_paths(
    draft_path: str | Path,
    output_dir: str | Path | None = None,
) -> ArtifactPaths:
    """Resolve dedicated artifact locations for report outputs without touching the source draft."""
    draft = Path(draft_path).resolve()
    artifact_root = (
        Path(output_dir).resolve() if output_dir is not None else draft.parent / "artifacts"
    )

    return ArtifactPaths(
        draft_path=draft,
        artifact_dir=artifact_root,
        report_markdown_path=artifact_root / f"{draft.stem}_report.md",
        report_json_path=artifact_root / f"{draft.stem}_report.json",
    )


def write_text_artifact(path: str | Path, content: str, source_draft_path: str | Path) -> Path:
    """Write text content to an artifact path while preventing source draft overwrite."""
    target_path = Path(path).resolve()
    source_path = Path(source_draft_path).resolve()
    if target_path == source_path:
        msg = "Artifact output path must not match the source draft path"
        raise ValueError(msg)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    return target_path
