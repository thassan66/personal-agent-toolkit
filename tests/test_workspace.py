from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from personal_agent_toolkit.core.workspace import Workspace, WorkspaceError


class WorkspaceTests(unittest.TestCase):
    def test_workspace_blocks_escape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Workspace(Path(td))
            with self.assertRaises(WorkspaceError):
                workspace.resolve_path("../outside.txt")

    def test_workspace_glob_and_grep(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            (root / "src" / "a.txt").write_text("alpha\nbeta\n", encoding="utf-8")
            (root / "src" / "b.py").write_text("print('alpha')\n", encoding="utf-8")

            workspace = Workspace(root)
            matches = workspace.glob("src/*")
            self.assertIn("src/a.txt", matches)
            self.assertIn("src/b.py", matches)

            grep_matches = workspace.grep("alpha", root="src", max_results=10)
            self.assertEqual(len(grep_matches), 2)


if __name__ == "__main__":
    unittest.main()
