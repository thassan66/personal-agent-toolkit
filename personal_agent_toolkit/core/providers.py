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
