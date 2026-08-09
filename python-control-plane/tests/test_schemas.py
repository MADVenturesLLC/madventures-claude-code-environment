from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from madclaude.schemas import SCHEMAS, export_schemas, schema_for, validate_instance


class SchemaTests(unittest.TestCase):
    def test_all_schemas_export_and_parse(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)
            export_schemas(destination)
            self.assertEqual(len(list(destination.glob("*.schema.json"))), len(SCHEMAS))
            for path in destination.glob("*.schema.json"):
                self.assertIsInstance(json.loads(path.read_text()), dict)

    def test_minimal_plan_validation(self) -> None:
        value = {
            "task_id": "TASK-1", "repository": "owner/repo", "base_sha": "0" * 40,
            "risk_class": "medium", "recommended_builder": "sonnet",
            "builder_justification": "bounded change", "eligible_fallbacks": ["opus"],
            "founder_gate_required": True, "governance_references": [], "unknowns": [],
            "status": "ready", "summary": "ok", "repository_findings": [],
            "plan_steps": [{"step": "one", "files": [], "rationale": "why", "acceptance": []}],
            "acceptance_mapping": [], "verification_plan": [], "risks": [], "stop_conditions": [],
            "founder_decisions_required": [], "confidence": "high",
        }
        self.assertEqual(validate_instance(value, schema_for("plan")), [])
        del value["recommended_builder"]
        self.assertTrue(validate_instance(value, schema_for("plan")))
        value["recommended_builder"] = "sonnet"
        value["unexpected"] = True
        self.assertTrue(validate_instance(value, schema_for("plan")))


if __name__ == "__main__":
    unittest.main()
