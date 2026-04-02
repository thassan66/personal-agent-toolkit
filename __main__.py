from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from .core.agents import AgentRegistry
from .core.builtin_commands import register_builtin_commands
from .core.builtin_tools import register_builtin_tools
from .core.commands import CommandRegistry
from .core.memory import MemoryStore
from .core.mcp import LocalMcpRegistry
from .core.planning import PlanStore
from .core.plugins import PluginManager
from .core.providers import EchoProvider, OpenAICompatibleProvider
from .core.query_engine import QueryEngine
from .core.skills import SkillRegistry
from .core.tasks import TaskManager
from .core.tools import ToolRegistry


def create_provider() -> object:
    provider_name = os.getenv("INDIE_AGENT_KIT_PROVIDER", "echo").strip().lower()
    if provider_name in {"openai", "openai-compatible", "openai_compatible"}:
        return OpenAICompatibleProvider(
            base_url=os.getenv("INDIE_AGENT_KIT_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.getenv("INDIE_AGENT_KIT_API_KEY", "dummy"),
            timeout=float(os.getenv("INDIE_AGENT_KIT_TIMEOUT", "120")),
    )
    return EchoProvider()


def create_engine(*, workspace: Path, model: str | None = None) -> QueryEngine:
    tools = ToolRegistry()
    tasks = TaskManager()
    commands = CommandRegistry()
    package_root = Path(__file__).resolve().parent
    project_root = package_root.parent
    agents = AgentRegistry.from_directory(package_root / "agents")
    plugins = PluginManager.from_directory(project_root / "plugins")
    mcp = LocalMcpRegistry.from_directory(project_root, project_root / "mcp_servers")
    memory = MemoryStore(project_root / ".indie_agent_kit_memory.jsonl")
    plan_store = PlanStore(project_root / ".indie_agent_kit_plan.json")
    skills = SkillRegistry.from_directory(project_root / "skills")

    register_builtin_tools(tools)
    register_builtin_commands(commands)
    plugins.register(tools, commands)

    return QueryEngine(
        cwd=workspace,
        provider=create_provider(),
        model=model or os.getenv("INDIE_AGENT_KIT_MODEL", "echo-local"),
        tools=tools,
        tasks=tasks,
        commands=commands,
        agents=agents,
        plugins=plugins,
        mcp=mcp,
        memory=memory,
        plan_store=plan_store,
        skills=skills,
        debug=os.getenv("INDIE_AGENT_KIT_DEBUG", "0") in {"1", "true", "yes", "on"},
    )


async def run_repl(*, workspace: Path, model: str | None = None) -> None:
    engine = create_engine(workspace=workspace, model=model)
    print("indie-agent-kit replica")
    print("type /help for commands, /exit to quit")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text in {"/exit", "/quit"}:
            break
        try:
            result = await engine.submit(text)
        except Exception as exc:  # pragma: no cover
            print(f"error: {type(exc).__name__}: {exc}")
            continue
        if result:
            print(result)


async def run_once(*, workspace: Path, prompt: str, model: str | None = None) -> None:
    engine = create_engine(workspace=workspace, model=model)
    result = await engine.submit(prompt)
    if result:
        print(result)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Indie Agent Kit")
    parser.add_argument("--prompt", help="Run a single prompt and exit")
    parser.add_argument("--cwd", default=".", help="Workspace directory")
    parser.add_argument("--model", help="Override the active model name")
    args = parser.parse_args(argv)

    workspace = Path(args.cwd).resolve()
    if args.prompt:
        asyncio.run(run_once(workspace=workspace, prompt=args.prompt, model=args.model))
        return
    asyncio.run(run_repl(workspace=workspace, model=args.model))


if __name__ == "__main__":
    main()
