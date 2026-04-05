from __future__ import annotations
import os
import urllib.error
import unittest
from unittest.mock import AsyncMock, patch

from personal_agent_toolkit.__main__ import _resolve_local_profile_model, create_provider, main
from personal_agent_toolkit.core.providers import AnthropicProvider
from personal_agent_toolkit.core.providers import EchoProvider, OllamaProvider, OpenAICompatibleProvider


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

    def test_anthropic_http_401_is_translated(self) -> None:
        provider = AnthropicProvider(api_key="bad-key")
        error = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )

        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "ANTHROPIC_API_KEY"):
                provider._complete_sync([], model="claude-sonnet-4-5", tools=None)  # noqa: SLF001


class OpenAICompatibleProviderTests(unittest.TestCase):
    def test_openai_compatible_provider_streams_content_chunks(self) -> None:
        provider = OpenAICompatibleProvider(
            base_url="http://localhost:11434/v1",
            api_key="dummy",
            provider_label="ollama",
        )
        streamed: list[dict[str, str]] = []

        class FakeStreamingResponse:
            def __init__(self, lines: list[bytes]) -> None:
                self._lines = lines

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def __iter__(self):
                return iter(self._lines)

        response = FakeStreamingResponse(
            [
                b'data: {"choices":[{"delta":{"role":"assistant","content":"Hello"}}]}\n\n',
                b'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
                b"data: [DONE]\n\n",
            ]
        )

        with patch("urllib.request.urlopen", return_value=response):
            result = provider._complete_sync(  # noqa: SLF001
                [],
                model="qwen2.5-coder:3b",
                tools=None,
                stream_handler=streamed.append,
            )

        self.assertEqual(result.content, "Hello world")
        self.assertEqual(
            streamed,
            [
                {"kind": "content_delta", "text": "Hello"},
                {"kind": "content_delta", "text": " world"},
            ],
        )

    def test_ollama_http_404_is_translated(self) -> None:
        provider = OllamaProvider(
            base_url="http://localhost:11434",
            api_key="dummy",
        )
        error = urllib.error.HTTPError(
            url="http://localhost:11434/api/chat",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "ollama pull qwen2.5-coder:14b"):
                provider._complete_sync([], model="qwen2.5-coder:14b", tools=None)  # noqa: SLF001

    def test_ollama_url_error_is_translated(self) -> None:
        provider = OllamaProvider(
            base_url="http://localhost:11434",
            api_key="dummy",
        )

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
            with self.assertRaisesRegex(RuntimeError, "Could not reach Ollama"):
                provider._complete_sync([], model="qwen2.5-coder:14b", tools=None)  # noqa: SLF001

    def test_ollama_timeout_is_translated(self) -> None:
        provider = OllamaProvider(
            base_url="http://localhost:11434",
            api_key="dummy",
        )

        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaisesRegex(RuntimeError, "--timeout 300"):
                provider._complete_sync([], model="qwen2.5-coder:3b", tools=None)  # noqa: SLF001


