from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from personal_agent_toolkit.core.agents import AgentRegistry
from personal_agent_toolkit.core.builtin_commands import register_builtin_commands
from personal_agent_toolkit.core.builtin_tools import register_builtin_tools
from personal_agent_toolkit.core.commands import CommandRegistry
from personal_agent_toolkit.core.memory import MemoryStore
from personal_agent_toolkit.core.mcp import LocalMcpRegistry
from personal_agent_toolkit.core.planning import PlanStore
from personal_agent_toolkit.core.plugins import PluginManager
from personal_agent_toolkit.core.providers import CompletionResponse, EchoProvider
from personal_agent_toolkit.core.query_engine import QueryEngine
from personal_agent_toolkit.core.skills import SkillRegistry
from personal_agent_toolkit.core.tasks import TaskManager, TaskType, generate_task_id
from personal_agent_toolkit.core.tools import ToolRegistry


class ScriptedProvider:
    def __init__(self, responses):
        self._responses = list(responses)

    async def complete(self, messages, *, model, tools=None, stream_handler=None):
        return self._responses.pop(0)


def build_engine(
    cwd: Path,
    *,
    provider=None,
    model: str = "test-model",
) -> QueryEngine:
    root = Path(__file__).resolve().parents[1]
    tools = ToolRegistry()
    register_builtin_tools(tools)
    commands = CommandRegistry()
    register_builtin_commands(commands)
    plugins = PluginManager.from_directory(root / "plugins")
    plugins.register(tools, commands)
    return QueryEngine(
        cwd=cwd,
        provider=provider or EchoProvider(),
        model=model,
        tools=tools,
        tasks=TaskManager(),
        commands=commands,
        agents=AgentRegistry.from_directory(root / "personal_agent_toolkit" / "agents"),
        plugins=plugins,
        mcp=LocalMcpRegistry.from_directory(root, root / "mcp_servers"),
        memory=MemoryStore(cwd / ".personal_agent_toolkit_memory.jsonl"),
        plan_store=PlanStore(cwd / ".personal_agent_toolkit_plan.json"),
        skills=SkillRegistry.from_directory(root / "skills"),
    )


