"""Configuration models and YAML loader for user job configuration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

from pydantic import Field, ValidationError

from .models import DomainModel


class ConfigConstraints(DomainModel):
    """Constraint settings loaded from user configuration."""

    preserve_concepts: tuple[str, ...] = ()
    forbid: tuple[str, ...] = ()
    max_new_sentences: int | None = Field(default=None, ge=0)
    word_count_tolerance_percent: float | None = Field(default=None, ge=0.0, le=100.0)


class ConfigPreferences(DomainModel):
    """Preference hints used to tune prioritization and scoring focus."""

    prioritize: tuple[str, ...] = ()


class UserConfig(DomainModel):
    """Top-level typed representation of a user-supplied job configuration file."""

    draft_path: str = Field(min_length=1)
    target_venue: str = Field(min_length=1)
    constraints: ConfigConstraints = ConfigConstraints()
    preferences: ConfigPreferences = ConfigPreferences()


def load_user_config(config_path: str | Path) -> UserConfig:
    """Load a YAML config file and validate it against the typed user config schema."""
    parsed = _load_yaml_mapping(config_path)

    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        msg = "Config file must contain a YAML mapping at the top level"
        raise ValidationError(msg)

    return UserConfig.model_validate(cast(dict[str, Any], parsed))


def _load_yaml_mapping(config_path: str | Path) -> Any:
    """Load YAML into Python objects using PyYAML when available, else a safe subset parser."""
    with Path(config_path).open(encoding="utf-8") as handle:
        content = handle.read()

    try:
        import yaml  # type: ignore[import-not-found]

        return yaml.safe_load(content)
    except ModuleNotFoundError:
        return _parse_yaml_subset(content)


def _parse_yaml_subset(content: str) -> Any:
    """Parse a restricted YAML subset that supports mappings and scalar lists."""
    tokenized = _tokenize(content)
    if not tokenized:
        return {}
    parsed, index = _parse_mapping(tokenized, 0, tokenized[0][0])
    if index != len(tokenized):
        msg = "Unable to parse YAML content"
        raise ValidationError(msg)
    return parsed


def _tokenize(content: str) -> list[tuple[int, str]]:
    """Convert YAML text into indentation-aware tokens while skipping empty/comment lines."""
    tokens: list[tuple[int, str]] = []
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indentation = len(raw_line) - len(raw_line.lstrip(" "))
        tokens.append((indentation, stripped))
    return tokens


def _parse_mapping(
    tokens: list[tuple[int, str]],
    index: int,
    indent: int,
) -> tuple[dict[str, Any], int]:
    """Parse a mapping block at a specific indentation level."""
    mapping: dict[str, Any] = {}
    while index < len(tokens):
        current_indent, text = tokens[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            msg = "Invalid YAML indentation"
            raise ValidationError(msg)
        if text.startswith("- "):
            msg = "Unexpected list item in mapping context"
            raise ValidationError(msg)
        if ":" not in text:
            msg = "Invalid YAML mapping entry"
            raise ValidationError(msg)
        key, remainder = text.split(":", 1)
        key = key.strip()
        remainder = remainder.strip()
        index += 1

        if remainder:
            mapping[key] = _parse_scalar(remainder)
            continue

        if index >= len(tokens) or tokens[index][0] <= indent:
            mapping[key] = {}
            continue

        child_indent, child_text = tokens[index]
        if child_text.startswith("- "):
            parsed_list, index = _parse_list(tokens, index, child_indent)
            mapping[key] = parsed_list
        else:
            parsed_mapping, index = _parse_mapping(tokens, index, child_indent)
            mapping[key] = parsed_mapping
    return mapping, index


def _parse_list(tokens: list[tuple[int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    """Parse a list block at a specific indentation level."""
    items: list[Any] = []
    while index < len(tokens):
        current_indent, text = tokens[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            msg = "Invalid YAML indentation inside list"
            raise ValidationError(msg)
        if not text.startswith("- "):
            break

        payload = text[2:].strip()
        index += 1

        if payload:
            items.append(_parse_scalar(payload))
            continue

        if index >= len(tokens) or tokens[index][0] <= indent:
            items.append({})
            continue

        child_indent, child_text = tokens[index]
        if child_text.startswith("- "):
            parsed_list, index = _parse_list(tokens, index, child_indent)
            items.append(parsed_list)
        else:
            parsed_mapping, index = _parse_mapping(tokens, index, child_indent)
            items.append(parsed_mapping)
    return items, index


def _parse_scalar(raw_value: str) -> Any:
    """Parse scalar YAML values into bool/int/float/None/str."""
    lowered = raw_value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "~"}:
        return None
    if re.fullmatch(r"-?\d+", raw_value):
        return int(raw_value)
    if re.fullmatch(r"-?\d+\.\d+", raw_value):
        return float(raw_value)
    if (raw_value.startswith('"') and raw_value.endswith('"')) or (
        raw_value.startswith("'") and raw_value.endswith("'")
    ):
        return raw_value[1:-1]
    return raw_value
