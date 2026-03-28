"""Tests for venue profile schema validation and YAML loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from editorial_fit_compiler.core.venue_profiles import (
    BUILTIN_VENUE_PROFILE_FILES,
    VenueProfile,
    load_builtin_venue_profile,
    load_venue_profile,
)
from pydantic import ValidationError

REQUIRED_TOP_LEVEL_FIELDS: tuple[str, ...] = (
    "audience",
    "tone",
    "structure_norms",
    "disfavored_markers",
    "score_weights",
)
REQUIRED_WEIGHT_FIELDS: tuple[str, ...] = (
    "opening_fit",
    "abstraction_control",
    "rhythm",
    "concreteness",
)


def test_load_venue_profile_parses_valid_yaml() -> None:
    """Loader should parse a valid venue profile into the typed schema."""
    loaded = load_venue_profile(_fixture_path("valid_profile.yaml"))

    assert isinstance(loaded, VenueProfile)
    assert loaded.venue_id == "smr"
    assert loaded.audience.primary_reader == "policy professionals"
    assert loaded.tone.voice == "analytical"
    assert loaded.structure_norms.opener_style == "stakes-first"
    assert loaded.disfavored_markers.markers == ("em_dash", "citation_clusters")
    assert loaded.score_weights.opening_fit == 0.35
    assert loaded.score_weights.abstraction_control == 0.2
    assert loaded.score_weights.rhythm == 0.2
    assert loaded.score_weights.concreteness == 0.25


def test_load_venue_profile_parses_valid_json() -> None:
    """Loader should parse a valid JSON venue profile into the typed schema."""
    loaded = load_venue_profile(_fixture_path("valid_profile.json"))

    assert isinstance(loaded, VenueProfile)
    assert loaded.profile_version == 1
    assert loaded.venue_id == "smr_json"


@pytest.mark.parametrize("missing_field", REQUIRED_TOP_LEVEL_FIELDS)
def test_load_venue_profile_requires_all_top_level_sections(missing_field: str) -> None:
    """Validation should fail when any required top-level profile section is absent."""
    with pytest.raises(ValidationError, match=missing_field):
        load_venue_profile(_fixture_path(f"missing_{missing_field}_profile.yaml"))


@pytest.mark.parametrize("missing_weight", REQUIRED_WEIGHT_FIELDS)
def test_load_venue_profile_requires_all_score_weight_fields(missing_weight: str) -> None:
    """Validation should fail when any required score weight field is absent."""
    with pytest.raises(ValidationError, match=missing_weight):
        load_venue_profile(_fixture_path(f"missing_weight_{missing_weight}_profile.yaml"))


def test_load_venue_profile_rejects_unsupported_profile_version() -> None:
    """Validation should return a version error for unsupported profile schema versions."""
    with pytest.raises(ValidationError, match=r"profile_version|Supported versions: 1"):
        load_venue_profile(_fixture_path("unsupported_version_profile.json"))


def test_load_venue_profile_rejects_non_mapping_top_level_data() -> None:
    """Loader should fail with a clear error when profile data is not a mapping/object."""
    with pytest.raises(ValueError, match="top-level mapping/object"):
        load_venue_profile(_fixture_path("invalid_top_level_profile.json"))


def test_load_venue_profile_returns_actionable_schema_errors() -> None:
    """Invalid profile schema should include actionable nested field error details."""
    with pytest.raises(ValidationError, match=r"opening_fit|score_weights"):
        load_venue_profile(_fixture_path("invalid_schema_profile.json"))


@pytest.mark.parametrize("venue_key", tuple(sorted(BUILTIN_VENUE_PROFILE_FILES)))
def test_load_builtin_venue_profile_resolves_packaged_v1_profiles(venue_key: str) -> None:
    """Built-in venue keys should resolve packaged resources into validated v1 profiles."""
    loaded = load_builtin_venue_profile(venue_key)

    assert isinstance(loaded, VenueProfile)
    assert loaded.profile_version == 1
    assert loaded.venue_id == venue_key
    assert len(loaded.disfavored_markers.markers) >= 1


def test_load_builtin_venue_profile_rejects_unknown_key() -> None:
    """Unknown built-in keys should fail with supported-key guidance."""
    with pytest.raises(ValueError, match=r"Unknown built-in venue profile|Supported built-ins"):
        load_builtin_venue_profile("unknown_venue")


def _fixture_path(filename: str) -> Path:
    """Resolve a venue profile fixture path used by venue schema tests."""
    return Path(__file__).parent / "fixtures" / "venue_profiles" / filename