class CoreTests(unittest.TestCase):
    def test_generate_task_id_prefix(self) -> None:
        task_id = generate_task_id(TaskType.LOCAL_BASH)
        self.assertEqual(task_id[0], "b")
        self.assertEqual(len(task_id), 9)

    def test_query_engine_handles_commands(self) -> None:
        async def scenario() -> None:
            with tempfile.TemporaryDirectory() as td:
                engine = build_engine(Path(td), provider=ScriptedProvider([]))
                result = await engine.submit("/tools")
                self.assertIn("shell_command", result)

        asyncio.run(scenario())

    def test_query_engine_can_switch_model_via_command(self) -> None:
        async def scenario() -> None:
            with tempfile.TemporaryDirectory() as td:
                engine = build_engine(Path(td), provider=ScriptedProvider([]))
                result = await engine.submit("/model custom-model")
                self.assertEqual(result, "model set to custom-model")
                self.assertEqual(engine.model, "custom-model")

        asyncio.run(scenario())

    def test_query_engine_runs_tool_loop(self) -> None:
        async def scenario() -> None:
            with tempfile.TemporaryDirectory() as td:
                provider = ScriptedProvider(
                    [
                        CompletionResponse(
                            role="assistant",
                            content="",
                            tool_calls=[
                                {
                                    "id": "call-1",
                                    "name": "write_file",
                                    "arguments": {"path": "note.txt", "content": "hello"},
                                }
                            ],
                        ),
                        CompletionResponse(role="assistant", content="done", tool_calls=[]),
                    ]
                )
                engine = build_engine(Path(td), provider=provider)
                result = await engine.submit("create a note")
                self.assertEqual(result, "done")
                self.assertEqual((Path(td) / "note.txt").read_text(encoding="utf-8"), "hello")

        asyncio.run(scenario())

    def test_phase_two_workspace_commands(self) -> None:
        async def scenario() -> None:
            with tempfile.TemporaryDirectory() as td:
                engine = build_engine(Path(td), provider=ScriptedProvider([]))

                write_result = await engine.submit('/write notes.txt "hello world"')
                self.assertIn("wrote", write_result)

                read_result = await engine.submit("/read notes.txt")
                self.assertEqual(read_result, "hello world")

                grep_result = await engine.submit("/grep hello")
                self.assertIn("notes.txt:1: hello world", grep_result)

                replace_result = await engine.submit('/replace notes.txt hello goodbye')
                self.assertIn("replaced 1 occurrence", replace_result)
                self.assertEqual(
                    (Path(td) / "notes.txt").read_text(encoding="utf-8"),
                    "goodbye world",
                )

        asyncio.run(scenario())

    def test_tool_command_can_invoke_registered_tool(self) -> None:
        async def scenario() -> None:
            with tempfile.TemporaryDirectory() as td:
                engine = build_engine(Path(td), provider=ScriptedProvider([]))
                result = await engine.submit('/tool pwd {}')
                payload = json.loads(result)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["result"]["cwd"], str(Path(td).resolve()))

        asyncio.run(scenario())

    def test_phase_three_diff_regex_plugin_mcp_and_subagent(self) -> None:
        async def scenario() -> None:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                engine = build_engine(root)

                await engine.submit('/write before.txt "alpha\\nbeta\\n"')
                await engine.submit('/write after.txt "alpha\\ngamma\\n"')
                diff_result = await engine.submit("/diff before.txt after.txt")
                self.assertIn("--- before.txt", diff_result)
                self.assertIn("+++ after.txt", diff_result)

                regex_result = await engine.submit('/regex-replace after.txt gamma delta')
                self.assertIn("regex replaced 1 occurrence", regex_result)
                self.assertEqual(
                    (root / "after.txt").read_text(encoding="utf-8"),
                    "alpha\ndelta\n",
                )

                plugins_result = await engine.submit("/plugins")
                self.assertIn("git-helper", plugins_result)
                self.assertIn("note-helper", plugins_result)

                note_template = await engine.submit("/note-template phase3")
                self.assertIn("TODO", note_template)
                self.assertIn("phase3", note_template)

                mcp_servers = await engine.submit("/mcp-servers")
                self.assertIn("workspace-docs", mcp_servers)
                mcp_resources = await engine.submit("/mcp-resources")
                self.assertIn("workspace://readme", mcp_resources)
                mcp_read = await engine.submit("/mcp-read workspace://about")
                self.assertIn("local MCP-style registry", mcp_read)

                delegate_result = await engine.submit("/delegate coder implement a helper")
                self.assertIn("implement a helper", delegate_result)

                spawned = await engine.submit("/spawn reviewer inspect this")
                self.assertIn("spawned reviewer as task", spawned)
                task_id = spawned.rsplit(" ", 1)[-1]
                waited = await engine.submit(f"/wait {task_id}")
                self.assertIn("status: completed", waited)
                self.assertIn("inspect this", waited)

        asyncio.run(scenario())

    def test_phase_four_memory_skills_and_search(self) -> None:
        async def scenario() -> None:
            with tempfile.TemporaryDirectory() as td:
                engine = build_engine(Path(td))

                note_result = await engine.submit('/note remember phase four progress')
                self.assertIn("saved note", note_result)

                memory_result = await engine.submit("/memory")
                self.assertIn("remember phase four progress", memory_result)

                memory_search = await engine.submit("/memory-search phase four")
                self.assertIn("remember phase four progress", memory_search)

                skills_result = await engine.submit("/skills")
                self.assertIn("debug", skills_result)
                self.assertIn("refactor", skills_result)

                skill_show = await engine.submit("/skill-show debug")
                self.assertIn("systematic debugging help", skill_show)

                skill_activate = await engine.submit("/skill debug")
                self.assertIn("debug", skill_activate)
                self.assertIn("debug", engine.active_skill_names)

                search_result = await engine.submit("/search memory")
                self.assertIn("tool: memory_add", search_result)
                self.assertIn("command: /memory", search_result)

                clear_result = await engine.submit("/skill-clear")
                self.assertEqual(clear_result, "cleared active skills")
                self.assertEqual(engine.active_skill_names, [])

        asyncio.run(scenario())

    def test_phase_five_plan_patch_and_workflow(self) -> None:
        async def scenario() -> None:
            with tempfile.TemporaryDirectory() as td:
                engine = build_engine(Path(td))

                set_title = await engine.submit("/plan-set Phase five")
                self.assertIn("Phase five", set_title)

                add_step = await engine.submit("/plan-add finish workflow support")
                self.assertIn("added step", add_step)
                step_id = add_step.rsplit(" ", 1)[-1]

                plan_view = await engine.submit("/plan")
                self.assertIn("Phase five", plan_view)
                self.assertIn("finish workflow support", plan_view)

                done_step = await engine.submit(f"/plan-done {step_id}")
                self.assertIn(step_id, done_step)
                self.assertIn("completed", await engine.submit("/plan"))

                await engine.submit('/write patch.txt "alpha beta gamma"')
                preview = await engine.submit('/patch-preview patch.txt beta theta')
                self.assertIn("--- patch.txt:before", preview)
                self.assertIn("+++ patch.txt:after", preview)

                replaced = await engine.submit('/replace-block patch.txt beta theta')
                self.assertIn("patch.txt", replaced)

                inserted = await engine.submit('/insert-after patch.txt theta " omega"')
                self.assertIn("patch.txt", inserted)
                self.assertEqual(
                    (Path(td) / "patch.txt").read_text(encoding="utf-8"),
                    "alpha theta omega gamma",
                )

                workflows = await engine.submit("/workflows")
                self.assertIn("capture-note", workflows)

                workflow_result = await engine.submit("/workflow capture-note phase-five")
                self.assertIn("Captured workflow note for: phase-five", workflow_result)
                self.assertIn("memory_saved:", workflow_result)

                memory_result = await engine.submit("/memory-search workflow:phase-five")
                self.assertIn("workflow:phase-five", memory_result)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
