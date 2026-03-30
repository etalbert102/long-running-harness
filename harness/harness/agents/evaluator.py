"""Evaluator agent acts as an adversarial reviewer with graded rubrics."""

import json
import logging
from pathlib import Path

from harness.backend import run_agent
from harness.client import get_output_dir
from harness.io_utils import read_text_file

logger = logging.getLogger("harness.evaluator")

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "evaluator.md"

MIN_PASSING_SCORE = 7.0

WEIGHTS = {
    "specCompliance": 0.35,
    "codeQuality": 0.25,
    "security": 0.25,
    "usability": 0.15,
}

EVALUATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "featureId",
        "overallScore",
        "dimensionScores",
        "passed",
        "issues",
        "recommendations",
    ],
    "properties": {
        "featureId": {"type": "string"},
        "overallScore": {"type": "number"},
        "passed": {"type": "boolean"},
        "dimensionScores": {
            "type": "object",
            "additionalProperties": False,
            "required": ["specCompliance", "codeQuality", "security", "usability"],
            "properties": {
                "specCompliance": {"type": "number"},
                "codeQuality": {"type": "number"},
                "security": {"type": "number"},
                "usability": {"type": "number"},
            },
        },
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "severity",
                    "dimension",
                    "description",
                    "file",
                    "line",
                    "suggestion",
                ],
                "additionalProperties": False,
                "properties": {
                    "severity": {"type": "string"},
                    "dimension": {"type": "string"},
                    "description": {"type": "string"},
                    "file": {"type": ["string", "null"]},
                    "line": {"type": ["number", "null"]},
                    "suggestion": {"type": ["string", "null"]},
                },
            },
        },
        "recommendations": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}


def _parse_evaluation(text: str) -> dict | None:
    """Extract the JSON evaluation from the evaluator response.

    Handles both raw JSON and responses where the model wraps output in
    markdown code fences (```json ... ``` or ``` ... ```).
    """
    # Try raw parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences and retry
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # Drop opening fence (```json or ```)
        start = 1
        # Drop closing fence if present
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        stripped = "\n".join(lines[start:end]).strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    return None


def _compute_weighted_score(dimension_scores: dict[str, float]) -> float:
    """Compute the weighted overall score from dimension scores."""
    total = 0.0
    for dim, weight in WEIGHTS.items():
        total += dimension_scores.get(dim, 0.0) * weight
    return round(total, 2)


async def run_evaluator(
    feature: dict,
    *,
    retry_count: int = 0,
    project_type: str | None = None,
) -> dict:
    """Run the evaluator agent to review a feature implementation."""
    feature_id = feature.get("id", "unknown")
    description = feature.get("description", "no description")
    steps = feature.get("steps", [])
    complexity = feature.get("complexity", "moderate")

    logger.info(
        f"[evaluator] Evaluating feature {feature_id}: {description} "
        f"(complexity={complexity}, retry_count={retry_count})"
    )

    system_prompt = read_text_file(PROMPT_PATH)
    steps_text = "\n".join(f"  - {step}" for step in steps) if steps else "  (no BDD steps defined)"

    prompt = (
        f"Evaluate the implementation of feature **{feature_id}**: {description}\n\n"
        f"### BDD Scenario\n{steps_text}\n\n"
        "Review the code in the current directory. The feature was just implemented. "
        "Use `git diff HEAD~1` to see what changed. Run tests, check types, and "
        "score the implementation using your rubric.\n\n"
        "Return your evaluation as a JSON object."
    )

    result = run_agent(
        role="evaluator",
        system_prompt=system_prompt,
        prompt=prompt,
        cwd=get_output_dir(),
        output_schema=EVALUATION_SCHEMA,
        complexity=complexity,
        retry_count=retry_count,
        project_type=project_type,
    )

    if result.error:
        logger.error(f"[evaluator] Feature {feature_id} evaluation failed: {result.error}")
        return {
            "score": 0.0,
            "passed": False,
            "feedback": f"Evaluator crashed: {result.error}",
            "dimensionScores": {key: 0.0 for key in WEIGHTS},
            "issues": [],
            "recommendations": [],
            "cost_usd": result.cost_usd,
        }

    logger.info(
        f"[evaluator] Feature {feature_id} evaluation complete: cost=${result.cost_usd:.4f}, turns={result.num_turns}"
    )

    evaluation = _parse_evaluation(result.output_text)
    if evaluation is None:
        logger.warning("[evaluator] Could not parse evaluation JSON from response")
        return {
            "score": 0.0,
            "passed": False,
            "feedback": f"Could not parse evaluator response. Raw text:\n{result.output_text[:1000]}",
            "dimensionScores": {key: 0.0 for key in WEIGHTS},
            "issues": [],
            "recommendations": [],
            "cost_usd": result.cost_usd,
        }

    dimension_scores = evaluation.get("dimensionScores", {})
    overall_score = _compute_weighted_score(dimension_scores)
    issues = evaluation.get("issues", [])

    has_critical_security = any(
        issue.get("severity") == "high" and issue.get("dimension") == "security"
        for issue in issues
    )
    passed = overall_score >= MIN_PASSING_SCORE and not has_critical_security

    feedback_parts = [f"Score: {overall_score}/10 ({'PASS' if passed else 'FAIL'})"]
    feedback_parts.append(f"Spec Compliance: {dimension_scores.get('specCompliance', 0)}/10")
    feedback_parts.append(f"Code Quality: {dimension_scores.get('codeQuality', 0)}/10")
    feedback_parts.append(f"Security: {dimension_scores.get('security', 0)}/10")
    feedback_parts.append(f"Usability: {dimension_scores.get('usability', 0)}/10")

    if issues:
        feedback_parts.append("\nIssues:")
        for issue in issues:
            severity = issue.get("severity", "unknown")
            description = issue.get("description", "no description")
            file_path = issue.get("file", "")
            line = issue.get("line", "")
            location = f" ({file_path}:{line})" if file_path else ""
            feedback_parts.append(f"  [{severity}]{location} {description}")

    recommendations = evaluation.get("recommendations", [])
    if recommendations:
        feedback_parts.append("\nRecommendations:")
        for recommendation in recommendations:
            feedback_parts.append(f"  - {recommendation}")

    feedback = "\n".join(feedback_parts)

    logger.info(f"[evaluator] Feature {feature_id}: score={overall_score}, passed={passed}")

    return {
        "score": overall_score,
        "passed": passed,
        "feedback": feedback,
        "dimensionScores": dimension_scores,
        "issues": issues,
        "recommendations": recommendations,
        "cost_usd": result.cost_usd,
    }
