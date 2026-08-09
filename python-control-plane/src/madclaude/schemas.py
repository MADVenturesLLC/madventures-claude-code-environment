from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from .errors import PolicyViolation

EVIDENCE_ITEM = {
    "type": "object",
    "additionalProperties": False,
    "required": ["claim", "evidence"],
    "properties": {
        "claim": {"type": "string"},
        "evidence": {"type": "string"},
        "source": {"type": ["string", "null"]},
    },
}

FINDING = {
    "type": "object",
    "additionalProperties": False,
    "required": ["severity", "title", "rationale", "evidence", "recommended_fix"],
    "properties": {
        "severity": {"type": "string", "enum": ["blocking", "critical", "high", "medium", "low", "note"]},
        "title": {"type": "string"},
        "file": {"type": ["string", "null"]},
        "line": {"type": ["integer", "null"], "minimum": 1},
        "rationale": {"type": "string"},
        "evidence": {"type": "string"},
        "recommended_fix": {"type": "string"},
    },
}

COMMAND_RESULT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["command", "status", "evidence"],
    "properties": {
        "command": {"type": "string"},
        "status": {"type": "string", "enum": ["passed", "failed", "blocked", "not_run"]},
        "exit_code": {"type": ["integer", "null"]},
        "evidence": {"type": "string"},
    },
}

CONFIDENCE = {"type": "string", "enum": ["certain", "high", "moderate", "low"]}

AUDIT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "executive_summary", "observed", "findings", "priority_actions", "unknowns", "confidence"],
    "properties": {
        "status": {"type": "string", "enum": ["complete", "partial", "blocked"]},
        "executive_summary": {"type": "string"},
        "observed": {"type": "array", "items": copy.deepcopy(EVIDENCE_ITEM)},
        "findings": {"type": "array", "items": copy.deepcopy(FINDING)},
        "priority_actions": {"type": "array", "items": {"type": "string"}},
        "unknowns": {"type": "array", "items": {"type": "string"}},
        "confidence": copy.deepcopy(CONFIDENCE),
    },
}

SCHEMAS: dict[str, dict[str, Any]] = {
    "plan": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "task_id", "repository", "base_sha", "risk_class", "recommended_builder",
            "builder_justification", "eligible_fallbacks", "founder_gate_required",
            "governance_references", "unknowns",
            "status", "summary", "repository_findings", "plan_steps", "acceptance_mapping",
            "verification_plan", "risks", "stop_conditions", "founder_decisions_required", "confidence"
        ],
        "properties": {
            "task_id": {"type": "string"},
            "repository": {"type": "string"},
            "base_sha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "risk_class": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
            "recommended_builder": {"type": "string"},
            "builder_justification": {"type": "string"},
            "eligible_fallbacks": {"type": "array", "items": {"type": "string"}},
            "founder_gate_required": {"type": "boolean"},
            "governance_references": {"type": "array", "items": {"type": "string"}},
            "unknowns": {"type": "array", "items": {"type": "string"}},
            "status": {"type": "string", "enum": ["ready", "blocked"]},
            "summary": {"type": "string"},
            "repository_findings": {"type": "array", "items": copy.deepcopy(EVIDENCE_ITEM)},
            "plan_steps": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["step", "files", "rationale", "acceptance"],
                    "properties": {
                        "step": {"type": "string"},
                        "files": {"type": "array", "items": {"type": "string"}},
                        "rationale": {"type": "string"},
                        "acceptance": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "acceptance_mapping": {"type": "array", "items": copy.deepcopy(EVIDENCE_ITEM)},
            "verification_plan": {"type": "array", "items": {"type": "string"}},
            "risks": {"type": "array", "items": {"type": "string"}},
            "stop_conditions": {"type": "array", "items": {"type": "string"}},
            "founder_decisions_required": {"type": "array", "items": {"type": "string"}},
            "confidence": copy.deepcopy(CONFIDENCE),
        },
    },
    "build": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "status", "summary", "approval_reference", "files_changed", "acceptance_results",
            "verification_expected", "residual_risks", "next_action", "confidence"
        ],
        "properties": {
            "status": {"type": "string", "enum": ["implemented", "partial", "blocked"]},
            "summary": {"type": "string"},
            "approval_reference": {"type": "string"},
            "files_changed": {"type": "array", "items": {"type": "string"}},
            "acceptance_results": {"type": "array", "items": copy.deepcopy(EVIDENCE_ITEM)},
            "verification_expected": {"type": "array", "items": {"type": "string"}},
            "residual_risks": {"type": "array", "items": {"type": "string"}},
            "next_action": {"type": "string"},
            "confidence": copy.deepcopy(CONFIDENCE),
        },
    },
    "verify": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "summary", "commands", "findings", "residual_risks", "confidence"],
        "properties": {
            "status": {"type": "string", "enum": ["passed", "failed", "blocked"]},
            "summary": {"type": "string"},
            "commands": {"type": "array", "items": copy.deepcopy(COMMAND_RESULT)},
            "findings": {"type": "array", "items": copy.deepcopy(FINDING)},
            "residual_risks": {"type": "array", "items": {"type": "string"}},
            "confidence": copy.deepcopy(CONFIDENCE),
        },
    },
    "review": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "disposition", "summary", "base_sha", "reviewed_sha", "findings", "verification_evidence",
            "residual_risks", "independence_statement", "confidence"
        ],
        "properties": {
            "disposition": {"type": "string", "enum": ["APPROVE", "REQUEST_CHANGES", "BLOCKED"]},
            "summary": {"type": "string"},
            "base_sha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "reviewed_sha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "findings": {"type": "array", "items": copy.deepcopy(FINDING)},
            "verification_evidence": {"type": "array", "items": copy.deepcopy(EVIDENCE_ITEM)},
            "residual_risks": {"type": "array", "items": {"type": "string"}},
            "independence_statement": {"type": "string"},
            "confidence": copy.deepcopy(CONFIDENCE),
        },
    },
    "release-readiness": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "disposition", "summary", "base_sha", "reviewed_sha", "gates", "blocking_findings",
            "residual_risks", "authority_boundary", "confidence"
        ],
        "properties": {
            "disposition": {"type": "string", "enum": ["READY", "NOT_READY", "BLOCKED"]},
            "summary": {"type": "string"},
            "base_sha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "reviewed_sha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "gates": {"type": "array", "items": copy.deepcopy(EVIDENCE_ITEM)},
            "blocking_findings": {"type": "array", "items": copy.deepcopy(FINDING)},
            "residual_risks": {"type": "array", "items": {"type": "string"}},
            "authority_boundary": {"type": "string"},
            "confidence": copy.deepcopy(CONFIDENCE),
        },
    },
    "repo-audit": copy.deepcopy(AUDIT_SCHEMA),
    "security-audit": copy.deepcopy(AUDIT_SCHEMA),
    "ui-review": copy.deepcopy(AUDIT_SCHEMA),
    "architecture-validation": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "disposition", "summary", "base_sha", "reviewed_sha", "invariants",
            "findings", "residual_risks", "authority_boundary", "confidence"
        ],
        "properties": {
            "disposition": {"type": "string", "enum": ["VALID", "INVALID", "BLOCKED"]},
            "summary": {"type": "string"},
            "base_sha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "reviewed_sha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "invariants": {"type": "array", "items": copy.deepcopy(EVIDENCE_ITEM)},
            "findings": {"type": "array", "items": copy.deepcopy(FINDING)},
            "residual_risks": {"type": "array", "items": {"type": "string"}},
            "authority_boundary": {"type": "string"},
            "confidence": copy.deepcopy(CONFIDENCE),
        },
    },
    "fix-until-green": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["round", "status", "diagnosis", "files_changed", "verification_expected", "residual_risks", "confidence"],
        "properties": {
            "round": {"type": "integer", "minimum": 1},
            "status": {"type": "string", "enum": ["repaired", "partial", "blocked"]},
            "diagnosis": {"type": "string"},
            "files_changed": {"type": "array", "items": {"type": "string"}},
            "verification_expected": {"type": "array", "items": {"type": "string"}},
            "residual_risks": {"type": "array", "items": {"type": "string"}},
            "confidence": copy.deepcopy(CONFIDENCE),
        },
    },
}


