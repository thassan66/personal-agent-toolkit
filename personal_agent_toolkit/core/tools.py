from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from .tasks import TaskManager
from .workspace import Workspace

ToolHandler = Callable[[Dict[str, Any], "ToolUseContext"], Awaitable[Dict[str, Any]]]
PermissionHook = Callable[[str, Dict[str, Any], "ToolUseContext"], bool]


@dataclass
class Tool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: ToolHandler


@dataclass
class ToolUseContext:
    cwd: Path
    workspace: Workspace
    tools: "ToolRegistry"
    tasks: TaskManager
    session_messages: list[dict[str, Any]]
    debug: bool = False
    commands: Any = None
    engine: Any = None


class ToolRegistry:
    def __init__(self, permission_hook: Optional[PermissionHook] = None) -> None:
        self._tools: Dict[str, Tool] = {}
        self._permission_hook = permission_hook

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list(self) -> list[Tool]:
        return [self._tools[name] for name in sorted(self._tools)]

    def as_openai_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in self.list()
        ]

    async def invoke(
        self, name: str, payload: Dict[str, Any], ctx: ToolUseContext
    ) -> Dict[str, Any]:
        tool = self._tools.get(name)
        if not tool:
            return {"ok": False, "error": f"tool_not_found: {name}"}
        engine = getattr(ctx, "engine", None)
        plugins = getattr(engine, "plugins", None)
        if self._permission_hook and not self._permission_hook(name, payload, ctx):
            return {"ok": False, "error": f"permission_denied: {name}"}
        try:
            if plugins is not None:
                await plugins.run_hooks(
                    "before_tool",
                    ctx=ctx,
                    payload={"tool": name, "arguments": payload},
                )
            result = await tool.handler(payload, ctx)
            wrapped = {"ok": True, "result": result}
            if plugins is not None:
                await plugins.run_hooks(
                    "after_tool",
                    ctx=ctx,
                    payload={"tool": name, "arguments": payload, "result": wrapped},
                )
            return wrapped
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
