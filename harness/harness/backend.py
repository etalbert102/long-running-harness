"""Provider-neutral agent execution backend."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from harness.client import (
    get_api_base_url,
    get_api_headers,
    get_api_key,
    get_anthropic_api_key,
    get_anthropic_base_url,
    get_anthropic_version,
    get_claude_code_oauth_token,
    get_output_dir,
    get_provider,
)
from harness.model_policy import select_model
from harness.runtime import AgentRuntime, RuntimeConfig, MAX_TURNS_BY_COMPLEXITY
from harness.transports import AnthropicTransport, OpenAICompatibleTransport, TransportError

logger = logging.getLogger("harness.backend")


@dataclass
class AgentRunResult:
    output_text: str
    cost_usd: float = 0.0
    num_turns: int = 0
    error: str | None = None


def run_agent(
    *,
    role: str,
    system_prompt: str,
    prompt: str,
    model_override: str | None = None,
    output_schema: dict | None = None,
    cwd: Path | None = None,
    complexity: str | None = None,
    retry_count: int = 0,
    project_type: str | None = None,
) -> AgentRunResult:
    """Execute a single agent run using the configured backend."""
    provider = get_provider()
    target_dir = cwd or get_output_dir()
    selection = select_model(
        role=role,
        complexity=complexity,
        retry_count=retry_count,
        structured_output=output_schema is not None,
        project_type=project_type,
    )
    model = model_override or selection.model
    selection_reason = "explicit override" if model_override else selection.reason

    if provider == "codex":
        return _run_with_codex_cli(
            role=role,
            target_dir=target_dir,
            model=model,
            selection_reason=selection_reason,
            system_prompt=system_prompt,
            prompt=prompt,
            output_schema=output_schema,
        )

    if provider == "openai-compatible":
        return _run_with_openai_compatible_api(
            role=role,
            target_dir=target_dir,
            model=model,
            selection_reason=selection_reason,
            system_prompt=system_prompt,
            prompt=prompt,
            output_schema=output_schema,
            complexity=complexity,
        )

    if provider == "anthropic":
        return _run_with_anthropic_api(
            role=role,
            target_dir=target_dir,
            model=model,
            selection_reason=selection_reason,
            system_prompt=system_prompt,
            prompt=prompt,
            output_schema=output_schema,
            complexity=complexity,
        )

    return AgentRunResult(
        output_text="",
        error=(
            f"Unsupported HARNESS_PROVIDER '{provider}'. "
            "Supported: codex, openai-compatible, anthropic"
        ),
    )


def _run_with_codex_cli(
    *,
    role: str,
    target_dir: Path,
    model: str,
    selection_reason: str,
    system_prompt: str,
    prompt: str,
    output_schema: dict | None,
) -> AgentRunResult:
    full_prompt = _compose_prompt(role, system_prompt, prompt)

    with tempfile.TemporaryDirectory(prefix="harness-codex-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        output_file = temp_dir / "last-message.txt"
        try:
            codex_executable = _resolve_codex_executable()
        except FileNotFoundError as exc:
            logger.error("[backend] %s failed to start: %s", role, exc)
            return AgentRunResult(output_text="", error=str(exc))

        command = [
            codex_executable,
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
            schema_file.write_text(_json_dumps(output_schema), encoding="utf-8")
            command.extend(["--output-schema", str(schema_file)])

        logger.info(
            "[backend] Running %s via codex in %s with model %s (%s)",
            role,
            target_dir,
            model,
            selection_reason,
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


def _run_with_openai_compatible_api(
    *,
    role: str,
    target_dir: Path,
    model: str,
    selection_reason: str,
    system_prompt: str,
    prompt: str,
    output_schema: dict | None,
    complexity: str | None = None,
) -> AgentRunResult:
    base_url = get_api_base_url()
    if not base_url:
        return AgentRunResult(
            output_text="",
            error=(
                "HARNESS_API_BASE_URL is required for provider 'openai-compatible'."
            ),
        )

    logger.info(
        "[backend] Running %s via openai-compatible API in %s with model %s (%s)",
        role,
        target_dir,
        model,
        selection_reason,
    )

    transport = OpenAICompatibleTransport(
        base_url=base_url,
        api_key=get_api_key() or None,
        headers=get_api_headers(),
    )
    max_turns = MAX_TURNS_BY_COMPLEXITY.get(complexity or "", RuntimeConfig.max_turns)
    runtime = AgentRuntime(
        transport=transport,
        workspace_root=target_dir,
        config=RuntimeConfig(max_turns=max_turns),
    )

    try:
        response = runtime.run(
            model=model,
            role=role,
            system_prompt=system_prompt,
            prompt=prompt,
            output_schema=output_schema,
        )
    except TransportError as exc:
        logger.error("[backend] %s failed: %s", role, exc)
        return AgentRunResult(output_text="", error=str(exc))
    except Exception as exc:  # pragma: no cover - defensive path
        logger.error("[backend] %s failed to start: %s", role, exc)
        return AgentRunResult(output_text="", error=str(exc))

    return AgentRunResult(output_text=response.content)


def _run_with_anthropic_api(
    *,
    role: str,
    target_dir: Path,
    model: str,
    selection_reason: str,
    system_prompt: str,
    prompt: str,
    output_schema: dict | None,
    complexity: str | None = None,
) -> AgentRunResult:
    api_key = get_anthropic_api_key()
    auth_token = ""
    auth_source = "api-key"
    if not api_key:
        auth_token = get_claude_code_oauth_token()
        auth_source = "claude-code-oauth"
    if not api_key and not auth_token:
        return AgentRunResult(
            output_text="",
            error=(
                "HARNESS_ANTHROPIC_API_KEY/HARNESS_API_KEY is required for provider 'anthropic', "
                "or a local Claude Code OAuth token must exist in ~/.claude/.credentials.json."
            ),
        )

    logger.info(
        "[backend] Running %s via anthropic API in %s with model %s (%s, auth=%s)",
        role,
        target_dir,
        model,
        selection_reason,
        auth_source,
    )

    transport = AnthropicTransport(
        api_key=api_key or None,
        auth_token=auth_token or None,
        base_url=get_anthropic_base_url(),
        headers=get_api_headers(),
        anthropic_version=get_anthropic_version(),
    )
    max_turns = MAX_TURNS_BY_COMPLEXITY.get(complexity or "", RuntimeConfig.max_turns)
    runtime = AgentRuntime(
        transport=transport,
        workspace_root=target_dir,
        config=RuntimeConfig(max_turns=max_turns),
    )

    try:
        response = runtime.run(
            model=model,
            role=role,
            system_prompt=system_prompt,
            prompt=prompt,
            output_schema=output_schema,
        )
    except TransportError as exc:
        logger.error("[backend] %s failed: %s", role, exc)
        return AgentRunResult(output_text="", error=str(exc))
    except Exception as exc:  # pragma: no cover - defensive path
        logger.error("[backend] %s failed to start: %s", role, exc)
        return AgentRunResult(output_text="", error=str(exc))

    return AgentRunResult(output_text=response.content)


def _compose_prompt(role: str, system_prompt: str, prompt: str) -> str:
    return (
        f"You are the harness {role} agent.\n\n"
        f"Follow the system instructions exactly.\n\n"
        f"<SYSTEM_PROMPT>\n{system_prompt}\n</SYSTEM_PROMPT>\n\n"
        f"<USER_PROMPT>\n{prompt}\n</USER_PROMPT>\n"
    )


def _resolve_codex_executable() -> str:
    """Resolve the Codex CLI executable reliably on Windows."""
    configured = os.environ.get("CODEX_EXECUTABLE", "").strip()
    if configured:
        return configured

    resolved = shutil.which("codex")
    if resolved:
        return resolved

    raise FileNotFoundError(
        "Could not find 'codex' on PATH. Set CODEX_EXECUTABLE or add Codex CLI to PATH."
    )


def _json_dumps(data: dict) -> str:
    import json

    return json.dumps(data, indent=2)
