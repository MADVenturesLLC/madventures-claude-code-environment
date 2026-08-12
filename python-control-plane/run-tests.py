#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = str(ROOT / "src")
TESTS = str(ROOT / "tests")
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.path.insert(0, SRC)
sys.path.insert(0, TESTS)

# ---------------------------------------------------------------------------
# Installed-layout test allowlist.
#
# These modules — and ONLY these modules — run when --installed is passed.
# They have zero dependencies on package-root-only resources (scripts/,
# plugin/, MANIFEST.json) and zero transitive imports from source-only
# modules.  Adding a module here is an explicit act; a new test module that
# requires package-root assets or imports a source-only module must NOT be
# added here — it belongs in the default (source/archive) suite only.
#
# The module count and test-case count are asserted at runtime so accidental
# exclusions or inclusions fail loudly instead of silently passing.
# ---------------------------------------------------------------------------
INSTALLED_MODULES = frozenset({
    "test_approval",
    "test_artifacts",
    "test_auth",
    "test_authoritative_engine",
    "test_backend",
    "test_baseline_policy_matrix",
    "test_evidence",
    "test_evidence_hashing",
    "test_git",
    "test_guard",
    "test_guard_adversarial",
    "test_hooks",
    "test_safe_read",
    "test_schema_keyword_coverage",
    "test_schemas",
    "test_secrets_patterns",
    "test_term",
    "test_workflow",
})
INSTALLED_MODULE_COUNT = 18

# Exact number of test cases the installed-compatible modules produce.
# If a test is added or removed from any installed module, this must be
# updated deliberately — drift fails loudly so accidental exclusions or
# inclusions cannot silently pass.
# A10-A: +12 (test_secrets_patterns) +7 (test_baseline_policy_matrix) = 163 -> 182.
INSTALLED_TEST_CASE_COUNT = 182

# The six source-only modules: they require package-root resources
# (scripts/, plugin/, MANIFEST.json) or transitively import a module that
# does.  They run only during source-tree and archive validation, never
# during installed-layout validation.  They are not skipped — they are not
# selected.
KNOWN_SOURCE_ONLY = frozenset({
    "test_wheelhouse_script",
    "test_mcp_release_install",
    "test_mcp_installed_copy",
    "test_plugin_parity",
    "test_mcp_lifecycle",
    "test_mcp_server",
})


def _installed_suite() -> unittest.TestSuite:
    """Build a suite from the explicit installed-compatible allowlist only."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in sorted(INSTALLED_MODULES):
        suite.addTests(loader.loadTestsFromName(name))
    return suite


def _default_suite() -> unittest.TestSuite:
    """Discover and run every test_* module — the source/archive suite."""
    return unittest.defaultTestLoader.discover(TESTS, pattern="test_*.py")


if __name__ == "__main__":
    installed_mode = "--installed" in sys.argv

    if installed_mode:
        # Assert the allowlist hasn't drifted — a new test module that someone
        # forgot to classify, or a removed module, must fail here.
        available = {
            path.stem
            for path in Path(TESTS).glob("test_*.py")
            if path.is_file()
        }
        missing_from_tree = sorted(INSTALLED_MODULES - available)
        if missing_from_tree:
            raise SystemExit(
                f"installed allowlist references non-existent modules: {missing_from_tree}"
            )
        extra_in_tree = sorted(available - INSTALLED_MODULES)
        # Any module not in the installed allowlist must be in the known
        # source-only set.  An unclassified module is an error.
        unclassified = sorted(set(extra_in_tree) - KNOWN_SOURCE_ONLY)
        if unclassified:
            raise SystemExit(
                f"unclassified test modules exist but are not in the installed "
                f"allowlist or the known source-only set: {unclassified}. "
                f"Classify them explicitly before proceeding."
            )
        if len(INSTALLED_MODULES) != INSTALLED_MODULE_COUNT:
            raise SystemExit(
                f"installed allowlist count drift: expected {INSTALLED_MODULE_COUNT}, "
                f"got {len(INSTALLED_MODULES)}"
            )

        suite = _installed_suite()
        actual_count = suite.countTestCases()
        if actual_count != INSTALLED_TEST_CASE_COUNT:
            raise SystemExit(
                f"installed test-case count drift: expected {INSTALLED_TEST_CASE_COUNT}, "
                f"got {actual_count}"
            )
    else:
        suite = _default_suite()

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)