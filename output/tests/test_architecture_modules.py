"""Tests for architecture package module imports."""

from importlib import import_module

MODULE_NAMES: tuple[str, ...] = (
    "editorial_fit_compiler.cli",
    "editorial_fit_compiler.core",
    "editorial_fit_compiler.analyzers",
    "editorial_fit_compiler.classifiers",
    "editorial_fit_compiler.reports",
    "editorial_fit_compiler.prompts",
    "editorial_fit_compiler.utils",
)


def test_architecture_modules_are_importable() -> None:
    """All top-level architecture modules should import successfully."""
    for module_name in MODULE_NAMES:
        module = import_module(module_name)
        assert module.__name__ == module_name
