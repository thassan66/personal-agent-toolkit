from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class McpResource:
    server: str
    uri: str
    name: str
    description: str
    kind: str
    path: str | None = None
    content: str | None = None


@dataclass(frozen=True)
class McpServer:
    name: str
    description: str
    resources: list[McpResource]


class LocalMcpRegistry:
    def __init__(self, workspace_root: Path, servers: list[McpServer]) -> None:
        self.workspace_root = workspace_root.resolve()
        self.servers = servers

    @classmethod
    def from_directory(cls, workspace_root: Path, directory: Path) -> "LocalMcpRegistry":
        servers: list[McpServer] = []
        if directory.exists():
            for file in sorted(directory.glob("*.json")):
                payload = json.loads(file.read_text(encoding="utf-8"))
                resources = [
                    McpResource(
                        server=str(payload["name"]),
                        uri=str(item["uri"]),
                        name=str(item.get("name", item["uri"])),
                        description=str(item.get("description", "")),
                        kind=str(item.get("kind", "text")),
                        path=item.get("path"),
                        content=item.get("content"),
                    )
                    for item in payload.get("resources", [])
                ]
                servers.append(
                    McpServer(
                        name=str(payload["name"]),
                        description=str(payload.get("description", "")),
                        resources=resources,
                    )
                )
        return cls(workspace_root, servers)

    def list_servers(self) -> list[McpServer]:
        return list(self.servers)

    def list_resources(self, server_name: str | None = None) -> list[McpResource]:
        resources: list[McpResource] = []
        for server in self.servers:
            if server_name and server.name != server_name:
                continue
            resources.extend(server.resources)
        return resources

    def read_resource(self, uri: str) -> dict[str, Any]:
        for resource in self.list_resources():
            if resource.uri != uri:
                continue
            if resource.kind == "file":
                if not resource.path:
                    raise ValueError(f"resource missing path: {uri}")
                path = (self.workspace_root / resource.path).resolve()
                return {
                    "server": resource.server,
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": resource.description,
                    "content": path.read_text(encoding="utf-8", errors="replace"),
                }
            return {
                "server": resource.server,
                "uri": resource.uri,
                "name": resource.name,
                "description": resource.description,
                "content": resource.content or "",
            }
        raise KeyError(uri)
