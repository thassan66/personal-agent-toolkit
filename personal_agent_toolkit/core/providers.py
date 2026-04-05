from __future__ import annotations

import asyncio
import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol

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
        stream_handler: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> CompletionResponse: ...


class EchoProvider:
    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: Optional[list[ToolSpec]] = None,
        stream_handler: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> CompletionResponse:
        user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        text = (user or {}).get("content", "")
        return CompletionResponse(role="assistant", content=f"[{model}] {text}", tool_calls=[])


def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
    if exc.fp is None:
        return ""
    try:
        body = exc.read()
    except Exception:  # pragma: no cover
        return ""
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace").strip()
    return str(body).strip()


def _format_http_error(prefix: str, exc: urllib.error.HTTPError, guidance: str) -> RuntimeError:
    detail = _read_http_error_body(exc)
    message = f"{prefix} ({exc.code} {exc.reason}). {guidance}"
    if detail:
        message += f" Response: {detail}"
    return RuntimeError(message)


def _normalize_ollama_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized[:-3]
    return normalized


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 120.0,
        provider_label: str = "openai-compatible",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.provider_label = provider_label

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: Optional[list[ToolSpec]] = None,
        stream_handler: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> CompletionResponse:
        return await asyncio.to_thread(self._complete_sync, messages, model, tools, stream_handler)

    def _complete_sync(
        self,
        messages: list[Message],
        model: str,
        tools: Optional[list[ToolSpec]],
        stream_handler: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> CompletionResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if stream_handler is not None:
            payload["stream"] = True

        req = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                if stream_handler is not None:
                    return self._consume_streaming_response(resp, stream_handler)
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise self._translate_http_error(exc, model=model) from exc
        except urllib.error.URLError as exc:
            raise self._translate_url_error(exc, model=model) from exc
        except TimeoutError as exc:
            raise self._translate_timeout_error(model=model) from exc
        except socket.timeout as exc:
            raise self._translate_timeout_error(model=model) from exc

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

    def _consume_streaming_response(
        self,
        resp: Any,
        stream_handler: Callable[[dict[str, Any]], None],
    ) -> CompletionResponse:
        role = "assistant"
        content_parts: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}

        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            payload = json.loads(data_str)
            choices = payload.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            if delta.get("role"):
                role = str(delta["role"])

            for key in ("thinking", "reasoning", "reasoning_content"):
                thinking_chunk = delta.get(key)
                if thinking_chunk:
                    stream_handler({"kind": "thinking_delta", "text": str(thinking_chunk)})

            content_chunk = delta.get("content")
            if content_chunk:
                text = str(content_chunk)
                content_parts.append(text)
                stream_handler({"kind": "content_delta", "text": text})

            for tool_call in delta.get("tool_calls") or []:
                index = int(tool_call.get("index", 0))
                entry = tool_calls.setdefault(
                    index,
                    {
                        "id": tool_call.get("id"),
                        "name": "",
                        "arguments": "",
                    },
                )
                if tool_call.get("id"):
                    entry["id"] = tool_call["id"]
                function = tool_call.get("function") or {}
                if function.get("name"):
                    entry["name"] += str(function["name"])
                if function.get("arguments"):
                    entry["arguments"] += str(function["arguments"])

        final_tool_calls: list[dict[str, Any]] = []
        for index in sorted(tool_calls):
            call = tool_calls[index]
            arguments = call["arguments"] or "{}"
            parsed_arguments: Any
            try:
                parsed_arguments = json.loads(arguments)
            except json.JSONDecodeError:
                parsed_arguments = {}
            final_tool_calls.append(
                {
                    "id": call["id"] or call["name"] or f"tool_call_{index}",
                    "name": call["name"] or "unknown_tool",
                    "arguments": parsed_arguments,
                }
            )

        return CompletionResponse(
            role=role,
            content="".join(content_parts),
            tool_calls=final_tool_calls,
        )

    def _translate_http_error(self, exc: urllib.error.HTTPError, *, model: str) -> RuntimeError:
        provider = self.provider_label
        if provider == "ollama" and exc.code == 404:
            return _format_http_error(
                "Ollama request failed",
                exc,
                f"Start Ollama, confirm the server is reachable at {self.base_url}, and pull the model with `ollama pull {model}`.",
            )
        if provider in {"openai", "gemini"} and exc.code == 401:
            env_var = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
            return _format_http_error(
                f"{provider} authentication failed",
                exc,
                f"Set {env_var} or PERSONAL_AGENT_TOOLKIT_API_KEY to a valid key.",
            )
        if exc.code == 401:
            return _format_http_error(
                f"{provider} authentication failed",
                exc,
                "Set PERSONAL_AGENT_TOOLKIT_API_KEY to a valid key.",
            )
        if exc.code == 404:
            return _format_http_error(
                f"{provider} request failed",
                exc,
                f"Check the base URL ({self.base_url}) and confirm the model `{model}` exists on that server.",
            )
        return _format_http_error(
            f"{provider} request failed",
            exc,
            "Check your provider credentials, base URL, and model name.",
        )

    def _translate_url_error(self, exc: urllib.error.URLError, *, model: str) -> RuntimeError:
        provider = self.provider_label
        if provider == "ollama":
            return RuntimeError(
                f"Could not reach Ollama at {self.base_url}. Start Ollama and confirm the model `{model}` is installed."
            )
        return RuntimeError(
            f"Could not reach {provider} at {self.base_url}. Check your network connection and provider base URL."
        )

    def _translate_timeout_error(self, *, model: str) -> RuntimeError:
        provider = self.provider_label
        if provider == "ollama":
            return RuntimeError(
                f"Ollama timed out while generating with `{model}`. The model is likely still loading or generating. "
                "Retry with a longer timeout such as `--timeout 300`, or use a smaller/faster model."
            )
        return RuntimeError(
            f"{provider} timed out while waiting for a response. Retry with a longer `--timeout` value."
        )


