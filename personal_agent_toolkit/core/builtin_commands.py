from __future__ import annotations

import json

from .commands import Command, CommandRegistry
from .tools import ToolUseContext


def _decode_escaped_text(value: str) -> str:
    try:
        return bytes(value, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return value


async def help_command(args: list[str], ctx: ToolUseContext) -> str:
    commands = [f"/{cmd.name}: {cmd.description}" for cmd in ctx.commands.list()]
    return "\n".join(commands) if commands else "no commands registered"


async def tools_command(args: list[str], ctx: ToolUseContext) -> str:
    lines = [f"{tool.name}: {tool.description}" for tool in ctx.tools.list()]
    return "\n".join(lines) if lines else "no tools registered"


async def tasks_command(args: list[str], ctx: ToolUseContext) -> str:
    tasks = ctx.tasks.all()
    if not tasks:
        return "no tasks"
    return "\n".join(f"{task.id} {task.status.value} {task.description}" for task in tasks)


async def history_command(args: list[str], ctx: ToolUseContext) -> str:
    return json.dumps(ctx.session_messages[-10:], indent=2)


async def pwd_command(args: list[str], ctx: ToolUseContext) -> str:
    return str(ctx.cwd)


async def ls_command(args: list[str], ctx: ToolUseContext) -> str:
    path = args[0] if args else "."
    recursive = "--recursive" in args or "-r" in args
    result = await ctx.tools.invoke(
        "list_dir",
        {"path": path, "recursive": recursive, "max_entries": 200},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    entries = payload["entries"]
    if not entries:
        return f"{path}: no entries"
    lines = []
    for entry in entries:
        kind = "d" if entry["type"] == "dir" else "f"
        size = "" if entry["size"] is None else f" ({entry['size']} bytes)"
        lines.append(f"{kind} {entry['path']}{size}")
    return "\n".join(lines)


async def read_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return "usage: /read <path>"
    result = await ctx.tools.invoke("read_file", {"path": args[0]}, ctx)
    if not result["ok"]:
        return result["error"]
    return str(result["result"]["content"])


async def write_command(args: list[str], ctx: ToolUseContext) -> str:
    if len(args) < 2:
        return "usage: /write <path> <content>"
    path, content = args[0], _decode_escaped_text(" ".join(args[1:]))
    result = await ctx.tools.invoke(
        "write_file",
        {"path": path, "content": content, "append": False},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    return f"wrote {result['result']['bytes_written']} bytes to {path}"


async def append_command(args: list[str], ctx: ToolUseContext) -> str:
    if len(args) < 2:
        return "usage: /append <path> <content>"
    path, content = args[0], _decode_escaped_text(" ".join(args[1:]))
    result = await ctx.tools.invoke(
        "write_file",
        {"path": path, "content": content, "append": True},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    return f"appended {result['result']['bytes_written']} bytes to {path}"


async def run_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return "usage: /run <command>"
    result = await ctx.tools.invoke(
        "shell_command",
        {"command": " ".join(args), "timeout": 30},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    stdout = (payload.get("stdout") or "").strip()
    stderr = (payload.get("stderr") or "").strip()
    parts = [f"exit_code={payload.get('exit_code')}"]
    if payload.get("task_id"):
        parts.append(f"task_id={payload['task_id']}")
    if stdout:
        parts.append(f"stdout:\n{stdout}")
    if stderr:
        parts.append(f"stderr:\n{stderr}")
    return "\n".join(parts)


async def grep_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return "usage: /grep <pattern> [root]"
    pattern = args[0]
    root = args[1] if len(args) > 1 else "."
    result = await ctx.tools.invoke(
        "grep_text",
        {"pattern": pattern, "root": root, "max_results": 50},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    matches = result["result"]["matches"]
    if not matches:
        return "no matches"
    return "\n".join(
        f"{match['path']}:{match['line']}: {match['text']}" for match in matches
    )


async def glob_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return "usage: /glob <pattern>"
    result = await ctx.tools.invoke(
        "glob_search",
        {"pattern": args[0], "max_entries": 100},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    matches = result["result"]["matches"]
    return "\n".join(matches) if matches else "no matches"


async def replace_command(args: list[str], ctx: ToolUseContext) -> str:
    if len(args) < 3:
        return "usage: /replace <path> <old> <new>"
    path, old, new = args[0], args[1], " ".join(args[2:])
    result = await ctx.tools.invoke(
        "replace_text",
        {"path": path, "old": old, "new": new},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    return f"replaced {payload['replacements']} occurrence(s) in {payload['path']}"


async def regex_replace_command(args: list[str], ctx: ToolUseContext) -> str:
    if len(args) < 3:
        return "usage: /regex-replace <path> <pattern> <replacement>"
    path, pattern, replacement = args[0], args[1], " ".join(args[2:])
    result = await ctx.tools.invoke(
        "replace_regex",
        {"path": path, "pattern": pattern, "replacement": replacement},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    return f"regex replaced {payload['replacements']} occurrence(s) in {payload['path']}"


async def diff_command(args: list[str], ctx: ToolUseContext) -> str:
    if len(args) < 2:
        return "usage: /diff <path_a> <path_b>"
    result = await ctx.tools.invoke(
        "diff_files",
        {"path_a": args[0], "path_b": args[1], "context_lines": 3},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    diff = result["result"]["diff"]
    return diff or "no diff"


async def task_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return await tasks_command(args, ctx)
    result = await ctx.tools.invoke("task_get", {"task_id": args[0]}, ctx)
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    if payload.get("error"):
        return f"{payload['error']}: {payload.get('task_id', '')}".rstrip()
    lines = [
        f"id: {payload['id']}",
        f"type: {payload['type']}",
        f"status: {payload['status']}",
        f"description: {payload['description']}",
    ]
    if payload.get("result") is not None:
        lines.append(f"result: {payload['result']}")
    metadata = payload.get("metadata") or {}
    if metadata:
        lines.append(f"metadata: {json.dumps(metadata, ensure_ascii=False)}")
    if payload.get("error"):
        lines.append(f"error: {payload['error']}")
    output = (payload.get("output") or "").strip()
    if output:
        lines.append(f"output:\n{output}")
    return "\n".join(lines)


async def delegate_command(args: list[str], ctx: ToolUseContext) -> str:
    if len(args) < 2:
        return "usage: /delegate <agent> <prompt>"
    result = await ctx.tools.invoke(
        "delegate_agent",
        {"agent": args[0], "prompt": " ".join(args[1:])},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    return str(result["result"]["result"])


async def spawn_command(args: list[str], ctx: ToolUseContext) -> str:
    if len(args) < 2:
        return "usage: /spawn <agent> <prompt>"
    result = await ctx.tools.invoke(
        "spawn_agent",
        {"agent": args[0], "prompt": " ".join(args[1:])},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    return f"spawned {payload['agent']} as task {payload['task_id']}"


async def wait_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return "usage: /wait <task_id>"
    result = await ctx.tools.invoke("wait_task", {"task_id": args[0]}, ctx)
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    if payload.get("error"):
        return f"{payload['error']}: {payload.get('task_id', '')}".rstrip()
    lines = [
        f"id: {payload['id']}",
        f"status: {payload['status']}",
    ]
    if payload.get("result") is not None:
        lines.append(f"result: {payload['result']}")
    if payload.get("error"):
        lines.append(f"error: {payload['error']}")
    return "\n".join(lines)


async def plugins_command(args: list[str], ctx: ToolUseContext) -> str:
    result = await ctx.tools.invoke("list_plugins", {}, ctx)
    if not result["ok"]:
        return result["error"]
    plugins = result["result"]["plugins"]
    if not plugins:
        return "no plugins loaded"
    return "\n".join(f"{plugin['name']}: {plugin['description']}" for plugin in plugins)


async def mcp_servers_command(args: list[str], ctx: ToolUseContext) -> str:
    result = await ctx.tools.invoke("mcp_list_resources", {}, ctx)
    if not result["ok"]:
        return result["error"]
    servers = result["result"]["servers"]
    if not servers:
        return "no local mcp servers"
    return "\n".join(f"{server['name']}: {server['description']}" for server in servers)


async def mcp_resources_command(args: list[str], ctx: ToolUseContext) -> str:
    payload = {"server": args[0]} if args else {}
    result = await ctx.tools.invoke("mcp_list_resources", payload, ctx)
    if not result["ok"]:
        return result["error"]
    resources = result["result"]["resources"]
    if not resources:
        return "no resources"
    return "\n".join(
        f"{resource['server']} {resource['uri']} {resource['name']}"
        for resource in resources
    )


async def mcp_read_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return "usage: /mcp-read <uri>"
    result = await ctx.tools.invoke("mcp_read_resource", {"uri": args[0]}, ctx)
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    return f"{payload['uri']}\n{payload['content']}"


async def note_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return "usage: /note <text>"
    result = await ctx.tools.invoke(
        "memory_add",
        {"text": _decode_escaped_text(" ".join(args))},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    return f"saved note {payload['id']}"


async def memory_command(args: list[str], ctx: ToolUseContext) -> str:
    limit = int(args[0]) if args else 10
    result = await ctx.tools.invoke("memory_list", {"limit": limit}, ctx)
    if not result["ok"]:
        return result["error"]
    entries = result["result"]["entries"]
    if not entries:
        return "no notes"
    return "\n".join(f"{entry['id']}: {entry['text']}" for entry in entries)


async def memory_search_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return "usage: /memory-search <query>"
    result = await ctx.tools.invoke(
        "memory_search",
        {"query": " ".join(args), "limit": 20},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    entries = result["result"]["entries"]
    if not entries:
        return "no matching notes"
    return "\n".join(f"{entry['id']}: {entry['text']}" for entry in entries)


async def skills_command(args: list[str], ctx: ToolUseContext) -> str:
    result = await ctx.tools.invoke("skills_list", {}, ctx)
    if not result["ok"]:
        return result["error"]
    skills = result["result"]["skills"]
    if not skills:
        return "no skills loaded"
    active = set(getattr(ctx.engine, "active_skill_names", []))
    lines = []
    for skill in skills:
        marker = "*" if skill["name"] in active else " "
        lines.append(f"{marker} {skill['name']}: {skill['description']}")
    return "\n".join(lines)


async def skill_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        active = getattr(ctx.engine, "active_skill_names", [])
        return ", ".join(active) if active else "no active skills"
    result = await ctx.tools.invoke("skill_activate", {"name": args[0]}, ctx)
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    if payload.get("error"):
        return f"{payload['error']}: {payload.get('name', '')}".rstrip()
    return f"active skills: {', '.join(payload['active_skills'])}"


async def skill_show_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return "usage: /skill-show <name>"
    result = await ctx.tools.invoke("skill_get", {"name": args[0]}, ctx)
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    if payload.get("error"):
        return f"{payload['error']}: {payload.get('name', '')}".rstrip()
    return f"{payload['name']}\n{payload['prompt']}"


async def skill_clear_command(args: list[str], ctx: ToolUseContext) -> str:
    result = await ctx.tools.invoke("skill_clear", {}, ctx)
    if not result["ok"]:
        return result["error"]
    return "cleared active skills"


async def search_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return "usage: /search <query>"
    result = await ctx.tools.invoke(
        "runtime_search",
        {"query": " ".join(args)},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    items = result["result"]["results"]
    if not items:
        return "no matches"
    return "\n".join(
        f"{item['kind']}: {item['name']} - {item['description']}" for item in items
    )


async def workflows_command(args: list[str], ctx: ToolUseContext) -> str:
    result = await ctx.tools.invoke("list_workflows", {}, ctx)
    if not result["ok"]:
        return result["error"]
    workflows = result["result"]["workflows"]
    return "\n".join(workflows) if workflows else "no workflows"


async def workflow_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return "usage: /workflow <name> [args...]"
    result = await ctx.tools.invoke(
        "run_workflow",
        {"name": args[0], "args": args[1:]},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    if payload.get("error"):
        return f"{payload['error']}: {payload.get('name', '')}".rstrip()
    outputs = payload.get("outputs") or []
    return "\n\n".join(outputs) if outputs else f"workflow {args[0]} finished"


async def plan_command(args: list[str], ctx: ToolUseContext) -> str:
    result = await ctx.tools.invoke("plan_get", {}, ctx)
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    title = payload.get("title") or "(untitled)"
    steps = payload.get("steps") or []
    if not steps:
        return f"{title}\n(no steps)"
    return "\n".join([str(title)] + [f"- [{step['status']}] {step['id']} {step['text']}" for step in steps])


async def plan_set_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return "usage: /plan-set <title>"
    result = await ctx.tools.invoke("plan_set_title", {"title": " ".join(args)}, ctx)
    if not result["ok"]:
        return result["error"]
    return f"plan title set to {result['result']['title']}"


async def plan_add_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return "usage: /plan-add <step>"
    result = await ctx.tools.invoke("plan_add_step", {"text": " ".join(args)}, ctx)
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    return f"added step {payload['id']}"


async def plan_done_command(args: list[str], ctx: ToolUseContext) -> str:
    if not args:
        return "usage: /plan-done <step_id>"
    result = await ctx.tools.invoke(
        "plan_update_step",
        {"id": args[0], "status": "completed"},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    return f"completed step {result['result']['id']}"


async def plan_clear_command(args: list[str], ctx: ToolUseContext) -> str:
    result = await ctx.tools.invoke("plan_clear", {}, ctx)
    if not result["ok"]:
        return result["error"]
    return "cleared plan"


async def patch_preview_command(args: list[str], ctx: ToolUseContext) -> str:
    if len(args) < 3:
        return "usage: /patch-preview <path> <old> <new>"
    result = await ctx.tools.invoke(
        "preview_patch",
        {"path": args[0], "old": args[1], "new": " ".join(args[2:])},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    if payload.get("error"):
        return payload["error"]
    return payload["diff"] or "no diff"


async def replace_block_command(args: list[str], ctx: ToolUseContext) -> str:
    if len(args) < 3:
        return "usage: /replace-block <path> <old> <new>"
    result = await ctx.tools.invoke(
        "replace_block",
        {"path": args[0], "old": args[1], "new": " ".join(args[2:])},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    if payload.get("error"):
        return payload["error"]
    return f"replaced block in {payload['path']}"


async def insert_after_command(args: list[str], ctx: ToolUseContext) -> str:
    if len(args) < 3:
        return "usage: /insert-after <path> <anchor> <content>"
    result = await ctx.tools.invoke(
        "insert_after",
        {"path": args[0], "anchor": args[1], "content": " ".join(args[2:])},
        ctx,
    )
    if not result["ok"]:
        return result["error"]
    payload = result["result"]
    if payload.get("error"):
        return payload["error"]
    return f"inserted content in {payload['path']}"


async def tool_command(args: list[str], ctx: ToolUseContext) -> str:
    if len(args) < 1:
        return "usage: /tool <name> [json-args]"
    name = args[0]
    if len(args) == 1:
        payload = {}
    else:
        try:
            payload = json.loads(" ".join(args[1:]))
        except json.JSONDecodeError as exc:
            return f"invalid json: {exc}"
    if not isinstance(payload, dict):
        return "tool arguments must decode to a JSON object"
    result = await ctx.tools.invoke(name, payload, ctx)
    return json.dumps(result, indent=2, ensure_ascii=False)


async def agents_command(args: list[str], ctx: ToolUseContext) -> str:
    engine = ctx.engine
    if engine is None:
        return "agent registry unavailable"
    lines = []
    for agent in engine.agents.list():
        marker = "*" if agent.name == engine.active_agent_name else " "
        model_suffix = f" [{agent.model}]" if agent.model else ""
        lines.append(f"{marker} {agent.name}{model_suffix}: {agent.description}")
    return "\n".join(lines) if lines else "no agents"


async def agent_command(args: list[str], ctx: ToolUseContext) -> str:
    engine = ctx.engine
    if engine is None:
        return "agent registry unavailable"
    if not args:
        return f"active agent: {engine.active_agent_name}"
    requested = args[0]
    agent = engine.agents.get(requested)
    if not agent:
        return f"unknown agent: {requested}"
    engine.active_agent_name = agent.name
    if agent.model:
        engine.model = agent.model
    return f"active agent set to {agent.name} (model={engine.model})"


async def model_command(args: list[str], ctx: ToolUseContext) -> str:
    engine = ctx.engine
    if engine is None:
        return "model control unavailable"
    if not args:
        return engine.model
    engine.model = args[0]
    return f"model set to {engine.model}"


async def exit_command(args: list[str], ctx: ToolUseContext) -> str:
    return "use Ctrl+C, Ctrl+D, /quit, or /exit from the REPL wrapper"


def register_builtin_commands(registry: CommandRegistry) -> None:
    registry.register(
        Command(
            name="help",
            description="Show available slash commands",
            handler=help_command,
        )
    )
    registry.register(
        Command(name="tools", description="List available tools", handler=tools_command)
    )
    registry.register(
        Command(name="tasks", description="List tracked tasks", handler=tasks_command)
    )
    registry.register(
        Command(
            name="history",
            description="Show recent message history",
            handler=history_command,
        )
    )
    registry.register(
        Command(name="note", description="Persist a note to memory", handler=note_command)
    )
    registry.register(
        Command(name="memory", description="List recent persistent notes", handler=memory_command)
    )
    registry.register(
        Command(
            name="memory-search",
            description="Search persistent notes",
            handler=memory_search_command,
        )
    )
    registry.register(
        Command(name="skills", description="List available skills", handler=skills_command)
    )
    registry.register(
        Command(name="skill", description="Activate or show active skills", handler=skill_command)
    )
    registry.register(
        Command(name="skill-show", description="Show one skill prompt", handler=skill_show_command)
    )
    registry.register(
        Command(name="skill-clear", description="Clear active skills", handler=skill_clear_command)
    )
    registry.register(
        Command(name="search", description="Search runtime capabilities", handler=search_command)
    )
    registry.register(
        Command(name="workflows", description="List plugin workflows", handler=workflows_command)
    )
    registry.register(
        Command(name="workflow", description="Run a plugin workflow", handler=workflow_command)
    )
    registry.register(
        Command(name="agents", description="List available agent profiles", handler=agents_command)
    )
    registry.register(
        Command(name="agent", description="Show or switch the active agent", handler=agent_command)
    )
    registry.register(
        Command(name="model", description="Show or override the current model", handler=model_command)
    )
    registry.register(
        Command(name="pwd", description="Print current working directory", handler=pwd_command)
    )
    registry.register(
        Command(name="ls", description="List workspace files", handler=ls_command)
    )
    registry.register(
        Command(name="read", description="Read a workspace file", handler=read_command)
    )
    registry.register(
        Command(name="write", description="Write a workspace file", handler=write_command)
    )
    registry.register(
        Command(name="append", description="Append to a workspace file", handler=append_command)
    )
    registry.register(
        Command(name="run", description="Run a shell command", handler=run_command)
    )
    registry.register(
        Command(name="grep", description="Search text in workspace files", handler=grep_command)
    )
    registry.register(
        Command(name="glob", description="Find files by glob pattern", handler=glob_command)
    )
    registry.register(
        Command(name="replace", description="Replace exact text in a file", handler=replace_command)
    )
    registry.register(
        Command(
            name="patch-preview",
            description="Preview an exact block replacement",
            handler=patch_preview_command,
        )
    )
    registry.register(
        Command(
            name="replace-block",
            description="Replace one exact text block in a file",
            handler=replace_block_command,
        )
    )
    registry.register(
        Command(
            name="insert-after",
            description="Insert content after an anchor in a file",
            handler=insert_after_command,
        )
    )
    registry.register(
        Command(
            name="regex-replace",
            description="Replace text using a regex pattern",
            handler=regex_replace_command,
        )
    )
    registry.register(
        Command(name="diff", description="Show a unified diff between two files", handler=diff_command)
    )
    registry.register(
        Command(name="plan", description="Show the current persistent plan", handler=plan_command)
    )
    registry.register(
        Command(name="plan-set", description="Set the plan title", handler=plan_set_command)
    )
    registry.register(
        Command(name="plan-add", description="Add a step to the plan", handler=plan_add_command)
    )
    registry.register(
        Command(name="plan-done", description="Mark a plan step completed", handler=plan_done_command)
    )
    registry.register(
        Command(name="plan-clear", description="Clear the persistent plan", handler=plan_clear_command)
    )
    registry.register(
        Command(name="task", description="Show one task or list tasks", handler=task_command)
    )
    registry.register(
        Command(
            name="delegate",
            description="Run another agent and return its output",
            handler=delegate_command,
        )
    )
    registry.register(
        Command(
            name="spawn",
            description="Spawn another agent as a background task",
            handler=spawn_command,
        )
    )
    registry.register(
        Command(name="wait", description="Wait for a background task", handler=wait_command)
    )
    registry.register(
        Command(name="plugins", description="List loaded plugins", handler=plugins_command)
    )
    registry.register(
        Command(name="mcp-servers", description="List local MCP servers", handler=mcp_servers_command)
    )
    registry.register(
        Command(name="mcp-resources", description="List local MCP resources", handler=mcp_resources_command)
    )
    registry.register(
        Command(name="mcp-read", description="Read a local MCP resource", handler=mcp_read_command)
    )
    registry.register(
        Command(name="tool", description="Invoke a tool with JSON args", handler=tool_command)
    )
    registry.register(
        Command(name="exit", description="Exit the REPL", handler=exit_command)
    )
    registry.register(
        Command(name="quit", description="Exit the REPL", handler=exit_command)
    )
