from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Iterable, Optional

from .tools import ToolUseContext

CommandHandler = Callable[[list[str], ToolUseContext], Awaitable[str]]


@dataclass
class Command:
    name: str
    description: str
    handler: CommandHandler


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: Dict[str, Command] = {}

    def register(self, cmd: Command) -> None:
        self._commands[cmd.name] = cmd

    def get(self, name: str) -> Optional[Command]:
        return self._commands.get(name)

    def names(self) -> Iterable[str]:
        return sorted(self._commands.keys())

    def list(self) -> list[Command]:
        return [self._commands[name] for name in sorted(self._commands)]

    async def run(self, raw: str, ctx: ToolUseContext) -> Optional[str]:
        if not raw.startswith("/"):
            return None
        parts = shlex.split(raw[1:])
        if not parts:
            return "empty command"
        engine = getattr(ctx, "engine", None)
        plugins = getattr(engine, "plugins", None)
        if plugins is not None:
            await plugins.run_hooks(
                "before_command",
                ctx=ctx,
                args=parts,
                payload={"raw": raw},
            )
        cmd = self._commands.get(parts[0])
        if not cmd:
            return f"unknown command: /{parts[0]}"
        result = await cmd.handler(parts[1:], ctx)
        if plugins is not None:
            await plugins.run_hooks(
                "after_command",
                ctx=ctx,
                args=parts,
                payload={"raw": raw, "result": result},
            )
        return result
