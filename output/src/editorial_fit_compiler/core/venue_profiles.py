"""Venue profile schema and YAML loader for publication-specific fit settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from pydantic import Field, ValidationError

from .config import _load_yaml_mapping
from .models import DomainModel


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

    venue_id: str = Field(min_length=1)
    audience: VenueAudience
    tone: VenueTone
    structure_norms: StructureNorms
    disfavored_markers: DisfavoredMarkers
    score_weights: ScoreWeights


def load_venue_profile(profile_path: str | Path) -> VenueProfile:
    """Load and validate a venue profile YAML file into a typed schema."""
    parsed = _load_yaml_mapping(profile_path)

    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        msg = "Venue profile file must contain a YAML mapping at the top level"
        raise ValidationError(msg)

    return VenueProfile.model_validate(cast(dict[str, Any], parsed))
