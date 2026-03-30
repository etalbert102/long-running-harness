"""Harness runtime configuration helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"

MODEL_TIERS = {
    "planner": "HARNESS_MODEL_PLANNER",
    "generator": "HARNESS_MODEL_GENERATOR",
    "evaluator": "HARNESS_MODEL_EVALUATOR",
}

DEFAULT_MODELS = {
    "planner": "gpt-5.4-mini",
    "generator": "gpt-5.3-codex",
    "evaluator": "gpt-5.4",
}

DEFAULT_POLICY_MODE = "dynamic"


def get_provider() -> str:
    """Return the active harness provider backend."""
    provider = os.environ.get("HARNESS_PROVIDER", "codex").strip().lower() or "codex"
    if provider == "codex-cli":
        return "codex"
    if provider in {"openai-api", "openai_compatible_api", "api"}:
        return "openai-compatible"
    if provider in {"anthropic-api", "claude", "claude-code"}:
        return "anthropic"
    return provider


def get_output_dir() -> Path:
    """Return the active output directory for this harness run."""
    override = os.environ.get("HARNESS_OUTPUT_OVERRIDE")
    path = Path(override) if override else DEFAULT_OUTPUT_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_model_for_role(role: str) -> str:
    """Get the model for a given agent role, checking env var overrides."""
    env_key = MODEL_TIERS.get(role, "HARNESS_MODEL")
    return os.environ.get(
        env_key,
        os.environ.get("HARNESS_MODEL", DEFAULT_MODELS.get(role, "gpt-5.3-codex")),
    )


def get_policy_mode() -> str:
    """Return the model selection policy mode."""
    return os.environ.get("HARNESS_MODEL_POLICY", DEFAULT_POLICY_MODE).strip().lower() or DEFAULT_POLICY_MODE


def get_project_type_override() -> str | None:
    """Return the explicit project type override, if any."""
    value = os.environ.get("HARNESS_PROJECT_TYPE", "").strip().lower()
    return value or None


def get_api_base_url() -> str:
    """Return the configured direct API base URL."""
    return os.environ.get("HARNESS_API_BASE_URL", "").strip().rstrip("/")


def get_api_key() -> str:
    """Return the configured API key for direct API backends."""
    return os.environ.get("HARNESS_API_KEY", "").strip()


def get_api_headers() -> dict[str, str]:
    """Return extra API headers from a JSON environment variable."""
    raw = os.environ.get("HARNESS_API_HEADERS", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def get_anthropic_base_url() -> str:
    """Return the configured Anthropic base URL or the public default."""
    value = os.environ.get("HARNESS_ANTHROPIC_BASE_URL", "").strip().rstrip("/")
    return value or "https://api.anthropic.com"


def get_anthropic_api_key() -> str:
    """Return the configured Anthropic API key."""
    return os.environ.get("HARNESS_ANTHROPIC_API_KEY", "").strip() or get_api_key()


def get_anthropic_version() -> str:
    """Return the configured Anthropic API version header."""
    return os.environ.get("HARNESS_ANTHROPIC_VERSION", "2023-06-01").strip() or "2023-06-01"


def get_allowed_sink_wrappers() -> list[str]:
    """Return allowed sink wrapper names for forbidden sink scanning.

    Merges DEFAULT_ALLOWED_WRAPPERS from fidelity_framework with any
    project-specific wrappers from HARNESS_ALLOWED_SINK_WRAPPERS (comma-separated).
    """
    try:
        from fidelity_framework_v1 import DEFAULT_ALLOWED_WRAPPERS
        base: list[str] = list(DEFAULT_ALLOWED_WRAPPERS)
    except ImportError:
        base = []

    extra = os.environ.get("HARNESS_ALLOWED_SINK_WRAPPERS", "").strip()
    if extra:
        base.extend(w.strip() for w in extra.split(",") if w.strip())
    return base


def get_claude_code_oauth_token() -> str:
    """Return the locally stored Claude Code OAuth access token, if available."""
    credentials_path = Path.home() / ".claude" / ".credentials.json"
    try:
        data = json.loads(credentials_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    oauth = data.get("claudeAiOauth")
    if not isinstance(oauth, dict):
        return ""
    token = oauth.get("accessToken", "")
    return str(token).strip()
