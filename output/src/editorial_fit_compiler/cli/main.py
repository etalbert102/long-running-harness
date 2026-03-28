"""CLI entrypoint for the Editorial Fit Compiler."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from editorial_fit_compiler import __version__
from editorial_fit_compiler.core.ingestion import load_document_from_path, load_document_from_text
from editorial_fit_compiler.core.models import Document
from editorial_fit_compiler.core.venue_profiles import load_builtin_venue_profile

try:
    import typer
except ModuleNotFoundError:  # pragma: no cover - exercised when typer is absent.
    typer = None

app = None


def _load_analysis_document(draft_path: Path | None) -> Document:
    """Load analysis input from a draft path or stdin when no path is provided."""
    if draft_path is not None:
        return load_document_from_path(draft_path)
    return load_document_from_text(sys.stdin.read(), source_name="<stdin>")


def _render_venue_profile_summary(venue_id: str) -> str:
    """Build a human-readable summary of a built-in venue profile."""
    profile = load_builtin_venue_profile(venue_id)
    marker_list = ", ".join(profile.disfavored_markers.markers)
    return (
        f"Venue profile: {profile.venue_id}\n"
        f"Version: v{profile.profile_version}\n"
        f"Audience: {profile.audience.primary_reader} ({profile.audience.knowledge_level})\n"
        f"Tone: {profile.tone.voice}; formality={profile.tone.formality}\n"
        f"Structure: opener={profile.structure_norms.opener_style}; "
        f"paragraphs={profile.structure_norms.paragraph_length_preference}\n"
        f"Disfavored markers: {marker_list}\n"
        "Score weights:\n"
        f"- opening_fit: {profile.score_weights.opening_fit:.2f}\n"
        f"- abstraction_control: {profile.score_weights.abstraction_control:.2f}\n"
        f"- rhythm: {profile.score_weights.rhythm:.2f}\n"
        f"- concreteness: {profile.score_weights.concreteness:.2f}"
    )


if typer is not None:
    app = typer.Typer(help="Editorial Fit Compiler command-line interface.")
    profile_app = typer.Typer(help="Inspect built-in venue profile definitions.")
    app.add_typer(profile_app, name="profile")

    @app.callback(invoke_without_command=True)
    def root(
        ctx: typer.Context,
        version: bool = typer.Option(
            False,
            "--version",
            help="Show the installed Editorial Fit Compiler version.",
        ),
    ) -> None:
        """Handle top-level CLI options and default behavior."""
        if version:
            typer.echo(f"efc {__version__}")
            raise typer.Exit()
        if ctx.invoked_subcommand is None:
            typer.echo("Editorial Fit Compiler CLI ready.")
            raise typer.Exit()

    @app.command()
    def analyze(draft_path: Path | None = None) -> None:
        """Load a supported draft file or stdin text into the canonical document model."""
        document = _load_analysis_document(draft_path)
        typer.echo(
            "Loaded draft "
            f"{document.source_path} ({len(document.text)} chars, "
            f"{len(document.paragraphs)} paragraphs)."
        )

    @profile_app.command("show")
    def profile_show(venue_id: str) -> None:
        """Print a human-readable summary for a built-in venue profile ID."""
        typer.echo(_render_venue_profile_summary(venue_id))


def _run_with_argparse(argv: Sequence[str] | None = None) -> int:
    """Run a minimal CLI fallback when Typer is unavailable."""
    parser = argparse.ArgumentParser(
        prog="efc",
        description="Editorial Fit Compiler command-line interface.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show the installed Editorial Fit Compiler version.",
    )
    subparsers = parser.add_subparsers(dest="command")
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a supported draft file.")
    analyze_parser.add_argument(
        "draft_path",
        type=Path,
        nargs="?",
        help="Path to a .md, .txt, or .docx draft. Omit to read from stdin.",
    )
    profile_parser = subparsers.add_parser("profile", help="Inspect built-in venue profiles.")
    profile_subparsers = profile_parser.add_subparsers(dest="profile_command")
    profile_show_parser = profile_subparsers.add_parser(
        "show",
        help="Print a built-in venue profile summary.",
    )
    profile_show_parser.add_argument(
        "venue_id",
        type=str,
        help="Built-in venue profile identifier (for example: smr).",
    )
    args = parser.parse_args(argv)
    if args.version:
        print(f"efc {__version__}")
    elif args.command == "analyze":
        document = _load_analysis_document(args.draft_path)
        print(
            "Loaded draft "
            f"{document.source_path} ({len(document.text)} chars, "
            f"{len(document.paragraphs)} paragraphs)."
        )
    elif args.command == "profile" and args.profile_command == "show":
        print(_render_venue_profile_summary(args.venue_id))
    else:
        print("Editorial Fit Compiler CLI ready.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI entrypoint and return a process status code."""
    if typer is not None:
        if argv is None:
            app()
        else:
            app(args=list(argv), prog_name="efc")
        return 0
    return _run_with_argparse(argv)


if __name__ == "__main__":
    raise SystemExit(main())
