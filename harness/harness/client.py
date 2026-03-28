"""Harness runtime configuration helpers."""

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


def get_provider() -> str:
    """Return the active harness provider backend."""
    return os.environ.get("HARNESS_PROVIDER", "codex").strip().lower() or "codex"


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
