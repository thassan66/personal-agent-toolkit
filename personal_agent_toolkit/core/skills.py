from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    prompt: str
    path: Path


class SkillRegistry:
    def __init__(self, skills: list[Skill]) -> None:
        self._skills = {skill.name: skill for skill in skills}

    @classmethod
    def from_directory(cls, path: Path) -> "SkillRegistry":
        skills: list[Skill] = []
        if path.exists():
            for file in sorted(path.glob("*.md")):
                prompt = file.read_text(encoding="utf-8")
                name, description = _parse_skill_metadata(file, prompt)
                skills.append(
                    Skill(
                        name=name,
                        description=description,
                        prompt=prompt.strip(),
                        path=file.resolve(),
                    )
                )
        return cls(skills)

    def list(self) -> list[Skill]:
        return [self._skills[name] for name in sorted(self._skills)]

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)


def _parse_skill_metadata(path: Path, text: str) -> tuple[str, str]:
    lines = [line.strip() for line in text.splitlines()]
    heading = next((line for line in lines if line.startswith("#")), "")
    name = heading.lstrip("# ").strip() if heading else path.stem.replace("_", "-")
    description = ""
    for line in lines:
        if not line or line.startswith("#"):
            continue
        description = line
        break
    return name, description or "No description provided."
