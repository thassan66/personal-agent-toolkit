from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class MemoryEntry:
    id: str
    created_at: str
    text: str
    tags: list[str]


class MemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def add(self, text: str, *, tags: list[str] | None = None) -> MemoryEntry:
        entry = MemoryEntry(
            id=uuid.uuid4().hex[:12],
            created_at=datetime.now(timezone.utc).isoformat(),
            text=text,
            tags=list(tags or []),
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        return entry

    def list(self, *, limit: int = 20) -> list[MemoryEntry]:
        entries = self._load()
        return entries[-limit:]

    def search(self, query: str, *, limit: int = 20) -> list[MemoryEntry]:
        needle = query.lower()
        matches = [
            entry
            for entry in self._load()
            if needle in entry.text.lower()
            or any(needle in tag.lower() for tag in entry.tags)
        ]
        return matches[-limit:]

    def summary(self, *, limit: int = 5) -> str:
        entries = self.list(limit=limit)
        if not entries:
            return ""
        return "\n".join(f"- {entry.text}" for entry in entries)

    def _load(self) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            entries.append(
                MemoryEntry(
                    id=str(payload["id"]),
                    created_at=str(payload["created_at"]),
                    text=str(payload["text"]),
                    tags=list(payload.get("tags", [])),
                )
            )
        return entries
