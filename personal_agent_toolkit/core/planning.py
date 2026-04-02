from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class PlanStep:
    id: str
    text: str
    status: str = "pending"


class PlanStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"title": "", "steps": []})

    def get(self) -> dict[str, object]:
        return self._read()

    def set_title(self, title: str) -> dict[str, object]:
        data = self._read()
        data["title"] = title
        self._write(data)
        return data

    def add_step(self, text: str) -> PlanStep:
        data = self._read()
        step = PlanStep(id=uuid.uuid4().hex[:10], text=text)
        data["steps"].append(asdict(step))
        self._write(data)
        return step

    def update_step(self, step_id: str, status: str) -> dict[str, object]:
        data = self._read()
        for step in data["steps"]:
            if step["id"] == step_id:
                step["status"] = status
                self._write(data)
                return step
        raise KeyError(step_id)

    def clear(self) -> None:
        self._write({"title": "", "steps": []})

    def _read(self) -> dict[str, object]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, object]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
