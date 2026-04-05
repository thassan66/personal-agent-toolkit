from __future__ import annotations

import asyncio
import io
import signal
import unittest
from pathlib import Path
from unittest.mock import patch

from personal_agent_toolkit.__main__ import (
    _build_prompt,
    _build_prompt_with_context,
    _render_repl_welcome,
    create_engine,
    run_repl,
)
from personal_agent_toolkit.core.agents import AgentRegistry
from personal_agent_toolkit.core.builtin_commands import register_builtin_commands
from personal_agent_toolkit.core.builtin_tools import register_builtin_tools
from personal_agent_toolkit.core.commands import CommandRegistry
from personal_agent_toolkit.core.mcp import LocalMcpRegistry
from personal_agent_toolkit.core.plugins import PluginManager
from personal_agent_toolkit.core.providers import CompletionResponse
from personal_agent_toolkit.core.query_engine import QueryEngine
from personal_agent_toolkit.core.skills import SkillRegistry
from personal_agent_toolkit.core.tasks import TaskManager
from personal_agent_toolkit.core.tools import ToolRegistry

REPO_ROOT = Path(__file__).resolve().parents[1]


class ScriptedProvider:
    def __init__(self, responses: list[CompletionResponse]) -> None:
        self._responses = list(responses)

    async def complete(self, messages, *, model, tools=None, stream_handler=None):  # noqa: ANN001
        return self._responses.pop(0)


class SlowProvider:
    def __init__(self, delay_seconds: float, response: CompletionResponse) -> None:
        self.delay_seconds = delay_seconds
        self.response = response

    async def complete(self, messages, *, model, tools=None, stream_handler=None):  # noqa: ANN001
        await asyncio.sleep(self.delay_seconds)
        return self.response


