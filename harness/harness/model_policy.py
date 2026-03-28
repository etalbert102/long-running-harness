"""Rule-based model selection for harness agents."""

from __future__ import annotations

from dataclasses import dataclass

from harness.client import (
    get_model_for_role,
    get_policy_mode,
    get_project_type_override,
)


@dataclass
class ModelSelection:
    """Selected model plus an explanation for logging."""

    model: str
    reason: str


def select_model(
    *,
    role: str,
    complexity: str | None = None,
    retry_count: int = 0,
    structured_output: bool = False,
    project_type: str | None = None,
) -> ModelSelection:
    """Choose a model for an agent task."""
    project = project_type or get_project_type_override() or "unknown"
    policy_mode = get_policy_mode()

    if policy_mode == "static":
        model = get_model_for_role(role)
        return ModelSelection(
            model=model,
            reason=f"policy=static role={role}",
        )

    effective_complexity = (complexity or "moderate").lower()
    base_model = get_model_for_role(role)

    if role in {"planner", "architect"}:
        return ModelSelection(
            model=base_model,
            reason=f"policy={policy_mode} role={role} reasoning-default",
        )

    if role == "evaluator":
        if structured_output or retry_count > 0:
            model = _env_or_default("HARNESS_MODEL_EVALUATOR_STRONG", base_model)
            return ModelSelection(
                model=model,
                reason=(
                    f"policy={policy_mode} role=evaluator structured_output={structured_output} "
                    f"retry_count={retry_count}"
                ),
            )
        return ModelSelection(
            model=base_model,
            reason=f"policy={policy_mode} role=evaluator default",
        )

    if role == "generator":
        cheap = _env_or_default("HARNESS_MODEL_GENERATOR_CHEAP", base_model)
        strong = _env_or_default("HARNESS_MODEL_GENERATOR_STRONG", base_model)

        if policy_mode == "cheap":
            return ModelSelection(
                model=cheap,
                reason=f"policy=cheap role=generator complexity={effective_complexity}",
            )
        if policy_mode == "quality":
            return ModelSelection(
                model=strong,
                reason=f"policy=quality role=generator complexity={effective_complexity}",
            )

        if retry_count >= 2:
            return ModelSelection(
                model=strong,
                reason=(
                    f"policy={policy_mode} role=generator retry-escalation "
                    f"complexity={effective_complexity} retry_count={retry_count}"
                ),
            )
        if retry_count == 1 and effective_complexity in {"moderate", "complex"}:
            return ModelSelection(
                model=strong,
                reason=(
                    f"policy={policy_mode} role=generator retry-escalation "
                    f"complexity={effective_complexity} retry_count={retry_count}"
                ),
            )
        if effective_complexity in {"setup", "simple"}:
            return ModelSelection(
                model=cheap,
                reason=(
                    f"policy={policy_mode} role=generator low-complexity "
                    f"complexity={effective_complexity} project_type={project}"
                ),
            )
        if effective_complexity == "complex":
            return ModelSelection(
                model=strong,
                reason=(
                    f"policy={policy_mode} role=generator high-complexity "
                    f"complexity={effective_complexity} project_type={project}"
                ),
            )
        return ModelSelection(
            model=base_model,
            reason=(
                f"policy={policy_mode} role=generator default "
                f"complexity={effective_complexity} project_type={project}"
            ),
        )

    return ModelSelection(
        model=base_model,
        reason=f"policy={policy_mode} role={role} fallback",
    )


def _env_or_default(env_key: str, fallback: str) -> str:
    import os

    return os.environ.get(env_key, "").strip() or fallback
