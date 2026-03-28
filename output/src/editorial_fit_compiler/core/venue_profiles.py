"""Venue profile schema and YAML loader for publication-specific fit settings."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any, cast

from pydantic import Field, model_validator

from .config import _load_yaml_mapping
from .models import DomainModel

SUPPORTED_PROFILE_EXTENSIONS: tuple[str, ...] = (".yaml", ".yml", ".json")
BUILTIN_VENUE_PROFILE_FILES: dict[str, str] = {
    "smr": "smr.yaml",
    "boston_review": "boston_review.yaml",
    "hdsr": "hdsr.yaml",
    "lawfare_like": "lawfare_like.yaml",
    "general_policy_magazine": "general_policy_magazine.yaml",
}


class VenueAudience(DomainModel):
    """Audience expectations for a venue profile."""

    primary_reader: str = Field(min_length=1)
    knowledge_level: str = Field(min_length=1)


class VenueTone(DomainModel):
    """Preferred tonal profile for a venue."""

    voice: str = Field(min_length=1)
    formality: str = Field(min_length=1)


class StructureNorms(DomainModel):
    """Structural norms a draft should follow for a venue."""

    opener_style: str = Field(min_length=1)
    paragraph_length_preference: str = Field(min_length=1)


class DisfavoredMarkers(DomainModel):
    """Markers and patterns a venue generally disfavors."""

    markers: tuple[str, ...]


class ScoreWeights(DomainModel):
    """Required score weighting dimensions used in venue-fit scoring."""

    opening_fit: float = Field(ge=0.0, le=1.0)
    abstraction_control: float = Field(ge=0.0, le=1.0)
    rhythm: float = Field(ge=0.0, le=1.0)
    concreteness: float = Field(ge=0.0, le=1.0)


class VenueProfile(DomainModel):
    """Validated venue profile used by the analysis and scoring pipeline."""

    profile_version: int = Field(default=1)
    venue_id: str = Field(min_length=1)
    audience: VenueAudience
    tone: VenueTone
    structure_norms: StructureNorms
    disfavored_markers: DisfavoredMarkers
    score_weights: ScoreWeights

    @model_validator(mode="after")
    def _validate_supported_profile_version(self) -> VenueProfile:
        """Ensure the profile loader only accepts supported schema versions."""
        if self.profile_version != 1:
            msg = (
                f"Unsupported venue profile version '{self.profile_version}'. "
                "Supported versions: 1."
            )
            raise ValueError(msg)
        return self


def load_venue_profile(profile_path: str | Path) -> VenueProfile:
    """Load and validate a versioned venue profile document from YAML or JSON."""
    parsed = _load_profile_mapping(profile_path)

    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        msg = "Venue profile file must contain a top-level mapping/object"
        raise ValueError(msg)

    return VenueProfile.model_validate(cast(dict[str, Any], parsed))


def load_builtin_venue_profile(venue_key: str) -> VenueProfile:
    """Load and validate a packaged built-in v1 venue profile by key."""
    builtin_filename = BUILTIN_VENUE_PROFILE_FILES.get(venue_key)
    if builtin_filename is None:
        supported = ", ".join(sorted(BUILTIN_VENUE_PROFILE_FILES))
        msg = (
            f"Unknown built-in venue profile '{venue_key}'. "
            f"Supported built-ins: {supported}."
        )
        raise ValueError(msg)

    profile_resource = resources.files("editorial_fit_compiler.core").joinpath(
        "resources", "venue_profiles", builtin_filename
    )
    if not profile_resource.is_file():
        msg = (
            f"Built-in venue profile resource '{builtin_filename}' "
            "is missing from packaged resources."
        )
        raise FileNotFoundError(msg)

    return load_venue_profile(Path(str(profile_resource)))


def _load_profile_mapping(profile_path: str | Path) -> Any:
    """Load a profile document by extension as YAML or JSON data."""
    profile_file = Path(profile_path)
    suffix = profile_file.suffix.lower()

    if suffix in {".yaml", ".yml"}:
        return _load_yaml_mapping(profile_file)
    if suffix == ".json":
        with profile_file.open(encoding="utf-8") as handle:
            return json.load(handle)

    msg = (
        "Unsupported venue profile file extension "
        f"'{suffix or '<none>'}'. Expected one of: {', '.join(SUPPORTED_PROFILE_EXTENSIONS)}."
    )
    raise ValueError(msg)
