from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class TaskType(str, Enum):
    LOCAL_BASH = "local_bash"
    LOCAL_AGENT = "local_agent"
    REMOTE_AGENT = "remote_agent"
    IN_PROCESS_TEAMMATE = "in_process_teammate"
    LOCAL_WORKFLOW = "local_workflow"
    MONITOR_MCP = "monitor_mcp"
    DREAM = "dream"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


TASK_PREFIXES: Dict[TaskType, str] = {
    TaskType.LOCAL_BASH: "b",
    TaskType.LOCAL_AGENT: "a",
    TaskType.REMOTE_AGENT: "r",
    TaskType.IN_PROCESS_TEAMMATE: "t",
    TaskType.LOCAL_WORKFLOW: "w",
    TaskType.MONITOR_MCP: "m",
    TaskType.DREAM: "d",
}
TASK_ID_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


def is_terminal_task_status(status: TaskStatus) -> bool:
    return status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED}


def generate_task_id(task_type: TaskType) -> str:
    suffix = "".join(
        TASK_ID_ALPHABET[b % len(TASK_ID_ALPHABET)] for b in secrets.token_bytes(8)
    )
    return f"{TASK_PREFIXES.get(task_type, 'x')}{suffix}"


@dataclass
class TaskState:
    id: str
    type: TaskType
    description: str
    status: TaskStatus = TaskStatus.PENDING
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    output: list[str] = field(default_factory=list)
    error: Optional[str] = None
    result: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskManager:
    def __init__(self) -> None:
        self._tasks: Dict[str, TaskState] = {}
        self._handles: Dict[str, asyncio.Task[Any]] = {}

    def spawn(
        self,
        task_type: TaskType,
        description: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TaskState:
        task = TaskState(
            id=generate_task_id(task_type),
            type=task_type,
            description=description,
            metadata=dict(metadata or {}),
        )
        self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> Optional[TaskState]:
        return self._tasks.get(task_id)

    def all(self) -> list[TaskState]:
        return list(self._tasks.values())

    def update_status(
        self, task_id: str, status: TaskStatus, error: Optional[str] = None
    ) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        task.status = status
        task.error = error
        if is_terminal_task_status(status):
            task.end_time = datetime.now(timezone.utc)

    def append_output(self, task_id: str, line: str) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.output.append(line)

    def set_result(self, task_id: str, result: Any) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.result = result

    def attach_handle(self, task_id: str, handle: asyncio.Task[Any]) -> None:
        self._handles[task_id] = handle

    def get_handle(self, task_id: str) -> Optional[asyncio.Task[Any]]:
        return self._handles.get(task_id)

    def cancel(self, task_id: str) -> Optional[TaskState]:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        handle = self._handles.get(task_id)
        if handle is not None and not handle.done():
            handle.cancel()
        self.update_status(task_id, TaskStatus.KILLED, error="cancelled")
        return task

    def clear(self, *, keep_non_terminal: bool = True) -> int:
        to_remove: list[str] = []
        for task_id, task in self._tasks.items():
            if keep_non_terminal and not is_terminal_task_status(task.status):
                continue
            to_remove.append(task_id)
        for task_id in to_remove:
            self._tasks.pop(task_id, None)
            self._handles.pop(task_id, None)
        return len(to_remove)

    async def wait(self, task_id: str) -> Optional[TaskState]:
        handle = self._handles.get(task_id)
        if handle is not None:
            try:
                await handle
            except Exception:
                pass
        return self._tasks.get(task_id)

    def snapshot(self, task_id: str) -> Optional[dict[str, Any]]:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        return {
            "id": task.id,
            "type": task.type.value,
            "status": task.status.value,
            "description": task.description,
            "error": task.error,
            "result": task.result,
            "output": "".join(task.output),
            "metadata": dict(task.metadata),
        }
