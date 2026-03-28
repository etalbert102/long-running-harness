"""Provider-neutral agent execution backend."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from harness.client import get_model_for_role, get_output_dir, get_provider

logger = logging.getLogger("harness.backend")


@dataclass
class AgentRunResult:
    output_text: str
    cost_usd: float = 0.0
    num_turns: int = 0
    error: str | None = None


def _compose_prompt(role: str, system_prompt: str, prompt: str) -> str:
    return (
        f"You are the harness {role} agent.\n\n"
        f"Follow the system instructions exactly.\n\n"
        f"<SYSTEM_PROMPT>\n{system_prompt}\n</SYSTEM_PROMPT>\n\n"
        f"<USER_PROMPT>\n{prompt}\n</USER_PROMPT>\n"
    )


def run_agent(
    *,
    role: str,
    system_prompt: str,
    prompt: str,
    model_override: str | None = None,
    output_schema: dict | None = None,
    cwd: Path | None = None,
) -> AgentRunResult:
    """Execute a single agent run using the configured backend."""
    provider = get_provider()
    if provider != "codex":
        return AgentRunResult(
            output_text="",
            error=f"Unsupported HARNESS_PROVIDER '{provider}'. Supported: codex",
        )

    target_dir = cwd or get_output_dir()
    model = model_override or get_model_for_role(role)
    full_prompt = _compose_prompt(role, system_prompt, prompt)

    with tempfile.TemporaryDirectory(prefix="harness-codex-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        output_file = temp_dir / "last-message.txt"
        command = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--full-auto",
            "--sandbox",
            "workspace-write",
            "--cd",
            str(target_dir),
            "--model",
            model,
            "--output-last-message",
            str(output_file),
            "-",
        ]

        if output_schema is not None:
            schema_file = temp_dir / "output-schema.json"
            schema_file.write_text(json.dumps(output_schema, indent=2), encoding="utf-8")
            command.extend(["--output-schema", str(schema_file)])

        logger.info(
            "[backend] Running %s via codex in %s with model %s",
            role,
            target_dir,
            model,
        )

        try:
            completed = subprocess.run(
                command,
                input=full_prompt.encode("utf-8", errors="replace"),
                capture_output=True,
                cwd=str(target_dir),
                env=os.environ.copy(),
                timeout=1800,
            )
        except Exception as exc:
            logger.error("[backend] %s failed to start: %s", role, exc)
            return AgentRunResult(output_text="", error=str(exc))

        output_text = ""
        if output_file.exists():
            output_text = output_file.read_text(encoding="utf-8", errors="replace").strip()

        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            stdout = completed.stdout.decode("utf-8", errors="replace").strip()
            error = stderr or stdout or f"codex exited with code {completed.returncode}"
            logger.error("[backend] %s failed: %s", role, error)
            return AgentRunResult(output_text=output_text, error=error)

        return AgentRunResult(output_text=output_text)
