from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    description: str
    model: Optional[str] = None
    system_prompt: str = ""


class AgentRegistry:
    def __init__(self, agents: Iterable[AgentDefinition] = ()) -> None:
        self._agents: Dict[str, AgentDefinition] = {
            agent.name: agent for agent in agents
        }

    @classmethod
    def from_directory(cls, path: Path) -> "AgentRegistry":
        agents = []
        if path.exists():
            for file in sorted(path.glob("*.json")):
                payload = json.loads(file.read_text(encoding="utf-8"))
                agents.append(
                    AgentDefinition(
                        name=str(payload["name"]),
                        description=str(payload.get("description", "")),
                        model=payload.get("model"),
                        system_prompt=str(payload.get("system_prompt", "")),
                    )
                )
        if not agents:
            agents.append(
                AgentDefinition(
                    name="default",
                    description="Fallback personal agent",
                    model=None,
                    system_prompt="You are a helpful personal coding agent.",
                )
            )
        return cls(agents)

    def get(self, name: str) -> Optional[AgentDefinition]:
        return self._agents.get(name)

    def list(self) -> list[AgentDefinition]:
        return [self._agents[name] for name in sorted(self._agents)]