def schema_for(route: str) -> dict[str, Any]:
    try:
        return copy.deepcopy(SCHEMAS[route])
    except KeyError as exc:
        raise PolicyViolation(f"No structured-output schema for route: {route}") from exc


def _matches_type(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, True)


def validate_instance(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        types = expected if isinstance(expected, list) else [expected]
        if not any(_matches_type(value, kind) for kind in types):
            return [f"{path}: expected {types}, found {type(value).__name__}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}")
    if isinstance(value, str) and schema.get("pattern") and not re.match(schema["pattern"], value):
        errors.append(f"{path}: string does not match {schema['pattern']!r}")
    if isinstance(value, int) and "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{path}: value is below minimum {schema['minimum']}")
    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}: unexpected property {key!r}")
        for key, item in value.items():
            if key in properties:
                errors.extend(validate_instance(item, properties[key], f"{path}.{key}"))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: expected at least {schema['minItems']} items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(validate_instance(item, item_schema, f"{path}[{index}]"))
    return errors


def export_schemas(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name, schema in SCHEMAS.items():
        (destination / f"{name}.schema.json").write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


# A9-02: exactly the keywords validate_instance implements. Any other keyword
# in a schema would silently no-op, so the coverage gate rejects it.
SUPPORTED_KEYWORDS = frozenset(
    {
        "type",
        "const",
        "enum",
        "pattern",
        "minimum",
        "required",
        "properties",
        "additionalProperties",
        "minItems",
        "items",
    }
)
# Non-validation annotation keywords, carried for tooling metadata only and
# kept separate so an annotation can never masquerade as an enforced
# constraint.
META_KEYWORDS = frozenset({"$schema"})


def iter_schema_keywords(schema: dict[str, Any], path: str = "$"):
    """Yield (path, keyword) for every keyword in a schema, descending through
    the same positions validate_instance recurses into: properties values and
    the items subschema."""
    for key in schema:
        yield path, key
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, subschema in properties.items():
            if isinstance(subschema, dict):
                yield from iter_schema_keywords(subschema, f"{path}.properties.{name}")
    items = schema.get("items")
    if isinstance(items, dict):
        yield from iter_schema_keywords(items, f"{path}.items")


def assert_supported_keywords(schema: dict[str, Any], name: str = "schema") -> None:
    """Fail closed on any keyword validate_instance does not implement."""
    unsupported = sorted(
        {key for _, key in iter_schema_keywords(schema)} - SUPPORTED_KEYWORDS - META_KEYWORDS
    )
    if unsupported:
        raise PolicyViolation(
            f"Schema {name} uses unsupported keyword(s) that would silently no-op: {', '.join(unsupported)}"
        )
