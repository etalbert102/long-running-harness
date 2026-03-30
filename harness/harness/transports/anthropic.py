"""Native Anthropic Messages API transport."""

from __future__ import annotations

import json
from typing import Any

import httpx

from harness.transports.base import ModelResponse, ToolCall, TransportError


class AnthropicTransport:
    """Transport for Anthropic's Messages API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth_token: str | None = None,
        base_url: str = "https://api.anthropic.com",
        headers: dict[str, str] | None = None,
        timeout_s: float = 180.0,
        anthropic_version: str = "2023-06-01",
    ) -> None:
        self.api_key = api_key
        self.auth_token = auth_token
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout_s = timeout_s
        self.anthropic_version = anthropic_version

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        output_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Execute a Messages API request."""
        system, anthropic_messages = self._convert_messages(messages, output_schema=output_schema)

        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": anthropic_messages,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [self._convert_tool(tool) for tool in tools]

        headers = {
            "anthropic-version": self.anthropic_version,
            "content-type": "application/json",
            **self.headers,
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        elif self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        else:
            raise TransportError("Anthropic transport requires either an API key or an auth token")

        with httpx.Client(timeout=self.timeout_s) as client:
            response = client.post(f"{self.base_url}/v1/messages", json=payload, headers=headers)

        data = self._decode_or_raise(response)
        content_blocks = data.get("content", [])

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in content_blocks:
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input", {}) or {},
                    )
                )

        return ModelResponse(
            content="".join(text_parts).strip(),
            tool_calls=tool_calls,
            raw=data,
            usage=data.get("usage"),
            finish_reason=data.get("stop_reason"),
        )

    def _convert_messages(
        self,
        messages: list[dict[str, Any]],
        *,
        output_schema: dict[str, Any] | None,
    ) -> tuple[str, list[dict[str, Any]]]:
        system_parts: list[str] = []
        converted: list[dict[str, Any]] = []

        if output_schema is not None:
            schema_text = json.dumps(output_schema, indent=2)
            system_parts.append(
                "Your final response must be a single JSON object matching this schema exactly:\n"
                f"{schema_text}"
            )

        for message in messages:
            role = message.get("role")
            if role == "system":
                content = message.get("content", "")
                if content:
                    system_parts.append(str(content))
                continue

            if role == "user":
                converted.append(
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": str(message.get("content", ""))}],
                    }
                )
                continue

            if role == "assistant":
                content_blocks: list[dict[str, Any]] = []
                text = message.get("content", "")
                if text:
                    content_blocks.append({"type": "text", "text": str(text)})
                for tool_call in message.get("tool_calls", []) or []:
                    function = tool_call.get("function", {})
                    arguments_raw = function.get("arguments", "{}")
                    try:
                        arguments = json.loads(arguments_raw)
                    except json.JSONDecodeError:
                        arguments = {}
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tool_call.get("id", ""),
                            "name": function.get("name", ""),
                            "input": arguments,
                        }
                    )
                converted.append({"role": "assistant", "content": content_blocks})
                continue

            if role == "tool":
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message.get("tool_call_id", ""),
                                "content": str(message.get("content", "")),
                            }
                        ],
                    }
                )

        return "\n\n".join(part for part in system_parts if part), converted

    def _convert_tool(self, tool: dict[str, Any]) -> dict[str, Any]:
        function = tool.get("function", {})
        return {
            "name": function.get("name", ""),
            "description": function.get("description", ""),
            "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
        }

    def _decode_or_raise(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            raise TransportError(str(payload))
        try:
            return response.json()
        except ValueError as exc:
            raise TransportError(f"Endpoint did not return JSON: {response.text[:1000]}") from exc
