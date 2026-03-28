"""Generator agent builds one feature per session."""

import logging
from pathlib import Path

from harness.backend import run_agent
from harness.client import get_output_dir
from harness.io_utils import read_text_file
from harness.progress import format_progress_header, read_progress

logger = logging.getLogger("harness.generator")

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "generator.md"


async def run_generator(feature: dict, evaluator_feedback: str | None = None) -> dict:
    """Run the generator agent to implement a single feature."""
    feature_id = feature.get("id", "unknown")
    description = feature.get("description", "no description")
    steps = feature.get("steps", [])

    logger.info(f"[generator] Starting feature {feature_id}: {description}")

    system_prompt = read_text_file(PROMPT_PATH)
    progress = read_progress()
    progress_header = format_progress_header(progress) if progress else "No progress file yet.\n"
    steps_text = "\n".join(f"  - {s}" for s in steps) if steps else "  (no BDD steps defined)"

    prompt_parts = [
        progress_header,
        "\n## Your Assignment\n\n",
        f"Implement feature **{feature_id}**: {description}\n\n",
        f"### BDD Scenario\n{steps_text}\n\n",
    ]

    if evaluator_feedback:
        prompt_parts.append(
            "### Previous Evaluator Feedback (you must address these issues)\n\n"
            f"{evaluator_feedback}\n\n"
            "Fix the issues identified above and ensure the feature passes evaluation.\n"
        )

    prompt_parts.append(
        "Implement this feature, write tests, verify everything passes, "
        "commit your changes, and update feature_list.json."
    )
    prompt = "".join(prompt_parts)

    result = run_agent(
        role="generator",
        system_prompt=system_prompt,
        prompt=prompt,
        cwd=get_output_dir(),
    )

    if result.error:
        logger.error(f"[generator] Feature {feature_id} failed: {result.error}")
    else:
        logger.info(
            f"[generator] Feature {feature_id} session complete: cost=${result.cost_usd:.4f}, turns={result.num_turns}"
        )

    updated_progress = read_progress()
    success = False
    if updated_progress:
        for item in updated_progress.items:
            if item.get("id") == feature_id and item.get("passes", False):
                success = True
                break

    return {
        "success": success,
        "cost_usd": result.cost_usd,
        "error": result.error,
    }