class OllamaProviderTests(unittest.TestCase):
    def test_ollama_provider_streams_native_chat_chunks(self) -> None:
        provider = OllamaProvider(
            base_url="http://localhost:11434",
            api_key="dummy",
        )
        streamed: list[dict[str, str]] = []

        class FakeStreamingResponse:
            def __init__(self, lines: list[bytes]) -> None:
                self._lines = lines

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def __iter__(self):
                return iter(self._lines)

        response = FakeStreamingResponse(
            [
                b'{"model":"deepseek-r1:14b","message":{"role":"assistant","thinking":"plan","content":"Hello"},"done":false}\n',
                b'{"model":"deepseek-r1:14b","message":{"role":"assistant","content":" world"},"done":true}\n',
            ]
        )

        with patch("urllib.request.urlopen", return_value=response):
            result = provider._complete_sync(  # noqa: SLF001
                [],
                model="deepseek-r1:14b",
                tools=None,
                stream_handler=streamed.append,
            )

        self.assertEqual(result.content, "Hello world")
        self.assertEqual(
            streamed,
            [
                {"kind": "thinking_delta", "text": "plan"},
                {"kind": "content_delta", "text": "Hello"},
                {"kind": "content_delta", "text": " world"},
            ],
        )


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

        self.assertIsInstance(provider, OllamaProvider)
        self.assertEqual(provider.api_key, "dummy")  # noqa: SLF001
        self.assertEqual(provider.base_url, "http://localhost:11434")  # noqa: SLF001
        self.assertEqual(provider.timeout, 300.0)  # noqa: SLF001

    def test_create_provider_respects_env_timeout_for_ollama(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PERSONAL_AGENT_TOOLKIT_PROVIDER": "ollama",
                "PERSONAL_AGENT_TOOLKIT_TIMEOUT": "45",
            },
            clear=True,
        ):
            provider = create_provider()

        self.assertIsInstance(provider, OllamaProvider)
        self.assertEqual(provider.timeout, 45.0)  # noqa: SLF001

    def test_create_provider_respects_explicit_timeout_for_ollama(self) -> None:
        provider = create_provider(provider_name="ollama", timeout=90)

        self.assertIsInstance(provider, OllamaProvider)
        self.assertEqual(provider.timeout, 90)  # noqa: SLF001

    def test_create_provider_uses_lm_studio_defaults(self) -> None:
        provider = create_provider(provider_name="lm-studio")

        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(provider.api_key, "lm-studio")  # noqa: SLF001
        self.assertEqual(provider.base_url, "http://localhost:1234/v1")  # noqa: SLF001

    def test_create_provider_uses_llamacpp_alias_defaults(self) -> None:
        provider = create_provider(provider_name="llamacpp")

        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(provider.api_key, "dummy")  # noqa: SLF001
        self.assertEqual(provider.base_url, "http://localhost:8080/v1")  # noqa: SLF001

    def test_create_provider_falls_back_to_echo(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            provider = create_provider()

        self.assertIsInstance(provider, EchoProvider)


class LocalProfileResolutionTests(unittest.TestCase):
    def test_balanced_profile_prefers_installed_qwen_fallback(self) -> None:
        with patch(
            "personal_agent_toolkit.__main__._fetch_ollama_models",
            return_value={"qwen2.5-coder:3b", "qwen2.5-coder:1.5b"},
        ):
            model = _resolve_local_profile_model(
                "balanced",
                provider_name="ollama",
                base_url=None,
                timeout=None,
            )

        self.assertEqual(model, "qwen2.5-coder:3b")

    def test_reasoning_profile_prefers_installed_deepseek(self) -> None:
        with patch(
            "personal_agent_toolkit.__main__._fetch_ollama_models",
            return_value={"deepseek-r1:14b", "qwen2.5-coder:14b"},
        ):
            model = _resolve_local_profile_model(
                "reasoning",
                provider_name="ollama",
                base_url=None,
                timeout=None,
            )

        self.assertEqual(model, "deepseek-r1:14b")


class MainCliTests(unittest.TestCase):
    def test_main_uses_local_profile_defaults(self) -> None:
        with patch(
            "personal_agent_toolkit.__main__._fetch_ollama_models",
            return_value={"qwen2.5-coder:14b"},
        ), patch("personal_agent_toolkit.__main__.run_repl", new_callable=AsyncMock) as run_repl:
            main(["--cwd", ".", "--local-profile", "balanced"])

        kwargs = run_repl.call_args.kwargs
        self.assertEqual(kwargs["provider_name"], "ollama")
        self.assertEqual(kwargs["model"], "qwen2.5-coder:14b")

    def test_main_uses_installed_ollama_fallback_for_local_profile(self) -> None:
        with patch(
            "personal_agent_toolkit.__main__._fetch_ollama_models",
            return_value={"qwen2.5-coder:3b", "qwen2.5-coder:1.5b"},
        ), patch("personal_agent_toolkit.__main__.run_repl", new_callable=AsyncMock) as run_repl:
            main(["--cwd", ".", "--local-profile", "balanced"])

        kwargs = run_repl.call_args.kwargs
        self.assertEqual(kwargs["provider_name"], "ollama")
        self.assertEqual(kwargs["model"], "qwen2.5-coder:3b")

    def test_main_preserves_explicit_provider_with_local_profile(self) -> None:
        with patch("personal_agent_toolkit.__main__.run_repl", new_callable=AsyncMock) as run_repl:
            main(["--cwd", ".", "--provider", "lm-studio", "--local-profile", "agentic"])

        kwargs = run_repl.call_args.kwargs
        self.assertEqual(kwargs["provider_name"], "lm-studio")
        self.assertEqual(kwargs["model"], "devstral:24b")

    def test_main_passes_public_reasoning_flag(self) -> None:
        with patch("personal_agent_toolkit.__main__.run_repl", new_callable=AsyncMock) as run_repl:
            main(["--cwd", ".", "--public-reasoning"])

        kwargs = run_repl.call_args.kwargs
        self.assertTrue(kwargs["public_reasoning"])


if __name__ == "__main__":
    unittest.main()