class NoToolsProvider:
    def __init__(self, response: CompletionResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def complete(self, messages, *, model, tools=None, stream_handler=None):  # noqa: ANN001
        self.calls.append({"model": model, "tools": tools})
        if tools:
            raise RuntimeError("model does not support tools")
        return self.response


class NoToolsSlowProvider:
    def __init__(self, delay_seconds: float, response: CompletionResponse) -> None:
        self.delay_seconds = delay_seconds
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def complete(self, messages, *, model, tools=None, stream_handler=None):  # noqa: ANN001
        self.calls.append({"model": model, "tools": tools})
        if tools:
            raise RuntimeError("model does not support tools")
        await asyncio.sleep(self.delay_seconds)
        return self.response


class InterruptingProvider:
    def __init__(self, trigger_interrupt) -> None:  # noqa: ANN001
        self.trigger_interrupt = trigger_interrupt

    async def complete(self, messages, *, model, tools=None, stream_handler=None):  # noqa: ANN001
        await asyncio.sleep(0.01)
        self.trigger_interrupt()
        await asyncio.sleep(1)
        return CompletionResponse(role="assistant", content="done", tool_calls=[])


class CliRenderingTests(unittest.TestCase):
    def test_render_repl_welcome_includes_context_and_tips(self) -> None:
        engine = create_engine(workspace=REPO_ROOT, model="echo-local", provider_name="echo")

        welcome = _render_repl_welcome(
            engine=engine,
            provider_label="echo",
            workspace=REPO_ROOT,
            color_enabled=False,
        )

        self.assertIn("Personal Agent Toolkit", welcome)
        self.assertIn("Session", welcome)
        self.assertIn("Workspace", welcome)
        self.assertIn(REPO_ROOT.name, welcome)
        self.assertIn("Reasoning", welcome)
        self.assertIn("/help", welcome)
        self.assertIn("/agents", welcome)
        self.assertIn("Mock mode is active", welcome)

    def test_build_prompt_uses_agent_name(self) -> None:
        self.assertEqual(_build_prompt("coder", color_enabled=False), "[coder] > ")

    def test_build_prompt_with_context_uses_model_and_reasoning(self) -> None:
        self.assertEqual(
            _build_prompt_with_context(
                agent_name="planner",
                model="deepseek-r1:14b",
                public_reasoning=True,
                color_enabled=False,
            ),
            "[planner|deepseek-r1:14b+r] > ",
        )

    def test_help_command_groups_commands(self) -> None:
        engine = create_engine(workspace=REPO_ROOT)
        result = asyncio.run(engine.submit("/help"))

        self.assertIn("Slash command guide", result)
        self.assertIn("Quick start", result)
        self.assertIn("/agents", result)
        self.assertIn("Planning and memory", result)

    def test_help_command_can_show_one_command(self) -> None:
        engine = create_engine(workspace=REPO_ROOT)
        result = asyncio.run(engine.submit("/help model"))

        self.assertIn("/model", result)
        self.assertIn("usage: /model [name]", result)
        self.assertIn("example: /model", result)

    def test_status_command_returns_session_snapshot(self) -> None:
        engine = create_engine(workspace=REPO_ROOT, public_reasoning=True)
        result = asyncio.run(engine.submit("/status"))

        self.assertIn("Session status", result)
        self.assertIn("provider:", result)
        self.assertIn("model:", result)
        self.assertIn("agent:", result)
        self.assertIn("reasoning: public", result)

    def test_public_reasoning_adds_system_instruction(self) -> None:
        engine = create_engine(workspace=REPO_ROOT, public_reasoning=True)

        system_messages = engine._system_messages()  # noqa: SLF001

        self.assertTrue(
            any("Reasoning summary:" in message["content"] for message in system_messages)
        )

    def test_agent_switch_preserves_current_model_when_persona_has_no_model(self) -> None:
        engine = create_engine(workspace=REPO_ROOT)
        asyncio.run(engine.submit("/model custom-model"))

        result = asyncio.run(engine.submit("/agent planner"))

        self.assertEqual(result, "active agent set to planner (model=custom-model)")
        self.assertEqual(engine.model, "custom-model")


class CliInteractionTests(unittest.TestCase):
    def test_run_repl_shows_welcome_and_prompt(self) -> None:
        stdout = io.StringIO()
        prompts: list[str] = []

        def fake_input(prompt: str = "") -> str:
            prompts.append(prompt)
            return "/quit"

        with patch("sys.stdout", stdout), patch(
            "builtins.input",
            side_effect=fake_input,
        ):
            asyncio.run(
                run_repl(
                    workspace=REPO_ROOT,
                    provider_name="echo",
                    model="echo-local",
                )
            )

        output = stdout.getvalue()
        self.assertIn("Personal Agent Toolkit", output)
        self.assertIn("Try this first", output)
        self.assertEqual(prompts, ["[coder|echo-local] > "])

    def test_run_repl_clear_command_rerenders_welcome(self) -> None:
        stdout = io.StringIO()
        prompts = iter(["/clear", "/quit"])

        with patch("sys.stdout", stdout), patch(
            "builtins.input",
            side_effect=lambda prompt="": next(prompts),
        ):
            asyncio.run(
                run_repl(
                    workspace=REPO_ROOT,
                    provider_name="echo",
                    model="echo-local",
                )
            )

        output = stdout.getvalue()
        self.assertGreaterEqual(output.count("Personal Agent Toolkit"), 2)

    def test_run_repl_ctrl_c_cancels_active_request_and_keeps_session_open(self) -> None:
        stdout = io.StringIO()
        prompts = iter(["long request", "/quit"])
        installed_handler = None

        def fake_getsignal(sig):  # noqa: ANN001
            return signal.default_int_handler

        def fake_signal(sig, handler):  # noqa: ANN001
            nonlocal installed_handler
            installed_handler = handler
            return signal.default_int_handler

        provider = InterruptingProvider(lambda: installed_handler(signal.SIGINT, None))
        tools = ToolRegistry()
        register_builtin_tools(tools)
        commands = CommandRegistry()
        register_builtin_commands(commands)
        plugins = PluginManager.from_directory(REPO_ROOT / "plugins")
        plugins.register(tools, commands)
        engine = QueryEngine(
            cwd=REPO_ROOT,
            provider=provider,
            model="test-model",
            tools=tools,
            tasks=TaskManager(),
            commands=commands,
            agents=AgentRegistry.from_directory(REPO_ROOT / "personal_agent_toolkit" / "agents"),
            plugins=plugins,
            mcp=LocalMcpRegistry.from_directory(REPO_ROOT, REPO_ROOT / "mcp_servers"),
            skills=SkillRegistry.from_directory(REPO_ROOT / "skills"),
        )

        with patch("sys.stdout", stdout), patch(
            "builtins.input",
            side_effect=lambda prompt="": next(prompts),
        ), patch("personal_agent_toolkit.__main__.create_engine", return_value=engine), patch(
            "personal_agent_toolkit.__main__.signal.getsignal",
            side_effect=fake_getsignal,
        ), patch(
            "personal_agent_toolkit.__main__.signal.signal",
            side_effect=fake_signal,
        ):
            asyncio.run(
                run_repl(
                    workspace=REPO_ROOT,
                    provider_name="ollama",
                    model="test-model",
                )
            )

        output = stdout.getvalue()
        self.assertIn("[cancelled] stopped current request", output)
        self.assertIn("Personal Agent Toolkit", output)

    def test_unknown_command_suggests_nearest_match(self) -> None:
        engine = create_engine(workspace=REPO_ROOT)
        result = asyncio.run(engine.submit("/modle test-model"))

        self.assertIn("unknown command: /modle", result)
        self.assertIn("did you mean /model?", result)
        self.assertIn("type /help", result)

    def test_query_engine_emits_progress_events_for_tool_rounds(self) -> None:
        tools = ToolRegistry()
        register_builtin_tools(tools)
        commands = CommandRegistry()
        register_builtin_commands(commands)
        plugins = PluginManager.from_directory(REPO_ROOT / "plugins")
        plugins.register(tools, commands)
        events: list[dict[str, object]] = []
        engine = QueryEngine(
            cwd=REPO_ROOT,
            provider=ScriptedProvider(
                [
                    CompletionResponse(
                        role="assistant",
                        content="",
                        tool_calls=[
                            {"id": "call-1", "name": "pwd", "arguments": {}},
                        ],
                    ),
                    CompletionResponse(role="assistant", content="done", tool_calls=[]),
                ]
            ),
            model="test-model",
            tools=tools,
            tasks=TaskManager(),
            commands=commands,
            agents=AgentRegistry.from_directory(REPO_ROOT / "personal_agent_toolkit" / "agents"),
            plugins=plugins,
            mcp=LocalMcpRegistry.from_directory(REPO_ROOT, REPO_ROOT / "mcp_servers"),
            skills=SkillRegistry.from_directory(REPO_ROOT / "skills"),
            progress_handler=events.append,
        )

        result = asyncio.run(engine.submit("where am i"))

        self.assertEqual(result, "done")
        self.assertEqual(
            [event["kind"] for event in events],
            [
                "submission_started",
                "model_round_started",
                "tool_batch_started",
                "tool_started",
                "tool_finished",
                "model_round_started",
                "assistant_completed",
            ],
        )
        self.assertEqual(events[3]["name"], "pwd")
        self.assertEqual(events[4]["name"], "pwd")
        self.assertTrue(events[4]["result"]["ok"])
        self.assertEqual(events[0]["provider"], "live")

    def test_query_engine_emits_waiting_progress_for_slow_model(self) -> None:
        tools = ToolRegistry()
        register_builtin_tools(tools)
        commands = CommandRegistry()
        register_builtin_commands(commands)
        plugins = PluginManager.from_directory(REPO_ROOT / "plugins")
        plugins.register(tools, commands)
        events: list[dict[str, object]] = []
        engine = QueryEngine(
            cwd=REPO_ROOT,
            provider=SlowProvider(
                0.01,
                CompletionResponse(role="assistant", content="done", tool_calls=[]),
            ),
            model="test-model",
            tools=tools,
            tasks=TaskManager(),
            commands=commands,
            agents=AgentRegistry.from_directory(REPO_ROOT / "personal_agent_toolkit" / "agents"),
            plugins=plugins,
            mcp=LocalMcpRegistry.from_directory(REPO_ROOT, REPO_ROOT / "mcp_servers"),
            skills=SkillRegistry.from_directory(REPO_ROOT / "skills"),
            progress_handler=events.append,
            progress_poll_interval=0.001,
        )

        result = asyncio.run(engine.submit("make a plan"))

        self.assertEqual(result, "done")
        self.assertEqual(events[0]["prompt_preview"], "make a plan")
        self.assertIn("model_waiting", [event["kind"] for event in events])

    def test_query_engine_retries_without_tools_when_model_rejects_them(self) -> None:
        tools = ToolRegistry()
        register_builtin_tools(tools)
        commands = CommandRegistry()
        register_builtin_commands(commands)
        plugins = PluginManager.from_directory(REPO_ROOT / "plugins")
        plugins.register(tools, commands)
        events: list[dict[str, object]] = []
        provider = NoToolsProvider(
            CompletionResponse(role="assistant", content="done", tool_calls=[])
        )
        engine = QueryEngine(
            cwd=REPO_ROOT,
            provider=provider,
            model="deepseek-r1:14b",
            tools=tools,
            tasks=TaskManager(),
            commands=commands,
            agents=AgentRegistry.from_directory(REPO_ROOT / "personal_agent_toolkit" / "agents"),
            plugins=plugins,
            mcp=LocalMcpRegistry.from_directory(REPO_ROOT, REPO_ROOT / "mcp_servers"),
            skills=SkillRegistry.from_directory(REPO_ROOT / "skills"),
            progress_handler=events.append,
        )

        result = asyncio.run(engine.submit("give me questions"))

        self.assertEqual(result, "done")
        self.assertEqual(len(provider.calls), 2)
        self.assertIsNotNone(provider.calls[0]["tools"])
        self.assertIsNone(provider.calls[1]["tools"])
        self.assertIn("tools_disabled_fallback", [event["kind"] for event in events])

    def test_query_engine_emits_interactive_model_warning_after_fallback_and_wait(self) -> None:
        tools = ToolRegistry()
        register_builtin_tools(tools)
        commands = CommandRegistry()
        register_builtin_commands(commands)
        plugins = PluginManager.from_directory(REPO_ROOT / "plugins")
        plugins.register(tools, commands)
        events: list[dict[str, object]] = []
        provider = NoToolsSlowProvider(
            0.03,
            CompletionResponse(role="assistant", content="done", tool_calls=[]),
        )
        engine = QueryEngine(
            cwd=REPO_ROOT,
            provider=provider,
            model="deepseek-r1:14b",
            tools=tools,
            tasks=TaskManager(),
            commands=commands,
            agents=AgentRegistry.from_directory(REPO_ROOT / "personal_agent_toolkit" / "agents"),
            plugins=plugins,
            mcp=LocalMcpRegistry.from_directory(REPO_ROOT, REPO_ROOT / "mcp_servers"),
            skills=SkillRegistry.from_directory(REPO_ROOT / "skills"),
            progress_handler=events.append,
            progress_poll_interval=0.005,
            interactive_warning_threshold=0.01,
        )

        result = asyncio.run(engine.submit("give me questions"))

        self.assertEqual(result, "done")
        warning_events = [event for event in events if event["kind"] == "interactive_model_warning"]
        self.assertEqual(len(warning_events), 1)
        self.assertIn("qwen2.5-coder", str(warning_events[0]["suggestion"]))


if __name__ == "__main__":
    unittest.main()
