from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .commands import Command, CommandRegistry
from .tools import Tool, ToolRegistry, ToolUseContext


@dataclass(frozen=True)
class PluginManifest:
    name: str
    description: str
    commands: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    hooks: dict[str, list[dict[str, Any]]]
    workflows: list[dict[str, Any]]


class PluginManager:
    def __init__(self, manifests: list[PluginManifest]) -> None:
        self.manifests = manifests

    @classmethod
    def from_directory(cls, path: Path) -> "PluginManager":
        manifests: list[PluginManifest] = []
        if path.exists():
            for file in sorted(path.glob("*.json")):
                payload = json.loads(file.read_text(encoding="utf-8"))
                manifests.append(
                    PluginManifest(
                        name=str(payload["name"]),
                        description=str(payload.get("description", "")),
                        commands=list(payload.get("commands", [])),
                        tools=list(payload.get("tools", [])),
                        hooks=dict(payload.get("hooks", {})),
                        workflows=list(payload.get("workflows", [])),
                    )
                )
        return cls(manifests)

    def list(self) -> list[PluginManifest]:
        return list(self.manifests)

    def register(self, tools: ToolRegistry, commands: CommandRegistry) -> None:
        for manifest in self.manifests:
            for tool_spec in manifest.tools:
                tools.register(self._build_tool(manifest, tool_spec))
            for cmd_spec in manifest.commands:
                commands.register(self._build_command(manifest, cmd_spec))

    def workflow_names(self) -> list[str]:
        names: list[str] = []
        for manifest in self.manifests:
            for workflow in manifest.workflows:
                names.append(str(workflow["name"]))
        return sorted(names)

    async def run_hooks(
        self,
        event: str,
        *,
        ctx: ToolUseContext,
        args: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> list[str]:
        outputs: list[str] = []
        for manifest in self.manifests:
            for hook in manifest.hooks.get(event, []):
                result = await self._run_action(
                    manifest,
                    hook.get("action", {}),
                    ctx=ctx,
                    args=args,
                    payload=payload,
                    subject=hook.get("name", event),
                )
                if result:
                    outputs.append(result)
        return outputs

    async def run_workflow(
        self,
        name: str,
        *,
        ctx: ToolUseContext,
        args: list[str] | None = None,
    ) -> list[str]:
        for manifest in self.manifests:
            for workflow in manifest.workflows:
                if workflow.get("name") != name:
                    continue
                outputs: list[str] = []
                for step in workflow.get("steps", []):
                    result = await self._run_action(
                        manifest,
                        step.get("action", {}),
                        ctx=ctx,
                        args=args,
                        payload=step.get("payload", {}),
                        subject=step.get("name", name),
                    )
                    if result:
                        outputs.append(result)
                return outputs
        raise KeyError(name)

    def _render_template(
        self,
        template: str,
        *,
        args: list[str] | None = None,
        payload: dict[str, Any] | None = None,
        ctx: ToolUseContext,
    ) -> str:
        values: dict[str, Any] = {
            "cwd": str(ctx.cwd),
            "args": args or [],
            "args_joined": " ".join(args or []),
        }
        if payload:
            values.update(payload)
        return template.format(**values)

    async def _run_action(
        self,
        manifest: PluginManifest,
        action: dict[str, Any],
        *,
        ctx: ToolUseContext,
        args: list[str] | None = None,
        payload: dict[str, Any] | None = None,
        subject: str = "",
    ) -> str:
        action_type = str(action.get("type", "template_response"))
        if action_type == "template_response":
            return self._render_template(
                str(action.get("template", "")),
                args=args,
                payload=payload,
                ctx=ctx,
            )
        if action_type == "shell":
            command = self._render_template(
                str(action.get("command", "")),
                args=args,
                payload=payload,
                ctx=ctx,
            )
            result = await ctx.tools.invoke(
                "shell_command",
                {"command": command, "timeout": float(action.get("timeout", 30))},
                ctx,
            )
            if not result["ok"]:
                return result["error"]
            tool_payload = result["result"]
            stdout = (tool_payload.get("stdout") or "").strip()
            stderr = (tool_payload.get("stderr") or "").strip()
            parts = [f"plugin={manifest.name}", f"action={subject or action_type}"]
            if stdout:
                parts.append(stdout)
            if stderr:
                parts.append(f"stderr:\n{stderr}")
            return "\n".join(parts)
        if action_type == "memory_add":
            text = self._render_template(
                str(action.get("text", "")),
                args=args,
                payload=payload,
                ctx=ctx,
            )
            result = await ctx.tools.invoke("memory_add", {"text": text}, ctx)
            if not result["ok"]:
                return result["error"]
            return f"memory_saved:{result['result']['id']}"
        if action_type == "tool":
            tool_name = str(action.get("tool", "")).strip()
            tool_payload = dict(payload or {})
            result = await ctx.tools.invoke(tool_name, tool_payload, ctx)
            return json.dumps(result, ensure_ascii=False)
        raise ValueError(f"unsupported plugin action: {action_type}")

    def _build_tool(self, manifest: PluginManifest, spec: dict[str, Any]) -> Tool:
        async def handler(payload: dict[str, Any], ctx: ToolUseContext) -> dict[str, Any]:
            content = await self._run_action(
                manifest,
                spec.get("action", {}),
                ctx=ctx,
                payload=payload,
                subject=str(spec.get("name", "")),
            )
            return {
                "plugin": manifest.name,
                "tool": spec["name"],
                "content": content,
            }

        return Tool(
            name=str(spec["name"]),
            description=str(spec.get("description", f"{manifest.name} plugin tool")),
            input_schema=dict(spec.get("input_schema", {"type": "object", "properties": {}})),
            handler=handler,
        )

    def _build_command(self, manifest: PluginManifest, spec: dict[str, Any]) -> Command:
        async def handler(args: list[str], ctx: ToolUseContext) -> str:
            return await self._run_action(
                manifest,
                spec.get("action", {}),
                ctx=ctx,
                args=args,
                subject=str(spec.get("name", "")),
            )

        return Command(
            name=str(spec["name"]),
            description=str(spec.get("description", f"{manifest.name} plugin command")),
            handler=handler,
        )
