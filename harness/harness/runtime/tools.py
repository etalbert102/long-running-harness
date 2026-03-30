"""Local workspace tools exposed to API-backed agent runtimes."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ToolExecutionResult:
    """Result of running a local tool."""

    content: str
    is_error: bool = False


class WorkspaceTools:
    """Safe tool surface for API-driven agents."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def schemas(self) -> list[dict[str, Any]]:
        """Return OpenAI-compatible tool schemas."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files and directories under the workspace.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["path"],
                        "properties": {
                            "path": {"type": "string"},
                            "max_entries": {"type": "integer"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a UTF-8 text file in the workspace.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["path"],
                        "properties": {
                            "path": {"type": "string"},
                            "max_chars": {"type": "integer"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_text",
                    "description": "Search for text in workspace files using a regex pattern. Falls back to literal substring match if the pattern is not valid regex.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["pattern"],
                        "properties": {
                            "pattern": {"type": "string"},
                            "path": {"type": ["string", "null"]},
                            "max_matches": {"type": "integer"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Run a non-destructive shell command inside the workspace.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["command"],
                        "properties": {
                            "command": {"type": "string"},
                            "timeout_ms": {"type": "integer"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "apply_patch",
                    "description": "Apply a unified git patch within the workspace.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["patch"],
                        "properties": {
                            "patch": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_git_diff",
                    "description": "Return git diff output from the workspace repository.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [],
                        "properties": {
                            "revspec": {"type": ["string", "null"]},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_json_artifact",
                    "description": "Write a JSON artifact to a file in the workspace.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["path", "json_text"],
                        "properties": {
                            "path": {"type": "string"},
                            "json_text": {"type": "string"},
                        },
                    },
                },
            },
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        """Dispatch a tool call by name."""
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return ToolExecutionResult(content=f"Unknown tool: {name}", is_error=True)
        try:
            return handler(arguments)
        except Exception as exc:  # pragma: no cover - defensive path
            return ToolExecutionResult(content=f"{name} failed: {exc}", is_error=True)

    def _tool_list_files(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        path = self._resolve_path(arguments.get("path", "."))
        max_entries = int(arguments.get("max_entries", 200))
        if not path.exists():
            return ToolExecutionResult(content=f"Path does not exist: {path}", is_error=True)
        entries: list[str] = []
        for index, entry in enumerate(sorted(path.iterdir(), key=lambda item: item.name.lower())):
            if index >= max_entries:
                entries.append("... truncated ...")
                break
            rel = entry.relative_to(self.workspace_root)
            suffix = "/" if entry.is_dir() else ""
            entries.append(f"{rel.as_posix()}{suffix}")
        return ToolExecutionResult(content="\n".join(entries) or "(empty)")

    def _tool_read_file(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        path = self._resolve_path(arguments["path"])
        max_chars = int(arguments.get("max_chars", 20000))
        if not path.exists():
            return ToolExecutionResult(content=f"File does not exist: {path}", is_error=True)
        if path.is_dir():
            return ToolExecutionResult(content=f"Path is a directory: {path}", is_error=True)
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = f"{text[:max_chars]}\n... truncated ..."
        return ToolExecutionResult(content=text)

    def _tool_search_text(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        pattern = arguments["pattern"]
        search_root = self._resolve_path(arguments.get("path", "."))
        max_matches = int(arguments.get("max_matches", 200))

        # Compile as regex; fall back to literal substring match if invalid
        try:
            compiled = re.compile(pattern)
            def line_matches(line: str) -> bool:
                return compiled.search(line) is not None
        except re.error:
            def line_matches(line: str) -> bool:  # type: ignore[misc]
                return pattern in line

        matches: list[str] = []
        for path in search_root.rglob("*"):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                if line_matches(line):
                    rel = path.relative_to(self.workspace_root)
                    matches.append(f"{rel.as_posix()}:{line_no}:{line.strip()}")
                    if len(matches) >= max_matches:
                        matches.append("... truncated ...")
                        return ToolExecutionResult(content="\n".join(matches))
        return ToolExecutionResult(content="\n".join(matches) or "(no matches)")

    def _tool_run_command(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        command = arguments["command"]
        timeout_ms = int(arguments.get("timeout_ms", 120000))
        blocked_tokens = (
            "rm ",
            "rmdir ",
            "del ",
            "format ",
            "shutdown ",
            "reboot ",
            "mkfs",
            "git reset --hard",
            "git clean -fd",
        )
        lowered = command.lower()
        if any(token in lowered for token in blocked_tokens):
            return ToolExecutionResult(content=f"Blocked command: {command}", is_error=True)

        completed = subprocess.run(
            command,
            cwd=str(self.workspace_root),
            shell=True,
            capture_output=True,
            timeout=timeout_ms / 1000,
            env=os.environ.copy(),
        )
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        content = (
            f"exit_code={completed.returncode}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )
        return ToolExecutionResult(content=content, is_error=completed.returncode != 0)

    def _tool_apply_patch(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        patch = arguments["patch"]
        completed = subprocess.run(
            ["git", "apply", "--recount", "--whitespace=nowarn", "-"],
            cwd=str(self.workspace_root),
            input=patch.encode("utf-8"),
            capture_output=True,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace")
            stdout = completed.stdout.decode("utf-8", errors="replace")
            return ToolExecutionResult(
                content=stderr or stdout or "git apply failed",
                is_error=True,
            )
        return ToolExecutionResult(content="Patch applied successfully.")

    def _tool_get_git_diff(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        revspec = arguments.get("revspec")
        command = ["git", "diff"]
        if revspec:
            command.append(str(revspec))
        completed = subprocess.run(
            command,
            cwd=str(self.workspace_root),
            capture_output=True,
        )
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        if completed.returncode != 0:
            return ToolExecutionResult(content=stderr or stdout or "git diff failed", is_error=True)
        return ToolExecutionResult(content=stdout or "(no diff)")

    def _tool_write_json_artifact(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        path = self._resolve_path(arguments["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            parsed = json.loads(arguments["json_text"])
        except json.JSONDecodeError as exc:
            return ToolExecutionResult(content=f"Invalid JSON text: {exc}", is_error=True)
        path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        return ToolExecutionResult(content=f"Wrote {path.relative_to(self.workspace_root).as_posix()}")

    def _resolve_path(self, raw_path: str) -> Path:
        candidate = (self.workspace_root / raw_path).resolve()
        if candidate != self.workspace_root and self.workspace_root not in candidate.parents:
            raise ValueError(f"Path escapes workspace: {raw_path}")
        return candidate
