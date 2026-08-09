from __future__ import annotations

import unittest
from pathlib import Path


class AuthoritativeEngineTests(unittest.TestCase):
    def test_no_executable_javascript_orchestration_remains(self) -> None:
        root = Path(__file__).resolve().parents[2]
        competing = sorted((root / "project" / ".claude" / "workflows").glob("*.js"))
        competing += sorted((root / "plugin" / "madventures-founderos" / "workflows").glob("*.js"))
        self.assertEqual(competing, [], "Python must be the only executable orchestration engine")


if __name__ == "__main__":
    unittest.main()
