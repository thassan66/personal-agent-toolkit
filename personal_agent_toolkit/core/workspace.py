from __future__ import annotations

from pathlib import Path
from typing import Iterable


class WorkspaceError(ValueError):
    pass


class Workspace:
    IGNORED_DIR_NAMES = {".git", ".hg", ".svn", ".venv", "node_modules", "__pycache__"}
    IGNORED_FILE_SUFFIXES = {".pyc", ".pyo"}

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def resolve_path(self, raw: str | Path) -> Path:
        raw_path = Path(raw)
        candidate = (
            (self.root / raw_path).resolve()
            if not raw_path.is_absolute()
            else raw_path.resolve()
        )
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError(f"path escapes workspace: {candidate}") from exc
        return candidate

    def ensure_parent(self, raw: str | Path) -> Path:
        path = self.resolve_path(raw)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def read_text(self, raw: str | Path, *, max_bytes: int = 100_000) -> str:
        path = self.resolve_path(raw)
        data = path.read_bytes()[:max_bytes]
        return data.decode("utf-8", errors="replace")

    def write_text(self, raw: str | Path, content: str, *, append: bool = False) -> Path:
        path = self.ensure_parent(raw)
        mode = "a" if append else "w"
        with path.open(mode, encoding="utf-8") as handle:
            handle.write(content)
        return path

    def list_entries(
        self,
        raw: str | Path = ".",
        *,
        recursive: bool = False,
        max_entries: int = 200,
    ) -> list[dict[str, object]]:
        path = self.resolve_path(raw)
        if not path.exists():
            raise WorkspaceError(f"path not found: {path}")
        iterator = path.rglob("*") if recursive else path.iterdir()
        entries: list[dict[str, object]] = []
        for item in iterator:
            if len(entries) >= max_entries:
                break
            try:
                rel = item.relative_to(self.root).as_posix()
            except ValueError:
                rel = str(item)
            entries.append(
                {
                    "path": rel,
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None,
                }
            )
        return entries

    def glob(self, pattern: str, *, max_entries: int = 200) -> list[str]:
        matches: list[str] = []
        for item in self.root.glob(pattern):
            if len(matches) >= max_entries:
                break
            matches.append(item.relative_to(self.root).as_posix())
        return sorted(matches)

    def grep(
        self,
        pattern: str,
        *,
        root: str | Path = ".",
        case_sensitive: bool = False,
        max_results: int = 100,
        include_extensions: Iterable[str] | None = None,
    ) -> list[dict[str, object]]:
        base = self.resolve_path(root)
        if not base.exists():
            raise WorkspaceError(f"path not found: {base}")

        needle = pattern if case_sensitive else pattern.lower()
        allowed = {ext.lower() for ext in include_extensions or []}
        results: list[dict[str, object]] = []

        for file in base.rglob("*"):
            if len(results) >= max_results:
                break
            if not file.is_file():
                continue
            if any(part in self.IGNORED_DIR_NAMES for part in file.parts):
                continue
            if file.suffix.lower() in self.IGNORED_FILE_SUFFIXES:
                continue
            if allowed and file.suffix.lower() not in allowed:
                continue

            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for line_no, line in enumerate(text.splitlines(), start=1):
                haystack = line if case_sensitive else line.lower()
                if needle in haystack:
                    results.append(
                        {
                            "path": file.relative_to(self.root).as_posix(),
                            "line": line_no,
                            "text": line,
                        }
                    )
                    if len(results) >= max_results:
                        break
        return results

    def replace_text(
        self,
        raw: str | Path,
        *,
        old: str,
        new: str,
        count: int = -1,
    ) -> dict[str, object]:
        path = self.resolve_path(raw)
        original = path.read_text(encoding="utf-8")
        replacements = original.count(old) if count < 0 else min(original.count(old), count)
        if replacements == 0:
            raise WorkspaceError(f"text not found in {path}")
        updated = original.replace(old, new, count)
        path.write_text(updated, encoding="utf-8")
        return {
            "path": path.relative_to(self.root).as_posix(),
            "replacements": replacements,
        }
