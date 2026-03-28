"""OpenAI-compatible chat-completions transport."""

from __future__ import annotations

import json
from typing import Any

import httpx

from harness.transports.base import ModelResponse, ToolCall, TransportError


class OpenAICompatibleTransport:
    """Transport for arbitrary OpenAI-compatible chat-completions endpoints."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        headers: dict[str, str] | None = None,
        timeout_s: float = 180.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = headers or {}
        self.timeout_s = timeout_s

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        output_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Execute a chat completion request."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if output_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "harness_output_schema",
                    "strict": True,
                    "schema": output_schema,
                },
            }

        request_headers = {
            "Content-Type": "application/json",
            **self.headers,
        }
        if self.api_key:
            request_headers["Authorization"] = f"Bearer {self.api_key}"

        response = self._post_json("/chat/completions", payload, request_headers)
        if response.status_code >= 400 and output_schema is not None:
            body_text = response.text
            if "response_format" in body_text or "json_schema" in body_text:
                payload.pop("response_format", None)
                schema_instruction = (
                    "Return a single JSON object that matches the requested schema exactly. "
                    "Do not wrap it in markdown."
                )
                fallback_messages = list(messages)
                fallback_messages.append(
                    {"role": "system", "content": schema_instruction},
                )
                payload["messages"] = fallback_messages
                response = self._post_json("/chat/completions", payload, request_headers)

        data = self._decode_or_raise(response)
        choices = data.get("choices", [])
        if not choices:
            raise TransportError("OpenAI-compatible endpoint returned no choices")

        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") in {"text", "output_text"}
            )

        tool_calls: list[ToolCall] = []
        for tool_call in message.get("tool_calls", []) or []:
            function = tool_call.get("function", {})
            arguments_raw = function.get("arguments", "{}")
            try:
                arguments = json.loads(arguments_raw)
            except json.JSONDecodeError as exc:
                raise TransportError(
                    f"Tool call arguments for {function.get('name', '<unknown>')} were not valid JSON: {exc}"
                ) from exc
            tool_calls.append(
                ToolCall(
                    id=tool_call.get("id", ""),
                    name=function.get("name", ""),
                    arguments=arguments,
                )
            )

        return ModelResponse(
            content=content or "",
            tool_calls=tool_calls,
            raw=data,
            usage=data.get("usage"),
            finish_reason=choices[0].get("finish_reason"),
        )

    def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
        with httpx.Client(timeout=self.timeout_s) as client:
            return client.post(f"{self.base_url}{path}", json=payload, headers=headers)

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
