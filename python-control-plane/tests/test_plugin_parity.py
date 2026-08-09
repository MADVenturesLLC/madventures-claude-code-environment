"""A9-04: source/plugin policy-module byte parity as a release-blocking gate.

Runs the SAME check as scripts/validate-config.py (the module is loaded from
the package root so the dependency-free harness and the validator share one
code path).
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_validator():
    spec = importlib.util.spec_from_file_location("mad_validate_config", ROOT / "scripts" / "validate-config.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()
POLICY_MODULES = VALIDATOR._policy_modules()
SOURCE = ROOT / "python-control-plane" / "src" / "madclaude"
BUNDLED_REL = Path("plugin") / "madventures-founderos" / "python-control-plane" / "src" / "madclaude"


def _fake_root(base: Path) -> Path:
    """Build a minimal canonical+plugin tree in parity, for negative mutation."""
    source = base / "python-control-plane" / "src" / "madclaude"
    bundled = base / BUNDLED_REL
    source.mkdir(parents=True)
    bundled.mkdir(parents=True)
    for name in POLICY_MODULES:
        content = (SOURCE / name).read_bytes()
        (source / name).write_bytes(content)
        (bundled / name).write_bytes(content)
    return base


class PluginParityTests(unittest.TestCase):
    def test_policy_modules_byte_identical(self) -> None:
        self.assertEqual(VALIDATOR.plugin_policy_module_drift(ROOT), [])

    def test_no_extra_plugin_modules(self) -> None:
        bundled = ROOT / BUNDLED_REL
        actual = {path.name for path in bundled.glob("*.py")}
        self.assertEqual(actual, set(POLICY_MODULES))

    def test_mutated_plugin_module_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = _fake_root(Path(temp))
            target = root / BUNDLED_REL / "guard.py"
            target.write_bytes(target.read_bytes() + b"\n# tampered\n")
            drift = VALIDATOR.plugin_policy_module_drift(root)
            self.assertTrue(any("guard.py" in problem for problem in drift), drift)

    def test_extra_plugin_module_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = _fake_root(Path(temp))
            (root / BUNDLED_REL / "smuggled.py").write_bytes(b"# not a policy module\n")
            drift = VALIDATOR.plugin_policy_module_drift(root)
            self.assertTrue(any("smuggled.py" in problem for problem in drift), drift)

    def test_missing_plugin_module_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = _fake_root(Path(temp))
            (root / BUNDLED_REL / "hook_policy.py").unlink()
            drift = VALIDATOR.plugin_policy_module_drift(root)
            self.assertTrue(any("hook_policy.py" in problem for problem in drift), drift)


class PluginClosureTests(unittest.TestCase):
    def test_hook_import_closure_is_shipped(self) -> None:
        closure = set(VALIDATOR._policy_closure())
        self.assertIn("safe_read.py", closure)
        self.assertLessEqual(closure, set(POLICY_MODULES))

    def test_fresh_plugin_hook_import_and_smoke(self) -> None:
        """Import the hook entry point from a FRESH copy of the bundled plugin
        (never the repo source tree) and run a portable smoke evaluation.
        Proves the bundled policy set is self-contained — a missing closure
        module fails here as an ImportError, not in a user's hook."""
        import json
        import os
        import shutil
        import subprocess

        with tempfile.TemporaryDirectory() as temp:
            fresh = Path(temp) / "fresh-plugin"
            shutil.copytree(ROOT / BUNDLED_REL.parents[1], fresh)
            probe = (
                "import json, sys\n"
                "sys.path.insert(0, sys.argv[1])\n"
                "from madclaude import hook_cli, hook_policy, safe_read\n"
                "inactive = hook_cli.evaluate_input({'tool_name': 'Read'})\n"
                "assert inactive == {}, inactive\n"
                "import os\n"
                "os.environ['MADCLAUDE_CONTROL_PLANE_ACTIVE'] = '1'\n"
                "os.environ.pop('MADCLAUDE_REPO_ROOT', None)\n"
                "denied = hook_cli.evaluate_input({'tool_name': 'Read', 'tool_input': {'file_path': 'x'}})\n"
                "assert denied['hookSpecificOutput']['permissionDecision'] == 'deny', denied\n"
                "print('fresh plugin hook smoke ok')\n"
            )
            completed = subprocess.run(
                [sys.executable, "-c", probe, str(fresh / "src")],
                capture_output=True,
                text=True,
                check=False,
                env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("fresh plugin hook smoke ok", completed.stdout)


if __name__ == "__main__":
    unittest.main()
