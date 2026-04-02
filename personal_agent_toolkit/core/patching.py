from __future__ import annotations

import difflib
from pathlib import Path

from .workspace import Workspace


def replace_block(
    workspace: Workspace,
    path: str | Path,
    *,
    old: str,
    new: str,
) -> dict[str, object]:
    file_path = workspace.resolve_path(path)
    original = file_path.read_text(encoding="utf-8")
    if old not in original:
        raise ValueError(f"block not found in {file_path}")
    updated = original.replace(old, new, 1)
    file_path.write_text(updated, encoding="utf-8")
    return {
        "path": file_path.relative_to(workspace.root).as_posix(),
        "replacements": 1,
    }


def insert_after(
    workspace: Workspace,
    path: str | Path,
    *,
    anchor: str,
    content: str,
) -> dict[str, object]:
    file_path = workspace.resolve_path(path)
    original = file_path.read_text(encoding="utf-8")
    if anchor not in original:
        raise ValueError(f"anchor not found in {file_path}")
    updated = original.replace(anchor, anchor + content, 1)
    file_path.write_text(updated, encoding="utf-8")
    return {
        "path": file_path.relative_to(workspace.root).as_posix(),
        "inserted": True,
    }


def preview_replace_block(
    workspace: Workspace,
    path: str | Path,
    *,
    old: str,
    new: str,
) -> str:
    file_path = workspace.resolve_path(path)
    original = file_path.read_text(encoding="utf-8")
    if old not in original:
        raise ValueError(f"block not found in {file_path}")
    updated = original.replace(old, new, 1)
    diff = difflib.unified_diff(
        original.splitlines(),
        updated.splitlines(),
        fromfile=f"{file_path.relative_to(workspace.root).as_posix()}:before",
        tofile=f"{file_path.relative_to(workspace.root).as_posix()}:after",
        lineterm="",
    )
    return "\n".join(diff)
