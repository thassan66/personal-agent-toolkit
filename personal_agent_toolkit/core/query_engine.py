from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

from .agents import AgentRegistry
from .commands import CommandRegistry
from .memory import MemoryStore
from .mcp import LocalMcpRegistry
from .planning import PlanStore
from .providers import CompletionResponse, EchoProvider, LLMProvider
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
        progress_handler: Optional[Callable[[dict[str, Any]], None]] = None,
        progress_poll_interval: float = 3.0,
        public_reasoning: bool = False,
        interactive_warning_threshold: float = 12.0,
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
        self.progress_handler = progress_handler
        self.progress_poll_interval = progress_poll_interval
        self.public_reasoning = public_reasoning
        self.interactive_warning_threshold = interactive_warning_threshold
        self.messages: list[dict[str, Any]] = []
        self.workspace = Workspace(self.cwd)
        agent_list = self.agents.list()
        self.active_agent_name = agent_list[0].name if agent_list else "default"
        self.active_skill_names: list[str] = []
        self._current_submission_tool_fallback = False
        self._current_submission_warning_emitted = False

    def _tools_enabled(self) -> bool:
        return os.getenv("PERSONAL_AGENT_TOOLKIT_ENABLE_TOOLS", "1").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @staticmethod
    def _tools_unsupported_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return "does not support tools" in text or "tool" in text and "not support" in text

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

    def _interactive_model_hint(self) -> str:
        model_lower = self.model.lower()
        if "deepseek" in model_lower:
            return "For interactive use, try `qwen2.5-coder:3b` for speed or `qwen2.5-coder:14b` for a better balance."
        if "14b" in model_lower:
            return "For faster interaction, try `qwen2.5-coder:3b`."
        return "For more responsive interaction, try a smaller or faster local model."

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
            progress_poll_interval=self.progress_poll_interval,
            public_reasoning=self.public_reasoning,
            interactive_warning_threshold=self.interactive_warning_threshold,
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

        if self.public_reasoning:
            system_messages.append(
                {
                    "role": "system",
                    "content": (
                        "Use public reasoning, not hidden chain-of-thought. "
                        "When answering, start with a brief visible section titled "
                        "'Reasoning summary:' with 2-4 short bullet points covering goal, approach, "
                        "key assumptions, and any constraints. Then provide the answer under 'Answer:'. "
                        "Do not mention private reasoning or hidden chain-of-thought."
                    ),
                }
            )

        return system_messages

    async def _complete(self, messages: list[dict[str, Any]]) -> CompletionResponse:
        def stream_handler(event: dict[str, Any]) -> None:
            kind = event.get("kind")
            if kind == "thinking_delta":
                self._emit_progress("model_stream_thinking", text=str(event.get("text", "")))
            elif kind == "content_delta":
                self._emit_progress("model_stream_content", text=str(event.get("text", "")))

        tool_specs = self.tools.as_openai_tools() if self._tools_enabled() else None
        handler = stream_handler if getattr(self, "stream_enabled", True) else None
        try:
            return await self.provider.complete(
                messages,
                model=self.model,
                tools=tool_specs,
                stream_handler=handler,
            )
        except RuntimeError as exc:
            if tool_specs and self._tools_unsupported_error(exc):
                self._current_submission_tool_fallback = True
                self._emit_progress(
                    "tools_disabled_fallback",
                    model=self.model,
                    reason=str(exc),
                )
                return await self.provider.complete(
                    messages,
                    model=self.model,
                    tools=None,
                    stream_handler=handler,
                )
            raise

    def _emit_progress(self, kind: str, **payload: Any) -> None:
        if self.progress_handler is None:
            return
        self.progress_handler({"kind": kind, **payload})

    async def _complete_with_progress(
        self,
        messages: list[dict[str, Any]],
        *,
        round_index: int,
    ) -> CompletionResponse:
        task = asyncio.create_task(self._complete(messages))
        elapsed = 0.0
        while True:
            try:
                return await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=self.progress_poll_interval,
                )
            except asyncio.TimeoutError:
                elapsed += self.progress_poll_interval
                self._emit_progress(
                    "model_waiting",
                    round=round_index + 1,
                    elapsed_seconds=elapsed,
                    agent=self.active_agent_name,
                    model=self.model,
                )
                if (
                    self._current_submission_tool_fallback
                    and not self._current_submission_warning_emitted
                    and elapsed >= self.interactive_warning_threshold
                ):
                    self._current_submission_warning_emitted = True
                    self._emit_progress(
                        "interactive_model_warning",
                        model=self.model,
                        suggestion=self._interactive_model_hint(),
                    )

    async def submit(self, text: str) -> str:
        ctx = self._ctx()
        cmd_result = await self.commands.run(text, ctx)
        if cmd_result is not None:
            return cmd_result

        self._current_submission_tool_fallback = False
        self._current_submission_warning_emitted = False
        self._emit_progress(
            "submission_started",
            agent=self.active_agent_name,
            model=self.model,
            provider="echo" if isinstance(self.provider, EchoProvider) else "live",
            prompt_preview=text.strip()[:120],
        )
        self.messages.append({"role": "user", "content": text})
        working_messages = self._system_messages() + list(self.messages)

        for round_index in range(self.max_tool_rounds):
            self._emit_progress(
                "model_round_started",
                agent=self.active_agent_name,
                model=self.model,
                round=round_index + 1,
            )
            reply = await self._complete_with_progress(
                working_messages,
                round_index=round_index,
            )
            assistant_payload: dict[str, Any] = {
                "role": reply.role,
                "content": reply.content,
            }
            if reply.tool_calls:
                assistant_payload["tool_calls"] = reply.tool_calls
            self.messages.append(assistant_payload)
            working_messages.append(assistant_payload)

            if not reply.tool_calls:
                self._emit_progress(
                    "assistant_completed",
                    agent=self.active_agent_name,
                    model=self.model,
                    round=round_index + 1,
                    content_preview=(reply.content or "").strip()[:120],
                )
                return reply.content

            self._emit_progress(
                "tool_batch_started",
                count=len(reply.tool_calls),
                round=round_index + 1,
            )
            for call in reply.tool_calls:
                started = time.perf_counter()
                self._emit_progress(
                    "tool_started",
                    name=call["name"],
                    arguments=call.get("arguments", {}),
                    round=round_index + 1,
                )
                result = await self.tools.invoke(call["name"], call.get("arguments", {}), ctx)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                self._emit_progress(
                    "tool_finished",
                    name=call["name"],
                    arguments=call.get("arguments", {}),
                    result=result,
                    elapsed_ms=elapsed_ms,
                    round=round_index + 1,
                )
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": call.get("id", call["name"]),
                    "name": call["name"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
                self.messages.append(tool_msg)
                working_messages.append(tool_msg)

        self._emit_progress("tool_loop_limit_reached", limit=self.max_tool_rounds)
        return "tool loop limit reached"
