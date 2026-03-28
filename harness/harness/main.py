"""Entry point for the agent-id harness."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from harness.multi_orchestrator import run_multi_orchestrator
from harness.orchestrator import run_orchestrator


def setup_logging(verbose: bool = False, log_file: str | None = None) -> None:
    """Configure structured logging to stderr and optionally to a file."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]

    if log_file:
        file_handler = logging.FileHandler(log_file, mode="a")
        file_handler.setFormatter(logging.Formatter(fmt))
        handlers.append(file_handler)

    logging.basicConfig(level=level, format=fmt, handlers=handlers)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Agent-ID Harness — Autonomous coding orchestrator",
    )
    parser.add_argument(
        "spec",
        type=Path,
        help="Path to the app_spec.md file",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Skip architect agent — run as single service (bypass monorepo detection)",
    )
    parser.add_argument(
        "--dashboard-url",
        type=str,
        default="",
        help="URL of the monitoring dashboard (e.g., https://agent-id.vercel.app)",
    )
    parser.add_argument(
        "--dashboard-secret",
        type=str,
        default="",
        help="Bearer token for dashboard ingest endpoint",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="codex",
        help="Agent backend provider: codex or openai-compatible (default: codex)",
    )
    parser.add_argument(
        "--model-policy",
        type=str,
        choices=("static", "dynamic", "cheap", "quality"),
        default=None,
        help="Dynamic model routing policy",
    )
    parser.add_argument(
        "--api-base-url",
        type=str,
        default=None,
        help="Base URL for an OpenAI-compatible API backend",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key for an OpenAI-compatible API backend",
    )
    parser.add_argument(
        "--api-header",
        action="append",
        default=None,
        help="Extra API header in Name=Value form; repeatable",
    )
    parser.add_argument(
        "--project-type",
        type=str,
        choices=("python", "node"),
        default=None,
        help="Force validator/tooling profile for generated project",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5.3-codex",
        help="Default model for all agent roles (default: gpt-5.3-codex)",
    )
    parser.add_argument(
        "--model-planner",
        type=str,
        default=None,
        help="Model for planner agent (overrides --model)",
    )
    parser.add_argument(
        "--model-generator",
        type=str,
        default=None,
        help="Model for generator agent (overrides --model)",
    )
    parser.add_argument(
        "--model-generator-cheap",
        type=str,
        default=None,
        help="Cheap/default model for setup and simple generator tasks",
    )
    parser.add_argument(
        "--model-generator-strong",
        type=str,
        default=None,
        help="Escalation model for moderate/complex or retrying generator tasks",
    )
    parser.add_argument(
        "--model-evaluator",
        type=str,
        default=None,
        help="Model for evaluator agent (overrides --model). Use opus for production runs.",
    )
    parser.add_argument(
        "--model-evaluator-strong",
        type=str,
        default=None,
        help="Escalation model for evaluator retries and structured-output reliability",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to log file (in addition to stderr). Default: harness-{timestamp}.log",
    )
    parser.add_argument(
        "--multi",
        action="store_true",
        help="Use architect-driven multi-service orchestration",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Default log file if not specified
    import os
    from datetime import datetime
    log_file = args.log_file
    if log_file is None:
        log_dir = Path(__file__).resolve().parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = str(log_dir / f"harness-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log")

    setup_logging(args.verbose, log_file=log_file)

    logger = logging.getLogger("harness.main")

    # Validate spec file exists
    if not args.spec.exists():
        logger.error(f"Spec file not found: {args.spec}")
        sys.exit(1)

    # Set environment for dashboard integration
    if args.dashboard_url:
        os.environ["DASHBOARD_URL"] = args.dashboard_url
    if args.dashboard_secret:
        os.environ["DASHBOARD_SECRET"] = args.dashboard_secret
    if args.provider:
        os.environ["HARNESS_PROVIDER"] = args.provider
    if args.model_policy:
        os.environ["HARNESS_MODEL_POLICY"] = args.model_policy
    if args.api_base_url:
        os.environ["HARNESS_API_BASE_URL"] = args.api_base_url
    if args.api_key:
        os.environ["HARNESS_API_KEY"] = args.api_key
    if args.api_header:
        import json

        headers: dict[str, str] = {}
        for item in args.api_header:
            if "=" not in item:
                logger.error(f"Invalid --api-header value (expected Name=Value): {item}")
                sys.exit(1)
            name, value = item.split("=", 1)
            headers[name.strip()] = value.strip()
        os.environ["HARNESS_API_HEADERS"] = json.dumps(headers)
    if args.project_type:
        os.environ["HARNESS_PROJECT_TYPE"] = args.project_type
    if args.model:
        os.environ["HARNESS_MODEL"] = args.model
    if args.model_planner:
        os.environ["HARNESS_MODEL_PLANNER"] = args.model_planner
    if args.model_generator:
        os.environ["HARNESS_MODEL_GENERATOR"] = args.model_generator
    if args.model_generator_cheap:
        os.environ["HARNESS_MODEL_GENERATOR_CHEAP"] = args.model_generator_cheap
    if args.model_generator_strong:
        os.environ["HARNESS_MODEL_GENERATOR_STRONG"] = args.model_generator_strong
    if args.model_evaluator:
        os.environ["HARNESS_MODEL_EVALUATOR"] = args.model_evaluator
    if args.model_evaluator_strong:
        os.environ["HARNESS_MODEL_EVALUATOR_STRONG"] = args.model_evaluator_strong

    from harness.client import get_api_base_url, get_model_for_role, get_policy_mode
    use_multi = args.multi and not args.single
    mode = "single" if args.single else "multi (architect-driven)" if use_multi else "single"
    logger.info(f"Starting harness with spec: {args.spec}")
    logger.info(f"Mode: {mode}")
    logger.info(f"Provider: {os.environ['HARNESS_PROVIDER']}")
    logger.info(f"Model policy: {get_policy_mode()}")
    if get_api_base_url():
        logger.info(f"API base URL: {get_api_base_url()}")
    if args.project_type:
        logger.info(f"Project type override: {args.project_type}")
    logger.info(f"Models — planner: {get_model_for_role('planner')}, generator: {get_model_for_role('generator')}, evaluator: {get_model_for_role('evaluator')}")
    logger.info(f"Log file: {log_file}")
    if args.dashboard_url:
        logger.info(f"Dashboard: {args.dashboard_url}")

    if args.single:
        asyncio.run(run_orchestrator(args.spec.resolve()))
    elif use_multi:
        asyncio.run(run_multi_orchestrator(args.spec.resolve()))
    else:
        asyncio.run(run_orchestrator(args.spec.resolve()))


if __name__ == "__main__":
    main()
