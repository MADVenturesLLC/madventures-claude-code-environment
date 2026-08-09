from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from madclaude.artifacts import read_canonical_artifact, render_canonical_artifact
from madclaude.errors import EvidenceError


class CanonicalArtifactTests(unittest.TestCase):
    def test_envelope_round_trip_and_tamper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "VERIFICATION.md"
            path.write_text(
                render_canonical_artifact(
                    "VERIFICATION",
                    {"status": "passed"},
                    workflow_id="workflow-1",
                    repository="/repo",
                    route="verify",
                    base_sha="a" * 40,
                    head_sha="b" * 40,
                    status="passed",
                ),
                encoding="utf-8",
            )
            metadata, payload = read_canonical_artifact(path)
            self.assertEqual(metadata["head_sha"], "b" * 40)
            self.assertEqual(payload, {"status": "passed"})
            path.write_text(path.read_text(encoding="utf-8").replace('"passed"', '"failed"'), encoding="utf-8")
            with self.assertRaises(EvidenceError):
                read_canonical_artifact(path)


if __name__ == "__main__":
    unittest.main()
