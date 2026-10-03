"""Version-consistency tripwire across the package identity surfaces.

The package asserts its version in several independent places (VERSION,
python-control-plane/pyproject.toml, python-control-plane/src/madclaude/version.py,
the plugin mirror, plugin.json). History shows a manual bump process drifts
silently; this module fails loudly instead. Runtime version derivation was
rejected by design: an installed-layout upward walk can read a HOST
repository's VERSION file, producing false identity.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _version_literal(rel: str) -> str:
    text = _read(rel)
    match = re.search(r'"version"\s*:\s*"(\d+\.\d+\.\d+)"', text)  # JSON
    if match is None:
        match = re.search(r'^version\s*=\s*"(\d+\.\d+\.\d+)"', text, re.MULTILINE)  # TOML
    assert match is not None, f"no version literal found in {rel}"
    return match.group(1)


class VersionConsistencyTests(unittest.TestCase):
    def test_all_identity_surfaces_match_version_file(self) -> None:
        declared = _read("VERSION").strip()
        self.assertRegex(declared, r"^\d+\.\d+\.\d+$")
        pyproject = _version_literal("python-control-plane/pyproject.toml")
        self.assertEqual(
            pyproject,
            declared,
            "python-control-plane/pyproject.toml version drifted from VERSION",
        )
        plugin_json = _version_literal(
            "plugin/madventures-founderos/.claude-plugin/plugin.json"
        )
        self.assertEqual(
            plugin_json,
            declared,
            "plugin.json version drifted from VERSION",
        )

    def test_control_plane_version_module_matches_version_file(self) -> None:
        declared = _read("VERSION").strip()
        source = _read("python-control-plane/src/madclaude/version.py")
        match = re.search(r'__version__\s*=\s*"(\d+\.\d+\.\d+)"', source)
        assert match is not None
        self.assertEqual(match.group(1), declared)
        # The plugin mirror must ship the identical module (byte parity is
        # enforced elsewhere; this asserts the value in the mirrored copy).
        mirror = _read(
            "plugin/madventures-founderos/python-control-plane/src/madclaude/version.py"
        )
        mirror_match = re.search(r'__version__\s*=\s*"(\d+\.\d+\.\d+)"', mirror)
        assert mirror_match is not None
        self.assertEqual(mirror_match.group(1), declared)


if __name__ == "__main__":
    unittest.main()
