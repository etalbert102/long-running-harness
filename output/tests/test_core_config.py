"""Tests for typed user configuration models and YAML loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from editorial_fit_compiler.core.config import (
    ConfigConstraints,
    ConfigPreferences,
    UserConfig,
    load_user_config,
)
from pydantic import ValidationError


def test_load_user_config_parses_valid_yaml_with_nested_models() -> None:
    """Loader should parse valid YAML and return strongly-typed nested config models."""
    loaded = load_user_config(_fixture_path("valid_job.yaml"))

    assert isinstance(loaded, UserConfig)
    assert loaded.draft_path == "drafts/input.md"
    assert loaded.target_venue == "smr"
    assert isinstance(loaded.constraints, ConfigConstraints)
    assert loaded.constraints.preserve_concepts == (
        "Behavioral Compression",
        "Decision-Space Erosion",
    )
    assert loaded.constraints.forbid == ("em_dash", "citations")
    assert loaded.constraints.max_new_sentences == 3
    assert loaded.constraints.word_count_tolerance_percent == 5.0
    assert isinstance(loaded.preferences, ConfigPreferences)
    assert loaded.preferences.prioritize == ("executive_credibility", "concrete_language")


def test_load_user_config_applies_defaults_for_optional_sections() -> None:
    """Loader should apply typed defaults when constraints and preferences are omitted."""
    loaded = load_user_config(_fixture_path("job_defaults.yaml"))

    assert loaded.constraints.preserve_concepts == ConfigConstraints().preserve_concepts
    assert loaded.constraints.forbid == ConfigConstraints().forbid
    assert loaded.constraints.max_new_sentences is None
    assert loaded.constraints.word_count_tolerance_percent is None
    assert loaded.preferences.prioritize == ConfigPreferences().prioritize


def test_load_user_config_requires_draft_path_and_target_venue() -> None:
    """Required top-level fields should be enforced by model validation."""
    with pytest.raises(ValidationError):
        load_user_config(_fixture_path("job_missing_required.yaml"))


def _fixture_path(filename: str) -> Path:
    """Resolve a configuration fixture path used by config model tests."""
    return Path(__file__).parent / "fixtures" / "config" / filename
