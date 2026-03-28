"""Planner agent decomposes app_spec.md into feature_list.json."""

import logging
from pathlib import Path

from harness.backend import run_agent
from harness.client import get_output_dir
from harness.io_utils import read_text_file

logger = logging.getLogger("harness.planner")

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "planner.md"


async def run_planner(app_spec_path: Path) -> bool:
    """Run the planner agent to create feature_list.json."""
    logger.info("[planner] Starting planner agent")

    system_prompt = read_text_file(PROMPT_PATH)
    app_spec = read_text_file(app_spec_path)

    output_dir = get_output_dir()
    (output_dir / "app_spec.md").write_text(app_spec)

    prompt = (
        "Here is the product specification. Decompose it into a comprehensive "
        f"feature list with BDD scenarios.\n\n---\n\n{app_spec}"
    )

    result = run_agent(
        role="planner",
        system_prompt=system_prompt,
        prompt=prompt,
        cwd=output_dir,
    )
    if result.error:
        logger.error(f"[planner] Session failed: {result.error}")
        return False

    logger.info(
        f"[planner] Session complete: cost=${result.cost_usd:.4f}, turns={result.num_turns}"
    )

    feature_list = output_dir / "feature_list.json"
    if feature_list.exists():
        logger.info(f"[planner] Created feature_list.json ({feature_list.stat().st_size} bytes)")
        return True

    logger.error("[planner] feature_list.json was not created")
    return False
