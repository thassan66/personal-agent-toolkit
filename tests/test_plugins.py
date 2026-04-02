from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from personal_agent_toolkit.core.agents import AgentRegistry
from personal_agent_toolkit.core.builtin_commands import register_builtin_commands
from personal_agent_toolkit.core.builtin_tools import register_builtin_tools
from personal_agent_toolkit.core.commands import CommandRegistry
from personal_agent_toolkit.core.memory import MemoryStore
from personal_agent_toolkit.core.plugins import PluginManager
from personal_agent_toolkit.core.providers import EchoProvider
from personal_agent_toolkit.core.query_engine import QueryEngine
from personal_agent_toolkit.core.tools import ToolRegistry
from personal_agent_toolkit.core.tasks import TaskManager


class PluginHookTests(unittest.IsolatedAsyncioTestCase):
    async def test_after_command_hook_can_write_memory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plugins_dir = root / "plugins"
            plugins_dir.mkdir()
            (plugins_dir / "hook.json").write_text(
                json.dumps(
                    {
                        "name": "hooky",
                        "description": "hook test",
                        "commands": [],
                        "tools": [],
                        "workflows": [],
                        "hooks": {
                            "after_command": [
                                {
                                    "name": "audit",
                                    "action": {
                                        "type": "memory_add",
                                        "text": "hook saw {raw}",
                                    },
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            tools = ToolRegistry()
            register_builtin_tools(tools)
            commands = CommandRegistry()
            register_builtin_commands(commands)
            plugins = PluginManager.from_directory(plugins_dir)
            plugins.register(tools, commands)
            memory = MemoryStore(root / ".memory.jsonl")

            engine = QueryEngine(
                cwd=root,
                provider=EchoProvider(),
                model="echo-local",
                tools=tools,
                tasks=TaskManager(),
                commands=commands,
                agents=AgentRegistry.from_directory(root / "agents"),
                plugins=plugins,
                memory=memory,
            )

            result = await engine.submit("/pwd")
            self.assertEqual(result, str(root.resolve()))
            entries = memory.list(limit=10)
            self.assertTrue(any("/pwd" in entry.text for entry in entries))


if __name__ == "__main__":
    unittest.main()
