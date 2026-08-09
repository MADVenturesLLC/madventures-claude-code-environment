from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from madclaude import safe_read
from madclaude.evidence import EVIDENCE_SOURCE_CAP_BYTES, hash_evidence_source
from madclaude.errors import EvidenceError, SafeReadError

CAP = EVIDENCE_SOURCE_CAP_BYTES


@unittest.skipUnless(os.name == "posix", "descriptor-based governed reads require POSIX")
class EvidenceHashingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name).resolve()
        self.content = b"evidence-payload\n"
        (self.root / "source.txt").write_bytes(self.content)
        self.computed = hashlib.sha256(self.content).hexdigest()
        self.other_hash = hashlib.sha256(b"other").hexdigest()
        self.fd = safe_read.open_root(self.root)

    def tearDown(self) -> None:
        os.close(self.fd)
        self._temp.cleanup()

    def test_truth_table_row_1_oversized_with_declared(self) -> None:
        (self.root / "big.bin").write_bytes(b"x" * (CAP + 1))
        self.assertEqual(
            hash_evidence_source(self.fd, "big.bin", self.other_hash),
            {
                "source_sha256": None,
                "declared_manifest_sha256": self.other_hash,
                "hash_provenance": "manifest_declared",
                "target_match": "not_checked",
                "verified": False,
            },
        )

    def test_truth_table_row_2_oversized_without_declared(self) -> None:
        (self.root / "big.bin").write_bytes(b"x" * (CAP + 2))
        self.assertEqual(
            hash_evidence_source(self.fd, "big.bin", None),
            {
                "source_sha256": None,
                "declared_manifest_sha256": None,
                "hash_provenance": "none",
                "target_match": "not_checked",
                "verified": False,
            },
        )

    def test_truth_table_row_3_in_limit_declared_matches(self) -> None:
        self.assertEqual(
            hash_evidence_source(self.fd, "source.txt", self.computed),
            {
                "source_sha256": self.computed,
                "declared_manifest_sha256": self.computed,
                "hash_provenance": "computed",
                "target_match": "match",
                "verified": True,
            },
        )

    def test_truth_table_row_4_in_limit_declared_mismatches(self) -> None:
        self.assertEqual(
            hash_evidence_source(self.fd, "source.txt", self.other_hash),
            {
                "source_sha256": self.computed,
                "declared_manifest_sha256": self.other_hash,
                "hash_provenance": "computed",
                "target_match": "mismatch",
                "verified": False,
            },
        )

    def test_truth_table_row_5_in_limit_no_declared(self) -> None:
        self.assertEqual(
            hash_evidence_source(self.fd, "source.txt", None),
            {
                "source_sha256": self.computed,
                "declared_manifest_sha256": None,
                "hash_provenance": "computed",
                "target_match": "no_target",
                "verified": False,
            },
        )

    def test_cap_plus_one_bound(self) -> None:
        (self.root / "exact.bin").write_bytes(b"x" * CAP)
        row = hash_evidence_source(self.fd, "exact.bin", None)
        self.assertEqual(row["hash_provenance"], "computed")
        self.assertEqual(row["source_sha256"], hashlib.sha256(b"x" * CAP).hexdigest())

        (self.root / "over.bin").write_bytes(b"x" * (CAP + 1))
        row = hash_evidence_source(self.fd, "over.bin", None)
        self.assertEqual(row["target_match"], "not_checked")
        self.assertIsNone(row["source_sha256"])

    def test_oversized_never_streams_past_cap_plus_one(self) -> None:
        (self.root / "huge.bin").write_bytes(b"x" * (CAP + 2))

        def spy_read(fd, size):
            raise AssertionError("oversized sources must not be read at all")

        with mock.patch.object(os, "read", spy_read):
            row = hash_evidence_source(self.fd, "huge.bin", None)
        self.assertIsNone(row["source_sha256"])
        self.assertEqual(row["target_match"], "not_checked")

    def test_read_bounded_to_cap_plus_one(self) -> None:
        captured: list[int] = []
        real_read = os.read

        def spy(fd, size):
            captured.append(size)
            return real_read(fd, size)

        with mock.patch.object(os, "read", spy):
            row = hash_evidence_source(self.fd, "source.txt", None)
        # Every single read request is bounded by the cap + 1 budget, and the
        # hash is computed from the one buffer those reads produced.
        self.assertTrue(captured)
        self.assertTrue(all(size <= CAP + 1 for size in captured))
        self.assertEqual(row["source_sha256"], self.computed)

    def test_declared_never_presented_as_computed(self) -> None:
        (self.root / "big.bin").write_bytes(b"x" * (CAP + 1))
        row = hash_evidence_source(self.fd, "big.bin", self.other_hash)
        self.assertEqual(row["hash_provenance"], "manifest_declared")
        self.assertIsNone(row["source_sha256"])
        self.assertFalse(row["verified"])

    def test_malformed_declared_hash_errors(self) -> None:
        for bad in ("not-a-hash", "A" * 64, "f" * 63, "f" * 65):
            with self.subTest(declared=bad):
                with self.assertRaises(EvidenceError):
                    hash_evidence_source(self.fd, "source.txt", bad)

    def test_read_interrupted_errors(self) -> None:
        with mock.patch.object(os, "read", side_effect=OSError("interrupted")):
            with self.assertRaises(EvidenceError):
                hash_evidence_source(self.fd, "source.txt", None)

    def test_missing_source_errors_not_fabricated_row(self) -> None:
        with self.assertRaises(EvidenceError):
            hash_evidence_source(self.fd, "missing.txt", None)

    def test_symlinked_source_errors(self) -> None:
        os.symlink("source.txt", self.root / "link.txt")
        with self.assertRaises(EvidenceError):
            hash_evidence_source(self.fd, "link.txt", None)


if __name__ == "__main__":
    unittest.main()
