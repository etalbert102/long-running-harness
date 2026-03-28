"""Base transport types for model API integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A tool invocation requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ModelResponse:
    """Normalized model response across providers."""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    finish_reason: str | None = None


class TransportError(RuntimeError):
    """Raised when the underlying transport fails."""

