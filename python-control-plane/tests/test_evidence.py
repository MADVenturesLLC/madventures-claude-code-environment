from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from madclaude.evidence import EvidenceBundle, redact, sha256_file


class EvidenceTests(unittest.TestCase):
    def test_redaction_manifest_and_private_permissions(self) -> None:
        self.assertEqual(redact({"api_key": "secret"})["api_key"], "[REDACTED]")
        self.assertNotIn("sk-ant-secret", redact("token sk-ant-secret123"))
        with tempfile.TemporaryDirectory() as temp:
            bundle = EvidenceBundle(Path(temp), "test")
            payload_path = bundle.write_json("payload.json", {"ANTHROPIC_API_KEY": "do-not-store", "ok": True})
            manifest = bundle.finalize("completed")
            payload = payload_path.read_text()
            self.assertNotIn("do-not-store", payload)
            parsed = json.loads(manifest.read_text())
            self.assertEqual(parsed["status"], "completed")
            self.assertTrue(parsed["files"])
            self.assertEqual(len(sha256_file(payload_path)), 64)
            if os.name != "nt":
                self.assertEqual(payload_path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(bundle.path.stat().st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
