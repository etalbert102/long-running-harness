"""Tests for the EFC CLI entrypoint."""

from __future__ import annotations

from editorial_fit_compiler.cli.main import app, main


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


def test_main_invokes_typer_app(monkeypatch: object) -> None:
    """`main()` should delegate execution to the Typer app object."""
    if app is None:
        return
    called = {"value": False}

    def fake_app() -> None:
        called["value"] = True

    monkeypatch.setattr("editorial_fit_compiler.cli.main.app", fake_app)
    main()
    assert called["value"] is True
