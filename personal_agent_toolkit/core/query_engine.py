from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .agents import AgentRegistry
from .commands import CommandRegistry
from .memory import MemoryStore
from .mcp import LocalMcpRegistry
from .planning import PlanStore
from .providers import CompletionResponse, LLMProvider
from .plugins import PluginManager
from .skills import SkillRegistry
from .tasks import TaskManager
from .tools import ToolRegistry, ToolUseContext
from .workspace import Workspace


class QueryEngine:
    def __init__(
        self,
        *,
        cwd: Path,
        provider: LLMProvider,
        model: str,
        tools: ToolRegistry,
        tasks: TaskManager,
        commands: CommandRegistry,
        agents: Optional[AgentRegistry] = None,
        plugins: Optional[PluginManager] = None,
        mcp: Optional[LocalMcpRegistry] = None,
        memory: Optional[MemoryStore] = None,
        plan_store: Optional[PlanStore] = None,
        skills: Optional[SkillRegistry] = None,
        debug: bool = False,
        max_tool_rounds: int = 8,
    ) -> None:
        self.cwd = cwd.resolve()
        self.provider = provider
        self.model = model
        self.tools = tools
        self.tasks = tasks
        self.commands = commands
        self.agents = agents or AgentRegistry()
        self.plugins = plugins
        self.mcp = mcp
        self.memory = memory
        self.plan_store = plan_store
        self.skills = skills or SkillRegistry([])
        self.debug = debug
        self.max_tool_rounds = max_tool_rounds
        self.messages: list[dict[str, Any]] = []
        self.workspace = Workspace(self.cwd)
        agent_list = self.agents.list()
        self.active_agent_name = agent_list[0].name if agent_list else "default"
        self.active_skill_names: list[str] = []

    def _ctx(self) -> ToolUseContext:
        return ToolUseContext(
            cwd=self.cwd,
            workspace=self.workspace,
            tools=self.tools,
            tasks=self.tasks,
            session_messages=self.messages,
            debug=self.debug,
            commands=self.commands,
            engine=self,
        )

    def clone_for_agent(self, agent_name: str) -> "QueryEngine":
        child = QueryEngine(
            cwd=self.cwd,
            provider=self.provider,
            model=self.model,
            tools=self.tools,
            tasks=self.tasks,
            commands=self.commands,
            agents=self.agents,
            plugins=self.plugins,
            mcp=self.mcp,
            memory=self.memory,
            plan_store=self.plan_store,
            skills=self.skills,
            debug=self.debug,
            max_tool_rounds=self.max_tool_rounds,
        )
        if self.agents.get(agent_name):
            child.active_agent_name = agent_name
            agent = self.agents.get(agent_name)
            if agent and agent.model:
                child.model = agent.model
        child.messages = list(self.messages)
        child.active_skill_names = list(self.active_skill_names)
        return child

    def _system_messages(self) -> list[dict[str, Any]]:
        system_messages: list[dict[str, Any]] = []
        agent = self.agents.get(self.active_agent_name)
        if agent and agent.system_prompt:
            system_messages.append({"role": "system", "content": agent.system_prompt})

        for skill_name in self.active_skill_names:
            skill = self.skills.get(skill_name)
            if skill:
                system_messages.append(
                    {
                        "role": "system",
                        "content": f"Active skill: {skill.name}\n{skill.prompt}",
                    }
                )

        if self.memory is not None:
            summary = self.memory.summary(limit=5)
            if summary:
                system_messages.append(
                    {
                        "role": "system",
                        "content": f"Recent persistent notes:\n{summary}",
                    }
                )

        if self.plan_store is not None:
            plan = self.plan_store.get()
            title = str(plan.get("title", "")).strip()
            steps = plan.get("steps", [])
            if title or steps:
                rendered_steps = "\n".join(
                    f"- [{step['status']}] {step['text']}" for step in steps[:10]
                )
                system_messages.append(
                    {
                        "role": "system",
                        "content": f"Current plan: {title or '(untitled)'}\n{rendered_steps}".strip(),
                    }
                )

        return system_messages

    async def _complete(self, messages: list[dict[str, Any]]) -> CompletionResponse:
        return await self.provider.complete(
            messages,
            model=self.model,
            tools=self.tools.as_openai_tools(),
        )

    async def submit(self, text: str) -> str:
        ctx = self._ctx()
        cmd_result = await self.commands.run(text, ctx)
        if cmd_result is not None:
            return cmd_result

        self.messages.append({"role": "user", "content": text})
        working_messages = self._system_messages() + list(self.messages)

        for _ in range(self.max_tool_rounds):
            reply = await self._complete(working_messages)
            assistant_payload: dict[str, Any] = {
                "role": reply.role,
                "content": reply.content,
            }
            if reply.tool_calls:
                assistant_payload["tool_calls"] = reply.tool_calls
            self.messages.append(assistant_payload)
            working_messages.append(assistant_payload)

            if not reply.tool_calls:
                return reply.content

            for call in reply.tool_calls:
                result = await self.tools.invoke(call["name"], call.get("arguments", {}), ctx)
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": call.get("id", call["name"]),
                    "name": call["name"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
                self.messages.append(tool_msg)
                working_messages.append(tool_msg)

        return "tool loop limit reached"
