from __future__ import annotations

import asyncio
import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional, Protocol

Message = dict[str, Any]
ToolSpec = dict[str, Any]


@dataclass
class CompletionResponse:
    role: str
    content: str
    tool_calls: list[dict[str, Any]]


class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: Optional[list[ToolSpec]] = None,
    ) -> CompletionResponse: ...


class EchoProvider:
    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: Optional[list[ToolSpec]] = None,
    ) -> CompletionResponse:
        user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        text = (user or {}).get("content", "")
        return CompletionResponse(role="assistant", content=f"[{model}] {text}", tool_calls=[])


class OpenAICompatibleProvider:
    def __init__(self, *, base_url: str, api_key: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: Optional[list[ToolSpec]] = None,
    ) -> CompletionResponse:
        return await asyncio.to_thread(self._complete_sync, messages, model, tools)

    def _complete_sync(
        self,
        messages: list[Message],
        model: str,
        tools: Optional[list[ToolSpec]],
    ) -> CompletionResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        req = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))

        message = data["choices"][0]["message"]
        content = message.get("content") or ""
        raw_tool_calls = message.get("tool_calls") or []
        tool_calls = []
        for call in raw_tool_calls:
            function = call.get("function") or {}
            arguments = function.get("arguments") or "{}"
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            tool_calls.append(
                {
                    "id": call.get("id") or function.get("name", "tool_call"),
                    "name": function.get("name", "unknown_tool"),
                    "arguments": arguments,
                }
            )
        return CompletionResponse(
            role=message.get("role", "assistant"),
            content=content,
            tool_calls=tool_calls,
        )


class AnthropicProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.anthropic.com/v1",
        timeout: float = 120.0,
        anthropic_version: str = "2023-06-01",
        max_tokens: int = 4096,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.anthropic_version = anthropic_version
        self.max_tokens = max_tokens

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: Optional[list[ToolSpec]] = None,
    ) -> CompletionResponse:
        return await asyncio.to_thread(self._complete_sync, messages, model, tools)

    def _complete_sync(
        self,
        messages: list[Message],
        model: str,
        tools: Optional[list[ToolSpec]],
    ) -> CompletionResponse:
        payload = self._build_payload(messages, model=model, tools=tools)
        req = urllib.request.Request(
            url=f"{self.base_url}/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": self.anthropic_version,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        return self._parse_response(data)

    def _build_payload(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: Optional[list[ToolSpec]],
    ) -> dict[str, Any]:
        system_parts: list[str] = []
        anthropic_messages: list[dict[str, Any]] = []
        pending_tool_results: list[dict[str, Any]] = []

        for message in messages:
            role = message.get("role")
            if role == "system":
                content = str(message.get("content", "")).strip()
                if content:
                    system_parts.append(content)
                continue

            if role == "tool":
                pending_tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": message.get("tool_call_id", message.get("name", "tool_call")),
                        "content": str(message.get("content", "")),
                    }
                )
                continue

            if pending_tool_results:
                anthropic_messages.append({"role": "user", "content": pending_tool_results})
                pending_tool_results = []

            if role == "assistant":
                content_blocks: list[dict[str, Any]] = []
                text_content = str(message.get("content", ""))
                if text_content:
                    content_blocks.append({"type": "text", "text": text_content})
                for call in message.get("tool_calls", []) or []:
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": call.get("id", call.get("name", "tool_call")),
                            "name": call.get("name", "unknown_tool"),
                            "input": call.get("arguments", {}),
                        }
                    )
                anthropic_messages.append(
                    {
                        "role": "assistant",
                        "content": content_blocks or [{"type": "text", "text": ""}],
                    }
                )
                continue

            anthropic_messages.append(
                {
                    "role": "user",
                    "content": str(message.get("content", "")),
                }
            )

        if pending_tool_results:
            anthropic_messages.append({"role": "user", "content": pending_tool_results})

        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": self.max_tokens,
            "messages": anthropic_messages,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if tools:
            payload["tools"] = self._normalize_tools(tools)
        return payload

    def _normalize_tools(self, tools: list[ToolSpec]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for tool in tools:
            if "function" in tool:
                fn = tool["function"]
                normalized.append(
                    {
                        "name": fn["name"],
                        "description": fn.get("description", ""),
                        "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                    }
                )
            else:
                normalized.append(
                    {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "input_schema": tool.get("input_schema", {"type": "object", "properties": {}}),
                    }
                )
        return normalized

    def _parse_response(self, payload: dict[str, Any]) -> CompletionResponse:
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in payload.get("content", []) or []:
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.get("id", block.get("name", "tool_call")),
                        "name": block.get("name", "unknown_tool"),
                        "arguments": block.get("input", {}),
                    }
                )
        return CompletionResponse(
            role=payload.get("role", "assistant"),
            content="\n".join(part for part in text_parts if part),
            tool_calls=tool_calls,
        )
