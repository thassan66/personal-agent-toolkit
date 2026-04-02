from __future__ import annotations

import asyncio

from .tasks import TaskManager, TaskStatus, TaskType


async def run_subagent(engine, *, agent_name: str, prompt: str) -> str:
    child = engine.clone_for_agent(agent_name)
    return await child.submit(prompt)


def spawn_subagent_task(engine, tasks: TaskManager, *, agent_name: str, prompt: str):
    task_state = tasks.spawn(
        TaskType.LOCAL_AGENT,
        f"subagent:{agent_name} {prompt}",
        metadata={"agent": agent_name, "prompt": prompt},
    )
    tasks.update_status(task_state.id, TaskStatus.RUNNING)

    async def runner() -> None:
        try:
            result = await run_subagent(engine, agent_name=agent_name, prompt=prompt)
            tasks.set_result(task_state.id, result)
            tasks.append_output(task_state.id, result)
            tasks.update_status(task_state.id, TaskStatus.COMPLETED)
        except Exception as exc:  # pragma: no cover
            tasks.set_result(task_state.id, None)
            tasks.update_status(task_state.id, TaskStatus.FAILED, error=str(exc))

    handle = asyncio.create_task(runner(), name=f"subagent-{task_state.id}")
    tasks.attach_handle(task_state.id, handle)
    return task_state
