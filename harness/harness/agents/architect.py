"""Architect agent analyzes the spec and determines project structure."""

import json
import logging
from pathlib import Path

from harness.backend import run_agent
from harness.client import get_output_dir
from harness.io_utils import read_text_file

logger = logging.getLogger("harness.architect")

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "architect.md"


async def run_architect(app_spec_path: Path) -> dict | None:
    """Run the architect agent to determine project structure."""
    logger.info("[architect] Starting architect agent")

    system_prompt = read_text_file(PROMPT_PATH)
    app_spec = read_text_file(app_spec_path)

    output_dir = get_output_dir()
    (output_dir / "app_spec.md").write_text(app_spec)

    prompt = (
        "Analyze this product specification and determine the optimal project structure.\n\n"
        f"---\n\n{app_spec}"
    )

    result = run_agent(
        role="planner",
        system_prompt=system_prompt,
        prompt=prompt,
        cwd=output_dir,
        complexity="complex",
    )
    if result.error:
        logger.error(f"[architect] Session failed: {result.error}")
        return None

    logger.info(
        f"[architect] Session complete: cost=${result.cost_usd:.4f}, turns={result.num_turns}"
    )

    services_path = output_dir / "services.json"
    if not services_path.exists():
        logger.error("[architect] services.json was not created")
        return None

    try:
        services = json.loads(read_text_file(services_path))
        arch = services.get("architecture", "unknown")
        num_services = len(services.get("services", []))
        num_phases = len(services.get("execution_order", []))
        logger.info(
            f"[architect] Architecture: {arch}, "
            f"{num_services} services, {num_phases} execution phases"
        )
        return services
    except json.JSONDecodeError as exc:
        logger.error(f"[architect] Failed to parse services.json: {exc}")
        return None


def is_multi_service(services: dict) -> bool:
    """Check if the architect determined a multi-service architecture."""
    return services.get("architecture") in ("workspace", "monorepo")


def get_parallel_groups(services: dict) -> list[list[dict]]:
    """Group services by parallel execution phase."""
    execution_order = services.get("execution_order", [])
    service_map = {service["name"]: service for service in services.get("services", [])}

    groups = []
    for phase in sorted(execution_order, key=lambda item: item.get("phase", 0)):
        group = []
        for name in phase.get("services", []):
            if name in service_map:
                group.append(service_map[name])
        if group:
            groups.append(group)

    return groups


def get_service_spec(services: dict, service: dict, app_spec: str) -> str:
    """Generate a focused spec for a single service."""
    contracts = services.get("shared_contracts", [])
    relevant_contracts = [
        contract for contract in contracts if service["name"] in contract.get("consumed_by", [])
    ]

    contract_section = ""
    if relevant_contracts:
        contract_names = ", ".join(contract["name"] for contract in relevant_contracts)
        contract_section = (
            "\n\n## Shared Contracts\n\n"
            f"This service depends on these shared type definitions: {contract_names}\n"
            "These are defined in the workspace and available as imports.\n"
        )

    return (
        f"# Service: {service['name']}\n\n"
        f"**Type:** {service['type']}\n"
        f"**Description:** {service['description']}\n"
        f"**Entrypoint:** {service['entrypoint']}\n"
        f"**Dependencies:** {', '.join(service.get('dependencies', [])) or 'None'}\n"
        f"**Estimated complexity:** {service.get('estimated_complexity', 'medium')}\n"
        f"{contract_section}\n"
        "---\n\n"
        "## Full Product Specification (for reference)\n\n"
        f"{app_spec}\n\n"
        "---\n\n"
        f"**IMPORTANT:** You are only building the `{service['name']}` service. "
        "Do not implement other services. Focus exclusively on the functionality "
        "described for this service in the spec above.\n"
    )
