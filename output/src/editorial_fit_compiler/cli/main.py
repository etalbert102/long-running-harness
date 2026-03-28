"""CLI entrypoint for the Editorial Fit Compiler."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from editorial_fit_compiler import __version__
from editorial_fit_compiler.core.ingestion import load_document_from_path

try:
    import typer
except ModuleNotFoundError:  # pragma: no cover - exercised when typer is absent.
    typer = None

app = None
if typer is not None:
    app = typer.Typer(help="Editorial Fit Compiler command-line interface.")

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
    def analyze(draft_path: Path) -> None:
        """Load a supported draft file into the canonical document model."""
        document = load_document_from_path(draft_path)
        typer.echo(
            "Loaded draft "
            f"{document.source_path} ({len(document.text)} chars, "
            f"{len(document.paragraphs)} paragraphs)."
        )


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
    analyze_parser.add_argument("draft_path", type=Path, help="Path to a .md or .txt draft.")
    args = parser.parse_args(argv)
    if args.version:
        print(f"efc {__version__}")
    elif args.command == "analyze":
        document = load_document_from_path(args.draft_path)
        print(
            "Loaded draft "
            f"{document.source_path} ({len(document.text)} chars, "
            f"{len(document.paragraphs)} paragraphs)."
        )
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
