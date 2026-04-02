from __future__ import annotations

import difflib
import re
from pathlib import Path

from .workspace import Workspace


def unified_diff_for_files(
    workspace: Workspace,
    path_a: str | Path,
    path_b: str | Path,
    *,
    context_lines: int = 3,
) -> str:
    file_a = workspace.resolve_path(path_a)
    file_b = workspace.resolve_path(path_b)
    text_a = file_a.read_text(encoding="utf-8", errors="replace").splitlines()
    text_b = file_b.read_text(encoding="utf-8", errors="replace").splitlines()
    diff = difflib.unified_diff(
        text_a,
        text_b,
        fromfile=file_a.relative_to(workspace.root).as_posix(),
        tofile=file_b.relative_to(workspace.root).as_posix(),
        lineterm="",
        n=context_lines,
    )
    return "\n".join(diff)


def regex_replace_in_file(
    workspace: Workspace,
    path: str | Path,
    *,
    pattern: str,
    replacement: str,
    count: int = 0,
    flags: int = 0,
) -> dict[str, object]:
    file_path = workspace.resolve_path(path)
    original = file_path.read_text(encoding="utf-8")
    compiled = re.compile(pattern, flags)
    updated, replacements = compiled.subn(replacement, original, count=count)
    if replacements == 0:
        raise ValueError(f"pattern not found in {file_path}")
    file_path.write_text(updated, encoding="utf-8")
    return {
        "path": file_path.relative_to(workspace.root).as_posix(),
        "replacements": replacements,
    }
