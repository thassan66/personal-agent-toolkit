from __future__ import annotations

import asyncio
from typing import Any

from .discovery import search_runtime
from .editing import regex_replace_in_file, unified_diff_for_files
from .patching import insert_after, preview_replace_block, replace_block
from .orchestration import run_subagent, spawn_subagent_task
from .tasks import TaskStatus, TaskType
from .tools import Tool, ToolRegistry, ToolUseContext


def _truncate(text: str, limit: int = 12000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


async def shell_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    cmd = str(payload.get("command", "")).strip()
    timeout = float(payload.get("timeout", 30))
    if not cmd:
        return {"stderr": "missing command", "exit_code": 2}

    task = ctx.tasks.spawn(TaskType.LOCAL_BASH, f"shell: {cmd}")
    ctx.tasks.update_status(task.id, TaskStatus.RUNNING)
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(ctx.cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")
        if out:
            ctx.tasks.append_output(task.id, out)
        if err:
            ctx.tasks.append_output(task.id, err)
        status = TaskStatus.COMPLETED if proc.returncode == 0 else TaskStatus.FAILED
        ctx.tasks.update_status(task.id, status, error=err or None)
        return {
            "task_id": task.id,
            "stdout": _truncate(out),
            "stderr": _truncate(err),
            "exit_code": proc.returncode,
        }
    except TimeoutError:
        ctx.tasks.update_status(task.id, TaskStatus.FAILED, error="timeout")
        return {
            "task_id": task.id,
            "stdout": "",
            "stderr": "timeout",
            "exit_code": 124,
        }


async def list_dir_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    raw_path = str(payload.get("path", "."))
    recursive = bool(payload.get("recursive", False))
    max_entries = int(payload.get("max_entries", 200))
    path = ctx.workspace.resolve_path(raw_path)
    try:
        entries = ctx.workspace.list_entries(
            raw_path,
            recursive=recursive,
            max_entries=max_entries,
        )
    except Exception as exc:
        return {"path": str(path), "entries": [], "error": str(exc)}
    return {"path": str(path), "entries": entries}


async def read_file_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    raw_path = str(payload.get("path", ""))
    max_bytes = int(payload.get("max_bytes", 100_000))
    path = ctx.workspace.resolve_path(raw_path)
    return {"path": str(path), "content": ctx.workspace.read_text(raw_path, max_bytes=max_bytes)}


async def write_file_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    raw_path = str(payload.get("path", ""))
    content = str(payload.get("content", ""))
    append = bool(payload.get("append", False))
    path = ctx.workspace.write_text(raw_path, content, append=append)
    return {
        "path": str(path),
        "bytes_written": len(content.encode("utf-8")),
        "append": append,
    }


async def glob_search_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    pattern = str(payload.get("pattern", "**/*"))
    max_entries = int(payload.get("max_entries", 200))
    return {
        "pattern": pattern,
        "matches": ctx.workspace.glob(pattern, max_entries=max_entries),
    }


async def grep_text_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    pattern = str(payload.get("pattern", "")).strip()
    if not pattern:
        return {"matches": [], "error": "missing pattern"}
    root = str(payload.get("root", "."))
    case_sensitive = bool(payload.get("case_sensitive", False))
    max_results = int(payload.get("max_results", 100))
    extensions = payload.get("extensions") or []
    if isinstance(extensions, str):
        extensions = [part.strip() for part in extensions.split(",") if part.strip()]
    return {
        "pattern": pattern,
        "matches": ctx.workspace.grep(
            pattern,
            root=root,
            case_sensitive=case_sensitive,
            max_results=max_results,
            include_extensions=extensions,
        ),
    }


async def replace_text_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    path = str(payload.get("path", "")).strip()
    old = str(payload.get("old", ""))
    new = str(payload.get("new", ""))
    count = int(payload.get("count", -1))
    if not path:
        return {"error": "missing path"}
    if not old:
        return {"error": "missing old text"}
    return ctx.workspace.replace_text(path, old=old, new=new, count=count)


async def diff_files_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    path_a = str(payload.get("path_a", "")).strip()
    path_b = str(payload.get("path_b", "")).strip()
    context_lines = int(payload.get("context_lines", 3))
    if not path_a or not path_b:
        return {"error": "missing path_a or path_b"}
    return {
        "path_a": path_a,
        "path_b": path_b,
        "diff": unified_diff_for_files(
            ctx.workspace,
            path_a,
            path_b,
            context_lines=context_lines,
        ),
    }


async def regex_replace_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    path = str(payload.get("path", "")).strip()
    pattern = str(payload.get("pattern", ""))
    replacement = str(payload.get("replacement", ""))
    count = int(payload.get("count", 0))
    if not path or not pattern:
        return {"error": "missing path or pattern"}
    return regex_replace_in_file(
        ctx.workspace,
        path,
        pattern=pattern,
        replacement=replacement,
        count=count,
    )


async def inspect_task_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    task_id = str(payload.get("task_id", "")).strip()
    task = ctx.tasks.get(task_id)
    if not task:
        return {"error": "task_not_found", "task_id": task_id}
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


async def run_registered_tool_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    name = str(payload.get("tool", "")).strip()
    args = payload.get("arguments") or {}
    if not name:
        return {"error": "missing tool"}
    if not isinstance(args, dict):
        return {"error": "arguments must be an object"}
    if name == "tool_run":
        return {"error": "tool_run cannot call itself"}
    result = await ctx.tools.invoke(name, args, ctx)
    return {
        "tool": name,
        "result": result,
    }


async def mcp_list_resources_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    registry = getattr(ctx.engine, "mcp", None)
    if registry is None:
        return {"servers": [], "resources": []}
    server = payload.get("server")
    resources = [
        {
            "server": resource.server,
            "uri": resource.uri,
            "name": resource.name,
            "description": resource.description,
            "kind": resource.kind,
        }
        for resource in registry.list_resources(server)
    ]
    return {
        "servers": [
            {"name": server.name, "description": server.description}
            for server in registry.list_servers()
        ],
        "resources": resources,
    }


async def mcp_read_resource_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    registry = getattr(ctx.engine, "mcp", None)
    if registry is None:
        return {"error": "mcp registry unavailable"}
    uri = str(payload.get("uri", "")).strip()
    if not uri:
        return {"error": "missing uri"}
    return registry.read_resource(uri)


async def delegate_agent_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    if ctx.engine is None:
        return {"error": "engine unavailable"}
    agent = str(payload.get("agent", "default")).strip() or "default"
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        return {"error": "missing prompt"}
    result = await run_subagent(ctx.engine, agent_name=agent, prompt=prompt)
    return {"agent": agent, "result": result}


async def spawn_agent_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    if ctx.engine is None:
        return {"error": "engine unavailable"}
    agent = str(payload.get("agent", "default")).strip() or "default"
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        return {"error": "missing prompt"}
    task = spawn_subagent_task(ctx.engine, ctx.tasks, agent_name=agent, prompt=prompt)
    return {"task_id": task.id, "agent": agent, "status": task.status.value}


async def wait_task_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    task_id = str(payload.get("task_id", "")).strip()
    if not task_id:
        return {"error": "missing task_id"}
    task = await ctx.tasks.wait(task_id)
    if task is None:
        return {"error": "task_not_found", "task_id": task_id}
    return ctx.tasks.snapshot(task_id) or {"error": "task_not_found", "task_id": task_id}


async def list_plugins_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    plugins = getattr(ctx.engine, "plugins", None)
    if plugins is None:
        return {"plugins": []}
    return {
        "plugins": [
            {"name": plugin.name, "description": plugin.description}
            for plugin in plugins.list()
        ]
    }


async def list_workflows_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    plugins = getattr(ctx.engine, "plugins", None)
    if plugins is None:
        return {"workflows": []}
    return {"workflows": plugins.workflow_names()}


async def run_workflow_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    plugins = getattr(ctx.engine, "plugins", None)
    if plugins is None:
        return {"error": "plugins unavailable"}
    name = str(payload.get("name", "")).strip()
    args = payload.get("args") or []
    if isinstance(args, str):
        args = [part for part in args.split(" ") if part]
    if not name:
        return {"error": "missing workflow name"}
    try:
        outputs = await plugins.run_workflow(name, ctx=ctx, args=list(args))
    except KeyError:
        return {"error": "workflow_not_found", "name": name}
    return {"name": name, "outputs": outputs}


async def memory_add_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    store = getattr(ctx.engine, "memory", None)
    if store is None:
        return {"error": "memory unavailable"}
    text = str(payload.get("text", "")).strip()
    if not text:
        return {"error": "missing text"}
    tags = payload.get("tags") or []
    if isinstance(tags, str):
        tags = [part.strip() for part in tags.split(",") if part.strip()]
    entry = store.add(text, tags=list(tags))
    return {"id": entry.id, "text": entry.text, "tags": entry.tags}


async def memory_list_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    store = getattr(ctx.engine, "memory", None)
    if store is None:
        return {"entries": []}
    limit = int(payload.get("limit", 20))
    entries = store.list(limit=limit)
    return {"entries": [entry.__dict__ for entry in entries]}


async def memory_search_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    store = getattr(ctx.engine, "memory", None)
    if store is None:
        return {"entries": []}
    query = str(payload.get("query", "")).strip()
    if not query:
        return {"entries": []}
    limit = int(payload.get("limit", 20))
    entries = store.search(query, limit=limit)
    return {"entries": [entry.__dict__ for entry in entries]}


async def list_skills_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    skills = getattr(ctx.engine, "skills", None)
    if skills is None:
        return {"skills": []}
    return {
        "skills": [
            {"name": skill.name, "description": skill.description}
            for skill in skills.list()
        ]
    }


async def get_skill_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    skills = getattr(ctx.engine, "skills", None)
    if skills is None:
        return {"error": "skills unavailable"}
    name = str(payload.get("name", "")).strip()
    skill = skills.get(name)
    if skill is None:
        return {"error": "skill_not_found", "name": name}
    return {
        "name": skill.name,
        "description": skill.description,
        "prompt": skill.prompt,
    }


async def activate_skill_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    skills = getattr(ctx.engine, "skills", None)
    if skills is None or ctx.engine is None:
        return {"error": "skills unavailable"}
    name = str(payload.get("name", "")).strip()
    skill = skills.get(name)
    if skill is None:
        return {"error": "skill_not_found", "name": name}
    if name not in ctx.engine.active_skill_names:
        ctx.engine.active_skill_names.append(name)
    return {"active_skills": list(ctx.engine.active_skill_names)}


async def clear_skills_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    if ctx.engine is None:
        return {"error": "engine unavailable"}
    ctx.engine.active_skill_names.clear()
    return {"active_skills": []}


async def runtime_search_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    if ctx.engine is None:
        return {"results": []}
    query = str(payload.get("query", "")).strip()
    return {"results": search_runtime(ctx.engine, query)}


async def plan_get_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    store = getattr(ctx.engine, "plan_store", None)
    if store is None:
        return {"title": "", "steps": []}
    return store.get()


async def plan_set_title_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    store = getattr(ctx.engine, "plan_store", None)
    if store is None:
        return {"error": "plan store unavailable"}
    title = str(payload.get("title", "")).strip()
    return store.set_title(title)


async def plan_add_step_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    store = getattr(ctx.engine, "plan_store", None)
    if store is None:
        return {"error": "plan store unavailable"}
    text = str(payload.get("text", "")).strip()
    if not text:
        return {"error": "missing text"}
    step = store.add_step(text)
    return {"id": step.id, "text": step.text, "status": step.status}


async def plan_update_step_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    store = getattr(ctx.engine, "plan_store", None)
    if store is None:
        return {"error": "plan store unavailable"}
    step_id = str(payload.get("id", "")).strip()
    status = str(payload.get("status", "pending")).strip()
    if not step_id:
        return {"error": "missing id"}
    return store.update_step(step_id, status)


async def plan_clear_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    store = getattr(ctx.engine, "plan_store", None)
    if store is None:
        return {"error": "plan store unavailable"}
    store.clear()
    return {"title": "", "steps": []}


async def preview_patch_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    path = str(payload.get("path", "")).strip()
    old = str(payload.get("old", ""))
    new = str(payload.get("new", ""))
    if not path or not old:
        return {"error": "missing path or old text"}
    return {
        "path": path,
        "diff": preview_replace_block(ctx.workspace, path, old=old, new=new),
    }


async def replace_block_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    path = str(payload.get("path", "")).strip()
    old = str(payload.get("old", ""))
    new = str(payload.get("new", ""))
    if not path or not old:
        return {"error": "missing path or old text"}
    return replace_block(ctx.workspace, path, old=old, new=new)


async def insert_after_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    path = str(payload.get("path", "")).strip()
    anchor = str(payload.get("anchor", ""))
    content = str(payload.get("content", ""))
    if not path or not anchor:
        return {"error": "missing path or anchor"}
    return insert_after(ctx.workspace, path, anchor=anchor, content=content)


async def pwd_tool(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
    return {"cwd": str(ctx.cwd), "workspace": str(ctx.workspace.root)}


def register_builtin_tools(registry: ToolRegistry) -> None:
    registry.register(
        Tool(
            name="shell_command",
            description="Run a shell command in the current workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "number"},
                },
                "required": ["command"],
            },
            handler=shell_tool,
        )
    )
    registry.register(
        Tool(
            name="list_dir",
            description="List files and directories inside the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "recursive": {"type": "boolean"},
                    "max_entries": {"type": "integer"},
                },
            },
            handler=list_dir_tool,
        )
    )
    registry.register(
        Tool(
            name="read_file",
            description="Read a UTF-8 text file from the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_bytes": {"type": "integer"},
                },
                "required": ["path"],
            },
            handler=read_file_tool,
        )
    )
    registry.register(
        Tool(
            name="write_file",
            description="Write a UTF-8 text file inside the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "append": {"type": "boolean"},
                },
                "required": ["path", "content"],
            },
            handler=write_file_tool,
        )
    )
    registry.register(
        Tool(
            name="glob_search",
            description="Find workspace paths matching a glob pattern.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "max_entries": {"type": "integer"},
                },
            },
            handler=glob_search_tool,
        )
    )
    registry.register(
        Tool(
            name="grep_text",
            description="Search text inside workspace files.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "root": {"type": "string"},
                    "case_sensitive": {"type": "boolean"},
                    "max_results": {"type": "integer"},
                    "extensions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["pattern"],
            },
            handler=grep_text_tool,
        )
    )
    registry.register(
        Tool(
            name="replace_text",
            description="Replace exact text in a workspace file.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old": {"type": "string"},
                    "new": {"type": "string"},
                    "count": {"type": "integer"},
                },
                "required": ["path", "old", "new"],
            },
            handler=replace_text_tool,
        )
    )
    registry.register(
        Tool(
            name="diff_files",
            description="Show a unified diff between two workspace files.",
            input_schema={
                "type": "object",
                "properties": {
                    "path_a": {"type": "string"},
                    "path_b": {"type": "string"},
                    "context_lines": {"type": "integer"},
                },
                "required": ["path_a", "path_b"],
            },
            handler=diff_files_tool,
        )
    )
    registry.register(
        Tool(
            name="replace_regex",
            description="Replace text by regex pattern in a workspace file.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "pattern": {"type": "string"},
                    "replacement": {"type": "string"},
                    "count": {"type": "integer"},
                },
                "required": ["path", "pattern", "replacement"],
            },
            handler=regex_replace_tool,
        )
    )
    registry.register(
        Tool(
            name="task_get",
            description="Inspect a tracked task by id.",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                },
                "required": ["task_id"],
            },
            handler=inspect_task_tool,
        )
    )
    registry.register(
        Tool(
            name="tool_run",
            description="Invoke another registered tool by name with JSON arguments.",
            input_schema={
                "type": "object",
                "properties": {
                    "tool": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["tool"],
            },
            handler=run_registered_tool_tool,
        )
    )
    registry.register(
        Tool(
            name="mcp_list_resources",
            description="List resources from the local MCP registry.",
            input_schema={
                "type": "object",
                "properties": {"server": {"type": "string"}},
            },
            handler=mcp_list_resources_tool,
        )
    )
    registry.register(
        Tool(
            name="mcp_read_resource",
            description="Read a resource by URI from the local MCP registry.",
            input_schema={
                "type": "object",
                "properties": {"uri": {"type": "string"}},
                "required": ["uri"],
            },
            handler=mcp_read_resource_tool,
        )
    )
    registry.register(
        Tool(
            name="delegate_agent",
            description="Run another agent in-process and return its result.",
            input_schema={
                "type": "object",
                "properties": {
                    "agent": {"type": "string"},
                    "prompt": {"type": "string"},
                },
                "required": ["prompt"],
            },
            handler=delegate_agent_tool,
        )
    )
    registry.register(
        Tool(
            name="spawn_agent",
            description="Spawn another agent as a tracked background task.",
            input_schema={
                "type": "object",
                "properties": {
                    "agent": {"type": "string"},
                    "prompt": {"type": "string"},
                },
                "required": ["prompt"],
            },
            handler=spawn_agent_tool,
        )
    )
    registry.register(
        Tool(
            name="wait_task",
            description="Wait for a tracked task to complete.",
            input_schema={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
            handler=wait_task_tool,
        )
    )
    registry.register(
        Tool(
            name="list_plugins",
            description="List loaded local plugins.",
            input_schema={"type": "object", "properties": {}},
            handler=list_plugins_tool,
        )
    )
    registry.register(
        Tool(
            name="list_workflows",
            description="List available plugin workflows.",
            input_schema={"type": "object", "properties": {}},
            handler=list_workflows_tool,
        )
    )
    registry.register(
        Tool(
            name="run_workflow",
            description="Run a named plugin workflow.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["name"],
            },
            handler=run_workflow_tool,
        )
    )
    registry.register(
        Tool(
            name="memory_add",
            description="Persist a note in the local memory store.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["text"],
            },
            handler=memory_add_tool,
        )
    )
    registry.register(
        Tool(
            name="memory_list",
            description="List recent persistent notes.",
            input_schema={
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
            handler=memory_list_tool,
        )
    )
    registry.register(
        Tool(
            name="memory_search",
            description="Search persistent notes.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
            handler=memory_search_tool,
        )
    )
    registry.register(
        Tool(
            name="skills_list",
            description="List available skills.",
            input_schema={"type": "object", "properties": {}},
            handler=list_skills_tool,
        )
    )
    registry.register(
        Tool(
            name="skill_get",
            description="Get a skill prompt by name.",
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            handler=get_skill_tool,
        )
    )
    registry.register(
        Tool(
            name="skill_activate",
            description="Activate a skill for the current session.",
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            handler=activate_skill_tool,
        )
    )
    registry.register(
        Tool(
            name="skill_clear",
            description="Clear active skills for the current session.",
            input_schema={"type": "object", "properties": {}},
            handler=clear_skills_tool,
        )
    )
    registry.register(
        Tool(
            name="runtime_search",
            description="Search tools, commands, agents, plugins, MCP, and skills.",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            handler=runtime_search_tool,
        )
    )
    registry.register(
        Tool(
            name="plan_get",
            description="Get the current persistent plan.",
            input_schema={"type": "object", "properties": {}},
            handler=plan_get_tool,
        )
    )
    registry.register(
        Tool(
            name="plan_set_title",
            description="Set the title of the persistent plan.",
            input_schema={
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            },
            handler=plan_set_title_tool,
        )
    )
    registry.register(
        Tool(
            name="plan_add_step",
            description="Add a step to the persistent plan.",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            handler=plan_add_step_tool,
        )
    )
    registry.register(
        Tool(
            name="plan_update_step",
            description="Update the status of a persistent plan step.",
            input_schema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "status": {"type": "string"},
                },
                "required": ["id", "status"],
            },
            handler=plan_update_step_tool,
        )
    )
    registry.register(
        Tool(
            name="plan_clear",
            description="Clear the persistent plan.",
            input_schema={"type": "object", "properties": {}},
            handler=plan_clear_tool,
        )
    )
    registry.register(
        Tool(
            name="preview_patch",
            description="Preview a block replacement as a unified diff.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old": {"type": "string"},
                    "new": {"type": "string"},
                },
                "required": ["path", "old", "new"],
            },
            handler=preview_patch_tool,
        )
    )
    registry.register(
        Tool(
            name="replace_block",
            description="Replace one exact text block in a file.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old": {"type": "string"},
                    "new": {"type": "string"},
                },
                "required": ["path", "old", "new"],
            },
            handler=replace_block_tool,
        )
    )
    registry.register(
        Tool(
            name="insert_after",
            description="Insert text after an anchor in a file.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "anchor": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "anchor", "content"],
            },
            handler=insert_after_tool,
        )
    )
    registry.register(
        Tool(
            name="pwd",
            description="Show the current working directory and workspace root.",
            input_schema={"type": "object", "properties": {}},
            handler=pwd_tool,
        )
    )
