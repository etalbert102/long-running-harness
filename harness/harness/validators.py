"""Hard validation gates for generated projects.

The generator cannot mark a feature as done unless the active validator suite
passes. The suite is chosen from project files and the copied app spec, so
Python projects use Python tooling and Node/TypeScript projects use npm-based
tooling.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from harness.client import get_output_dir

logger = logging.getLogger("harness.validators")


@dataclass
class ValidationResult:
    name: str
    passed: bool
    output: str


@dataclass
class ProjectProfile:
    kind: str
    typecheck_cmd: list[str] | None
    lint_cmd: list[str] | None
    build_cmd: list[str] | None
    test_cmd: list[str] | None


PYTHON_HINTS = (
    "python",
    "pytest",
    "ruff",
    "mypy",
    "fastapi",
    "flask",
    "django",
    "pydantic",
)

NODE_HINTS = (
    "typescript",
    "javascript",
    "node",
    "npm",
    "eslint",
    "vitest",
    "tsconfig",
)


def _build_env(cwd: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build a subprocess environment for validator commands."""
    env = os.environ.copy()
    src_dir = cwd / "src"
    if src_dir.exists():
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(src_dir) if not existing else os.pathsep.join([str(src_dir), existing])
    if extra:
        env.update(extra)
    return env


async def _run_cmd(
    name: str,
    cmd: list[str],
    cwd: Path,
    *,
    extra_env: dict[str, str] | None = None,
) -> ValidationResult:
    """Run a shell command and capture output."""
    logger.info(f"[validators] Running {name}: {' '.join(cmd)}")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            env=_build_env(cwd, extra_env),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        output = stdout.decode("utf-8", errors="replace")
        passed = proc.returncode == 0
        logger.info(f"[validators] {name}: {'PASS' if passed else 'FAIL'} (exit {proc.returncode})")
        return ValidationResult(name=name, passed=passed, output=output)
    except asyncio.TimeoutError:
        logger.warning(f"[validators] {name}: TIMEOUT")
        return ValidationResult(name=name, passed=False, output="Timed out after 120s")
    except FileNotFoundError:
        logger.warning(f"[validators] {name}: command not found")
        return ValidationResult(name=name, passed=False, output=f"Command not found: {cmd[0]}")


def _find_python_files(cwd: Path) -> list[Path]:
    return [
        path for path in cwd.rglob("*.py")
        if ".venv" not in path.parts and "venv" not in path.parts and "__pycache__" not in path.parts
    ]


def _spec_text(cwd: Path) -> str:
    spec_path = cwd / "app_spec.md"
    if not spec_path.exists():
        return ""
    try:
        return spec_path.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return ""


def _detect_project_kind(cwd: Path) -> str:
    forced_kind = os.environ.get("HARNESS_PROJECT_TYPE", "").strip().lower()
    if forced_kind in {"python", "node"}:
        return forced_kind

    if (cwd / "package.json").exists():
        return "node"
    if (cwd / "pyproject.toml").exists() or (cwd / "requirements.txt").exists() or (cwd / "setup.py").exists():
        return "python"

    if _find_python_files(cwd):
        return "python"

    spec_text = _spec_text(cwd)
    if any(hint in spec_text for hint in PYTHON_HINTS):
        return "python"
    if any(hint in spec_text for hint in NODE_HINTS):
        return "node"

    return "unknown"


def _pick_python_typecheck(cwd: Path) -> list[str]:
    if shutil.which("mypy"):
        return ["mypy", "."]
    return [sys.executable, "-m", "compileall", "."]


def _pick_python_lint(cwd: Path) -> list[str]:
    if shutil.which("ruff"):
        return ["ruff", "check", "."]

    python_files = _find_python_files(cwd)
    if not python_files:
        return [sys.executable, "-m", "compileall", "."]
    return [sys.executable, "-m", "py_compile", *[str(path) for path in python_files]]


def _pick_python_build(cwd: Path) -> list[str] | None:
    if not (cwd / "pyproject.toml").exists():
        return None
    return [sys.executable, "-m", "build"]


