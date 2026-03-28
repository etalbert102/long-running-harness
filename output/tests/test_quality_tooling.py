"""Tests for local quality-tool configuration defaults."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path
from shutil import which

import pytest


def _project_root() -> Path:
    """Return the repository root directory for subprocess-based tool checks."""
    return Path(__file__).resolve().parents[1]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command from the repository root and return the result."""
    return subprocess.run(
        args,
        cwd=_project_root(),
        text=True,
        capture_output=True,
        check=False,
    )


def test_pyproject_includes_quality_tool_defaults() -> None:
    """The project should define pytest, ruff, and mypy defaults in pyproject.toml."""
    pyproject = _project_root() / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    tool = data["tool"]

    assert "pytest" in tool
    assert "ruff" in tool
    assert "mypy" in tool
    assert "editorial_fit_compiler" in tool
    assert tool["pytest"]["ini_options"]["pythonpath"] == ["src"]
    assert tool["mypy"]["files"] == ["src"]
    assert (
        tool["editorial_fit_compiler"]["verify_command"]
        == "python -m pytest && ruff check src tests && mypy"
    )


def test_ruff_command_runs_with_defaults() -> None:
    """Ruff should run with the repository default configuration."""
    if which("ruff") is None:
        pytest.skip("ruff is not available in this environment")

    command = ["ruff", "check", "src", "tests"]
    result = _run(command)
    assert result.returncode == 0, (
        f"Command failed: {' '.join(command)}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_mypy_command_runs_with_defaults() -> None:
    """Mypy should run with the repository default configuration."""
    if which("mypy") is None:
        pytest.skip("mypy is not available in this environment")

    command = ["mypy"]
    result = _run(command)
    assert result.returncode == 0, (
        f"Command failed: {' '.join(command)}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_pytest_collect_only_runs_with_defaults() -> None:
    """Pytest should collect tests successfully with the repository defaults."""
    command = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
    result = _run(command)
    assert result.returncode == 0, (
        f"Command failed: {' '.join(command)}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
