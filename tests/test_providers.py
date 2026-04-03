from __future__ import annotations

import unittest

from personal_agent_toolkit.core.providers import AnthropicProvider


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


if __name__ == "__main__":
    unittest.main()