def _pick_python_test(cwd: Path) -> list[str]:
    if shutil.which("pytest"):
        return [sys.executable, "-m", "pytest", "-q", "tests"]
    return [sys.executable, "-m", "unittest", "discover"]


def detect_project_profile(cwd: Path | None = None) -> ProjectProfile:
    """Detect which validator suite should run."""
    target = cwd or get_output_dir()
    kind = _detect_project_kind(target)

    if kind == "node":
        return ProjectProfile(
            kind="node",
            typecheck_cmd=["npx", "tsc", "--noEmit"],
            lint_cmd=["npx", "eslint", "."],
            build_cmd=["npm", "run", "build"],
            test_cmd=["npm", "test"],
        )

    if kind == "python":
        return ProjectProfile(
            kind="python",
            typecheck_cmd=_pick_python_typecheck(target),
            lint_cmd=_pick_python_lint(target),
            build_cmd=_pick_python_build(target),
            test_cmd=_pick_python_test(target),
        )

    return ProjectProfile(
        kind="unknown",
        typecheck_cmd=None,
        lint_cmd=None,
        build_cmd=None,
        test_cmd=None,
    )


async def run_typecheck(cwd: Path | None = None) -> ValidationResult:
    """Run the active type-check or syntax-check command."""
    target = cwd or get_output_dir()
    profile = detect_project_profile(target)
    if not profile.typecheck_cmd:
        return ValidationResult("typecheck", False, "No project type detected")
    return await _run_cmd("typecheck", profile.typecheck_cmd, target)


async def run_lint(cwd: Path | None = None) -> ValidationResult:
    """Run the active linter command."""
    target = cwd or get_output_dir()
    profile = detect_project_profile(target)
    if not profile.lint_cmd:
        return ValidationResult("lint", False, "No project type detected")
    return await _run_cmd("lint", profile.lint_cmd, target)


async def run_build(cwd: Path | None = None) -> ValidationResult:
    """Run the active build or packaging command."""
    target = cwd or get_output_dir()
    profile = detect_project_profile(target)
    if not profile.build_cmd:
        return ValidationResult("build", True, f"No build step configured for {profile.kind} project")
    return await _run_cmd("build", profile.build_cmd, target)


async def run_tests(cwd: Path | None = None) -> ValidationResult:
    """Run the active test command."""
    target = cwd or get_output_dir()
    profile = detect_project_profile(target)
    if not profile.test_cmd:
        return ValidationResult("test", False, "No project type detected")
    return await _run_cmd("test", profile.test_cmd, target)


async def run_all_validators(cwd: Path | None = None) -> list[ValidationResult]:
    """Run the validator suite for the detected project type."""
    target = cwd or get_output_dir()
    profile = detect_project_profile(target)

    if profile.kind == "unknown":
        logger.warning(f"[validators] Could not infer project type in {target}")
        return [ValidationResult(name="setup", passed=False, output="Could not infer project type from files or spec")]

    typecheck_result, lint_result = await asyncio.gather(
        run_typecheck(target),
        run_lint(target),
    )
    results = [typecheck_result, lint_result]

    if typecheck_result.passed:
        build_result = await run_build(target)
        results.append(build_result)
        if build_result.passed:
            results.append(await run_tests(target))
        else:
            results.append(ValidationResult(name="test", passed=False, output="Skipped: build failed"))
    else:
        results.append(ValidationResult(name="build", passed=False, output="Skipped: typecheck failed"))
        results.append(ValidationResult(name="test", passed=False, output="Skipped: typecheck failed"))

    return results


def all_passed(results: list[ValidationResult]) -> bool:
    """Check if all validators passed."""
    return all(result.passed for result in results)


def format_failures(results: list[ValidationResult]) -> str:
    """Format failed validation results for the generator retry prompt."""
    failures = [result for result in results if not result.passed]
    if not failures:
        return "All validators passed."

    parts = []
    for failure in failures:
        parts.append(f"## {failure.name} FAILED\n{failure.output[:2000]}")

    return "\n\n".join(parts)
