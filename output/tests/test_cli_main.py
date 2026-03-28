"""Tests for the EFC CLI entrypoint."""

from __future__ import annotations

import io
from pathlib import Path

from pytest import MonkeyPatch

import editorial_fit_compiler.cli.main as cli_main
from editorial_fit_compiler.cli.main import _run_with_argparse, app, main


def test_cli_root_runs_without_subcommand(capsys: object) -> None:
    """CLI should be runnable and print readiness text by default."""
    exit_code = main([])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Editorial Fit Compiler CLI ready." in captured.out


def test_cli_version_option_outputs_version(capsys: object) -> None:
    """CLI should expose a version flag for quick verification."""
    exit_code = main(["--version"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip().startswith("efc ")


def test_main_invokes_typer_app(monkeypatch: MonkeyPatch) -> None:
    """`main()` should delegate execution to the Typer app object."""
    if app is None:
        return
    called = {"value": False}

    def fake_app() -> None:
        called["value"] = True

    monkeypatch.setattr("editorial_fit_compiler.cli.main.app", fake_app)
    main()
    assert called["value"] is True


def test_run_with_argparse_works_without_typer(
    capsys: object,
    monkeypatch: MonkeyPatch,
) -> None:
    """`main()` should fall back to argparse when Typer is unavailable."""
    monkeypatch.setattr(cli_main, "typer", None)
    monkeypatch.setattr(cli_main, "app", None)
    exit_code = main(["--version"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip().startswith("efc ")


def test_argparse_runner_default_output(capsys: object) -> None:
    """The argparse fallback should print the default readiness message."""
    exit_code = _run_with_argparse([])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Editorial Fit Compiler CLI ready." in captured.out


def test_cli_analyze_loads_text_draft(capsys: object) -> None:
    """The analyze command should ingest a .txt draft path into the document model."""
    draft_path = Path(__file__).parent / "fixtures" / "ingestion" / "sample.txt"
    exit_code = main(["analyze", str(draft_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Loaded draft" in captured.out
    assert "2 paragraphs" in captured.out


def test_argparse_analyze_reads_stdin_when_draft_path_is_omitted(
    capsys: object,
    monkeypatch: MonkeyPatch,
) -> None:
    """Analyze should read stdin text when draft_path is omitted."""
    monkeypatch.setattr("sys.stdin", io.StringIO("First block.\n\nSecond block."))

    exit_code = _run_with_argparse(["analyze"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Loaded draft <stdin>" in captured.out
    assert "2 paragraphs" in captured.out


def test_cli_profile_show_prints_human_readable_summary(capsys: object) -> None:
    """The profile show command should print a readable built-in venue summary."""
    exit_code = main(["profile", "show", "smr"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Venue profile: smr" in captured.out
    assert "Audience:" in captured.out
    assert "Score weights:" in captured.out


def test_argparse_profile_show_prints_human_readable_summary(capsys: object) -> None:
    """Argparse fallback should support profile show output for known venue IDs."""
    exit_code = _run_with_argparse(["profile", "show", "smr"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Venue profile: smr" in captured.out
    assert "Disfavored markers:" in captured.out