class OllamaProvider:
    def __init__(self, *, base_url: str, api_key: str, timeout: float = 300.0) -> None:
        self.base_url = _normalize_ollama_base_url(base_url)
        self.api_key = api_key
        self.timeout = timeout
        self.provider_label = "ollama"

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: Optional[list[ToolSpec]] = None,
        stream_handler: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> CompletionResponse:
        return await asyncio.to_thread(self._complete_sync, messages, model, tools, stream_handler)

    def _complete_sync(
        self,
        messages: list[Message],
        model: str,
        tools: Optional[list[ToolSpec]],
        stream_handler: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> CompletionResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": self._normalize_messages(messages),
            "stream": bool(stream_handler),
        }
        if tools:
            payload["tools"] = tools

        req = urllib.request.Request(
            url=f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                if stream_handler is not None:
                    return self._consume_streaming_response(resp, stream_handler)
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise self._translate_http_error(exc, model=model) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {self.base_url}. Start Ollama and confirm the model `{model}` is installed."
            ) from exc
        except TimeoutError as exc:
            raise RuntimeError(
                f"Ollama timed out while generating with `{model}`. The model is likely still loading or generating. "
                "Retry with a longer timeout such as `--timeout 300`, or use a smaller/faster model."
            ) from exc
        except socket.timeout as exc:
            raise RuntimeError(
                f"Ollama timed out while generating with `{model}`. The model is likely still loading or generating. "
                "Retry with a longer timeout such as `--timeout 300`, or use a smaller/faster model."
            ) from exc
        return self._parse_response(data)

    def _normalize_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role", "user"))
            entry: dict[str, Any] = {"role": role}
            if role == "assistant":
                entry["content"] = str(message.get("content", ""))
                tool_calls = []
                for call in message.get("tool_calls", []) or []:
                    tool_calls.append(
                        {
                            "function": {
                                "name": call.get("name", "unknown_tool"),
                                "arguments": call.get("arguments", {}),
                            }
                        }
                    )
                if tool_calls:
                    entry["tool_calls"] = tool_calls
                normalized.append(entry)
                continue
            if role == "tool":
                entry["content"] = str(message.get("content", ""))
                normalized.append(entry)
                continue
            entry["content"] = str(message.get("content", ""))
            normalized.append(entry)
        return normalized

    def _consume_streaming_response(
        self,
        resp: Any,
        stream_handler: Callable[[dict[str, Any]], None],
    ) -> CompletionResponse:
        role = "assistant"
        content_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            payload = json.loads(line)
            message = payload.get("message") or {}
            if message.get("role"):
                role = str(message["role"])
            thinking = message.get("thinking")
            if thinking:
                stream_handler({"kind": "thinking_delta", "text": str(thinking)})
            content = message.get("content")
            if content:
                text = str(content)
                content_parts.append(text)
                stream_handler({"kind": "content_delta", "text": text})
            chunk_tool_calls = self._parse_tool_calls(message.get("tool_calls") or [])
            if chunk_tool_calls:
                tool_calls.extend(chunk_tool_calls)
            if payload.get("done"):
                break

        return CompletionResponse(
            role=role,
            content="".join(content_parts),
            tool_calls=tool_calls,
        )

    def _parse_response(self, payload: dict[str, Any]) -> CompletionResponse:
        message = payload.get("message") or {}
        return CompletionResponse(
            role=str(message.get("role", "assistant")),
            content=str(message.get("content", "")),
            tool_calls=self._parse_tool_calls(message.get("tool_calls") or []),
        )

    def _parse_tool_calls(self, raw_tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        for index, call in enumerate(raw_tool_calls):
            function = call.get("function") or {}
            parsed.append(
                {
                    "id": function.get("name", f"tool_call_{index}"),
                    "name": function.get("name", "unknown_tool"),
                    "arguments": function.get("arguments", {}),
                }
            )
        return parsed

    def _translate_http_error(self, exc: urllib.error.HTTPError, *, model: str) -> RuntimeError:
        if exc.code == 404:
            return _format_http_error(
                "Ollama request failed",
                exc,
                f"Start Ollama, confirm the server is reachable at {self.base_url}, and pull the model with `ollama pull {model}`.",
            )
        return _format_http_error(
            "Ollama request failed",
            exc,
            "Check your Ollama server, model name, and request options.",
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
        stream_handler: Optional[Callable[[dict[str, Any]], None]] = None,
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
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise self._translate_http_error(exc) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach Anthropic at {self.base_url}. Check your network connection and base URL."
            ) from exc
        except TimeoutError as exc:
            raise RuntimeError(
                "Anthropic timed out while waiting for a response. Retry with a longer `--timeout` value."
            ) from exc
        except socket.timeout as exc:
            raise RuntimeError(
                "Anthropic timed out while waiting for a response. Retry with a longer `--timeout` value."
            ) from exc
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

    def _translate_http_error(self, exc: urllib.error.HTTPError) -> RuntimeError:
        if exc.code == 401:
            return _format_http_error(
                "Anthropic authentication failed",
                exc,
                "Set ANTHROPIC_API_KEY or PERSONAL_AGENT_TOOLKIT_API_KEY to a valid key.",
            )
        return _format_http_error(
            "Anthropic request failed",
            exc,
            "Check your API key, base URL, and model name.",
        )
