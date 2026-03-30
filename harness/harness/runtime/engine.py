"""Agent runtime that pairs model transports with local workspace tools."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness.runtime.tools import WorkspaceTools
from harness.transports.base import ModelResponse, TransportError

logger = logging.getLogger("harness.runtime")


MAX_TURNS_BY_COMPLEXITY: dict[str, int] = {
    "setup": 8,
    "simple": 12,
    "moderate": 20,
    "complex": 24,
}


@dataclass
class RuntimeConfig:
    """Runtime settings for an agent execution."""

    max_turns: int = 24
    temperature: float = 0.0


class AgentRuntime:
    """A local tool-using runtime for API-backed models."""

    def __init__(
        self,
        *,
        transport: Any,
        workspace_root: Path,
        config: RuntimeConfig | None = None,
    ) -> None:
        self.transport = transport
        self.workspace_root = workspace_root
        self.config = config or RuntimeConfig()
        self.tools = WorkspaceTools(workspace_root)

    def run(
        self,
        *,
        model: str,
        role: str,
        system_prompt: str,
        prompt: str,
        output_schema: dict[str, Any] | None = None,
    ) -> ModelResponse:
        """Run the agent loop until final content is produced."""
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": self._build_runtime_system_prompt(role, system_prompt, output_schema),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]

        last_response: ModelResponse | None = None
        for turn in range(1, self.config.max_turns + 1):
            logger.debug("[runtime] Turn %s for %s using model %s", turn, role, model)
            response = self.transport.complete(
                model=model,
                messages=messages,
                tools=self.tools.schemas(),
                output_schema=output_schema,
                temperature=self.config.temperature,
            )
            last_response = response

            if response.tool_calls:
                assistant_message: dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.name,
                                "arguments": json.dumps(tool_call.arguments),
                            },
                        }
                        for tool_call in response.tool_calls
                    ],
                }
                messages.append(assistant_message)

                for tool_call in response.tool_calls:
                    tool_result = self.tools.execute(tool_call.name, tool_call.arguments)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result.content,
                        }
                    )
                continue

            if response.content:
                return response

        raise TransportError(
            f"Agent runtime exceeded max turns ({self.config.max_turns}) without producing final content"
        )

    def _build_runtime_system_prompt(
        self,
        role: str,
        system_prompt: str,
        output_schema: dict[str, Any] | None,
    ) -> str:
        tool_guidance = (
            "You are running inside the harness API runtime with local tools.\n"
            "Use tools to inspect files, search text, run non-destructive commands, apply patches, "
            "read git diffs, and write JSON artifacts.\n"
            "Prefer reading only the files you need. Keep command usage targeted.\n"
            "If you modify code, use the apply_patch tool or write_json_artifact for JSON outputs.\n"
            "If you are asked to produce a file artifact such as feature_list.json or services.json, "
            "you must write it into the workspace before finishing.\n"
        )
        schema_guidance = ""
        if output_schema is not None:
            schema_guidance = (
                "Your final response must be a single JSON object that matches the requested schema exactly.\n"
            )
        return (
            f"You are the harness {role} agent.\n\n"
            f"{tool_guidance}"
            f"{schema_guidance}\n"
            f"<SYSTEM_PROMPT>\n{system_prompt}\n</SYSTEM_PROMPT>\n"
        )
