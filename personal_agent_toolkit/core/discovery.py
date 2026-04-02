from __future__ import annotations

from typing import Any


def search_runtime(engine: Any, query: str) -> list[dict[str, str]]:
    needle = query.lower().strip()
    if not needle:
        return []

    matches: list[dict[str, str]] = []

    def add(kind: str, name: str, description: str) -> None:
        haystack = f"{name} {description}".lower()
        if needle in haystack:
            matches.append({"kind": kind, "name": name, "description": description})

    for tool in engine.tools.list():
        add("tool", tool.name, tool.description)
    for command in engine.commands.list():
        add("command", f"/{command.name}", command.description)
    for agent in engine.agents.list():
        add("agent", agent.name, agent.description)

    plugins = getattr(engine, "plugins", None)
    if plugins is not None:
        for plugin in plugins.list():
            add("plugin", plugin.name, plugin.description)

    skills = getattr(engine, "skills", None)
    if skills is not None:
        for skill in skills.list():
            add("skill", skill.name, skill.description)

    mcp = getattr(engine, "mcp", None)
    if mcp is not None:
        for server in mcp.list_servers():
            add("mcp-server", server.name, server.description)
        for resource in mcp.list_resources():
            add("mcp-resource", resource.uri, resource.description or resource.name)

    return matches
