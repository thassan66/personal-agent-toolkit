from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from personal_agent_toolkit.__main__ import create_provider
from personal_agent_toolkit.core.providers import AnthropicProvider
from personal_agent_toolkit.core.providers import EchoProvider, OpenAICompatibleProvider


class AnthropicProviderTests(unittest.TestCase):
    def test_build_payload_extracts_system_and_tool_results(self) -> None:
        provider = AnthropicProvider(api_key="test-key")
        payload = provider._build_payload(  # noqa: SLF001
            [
                {"role": "system", "content": "system one"},
                {"role": "user", "content": "hello"},
                {
                    "role": "assistant",
                    "content": "working",
                    "tool_calls": [
                        {"id": "call-1", "name": "list_dir", "arguments": {"path": "."}}
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call-1",
                    "name": "list_dir",
                    "content": "{\"ok\": true}",
                },
            ],
            model="claude-sonnet",
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "list_dir",
                        "description": "List files",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        )

        self.assertEqual(payload["system"], "system one")
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertEqual(payload["messages"][1]["role"], "assistant")
        self.assertEqual(payload["messages"][2]["role"], "user")
        self.assertEqual(payload["messages"][2]["content"][0]["type"], "tool_result")
        self.assertEqual(payload["tools"][0]["name"], "list_dir")

    def test_parse_response_extracts_text_and_tool_use(self) -> None:
        provider = AnthropicProvider(api_key="test-key")
        result = provider._parse_response(  # noqa: SLF001
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I will use a tool"},
                    {
                        "type": "tool_use",
                        "id": "call-2",
                        "name": "read_file",
                        "input": {"path": "README.md"},
                    },
                ],
            }
        )

        self.assertEqual(result.role, "assistant")
        self.assertEqual(result.content, "I will use a tool")
        self.assertEqual(result.tool_calls[0]["id"], "call-2")
        self.assertEqual(result.tool_calls[0]["name"], "read_file")


class CreateProviderTests(unittest.TestCase):
    def test_create_provider_uses_native_anthropic(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PERSONAL_AGENT_TOOLKIT_PROVIDER": "claude",
                "ANTHROPIC_API_KEY": "anthropic-test-key",
            },
            clear=True,
        ):
            provider = create_provider()

        self.assertIsInstance(provider, AnthropicProvider)
        self.assertEqual(provider.api_key, "anthropic-test-key")  # noqa: SLF001
        self.assertEqual(provider.base_url, "https://api.anthropic.com/v1")  # noqa: SLF001

    def test_create_provider_uses_openai_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PERSONAL_AGENT_TOOLKIT_PROVIDER": "openai",
                "OPENAI_API_KEY": "openai-test-key",
            },
            clear=True,
        ):
            provider = create_provider()

        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(provider.api_key, "openai-test-key")  # noqa: SLF001
        self.assertEqual(provider.base_url, "https://api.openai.com/v1")  # noqa: SLF001

    def test_create_provider_uses_gemini_alias_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PERSONAL_AGENT_TOOLKIT_PROVIDER": "gemini",
                "GEMINI_API_KEY": "gemini-test-key",
            },
            clear=True,
        ):
            provider = create_provider()

        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(provider.api_key, "gemini-test-key")  # noqa: SLF001
        self.assertEqual(
            provider.base_url,  # noqa: SLF001
            "https://generativelanguage.googleapis.com/v1beta/openai",
        )

    def test_create_provider_uses_ollama_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PERSONAL_AGENT_TOOLKIT_PROVIDER": "ollama",
            },
            clear=True,
        ):
            provider = create_provider()

        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(provider.api_key, "dummy")  # noqa: SLF001
        self.assertEqual(provider.base_url, "http://localhost:11434/v1")  # noqa: SLF001

    def test_create_provider_falls_back_to_echo(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            provider = create_provider()

        self.assertIsInstance(provider, EchoProvider)


if __name__ == "__main__":
    unittest.main()
